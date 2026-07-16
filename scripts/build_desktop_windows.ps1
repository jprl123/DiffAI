# Empacota o DiffAI Desktop em um .exe (Windows) via PyInstaller.
#
# Uso (PowerShell, na raiz do repo, com .venv ativo):
#   .\scripts\build_desktop_windows.ps1
#   .\scripts\build_desktop_windows.ps1 -Unlimited
#
# Saída: dist\diffAI\diffAI.exe  +  dist\diffAI-windows.zip
# Com -Unlimited: dist\diffAI-windows-test-unlimited.zip
#
# Requer Windows (ou CI windows-latest). Não roda em macOS/Linux.

param(
    [switch]$Unlimited
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$AppName = "diffAI"
$Py = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

$FlagsFile = "app\licensing\build_flags.py"
$FlagsBackup = $null

function Restore-Flags {
    if ($FlagsBackup -and (Test-Path $FlagsBackup)) {
        Move-Item -Force $FlagsBackup $FlagsFile
        $script:FlagsBackup = $null
    }
}

try {
    if ($Unlimited) {
        Write-Host "==> Build de TESTE ilimitado (sem limites de plano/trial)"
        $FlagsBackup = [System.IO.Path]::GetTempFileName()
        Copy-Item $FlagsFile $FlagsBackup -Force
        @"
"""Flags gravadas no build do desktop (não editar à mão em produção).

Build de TESTE gerado com scripts/build_desktop_windows.ps1 -Unlimited.
"""
from __future__ import annotations

UNLIMITED = True
"@ | Set-Content -Path $FlagsFile -Encoding UTF8
    }

    Write-Host "==> Limpando builds anteriores"
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist
    Remove-Item -Force -ErrorAction SilentlyContinue "$AppName.spec", "Compare Docs.spec"

    $IconFlag = @()
    if (Test-Path "assets\branding\diffai.ico") {
        $IconFlag = @("--icon", "assets\branding\diffai.ico")
    } elseif (Test-Path "assets\branding\diffai-icon.png") {
        $IconFlag = @("--icon", "assets\branding\diffai-icon.png")
    } else {
        Write-Host "AVISO: ícone em assets/branding/ não encontrado — .exe sem ícone custom."
    }

    Write-Host "==> Instalando PyInstaller (se necessário)"
    & $Py -m pip install -q "pyinstaller>=6.0"

    Write-Host "==> Rodando PyInstaller"
    # No Windows, --add-data usa ponto-e-vírgula: "origem;destino"
    & $Py -m PyInstaller `
        --name $AppName `
        --windowed `
        --noconfirm `
        --onedir `
        @IconFlag `
        --add-data "web;web" `
        --collect-data docx `
        --collect-submodules app `
        --collect-submodules reportlab `
        --hidden-import openpyxl `
        --hidden-import uvicorn.logging `
        --hidden-import uvicorn.loops.auto `
        --hidden-import uvicorn.protocols.http.auto `
        --hidden-import uvicorn.protocols.websockets.auto `
        --hidden-import uvicorn.lifespan.on `
        --hidden-import clr `
        desktop\launcher.py

    $ExeDir = "dist\$AppName"
    $Exe = Join-Path $ExeDir "$AppName.exe"
    if (-not (Test-Path $Exe)) {
        throw "ERRO: $Exe não foi gerado."
    }

    # python-docx: garante pasta parts/ junto dos templates (mesmo fix do macOS).
    Write-Host "==> Corrigindo paths do python-docx no bundle"
    $DocxRes = Join-Path $ExeDir "_internal\docx"
    if (Test-Path (Join-Path $DocxRes "templates")) {
        New-Item -ItemType Directory -Force -Path (Join-Path $DocxRes "parts") | Out-Null
    }

    $ZipName = if ($Unlimited) { "$AppName-windows-test-unlimited.zip" } else { "$AppName-windows.zip" }
    $ZipPath = Join-Path "dist" $ZipName
    Write-Host "==> Empacotando ZIP ($ZipName)"
    Remove-Item -Force -ErrorAction SilentlyContinue $ZipPath
    Compress-Archive -Path $ExeDir -DestinationPath $ZipPath -Force

    Write-Host ""
    Write-Host "==> Build concluído"
    Write-Host "    Exe:  $Exe"
    Write-Host "    Zip:  $ZipPath"
    if ($Unlimited) {
        Write-Host "    Modo: TESTE ILIMITADO (plano beta, sem trial/limites)"
    }
    Write-Host "    Nota: Windows 10/11 precisa do WebView2 Runtime (já vem na maioria das máquinas)."
}
finally {
    Restore-Flags
}
