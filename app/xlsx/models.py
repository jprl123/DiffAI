"""Modelos auxiliares do pipeline de comparação XLSX."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class ColorConfig:
    """Cores padrão do redline (estilo Litera Compare)."""

    deletion: str = "#DC2626"
    insertion: str = "#2563EB"
    moved: str = "#16A34A"


@dataclass
class SummaryStats:
    """Totais de alto nível para a aba Summary."""

    deletions: int = 0
    insertions: int = 0
    moved: int = 0
    changed_pages: List[int] = field(default_factory=list)
    compared_on: str = ""
