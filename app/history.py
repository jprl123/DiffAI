"""Histórico persistente de comparações.

Cada par processado vira uma entrada em ``~/.comparedocs/history.json``
(sobrevive ao fechamento do app — requisito da aba Histórico). Escrita
atômica (arquivo temporário + rename) e acesso protegido por lock.

O histórico também serve de fonte de verdade para ``POST /api/open`` após
reiniciar o app: um caminho listado nos outputs de uma entrada pode ser
aberto mesmo que o whitelist em memória da sessão atual não o conheça.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_PATH = os.path.join(
    os.path.expanduser("~"), ".comparedocs", "history.json"
)
MAX_ENTRIES = 500


class HistoryStore:
    def __init__(self, path: Optional[str] = None) -> None:
        self._path = os.path.abspath(
            path
            or os.environ.get("COMPAREDOCS_HISTORY_PATH")
            or DEFAULT_HISTORY_PATH
        )
        self._lock = threading.Lock()

    @property
    def path(self) -> str:
        return self._path

    # -- IO interno -----------------------------------------------------------

    def _load(self) -> List[Dict[str, Any]]:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                return data
            logger.warning("Histórico corrompido (não é lista); recomeçando vazio.")
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            logger.warning("Não foi possível ler o histórico (%s); recomeçando.", exc)
        return []

    def _save(self, entries: List[Dict[str, Any]]) -> None:
        directory = os.path.dirname(self._path)
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(entries, fh, ensure_ascii=False, indent=1)
            os.replace(tmp_path, self._path)
        except OSError:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # -- API ------------------------------------------------------------------

    def add_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Adiciona uma entrada (mais recente primeiro) e retorna com id."""
        record = dict(entry)
        record.setdefault("id", uuid.uuid4().hex[:12])
        with self._lock:
            entries = self._load()
            entries.insert(0, record)
            del entries[MAX_ENTRIES:]
            try:
                self._save(entries)
            except OSError as exc:
                logger.warning("Falha ao gravar histórico: %s", exc)
        return record

    def list_entries(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self._lock:
            entries = self._load()
        return entries[: max(0, int(limit))]

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            entries = self._load()
        for entry in entries:
            if entry.get("id") == entry_id:
                return dict(entry)
        return None

    def remove_entry(self, entry_id: str) -> bool:
        with self._lock:
            entries = self._load()
            remaining = [e for e in entries if e.get("id") != entry_id]
            if len(remaining) == len(entries):
                return False
            self._save(remaining)
        return True

    def clear(self) -> int:
        with self._lock:
            entries = self._load()
            self._save([])
        return len(entries)

    def path_known(self, path: str) -> bool:
        """True se ``path`` é um output registrado (ou diretório pai direto)."""
        if not path:
            return False
        ap = os.path.abspath(path)
        with self._lock:
            entries = self._load()
        for entry in entries:
            outputs = entry.get("outputs") or {}
            for out in outputs.values():
                if not isinstance(out, str):
                    continue
                out_abs = os.path.abspath(out)
                if out_abs == ap or os.path.dirname(out_abs) == ap:
                    return True
        return False


_store: Optional[HistoryStore] = None
_store_lock = threading.Lock()


def get_store() -> HistoryStore:
    """Singleton do processo (caminho configurável via COMPAREDOCS_HISTORY_PATH)."""
    global _store
    with _store_lock:
        if _store is None:
            _store = HistoryStore()
        return _store
