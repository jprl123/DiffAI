"""Servidor de licenças do Compare Docs.

Roda separado do app (hoje local, amanhã num VPS/cloud — o app só precisa
da URL). Emite payloads de licença ASSINADOS (Ed25519); o app verifica a
assinatura com a chave pública embutida.

Endpoints:
- POST /v1/activate   {email, key, device, device_name} → {payload, signature}
- POST /v1/validate   {key, device}                     → {payload, signature}
- POST /v1/deactivate {key, device}                     → {ok}
- GET  /v1/health
- GET  /v1/checkout/{plan}  → redirect 303 para Stripe Checkout
- POST /v1/stripe/webhook   → eventos Stripe (assinatura verificada)

Rodar: .venv/bin/python -m licensing_server.server  (porta 8390)
Emitir chave: .venv/bin/python -m licensing_server.issue --email x@y.com --plan pro
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from licensing_server.crypto import sign_payload
from licensing_server.db import LicenseDB

logger = logging.getLogger(__name__)

# Carrega .env da raiz do repo (se existir) — nunca sobrescreve env já setado.
try:
    from dotenv import load_dotenv

    _root = Path(__file__).resolve().parents[1]
    load_dotenv(_root / ".env", override=False)
except ImportError:
    pass

app = FastAPI(title="Compare Docs — Licensing", docs_url=None, redoc_url=None)

# CORS: o portal do cliente (landing na Vercel) chama esta API do navegador.
# Em produção, restrinja via PORTAL_ALLOWED_ORIGINS="https://comparedocs.app".
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

_origins = [
    o.strip()
    for o in os.environ.get("PORTAL_ALLOWED_ORIGINS", "*").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

_db: Optional[LicenseDB] = None

PLAN_FEATURES: Dict[str, Dict[str, Any]] = {
    "trial": {"batch_max": 5, "reports": True, "docx_export": True, "branding": False},
    "pro": {"batch_max": None, "reports": True, "docx_export": True, "branding": False},
    "team": {"batch_max": None, "reports": True, "docx_export": True, "branding": True},
    "perpetual": {"batch_max": None, "reports": True, "docx_export": True, "branding": False},
}

GRACE_DAYS = 7  # tolerância offline após expirar


def get_db() -> LicenseDB:
    global _db
    if _db is None:
        _db = LicenseDB()
    return _db


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _normalize_license_key(key: str) -> str:
    raw = (key or "").strip().upper()
    for ch in (" ", "\t", "\n", "\r", "\u00a0", "\u200b"):
        raw = raw.replace(ch, "")
    for ch in ("\u2010", "\u2011", "\u2013", "\u2014", "\u2212"):
        raw = raw.replace(ch, "-")
    compact = raw.replace("-", "")
    if compact.startswith("CDOC") and len(compact) == 20:
        return "CDOC-%s-%s-%s-%s" % (
            compact[4:8], compact[8:12], compact[12:16], compact[16:20],
        )
    return raw


def _check_license(key: str, email: Optional[str] = None) -> Dict[str, Any]:
    lic = get_db().get_license(_normalize_license_key(key))
    if lic is None:
        raise HTTPException(status_code=404, detail="Chave de licença não encontrada.")
    if lic["status"] != "active":
        raise HTTPException(status_code=403, detail="Esta licença foi revogada.")
    if email is not None and lic["email"] != email.strip().lower():
        raise HTTPException(
            status_code=403, detail="E-mail não confere com o da licença."
        )
    if lic["expires_at"]:
        expires = datetime.datetime.fromisoformat(lic["expires_at"])
        if expires < _now():
            raise HTTPException(
                status_code=403,
                detail="Licença expirada em %s. Renove sua assinatura."
                       % expires.strftime("%d/%m/%Y"),
            )
    return lic


def _signed_response(lic: Dict[str, Any], device: str) -> Dict[str, Any]:
    payload = {
        "v": 1,
        "email": lic["email"],
        "key_hint": lic["key"][:9] + "…" + lic["key"][-4:],
        "plan": lic["plan"],
        "features": PLAN_FEATURES.get(lic["plan"], PLAN_FEATURES["pro"]),
        "device": device,
        "expires_at": lic["expires_at"],
        "grace_days": GRACE_DAYS,
        "issued_at": _now().isoformat(),
    }
    return {"payload": payload, "signature": sign_payload(payload)}


async def _body(request: Request) -> Dict[str, Any]:
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Corpo JSON inválido.")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Corpo JSON inválido.")
    return data


@app.get("/v1/health")
def health() -> Dict[str, bool]:
    return {"ok": True}


@app.post("/v1/activate")
async def activate(request: Request) -> Dict[str, Any]:
    data = await _body(request)
    email = str(data.get("email") or "").strip()
    key = _normalize_license_key(str(data.get("key") or ""))
    device = str(data.get("device") or "").strip()
    device_name = str(data.get("device_name") or "").strip()[:80]
    if not email or not key or not device:
        raise HTTPException(
            status_code=400, detail="Informe e-mail, chave de licença e dispositivo."
        )
    lic = _check_license(key, email=email)
    activations = get_db().list_activations(key)
    devices = {a["device"] for a in activations}
    if device not in devices and len(devices) >= int(lic["max_devices"]):
        raise HTTPException(
            status_code=409,
            detail="Limite de %d dispositivo(s) atingido para esta licença. "
                   "Desative outro dispositivo para continuar."
                   % int(lic["max_devices"]),
        )
    get_db().upsert_activation(key, device, device_name)
    logger.info("Ativação: %s em %s (%s)", key, device[:12], device_name)
    return _signed_response(lic, device)


@app.post("/v1/validate")
async def validate(request: Request) -> Dict[str, Any]:
    data = await _body(request)
    key = _normalize_license_key(str(data.get("key") or ""))
    device = str(data.get("device") or "").strip()
    if not key or not device:
        raise HTTPException(status_code=400, detail="Informe chave e dispositivo.")
    lic = _check_license(key)
    devices = {a["device"] for a in get_db().list_activations(key)}
    if device not in devices:
        raise HTTPException(
            status_code=403,
            detail="Este dispositivo não está ativado para esta licença.",
        )
    get_db().upsert_activation(key, device, "")
    return _signed_response(lic, device)


@app.post("/v1/deactivate")
async def deactivate(request: Request) -> Dict[str, Any]:
    data = await _body(request)
    key = _normalize_license_key(str(data.get("key") or ""))
    device = str(data.get("device") or "").strip()
    if not key or not device:
        raise HTTPException(status_code=400, detail="Informe chave e dispositivo.")
    removed = get_db().remove_activation(key, device)
    return {"ok": bool(removed)}


# -- Portal do cliente (landing page) -------------------------------------------
#
# "Login" sem senha, coerente com o modelo do produto: e-mail + chave de
# licença. O token de sessão é um payload assinado (Ed25519, mesma chave das
# licenças) com validade de 7 dias — o servidor o verifica sem estado.

import base64 as _b64  # noqa: E402

from licensing_server.crypto import canonical_json, load_private_key  # noqa: E402

PORTAL_TOKEN_DAYS = 7


def _portal_token(key: str, email: str) -> str:
    payload = {
        "key": key,
        "email": email,
        "exp": (_now() + datetime.timedelta(days=PORTAL_TOKEN_DAYS)).isoformat(),
    }
    body = canonical_json(payload)
    sig = load_private_key().sign(body)
    return "%s.%s" % (
        _b64.urlsafe_b64encode(body).decode("ascii"),
        _b64.urlsafe_b64encode(sig).decode("ascii"),
    )


def _verify_portal_token(token: str) -> Dict[str, Any]:
    try:
        body_b64, sig_b64 = token.split(".", 1)
        body = _b64.urlsafe_b64decode(body_b64.encode("ascii"))
        sig = _b64.urlsafe_b64decode(sig_b64.encode("ascii"))
        load_private_key().public_key().verify(sig, body)
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=401, detail="Sessão inválida. Entre novamente.")
    exp = datetime.datetime.fromisoformat(payload.get("exp", ""))
    if exp < _now():
        raise HTTPException(status_code=401, detail="Sessão expirada. Entre novamente.")
    return payload


def _portal_auth(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sessão ausente. Entre novamente.")
    return _verify_portal_token(auth[7:].strip())


def _portal_license_view(lic: Dict[str, Any]) -> Dict[str, Any]:
    activations = get_db().list_activations(lic["key"])
    return {
        "email": lic["email"],
        "plan": lic["plan"],
        "key_hint": lic["key"][:9] + "…" + lic["key"][-4:],
        "expires_at": lic["expires_at"],
        "max_devices": lic["max_devices"],
        "status": lic["status"],
        "devices": [
            {
                "device": a["device"],
                "device_name": a["device_name"] or "Dispositivo",
                "activated_at": a["activated_at"],
                "last_seen": a["last_seen"],
            }
            for a in activations
        ],
    }


@app.post("/v1/portal/login")
async def portal_login(request: Request) -> Dict[str, Any]:
    data = await _body(request)
    email = str(data.get("email") or "").strip()
    key = _normalize_license_key(str(data.get("key") or ""))
    if not email or not key:
        raise HTTPException(status_code=400, detail="Informe e-mail e chave de licença.")
    lic = _check_license(key, email=email)
    logger.info("Portal: login de %s (%s…)", lic["email"], key[:9])
    return {
        "token": _portal_token(lic["key"], lic["email"]),
        "license": _portal_license_view(lic),
    }


@app.get("/v1/portal/me")
def portal_me(request: Request) -> Dict[str, Any]:
    session = _portal_auth(request)
    lic = get_db().get_license(session["key"])
    if lic is None:
        raise HTTPException(status_code=404, detail="Licença não encontrada.")
    return {"license": _portal_license_view(lic)}


@app.post("/v1/portal/deactivate")
async def portal_deactivate(request: Request) -> Dict[str, Any]:
    session = _portal_auth(request)
    data = await _body(request)
    device = str(data.get("device") or "").strip()
    if not device:
        raise HTTPException(status_code=400, detail="Informe o dispositivo.")
    get_db().remove_activation(session["key"], device)
    lic = get_db().get_license(session["key"])
    return {"license": _portal_license_view(lic)}


# -- Stripe --------------------------------------------------------------------

@app.get("/v1/checkout/success", response_class=HTMLResponse)
def checkout_success() -> str:
    return (
        "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
        "<title>Pagamento confirmado</title>"
        "<body style='font-family:system-ui;max-width:480px;margin:48px auto;padding:0 16px'>"
        "<h1>Pagamento confirmado</h1>"
        "<p>Enviamos a chave de licença para o e-mail informado no checkout. "
        "Abra o Compare Docs e use <b>Ativar licença</b>.</p>"
        "</body></html>"
    )


@app.get("/v1/checkout/cancel", response_class=HTMLResponse)
def checkout_cancel() -> str:
    return (
        "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
        "<title>Checkout cancelado</title>"
        "<body style='font-family:system-ui;max-width:480px;margin:48px auto;padding:0 16px'>"
        "<h1>Checkout cancelado</h1>"
        "<p>Nenhuma cobrança foi feita. Você pode tentar de novo quando quiser.</p>"
        "</body></html>"
    )


@app.get("/v1/checkout/{plan}")
def checkout(plan: str):
    from licensing_server import stripe_integration

    plan = plan.strip().lower()
    if plan not in ("pro", "team"):
        raise HTTPException(status_code=404, detail="Plano não encontrado.")
    try:
        url = stripe_integration.create_checkout_session(plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("Checkout falhou: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Checkout indisponível no momento. Verifique a configuração Stripe.",
        ) from exc
    except Exception as exc:
        logger.exception("Erro ao criar Checkout Session")
        raise HTTPException(status_code=502, detail="Falha ao falar com o Stripe.") from exc
    return RedirectResponse(url=url, status_code=303)


@app.post("/v1/stripe/webhook")
async def stripe_webhook(request: Request) -> Dict[str, Any]:
    from licensing_server import stripe_integration

    payload = await request.body()
    sig = request.headers.get("stripe-signature") or ""
    if not sig:
        raise HTTPException(status_code=400, detail="Assinatura Stripe ausente.")
    try:
        event = stripe_integration.construct_event(payload, sig)
    except Exception as exc:
        logger.warning("Webhook Stripe rejeitado: %s", exc)
        raise HTTPException(status_code=400, detail="Assinatura inválida.") from exc

    # construct_event devolve StripeObject; normaliza para dict.
    if hasattr(event, "to_dict"):
        event_dict = event.to_dict()
    else:
        event_dict = dict(event)

    try:
        return stripe_integration.handle_webhook_event(event_dict, get_db())
    except Exception as exc:
        logger.exception("Falha ao processar evento Stripe %s", event_dict.get("id"))
        raise HTTPException(status_code=500, detail="Falha ao processar evento.") from exc


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    # Local: 127.0.0.1:8390. Em PaaS (Railway/Fly/Render), a plataforma define
    # PORT e o bind precisa ser 0.0.0.0.
    port = int(os.environ.get("PORT", "8390"))
    host = "0.0.0.0" if "PORT" in os.environ else "127.0.0.1"
    uvicorn.run(app, host=host, port=port, log_level="info")
