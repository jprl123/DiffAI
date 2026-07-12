#!/bin/bash
# Empacota o Compare Docs Desktop em um .app (macOS) via PyInstaller.
#
# Uso: ./scripts/build_desktop.sh
# Saída: dist/Compare Docs.app
#
# Para DISTRIBUIR fora desta máquina ainda é preciso assinar e notarizar
# (conta Apple Developer): codesign + notarytool — ver docs/LICENCIAMENTO.md.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=.venv/bin/python

echo "==> Limpando builds anteriores"
rm -rf build/ dist/ CompareDocs.spec

echo "==> Rodando PyInstaller"
$PY -m PyInstaller \
  --name "Compare Docs" \
  --windowed \
  --noconfirm \
  --add-data "web:web" \
  --collect-submodules app \
  --collect-submodules reportlab \
  --hidden-import openpyxl \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan.on \
  --osx-bundle-identifier "app.comparedocs.desktop" \
  desktop/launcher.py

echo ""
echo "==> Build concluído: dist/Compare Docs.app"
echo "    Teste local:  open \"dist/Compare Docs.app\""
echo "    (Gatekeeper: para distribuir, assinar + notarizar.)"
