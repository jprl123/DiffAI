"""API FastAPI do Compare-Docs — rotas + frontend estático.

Servidor local (mesma origem para API e interface): não há CORS.
Rodar com: ``.venv/bin/python -m app.main`` (porta fixa 8377).
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import threading
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.datastructures import UploadFile

from app import jobs
from app.batch import pair_files
from app.jobs import JobManager
from app.native_dialogs import pick_folder

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_HTML = os.path.join(PROJECT_ROOT, "web", "index.html")

app = FastAPI(title="Compare-Docs", docs_url=None, redoc_url=None)
manager = JobManager()

_TRUE_VALUES = {"1", "true", "yes", "on", "sim", "verdadeiro"}

_PLACEHOLDER_HTML = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>Compare-Docs</title></head>
<body style="font-family: sans-serif; padding: 2rem;">
<h1>Compare-Docs</h1>
<p>A interface (web/index.html) ainda não foi instalada. A API está ativa em
<code>/api/health</code>.</p>
</body></html>"""


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in _TRUE_VALUES


def _parse_reports(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip().lower() for v in value if str(v).strip()]
    return [part.strip().lower() for part in str(value).split(",") if part.strip()]


def _normalize_options(raw: Any) -> Dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    output_dir = raw.get("output_dir")
    if output_dir is not None and not str(output_dir).strip():
        output_dir = None
    return {
        "changed_pages_only": _parse_bool(raw.get("changed_pages_only")),
        "export_docx": _parse_bool(raw.get("export_docx")),
        "exec_summary": _parse_bool(raw.get("exec_summary")),
        "reports": _parse_reports(raw.get("reports")),
        "output_dir": str(output_dir) if output_dir else None,
    }


async def _read_json_body(request: Request) -> Dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Corpo da requisição não é um JSON válido.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="O corpo JSON deve ser um objeto.")
    return payload


async def _save_upload(upload: UploadFile, target_dir: str) -> str:
    """Salva um upload preservando o nome original do arquivo."""
    filename = os.path.basename(upload.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="Arquivo enviado sem nome válido.")
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, filename)
    content = await upload.read()
    if not content:
        raise HTTPException(
            status_code=400,
            detail="O arquivo '%s' está vazio. Envie um documento válido." % filename,
        )
    with open(target_path, "wb") as fh:
        fh.write(content)
    return target_path


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@app.get("/")
def index() -> Any:
    if os.path.isfile(INDEX_HTML):
        return FileResponse(INDEX_HTML, media_type="text/html")
    return HTMLResponse(_PLACEHOLDER_HTML, status_code=200)


@app.get("/api/health")
def health() -> Dict[str, bool]:
    return {"ok": True}


# ---------------------------------------------------------------------------
# Licenciamento
# ---------------------------------------------------------------------------

from app.licensing import client as licensing  # noqa: E402


def _enforce_license(pairs_count: int) -> None:
    allowed, message = licensing.can_compare(pairs_count)
    if not allowed:
        # 402 Payment Required — o frontend intercepta e abre a ativação.
        raise HTTPException(status_code=402, detail=message)


@app.get("/api/license/status")
def license_status() -> Dict[str, Any]:
    # Revalidação online oportunista, sem bloquear a resposta.
    threading.Thread(target=licensing.revalidate_if_due, daemon=True).start()
    return licensing.status()


@app.post("/api/license/activate")
async def license_activate(request: Request) -> Dict[str, Any]:
    payload = await _read_json_body(request)
    try:
        return licensing.activate(
            str(payload.get("email") or ""), str(payload.get("key") or "")
        )
    except licensing.LicenseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/license/deactivate")
def license_deactivate() -> Dict[str, Any]:
    return licensing.deactivate()


@app.get("/api/plans")
def get_plans() -> Dict[str, Any]:
    from app.licensing.plans import PLANS, SALES_EMAIL

    return {"plans": PLANS, "sales_email": SALES_EMAIL}


@app.post("/api/compare/single")
async def compare_single(request: Request) -> Dict[str, str]:
    content_type = (request.headers.get("content-type") or "").lower()

    if content_type.startswith("application/json"):
        payload = await _read_json_body(request)
        base_path = str(payload.get("base_path") or "").strip()
        compare_path = str(payload.get("compare_path") or "").strip()
        options = _normalize_options(payload.get("options"))
        swap = _parse_bool(payload.get("swap")) or _parse_bool(
            (payload.get("options") or {}).get("swap") if isinstance(payload.get("options"), dict) else None
        )
        if not base_path or not compare_path:
            raise HTTPException(
                status_code=400,
                detail="Informe 'base_path' e 'compare_path' no corpo JSON.",
            )
        if not os.path.isfile(base_path):
            raise HTTPException(
                status_code=400, detail="Arquivo base não encontrado: '%s'." % base_path
            )
        if not os.path.isfile(compare_path):
            raise HTTPException(
                status_code=400,
                detail="Arquivo de comparação não encontrado: '%s'." % compare_path,
            )
    else:
        try:
            form = await request.form()
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Envie multipart/form-data com 'base_file' e 'compare_file', "
                       "ou JSON com 'base_path' e 'compare_path'.",
            )
        base_file = form.get("base_file")
        compare_file = form.get("compare_file")
        if not isinstance(base_file, UploadFile) or not isinstance(compare_file, UploadFile):
            raise HTTPException(
                status_code=400,
                detail="Envie os dois arquivos: 'base_file' e 'compare_file'.",
            )
        options = _normalize_options(
            {
                "changed_pages_only": form.get("changed_pages_only"),
                "export_docx": form.get("export_docx"),
                "exec_summary": form.get("exec_summary"),
                "reports": form.get("reports"),
                "output_dir": form.get("output_dir"),
            }
        )
        swap = _parse_bool(form.get("swap"))
        upload_root = tempfile.mkdtemp(prefix="comparedocs-upload-")
        base_path = await _save_upload(base_file, os.path.join(upload_root, "base"))
        compare_path = await _save_upload(compare_file, os.path.join(upload_root, "compare"))

    if swap:
        base_path, compare_path = compare_path, base_path

    _enforce_license(pairs_count=1)
    job_id = manager.create_job([(base_path, compare_path)], options)
    licensing.consume(1)
    return {"job_id": job_id}


@app.post("/api/batch/preview")
async def batch_preview(request: Request) -> Dict[str, Any]:
    """Prévia do pareamento do lote — nada é processado aqui."""
    from app.batch import pair_files_detailed

    payload = await _read_json_body(request)
    base_dir = str(payload.get("base_dir") or "").strip()
    compare_dir = str(payload.get("compare_dir") or "").strip()
    if _parse_bool(payload.get("swap")):
        base_dir, compare_dir = compare_dir, base_dir
    if not base_dir or not compare_dir:
        raise HTTPException(
            status_code=400, detail="Informe 'base_dir' e 'compare_dir' no corpo JSON."
        )
    if not os.path.isdir(base_dir):
        raise HTTPException(
            status_code=400, detail="Pasta base não encontrada: '%s'." % base_dir
        )
    if not os.path.isdir(compare_dir):
        raise HTTPException(
            status_code=400, detail="Pasta revisada não encontrada: '%s'." % compare_dir
        )
    try:
        pairs, unmatched_base, unmatched_compare = pair_files_detailed(
            base_dir, compare_dir
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "pairs": pairs,
        "unmatched_base": unmatched_base,
        "unmatched_compare": unmatched_compare,
    }


@app.get("/api/branding")
def branding_get() -> Dict[str, Any]:
    from app.branding import branding_status

    return branding_status()


@app.post("/api/branding/logo")
async def branding_upload(request: Request) -> Dict[str, Any]:
    from app.branding import branding_status, save_logo

    if not branding_status()["allowed"]:
        raise HTTPException(
            status_code=403,
            detail="A marca do escritório é exclusiva do plano Equipe.",
        )
    try:
        form = await request.form()
    except Exception:
        raise HTTPException(
            status_code=400, detail="Envie o arquivo do logo em multipart/form-data."
        )
    upload = form.get("logo")
    if not isinstance(upload, UploadFile):
        raise HTTPException(status_code=400, detail="Envie o campo 'logo' com a imagem.")
    data = await upload.read()
    try:
        save_logo(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return branding_status()


@app.delete("/api/branding/logo")
def branding_delete() -> Dict[str, Any]:
    from app.branding import branding_status, clear_logo

    clear_logo()
    return branding_status()


@app.post("/api/compare/batch")
async def compare_batch(request: Request) -> Dict[str, str]:
    payload = await _read_json_body(request)
    base_dir = str(payload.get("base_dir") or "").strip()
    compare_dir = str(payload.get("compare_dir") or "").strip()
    raw_options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    options = _normalize_options(raw_options)
    swap = _parse_bool(payload.get("swap")) or _parse_bool(raw_options.get("swap"))

    if not base_dir or not compare_dir:
        raise HTTPException(
            status_code=400, detail="Informe 'base_dir' e 'compare_dir' no corpo JSON."
        )
    if swap:
        base_dir, compare_dir = compare_dir, base_dir
    if not os.path.isdir(base_dir):
        raise HTTPException(
            status_code=400, detail="Pasta base não encontrada: '%s'." % base_dir
        )
    if not os.path.isdir(compare_dir):
        raise HTTPException(
            status_code=400, detail="Pasta revisada não encontrada: '%s'." % compare_dir
        )

    try:
        pairs, unmatched_base, unmatched_compare = pair_files(base_dir, compare_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not pairs:
        parts = [
            "Nenhum par de documentos correspondentes foi encontrado entre as duas pastas."
        ]
        if unmatched_base:
            parts.append("Sem correspondência na pasta base: %s." % ", ".join(unmatched_base))
        else:
            parts.append("A pasta base não contém arquivos .docx, .pdf ou .xlsx.")
        if unmatched_compare:
            parts.append(
                "Sem correspondência na pasta revisada: %s." % ", ".join(unmatched_compare)
            )
        else:
            parts.append("A pasta revisada não contém arquivos .docx, .pdf ou .xlsx.")
        parts.append("Verifique se os nomes dos arquivos são semelhantes nos dois lados.")
        raise HTTPException(status_code=400, detail=" ".join(parts))

    _enforce_license(pairs_count=len(pairs))
    job_id = manager.create_job(pairs, options)
    licensing.consume(len(pairs))
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> Dict[str, Any]:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job não encontrado: '%s'." % job_id)
    return job


@app.get("/api/jobs/{job_id}/result/{index}")
def get_job_result(job_id: str, index: int) -> Dict[str, Any]:
    if manager.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job não encontrado: '%s'." % job_id)
    result = manager.get_result(job_id, index)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Resultado %d não disponível para o job '%s'." % (index, job_id),
        )
    return result


@app.get("/api/jobs/{job_id}/result/{index}/insights")
def get_job_insights(job_id: str, index: int) -> Dict[str, Any]:
    """Análise IA local — resumo executivo e alertas (sem envio à nuvem)."""
    if manager.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job não encontrado: '%s'." % job_id)
    result = manager.get_result_object(job_id, index)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Resultado %d não disponível para o job '%s'." % (index, job_id),
        )
    from app.ai.insights import generate_insights

    return generate_insights(result)


@app.get("/api/history")
def get_history(limit: int = 200) -> Dict[str, Any]:
    """Histórico persistente de comparações (mais recente primeiro)."""
    from app.history import get_store

    return {"entries": get_store().list_entries(limit=limit)}


@app.delete("/api/history/{entry_id}")
def delete_history_entry(entry_id: str) -> Dict[str, bool]:
    from app.history import get_store

    if not get_store().remove_entry(entry_id):
        raise HTTPException(
            status_code=404, detail="Entrada de histórico não encontrada."
        )
    return {"ok": True}


@app.get("/api/history/{entry_id}/result")
def get_history_result(entry_id: str) -> Dict[str, Any]:
    """Resultado da comparação (mudanças) — sobrevive ao reinício do app."""
    from app.history import get_store
    from app.history_result import result_dict_for_entry

    entry = get_store().get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entrada de histórico não encontrada.")
    if entry.get("status") != "ok":
        raise HTTPException(
            status_code=400,
            detail="Esta comparação falhou e não possui resultado detalhado.",
        )
    data = result_dict_for_entry(entry)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail="Não foi possível carregar as mudanças — arquivos originais ausentes.",
        )
    return data


@app.get("/api/history/{entry_id}/insights")
def get_history_insights(entry_id: str) -> Dict[str, Any]:
    from app.history import get_store
    from app.history_result import result_object_for_entry

    entry = get_store().get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entrada de histórico não encontrada.")
    if entry.get("status") != "ok":
        raise HTTPException(
            status_code=400,
            detail="Esta comparação falhou e não possui análise disponível.",
        )
    result = result_object_for_entry(entry)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Não foi possível gerar a análise — arquivos originais ausentes.",
        )
    from app.ai.insights import generate_insights

    return generate_insights(result)


@app.delete("/api/history")
def clear_history() -> Dict[str, Any]:
    from app.history import get_store

    removed = get_store().clear()
    return {"ok": True, "removed": removed}


@app.post("/api/pick-folder")
async def pick_folder_route(request: Request) -> Any:
    """Abre o explorador de arquivos nativo para escolher uma pasta."""
    payload: Dict[str, Any] = {}
    try:
        payload = await request.json()
    except Exception:
        pass
    if not isinstance(payload, dict):
        payload = {}
    initial_dir = str(payload.get("initial_dir") or "").strip() or None
    prompt = str(payload.get("prompt") or "Selecionar pasta").strip() or "Selecionar pasta"
    path = pick_folder(initial_dir=initial_dir, prompt=prompt)
    if not path:
        return Response(status_code=204)
    return {"path": path}


@app.post("/api/open")
async def open_path(request: Request) -> Dict[str, bool]:
    payload = await _read_json_body(request)
    path = str(payload.get("path") or "").strip()
    if not path:
        raise HTTPException(status_code=400, detail="Informe 'path' no corpo JSON.")
    if not jobs.is_path_allowed(path):
        # Após reiniciar o app, o whitelist em memória zera — mas outputs
        # registrados no histórico persistente continuam legítimos.
        from app.history import get_store

        if not get_store().path_known(path):
            raise HTTPException(
                status_code=403,
                detail="Este caminho não foi gerado por uma comparação do "
                       "Compare Docs e não pode ser aberto.",
            )
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado: '%s'." % path)
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    try:
        subprocess.Popen([opener, path])
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail="Falha ao abrir o arquivo: %s" % exc
        )
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="127.0.0.1", port=8377, log_level="info")
