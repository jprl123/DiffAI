"""Preferências persistentes do app (idioma, onboarding, recursos padrão).

Vivem em ``~/.comparedocs/settings.json`` — o mesmo diretório de licença,
trial e histórico. Escrita atômica (temp + rename) e acesso protegido por
lock, no mesmo padrão de ``app/history.py``.

Chaves
------
- ``language``: "pt" | "en" | None. None = ainda não escolhido (dispara o
  seletor de idioma na primeira execução).
- ``onboarding_done``: bool. False = mostrar o tutorial guiado.
- ``compare_setup_done``: bool. False = mostrar o modal de opções de
  comparação na primeira execução (depois do idioma).
- ``default_features``: dict de toggles de SAÍDA que vêm pré-marcados ao
  abrir o app. Todos começam desligados (decisão do usuário 2026-07-14).
  NÃO inclui "aceite de revisões" — esse é passo de correção, sempre ligado.
- ``compare_options``: dict do que comparar (moves, formatação, headers…).
  Defaults True — o motor já compara esses aspectos.
- ``libreoffice_banner_dismissed``: bool. True = ocultar o aviso de
  LibreOffice ausente (até o usuário pedir de novo em Configurações).
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from typing import Any, Dict, Optional

from app.compare_options import COMPARE_OPTION_DEFAULTS, COMPARE_OPTION_KEYS

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS_PATH = os.path.join(
    os.path.expanduser("~"), ".comparedocs", "settings.json"
)

# Recursos de SAÍDA que o usuário pode deixar pré-ligados. Espelham os toggles
# da UI (options em jobs.py). Todos off por padrão.
_DEFAULT_FEATURE_KEYS = (
    "changed_pages_only",
    "export_docx",
    "exec_summary",
)

_DEFAULTS: Dict[str, Any] = {
    "language": None,
    "onboarding_done": False,
    "compare_setup_done": False,
    "default_features": {key: False for key in _DEFAULT_FEATURE_KEYS},
    "compare_options": dict(COMPARE_OPTION_DEFAULTS),
    "libreoffice_banner_dismissed": False,
}

_VALID_LANGUAGES = ("pt", "en")


def _default_settings() -> Dict[str, Any]:
    import copy

    return copy.deepcopy(_DEFAULTS)


class SettingsStore:
    def __init__(self, path: Optional[str] = None) -> None:
        self._path = os.path.abspath(
            path
            or os.environ.get("COMPAREDOCS_SETTINGS_PATH")
            or DEFAULT_SETTINGS_PATH
        )
        self._lock = threading.Lock()

    @property
    def path(self) -> str:
        return self._path

    def _read_raw(self) -> Dict[str, Any]:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            logger.warning("settings.json ilegível (%s); usando padrões.", exc)
        return {}

    def _normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Mescla o cru sobre os padrões, validando os campos conhecidos."""
        merged = _default_settings()

        lang = raw.get("language")
        if lang in _VALID_LANGUAGES:
            merged["language"] = lang

        merged["onboarding_done"] = bool(raw.get("onboarding_done", False))
        merged["compare_setup_done"] = bool(raw.get("compare_setup_done", False))
        merged["libreoffice_banner_dismissed"] = bool(
            raw.get("libreoffice_banner_dismissed", False)
        )

        feats = raw.get("default_features")
        if isinstance(feats, dict):
            for key in _DEFAULT_FEATURE_KEYS:
                if key in feats:
                    merged["default_features"][key] = bool(feats[key])

        cmp_opts = raw.get("compare_options")
        if isinstance(cmp_opts, dict):
            for key in COMPARE_OPTION_KEYS:
                if key in cmp_opts:
                    merged["compare_options"][key] = bool(cmp_opts[key])
        return merged

    def get(self) -> Dict[str, Any]:
        with self._lock:
            return self._normalize(self._read_raw())

    def update(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        """Mescla ``patch`` (validado) e persiste. Retorna o estado final."""
        if not isinstance(patch, dict):
            raise ValueError("patch de settings deve ser um objeto JSON.")
        with self._lock:
            current = self._normalize(self._read_raw())

            if "language" in patch:
                lang = patch["language"]
                if lang not in _VALID_LANGUAGES:
                    raise ValueError(
                        "language inválido: %r (esperado 'pt' ou 'en')." % (lang,)
                    )
                current["language"] = lang

            if "onboarding_done" in patch:
                current["onboarding_done"] = bool(patch["onboarding_done"])

            if "compare_setup_done" in patch:
                current["compare_setup_done"] = bool(patch["compare_setup_done"])

            if "libreoffice_banner_dismissed" in patch:
                current["libreoffice_banner_dismissed"] = bool(
                    patch["libreoffice_banner_dismissed"]
                )

            if "default_features" in patch:
                feats = patch["default_features"]
                if not isinstance(feats, dict):
                    raise ValueError("default_features deve ser um objeto.")
                for key, value in feats.items():
                    if key in _DEFAULT_FEATURE_KEYS:
                        current["default_features"][key] = bool(value)

            if "compare_options" in patch:
                cmp_opts = patch["compare_options"]
                if not isinstance(cmp_opts, dict):
                    raise ValueError("compare_options deve ser um objeto.")
                for key, value in cmp_opts.items():
                    if key in COMPARE_OPTION_KEYS:
                        current["compare_options"][key] = bool(value)

            self._write(current)
            return current

    def _write(self, data: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix=".settings-", suffix=".json", dir=os.path.dirname(self._path)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


_store: Optional[SettingsStore] = None
_store_lock = threading.Lock()


def get_store() -> SettingsStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = SettingsStore()
        return _store
