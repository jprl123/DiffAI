"""Ponto de entrada da extração: despacho por extensão de arquivo."""
from __future__ import annotations

import logging
from pathlib import Path

from app.extract.docx_extractor import extract_docx
from app.extract.pdf_extractor import extract_pdf
from app.extract.xlsx_extractor import extract_xlsx
from app.models import Document

logger = logging.getLogger(__name__)

_EXTRACTORS = {
    ".docx": extract_docx,
    ".pdf": extract_pdf,
    ".xlsx": extract_xlsx,
    ".xlsm": extract_xlsx,
}


def load_document(path: str) -> Document:
    """Carrega um documento (.docx, .pdf ou .xlsx) para o modelo canônico.

    Levanta ``ValueError`` (mensagens em pt-BR) para caminho vazio, arquivo
    inexistente ou formato não suportado.
    """
    if path is None or not str(path).strip():
        raise ValueError("Caminho de arquivo vazio: informe um .docx, .pdf, .xlsx ou .xlsm.")

    p = Path(str(path))
    if not p.exists():
        raise ValueError("Arquivo não encontrado: '%s'" % path)
    if not p.is_file():
        raise ValueError("O caminho não aponta para um arquivo: '%s'" % path)

    ext = p.suffix.lower()
    extractor = _EXTRACTORS.get(ext)
    if extractor is None:
        raise ValueError(
            "Formato não suportado: '%s'. Formatos aceitos: .docx, .pdf, .xlsx e .xlsm."
            % (ext or p.name)
        )

    logger.info("Extraindo %s (%s)", p.name, ext)
    return extractor(str(p))
