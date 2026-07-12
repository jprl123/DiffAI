#!/usr/bin/env bash
# Sobe o servidor de licenças + encaminha webhooks Stripe (sandbox).
# Pré-requisitos:
#   1. cp .env.example .env  e preencha sk_test_ / price_ test / etc.
#   2. brew install stripe/stripe-cli/stripe && stripe login
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Crie .env a partir de .env.example antes." >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a; source .env; set +a

echo "→ Servidor de licenças em :8390"
.venv/bin/python -m licensing_server.server &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

sleep 1
echo "→ stripe listen → localhost:8390/v1/stripe/webhook"
echo "  (copie o whsec_... para STRIPE_WEBHOOK_SECRET no .env e reinicie se for a 1ª vez)"
echo "→ Checkout de teste: open http://127.0.0.1:8390/v1/checkout/pro"
exec stripe listen --forward-to localhost:8390/v1/stripe/webhook
