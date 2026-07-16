"""Extração de documentos PDF (PyMuPDF/fitz) para o modelo canônico.

Estratégia:
- ``page.get_text("dict")`` por página; spans -> linhas -> blocos de parágrafo.
- Heurística de título baseada no tamanho de fonte modal do documento (corpo).
- Formatação por span: bold = flags & 16, italic = flags & 2 (verificado
  empiricamente com PDFs gerados pelo próprio fitz).
- Hifenização de fim de linha desfeita ("palavra-" + quebra -> "palavra").
- Tabelas via ``page.find_tables()``; blocos de texto dentro do bbox da tabela
  são removidos para não duplicar conteúdo.
- Imagens via ``page.get_images(full=True)`` com SHA-1 dos bytes extraídos,
  posicionadas após os blocos de texto da página.
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz

from app.models import Block, BlockKind, Cell, Document, Run

logger = logging.getLogger(__name__)

_BOLD_FLAG = 16   # 2**4
_ITALIC_FLAG = 2  # 2**1

_HEADING_MAX_CHARS = 120
_HEADING_SIZE_RATIO = 1.15
_HEADING_L1_SIZE_RATIO = 1.4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iter_text_spans(raw_page: Dict[str, Any]):
    """Itera (block, line, span) de texto de um dict de página."""
    for block in raw_page.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                yield block, line, span


def _body_font_size(raw_pages: List[Dict[str, Any]]) -> float:
    """Tamanho de fonte modal do documento, ponderado por quantidade de texto."""
    weights: Dict[float, int] = {}
    for raw in raw_pages:
        for _block, _line, span in _iter_text_spans(raw):
            text = span.get("text", "")
            if not text.strip():
                continue
            size = round(float(span.get("size", 0.0)), 1)
            weights[size] = weights.get(size, 0) + len(text.strip())
    if not weights:
        return 0.0
    return max(weights.items(), key=lambda kv: kv[1])[0]


def _append_run(runs: List[Run], text: str, bold: bool, italic: bool) -> None:
    """Anexa texto fundindo com o run anterior quando o estilo é o mesmo."""
    if not text:
        return
    run = Run(text=text, bold=bold, italic=italic)
    if runs and runs[-1].style_key() == run.style_key():
        runs[-1].text += text
    else:
        runs.append(run)


def _join_line(runs: List[Run], line_spans: List[Dict[str, Any]]) -> None:
    """Anexa uma linha aos runs acumulados, tratando hifenização e espaços."""
    first_text = ""
    for span in line_spans:
        if span.get("text"):
            first_text = span["text"]
            break
    if not first_text:
        return

    if runs:
        last = runs[-1]
        stripped = last.text.rstrip()
        first_char = first_text.lstrip()[:1]
        if (
            stripped.endswith("-")
            and len(stripped) >= 2
            and stripped[-2].isalpha()
            and first_char.isalpha()
        ):
            # Hifenização de quebra de linha: "palavra-" + "continuação".
            last.text = stripped[:-1]
            if not last.text:
                runs.pop()
        elif not last.text.endswith((" ", "\n")):
            last.text += " "

    for span in line_spans:
        text = span.get("text", "")
        if not text:
            continue
        flags = int(span.get("flags", 0))
        _append_run(runs, text, bool(flags & _BOLD_FLAG), bool(flags & _ITALIC_FLAG))


def _block_metrics(block: Dict[str, Any]) -> Tuple[float, bool]:
    """(tamanho de fonte dominante, todos os spans em negrito) de um bloco."""
    weights: Dict[float, int] = {}
    all_bold = True
    seen_any = False
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text = span.get("text", "")
            if not text.strip():
                continue
            seen_any = True
            size = round(float(span.get("size", 0.0)), 1)
            weights[size] = weights.get(size, 0) + len(text.strip())
            if not (int(span.get("flags", 0)) & _BOLD_FLAG):
                all_bold = False
    if not weights:
        return 0.0, False
    dominant = max(weights.items(), key=lambda kv: kv[1])[0]
    return dominant, (all_bold and seen_any)


def _text_block_to_model(
    block: Dict[str, Any], body_size: float, page_number: int
) -> Optional[Block]:
    """Converte um bloco visual do get_text('dict') em um Block do modelo."""
    runs: List[Run] = []
    for line in block.get("lines", []):
        spans = [s for s in line.get("spans", []) if s.get("text")]
        if not any(s["text"].strip() for s in spans):
            continue
        _join_line(runs, spans)

    text = "".join(r.text for r in runs).strip()
    if not text:
        return None

    dominant_size, all_bold = _block_metrics(block)
    kind = BlockKind.PARAGRAPH
    level = 0
    if (
        len(text) < _HEADING_MAX_CHARS
        and not text.endswith(".")
        and (
            (body_size > 0 and dominant_size >= body_size * _HEADING_SIZE_RATIO)
            or all_bold
        )
    ):
        kind = BlockKind.HEADING
        if body_size > 0 and dominant_size >= body_size * _HEADING_L1_SIZE_RATIO:
            level = 1
        else:
            level = 2

    return Block(kind=kind, runs=runs, level=level, page=page_number)


def _find_tables_safe(page: "fitz.Page") -> List[Any]:
    try:
        finder = page.find_tables()
        return list(finder.tables) if finder is not None else []
    except Exception as exc:
        logger.warning(
            "find_tables falhou na página %d: %s", page.number + 1, exc
        )
        return []


def _table_to_block(table: Any, page_number: int) -> Optional[Block]:
    try:
        data = table.extract()
    except Exception as exc:
        logger.warning("Falha ao extrair tabela: %s", exc)
        return None
    rows: List[List[Cell]] = []
    for raw_row in data or []:
        row: List[Cell] = []
        for raw_cell in raw_row:
            cell_text = (raw_cell or "").strip()
            row.append(Cell(runs=[Run(text=cell_text)] if cell_text else []))
        rows.append(row)
    has_content = any(any(c.text.strip() for c in row) for row in rows)
    if not rows or not has_content:
        return None
    return Block(kind=BlockKind.TABLE, rows=rows, page=page_number)


def _inside_any(rect: "fitz.Rect", table_rects: List["fitz.Rect"]) -> bool:
    """O centro do bloco de texto cai dentro do bbox de alguma tabela?"""
    center = fitz.Point((rect.x0 + rect.x1) / 2.0, (rect.y0 + rect.y1) / 2.0)
    for trect in table_rects:
        if trect.contains(center):
            return True
    return False


def _image_blocks(doc: "fitz.Document", page: "fitz.Page", page_number: int) -> List[Block]:
    blocks: List[Block] = []
    seen_xrefs = set()
    try:
        images = page.get_images(full=True)
    except Exception as exc:
        logger.warning("get_images falhou na página %d: %s", page_number, exc)
        return blocks
    for image_info in images:
        xref = image_info[0]
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)
        try:
            extracted = doc.extract_image(xref)
            data = extracted.get("image", b"") if extracted else b""
        except Exception as exc:
            logger.warning("Falha ao extrair imagem xref=%d: %s", xref, exc)
            continue
        if not data:
            continue
        blocks.append(
            Block(
                kind=BlockKind.IMAGE,
                image_hash=hashlib.sha1(data).hexdigest(),
                page=page_number,
            )
        )
    return blocks


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def extract_pdf(path: str) -> Document:
    """Extrai um arquivo .pdf para o modelo canônico ``Document``.

    Levanta ``ValueError`` (mensagens em pt-BR) para arquivo inexistente,
    corrompido, protegido por senha ou sem conteúdo extraível.
    """
    p = Path(path)
    if not p.is_file():
        raise ValueError("Arquivo não encontrado: '%s'" % path)

    try:
        doc = fitz.open(str(p))
    except Exception as exc:
        raise ValueError(
            "Não foi possível abrir o PDF '%s': arquivo inválido ou corrompido (%s)"
            % (path, exc)
        ) from exc

    try:
        if doc.needs_pass:
            raise ValueError(
                "PDF protegido por senha, não é possível extrair: '%s'" % path
            )

        page_count = doc.page_count

        page_w = page_h = None
        if page_count > 0:
            try:
                rect0 = doc.load_page(0).rect
                page_w = float(rect0.width)
                page_h = float(rect0.height)
                # Se alguma página for mais larga (paisagem), usa a maior
                # largura vista — evita cortar balanços mistos.
                for pno in range(1, min(page_count, 8)):
                    r = doc.load_page(pno).rect
                    if float(r.width) > (page_w or 0):
                        page_w = float(r.width)
                        page_h = float(r.height)
            except Exception:
                page_w = page_h = None

        # Passe 1: coleta dados brutos de todas as páginas (texto + tabelas).
        raw_pages: List[Dict[str, Any]] = []
        page_tables: List[List[Any]] = []
        for pno in range(page_count):
            try:
                page = doc.load_page(pno)
                raw_pages.append(page.get_text("dict"))
            except Exception as exc:
                raise ValueError(
                    "Falha ao ler a página %d do PDF '%s': %s"
                    % (pno + 1, path, exc)
                ) from exc
            page_tables.append(_find_tables_safe(page))

        body_size = _body_font_size(raw_pages)

        # Passe 2: monta os blocos na ordem de leitura.
        blocks: List[Block] = []
        for pno in range(page_count):
            page_number = pno + 1
            raw = raw_pages[pno]
            tables = page_tables[pno]
            table_rects = [fitz.Rect(t.bbox) for t in tables]

            # (y0, x0, block) para preservar a ordem visual da página.
            items: List[Tuple[float, float, Block]] = []

            for raw_block in raw.get("blocks", []):
                if raw_block.get("type") != 0:
                    continue
                rect = fitz.Rect(raw_block.get("bbox", (0, 0, 0, 0)))
                if table_rects and _inside_any(rect, table_rects):
                    continue  # texto pertence a uma tabela: não duplica
                model_block = _text_block_to_model(raw_block, body_size, page_number)
                if model_block is not None:
                    items.append((rect.y0, rect.x0, model_block))

            for table in tables:
                table_block = _table_to_block(table, page_number)
                if table_block is not None:
                    trect = fitz.Rect(table.bbox)
                    items.append((trect.y0, trect.x0, table_block))

            items.sort(key=lambda item: (item[0], item[1]))
            blocks.extend(item[2] for item in items)

            # Imagens após os blocos de texto da página (ordem aproximada).
            blocks.extend(_image_blocks(doc, doc.load_page(pno), page_number))

        if not blocks:
            raise ValueError(
                "Documento vazio: nenhum conteúdo extraível em '%s'" % path
            )

        # PDF digitalizado (imagem sem camada de texto): comparar seria
        # inútil e SILENCIOSAMENTE errado — melhor falhar com clareza.
        text_chars = sum(
            len(b.normalized_text()) for b in blocks if b.kind != BlockKind.IMAGE
        )
        image_blocks_count = sum(1 for b in blocks if b.kind == BlockKind.IMAGE)
        if text_chars < 50 and image_blocks_count > 0:
            raise ValueError(
                "O PDF '%s' parece ser digitalizado (imagem, sem camada de "
                "texto) — a comparação de texto não funciona nele. "
                "Converta com OCR antes de comparar (suporte a OCR está no "
                "roadmap do diffAI)." % os.path.basename(str(p))
            )

        for i, block in enumerate(blocks):
            block.index = i

        metadata = doc.metadata or {}
        title = (metadata.get("title") or "").strip()
        if not title:
            title = p.stem

        return Document(
            source_path=str(p),
            fmt="pdf",
            blocks=blocks,
            page_count=page_count,
            title=title,
            page_width_pt=page_w,
            page_height_pt=page_h,
        )
    finally:
        doc.close()
