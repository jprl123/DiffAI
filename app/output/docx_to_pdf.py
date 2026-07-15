"""Conversão DOCX → PDF preservando layout (LibreOffice headless).

Usa um perfil de usuário DEDICADO (``-env:UserInstallation``): sem isso o
soffice headless falha silenciosamente sempre que o LibreOffice estiver
aberto como aplicativo, porque o perfil padrão fica travado pela instância
gráfica. Com perfil próprio a conversão funciona mesmo com o app aberto.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from typing import List, Optional

logger = logging.getLogger(__name__)

# Página oficial — detecta Mac Apple Silicon / Intel no browser.
LIBREOFFICE_DOWNLOAD_URL = (
    "https://www.libreoffice.org/download/download-libreoffice/"
)

_PROFILE_DIR = os.path.join(
    os.path.expanduser("~"), ".comparedocs", "libreoffice_profile"
)

_MAC_SOFFICE = "/Applications/LibreOffice.app/Contents/MacOS/soffice"


def _candidate_commands() -> List[str]:
    cmds = ["soffice", "libreoffice"]
    if sys.platform == "darwin":
        if os.path.isfile(_MAC_SOFFICE):
            cmds.insert(0, _MAC_SOFFICE)
    elif sys.platform == "win32":
        for win_path in (
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ):
            if os.path.isfile(win_path):
                cmds.insert(0, win_path)
    return cmds


def find_soffice() -> Optional[str]:
    """Caminho absoluto do soffice, ou None se LibreOffice não estiver instalado."""
    for cmd in _candidate_commands():
        if os.path.isfile(cmd):
            return cmd
        resolved = shutil.which(cmd)
        if resolved:
            return resolved
    return None


def libreoffice_status(timeout: float = 8.0) -> dict:
    """Estado para a UI: instalado, caminho, versão e URL de download."""
    path = find_soffice()
    version: Optional[str] = None
    if path:
        try:
            proc = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            line = (proc.stdout or proc.stderr or "").strip().splitlines()
            if line:
                version = line[0].strip()[:120]
        except (OSError, subprocess.TimeoutExpired):
            version = None
    return {
        "installed": path is not None,
        "path": path,
        "version": version,
        "download_url": LIBREOFFICE_DOWNLOAD_URL,
        "platform": sys.platform,
    }


def _profile_url() -> str:
    os.makedirs(_PROFILE_DIR, exist_ok=True)
    path = _PROFILE_DIR.replace(os.sep, "/")
    if not path.startswith("/"):
        path = "/" + path
    return "file://" + path


def _run_soffice(cmd: str, docx_path: str, out_dir: str, timeout: int) -> Optional[str]:
    """Roda uma conversão; retorna stderr/stdout de erro ou None se ok."""
    proc = subprocess.run(
        [
            cmd,
            "-env:UserInstallation=%s" % _profile_url(),
            "--headless",
            "--norestore",
            "--convert-to",
            "pdf",
            "--outdir",
            out_dir,
            docx_path,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout or "código %d" % proc.returncode).strip()[:500]
    return None


def convert_docx_to_pdf(docx_path: str, pdf_path: str, timeout: int = 180) -> bool:
    """Converte DOCX em PDF via LibreOffice. Retorna False se indisponível."""
    docx_path = os.path.abspath(docx_path)
    pdf_path = os.path.abspath(pdf_path)
    if not os.path.isfile(docx_path):
        return False

    out_dir = os.path.dirname(pdf_path) or "."
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(docx_path))[0]
    generated = os.path.join(out_dir, stem + ".pdf")

    resolved = find_soffice()
    if not resolved:
        logger.warning("LibreOffice não encontrado — conversão DOCX→PDF indisponível.")
        return False

    try:
        error = _run_soffice(resolved, docx_path, out_dir, timeout)
        if error is not None:
            # Perfil pode ter ficado corrompido (ex.: processo morto no
            # meio de uma conversão anterior) — recria e tenta 1x de novo.
            logger.warning(
                "LibreOffice (%s) falhou (%s); recriando perfil e repetindo.",
                resolved, error,
            )
            shutil.rmtree(_PROFILE_DIR, ignore_errors=True)
            error = _run_soffice(resolved, docx_path, out_dir, timeout)
        if error is not None:
            logger.warning(
                "LibreOffice (%s) falhou ao converter %s: %s",
                resolved, docx_path, error,
            )
            return False
        if not os.path.isfile(generated):
            logger.warning("LibreOffice não gerou %s", generated)
            return False
        if os.path.abspath(generated) != pdf_path:
            if os.path.isfile(pdf_path):
                os.remove(pdf_path)
            os.replace(generated, pdf_path)
        logger.info("PDF gerado via LibreOffice: %s", pdf_path)
        return True
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Conversão DOCX→PDF com %s falhou: %s", resolved, exc)
        return False


def open_libreoffice_download() -> str:
    """Abre a página de download do LibreOffice no navegador. Retorna a URL."""
    import webbrowser

    webbrowser.open(LIBREOFFICE_DOWNLOAD_URL)
    return LIBREOFFICE_DOWNLOAD_URL
