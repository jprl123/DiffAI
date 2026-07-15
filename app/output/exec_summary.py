"""Resumo executivo de 1 página — para anexar em e-mail, ticket ou dossiê.

Reaproveita o pacote de insights (app/ai/insights.py): síntese em linguagem
de negócio, destaques, pontos de atenção e recomendações, mais os totais.
Sempre UMA página: listas truncadas, textos limitados.
"""
from __future__ import annotations

import os
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.ai.insights import generate_insights
from app.models import ComparisonResult
from app.output.summary import APP_NAME, format_compared_at

_PAGE_MARGIN = 1.6 * cm
_CONTENT_WIDTH = A4[0] - 2 * _PAGE_MARGIN

_ACCENT = colors.HexColor("#2563eb")
_MUTED = colors.HexColor("#6b7280")
_DANGER = colors.HexColor("#b91c1c")
_WARN = colors.HexColor("#b45309")
_RULE = colors.HexColor("#e5e7eb")


def _esc(text: str) -> str:
    return (
        str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _clip(text: str, limit: int = 220) -> str:
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _styles() -> dict:
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13)
    return {
        "brand": ParagraphStyle("brand", parent=base, fontSize=8,
                                textColor=_MUTED, spaceAfter=1),
        "title": ParagraphStyle("title", parent=base, fontName="Helvetica-Bold",
                                fontSize=16, leading=20),
        "meta": ParagraphStyle("meta", parent=base, fontSize=8.5, textColor=_MUTED),
        "h2": ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold",
                             fontSize=10.5, spaceBefore=10, spaceAfter=4),
        "body": base,
        "bullet": ParagraphStyle("bullet", parent=base, leftIndent=10,
                                 bulletIndent=0, spaceAfter=2),
        "tile-num": ParagraphStyle("tile-num", parent=base,
                                   fontName="Helvetica-Bold", fontSize=15,
                                   leading=17, alignment=1),
        "tile-label": ParagraphStyle("tile-label", parent=base, fontSize=7.5,
                                     textColor=_MUTED, alignment=1),
        "footer": ParagraphStyle("footer", parent=base, fontSize=7.5,
                                 textColor=_MUTED, alignment=1),
    }


def _stat_tiles(result: ComparisonResult, st: dict) -> Table:
    s = result.stats
    tiles = [
        (str(s.total_changes), "Alterações"),
        (str(s.content_changes), "Conteúdo"),
        (str(s.noise_changes), "Rotineiras"),
        (str(s.formatting_changes), "Formatação"),
        (str(s.moves), "Movimentações"),
        (str(s.table_changes), "Tabelas"),
    ]
    cells = [
        [Paragraph(num, st["tile-num"]), Paragraph(label, st["tile-label"])]
        for num, label in tiles
    ]
    data = [[c[0] for c in cells], [c[1] for c in cells]]
    width = _CONTENT_WIDTH / len(tiles)
    table = Table(data, colWidths=[width] * len(tiles))
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, _RULE),
        ("LINEAFTER", (0, 0), (-2, -1), 0.75, _RULE),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
    ]))
    return table


def write_exec_summary_pdf(result: ComparisonResult, out_path: str) -> None:
    """Gera o resumo executivo de 1 página."""
    if result is None or result.stats is None:
        raise ValueError("Resultado de comparação inválido para o resumo executivo.")
    insights = generate_insights(result)
    st = _styles()

    story: List[Flowable] = []

    # Cabeçalho: logo do produto (+ logo do escritório quando o plano permite)
    from app.branding import active_logo_path
    from app.output.summary import app_logo_path

    firm_logo = active_logo_path()
    product_logo = app_logo_path()
    brand_col = [
        Paragraph("<b>%s</b>" % _esc(APP_NAME), st["brand"]),
        Paragraph("Resumo Executivo da Comparação", st["title"]),
        Paragraph(
            "%s &nbsp;·&nbsp; %s"
            % (_esc(format_compared_at(result.compared_at)),
               _esc("%s vs %s" % (
                   os.path.basename(result.base_path or "base"),
                   os.path.basename(result.compare_path or "revisado"),
               ))),
            st["meta"],
        ),
    ]
    logo = firm_logo or product_logo
    if logo:
        img = Image(logo)
        max_h = 1.4 * cm
        ratio = float(img.imageWidth) / float(img.imageHeight or 1)
        img.drawHeight = max_h
        img.drawWidth = min(max_h * ratio, 4.5 * cm)
        header = Table(
            [[brand_col, img]],
            colWidths=[_CONTENT_WIDTH - 5 * cm, 5 * cm],
        )
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header)
    else:
        story.extend(brand_col)

    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.75, color=_RULE))
    story.append(Spacer(1, 10))

    story.append(_stat_tiles(result, st))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Síntese", st["h2"]))
    story.append(Paragraph(
        _esc(_clip(insights.get("executive_summary", ""), 400)), st["body"]
    ))

    highlights = [h for h in (insights.get("highlights") or []) if h][:5]
    if highlights:
        story.append(Paragraph("Principais mudanças", st["h2"]))
        for item in highlights:
            story.append(Paragraph("• %s" % _esc(_clip(item)), st["bullet"]))

    risks = (insights.get("risks") or [])[:4]
    if risks:
        story.append(Paragraph("Pontos de atenção", st["h2"]))
        for risk in risks:
            color = _DANGER if risk.get("severity") == "high" else _WARN
            story.append(Paragraph(
                '• <font color="%s"><b>%s</b></font> — %s'
                % (color.hexval().replace("0x", "#"),
                   _esc(str(risk.get("type", "")).capitalize()),
                   _esc(_clip(risk.get("message", "")))),
                st["bullet"],
            ))

    recs = [r for r in (insights.get("recommendations") or []) if r][:3]
    if recs:
        story.append(Paragraph("Recomendações", st["h2"]))
        for rec in recs:
            story.append(Paragraph("• %s" % _esc(_clip(rec)), st["bullet"]))

    pages = result.stats.changed_pages
    if pages:
        story.append(Paragraph("Páginas afetadas", st["h2"]))
        story.append(Paragraph(
            _esc(", ".join(str(p) for p in pages[:40])
                 + ("…" if len(pages) > 40 else "")),
            st["body"],
        ))

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_RULE))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Gerado por %s — este resumo não substitui a revisão do redline completo."
        % _esc(APP_NAME),
        st["footer"],
    ))

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        leftMargin=_PAGE_MARGIN,
        rightMargin=_PAGE_MARGIN,
        topMargin=1.4 * cm,
        bottomMargin=1.2 * cm,
        title="Resumo Executivo — diffAI",
        author=APP_NAME,
    )
    doc.build(story)
