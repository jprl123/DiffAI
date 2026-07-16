"""Geração do PDF redline com ReportLab (platypus).

Entrada: ComparisonResult (app/models.py). Saída: PDF A4 com:
  - cabeçalho na 1ª página (título, arquivos, data, legenda compacta);
  - corpo com os render_blocks marcados (inserção azul sublinhado, exclusão
    vermelha tachada, movido verde, formatação com fundo amarelo claro);
  - tabelas platypus com fundo por linha (insert/delete) e grid fino;
  - placeholders para imagens;
  - página de síntese ("Summary of Changes") ao final, sempre.

Cálculo de páginas afetadas (stats.changed_pages)
-------------------------------------------------
Quando result.stats.changed_pages chega vazio e há mudanças (caso DOCX, em que
a extração não conhece páginas), o layout FINAL do PDF é a única fonte de
verdade. Abordagem em duas passadas, documentada em ARCHITECTURE.md:

  Passada 1: o story é construído com um flowable invisível de tamanho zero
  (_PageProbe) logo após cada bloco alterado. O PDF é gerado em um BytesIO
  descartável; durante o draw() de cada probe o número da página corrente do
  canvas é registrado. Isso equivale ao "canvasmaker que registra página
  corrente por flowable marcado", sem depender de âncoras nem de reabrir o
  arquivo com fitz.

  Passada 2: result.stats.changed_pages é preenchido com as páginas coletadas
  e o PDF definitivo é gerado em out_path — agora com a página de síntese
  exibindo a lista correta. Os probes têm dimensão 0x0 e existem nas duas
  passadas, portanto o layout é idêntico entre elas (a única diferença de
  conteúdo, a linha "Páginas afetadas", está na síntese, que fica DEPOIS de
  todo o corpo e não desloca nada).
"""
from __future__ import annotations

import io
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Set

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import HRFlowable

from app.models import (
    BlockKind,
    Category,
    ChangeType,
    ComparisonResult,
    Fragment,
    RenderBlock,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paleta
# ---------------------------------------------------------------------------

COLOR_INSERT = "#1a56db"      # azul — inserção
COLOR_DELETE = "#c81e1e"      # vermelho — exclusão
COLOR_MOVE = "#046c4e"        # verde escuro — movido
COLOR_MUTED = "#6b7280"       # cinza — metadados, sufixo [movido]
BG_FORMATTING = "#fdf6b2"     # amarelo claro — mudança de formatação
BG_ROW_INSERT = "#ebf5ff"     # fundo de linha inserida em tabela
BG_ROW_DELETE = "#fdf2f2"     # fundo de linha removida em tabela
BG_TABLE_HEADER = "#f3f4f6"   # cabeçalho de tabela (cinza claro)
GRID_COLOR = "#c9ced6"        # grid fino cinza
BOX_COLOR = "#9aa0a8"         # borda de placeholder de imagem

_PAGE_MARGIN = 2 * cm
_CONTENT_WIDTH = A4[0] - 2 * _PAGE_MARGIN
# Largura efetiva durante um build (paisagem usa a largura real da página).
_active_content_width = _CONTENT_WIDTH


def _cw() -> float:
    return _active_content_width


def _pagesize_for_result(result: ComparisonResult):
    """A4 retrato por padrão; paisagem (ou tamanho do PDF) quando o layout indica."""
    layout = getattr(result, "preview_layout", None) or {}
    try:
        w = float(layout["page_width_pt"]) if layout.get("page_width_pt") else None
        h = float(layout["page_height_pt"]) if layout.get("page_height_pt") else None
    except (TypeError, ValueError):
        w = h = None
    if w and h and w > h:
        # Limita a algo razoável (≈ A3 paisagem) para não estourar memória.
        max_w, max_h = landscape(A4)[0] * 1.15, landscape(A4)[1] * 1.15
        return (min(w, max_w), min(h, max_h))
    if layout.get("orientation") == "landscape":
        return landscape(A4)
    return A4

_MOVE_PREFIX = "⇄"       # ⇄
_GROUP_SEPARATOR = "· · ·"   # · · ·
_BREADCRUMB_SEP = " › "  # ›


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def _esc(text: Optional[str]) -> str:
    """Escapa &, < e > ANTES de qualquer markup inline do ReportLab."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_date(iso_ts: Optional[str]) -> str:
    """Formata timestamp ISO como dd/mm/aaaa hh:mm; devolve o cru se falhar."""
    if not iso_ts:
        return "—"
    try:
        cleaned = iso_ts.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return str(iso_ts)


def _build_styles() -> Dict[str, ParagraphStyle]:
    base = dict(fontName="Helvetica", textColor=colors.HexColor("#111827"))
    styles: Dict[str, ParagraphStyle] = {}
    styles["title"] = ParagraphStyle(
        "cd-title", fontName="Helvetica-Bold", fontSize=18, leading=22,
        spaceAfter=6, textColor=colors.HexColor("#111827"))
    styles["subtitle"] = ParagraphStyle(
        "cd-subtitle", fontName="Helvetica", fontSize=11.5, leading=15,
        spaceAfter=2, textColor=colors.HexColor("#111827"))
    styles["meta"] = ParagraphStyle(
        "cd-meta", fontName="Helvetica", fontSize=9, leading=12,
        spaceAfter=8, textColor=colors.HexColor(COLOR_MUTED))
    styles["legend"] = ParagraphStyle(
        "cd-legend", fontName="Helvetica", fontSize=8.5, leading=11,
        textColor=colors.HexColor("#374151"))
    styles["body"] = ParagraphStyle(
        "cd-body", alignment=TA_JUSTIFY, fontSize=10, leading=14,
        spaceAfter=6, **base)
    styles["list"] = ParagraphStyle(
        "cd-list", alignment=TA_JUSTIFY, fontSize=10, leading=14,
        spaceAfter=4, leftIndent=18, bulletIndent=6, **base)
    styles["h1"] = ParagraphStyle(
        "cd-h1", fontName="Helvetica-Bold", fontSize=15, leading=19,
        spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#111827"))
    styles["h2"] = ParagraphStyle(
        "cd-h2", fontName="Helvetica-Bold", fontSize=12.5, leading=16,
        spaceBefore=12, spaceAfter=5, textColor=colors.HexColor("#111827"))
    styles["h3"] = ParagraphStyle(
        "cd-h3", fontName="Helvetica-Bold", fontSize=11, leading=14,
        spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#111827"))
    styles["breadcrumb"] = ParagraphStyle(
        "cd-breadcrumb", fontName="Helvetica-Oblique", fontSize=9, leading=12,
        spaceBefore=10, spaceAfter=4, textColor=colors.HexColor(COLOR_MUTED))
    styles["separator"] = ParagraphStyle(
        "cd-separator", fontName="Helvetica", fontSize=11, leading=14,
        alignment=TA_CENTER, spaceBefore=10, spaceAfter=10,
        textColor=colors.HexColor(COLOR_MUTED))
    styles["cell"] = ParagraphStyle(
        "cd-cell", alignment=TA_LEFT, fontName="Helvetica", fontSize=8.5,
        leading=11, textColor=colors.HexColor("#111827"))
    styles["cell-header"] = ParagraphStyle(
        "cd-cell-header", alignment=TA_LEFT, fontName="Helvetica-Bold",
        fontSize=8.5, leading=11, textColor=colors.HexColor("#111827"))
    styles["placeholder"] = ParagraphStyle(
        "cd-placeholder", alignment=TA_CENTER, fontName="Helvetica",
        fontSize=9.5, leading=12, textColor=colors.HexColor(COLOR_MUTED))
    styles["synth-title"] = ParagraphStyle(
        "cd-synth-title", fontName="Helvetica-Bold", fontSize=15, leading=19,
        spaceAfter=10, textColor=colors.HexColor("#111827"))
    styles["note"] = ParagraphStyle(
        "cd-note", fontName="Helvetica-Oblique", fontSize=10, leading=14,
        spaceBefore=8, spaceAfter=8, textColor=colors.HexColor(COLOR_MUTED))
    return styles


# ---------------------------------------------------------------------------
# Probe de página (ver docstring do módulo)
# ---------------------------------------------------------------------------

class _PageProbe(Flowable):
    """Flowable invisível (0x0) que registra a página em que foi desenhado.

    Colocado imediatamente após o flowable de cada bloco alterado; como tem
    dimensão zero, nunca desloca o layout nem cai sozinho em outra página.
    """

    def __init__(self, registry: Set[int]) -> None:
        Flowable.__init__(self)
        self.width = 0
        self.height = 0
        self._registry = registry

    def wrap(self, availWidth: float, availHeight: float):  # noqa: N803
        return (0, 0)

    def draw(self) -> None:
        self._registry.add(self.canv.getPageNumber())


# ---------------------------------------------------------------------------
# Fragments -> markup inline do ReportLab
# ---------------------------------------------------------------------------

def _fragment_markup(frag: Fragment, rb: RenderBlock) -> str:
    """Converte um Fragment em markup inline. O texto é escapado ANTES."""
    text = _esc(getattr(frag, "text", "") or "")
    if not text:
        return ""
    op = getattr(frag, "op", "equal") or "equal"
    # Em blocos inteiramente inseridos/removidos, todo o texto recebe a
    # marcação do bloco mesmo que o motor tenha emitido fragments "equal".
    if op == "equal":
        if rb.change_type == ChangeType.INSERT:
            op = "insert"
        elif rb.change_type == ChangeType.DELETE:
            op = "delete"
    if op == "insert":
        return '<font color="%s"><u>%s</u></font>' % (COLOR_INSERT, text)
    if op == "delete":
        return '<font color="%s"><strike>%s</strike></font>' % (COLOR_DELETE, text)
    if op == "format":
        if frag.bold:
            text = "<b>%s</b>" % text
        if frag.italic:
            text = "<i>%s</i>" % text
        if frag.underline:
            text = "<u>%s</u>" % text
        if frag.strike:
            text = "<strike>%s</strike>" % text
        return '<font backColor="%s">%s</font>' % (BG_FORMATTING, text)
    # equal: respeita a formatação do fragment
    if frag.bold:
        text = "<b>%s</b>" % text
    if frag.italic:
        text = "<i>%s</i>" % text
    if frag.underline:
        text = "<u>%s</u>" % text
    if frag.strike:
        text = "<strike>%s</strike>" % text
    if rb.change_type in (ChangeType.MOVE, ChangeType.MOVE_MODIFY):
        text = '<font color="%s">%s</font>' % (COLOR_MOVE, text)
    return text


def _block_markup(rb: RenderBlock) -> str:
    """Markup completo de um bloco textual (paragraph/heading/list_item)."""
    parts = [_fragment_markup(f, rb) for f in (rb.fragments or [])]
    markup = "".join(p for p in parts if p)
    if rb.change_type in (ChangeType.MOVE, ChangeType.MOVE_MODIFY):
        markup = (
            '<font color="%s">%s </font>' % (COLOR_MOVE, _MOVE_PREFIX)
            + markup
            + ' <font color="%s">[movido]</font>' % COLOR_MUTED
        )
    if rb.category == Category.FORMATTING:
        has_fmt_marks = any(getattr(f, "op", "equal") == "format" for f in (rb.fragments or []))
        if not has_fmt_marks:
            markup = '<font backColor="%s">%s</font>' % (BG_FORMATTING, markup)
    return markup


# ---------------------------------------------------------------------------
# Blocos -> flowables
# ---------------------------------------------------------------------------

def _heading_style_key(level: int) -> str:
    if level <= 1:
        return "h1"
    if level == 2:
        return "h2"
    return "h3"


_IMAGE_LABELS = {
    ChangeType.EQUAL: "[Imagem]",
    ChangeType.INSERT: "[Imagem inserida]",
    ChangeType.DELETE: "[Imagem removida]",
    ChangeType.MODIFY: "[Imagem substituída]",
    ChangeType.MOVE: "[Imagem movida]",
    ChangeType.MOVE_MODIFY: "[Imagem movida e substituída]",
}


def _image_placeholder(rb: RenderBlock, styles: Dict[str, ParagraphStyle]) -> Flowable:
    label = _IMAGE_LABELS.get(rb.change_type, "[Imagem]")
    text = _esc(label)
    if rb.change_type == ChangeType.INSERT:
        text = '<font color="%s"><u>%s</u></font>' % (COLOR_INSERT, text)
    elif rb.change_type == ChangeType.DELETE:
        text = '<font color="%s"><strike>%s</strike></font>' % (COLOR_DELETE, text)
    elif rb.change_type in (ChangeType.MOVE, ChangeType.MOVE_MODIFY):
        text = '<font color="%s">%s</font>' % (COLOR_MOVE, text)
    para = Paragraph(text, styles["placeholder"])
    box = Table([[para]], colWidths=[6 * cm], rowHeights=[1.4 * cm])
    box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(BOX_COLOR)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    box.hAlign = "LEFT"
    return box


def _cell_paragraph(
    frags: List[Fragment],
    rb: RenderBlock,
    row_op: str,
    style: ParagraphStyle,
) -> Paragraph:
    parts: List[str] = []
    for frag in frags or []:
        text = _esc(getattr(frag, "text", "") or "")
        if not text:
            continue
        op = getattr(frag, "op", "equal") or "equal"
        if row_op == "delete":
            # linha removida: texto tachado em vermelho, independente do op
            parts.append('<font color="%s"><strike>%s</strike></font>' % (COLOR_DELETE, text))
        elif op == "insert" or (op == "equal" and row_op == "insert"):
            parts.append('<font color="%s"><u>%s</u></font>' % (COLOR_INSERT, text))
        elif op == "delete":
            parts.append('<font color="%s"><strike>%s</strike></font>' % (COLOR_DELETE, text))
        else:
            if frag.bold:
                text = "<b>%s</b>" % text
            if frag.italic:
                text = "<i>%s</i>" % text
            if frag.underline:
                text = "<u>%s</u>" % text
            if frag.strike:
                text = "<strike>%s</strike>" % text
            parts.append(text)
    return Paragraph("".join(parts), style)


def _table_flowable(rb: RenderBlock, styles: Dict[str, ParagraphStyle]) -> Flowable:
    rows = rb.rows or []
    n_rows = len(rows)
    n_cols = max((len(r) for r in rows), default=0)
    if n_rows == 0 or n_cols == 0:
        return Paragraph(_esc("[Tabela vazia]"), styles["note"])

    row_ops = list(rb.row_ops or [])
    while len(row_ops) < n_rows:
        row_ops.append("equal")

    data: List[List[Paragraph]] = []
    for ri in range(n_rows):
        row_op = row_ops[ri] if row_ops[ri] in ("equal", "insert", "delete", "modify") else "equal"
        cell_style = styles["cell-header"] if ri == 0 else styles["cell"]
        line: List[Paragraph] = []
        for ci in range(n_cols):
            frags = rows[ri][ci] if ci < len(rows[ri]) else []
            line.append(_cell_paragraph(frags, rb, row_op, cell_style))
        data.append(line)

    col_width = _cw() / float(n_cols)
    table = Table(data, colWidths=[col_width] * n_cols, repeatRows=1)

    commands = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(GRID_COLOR)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BG_TABLE_HEADER)),
    ]
    for ri in range(n_rows):
        op = row_ops[ri]
        if op == "insert":
            commands.append(("BACKGROUND", (0, ri), (-1, ri), colors.HexColor(BG_ROW_INSERT)))
        elif op == "delete":
            commands.append(("BACKGROUND", (0, ri), (-1, ri), colors.HexColor(BG_ROW_DELETE)))
    table.setStyle(TableStyle(commands))
    table.hAlign = "LEFT"
    return table


def _block_flowables(rb: RenderBlock, styles: Dict[str, ParagraphStyle]) -> List[Flowable]:
    """Converte um RenderBlock nos flowables correspondentes."""
    if rb.kind == BlockKind.TABLE:
        return [_table_flowable(rb, styles), Spacer(1, 6)]
    if rb.kind == BlockKind.IMAGE:
        return [_image_placeholder(rb, styles), Spacer(1, 6)]

    markup = _block_markup(rb)
    if rb.kind == BlockKind.HEADING:
        return [Paragraph(markup, styles[_heading_style_key(rb.level or 1)])]
    if rb.kind == BlockKind.LIST_ITEM:
        return [Paragraph(markup, styles["list"], bulletText="•")]
    # PARAGRAPH (e qualquer kind desconhecido cai aqui, defensivamente)
    return [Paragraph(markup, styles["body"])]


def _is_header_footer(rb: RenderBlock) -> bool:
    return bool(rb.section_path) and rb.section_path[0] in ("Cabeçalho", "Rodapé")


def _append_block(
    story: List[Flowable],
    rb: RenderBlock,
    styles: Dict[str, ParagraphStyle],
    registry: Set[int],
) -> None:
    # Cabeçalho/rodapé: só aparecem quando mudaram, e com rótulo — repetir
    # rodapé inalterado no fim do documento seria ruído.
    if _is_header_footer(rb):
        if rb.change_type == ChangeType.EQUAL:
            return
        story.append(Paragraph(
            "<i>%s do documento:</i>" % _esc(rb.section_path[0]),
            styles["breadcrumb"],
        ))
    flowables = _block_flowables(rb, styles)
    if not flowables:
        return
    story.append(flowables[0])
    if rb.change_type != ChangeType.EQUAL:
        # Probe logo após o conteúdo principal do bloco (antes do Spacer),
        # registrando a página onde o bloco termina.
        story.append(_PageProbe(registry))
    story.extend(flowables[1:])


# ---------------------------------------------------------------------------
# Cabeçalho e legenda
# ---------------------------------------------------------------------------

def _legend_flowable(styles: Dict[str, ParagraphStyle]) -> Flowable:
    legend = styles["legend"]
    cells = [
        Paragraph("<b>Legenda:</b>", legend),
        Paragraph('<font color="%s"><u>inserção</u></font>' % COLOR_INSERT, legend),
        Paragraph('<font color="%s"><strike>exclusão</strike></font>' % COLOR_DELETE, legend),
        Paragraph('<font color="%s">%s movido</font>' % (COLOR_MOVE, _MOVE_PREFIX), legend),
        Paragraph('<font backColor="%s">formatação</font>' % BG_FORMATTING, legend),
    ]
    widths = [2.0 * cm, 2.9 * cm, 2.9 * cm, 2.9 * cm, 2.9 * cm]
    strip = Table([cells], colWidths=widths)
    strip.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9fafb")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(GRID_COLOR)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    strip.hAlign = "LEFT"
    return strip


def _header_flowables(
    result: ComparisonResult, styles: Dict[str, ParagraphStyle]
) -> List[Flowable]:
    base_name = result.base_title or os.path.basename(result.base_path or "") or "documento base"
    comp_name = (
        result.compare_title or os.path.basename(result.compare_path or "") or "documento revisado"
    )
    story: List[Flowable] = []

    # Logo do escritório (plano Equipe) no topo, alinhado à direita.
    from app.branding import active_logo_path

    logo = active_logo_path()
    title_par = Paragraph("Comparação de Documentos", styles["title"])
    if logo:
        from reportlab.platypus import Image, Table as RLTable, TableStyle as RLTableStyle

        img = Image(logo)
        max_h = 1.3 * cm
        ratio = float(img.imageWidth) / float(img.imageHeight or 1)
        img.drawHeight = max_h
        img.drawWidth = min(max_h * ratio, 4.5 * cm)
        header = RLTable(
            [[title_par, img]], colWidths=[_cw() - 5 * cm, 5 * cm]
        )
        header.setStyle(RLTableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header)
    else:
        story.append(title_par)
    story.append(Paragraph(
        '<b>%s</b> <font color="%s">vs</font> <b>%s</b>'
        % (_esc(base_name), COLOR_MUTED, _esc(comp_name)),
        styles["subtitle"],
    ))
    story.append(Paragraph(
        "Data da comparação: %s" % _esc(_fmt_date(result.compared_at)),
        styles["meta"],
    ))
    story.append(_legend_flowable(styles))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.7, color=colors.HexColor(GRID_COLOR)))
    story.append(Spacer(1, 10))
    return story


# ---------------------------------------------------------------------------
# Corpo — variante "somente páginas alteradas"
# ---------------------------------------------------------------------------

def _changed_groups(blocks: List[RenderBlock]) -> List[List[int]]:
    """Índices a incluir na variante enxuta, agrupados por contiguidade.

    Cada bloco alterado entra com o bloco EQUAL imediatamente anterior e
    posterior como contexto; índices contíguos formam um grupo.
    """
    include: Set[int] = set()
    for i, rb in enumerate(blocks):
        if rb.change_type != ChangeType.EQUAL:
            include.add(i)
            if i > 0:
                include.add(i - 1)
            if i + 1 < len(blocks):
                include.add(i + 1)
    if not include:
        return []
    ordered = sorted(include)
    groups: List[List[int]] = [[ordered[0]]]
    for idx in ordered[1:]:
        if idx == groups[-1][-1] + 1:
            groups[-1].append(idx)
        else:
            groups.append([idx])
    return groups


def _append_changed_pages_body(
    story: List[Flowable],
    result: ComparisonResult,
    styles: Dict[str, ParagraphStyle],
    registry: Set[int],
) -> None:
    blocks = result.render_blocks
    groups = _changed_groups(blocks)
    if not groups:
        story.append(Paragraph(
            "Nenhuma alteração encontrada entre os documentos.",
            styles["note"],
        ))
        return
    for gi, group in enumerate(groups):
        if gi > 0:
            story.append(Paragraph(_GROUP_SEPARATOR, styles["separator"]))
        # Breadcrumb da seção do primeiro bloco ALTERADO do grupo
        anchor = next(
            (blocks[i] for i in group if blocks[i].change_type != ChangeType.EQUAL),
            blocks[group[0]],
        )
        if anchor.section_path:
            crumb = _BREADCRUMB_SEP.join(_esc(p) for p in anchor.section_path if p)
            if crumb:
                story.append(Paragraph(crumb, styles["breadcrumb"]))
        for i in group:
            _append_block(story, blocks[i], styles, registry)


# ---------------------------------------------------------------------------
# Página de síntese
# ---------------------------------------------------------------------------

def _synthesis_flowables(
    result: ComparisonResult, styles: Dict[str, ParagraphStyle]
) -> List[Flowable]:
    from app.output.summary import APP_NAME, SUMMARY_TITLE, app_logo_path, summary_rows

    rows = summary_rows(result)
    data = []
    for label, value in rows:
        data.append([
            Paragraph("<b>%s</b>" % _esc(label), styles["cell"]),
            Paragraph(_esc(value), styles["cell"]),
        ])
    table = Table(data, colWidths=[6.5 * cm, _cw() - 6.5 * cm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(GRID_COLOR)),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(BG_TABLE_HEADER)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    table.hAlign = "LEFT"
    brand_style = ParagraphStyle(
        "synth-brand", parent=styles["cell"], fontSize=9,
        textColor=colors.HexColor("#6b7280"), alignment=TA_CENTER,
    )
    title_style = ParagraphStyle(
        "synth-title-center", parent=styles["synth-title"], alignment=TA_CENTER,
    )
    out: List[Flowable] = [
        Paragraph("<b>%s</b>" % _esc(APP_NAME), brand_style),
        Spacer(1, 2),
        Paragraph(SUMMARY_TITLE, title_style),
        Spacer(1, 8),
        table,
        Spacer(1, 10),
        Paragraph("<i>Gerado por %s</i>" % _esc(APP_NAME), brand_style),
    ]
    logo = app_logo_path()
    if logo:
        try:
            end_img = Image(logo)
            max_h = 0.9 * cm
            ratio = float(end_img.imageWidth) / float(end_img.imageHeight or 1)
            end_img.drawHeight = max_h
            end_img.drawWidth = min(max_h * ratio, 1.8 * cm)
            end_img.hAlign = "CENTER"
            out.append(Spacer(1, 12))
            out.append(end_img)
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------
# Montagem e build
# ---------------------------------------------------------------------------

def _build_story(
    result: ComparisonResult,
    changed_pages_only: bool,
    registry: Set[int],
) -> List[Flowable]:
    styles = _build_styles()
    story = _header_flowables(result, styles)
    if changed_pages_only:
        _append_changed_pages_body(story, result, styles, registry)
    else:
        for rb in result.render_blocks:
            _append_block(story, rb, styles, registry)
    story.append(PageBreak())
    story.extend(_synthesis_flowables(result, styles))
    return story


def _build_pdf(result, target, changed_pages_only, registry):
    # type: (ComparisonResult, object, bool, Set[int]) -> None
    global _active_content_width
    pagesize = _pagesize_for_result(result)
    margin = _PAGE_MARGIN
    if pagesize[0] > pagesize[1]:
        margin = 1.2 * cm  # paisagem: mais área útil para tabelas largas
    prev_cw = _active_content_width
    _active_content_width = pagesize[0] - 2 * margin
    try:
        doc = SimpleDocTemplate(
            target,
            pagesize=pagesize,
            leftMargin=margin,
            rightMargin=margin,
            topMargin=1.8 * cm,
            bottomMargin=1.8 * cm,
            title="Comparação de Documentos",
            author="DiffAI",
        )
        doc.build(_build_story(result, changed_pages_only, registry))
    finally:
        _active_content_width = prev_cw


def _has_changes(result: ComparisonResult) -> bool:
    if result.stats is not None and result.stats.total_changes > 0:
        return True
    if result.changes:
        return True
    return any(rb.change_type != ChangeType.EQUAL for rb in result.render_blocks)


def _validate(result: ComparisonResult, out_path: str) -> None:
    if result is None or not hasattr(result, "render_blocks") or not hasattr(result, "stats"):
        raise ValueError(
            "Resultado de comparação inválido: esperado um ComparisonResult preenchido."
        )
    if result.stats is None:
        raise ValueError("Resultado de comparação sem estatísticas (stats ausente).")
    if result.render_blocks is None or len(result.render_blocks) == 0:
        raise ValueError(
            "Nada para renderizar: o resultado não contém blocos — "
            "os documentos comparados parecem vazios."
        )
    if not out_path or not str(out_path).strip():
        raise ValueError("Caminho de saída do PDF inválido (vazio).")
    if os.path.isdir(out_path):
        raise ValueError(
            "Caminho de saída '%s' é um diretório; informe o caminho do arquivo PDF."
            % out_path
        )


def write_redline_pdf(
    result: ComparisonResult,
    out_path: str,
    changed_pages_only: bool = False,
) -> None:
    """Gera o PDF redline em out_path a partir de um ComparisonResult.

    Efeito colateral documentado (ver ARCHITECTURE.md): se
    result.stats.changed_pages estiver vazio e houver mudanças, a lista é
    calculada a partir do layout do PDF gerado (duas passadas com _PageProbe)
    e preenchida em result.stats.changed_pages antes do build final.
    """
    _validate(result, out_path)

    parent = os.path.dirname(os.path.abspath(out_path))
    try:
        os.makedirs(parent, exist_ok=True)
    except OSError as exc:
        raise ValueError(
            "Não foi possível criar o diretório de saída '%s': %s" % (parent, exc)
        )

    # Passada 1 (opcional): descobrir as páginas afetadas pelo layout final.
    if not result.stats.changed_pages and _has_changes(result):
        registry: Set[int] = set()
        buffer = io.BytesIO()
        try:
            _build_pdf(result, buffer, changed_pages_only, registry)
        except ValueError:
            raise
        except Exception as exc:
            logger.exception("Falha na passada de medição de páginas")
            raise ValueError("Falha ao montar o PDF redline: %s" % exc)
        result.stats.changed_pages = sorted(registry)
        logger.debug("Páginas afetadas calculadas do layout: %s", result.stats.changed_pages)

    # Passada final: PDF definitivo com a síntese correta.
    try:
        _build_pdf(result, out_path, changed_pages_only, set())
    except ValueError:
        raise
    except Exception as exc:
        logger.exception("Falha ao gravar o PDF redline em %s", out_path)
        raise ValueError("Falha ao gerar o PDF redline em '%s': %s" % (out_path, exc))
    logger.info("PDF redline gerado: %s (changed_pages_only=%s)", out_path, changed_pages_only)
