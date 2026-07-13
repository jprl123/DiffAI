#!/bin/bash
# Empacota o diffAI Desktop em um .app (macOS) via PyInstaller.
#
# Uso: ./scripts/build_desktop.sh
# Saída: dist/diffAI.app  +  dist/diffAI-mac.zip  (+ .dmg se hdiutil ok)
#
# Para DISTRIBUIR fora desta máquina ainda é preciso assinar e notarizar
# (conta Apple Developer): codesign + notarytool — ver docs/LICENCIAMENTO.md.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=.venv/bin/python
APP_NAME="diffAI"

echo "==> Limpando builds anteriores"
rm -rf build/ dist/ "${APP_NAME}.spec" "Compare Docs.spec"

echo "==> Rodando PyInstaller (licença → Railway embutida em server_url.py)"
$PY -m PyInstaller \
  --name "$APP_NAME" \
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
  --osx-bundle-identifier "app.diffai.desktop" \
  desktop/launcher.py

APP="dist/${APP_NAME}.app"
if [[ ! -d "$APP" ]]; then
  echo "ERRO: $APP não foi gerado."
  exit 1
fi

echo "==> Empacotando ZIP para download"
(
  cd dist
  rm -f "${APP_NAME}-mac.zip"
  ditto -c -k --sequesterRsrc --keepParent "${APP_NAME}.app" "${APP_NAME}-mac.zip"
)

if command -v hdiutil >/dev/null 2>&1; then
  echo "==> Criando DMG"
  DMG="dist/${APP_NAME}-mac.dmg"
  rm -f "$DMG"
  hdiutil create -volname "$APP_NAME" -srcfolder "$APP" -ov -format UDZO "$DMG"
fi

echo ""
echo "==> Build concluído"
echo "    App:  $APP"
echo "    Zip:  dist/${APP_NAME}-mac.zip"
[[ -f "dist/${APP_NAME}-mac.dmg" ]] && echo "    DMG:  dist/${APP_NAME}-mac.dmg"
echo "    Teste: open \"$APP\""
echo "    (Gatekeeper: para distribuir sem aviso, assinar + notarizar.)"
