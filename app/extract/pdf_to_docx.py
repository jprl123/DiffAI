"""Conversão PDF → DOCX (pdf2docx) para rotear pares PDF pelo pipeline Word.

Pares .pdf x .pdf historicamente caíam direto no gerador ReportLab
(app/output/redline_pdf.py), que re-tipografa o documento em layout
padronizado. Convertendo os dois PDFs para DOCX primeiro, o par passa a usar
o MESMO fluxo dos pares .docx: comparação canônica + redline in-place
preservando a formatação + PDF fiel via LibreOffice.

Só funciona para PDF nato-digital (com camada de texto). PDF escaneado
(imagem pura) geraria um DOCX vazio e um redline sem conteúdo — nesses casos
levantamos ``PdfConversionError`` e o chamador (app/jobs.py) volta ao gerador
padronizado, registrando warning no item.
"""
from __future__ import annotations

import copy
import logging
import os

logger = logging.getLogger(__name__)

# pdf2docx loga no ROOT logger (logging.info direto, com basicConfig no
# import) — uma linha por página convertida. O filtro abaixo derruba esses
# registros apenas enquanto a conversão roda.
class _DropRootRecords(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.name != "root"

# Mínimo de caracteres não-brancos no PDF inteiro para considerarmos que há
# camada de texto utilizável (abaixo disso tratamos como escaneado).
_MIN_TEXT_CHARS = 40


class PdfConversionError(ValueError):
    """PDF não pôde ser convertido para DOCX (escaneado, protegido, corrompido)."""


def _ensure_text_layer(pdf_path: str) -> None:
    import fitz  # PyMuPDF

    name = os.path.basename(pdf_path)
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise PdfConversionError("Não foi possível abrir '%s': %s" % (name, exc)) from exc
    try:
        if doc.needs_pass:
            raise PdfConversionError("PDF protegido por senha: '%s'." % name)
        chars = 0
        for page in doc:
            chars += len("".join(page.get_text().split()))
            if chars >= _MIN_TEXT_CHARS:
                return
    finally:
        doc.close()
    raise PdfConversionError(
        "PDF sem camada de texto (provavelmente escaneado): '%s'." % name
    )


def _is_pseudo_table(tbl) -> bool:
    """True se a tabela é, na verdade, um parágrafo corrido que o pdf2docx
    envolveu em grade (uma palavra por célula).

    Sinais: (a) uma única linha (qualquer largura), ou (b) muitas colunas
    (≥5) com a maioria das células de uma só palavra — parágrafo que quebrou
    em N linhas visuais vira tabela N×M. Tabelas REAIS destes contratos têm
    poucas colunas (2–4) com cabeçalho + dados, então não disparam (b).
    """
    n_rows = len(tbl.rows)
    if n_rows == 1:
        return True
    n_cols = len(tbl.columns)
    if n_cols < 5:
        return False
    cells = [c.text.strip() for row in tbl.rows for c in row.cells]
    nonempty = [txt for txt in cells if txt]
    if not nonempty:
        return False
    single_word = sum(1 for txt in nonempty if " " not in txt)
    return (single_word / len(nonempty)) >= 0.6


def _flatten_pseudo_tables(docx_path: str) -> int:
    """Achata pseudo-tabelas do pdf2docx em parágrafos (correção B3).

    Em PDF nativo, o pdf2docx frequentemente envolve parágrafos corridos em
    TABELAS com uma palavra por célula (ex.: "CONSIDERANDO | que | a |
    CONTRATANTE | …"). Renderizadas, quebram a visualização (vãos enormes,
    palavras partidas) e degradam o alinhamento do diff — e prendem trechos
    do texto que deveriam ser comparados como prosa (contribui para B1).
    Detectadas por ``_is_pseudo_table``, são desmontadas de volta a um
    parágrafo, na ordem de leitura (linha a linha), preservando os runs.

    Retorna quantas tabelas foram achatadas. Nunca levanta — falha aqui não
    deve derrubar a conversão.
    """
    from docx import Document
    from docx.oxml.ns import qn

    try:
        doc = Document(docx_path)
    except Exception as exc:
        logger.warning("Não foi possível reabrir '%s' p/ achatar tabelas (%s).",
                       os.path.basename(docx_path), exc)
        return 0

    body = doc.element.body
    flattened = 0
    for tbl in list(doc.tables):
        tbl_el = tbl._element
        # Só tabelas de nível superior (evita mexer em tabelas aninhadas).
        if tbl_el.getparent() is not body:
            continue
        if not _is_pseudo_table(tbl):
            continue  # tabelas reais (grade de campos) permanecem intactas

        new_p = tbl_el.makeelement(qn("w:p"), {})
        ppr_copied = False
        last_text = ""
        # Ordem de leitura: todas as linhas, célula a célula (um parágrafo que
        # quebrou em N linhas visuais virou uma tabela de N linhas).
        cells_in_order = [c for r in tbl.rows for c in r.cells]
        prev_cell_text = None
        for cell in cells_in_order:
            cell_text = cell.text.strip()
            # O pdf2docx às vezes duplica palavras em células vizinhas
            # ("tiverem | tiverem"). Como só achatamos PROSA (pseudo-tabela),
            # célula idêntica à anterior é sempre artefato — descarta.
            if cell_text and cell_text == prev_cell_text:
                continue
            if cell_text:
                prev_cell_text = cell_text
            for para in cell.paragraphs:
                ppr = para._p.find(qn("w:pPr"))
                if not ppr_copied and ppr is not None:
                    ppr_copy = copy.deepcopy(ppr)
                    # Remove o recuo herdado da célula (posição x no PDF) — num
                    # parágrafo normal isso vira 1ª linha deslocada. Mantém
                    # alinhamento/espaçamento.
                    for ind in ppr_copy.findall(qn("w:ind")):
                        ppr_copy.remove(ind)
                    new_p.append(ppr_copy)
                    ppr_copied = True
                for run in para.runs:
                    new_p.append(copy.deepcopy(run._element))
                    last_text = run.text or last_text
            # Garante um espaço entre células vizinhas se ainda não houver.
            if last_text and not last_text.endswith((" ", "\t", " ")):
                sep = new_p.makeelement(qn("w:r"), {})
                t = sep.makeelement(qn("w:t"), {qn("xml:space"): "preserve"})
                t.text = " "
                sep.append(t)
                new_p.append(sep)
                last_text = " "

        tbl_el.addprevious(new_p)
        tbl_el.getparent().remove(tbl_el)
        flattened += 1

    if flattened:
        try:
            doc.save(docx_path)
            logger.info("Pseudo-tabelas achatadas em %s: %d",
                        os.path.basename(docx_path), flattened)
        except Exception as exc:
            logger.warning("Falha ao salvar DOCX achatado '%s' (%s).",
                           os.path.basename(docx_path), exc)
            return 0
    return flattened


def _pdf_page_size_pt(pdf_path: str):
    """Retorna (width_pt, height_pt) da página mais larga do PDF."""
    import fitz

    doc = fitz.open(pdf_path)
    try:
        if doc.page_count <= 0:
            return None, None
        best_w = best_h = 0.0
        for pno in range(doc.page_count):
            rect = doc.load_page(pno).rect
            w, h = float(rect.width), float(rect.height)
            if w > best_w:
                best_w, best_h = w, h
        if best_w > 0 and best_h > 0:
            return best_w, best_h
    finally:
        doc.close()
    return None, None


def _apply_pdf_page_geometry(pdf_path: str, docx_path: str) -> None:
    """Copia largura/altura/orientação do PDF para as seções do DOCX.

    O pdf2docx costuma gravar A4 retrato mesmo quando o PDF é paisagem —
    o redline in-place + LibreOffice então corta o conteúdo. Forçamos a
    geometria real do PDF de origem.
    """
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.shared import Pt

    width_pt, height_pt = _pdf_page_size_pt(pdf_path)
    if not width_pt or not height_pt:
        return

    try:
        doc = Document(docx_path)
    except Exception as exc:
        logger.warning(
            "Não foi possível reabrir '%s' p/ aplicar geometria (%s).",
            os.path.basename(docx_path), exc,
        )
        return

    landscape = width_pt > height_pt
    try:
        for section in doc.sections:
            section.orientation = (
                WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
            )
            # python-docx troca width/height ao mudar orientation — redefine.
            section.page_width = Pt(width_pt)
            section.page_height = Pt(height_pt)
            # Margens um pouco menores em paisagem para caber tabelas largas.
            if landscape:
                for attr in ("left_margin", "right_margin"):
                    try:
                        current = getattr(section, attr)
                        if current and float(current.pt) > 54:  # > 0.75"
                            setattr(section, attr, Pt(36))  # 0.5"
                    except Exception:
                        pass
        doc.save(docx_path)
        logger.info(
            "Geometria PDF→DOCX: %.0f×%.0f pt (%s) em %s",
            width_pt, height_pt,
            "paisagem" if landscape else "retrato",
            os.path.basename(docx_path),
        )
    except Exception as exc:
        logger.warning(
            "Falha ao aplicar geometria de página em '%s' (%s).",
            os.path.basename(docx_path), exc,
        )


def convert_pdf_to_docx(pdf_path: str, docx_path: str) -> None:
    """Converte um PDF nato-digital em DOCX editável.

    Levanta ``PdfConversionError`` quando o PDF não tem texto extraível ou a
    conversão falha — o chamador decide o fallback.
    """
    if not pdf_path or not os.path.isfile(pdf_path):
        raise PdfConversionError("Arquivo PDF não encontrado: '%s'" % pdf_path)

    _ensure_text_layer(pdf_path)

    out_dir = os.path.dirname(os.path.abspath(docx_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    try:
        from pdf2docx import Converter
    except Exception as exc:
        raise PdfConversionError(
            "Biblioteca pdf2docx indisponível: %s" % exc
        ) from exc

    converter = None
    quiet = _DropRootRecords()
    logging.getLogger().addFilter(quiet)
    try:
        converter = Converter(pdf_path)
        converter.convert(docx_path)
    except PdfConversionError:
        raise
    except Exception as exc:
        raise PdfConversionError(
            "Falha ao converter '%s' para DOCX: %s" % (os.path.basename(pdf_path), exc)
        ) from exc
    finally:
        logging.getLogger().removeFilter(quiet)
        if converter is not None:
            try:
                converter.close()
            except Exception:
                pass

    if not os.path.isfile(docx_path) or os.path.getsize(docx_path) == 0:
        raise PdfConversionError(
            "Conversão de '%s' não produziu DOCX válido." % os.path.basename(pdf_path)
        )
    # Correção B3: desfaz as pseudo-tabelas (parágrafos corridos que o pdf2docx
    # envolve em tabela) antes de o par seguir para extração/comparação.
    _flatten_pseudo_tables(docx_path)
    # Paisagem / tamanho real da página do PDF (pdf2docx tende a forçar A4).
    _apply_pdf_page_geometry(pdf_path, docx_path)
    logger.info("PDF convertido para DOCX: %s -> %s", pdf_path, docx_path)
