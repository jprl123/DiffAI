#!/bin/bash
# Instala Python moderno (Homebrew) e recria o venv do projeto.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON_FORMULA="${PYTHON_FORMULA:-python@3.14}"
BREW_PY="/opt/homebrew/opt/${PYTHON_FORMULA}/bin/python3"

if ! command -v brew >/dev/null 2>&1; then
  echo "Erro: Homebrew não encontrado. Instale em https://brew.sh" >&2
  exit 1
fi

if [ ! -x "$BREW_PY" ]; then
  echo "Instalando ${PYTHON_FORMULA} via Homebrew…"
  brew install "${PYTHON_FORMULA}"
fi

if [ ! -x "$BREW_PY" ]; then
  # fallback: python3.14 / python3.13 no PATH do Homebrew
  for candidate in python3.14 python3.13; do
    if command -v "$candidate" >/dev/null 2>&1; then
      BREW_PY="$(command -v "$candidate")"
      break
    fi
  done
fi

if [ ! -x "$BREW_PY" ]; then
  echo "Erro: não encontrei o interpretador após instalar ${PYTHON_FORMULA}." >&2
  exit 1
fi

echo "Usando: $($BREW_PY --version) ($BREW_PY)"

if [ -d .venv ]; then
  echo "Removendo venv antigo…"
  rm -rf .venv
fi

echo "Criando .venv…"
"$BREW_PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo ""
echo "Pronto. Versão do projeto:"
.venv/bin/python --version
echo ""
echo "Para usar este Python no terminal global, adicione ao ~/.zshrc:"
echo '  export PATH="/opt/homebrew/opt/python@3.14/bin:$PATH"'
echo ""
echo "Depois rode: source ~/.zshrc && python3 --version"
