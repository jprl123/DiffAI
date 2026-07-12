"""Carrega o resultado de comparação a partir de uma entrada do histórico."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _load_json_report(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        logger.warning("Relatório JSON ilegível (%s): %s", path, exc)
        return None
    if isinstance(data, dict) and isinstance(data.get("changes"), list):
        return data
    return None


def _recompare(base_path: str, compare_path: str) -> Optional[Dict[str, Any]]:
    try:
        from app.engine.compare import compare_documents
        from app.extract.loader import load_document

        base_doc = load_document(base_path)
        compare_doc = load_document(compare_path)
        result = compare_documents(base_doc, compare_doc)
        return result.to_dict()
    except Exception as exc:
        logger.warning(
            "Falha ao re-comparar '%s' vs '%s': %s",
            base_path,
            compare_path,
            exc,
        )
        return None


def result_dict_for_entry(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Devolve o mesmo formato de ``ComparisonResult.to_dict()`` para a UI."""
    outputs = entry.get("outputs") or {}
    json_path = outputs.get("json")
    if isinstance(json_path, str) and os.path.isfile(json_path):
        data = _load_json_report(json_path)
        if data is not None:
            return data

    base_path = str(entry.get("base_path") or "").strip()
    compare_path = str(entry.get("compare_path") or "").strip()
    if base_path and compare_path and os.path.isfile(base_path) and os.path.isfile(compare_path):
        return _recompare(base_path, compare_path)
    return None


def result_object_for_entry(entry: Dict[str, Any]) -> Optional[Any]:
    """Objeto ComparisonResult — para análise IA e extensões."""
    data = result_dict_for_entry(entry)
    if data is None:
        return None
    try:
        from app.models import ComparisonResult

        # to_dict é lossy para reconstruir dataclass; re-comparar é mais seguro.
        base_path = str(entry.get("base_path") or "").strip()
        compare_path = str(entry.get("compare_path") or "").strip()
        if base_path and compare_path and os.path.isfile(base_path) and os.path.isfile(compare_path):
            from app.engine.compare import compare_documents
            from app.extract.loader import load_document

            return compare_documents(load_document(base_path), load_document(compare_path))
    except Exception as exc:
        logger.warning("Falha ao materializar resultado do histórico: %s", exc)
    return None


def find_entry(entries: list, entry_id: str) -> Optional[Dict[str, Any]]:
    for entry in entries:
        if entry.get("id") == entry_id:
            return entry
    return None
