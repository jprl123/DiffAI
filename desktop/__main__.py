"""Ponto de entrada do Compare Docs Desktop."""
from __future__ import annotations

import os
import sys
import traceback

from desktop.log_util import LOG_FILE, setup_logging

logger = setup_logging()


def _show_fatal_error(message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Compare Docs — erro ao iniciar", message)
        root.destroy()
    except Exception:
        pass
    print(message, file=sys.stderr)


def main() -> None:
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
    logger.info("Iniciando Compare Docs Desktop…")

    # Modo 1 (padrão): janela nativa com interface web — funciona no macOS.
    if "--tk" not in sys.argv:
        try:
            from desktop.launcher import launch

            launch()
            return
        except Exception as exc:
            logger.exception("Launcher webview falhou: %s", exc)
            _show_fatal_error(
                "Falha ao abrir a janela nativa.\n\n%s\n\nLog: %s"
                % (exc, LOG_FILE)
            )
            raise SystemExit(1) from exc

    # Modo 2 (legado): CustomTkinter — só se passar --tk explicitamente.
    try:
        from desktop.app import main as run_tk_app

        logger.info("Modo legado CustomTkinter (--tk)")
        run_tk_app()
    except Exception as exc:
        detail = traceback.format_exc()
        logger.exception("CustomTkinter falhou: %s", exc)
        _show_fatal_error(
            "Não foi possível abrir o aplicativo (Tk):\n\n%s\n\n%s\n\nLog: %s"
            % (exc, detail, LOG_FILE)
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
