"""Launcher desktop: janela nativa com a interface web local.

Evita problemas do Tk 8.5 do macOS com CustomTkinter. Sobe o servidor FastAPI
em thread e abre uma janela nativa (pywebview) apontando para localhost.
"""
from __future__ import annotations

import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from typing import Optional

from desktop.log_util import LOG_FILE, setup_logging

logger = setup_logging()

HOST = "127.0.0.1"
DEFAULT_PORT = 8377
MAX_PORT_TRIES = 20


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((HOST, port))
            return True
        except OSError:
            return False


def _pick_port() -> int:
    for port in range(DEFAULT_PORT, DEFAULT_PORT + MAX_PORT_TRIES):
        if _port_free(port):
            return port
    raise RuntimeError(
        "Nenhuma porta livre entre %d e %d." % (DEFAULT_PORT, DEFAULT_PORT + MAX_PORT_TRIES - 1)
    )


def _wait_for_server(url: str, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(0.15)
    return False


def _run_uvicorn(port: int, ready: threading.Event, error_box: list) -> None:
    try:
        import uvicorn
        from app.main import app as fastapi_app

        logger.info("Iniciando servidor em http://%s:%d", HOST, port)

        config = uvicorn.Config(
            fastapi_app,
            host=HOST,
            port=port,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)

        def on_started() -> None:
            ready.set()
            logger.info("Servidor pronto.")

        # uvicorn não tem hook simples; marcamos ready após pequeno delay no waiter
        ready.set()
        server.run()
    except Exception as exc:
        error_box.append(exc)
        logger.exception("Falha no servidor: %s", exc)
        ready.set()


def _open_webview(title: str, url: str) -> None:
    import webview

    from desktop.api import DesktopApi

    logger.info("Abrindo janela nativa: %s", url)
    webview.create_window(
        title,
        url,
        width=1200,
        height=820,
        min_size=(900, 600),
        text_select=True,
        js_api=DesktopApi(),
    )
    webview.start(debug=False)
    logger.info("Janela fechada.")


def _open_browser_fallback(url: str) -> None:
    logger.warning("pywebview indisponível — abrindo no navegador: %s", url)
    webbrowser.open(url)
    print("")
    print("Compare Docs rodando em: %s" % url)
    print("Log detalhado: %s" % LOG_FILE)
    print("Pressione Ctrl+C para encerrar.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Encerrado pelo usuário (Ctrl+C).")


def launch() -> None:
    port = _pick_port()
    health_url = "http://%s:%d/api/health" % (HOST, port)
    app_url = "http://%s:%d/" % (HOST, port)

    ready = threading.Event()
    errors: list = []
    thread = threading.Thread(
        target=_run_uvicorn,
        args=(port, ready, errors),
        name="comparedocs-server",
        daemon=True,
    )
    thread.start()

    if not ready.wait(timeout=5.0):
        raise RuntimeError("Servidor não iniciou a tempo. Veja %s" % LOG_FILE)

    if errors:
        raise errors[0]

    if not _wait_for_server(health_url):
        raise RuntimeError(
            "Servidor não respondeu em %s. Veja o log: %s" % (health_url, LOG_FILE)
        )

    logger.info("Interface disponível em %s", app_url)

    try:
        import webview  # noqa: F401

        _open_webview("Compare Docs", app_url)
    except Exception as exc:
        logger.exception("pywebview falhou: %s", exc)
        _open_browser_fallback(app_url)


def main() -> None:
    try:
        launch()
    except Exception as exc:
        logger.exception("Erro fatal: %s", exc)
        print("")
        print("ERRO: %s" % exc)
        print("Log completo: %s" % LOG_FILE)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
