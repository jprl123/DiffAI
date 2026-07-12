"""Marca do escritório (white-label) — logo nos relatórios e resumos.

Exclusivo do plano Equipe (feature ``branding`` no payload da licença).
O logo fica em ``~/.comparedocs/branding/logo.<png|jpg>``; PNG e JPEG apenas,
até 1 MB. Os renderizadores (PDF padronizado, resumo executivo, relatório
HTML) chamam ``active_logo_path()`` — que só devolve o arquivo quando o
plano atual permite, então perder a licença desliga a marca sozinho.
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

BRANDING_DIR = os.environ.get(
    "COMPAREDOCS_BRANDING_DIR",
    os.path.join(os.path.expanduser("~"), ".comparedocs", "branding"),
)
MAX_LOGO_BYTES = 1_000_000

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"


def _logo_candidates() -> list:
    return [
        os.path.join(BRANDING_DIR, "logo.png"),
        os.path.join(BRANDING_DIR, "logo.jpg"),
    ]


def stored_logo_path() -> Optional[str]:
    """Logo salvo no disco, independente de plano (para a UI de Conta)."""
    for path in _logo_candidates():
        if os.path.isfile(path):
            return path
    return None


def branding_allowed() -> bool:
    """True quando o plano atual inclui a feature de marca (Equipe)."""
    from app.licensing import client as licensing

    st = licensing.status()
    if st.get("state") != "active":
        return False
    return bool((st.get("features") or {}).get("branding"))


def active_logo_path() -> Optional[str]:
    """Logo pronto para uso nos renderizadores — None se plano não permite."""
    path = stored_logo_path()
    if path is None:
        return None
    if not branding_allowed():
        return None
    return path


def active_logo_data_uri() -> Optional[str]:
    """Logo como data URI (para o relatório HTML auto-contido)."""
    path = active_logo_path()
    if path is None:
        return None
    mime = "image/png" if path.endswith(".png") else "image/jpeg"
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    return "data:%s;base64,%s" % (mime, base64.b64encode(data).decode("ascii"))


def save_logo(data: bytes) -> str:
    """Valida e grava o logo. Retorna o caminho. Lança ValueError com
    mensagem pt-BR em conteúdo inválido."""
    if not data:
        raise ValueError("Arquivo de logo vazio.")
    if len(data) > MAX_LOGO_BYTES:
        raise ValueError("Logo muito grande — o limite é 1 MB.")
    if data.startswith(_PNG_MAGIC):
        ext = "png"
    elif data.startswith(_JPEG_MAGIC):
        ext = "jpg"
    else:
        raise ValueError("Formato não suportado — envie um PNG ou JPEG.")
    clear_logo()
    os.makedirs(BRANDING_DIR, exist_ok=True)
    path = os.path.join(BRANDING_DIR, "logo." + ext)
    with open(path, "wb") as fh:
        fh.write(data)
    logger.info("Logo do escritório salvo em %s", path)
    return path


def clear_logo() -> bool:
    removed = False
    for path in _logo_candidates():
        try:
            os.remove(path)
            removed = True
        except OSError:
            pass
    return removed


def branding_status() -> Dict[str, Any]:
    """Estado para a UI: {allowed, has_logo, active}."""
    allowed = branding_allowed()
    has_logo = stored_logo_path() is not None
    return {"allowed": allowed, "has_logo": has_logo, "active": allowed and has_logo}
