"""Orquestrador do motor de comparação."""
from __future__ import annotations

import difflib
import logging
from typing import Dict, List, Optional, Tuple

from app.engine.align import AlignedBlock, align_blocks
from app.engine.classify import (
    classify_block_change,
    classify_image_change,
    classify_table_change,
    make_summary,
)
from app.engine.worddiff import formatting_style_diff_runs, runs_have_formatting_diff, worddiff_runs
from app.models import (
    NOISE_CATEGORIES,
    Block,
    BlockKind,
    Category,
    CellChange,
    Change,
    ChangeType,
    ComparisonResult,
    Document,
    Fragment,
    RenderBlock,
    Run,
    Stats,
    assign_section_paths,
)

logger = logging.getLogger(__name__)


logger = logging.getLogger(__name__)


def _layout_kwargs(block: Block) -> dict:
    return {
        "style_name": block.style_name,
        "align": block.align,
        "indent_left_pt": block.indent_left_pt,
        "indent_right_pt": block.indent_right_pt,
        "indent_first_pt": block.indent_first_pt,
        "space_before_pt": block.space_before_pt,
        "space_after_pt": block.space_after_pt,
    }


def _fragment_from_run(run: Run, op: str = "equal") -> Fragment:
    return Fragment(
        text=run.text,
        op=op,
        bold=run.bold,
        italic=run.italic,
        underline=run.underline,
        strike=run.strike,
        font_name=run.font_name,
        font_size_pt=run.font_size_pt,
    )


def _fragments_from_runs(runs: List[Run], op: str = "equal") -> List[Fragment]:
    return [_fragment_from_run(r, op) for r in runs]


def _preview_layout_from_doc(compare: Document, base: Document) -> dict:
    doc = compare if compare.default_font or compare.default_font_size_pt else base
    font = doc.default_font or "Times New Roman"
    size = doc.default_font_size_pt or 11.0
    width = compare.page_width_pt or base.page_width_pt
    height = compare.page_height_pt or base.page_height_pt
    orientation = "portrait"
    if width and height and float(width) > float(height):
        orientation = "landscape"
    return {
        "font_family": font,
        "font_size_pt": size,
        "line_height": 1.15,
        "source_fmt": doc.fmt,
        "page_width_pt": width,
        "page_height_pt": height,
        "orientation": orientation,
    }


def compare_documents(base: Document, compare: Document) -> ComparisonResult:
    """Compara dois documentos normalizados e retorna o resultado completo."""
    assign_section_paths(base)
    assign_section_paths(compare)

    result = ComparisonResult(
        base_path=base.source_path,
        compare_path=compare.source_path,
        base_title=base.title,
        compare_title=compare.title,
    )

    alignments = align_blocks(base.blocks, compare.blocks)
    change_id = 1
    render_blocks: List[RenderBlock] = []

    for aligned in alignments:
        rb, change, change_id = _process_alignment(
            aligned, base.blocks, compare.blocks, change_id
        )
        if rb is not None:
            render_blocks.append(rb)
        if change is not None:
            result.changes.append(change)

    result.render_blocks = render_blocks
    result.stats = _build_stats(result.changes, compare.blocks, render_blocks)
    result.preview_layout = _preview_layout_from_doc(compare, base)
    return result


def _process_alignment(
    aligned: AlignedBlock,
    base_blocks: List[Block],
    compare_blocks: List[Block],
    change_id: int,
) -> Tuple[Optional[RenderBlock], Optional[Change], int]:
    ct = aligned.change_type
    bi = aligned.base_index
    cj = aligned.compare_index

    if ct == ChangeType.EQUAL and bi is not None and cj is not None:
        block = compare_blocks[cj]
        return _render_equal(block), None, change_id

    if ct == ChangeType.INSERT and cj is not None:
        block = compare_blocks[cj]
        change, change_id = _make_block_change(
            change_id, ct, block, None, None, block
        )
        rb = _render_insert_delete(block, ct, change)
        return rb, change, change_id

    if ct == ChangeType.DELETE and bi is not None:
        block = base_blocks[bi]
        change, change_id = _make_block_change(
            change_id, ct, None, block, block, None
        )
        rb = _render_insert_delete(block, ct, change)
        return rb, change, change_id

    if bi is not None and cj is not None:
        base_block = base_blocks[bi]
        compare_block = compare_blocks[cj]
        if base_block.kind == BlockKind.TABLE or compare_block.kind == BlockKind.TABLE:
            return _diff_table_pair(
                base_block, compare_block, bi, cj, ct, change_id
            )
        if base_block.kind == BlockKind.IMAGE or compare_block.kind == BlockKind.IMAGE:
            return _diff_image_pair(
                base_block, compare_block, bi, cj, ct, change_id
            )
        return _diff_text_pair(
            base_block, compare_block, bi, cj, ct, change_id
        )

    return None, None, change_id


def _render_equal(block: Block) -> RenderBlock:
    fragments = _fragments_from_runs(block.runs, "equal")
    return RenderBlock(
        kind=block.kind,
        change_type=ChangeType.EQUAL,
        fragments=fragments,
        level=block.level,
        page=block.page,
        section_path=list(block.section_path),
        **_layout_kwargs(block),
    )


def _render_insert_delete(
    block: Block, change_type: ChangeType, change: Change
) -> RenderBlock:
    if block.kind == BlockKind.TABLE:
        rows, row_ops = _table_rows_as_fragments(block, change_type)
        return RenderBlock(
            kind=BlockKind.TABLE,
            change_type=change_type,
            category=change.category,
            rows=rows,
            row_ops=row_ops,
            page=block.page,
            section_path=list(block.section_path),
            change_id=change.id,
            **_layout_kwargs(block),
        )
    if block.kind == BlockKind.IMAGE:
        return RenderBlock(
            kind=BlockKind.IMAGE,
            change_type=change_type,
            category=change.category,
            page=block.page,
            section_path=list(block.section_path),
            change_id=change.id,
            **_layout_kwargs(block),
        )
    op = "insert" if change_type == ChangeType.INSERT else "delete"
    fragments = _fragments_from_runs(block.runs, op)
    # Parágrafo numerado EXCLUÍDO: o rótulo ("(a)") não está nos runs e o
    # parágrafo inserido no redline fiel não tem numeração automática — o
    # rótulo entra tachado junto. (Inserções mantêm o auto-número do Word.)
    if block.list_label and change_type == ChangeType.DELETE:
        fragments = [Fragment(text=block.list_label + "\t", op=op)] + fragments
    return RenderBlock(
        kind=block.kind,
        change_type=change_type,
        category=change.category,
        fragments=fragments,
        level=block.level,
        page=block.page,
        section_path=list(block.section_path),
        change_id=change.id,
        **_layout_kwargs(block),
    )


def _table_rows_as_fragments(
    block: Block, change_type: ChangeType
) -> Tuple[List[List[List[Fragment]]], List[str]]:
    op = "insert" if change_type == ChangeType.INSERT else "delete"
    row_op = "insert" if change_type == ChangeType.INSERT else "delete"
    rows: List[List[List[Fragment]]] = []
    row_ops: List[str] = []
    for row in block.rows:
        cell_frags: List[List[Fragment]] = []
        for cell in row:
            frags = [_fragment_from_run(r, op) for r in cell.runs]
            cell_frags.append(frags)
        rows.append(cell_frags)
        row_ops.append(row_op)
    return rows, row_ops


def _make_block_change(
    change_id: int,
    change_type: ChangeType,
    compare_block: Optional[Block],
    base_block: Optional[Block],
    old_block: Optional[Block],
    new_block: Optional[Block],
) -> Tuple[Change, int]:
    kind = BlockKind.PARAGRAPH
    if compare_block is not None:
        kind = compare_block.kind
    elif base_block is not None:
        kind = base_block.kind

    old_text = old_block.text if old_block else ""
    new_text = new_block.text if new_block else ""
    base_runs = old_block.runs if old_block else []
    compare_runs = new_block.runs if new_block else []

    category = classify_block_change(
        change_type, kind, old_text, new_text, base_runs, compare_runs
    )
    if kind == BlockKind.IMAGE:
        category = classify_image_change(change_type)
    elif kind == BlockKind.TABLE:
        category = classify_table_change()

    # Cabeçalho/rodapé: mudança real, mas de METADADOS — não compete com
    # conteúdo substantivo na atenção do revisor.
    for blk in (old_block, new_block):
        if blk is not None and blk.style_name in ("__header__", "__footer__"):
            category = Category.METADATA
            break

    section_path: List[str] = []
    page_base = None
    page_compare = None
    moved_from = None
    moved_to = None
    if compare_block is not None:
        section_path = list(compare_block.section_path)
        page_compare = compare_block.page
        moved_to = compare_block.index
    if base_block is not None:
        if not section_path:
            section_path = list(base_block.section_path)
        page_base = base_block.page
        moved_from = base_block.index

    change = Change(
        id=change_id,
        change_type=change_type,
        category=category,
        section_path=section_path,
        page_base=page_base,
        page_compare=page_compare,
        old_text=old_text,
        new_text=new_text,
        summary=make_summary(category, change_type, kind),
        moved_from_index=moved_from,
        moved_to_index=moved_to,
    )
    return change, change_id + 1


def _diff_text_pair(
    base_block: Block,
    compare_block: Block,
    bi: int,
    cj: int,
    change_type: ChangeType,
    change_id: int,
) -> Tuple[RenderBlock, Change, int]:
    # Renumeração automática ("(a)" → "(b)"): o rótulo não existe nos runs —
    # injeta pseudo-runs para o diff marcar a mudança (regra do produto:
    # alteração de numeração de cláusula/item é relevante e deve aparecer).
    label_changed = (base_block.list_label or "") != (compare_block.list_label or "")
    base_runs = base_block.runs
    compare_runs = compare_block.runs
    if label_changed:
        if base_block.list_label:
            base_runs = [Run(text=base_block.list_label + "\t")] + base_runs
        if compare_block.list_label:
            compare_runs = [Run(text=compare_block.list_label + "\t")] + compare_runs

    if (
        change_type != ChangeType.EQUAL
        and runs_have_formatting_diff(base_runs, compare_runs)
    ):
        fragments = formatting_style_diff_runs(base_runs, compare_runs)
    else:
        fragments = worddiff_runs(base_runs, compare_runs)
    if change_type == ChangeType.EQUAL:
        fragments = [
            Fragment(
                text=f.text, op="equal",
                bold=f.bold, italic=f.italic,
                underline=f.underline, strike=f.strike,
                font_name=f.font_name, font_size_pt=f.font_size_pt,
            )
            for f in fragments
        ]

    category = classify_block_change(
        change_type,
        compare_block.kind,
        base_block.text,
        compare_block.text,
        base_block.runs,
        compare_block.runs,
    )
    # Cabeçalho/rodapé pareado: metadados (mesma regra do caminho insert/delete).
    for blk in (base_block, compare_block):
        if blk.style_name in ("__header__", "__footer__"):
            category = Category.METADATA
            break

    old_text = base_block.text
    new_text = compare_block.text
    summary = make_summary(category, change_type, compare_block.kind)
    if label_changed:
        old_label = base_block.list_label or "—"
        new_label = compare_block.list_label or "—"
        if base_block.normalized_text() == compare_block.normalized_text():
            # Só a numeração mudou: relevante (pode indicar item faltando ou
            # referência quebrada) — nunca classificar como ruído.
            category = Category.CONTENT
            summary = "Numeração alterada de %s para %s" % (old_label, new_label)
        else:
            summary = "%s Numeração: %s → %s" % (summary, old_label, new_label)
        if base_block.list_label:
            old_text = "%s\t%s" % (base_block.list_label, old_text)
        if compare_block.list_label:
            new_text = "%s\t%s" % (compare_block.list_label, new_text)

    change = Change(
        id=change_id,
        change_type=change_type,
        category=category,
        section_path=list(compare_block.section_path),
        page_base=base_block.page,
        page_compare=compare_block.page,
        old_text=old_text,
        new_text=new_text,
        summary=summary,
        moved_from_index=bi if change_type in (ChangeType.MOVE, ChangeType.MOVE_MODIFY) else None,
        moved_to_index=cj if change_type in (ChangeType.MOVE, ChangeType.MOVE_MODIFY) else None,
    )
    rb = RenderBlock(
        kind=compare_block.kind,
        change_type=change_type,
        category=category,
        fragments=fragments,
        level=compare_block.level,
        page=compare_block.page,
        section_path=list(compare_block.section_path),
        change_id=change.id,
        list_label=compare_block.list_label if label_changed else None,
        **_layout_kwargs(compare_block),
    )
    return rb, change, change_id + 1


def _diff_image_pair(
    base_block: Block,
    compare_block: Block,
    bi: int,
    cj: int,
    change_type: ChangeType,
    change_id: int,
) -> Tuple[RenderBlock, Change, int]:
    if base_block.image_hash == compare_block.image_hash and change_type == ChangeType.EQUAL:
        return _render_equal(compare_block), None, change_id

    effective_type = change_type
    if base_block.image_hash != compare_block.image_hash:
        if change_type in (ChangeType.MOVE, ChangeType.MOVE_MODIFY):
            effective_type = ChangeType.MOVE_MODIFY
        elif change_type == ChangeType.EQUAL:
            effective_type = ChangeType.MODIFY

    category = classify_image_change(effective_type)
    change = Change(
        id=change_id,
        change_type=effective_type,
        category=category,
        section_path=list(compare_block.section_path),
        page_base=base_block.page,
        page_compare=compare_block.page,
        old_text=base_block.image_hash or "",
        new_text=compare_block.image_hash or "",
        summary=make_summary(category, effective_type, BlockKind.IMAGE),
        moved_from_index=bi if effective_type in (ChangeType.MOVE, ChangeType.MOVE_MODIFY) else None,
        moved_to_index=cj if effective_type in (ChangeType.MOVE, ChangeType.MOVE_MODIFY) else None,
    )
    rb = RenderBlock(
        kind=BlockKind.IMAGE,
        change_type=effective_type,
        category=category,
        page=compare_block.page,
        section_path=list(compare_block.section_path),
        change_id=change.id,
        **_layout_kwargs(compare_block),
    )
    return rb, change, change_id + 1


def _row_text(row: List) -> str:
    return " | ".join(c.text for c in row)


def _align_table_rows(
    base_rows: List[List], compare_rows: List[List]
) -> List[Tuple[Optional[int], Optional[int], str]]:
    """Alinha linhas de tabela; retorna (base_idx, compare_idx, op)."""
    base_texts = [_row_text(r) for r in base_rows]
    compare_texts = [_row_text(r) for r in compare_rows]
    n = len(base_rows)
    m = len(compare_rows)

    base_status = [None] * n
    compare_status = [None] * m
    base_pair = [-1] * n
    compare_pair = [-1] * m

    matcher = difflib.SequenceMatcher(None, base_texts, compare_texts, autojunk=False)
    for bi, bj, size in matcher.get_matching_blocks():
        for offset in range(size):
            i = bi + offset
            j = bj + offset
            base_status[i] = "equal"
            compare_status[j] = "equal"
            base_pair[i] = j
            compare_pair[j] = i

    # Similaridade CONFINADA aos vãos entre âncoras, melhor score primeiro,
    # sem cruzamento — espelho do alinhador de blocos (o ganancioso global
    # com trava monotônica pareava "Seal"↔"Share" e deixava as definições
    # Pre-Seed-3/4 como delete+insert; ver tests/fixtures/memorandum).
    anchors = sorted(
        (bi, base_pair[bi]) for bi in range(n) if base_status[bi] is not None
    )
    prev_bi, prev_cj = -1, -1
    for a_bi, a_cj in anchors + [(n, m)]:
        base_orphans = [
            bi for bi in range(prev_bi + 1, a_bi) if base_status[bi] is None
        ]
        compare_orphans = [
            cj for cj in range(prev_cj + 1, a_cj) if compare_status[cj] is None
        ]
        prev_bi, prev_cj = a_bi, a_cj
        if not base_orphans or not compare_orphans:
            continue
        scored = []
        for bi in base_orphans:
            for cj in compare_orphans:
                ratio = difflib.SequenceMatcher(
                    None, base_texts[bi], compare_texts[cj], autojunk=False
                ).ratio()
                if ratio >= 0.55:
                    scored.append((ratio, bi, cj))
        scored.sort(key=lambda item: (-item[0], item[1], item[2]))
        accepted: List[Tuple[int, int]] = []
        for ratio, bi, cj in scored:
            if base_status[bi] is not None or compare_status[cj] is not None:
                continue
            if any((bi2 - bi) * (cj2 - cj) < 0 for bi2, cj2 in accepted):
                continue
            accepted.append((bi, cj))
            base_status[bi] = "modify"
            compare_status[cj] = "modify"
            base_pair[bi] = cj
            compare_pair[cj] = bi

    for bi in range(n):
        if base_status[bi] is None:
            base_status[bi] = "delete"
    for cj in range(m):
        if compare_status[cj] is None:
            compare_status[cj] = "insert"

    aligned: List[Tuple[Optional[int], Optional[int], str]] = []
    seen_compare: set = set()
    for bi in range(n):
        op = base_status[bi]
        cj = base_pair[bi]
        if op == "delete":
            aligned.append((bi, None, "delete"))
        elif cj >= 0 and cj not in seen_compare:
            aligned.append((bi, cj, op or "equal"))
            seen_compare.add(cj)
    for cj in range(m):
        if compare_status[cj] == "insert":
            aligned.append((None, cj, "insert"))

    def sort_key(item: Tuple[Optional[int], Optional[int], str]) -> tuple:
        bi, cj, _op = item
        if cj is not None:
            return (cj, 0, bi if bi is not None else -1)
        anchor = m
        for j in range(m):
            if compare_pair[j] >= 0 and compare_pair[j] > (bi or 0):
                anchor = j
                break
        return (anchor, -1, bi or 0)

    return sorted(aligned, key=sort_key)


def _diff_table_pair(
    base_block: Block,
    compare_block: Block,
    bi: int,
    cj: int,
    change_type: ChangeType,
    change_id: int,
) -> Tuple[RenderBlock, Change, int]:
    row_alignments = _align_table_rows(base_block.rows, compare_block.rows)
    render_rows: List[List[List[Fragment]]] = []
    row_ops: List[str] = []
    cell_changes: List[CellChange] = []
    has_change = change_type != ChangeType.EQUAL

    for base_idx, compare_idx, row_op in row_alignments:
        if row_op == "delete" and base_idx is not None:
            row = base_block.rows[base_idx]
            cell_frags = [
                [Fragment(text=r.text, op="delete", bold=r.bold, italic=r.italic,
                          underline=r.underline, strike=r.strike) for r in cell.runs]
                for cell in row
            ]
            render_rows.append(cell_frags)
            row_ops.append("delete")
            has_change = True
            continue

        if row_op == "insert" and compare_idx is not None:
            row = compare_block.rows[compare_idx]
            cell_frags = [
                [Fragment(text=r.text, op="insert", bold=r.bold, italic=r.italic,
                          underline=r.underline, strike=r.strike) for r in cell.runs]
                for cell in row
            ]
            render_rows.append(cell_frags)
            row_ops.append("insert")
            has_change = True
            continue

        if base_idx is not None and compare_idx is not None:
            base_row = base_block.rows[base_idx]
            compare_row = compare_block.rows[compare_idx]
            cell_frags_row: List[List[Fragment]] = []
            max_cols = max(len(base_row), len(compare_row))
            row_changed = row_op == "modify"

            for col in range(max_cols):
                base_cell = base_row[col] if col < len(base_row) else None
                compare_cell = compare_row[col] if col < len(compare_row) else None
                old_text = base_cell.text if base_cell else ""
                new_text = compare_cell.text if compare_cell else ""
                base_runs = base_cell.runs if base_cell else []
                compare_runs = compare_cell.runs if compare_cell else []

                if row_op == "equal" and old_text == new_text:
                    frags = [
                        Fragment(text=r.text, op="equal", bold=r.bold, italic=r.italic,
                                 underline=r.underline, strike=r.strike)
                        for r in compare_runs
                    ]
                else:
                    frags = worddiff_runs(base_runs, compare_runs)
                    if old_text != new_text or row_op == "modify":
                        row_changed = True
                        cell_ct = ChangeType.MODIFY
                        if not old_text and new_text:
                            cell_ct = ChangeType.INSERT
                        elif old_text and not new_text:
                            cell_ct = ChangeType.DELETE
                        cell_changes.append(
                            CellChange(
                                row=len(render_rows),
                                col=col,
                                change_type=cell_ct,
                                old_text=old_text,
                                new_text=new_text,
                            )
                        )

                cell_frags_row.append(frags)

            render_rows.append(cell_frags_row)
            final_op = "modify" if row_changed else "equal"
            row_ops.append(final_op)
            if row_changed:
                has_change = True

    effective_type = change_type
    if has_change and change_type == ChangeType.EQUAL:
        effective_type = ChangeType.MODIFY
    if not has_change:
        rb = RenderBlock(
            kind=BlockKind.TABLE,
            change_type=ChangeType.EQUAL,
            rows=render_rows,
            row_ops=row_ops,
            page=compare_block.page,
            section_path=list(compare_block.section_path),
            **_layout_kwargs(compare_block),
        )
        return rb, None, change_id

    category = classify_table_change()
    change = Change(
        id=change_id,
        change_type=effective_type,
        category=category,
        section_path=list(compare_block.section_path),
        page_base=base_block.page,
        page_compare=compare_block.page,
        old_text=base_block.text,
        new_text=compare_block.text,
        summary=make_summary(category, effective_type, BlockKind.TABLE),
        cell_changes=cell_changes,
        moved_from_index=bi if effective_type in (ChangeType.MOVE, ChangeType.MOVE_MODIFY) else None,
        moved_to_index=cj if effective_type in (ChangeType.MOVE, ChangeType.MOVE_MODIFY) else None,
    )
    rb = RenderBlock(
        kind=BlockKind.TABLE,
        change_type=effective_type,
        category=category,
        rows=render_rows,
        row_ops=row_ops,
        page=compare_block.page,
        section_path=list(compare_block.section_path),
        change_id=change.id,
        **_layout_kwargs(compare_block),
    )
    return rb, change, change_id + 1


def _count_fragment_runs(fragments: List["Fragment"]) -> Tuple[int, int]:
    """Conta TRECHOS CONTÍNUOS de inserção e de exclusão numa lista de
    fragmentos. Uma sequência consecutiva de fragmentos "insert" conta 1
    inserção; idem para "delete". "equal"/"format" quebram o trecho.

    Ex.: [equal, delete, insert, equal, insert] → (2 inserções, 1 exclusão).
    """
    ins = dele = 0
    prev = ""
    for frag in fragments or ():
        op = getattr(frag, "op", "equal")
        if op == "insert" and prev != "insert":
            ins += 1
        elif op == "delete" and prev != "delete":
            dele += 1
        prev = op
    return ins, dele


def _count_block_runs(block: "RenderBlock") -> Tuple[int, int]:
    """Trechos contínuos de inserção/exclusão de UM bloco renderizado.

    - Tabela: linha inteira nova/removida conta 1; nas demais linhas, conta
      os trechos dentro de cada célula (valor de célula alterado = 1 del + 1
      ins).
    - Parágrafo/título/imagem: conta os trechos nos fragmentos; se o bloco
      não tem fragmentos nem linhas (ex.: imagem só com marcador), usa o tipo
      do bloco (INSERT/DELETE) como 1 trecho.
    """
    ins = dele = 0
    if block.rows:
        for idx, row in enumerate(block.rows):
            rop = block.row_ops[idx] if idx < len(block.row_ops) else "equal"
            if rop == "insert":
                ins += 1
                continue
            if rop == "delete":
                dele += 1
                continue
            for cell in row:  # cada célula é uma lista de fragmentos
                ci, cd = _count_fragment_runs(cell)
                ins += ci
                dele += cd
        return ins, dele

    if block.fragments:
        return _count_fragment_runs(block.fragments)

    # Bloco sem texto marcável (ex.: imagem): usa o tipo do bloco.
    if block.change_type == ChangeType.INSERT:
        return 1, 0
    if block.change_type == ChangeType.DELETE:
        return 0, 1
    return 0, 0


def _build_stats(
    changes: List[Change],
    compare_blocks: List[Block],
    render_blocks: Optional[List["RenderBlock"]] = None,
) -> Stats:
    stats = Stats()
    by_category: Dict[str, int] = {}

    # Categorias, movimentações, modificações e páginas: por Change (bloco).
    changed_pages: set = set()
    for change in changes:
        cat_key = change.category.value
        by_category[cat_key] = by_category.get(cat_key, 0) + 1

        if change.change_type in (ChangeType.MOVE, ChangeType.MOVE_MODIFY):
            stats.moves += 1
        elif change.change_type == ChangeType.MODIFY:
            stats.modifications += 1

        if change.category == Category.FORMATTING:
            stats.formatting_changes += 1
        elif change.category in NOISE_CATEGORIES:
            stats.noise_changes += 1
        elif change.category == Category.CONTENT:
            stats.content_changes += 1
        elif change.category == Category.TABLE:
            stats.table_changes += 1
        elif change.category == Category.IMAGE:
            stats.image_changes += 1

        if change.page_compare is not None:
            changed_pages.add(change.page_compare)

    # Inserções/exclusões: TRECHOS CONTÍNUOS marcados no redline (inclui inline,
    # células e linhas de tabela) — não só parágrafos inteiros. Blocos movidos
    # contam só como movimentação, sem inflar ins/del.
    for block in render_blocks or ():
        if block.change_type in (ChangeType.MOVE, ChangeType.MOVE_MODIFY):
            continue
        bi, bd = _count_block_runs(block)
        stats.insertions += bi
        stats.deletions += bd

    # Total do Summary = inserções + exclusões + movimentações.
    stats.total_changes = stats.insertions + stats.deletions + stats.moves
    stats.by_category = by_category
    stats.changed_pages = sorted(changed_pages)
    return stats
