"""Dados da página de síntese ("Summary of Changes") — fonte única.

Usado pelo redline DOCX in-place (que vira o PDF fiel via LibreOffice) e
pelo redline PDF padronizado, para que as duas saídas apresentem sempre a
mesma síntese.
"""
from __future__ import annotations

import datetime
import os
import sys
from typing import List, Optional, Tuple

from app.models import ComparisonResult

APP_NAME = "DiffAI"
SUMMARY_TITLE = "Summary of Changes"

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def app_logo_path() -> Optional[str]:
    """Logo embutida do produto (sempre disponível — não é white-label)."""
    candidates = [
        os.path.join(_PROJECT_ROOT, "web", "logo.png"),
        os.path.join(_PROJECT_ROOT, "web", "logo-128.png"),
        os.path.join(_PROJECT_ROOT, "assets", "branding", "diffai-icon.png"),
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates = [
            os.path.join(meipass, "web", "logo.png"),
            os.path.join(meipass, "web", "logo-128.png"),
            os.path.join(meipass, "assets", "branding", "diffai-icon.png"),
        ] + candidates
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def format_compared_at(iso_timestamp: str) -> str:
    """ISO -> 'dd/mm/aaaa hh:mm' (ou o texto original se não parsear)."""
    if not iso_timestamp:
        return "—"
    try:
        dt = datetime.datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso_timestamp


def summary_rows(result: ComparisonResult) -> List[Tuple[str, str]]:
    """Linhas (métrica, valor) da síntese, na ordem de exibição.

    Total de alterações = inserções + exclusões + movimentações.
    """
    s = result.stats
    total = int(s.insertions) + int(s.deletions) + int(s.moves)
    return [
        ("Data da comparação", format_compared_at(result.compared_at)),
        ("Arquivo base", os.path.basename(result.base_path or "") or "—"),
        ("Arquivo revisado", os.path.basename(result.compare_path or "") or "—"),
        ("Total de alterações", str(total)),
        ("Inserções", str(s.insertions)),
        ("Exclusões", str(s.deletions)),
        ("Movimentações", str(s.moves)),
    ]
