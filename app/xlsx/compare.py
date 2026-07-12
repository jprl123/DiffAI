"""Motor de diff estrutural entre duas planilhas."""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal, Optional, Set, Tuple

from app.xlsx.extract import XlsxCell, XlsxSheet, extract_sheets
from app.xlsx.models import SummaryStats

CellStatus = Literal["equal", "insert", "delete", "modified"]
RowStatus = Literal["equal", "insert", "delete", "replace"]


@dataclass
class CellDiff:
    row: int
    col: int
    base_cell: Optional[XlsxCell]
    compare_cell: Optional[XlsxCell]
    status: CellStatus


@dataclass
class RowDiff:
    status: RowStatus
    base_row_index: Optional[int]
    compare_row_index: Optional[int]
    cells: List[CellDiff] = field(default_factory=list)


@dataclass
class SheetDiff:
    name: str
    rows: List[RowDiff] = field(default_factory=list)
    base_only: bool = False
    compare_only: bool = False
    col_map: List[Tuple[Optional[int], Optional[int]]] = field(default_factory=list)


@dataclass
class XlsxStats:
    row_add: int = 0
    row_del: int = 0
    col_add: int = 0
    col_del: int = 0
    value_changes: int = 0
    formula_and_value_changes: int = 0
    formula_only_changes: int = 0
    modified_cells: int = 0
    emptied_cells: int = 0


@dataclass
class XlsxDiff:
    sheets: List[SheetDiff] = field(default_factory=list)
    summary: SummaryStats = field(default_factory=SummaryStats)
    stats: XlsxStats = field(default_factory=XlsxStats)
    base_filename: str = ""
    compare_filename: str = ""


def compare_xlsx(
    base_bytes: bytes,
    compare_bytes: bytes,
    base_filename: str = "",
    compare_filename: str = "",
) -> XlsxDiff:
    base_sheets = extract_sheets(base_bytes)
    compare_sheets = extract_sheets(compare_bytes)
    compare_by_name = {s.name: s for s in compare_sheets}
    used_names: Set[str] = set()

    sheet_diffs: List[SheetDiff] = []
    deletions = 0
    insertions = 0
    stats = XlsxStats()

    for base_sheet in base_sheets:
        compare_sheet = compare_by_name.get(base_sheet.name)
        if compare_sheet is None:
            diff = _sheet_as_deleted(base_sheet)
            sheet_diffs.append(diff)
            deletions += _count_nonempty_rows(base_sheet)
            stats.row_del += _count_nonempty_rows(base_sheet)
            continue
        used_names.add(base_sheet.name)
        diff = _compare_sheets(base_sheet, compare_sheet)
        sheet_diffs.append(diff)

        for base_c, compare_c in diff.col_map:
            if base_c is None and compare_c is not None:
                stats.col_add += 1
            elif compare_c is None and base_c is not None:
                stats.col_del += 1

        for row in diff.rows:
            if row.status == "insert":
                insertions += 1
                stats.row_add += 1
            elif row.status == "delete":
                deletions += 1
                stats.row_del += 1
            elif row.status == "replace":
                for cell in row.cells:
                    base_text = cell.base_cell.value if cell.base_cell else ""
                    compare_text = cell.compare_cell.value if cell.compare_cell else ""
                    base_is_formula = bool(cell.base_cell and cell.base_cell.is_formula)
                    compare_is_formula = bool(cell.compare_cell and cell.compare_cell.is_formula)
                    if cell.status == "modified":
                        deletions += 1
                        insertions += 1
                        stats.modified_cells += 1
                        if base_is_formula or compare_is_formula:
                            if base_is_formula and compare_is_formula:
                                stats.formula_and_value_changes += 1
                            else:
                                stats.formula_only_changes += 1
                        else:
                            stats.value_changes += 1
                    elif cell.status == "insert":
                        insertions += 1
                        stats.modified_cells += 1
                        if compare_text:
                            stats.value_changes += 1
                    elif cell.status == "delete":
                        deletions += 1
                        stats.modified_cells += 1
                        if base_text:
                            stats.emptied_cells += 1
                            stats.value_changes += 1

    for compare_sheet in compare_sheets:
        if compare_sheet.name in used_names:
            continue
        diff = _sheet_as_inserted(compare_sheet)
        sheet_diffs.append(diff)
        added = _count_nonempty_rows(compare_sheet)
        insertions += added
        stats.row_add += added

    summary = SummaryStats(
        deletions=deletions,
        insertions=insertions,
        moved=0,
        changed_pages=[],
        compared_on=datetime.now().strftime("%d/%m/%Y"),
    )

    return XlsxDiff(
        sheets=sheet_diffs,
        summary=summary,
        stats=stats,
        base_filename=base_filename,
        compare_filename=compare_filename,
    )


def _count_nonempty_rows(sheet: XlsxSheet) -> int:
    return sum(1 for row in sheet.rows if any(cell.value for cell in row))


def _sheet_as_deleted(sheet: XlsxSheet) -> SheetDiff:
    diff = SheetDiff(name=sheet.name, base_only=True)
    for row_idx, row in enumerate(sheet.rows):
        diff.rows.append(
            RowDiff(
                status="delete",
                base_row_index=row_idx,
                compare_row_index=None,
                cells=[
                    CellDiff(
                        row=row_idx + 1,
                        col=cell.col,
                        base_cell=cell,
                        compare_cell=None,
                        status="delete",
                    )
                    for cell in row
                ],
            )
        )
    return diff


def _sheet_as_inserted(sheet: XlsxSheet) -> SheetDiff:
    diff = SheetDiff(name=sheet.name, compare_only=True)
    for row_idx, row in enumerate(sheet.rows):
        diff.rows.append(
            RowDiff(
                status="insert",
                base_row_index=None,
                compare_row_index=row_idx,
                cells=[
                    CellDiff(
                        row=row_idx + 1,
                        col=cell.col,
                        base_cell=None,
                        compare_cell=cell,
                        status="insert",
                    )
                    for cell in row
                ],
            )
        )
    return diff


def _compare_sheets(base: XlsxSheet, compare: XlsxSheet) -> SheetDiff:
    diff = SheetDiff(name=base.name)
    col_map = _align_columns(base, compare)
    diff.col_map = col_map

    common_base_cols = [b for b, c in col_map if b is not None and c is not None]
    common_compare_cols = [c for b, c in col_map if b is not None and c is not None]

    base_fps = _common_col_fingerprints(base, common_base_cols)
    compare_fps = _common_col_fingerprints(compare, common_compare_cols)
    matcher = difflib.SequenceMatcher(None, base_fps, compare_fps, autojunk=False)

    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                diff.rows.append(_aligned_row_diff(base, compare, i, j, col_map, is_equal=True))
        elif op == "delete":
            for i in range(i1, i2):
                diff.rows.append(_row_as_delete(base, i))
        elif op == "insert":
            for j in range(j1, j2):
                diff.rows.append(_row_as_insert(compare, j))
        elif op == "replace":
            base_range = list(range(i1, i2))
            compare_range = list(range(j1, j2))
            pairs, extra_base, extra_compare = _best_row_alignment(
                base_range, compare_range, base_fps, compare_fps
            )
            all_indices = sorted(
                [("pair", bi, ci) for bi, ci in pairs]
                + [("delete", bi, None) for bi in extra_base]
                + [("insert", None, ci) for ci in extra_compare],
                key=lambda t: _replace_item_sort_key(t, pairs),
            )
            for kind, bi, ci in all_indices:
                if kind == "pair":
                    diff.rows.append(_aligned_row_diff(base, compare, bi, ci, col_map))
                elif kind == "delete":
                    diff.rows.append(_row_as_delete(base, bi))
                elif kind == "insert":
                    diff.rows.append(_row_as_insert(compare, ci))

    return diff


def _replace_item_sort_key(
    item: Tuple[str, Optional[int], Optional[int]],
    pairs: List[Tuple[int, int]],
) -> Tuple[float, int]:
    kind, bi, ci = item
    if ci is not None:
        return (float(ci), 0 if kind == "pair" else 1)
    assert bi is not None
    best_ci: Optional[float] = None
    for pair_bi, pair_ci in sorted(pairs, key=lambda p: p[0]):
        if pair_bi > bi:
            best_ci = pair_ci - 0.1
            break
    if best_ci is None:
        if pairs:
            best_ci = max(ci for _, ci in pairs) + 0.5
        else:
            best_ci = 9999.0
    return (best_ci, 2)


def _best_row_alignment(
    base_range: List[int],
    compare_range: List[int],
    base_fps: List[str],
    compare_fps: List[str],
) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
    if not base_range or not compare_range:
        return [], list(base_range), list(compare_range)

    matches: List[Tuple[float, int, int]] = []
    for bi in base_range:
        for ci in compare_range:
            ratio = difflib.SequenceMatcher(None, base_fps[bi], compare_fps[ci]).ratio()
            matches.append((ratio, bi, ci))

    matches.sort(reverse=True)
    paired_base: Set[int] = set()
    paired_compare: Set[int] = set()
    pairs: List[Tuple[int, int]] = []
    min_similarity = 0.60

    for ratio, bi, ci in matches:
        if ratio < min_similarity:
            break
        if bi in paired_base or ci in paired_compare:
            continue
        pairs.append((bi, ci))
        paired_base.add(bi)
        paired_compare.add(ci)

    extra_base = [bi for bi in base_range if bi not in paired_base]
    extra_compare = [ci for ci in compare_range if ci not in paired_compare]
    return pairs, extra_base, extra_compare


def _common_col_fingerprints(sheet: XlsxSheet, col_indices: List[int]) -> List[str]:
    fingerprints = []
    for row in sheet.rows:
        parts = []
        for col_idx in col_indices:
            if 0 <= col_idx < len(row):
                parts.append(row[col_idx].value)
            else:
                parts.append("")
        fingerprints.append("\t".join(parts))
    return fingerprints


def _align_columns(
    base: XlsxSheet, compare: XlsxSheet
) -> List[Tuple[Optional[int], Optional[int]]]:
    if not base.rows or not compare.rows:
        max_cols = max(base.max_col, compare.max_col)
        return [
            (i if i < base.max_col else None, i if i < compare.max_col else None)
            for i in range(max_cols)
        ]

    base_headers = [" ".join(cell.value.casefold().split()) for cell in base.rows[0]]
    compare_headers = [" ".join(cell.value.casefold().split()) for cell in compare.rows[0]]
    matcher = difflib.SequenceMatcher(None, base_headers, compare_headers, autojunk=False)
    pairs: List[Tuple[Optional[int], Optional[int]]] = []

    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                pairs.append((i, j))
        elif op == "replace":
            base_range = list(range(i1, i2))
            compare_range = list(range(j1, j2))
            for k in range(max(len(base_range), len(compare_range))):
                b = base_range[k] if k < len(base_range) else None
                c = compare_range[k] if k < len(compare_range) else None
                pairs.append((b, c))
        elif op == "delete":
            for i in range(i1, i2):
                pairs.append((i, None))
        elif op == "insert":
            for j in range(j1, j2):
                pairs.append((None, j))

    return pairs


def _aligned_row_diff(
    base: XlsxSheet,
    compare: XlsxSheet,
    base_row_idx: int,
    compare_row_idx: int,
    col_map: List[Tuple[Optional[int], Optional[int]]],
    is_equal: bool = False,
) -> RowDiff:
    row_diff = RowDiff(
        status="equal",
        base_row_index=base_row_idx,
        compare_row_index=compare_row_idx,
    )
    any_change = False

    for out_col_idx0, (base_col_idx0, compare_col_idx0) in enumerate(col_map):
        base_cell = base.cell_at(base_row_idx, base_col_idx0) if base_col_idx0 is not None else None
        compare_cell = (
            compare.cell_at(compare_row_idx, compare_col_idx0)
            if compare_col_idx0 is not None
            else None
        )

        if base_col_idx0 is None and compare_col_idx0 is not None:
            status: CellStatus = "insert" if compare_cell and compare_cell.value else "equal"
            any_change = any_change or status != "equal"
        elif compare_col_idx0 is None and base_col_idx0 is not None:
            status = "delete" if base_cell and base_cell.value else "equal"
            any_change = any_change or status != "equal"
        else:
            base_text = base_cell.value if base_cell else ""
            compare_text = compare_cell.value if compare_cell else ""
            if base_text == compare_text:
                status = "equal"
            elif not base_text and compare_text:
                status = "insert"
                any_change = True
            elif base_text and not compare_text:
                status = "delete"
                any_change = True
            else:
                status = "modified"
                any_change = True

        row_diff.cells.append(
            CellDiff(
                row=compare_row_idx + 1,
                col=out_col_idx0 + 1,
                base_cell=base_cell,
                compare_cell=compare_cell,
                status=status,
            )
        )

    if is_equal and not any_change:
        row_diff.status = "equal"
    elif any_change:
        row_diff.status = "replace"
    else:
        row_diff.status = "equal"

    return row_diff


def _row_as_delete(base: XlsxSheet, row_idx: int) -> RowDiff:
    return RowDiff(
        status="delete",
        base_row_index=row_idx,
        compare_row_index=None,
        cells=[
            CellDiff(
                row=row_idx + 1,
                col=cell.col,
                base_cell=cell,
                compare_cell=None,
                status="delete",
            )
            for cell in base.rows[row_idx]
        ],
    )


def _row_as_insert(compare: XlsxSheet, row_idx: int) -> RowDiff:
    return RowDiff(
        status="insert",
        base_row_index=None,
        compare_row_index=row_idx,
        cells=[
            CellDiff(
                row=row_idx + 1,
                col=cell.col,
                base_cell=None,
                compare_cell=cell,
                status="insert",
            )
            for cell in compare.rows[row_idx]
        ],
    )
