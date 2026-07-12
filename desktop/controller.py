"""Controlador desktop — reutiliza JobManager sem HTTP."""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.batch import pair_files
from app.jobs import JobManager, is_path_allowed, register_output_path


class ComparisonController:
    """Orquestra comparações locais com o mesmo pipeline da versão web."""

    def __init__(self) -> None:
        self.manager = JobManager()

    def build_options(
        self,
        changed_pages_only: bool,
        export_docx: bool,
        report_html: bool,
        report_xlsx: bool,
        report_json: bool,
        output_dir: Optional[str],
    ) -> Dict[str, Any]:
        reports: List[str] = []
        if report_html:
            reports.append("html")
        if report_xlsx:
            reports.append("xlsx")
        if report_json:
            reports.append("json")
        return {
            "changed_pages_only": changed_pages_only,
            "export_docx": export_docx,
            "reports": reports,
            "output_dir": output_dir or None,
        }

    def start_single(
        self,
        base_path: str,
        compare_path: str,
        options: Dict[str, Any],
        swap: bool = False,
    ) -> str:
        if swap:
            base_path, compare_path = compare_path, base_path
        return self.manager.create_job([(base_path, compare_path)], options)

    def start_batch(
        self,
        base_dir: str,
        compare_dir: str,
        options: Dict[str, Any],
        swap: bool = False,
    ) -> Tuple[str, List[Tuple[str, str]]]:
        if swap:
            base_dir, compare_dir = compare_dir, base_dir
        pairs, unmatched_base, unmatched_compare = pair_files(base_dir, compare_dir)
        if not pairs:
            msg = "Nenhum par correspondente encontrado entre as pastas."
            if unmatched_base:
                msg += " Sem par na base: %s." % ", ".join(unmatched_base[:5])
            if unmatched_compare:
                msg += " Sem par na revisada: %s." % ", ".join(unmatched_compare[:5])
            raise ValueError(msg)
        job_id = self.manager.create_job(pairs, options)
        return job_id, pairs

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.manager.get_job(job_id)

    def get_result(self, job_id: str, index: int) -> Optional[Dict[str, Any]]:
        return self.manager.get_result(job_id, index)

    def open_path(self, path: str) -> None:
        if not path or not os.path.exists(path):
            raise FileNotFoundError("Arquivo não encontrado: '%s'" % path)
        if not is_path_allowed(path):
            parent = os.path.dirname(os.path.abspath(path))
            if not is_path_allowed(parent):
                register_output_path(path)
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([opener, path])

    def open_folder(self, path: str) -> None:
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        if not folder or not os.path.isdir(folder):
            raise FileNotFoundError("Pasta não encontrada.")
        self.open_path(folder)
