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
    logger.info("PDF convertido para DOCX: %s -> %s", pdf_path, docx_path)
