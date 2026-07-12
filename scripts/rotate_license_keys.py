#!/usr/bin/env python3
"""Rotação das chaves de assinatura de licenças (dev → produção).

O que faz, em um comando:
1. Gera um NOVO par Ed25519 em ~/.comparedocs-server/signing_key.pem
   (FORA do repositório — a chave privada de produção nunca é versionada).
2. Atualiza app/licensing/pubkey.py com a nova chave pública.
3. O servidor de licenças passa a usar a nova chave automaticamente
   (licensing_server/crypto.py prefere esse caminho quando o arquivo existe).

Consequência esperada: licenças assinadas com a chave ANTIGA param de validar —
todo mundo precisa reativar (em produção, rotacionar = invalidar a base; por
isso se faz UMA vez antes do lançamento). Recuse-se a sobrescrever uma chave
de produção existente sem --force.

Uso: .venv/bin/python scripts/rotate_license_keys.py [--force]
"""
from __future__ import annotations

import argparse
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)

KEY_PATH = os.path.join(
    os.path.expanduser("~"), ".comparedocs-server", "signing_key.pem"
)
PUBKEY_PY = os.path.join(PROJECT_ROOT, "app", "licensing", "pubkey.py")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="sobrescreve uma chave de produção existente")
    args = parser.parse_args()

    if os.path.exists(KEY_PATH) and not args.force:
        print("Já existe chave de produção em %s." % KEY_PATH)
        print("Rotacionar INVALIDA todas as licenças emitidas com ela.")
        print("Se é isso mesmo, rode de novo com --force.")
        return 1

    import base64

    priv = Ed25519PrivateKey.generate()
    os.makedirs(os.path.dirname(KEY_PATH), exist_ok=True)
    with open(KEY_PATH, "wb") as fh:
        fh.write(priv.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
    os.chmod(KEY_PATH, 0o600)

    pub_b64 = base64.b64encode(priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )).decode("ascii")

    with open(PUBKEY_PY, "r", encoding="utf-8") as fh:
        source = fh.read()
    new_source, count = re.subn(
        r'LICENSE_PUBLIC_KEY_B64 = "[^"]*"',
        'LICENSE_PUBLIC_KEY_B64 = "%s"' % pub_b64,
        source,
    )
    if count != 1:
        print("ERRO: não encontrei LICENSE_PUBLIC_KEY_B64 em %s" % PUBKEY_PY)
        return 1
    with open(PUBKEY_PY, "w", encoding="utf-8") as fh:
        fh.write(new_source)

    print("Par de chaves rotacionado com sucesso.")
    print("  Privada (NUNCA versionar; faça backup seguro): %s" % KEY_PATH)
    print("  Pública atualizada em: app/licensing/pubkey.py")
    print()
    print("Próximos passos:")
    print("  1. Reinicie o servidor de licenças.")
    print("  2. Reative as licenças existentes (as antigas não validam mais).")
    print("  3. No deploy da VPS, copie a privada para o servidor e aponte")
    print("     COMPAREDOCS_SIGNING_KEY para o caminho dela.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
