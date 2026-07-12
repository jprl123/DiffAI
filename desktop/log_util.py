"""Logging do app desktop — arquivo + terminal."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# App empacotado (PyInstaller): logs na pasta do usuário, nunca dentro do bundle.
if getattr(sys, "frozen", False):
    LOG_DIR = os.path.join(os.path.expanduser("~"), ".comparedocs", "logs")
else:
    LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "desktop.log")

_configured = False


def setup_logging() -> logging.Logger:
    """Configura logger 'comparedocs.desktop' (idempotente)."""
    global _configured
    logger = logging.getLogger("comparedocs.desktop")
    if _configured:
        return logger

    os.makedirs(LOG_DIR, exist_ok=True)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    logger.info("=== Compare Docs Desktop — sessão %s ===", datetime.now().isoformat())
    logger.info("Python: %s", sys.executable)
    logger.info("Log em: %s", LOG_FILE)

    _configured = True
    return logger
