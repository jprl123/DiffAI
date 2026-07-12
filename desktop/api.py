"""API JavaScript exposta ao frontend no app desktop (pywebview)."""
from __future__ import annotations

from typing import Optional

from app.native_dialogs import pick_folder as pick_folder_native


class DesktopApi:
    """Métodos chamáveis via ``window.pywebview.api`` no frontend."""

    def is_desktop(self) -> bool:
        return True

    def pick_folder(self, initial_dir: str = "") -> str:
        """Abre o seletor nativo de pasta (Finder / Explorer)."""
        initial = initial_dir.strip() or None
        try:
            import webview
            from webview import FileDialog

            windows = webview.windows
            if windows:
                result = windows[0].create_file_dialog(
                    FileDialog.FOLDER,
                    directory=initial,
                )
                if result and len(result) > 0:
                    path = str(result[0]).strip()
                    if path:
                        return path
        except Exception:
            pass

        path = pick_folder_native(initial, prompt="Selecionar pasta")
        return path or ""
