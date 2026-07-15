"""Flags gravadas no build do desktop (não editar à mão em produção).

O script ``scripts/build_desktop.sh --unlimited`` define ``UNLIMITED = True``
só na cópia empacotada, para builds de teste beta sem limite de plano.
"""
from __future__ import annotations

# False em releases comerciais. True só em builds de teste (--unlimited).
UNLIMITED = False
