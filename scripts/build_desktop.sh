#!/bin/bash
# Empacota o diffAI Desktop em um .app (macOS) via PyInstaller.
#
# Uso:
#   ./scripts/build_desktop.sh              # build comercial (com licença)
#   ./scripts/build_desktop.sh --unlimited  # build de TESTE sem limites de plano
#
# Saída: dist/diffAI.app  +  dist/diffAI-mac.zip  (+ .dmg se hdiutil ok)
# Com --unlimited: dist/diffAI-mac-test-unlimited.zip
#
# Para DISTRIBUIR fora desta máquina ainda é preciso assinar e notarizar
# (conta Apple Developer): codesign + notarytool — ver docs/LICENCIAMENTO.md.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=.venv/bin/python
APP_NAME="diffAI"
UNLIMITED=0
for arg in "$@"; do
  case "$arg" in
    --unlimited|-u) UNLIMITED=1 ;;
  esac
done

FLAGS_FILE="app/licensing/build_flags.py"
FLAGS_BACKUP=""
restore_flags() {
  if [[ -n "${FLAGS_BACKUP}" && -f "${FLAGS_BACKUP}" ]]; then
    mv "${FLAGS_BACKUP}" "${FLAGS_FILE}"
    FLAGS_BACKUP=""
  fi
}
trap restore_flags EXIT

if [[ "$UNLIMITED" -eq 1 ]]; then
  echo "==> Build de TESTE ilimitado (sem limites de plano/trial)"
  FLAGS_BACKUP="$(mktemp)"
  cp "${FLAGS_FILE}" "${FLAGS_BACKUP}"
  cat > "${FLAGS_FILE}" <<'EOF'
"""Flags gravadas no build do desktop (não editar à mão em produção).

Build de TESTE gerado com scripts/build_desktop.sh --unlimited.
"""
from __future__ import annotations

UNLIMITED = True
EOF
fi

echo "==> Limpando builds anteriores"
rm -rf build/ dist/ "${APP_NAME}.spec" "Compare Docs.spec"

ICON_ICNS="assets/branding/diffai.icns"
ICON_PNG="assets/branding/diffai-icon.png"
ICON_FLAG=()
if [[ -f "$ICON_ICNS" ]]; then
  ICON_FLAG=(--icon "$ICON_ICNS")
elif [[ -f "$ICON_PNG" ]]; then
  ICON_FLAG=(--icon "$ICON_PNG")
else
  echo "AVISO: logo em assets/branding/ não encontrada — .app sem ícone custom."
fi

echo "==> Rodando PyInstaller (licença → Railway embutida em server_url.py)"
$PY -m PyInstaller \
  --name "$APP_NAME" \
  --windowed \
  --noconfirm \
  "${ICON_FLAG[@]}" \
  --add-data "web:web" \
  --collect-data docx \
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

# python-docx resolve templates via __file__/../templates (ex.: parts/hdrftr.py).
# No bundle, os .py ficam no PYZ e só os XML vão para Resources/docx/templates.
# Sem o diretório `parts` no disco, open(".../parts/../templates/...") falha com ENOENT.
echo "==> Corrigindo paths do python-docx no bundle"
DOCX_RES="${APP}/Contents/Resources/docx"
if [[ -d "${DOCX_RES}/templates" ]]; then
  mkdir -p "${DOCX_RES}/parts"
  # Garante ficheiros reais (não só symlink) sob Frameworks — App Translocation
  # no macOS por vezes parte symlinks relativos do PyInstaller.
  DOCX_FW="${APP}/Contents/Frameworks/docx"
  if [[ -L "${DOCX_FW}" ]]; then
    rm -f "${DOCX_FW}"
    mkdir -p "${DOCX_FW}/parts"
    cp -R "${DOCX_RES}/templates" "${DOCX_FW}/templates"
    [[ -f "${DOCX_RES}/py.typed" ]] && cp "${DOCX_RES}/py.typed" "${DOCX_FW}/py.typed"
  elif [[ -d "${DOCX_FW}" ]]; then
    mkdir -p "${DOCX_FW}/parts"
  fi
fi

ZIP_NAME="${APP_NAME}-mac.zip"
if [[ "$UNLIMITED" -eq 1 ]]; then
  ZIP_NAME="${APP_NAME}-mac-test-unlimited.zip"
fi

echo "==> Empacotando ZIP para download ($ZIP_NAME)"
(
  cd dist
  rm -f "$ZIP_NAME"
  ditto -c -k --sequesterRsrc --keepParent "${APP_NAME}.app" "$ZIP_NAME"
)

if command -v hdiutil >/dev/null 2>&1; then
  echo "==> Criando DMG"
  DMG="dist/${APP_NAME}-mac.dmg"
  if [[ "$UNLIMITED" -eq 1 ]]; then
    DMG="dist/${APP_NAME}-mac-test-unlimited.dmg"
  fi
  rm -f "$DMG"
  if ! hdiutil create -volname "$APP_NAME" -srcfolder "$APP" -ov -format UDZO "$DMG"; then
    echo "AVISO: DMG falhou (ZIP continua ok)."
  fi
fi

restore_flags
trap - EXIT

echo ""
echo "==> Build concluído"
echo "    App:  $APP"
echo "    Zip:  dist/$ZIP_NAME"
[[ "$UNLIMITED" -eq 1 ]] && echo "    Modo: TESTE ILIMITADO (plano beta, sem trial/limites)"
echo "    Teste: open \"$APP\""
echo "    Gatekeeper (quem receber): xattr -cr ~/Downloads/diffAI.app && open ~/Downloads/diffAI.app"
