"""Gerenciamento de jobs de comparação (fila em thread, progresso, resiliência).

Um job processa uma lista de pares (base, comparação). Cada par é carregado,
comparado e tem suas saídas geradas conforme as opções. Falha em um par NÃO
derruba o lote: o erro é registrado no item e o processamento continua.

O estado dos jobs vive em memória, protegido por ``threading.Lock``. Os
caminhos de arquivos gerados entram em um whitelist global consultado pelo
endpoint ``POST /api/open`` (só abrimos o que este processo gerou).
"""
from __future__ import annotations

import copy
import dataclasses
import datetime
import logging
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from app.models import ComparisonResult, Stats

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Whitelist global de caminhos gerados (para POST /api/open)
# ---------------------------------------------------------------------------

_whitelist_lock = threading.Lock()
_output_whitelist: Set[str] = set()


def register_output_path(path: str) -> None:
    """Registra um caminho gerado por um job (permitido em /api/open)."""
    with _whitelist_lock:
        _output_whitelist.add(os.path.abspath(path))


def is_path_allowed(path: str) -> bool:
    """True se o caminho foi gerado por um job desta sessão, ou se é o
    diretório pai direto de um caminho gerado."""
    if not path:
        return False
    ap = os.path.abspath(path)
    with _whitelist_lock:
        if ap in _output_whitelist:
            return True
        for wp in _output_whitelist:
            if os.path.dirname(wp) == ap:
                return True
    return False


# ---------------------------------------------------------------------------
# Nomes de saída — usa app.output.naming quando disponível; fallback interno
# segue o mesmo contrato documentado em docs/ARCHITECTURE.md.
# ---------------------------------------------------------------------------

_SANITIZE_RE = re.compile(r"[\\/:*?\"<>|\x00-\x1f]+")


def _sanitize_stem(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    stem = _SANITIZE_RE.sub("_", stem).strip()
    return stem or "documento"


def _fallback_redline_pdf_name(base_path: str, compare_path: str) -> str:
    return "[Redline] %s vs %s.pdf" % (_sanitize_stem(base_path), _sanitize_stem(compare_path))


def _fallback_changed_pages_pdf_name(base_path: str, compare_path: str) -> str:
    # Alinha com app.output.naming (sufixo localizado quando o módulo existe).
    return "[Redline-Changed Pages] %s.pdf" % (
        "%s vs %s" % (_sanitize_stem(base_path), _sanitize_stem(compare_path))
    )


def _fallback_redline_docx_name(base_path: str, compare_path: str) -> str:
    return "[Redline] %s vs %s.docx" % (_sanitize_stem(base_path), _sanitize_stem(compare_path))


def _fallback_redline_xlsx_name(base_path: str, compare_path: str) -> str:
    return "[Redline] %s vs %s.xlsx" % (_sanitize_stem(base_path), _sanitize_stem(compare_path))


def _fallback_exec_summary_name(base_path: str, compare_path: str) -> str:
    return "[Resumo] %s vs %s.pdf" % (_sanitize_stem(base_path), _sanitize_stem(compare_path))


def _fallback_report_name(base_path: str, compare_path: str, ext: str) -> str:
    return "[Report] %s vs %s.%s" % (
        _sanitize_stem(base_path), _sanitize_stem(compare_path), ext.lstrip(".")
    )


_PIPELINE_IMPORTS: Dict[str, Tuple[str, str]] = {
    "load_document": ("app.extract.loader", "load_document"),
    "compare_documents": ("app.engine.compare", "compare_documents"),
    "convert_pdf_to_docx": ("app.extract.pdf_to_docx", "convert_pdf_to_docx"),
    "has_tracked_revisions": ("app.extract.docx_revisions", "has_tracked_revisions"),
    "accept_all_revisions": ("app.extract.docx_revisions", "accept_all_revisions"),
    "write_redline_pdf": ("app.output.redline_pdf", "write_redline_pdf"),
    "write_redline_docx": ("app.output.redline_docx", "write_redline_docx"),
    "write_redline_docx_inplace": ("app.output.redline_docx_inplace", "write_redline_docx_inplace"),
    "convert_docx_to_pdf": ("app.output.docx_to_pdf", "convert_docx_to_pdf"),
    "write_redline_xlsx": ("app.output.redline_xlsx", "write_redline_xlsx"),
    "write_exec_summary_pdf": ("app.output.exec_summary", "write_exec_summary_pdf"),
    "exec_summary_name": ("app.output.naming", "exec_summary_name"),
    "write_html_report": ("app.output.report", "write_html_report"),
    "write_xlsx_report": ("app.output.report", "write_xlsx_report"),
    "write_json_report": ("app.output.report", "write_json_report"),
    "redline_pdf_name": ("app.output.naming", "redline_pdf_name"),
    "changed_pages_pdf_name": ("app.output.naming", "changed_pages_pdf_name"),
    "redline_docx_name": ("app.output.naming", "redline_docx_name"),
    "redline_xlsx_name": ("app.output.naming", "redline_xlsx_name"),
    "report_name": ("app.output.naming", "report_name"),
}

_NAMING_FALLBACKS: Dict[str, Callable[..., str]] = {
    "redline_pdf_name": _fallback_redline_pdf_name,
    "changed_pages_pdf_name": _fallback_changed_pages_pdf_name,
    "redline_docx_name": _fallback_redline_docx_name,
    "redline_xlsx_name": _fallback_redline_xlsx_name,
    "report_name": _fallback_report_name,
    "exec_summary_name": _fallback_exec_summary_name,
}

VALID_REPORTS = ("html", "xlsx", "json")
_XLSX_EXTENSIONS = (".xlsx", ".xlsm")
_DOCX_EXTENSIONS = (".docx",)
_PDF_EXTENSIONS = (".pdf",)


def _is_xlsx_pair(base_path: str, compare_path: str) -> bool:
    base_ext = os.path.splitext(base_path)[1].lower()
    compare_ext = os.path.splitext(compare_path)[1].lower()
    return base_ext in _XLSX_EXTENSIONS and compare_ext in _XLSX_EXTENSIONS


def _comparison_result_from_xlsx_diff(
    base_path: str,
    compare_path: str,
    xlsx_diff: Any,
    duration: float,
) -> ComparisonResult:
    """Monta um ComparisonResult leve a partir do diff estrutural XLSX."""
    xs = xlsx_diff.stats
    table_changes = (
        int(xs.row_add)
        + int(xs.row_del)
        + int(xs.col_add)
        + int(xs.col_del)
        + int(xs.modified_cells)
    )
    insertions = int(xs.row_add) + int(xs.col_add) + int(xs.value_changes)
    deletions = int(xs.row_del) + int(xs.col_del) + int(xs.emptied_cells)
    modifications = int(xs.modified_cells)
    total = insertions + deletions + modifications
    stats = Stats(
        total_changes=total,
        insertions=insertions,
        deletions=deletions,
        modifications=modifications,
        table_changes=table_changes,
        content_changes=0,
        by_category={"table": table_changes},
    )
    return ComparisonResult(
        base_path=base_path,
        compare_path=compare_path,
        base_title=os.path.basename(base_path),
        compare_title=os.path.basename(compare_path),
        stats=stats,
        compared_at=datetime.datetime.now().isoformat(),
        duration_seconds=duration,
    )


def _is_docx_pair(base_path: str, compare_path: str) -> bool:
    base_ext = os.path.splitext(base_path)[1].lower()
    compare_ext = os.path.splitext(compare_path)[1].lower()
    return base_ext in _DOCX_EXTENSIONS and compare_ext in _DOCX_EXTENSIONS


def _is_pdf_pair(base_path: str, compare_path: str) -> bool:
    base_ext = os.path.splitext(base_path)[1].lower()
    compare_ext = os.path.splitext(compare_path)[1].lower()
    return base_ext in _PDF_EXTENSIONS and compare_ext in _PDF_EXTENSIONS


class JobManager:
    """Executa lotes de comparação em ``threading.Thread`` daemon.

    ``pipeline`` (opcional) permite injetar funções substitutas — usado em
    testes quando os módulos de extração/motor/saída ainda não existem.
    """

    def __init__(
        self,
        pipeline: Optional[Dict[str, Callable[..., Any]]] = None,
        history_store: Optional[Any] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._results: Dict[str, List[Optional[ComparisonResult]]] = {}
        self._pipeline_overrides: Dict[str, Callable[..., Any]] = dict(pipeline or {})
        if history_store is None:
            from app.history import get_store
            history_store = get_store()
        self._history = history_store

    # -- resolução do pipeline ------------------------------------------------

    def _resolve(self, name: str) -> Callable[..., Any]:
        override = self._pipeline_overrides.get(name)
        if override is not None:
            return override
        module_name, attr = _PIPELINE_IMPORTS[name]
        try:
            module = __import__(module_name, fromlist=[attr])
            return getattr(module, attr)
        except Exception as exc:
            fallback = _NAMING_FALLBACKS.get(name)
            if fallback is not None:
                logger.warning(
                    "Módulo %s indisponível (%s); usando nomes de saída padrão.",
                    module_name, exc,
                )
                return fallback
            raise ValueError(
                "Módulo de comparação indisponível: não foi possível importar "
                "'%s.%s' (%s). Verifique a instalação do aplicativo." % (module_name, attr, exc)
            )

    # -- API pública ----------------------------------------------------------

    def create_job(self, pairs: List[Tuple[str, str]], options: Dict[str, Any]) -> str:
        job_id = uuid.uuid4().hex[:8]
        options = dict(options or {})
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "running",
                "progress": {"done": 0, "total": len(pairs), "current": ""},
                "items": [],
                "summary": None,
            }
            self._results[job_id] = []
        thread = threading.Thread(
            target=self._run_job,
            args=(job_id, list(pairs), options),
            name="comparedocs-job-%s" % job_id,
            daemon=True,
        )
        thread.start()
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return copy.deepcopy(job)

    def get_result(self, job_id: str, index: int) -> Optional[Dict[str, Any]]:
        try:
            with self._lock:
                result = self._results[job_id][index]
        except (KeyError, IndexError, TypeError):
            return None
        if result is None:
            return None
        return result.to_dict()

    def get_result_object(self, job_id: str, index: int) -> Optional[ComparisonResult]:
        """Retorna o objeto ComparisonResult (para análise IA e extensões)."""
        try:
            with self._lock:
                result = self._results[job_id][index]
        except (KeyError, IndexError, TypeError):
            return None
        return result

    # -- execução -------------------------------------------------------------

    def _run_job(self, job_id: str, pairs: List[Tuple[str, str]], options: Dict[str, Any]) -> None:
        started = time.time()
        ok = 0
        failed = 0
        try:
            output_dir = self._prepare_output_dir(job_id, options)
            for index, (base_path, compare_path) in enumerate(pairs):
                current_name = os.path.basename(base_path)
                self._update_progress(job_id, current=current_name)
                item, result = self._process_pair(base_path, compare_path, options, output_dir)
                if item.get("status") == "ok":
                    ok += 1
                else:
                    failed += 1
                with self._lock:
                    self._jobs[job_id]["items"].append(item)
                    self._results[job_id].append(result)
                    self._jobs[job_id]["progress"]["done"] = index + 1
                self._record_history(job_id, index, item, result)
            summary = {"ok": ok, "failed": failed, "seconds": round(time.time() - started, 2)}
            with self._lock:
                self._jobs[job_id]["summary"] = summary
                self._jobs[job_id]["status"] = "done"
                self._jobs[job_id]["progress"]["current"] = ""
            logger.info("Job %s concluído: %s", job_id, summary)
        except Exception as exc:
            logger.exception("Job %s abortado por erro inesperado", job_id)
            with self._lock:
                job = self._jobs.get(job_id)
                if job is not None:
                    job["status"] = "error"
                    job["error"] = str(exc)
                    job["summary"] = {
                        "ok": ok,
                        "failed": failed,
                        "seconds": round(time.time() - started, 2),
                    }

    def _record_history(
        self,
        job_id: str,
        index: int,
        item: Dict[str, Any],
        result: Optional[ComparisonResult],
    ) -> None:
        """Persiste o par processado no histórico (falha aqui nunca derruba o job)."""
        try:
            base_path, compare_path = item.get("pair", ["", ""])
            self._history.add_entry({
                "at": datetime.datetime.now().isoformat(timespec="seconds"),
                "job_id": job_id,
                "index": index,
                "base_name": os.path.basename(base_path or ""),
                "compare_name": os.path.basename(compare_path or ""),
                "base_path": base_path,
                "compare_path": compare_path,
                "status": item.get("status"),
                "error": item.get("error"),
                "warnings": list(item.get("warnings") or []),
                "outputs": dict(item.get("outputs") or {}),
                "stats": item.get("stats"),
                "duration_seconds": getattr(result, "duration_seconds", None),
            })
        except Exception:
            logger.exception("Falha ao registrar entrada no histórico")

    def _prepare_output_dir(self, job_id: str, options: Dict[str, Any]) -> str:
        output_dir = options.get("output_dir")
        if not output_dir:
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            # App empacotado (PyInstaller): nunca gravar dentro do bundle —
            # saída vai para a pasta do usuário.
            if getattr(sys, "frozen", False):
                root = os.path.join(
                    os.path.expanduser("~"), "Documents", "diffAI"
                )
            else:
                root = os.path.join(PROJECT_ROOT, "output")
            output_dir = os.path.join(root, "%s-%s" % (stamp, job_id))
        output_dir = os.path.abspath(str(output_dir))
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as exc:
            raise ValueError(
                "Não foi possível criar o diretório de saída '%s': %s" % (output_dir, exc)
            )
        return output_dir

    def _update_progress(self, job_id: str, current: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job["progress"]["current"] = current

    def _process_pair(
        self,
        base_path: str,
        compare_path: str,
        options: Dict[str, Any],
        output_dir: str,
    ) -> Tuple[Dict[str, Any], Optional[ComparisonResult]]:
        item: Dict[str, Any] = {
            "pair": [base_path, compare_path],
            "status": "ok",
            "error": None,
            "warnings": [],
            "outputs": {},
            "stats": None,
        }
        pair_started = time.time()
        try:
            # XLSX: motor próprio (célula a célula). Evita o compare canônico
            # de tabelas — em Cap Tables com dimensão fantasma isso travava.
            if _is_xlsx_pair(base_path, compare_path):
                return self._process_xlsx_pair(
                    base_path, compare_path, options, output_dir, item, pair_started,
                )

            load_document = self._resolve("load_document")
            compare_documents = self._resolve("compare_documents")

            # PDF x PDF: converte ambos para DOCX e segue o MESMO pipeline dos
            # pares Word (redline in-place + PDF fiel). Se a conversão falhar
            # (PDF escaneado, protegido…), cai no gerador padronizado antigo.
            load_base, load_compare, pdf_docx_dir = base_path, compare_path, None
            if _is_pdf_pair(base_path, compare_path):
                load_base, load_compare, pdf_docx_dir = self._convert_pdf_pair_to_docx(
                    base_path, compare_path, item["warnings"]
                )
            # DOCX com track changes PENDENTES: aceita tudo em cópia temporária
            # antes de extrair/comparar (inserção pendente é invisível ao
            # extrator e as marcas antigas poluiriam o redline in-place).
            load_base, load_compare, revisions_dir = self._accept_pending_revisions(
                load_base, load_compare, item["warnings"]
            )
            try:
                base_doc = load_document(load_base)
                compare_doc = load_document(load_compare)
                result = compare_documents(base_doc, compare_doc)
                if load_base != base_path or load_compare != compare_path:
                    # Entradas passaram por cópia/conversão; caminhos exibidos
                    # são sempre os originais do usuário.
                    result.base_path = base_path
                    result.compare_path = compare_path
                result.compared_at = datetime.datetime.now().isoformat()
                result.duration_seconds = round(time.time() - pair_started, 3)

                # O redline in-place parte do DOCX revisado EFETIVO (convertido
                # de PDF e/ou com revisões aceitas), quando houver.
                docx_compare_path = (
                    load_compare
                    if load_compare != compare_path
                    and load_compare.lower().endswith(".docx")
                    else None
                )
                outputs = self._generate_outputs(
                    result, base_path, compare_path, options, output_dir,
                    warnings=item["warnings"],
                    docx_compare_path=docx_compare_path,
                )
            finally:
                if pdf_docx_dir is not None:
                    shutil.rmtree(pdf_docx_dir, ignore_errors=True)
                if revisions_dir is not None:
                    shutil.rmtree(revisions_dir, ignore_errors=True)
            item["outputs"] = outputs
            item["stats"] = dataclasses.asdict(result.stats)
            return item, result
        except Exception as exc:
            logger.exception(
                "Falha ao comparar '%s' x '%s'",
                os.path.basename(base_path), os.path.basename(compare_path),
            )
            item["status"] = "error"
            item["error"] = str(exc)
            return item, None

    def _convert_pdf_pair_to_docx(
        self,
        base_path: str,
        compare_path: str,
        warnings: List[str],
    ) -> Tuple[str, str, Optional[str]]:
        """Converte um par PDF em DOCX temporários com os stems originais.

        Retorna ``(base_docx, compare_docx, temp_dir)`` em sucesso. Em falha,
        registra warning e retorna os caminhos originais com ``temp_dir=None``
        — o par segue pelo gerador de PDF padronizado (comportamento antigo).
        """
        temp_dir = tempfile.mkdtemp(prefix="comparedocs-pdf2docx-")
        try:
            convert_pdf_to_docx = self._resolve("convert_pdf_to_docx")
            # Subpastas separadas: base e revisado costumam ter o mesmo nome.
            base_docx = os.path.join(
                temp_dir, "base", _sanitize_stem(base_path) + ".docx"
            )
            compare_docx = os.path.join(
                temp_dir, "compare", _sanitize_stem(compare_path) + ".docx"
            )
            convert_pdf_to_docx(base_path, base_docx)
            convert_pdf_to_docx(compare_path, compare_docx)
            return base_docx, compare_docx, temp_dir
        except Exception as exc:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.warning(
                "Conversão PDF→DOCX indisponível para '%s' x '%s' (%s); "
                "usando gerador de PDF padronizado.",
                os.path.basename(base_path), os.path.basename(compare_path), exc,
            )
            warnings.append(
                "Não foi possível usar o pipeline fiel para este par de PDFs "
                "(%s). O redline foi gerado com layout padronizado." % exc
            )
            return base_path, compare_path, None

    def _accept_pending_revisions(
        self,
        base_path: str,
        compare_path: str,
        warnings: List[str],
    ) -> Tuple[str, str, Optional[str]]:
        """Aceita track changes pendentes dos DOCX de entrada, em cópia.

        Retorna ``(load_base, load_compare, temp_dir)``. Arquivos sem revisões
        (ou não-DOCX) passam intocados; falha na detecção/aceite mantém o
        arquivo original e registra warning — nunca derruba o par.
        """
        temp_dir: Optional[str] = None
        resolved: List[str] = []
        for side, path in (("base", base_path), ("compare", compare_path)):
            resolved.append(path)
            if not path.lower().endswith(".docx") or not os.path.isfile(path):
                continue
            try:
                has_tracked_revisions = self._resolve("has_tracked_revisions")
                if not has_tracked_revisions(path):
                    continue
                accept_all_revisions = self._resolve("accept_all_revisions")
                if temp_dir is None:
                    temp_dir = tempfile.mkdtemp(prefix="comparedocs-revisions-")
                dst = os.path.join(temp_dir, side, os.path.basename(path))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(path, dst)
                accept_all_revisions(dst)
                resolved[-1] = dst
                warnings.append(
                    "O documento %s ('%s') tinha marcas de revisão pendentes — "
                    "todas foram aceitas automaticamente antes da comparação "
                    "(o arquivo original não foi alterado)."
                    % ("base" if side == "base" else "revisado", os.path.basename(path))
                )
                logger.info(
                    "Revisões pendentes aceitas (cópia) em '%s'", os.path.basename(path)
                )
            except Exception as exc:
                logger.warning(
                    "Falha ao aceitar revisões de '%s' (%s); usando o arquivo "
                    "original.", os.path.basename(path), exc,
                )
                warnings.append(
                    "Não foi possível aceitar as marcas de revisão de '%s' (%s) — "
                    "a comparação usou o arquivo como está."
                    % (os.path.basename(path), exc)
                )
                resolved[-1] = path
        return resolved[0], resolved[1], temp_dir

    def _process_xlsx_pair(
        self,
        base_path: str,
        compare_path: str,
        options: Dict[str, Any],
        output_dir: str,
        item: Dict[str, Any],
        pair_started: float,
    ) -> Tuple[Dict[str, Any], Optional[ComparisonResult]]:
        write_redline_xlsx = self._resolve("write_redline_xlsx")
        redline_xlsx_name = self._resolve("redline_xlsx_name")
        xlsx_path = os.path.join(
            output_dir, redline_xlsx_name(base_path, compare_path)
        )
        xlsx_diff = write_redline_xlsx(base_path, compare_path, xlsx_path)
        outputs: Dict[str, str] = {
            "redline_xlsx": xlsx_path,
            "xlsx": xlsx_path,
        }
        register_output_path(xlsx_path)

        if bool(options.get("exec_summary")):
            item["warnings"].append(
                "Resumo executivo não é gerado para planilhas Excel."
            )

        result = _comparison_result_from_xlsx_diff(
            base_path, compare_path, xlsx_diff,
            duration=round(time.time() - pair_started, 3),
        )

        report = options.get("report")
        if report and report != "xlsx":
            # Relatório analítico (html/json) a partir do resultado leve.
            writer = self._resolve("write_%s_report" % report)
            report_name = self._resolve("report_name")
            report_path = os.path.join(
                output_dir, report_name(base_path, compare_path, report)
            )
            writer(result, report_path)
            outputs["report"] = report_path
            register_output_path(report_path)

        item["outputs"] = outputs
        item["stats"] = dataclasses.asdict(result.stats)
        return item, result

    def _generate_outputs(
        self,
        result: ComparisonResult,
        base_path: str,
        compare_path: str,
        options: Dict[str, Any],
        output_dir: str,
        warnings: Optional[List[str]] = None,
        docx_compare_path: Optional[str] = None,
    ) -> Dict[str, str]:
        """Gera as saídas do par. ``docx_compare_path`` aponta para o DOCX
        revisado quando os arquivos enviados não são .docx (par PDF convertido)
        — nesse caso o par usa o pipeline fiel dos documentos Word."""
        outputs: Dict[str, str] = {}
        warnings = warnings if warnings is not None else []
        is_xlsx = _is_xlsx_pair(base_path, compare_path)

        if is_xlsx:
            write_redline_xlsx = self._resolve("write_redline_xlsx")
            redline_xlsx_name = self._resolve("redline_xlsx_name")
            xlsx_path = os.path.join(
                output_dir, redline_xlsx_name(base_path, compare_path)
            )
            write_redline_xlsx(base_path, compare_path, xlsx_path)
            outputs["redline_xlsx"] = xlsx_path
            outputs["xlsx"] = xlsx_path
            register_output_path(xlsx_path)
        elif _is_docx_pair(base_path, compare_path) or docx_compare_path is not None:
            source_docx = docx_compare_path if docx_compare_path is not None else compare_path
            write_redline_docx_inplace = self._resolve("write_redline_docx_inplace")
            convert_docx_to_pdf = self._resolve("convert_docx_to_pdf")
            redline_docx_name = self._resolve("redline_docx_name")
            redline_pdf_name = self._resolve("redline_pdf_name")

            docx_path = os.path.join(
                output_dir, redline_docx_name(base_path, compare_path)
            )
            write_redline_docx_inplace(result, source_docx, docx_path)
            outputs["docx"] = docx_path
            register_output_path(docx_path)

            pdf_path = os.path.join(output_dir, redline_pdf_name(base_path, compare_path))
            if not convert_docx_to_pdf(docx_path, pdf_path):
                logger.warning(
                    "Conversão via LibreOffice falhou — PDF redline gerado com "
                    "layout padronizado, SEM a formatação original do DOCX."
                )
                warnings.append(
                    "PDF gerado com layout padronizado (a conversão fiel via "
                    "LibreOffice falhou ou o LibreOffice não está instalado). "
                    "O DOCX redline preserva a formatação original."
                )
                write_redline_pdf = self._resolve("write_redline_pdf")
                write_redline_pdf(result, pdf_path, changed_pages_only=False)
            outputs["pdf"] = pdf_path
            register_output_path(pdf_path)

            if bool(options.get("changed_pages_only")):
                changed_pages_pdf_name = self._resolve("changed_pages_pdf_name")
                cp_path = os.path.join(
                    output_dir, changed_pages_pdf_name(base_path, compare_path)
                )
                write_redline_pdf = self._resolve("write_redline_pdf")
                write_redline_pdf(result, cp_path, changed_pages_only=True)
                outputs["changed_pages_pdf"] = cp_path
                register_output_path(cp_path)
        else:
            write_redline_pdf = self._resolve("write_redline_pdf")
            redline_pdf_name = self._resolve("redline_pdf_name")

            pdf_path = os.path.join(output_dir, redline_pdf_name(base_path, compare_path))
            write_redline_pdf(result, pdf_path, changed_pages_only=False)
            outputs["pdf"] = pdf_path
            register_output_path(pdf_path)

            if bool(options.get("changed_pages_only")):
                changed_pages_pdf_name = self._resolve("changed_pages_pdf_name")
                cp_path = os.path.join(
                    output_dir, changed_pages_pdf_name(base_path, compare_path)
                )
                write_redline_pdf(result, cp_path, changed_pages_only=True)
                outputs["changed_pages_pdf"] = cp_path
                register_output_path(cp_path)

            if bool(options.get("export_docx")):
                # DOCX fiel já foi gerado acima para pares .docx
                if not _is_docx_pair(base_path, compare_path):
                    write_redline_docx = self._resolve("write_redline_docx")
                    redline_docx_name = self._resolve("redline_docx_name")
                    docx_path = os.path.join(
                        output_dir, redline_docx_name(base_path, compare_path)
                    )
                    write_redline_docx(result, docx_path)
                    outputs["docx"] = docx_path
                    register_output_path(docx_path)

        if bool(options.get("exec_summary")):
            write_exec_summary_pdf = self._resolve("write_exec_summary_pdf")
            exec_summary_name = self._resolve("exec_summary_name")
            summary_path = os.path.join(
                output_dir, exec_summary_name(base_path, compare_path)
            )
            write_exec_summary_pdf(result, summary_path)
            outputs["exec_summary"] = summary_path
            register_output_path(summary_path)

        reports = options.get("reports") or []
        if isinstance(reports, str):
            reports = [r.strip() for r in reports.split(",") if r.strip()]
        report_name = None
        for report_ext in reports:
            report_ext = str(report_ext).lower().strip()
            if report_ext not in VALID_REPORTS:
                logger.warning("Formato de relatório desconhecido ignorado: %r", report_ext)
                continue
            # Para pares XLSX, o redline já é o .xlsx principal — relatório analítico
            # em xlsx seria redundante com o mesmo nome.
            if is_xlsx and report_ext == "xlsx":
                continue
            if report_name is None:
                report_name = self._resolve("report_name")
            writer = self._resolve("write_%s_report" % report_ext)
            report_path = os.path.join(
                output_dir, report_name(base_path, compare_path, report_ext)
            )
            writer(result, report_path)
            outputs[report_ext] = report_path
            register_output_path(report_path)

        return outputs
