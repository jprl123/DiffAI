#!/usr/bin/env bash
# Entrypoint para Railway / Docker — SQLite e chave Ed25519 em volume persistente.
set -euo pipefail

DATA_DIR="${COMPAREDOCS_DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"

export COMPAREDOCS_LICENSE_DB="${COMPAREDOCS_LICENSE_DB:-$DATA_DIR/licenses.db}"
export COMPAREDOCS_SIGNING_KEY="${COMPAREDOCS_SIGNING_KEY:-$DATA_DIR/signing_key.pem}"

# Opcional: colar a chave privada PEM inteira na env COMPAREDOCS_SIGNING_KEY_PEM (Railway Secret)
if [ -n "${COMPAREDOCS_SIGNING_KEY_PEM:-}" ] && [ ! -f "$COMPAREDOCS_SIGNING_KEY" ]; then
  printf '%b' "$COMPAREDOCS_SIGNING_KEY_PEM" > "$COMPAREDOCS_SIGNING_KEY"
  chmod 600 "$COMPAREDOCS_SIGNING_KEY"
  echo "Chave de assinatura gravada em $COMPAREDOCS_SIGNING_KEY (via env)."
fi

if [ ! -f "$COMPAREDOCS_SIGNING_KEY" ]; then
  DEV_KEY="/app/licensing_server/dev_signing_key.pem"
  if [ -f "$DEV_KEY" ]; then
    echo "AVISO: usando chave de DESENVOLVIMENTO. Gere produção antes de vender de verdade."
    export COMPAREDOCS_SIGNING_KEY="$DEV_KEY"
  else
    echo "ERRO: chave de assinatura ausente. Configure COMPAREDOCS_SIGNING_KEY_PEM ou volume em /data."
    exit 1
  fi
fi

PORT="${PORT:-8390}"
echo "diffAI licensing — db=$COMPAREDOCS_LICENSE_DB port=$PORT"
exec uvicorn licensing_server.server:app --host 0.0.0.0 --port "$PORT"
