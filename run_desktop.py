#!/usr/bin/env python3
"""Executor Python do diffAI Desktop.

Abre uma janela nativa com a interface web local (recomendado no macOS).
Logs em logs/desktop.log

Uso:
    .venv/bin/python run_desktop.py
"""
from __future__ import annotations

import os
import subprocess
import sys


def _project_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _venv_python(root: str) -> str:
    if sys.platform == "win32":
        return os.path.join(root, ".venv", "Scripts", "python.exe")
    return os.path.join(root, ".venv", "bin", "python")


def _in_project_venv(root: str) -> bool:
    try:
        return os.path.samefile(sys.executable, _venv_python(root))
    except (OSError, ValueError):
        exe = os.path.realpath(sys.executable)
        return exe.startswith(os.path.realpath(os.path.join(root, ".venv")))


def _reexec_with_venv_python(root: str) -> None:
    venv_py = _venv_python(root)
    if not os.path.isfile(venv_py):
        print(
            "Erro: ambiente virtual não encontrado.\n"
            "Crie com: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1)
    os.chdir(root)
    os.execv(venv_py, [venv_py, os.path.abspath(__file__)] + sys.argv[1:])


def _ensure_dependencies(python_exe: str, root: str) -> None:
    missing = []
    for mod in ("customtkinter", "webview"):
        try:
            subprocess.run(
                [python_exe, "-c", "import %s" % mod],
                cwd=root,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (subprocess.CalledProcessError, OSError):
            missing.append(mod)
    if missing:
        print("Instalando dependências (%s)…" % ", ".join(missing), file=sys.stderr)
        subprocess.run(
            [python_exe, "-m", "pip", "install", "-r", os.path.join(root, "requirements.txt")],
            cwd=root,
            check=True,
        )


def main() -> None:
    root = _project_root()
    os.chdir(root)
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

    if root not in sys.path:
        sys.path.insert(0, root)

    if not _in_project_venv(root):
        _reexec_with_venv_python(root)
        return

    _ensure_dependencies(sys.executable, root)

    from desktop.__main__ import main as run_desktop

    run_desktop()


if __name__ == "__main__":
    main()
