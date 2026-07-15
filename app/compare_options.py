"""Opções de comparação — filtro de blocos/alterações no pipeline.

Espelham toggles da UI (estilo Draftable). Defaults True = comparar tudo
o que o motor já sabe fazer. Opções que o extrator não cobre (footnotes,
comments, watermarks, math…) ficam de fora desta lista.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List

from app.models import (
    BlockKind,
    Category,
    Change,
    ChangeType,
    ComparisonResult,
    Document,
)

# Defaults persistidos em settings e usados se a chave não vier no request.
COMPARE_OPTION_DEFAULTS: Dict[str, bool] = {
    "detect_moves": True,
    "include_formatting": True,
    "compare_headers": True,
    "compare_footers": True,
    "compare_tables": True,
    "compare_images": True,
}

COMPARE_OPTION_KEYS = tuple(COMPARE_OPTION_DEFAULTS.keys())


def coerce_compare_options(raw: Any) -> Dict[str, bool]:
    """Mescla ``raw`` sobre os defaults; aceita só chaves conhecidas."""
    out = dict(COMPARE_OPTION_DEFAULTS)
    if not isinstance(raw, dict):
        return out
    for key in COMPARE_OPTION_KEYS:
        if key in raw and raw[key] is not None and str(raw[key]).strip() != "":
            val = raw[key]
            if isinstance(val, bool):
                out[key] = val
            else:
                out[key] = str(val).strip().lower() in {
                    "1", "true", "yes", "on", "sim", "verdadeiro",
                }
    return out


def filter_document(doc: Document, options: Dict[str, bool]) -> Document:
    """Remove blocos que o usuário pediu para ignorar (pré-compare)."""
    opts = coerce_compare_options(options)
    kept = []
    for block in doc.blocks:
        style = block.style_name or ""
        if style == "__header__" and not opts["compare_headers"]:
            continue
        if style == "__footer__" and not opts["compare_footers"]:
            continue
        if block.kind == BlockKind.TABLE and not opts["compare_tables"]:
            continue
        if block.kind == BlockKind.IMAGE and not opts["compare_images"]:
            continue
        kept.append(block)
    if len(kept) == len(doc.blocks):
        return doc
    filtered = copy.copy(doc)
    filtered.blocks = kept
    return filtered


def filter_result(
    result: ComparisonResult,
    options: Dict[str, bool],
) -> ComparisonResult:
    """Pós-compare: tira moves e/ou formatação se desligados."""
    opts = coerce_compare_options(options)
    if opts["detect_moves"] and opts["include_formatting"]:
        return result

    changes: List[Change] = []
    for change in result.changes:
        if not opts["detect_moves"] and change.change_type in (
            ChangeType.MOVE,
            ChangeType.MOVE_MODIFY,
        ):
            continue
        if (
            not opts["include_formatting"]
            and change.category == Category.FORMATTING
        ):
            continue
        changes.append(change)

    if len(changes) == len(result.changes):
        return result

    from app.engine.compare import _build_stats

    result.changes = changes
    result.stats = _build_stats(changes, [])
    # Render blocks also carry formatting/move markup — drop matching ones.
    if result.render_blocks:
        kept_rb = []
        for rb in result.render_blocks:
            if (
                not opts["detect_moves"]
                and rb.change_type in (ChangeType.MOVE, ChangeType.MOVE_MODIFY)
            ):
                continue
            if (
                not opts["include_formatting"]
                and rb.category == Category.FORMATTING
            ):
                continue
            kept_rb.append(rb)
        result.render_blocks = kept_rb
    return result
