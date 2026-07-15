"""Saída XLSX redline — planilha marcada com diff célula a célula."""
from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

from app.xlsx.compare import XlsxDiff
from app.xlsx.models import ColorConfig
from app.xlsx.redline import generate_redline_xlsx

logger = logging.getLogger(__name__)


def write_redline_xlsx(
    base_path: str,
    compare_path: str,
    out_path: str,
    colors: Optional[ColorConfig] = None,
) -> XlsxDiff:
    """Gera o XLSX redline comparando base vs revisado. Retorna o diff."""
    with open(base_path, "rb") as fh:
        base_bytes = fh.read()
    with open(compare_path, "rb") as fh:
        compare_bytes = fh.read()

    if not base_bytes:
        raise ValueError("Arquivo base vazio: '%s'" % base_path)
    if not compare_bytes:
        raise ValueError("Arquivo de comparação vazio: '%s'" % compare_path)

    data, diff = generate_redline_xlsx(
        base_bytes,
        compare_bytes,
        colors=colors,
        base_filename=os.path.basename(base_path),
        compare_filename=os.path.basename(compare_path),
    )

    parent = os.path.dirname(os.path.abspath(out_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.write(data)

    logger.info("Redline XLSX gravado em %s", out_path)
    return diff
