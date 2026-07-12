"""Assinatura de licenças (Ed25519).

O servidor assina o payload da licença com a chave PRIVADA; o app embute a
chave PÚBLICA e verifica a assinatura offline. Sem a chave privada é
impossível forjar uma licença válida.

ATENÇÃO (produção): ``dev_signing_key.pem`` é a chave de DESENVOLVIMENTO,
versionada junto com o código para facilitar testes. Antes de distribuir
comercialmente: gere um novo par (``python -m licensing_server.crypto``),
guarde a privada só no servidor (fora do repositório) e atualize a pública
em ``app/licensing/pubkey.py``.
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

_PROD_KEY_PATH = os.path.join(
    os.path.expanduser("~"), ".comparedocs-server", "signing_key.pem"
)
_DEV_KEY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "dev_signing_key.pem"
)

# Ordem de preferência: env explícita > chave de produção (fora do repo,
# criada por scripts/rotate_license_keys.py) > chave de desenvolvimento.
DEFAULT_KEY_PATH = os.environ.get("COMPAREDOCS_SIGNING_KEY") or (
    _PROD_KEY_PATH if os.path.isfile(_PROD_KEY_PATH) else _DEV_KEY_PATH
)


def canonical_json(payload: Dict[str, Any]) -> bytes:
    """Serialização determinística — a MESMA no servidor e no app."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def load_private_key(path: str = DEFAULT_KEY_PATH) -> Ed25519PrivateKey:
    with open(path, "rb") as fh:
        key = serialization.load_pem_private_key(fh.read(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Chave de assinatura inválida: esperado Ed25519.")
    return key


def sign_payload(payload: Dict[str, Any], key_path: str = DEFAULT_KEY_PATH) -> str:
    """Assina o payload e retorna a assinatura em base64."""
    signature = load_private_key(key_path).sign(canonical_json(payload))
    return base64.b64encode(signature).decode("ascii")


def public_key_b64(key_path: str = DEFAULT_KEY_PATH) -> str:
    pub = load_private_key(key_path).public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return base64.b64encode(pub).decode("ascii")


if __name__ == "__main__":
    # Gera um NOVO par de chaves no caminho indicado (não sobrescreve).
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "signing_key.pem"
    if os.path.exists(target):
        print("Arquivo já existe: %s (não sobrescrevo chaves)." % target)
        sys.exit(1)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    with open(target, "wb") as fh:
        fh.write(pem)
    os.chmod(target, 0o600)
    print("Chave privada gravada em %s" % target)
    print("Chave pública (embutir no app):", public_key_b64(target))
