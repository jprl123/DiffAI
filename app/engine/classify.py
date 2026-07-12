"""Classificação de mudanças: conteúdo, formatação ou ruído rotineiro."""
from __future__ import annotations

import re
from typing import List, Optional

from app.engine.worddiff import runs_have_formatting_diff
from app.models import BlockKind, Category, ChangeType, Run

_DATE_PATTERNS = [
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(
        r"\b\d{1,2}\s+de\s+"
        r"(janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
        r"\s+de\s+\d{4}\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
        r"\s+de\s+\d{4}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b", re.IGNORECASE),
]

_VERSION_PATTERNS = [
    re.compile(r"\bvers[aã]o\s+\d+(?:\.\d+)*\b", re.IGNORECASE),
    re.compile(r"\bv\d+(?:\.\d+)*\b", re.IGNORECASE),
    re.compile(r"\brev\.?\s*[a-z0-9]+\b", re.IGNORECASE),
    re.compile(r"\brevis[aã]o\s+\d+\b", re.IGNORECASE),
    re.compile(r"\bvers[aã]o\s+\d+\.\d+\b", re.IGNORECASE),
]

_PAGENUM_PATTERNS = [
    re.compile(r"\bp[aá]gina\s+\d+\s+de\s+\d+\b", re.IGNORECASE),
    re.compile(r"\bp\.?\s*\d+\b", re.IGNORECASE),
    re.compile(r"\bpage\s+\d+\s+of\s+\d+\b", re.IGNORECASE),
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "")


def _strip_noise(text: str, patterns: List[re.Pattern]) -> str:
    result = text
    for pattern in patterns:
        result = pattern.sub("", result)
    return result


def _only_noise_remains(old_text: str, new_text: str, patterns: List[re.Pattern]) -> bool:
    old_norm = _normalize(old_text)
    new_norm = _normalize(new_text)
    if old_norm == new_norm:
        return False
    old_stripped = _normalize(_strip_noise(old_norm, patterns))
    new_stripped = _normalize(_strip_noise(new_norm, patterns))
    return old_stripped == new_stripped


def _only_combined_noise(old_text: str, new_text: str) -> bool:
    """True se a diferença se resume a datas, versões e/ou numeração de página."""
    all_patterns = _DATE_PATTERNS + _VERSION_PATTERNS + _PAGENUM_PATTERNS
    return _only_noise_remains(old_text, new_text, all_patterns)


def _combined_noise_category(old_text: str, new_text: str) -> Category:
    """Escolhe a categoria de ruído quando há múltiplos padrões na mesma linha."""
    old_norm = _normalize(old_text)
    new_norm = _normalize(new_text)
    if _only_noise_remains(old_text, new_text, _VERSION_PATTERNS):
        return Category.NOISE_VERSION
    if _only_noise_remains(old_text, new_text, _DATE_PATTERNS):
        return Category.NOISE_DATE
    if _only_noise_remains(old_text, new_text, _PAGENUM_PATTERNS):
        return Category.NOISE_PAGENUM
    if any(p.search(old_norm) or p.search(new_norm) for p in _VERSION_PATTERNS):
        return Category.NOISE_VERSION
    if any(p.search(old_norm) or p.search(new_norm) for p in _DATE_PATTERNS):
        return Category.NOISE_DATE
    return Category.NOISE_VERSION


def _only_whitespace_diff(old_text: str, new_text: str) -> bool:
    return _collapse_ws(old_text).strip() == _collapse_ws(new_text).strip() and old_text != new_text


def _only_punct_case_diff(old_text: str, new_text: str) -> bool:
    old_alpha = re.sub(r"[^\w]+", "", old_text, flags=re.UNICODE).casefold()
    new_alpha = re.sub(r"[^\w]+", "", new_text, flags=re.UNICODE).casefold()
    return old_alpha == new_alpha and _normalize(old_text) != _normalize(new_text)


def classify_block_change(
    change_type: ChangeType,
    kind: BlockKind,
    old_text: str,
    new_text: str,
    base_runs: Optional[List[Run]] = None,
    compare_runs: Optional[List[Run]] = None,
) -> Category:
    """Atribui UMA categoria a uma mudança de bloco."""
    if kind == BlockKind.IMAGE:
        return Category.IMAGE
    if kind == BlockKind.TABLE:
        return Category.TABLE

    if change_type in (ChangeType.INSERT, ChangeType.DELETE, ChangeType.MOVE):
        if _only_noise_remains(old_text, new_text, _DATE_PATTERNS):
            return Category.NOISE_DATE
        if _only_noise_remains(old_text, new_text, _VERSION_PATTERNS):
            return Category.NOISE_VERSION
        if _only_noise_remains(old_text, new_text, _PAGENUM_PATTERNS):
            return Category.NOISE_PAGENUM
        return Category.CONTENT

    if change_type in (ChangeType.MODIFY, ChangeType.MOVE_MODIFY):
        if base_runs is not None and compare_runs is not None:
            if runs_have_formatting_diff(base_runs, compare_runs):
                return Category.FORMATTING
        if _normalize(old_text) == _normalize(new_text):
            if change_type in (ChangeType.MOVE, ChangeType.MOVE_MODIFY):
                return Category.CONTENT
            return Category.FORMATTING
        if _only_combined_noise(old_text, new_text):
            return _combined_noise_category(old_text, new_text)
        if _only_whitespace_diff(old_text, new_text):
            return Category.NOISE_WHITESPACE
        if _only_punct_case_diff(old_text, new_text):
            return Category.NOISE_PUNCT
        if _only_noise_remains(old_text, new_text, _DATE_PATTERNS):
            return Category.NOISE_DATE
        if _only_noise_remains(old_text, new_text, _VERSION_PATTERNS):
            return Category.NOISE_VERSION
        if _only_noise_remains(old_text, new_text, _PAGENUM_PATTERNS):
            return Category.NOISE_PAGENUM
        return Category.CONTENT

    return Category.CONTENT


def classify_table_change() -> Category:
    return Category.TABLE


def classify_image_change(change_type: ChangeType) -> Category:
    return Category.IMAGE


def make_summary(category: Category, change_type: ChangeType, kind: BlockKind) -> str:
    """Descrição curta legível em pt-BR."""
    if kind == BlockKind.IMAGE:
        if change_type == ChangeType.INSERT:
            return "Imagem inserida"
        if change_type == ChangeType.DELETE:
            return "Imagem removida"
        if change_type in (ChangeType.MOVE, ChangeType.MOVE_MODIFY):
            return "Imagem movida"
        return "Imagem substituída"
    if kind == BlockKind.TABLE:
        if change_type == ChangeType.INSERT:
            return "Tabela inserida"
        if change_type == ChangeType.DELETE:
            return "Tabela removida"
        return "Tabela alterada"
    if change_type == ChangeType.INSERT:
        return "Parágrafo inserido"
    if change_type == ChangeType.DELETE:
        return "Parágrafo removido"
    if change_type == ChangeType.MOVE:
        return "Parágrafo movido"
    if change_type == ChangeType.MOVE_MODIFY:
        return "Parágrafo movido e alterado"
    if category == Category.FORMATTING:
        return "Formatação alterada"
    if category == Category.NOISE_DATE:
        return "Data atualizada"
    if category == Category.NOISE_VERSION:
        return "Versão atualizada"
    if category == Category.NOISE_PAGENUM:
        return "Numeração de página alterada"
    if category == Category.NOISE_WHITESPACE:
        return "Espaçamento alterado"
    if category == Category.NOISE_PUNCT:
        return "Pontuação ou caixa alterada"
    return "Texto alterado"
