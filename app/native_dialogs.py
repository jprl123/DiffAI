"""Diálogos nativos do sistema (seleção de pasta).

Usado pela API local quando o app roda sem pywebview (navegador em localhost)
ou como fallback no desktop.
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional


def _escape_applescript(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _pick_folder_macos(initial_dir: Optional[str], prompt: str) -> Optional[str]:
    script = 'POSIX path of (choose folder with prompt "%s"' % _escape_applescript(prompt)
    if initial_dir and os.path.isdir(initial_dir):
        script += ' default location (POSIX file "%s")' % _escape_applescript(initial_dir)
    script += ")"
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    path = proc.stdout.strip()
    return path or None


def _pick_folder_windows(initial_dir: Optional[str], prompt: str) -> Optional[str]:
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$dlg = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$dlg.Description = '%s'; "
        "$dlg.ShowNewFolderButton = $true; "
    ) % prompt.replace("'", "''")
    if initial_dir and os.path.isdir(initial_dir):
        ps += "$dlg.SelectedPath = '%s'; " % initial_dir.replace("'", "''")
    ps += (
        "if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) "
        "{ Write-Output $dlg.SelectedPath }"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    path = proc.stdout.strip()
    return path or None


def _pick_folder_linux(initial_dir: Optional[str], prompt: str) -> Optional[str]:
    for cmd, args in (
        ("zenity", ["--file-selection", "--directory", "--title=%s" % prompt]),
        ("kdialog", ["--getexistingdirectory", initial_dir or ".", "--title", prompt]),
    ):
        try:
            proc = subprocess.run(
                [cmd, *args],
                capture_output=True,
                text=True,
                timeout=300,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode != 0:
            return None
        path = proc.stdout.strip()
        if path:
            return path
    return _pick_folder_tk(initial_dir, prompt)


def _pick_folder_tk(initial_dir: Optional[str], prompt: str) -> Optional[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        path = filedialog.askdirectory(
            title=prompt,
            initialdir=initial_dir if initial_dir and os.path.isdir(initial_dir) else None,
            mustexist=True,
            parent=root,
        )
    finally:
        root.destroy()
    return path or None


def pick_folder(
    initial_dir: Optional[str] = None,
    prompt: str = "Selecionar pasta",
) -> Optional[str]:
    """Abre o explorador nativo e devolve o caminho absoluto, ou None se cancelado."""
    initial = os.path.abspath(initial_dir) if initial_dir and os.path.isdir(initial_dir) else None
    if sys.platform == "darwin":
        path = _pick_folder_macos(initial, prompt)
    elif sys.platform == "win32":
        path = _pick_folder_windows(initial, prompt)
    else:
        path = _pick_folder_linux(initial, prompt)

    if not path:
        return None
    path = os.path.abspath(path)
    return path if os.path.isdir(path) else None
