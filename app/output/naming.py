"""Nomes padronizados dos arquivos de saída do Compare-Docs.

Contrato (docs/ARCHITECTURE.md):
    redline_pdf_name        -> "[Redline] {base} vs {compare}.pdf"
    changed_pages_pdf_name  -> "[Redline-Changed Pages] {base} vs {compare}.pdf"
    redline_docx_name       -> "[Redline] {base} vs {compare}.docx"
    report_name             -> "[Report] {base} vs {compare}.{ext}"

{base}/{compare} são os stems (nome do arquivo sem extensão), sanitizados:
caracteres proibidos em nomes de arquivo são removidos, espaços colapsados e
o comprimento é limitado para evitar estourar o limite do sistema de arquivos.
"""
from __future__ import annotations

import os
import re
from typing import Optional

# Caracteres proibidos em nomes de arquivo (Windows é o denominador comum:
# < > : " / \ | ? *), mais caracteres de controle.
_FORBIDDEN_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')

# Limite defensivo por stem — mantém o nome final bem abaixo dos 255 bytes
# permitidos pela maioria dos sistemas de arquivos.
_MAX_STEM_LEN = 100

_FALLBACK_STEM = "documento"

# Sufixos localizados por idioma (item 5). O idioma vem de settings.json
# (mesmo store da UI); None/desconhecido → pt (comportamento histórico).
# "[Redline]" é termo de arte — igual nos dois idiomas.
_LABELS = {
    "pt": {
        "changed_pages": "Redline-Páginas Alteradas",
        "summary": "Resumo",
        "report": "Relatório",
    },
    "en": {
        "changed_pages": "Redline-Changed Pages",
        "summary": "Summary",
        "report": "Report",
    },
}


def _lang() -> str:
    """Idioma atual (pt|en) a partir de settings; pt como padrão seguro."""
    try:
        from app.settings import get_store

        lang = get_store().get().get("language")
        if lang in _LABELS:
            return lang
    except Exception:
        pass
    return "pt"


def sanitize_stem(name: Optional[str]) -> str:
    """Sanitiza um stem para uso seguro em nome de arquivo.

    Remove caracteres proibidos, colapsa espaços, apara pontos/espaços das
    bordas (inválidos no fim de nomes no Windows) e trunca stems muito longos.
    Retorna um fallback quando o resultado ficaria vazio.
    """
    if not name:
        return _FALLBACK_STEM
    cleaned = _FORBIDDEN_RE.sub("", str(name))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if len(cleaned) > _MAX_STEM_LEN:
        cleaned = cleaned[:_MAX_STEM_LEN].rstrip(" .")
    return cleaned or _FALLBACK_STEM


def _stem(path: Optional[str]) -> str:
    """Extrai e sanitiza o stem (nome sem extensão) de um caminho."""
    if not path:
        return _FALLBACK_STEM
    base = os.path.basename(str(path).rstrip("/\\"))
    stem, _ext = os.path.splitext(base)
    return sanitize_stem(stem or base)


def _pair(base_path: str, compare_path: str) -> str:
    return "%s vs %s" % (_stem(base_path), _stem(compare_path))


def redline_pdf_name(base_path: str, compare_path: str) -> str:
    """Nome do PDF redline completo."""
    return "[Redline] %s.pdf" % _pair(base_path, compare_path)


def changed_pages_pdf_name(base_path: str, compare_path: str) -> str:
    """Nome do PDF redline contendo apenas as páginas alteradas (localizado)."""
    return "[%s] %s.pdf" % (_LABELS[_lang()]["changed_pages"], _pair(base_path, compare_path))


def redline_docx_name(base_path: str, compare_path: str) -> str:
    """Nome do DOCX redline (versão editável)."""
    return "[Redline] %s.docx" % _pair(base_path, compare_path)


def redline_xlsx_name(base_path: str, compare_path: str) -> str:
    """Nome do XLSX redline (planilha marcada)."""
    return "[Redline] %s.xlsx" % _pair(base_path, compare_path)


def report_name(base_path: str, compare_path: str, ext: str) -> str:
    """Nome do relatório analítico ("html", "xlsx" ou "json")."""
    if ext is None:
        raise ValueError("Extensão do relatório não informada (esperado: html, xlsx ou json).")
    clean_ext = str(ext).strip().lstrip(".").lower()
    if not clean_ext or not re.match(r"^[a-z0-9]+$", clean_ext):
        raise ValueError(
            "Extensão de relatório inválida: %r (esperado algo como html, xlsx ou json)." % (ext,)
        )
    return "[%s] %s.%s" % (_LABELS[_lang()]["report"], _pair(base_path, compare_path), clean_ext)


def exec_summary_name(base_path: str, compare_path: str) -> str:
    """Nome do resumo executivo de 1 página (localizado)."""
    return "[%s] %s.pdf" % (_LABELS[_lang()]["summary"], _pair(base_path, compare_path))
