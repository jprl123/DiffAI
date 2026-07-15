"""Cliente de licenciamento do app.

Estados possíveis (``status()["state"]``):
- ``trial``          — sem licença, avaliação vigente (14 dias / 25 comparações)
- ``active``         — licença assinada válida para este dispositivo
- ``expired``        — licença venceu (além da tolerância) → bloqueado
- ``locked``         — sem licença e avaliação esgotada → bloqueado
- ``invalid``        — arquivo de licença corrompido/forjado → tratado como locked

A licença local é um payload JSON + assinatura Ed25519 do servidor; o app
verifica com a chave pública embutida (``pubkey.py``) — funciona offline.
Revalidação online oportunista a cada 24h (renovações estendem a validade;
revogação derruba a licença).

Honestidade sobre o trial: ele é controlado localmente e pode ser burlado
por quem apagar ``~/.comparedocs/trial.json``. Anti-abuso real de trial
exige emissão server-side — anotado em docs/MUDANCAS_FUTURAS.md.
"""
from __future__ import annotations

import base64
import datetime
import json
import logging
import os
import threading
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.licensing.device import device_fingerprint, device_name
from app.licensing.pubkey import LICENSE_PUBLIC_KEY_B64
from app.licensing import build_flags

logger = logging.getLogger(__name__)

TRIAL_DAYS = 14
TRIAL_COMPARISONS = 25
TRIAL_BATCH_MAX = 5
REVALIDATE_HOURS = 24

# Build de teste: scripts/build_desktop.sh --unlimited
_UNLIMITED = bool(getattr(build_flags, "UNLIMITED", False)) or (
    os.environ.get("COMPAREDOCS_UNLIMITED", "").strip().lower() in ("1", "true", "yes")
)

_BASE_DIR = os.path.join(os.path.expanduser("~"), ".comparedocs")
LICENSE_PATH = os.environ.get(
    "COMPAREDOCS_LICENSE_PATH", os.path.join(_BASE_DIR, "license.json")
)
TRIAL_PATH = os.environ.get(
    "COMPAREDOCS_TRIAL_PATH", os.path.join(_BASE_DIR, "trial.json")
)
from app.licensing.server_url import DEFAULT_SERVER_URL

SERVER_URL = os.environ.get(
    "COMPAREDOCS_LICENSE_SERVER", DEFAULT_SERVER_URL
).rstrip("/")

_lock = threading.Lock()


class LicenseError(Exception):
    """Erro de licenciamento com mensagem apresentável ao usuário."""


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _canonical(payload: Dict[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _parse_dt(value: Optional[str]) -> Optional[datetime.datetime]:
    if not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def _server_post(path: str, body: Dict[str, Any], timeout: float = 6.0) -> Dict[str, Any]:
    url = SERVER_URL + path
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.load(exc).get("detail")
        except Exception:
            detail = None
        raise LicenseError(detail or "Erro do servidor de licenças (%d)." % exc.code)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise ConnectionError(str(exc))


# ---------------------------------------------------------------------------
# Verificação da licença local
# ---------------------------------------------------------------------------

def _verify_signature(payload: Dict[str, Any], signature_b64: str) -> bool:
    try:
        pub = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(LICENSE_PUBLIC_KEY_B64)
        )
        pub.verify(base64.b64decode(signature_b64), _canonical(payload))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def _load_license() -> Optional[Dict[str, Any]]:
    """Retorna {payload, signature, last_validated_at} se íntegro; senão None."""
    data = _read_json(LICENSE_PATH)
    if not data:
        return None
    payload = data.get("payload")
    signature = data.get("signature")
    if not isinstance(payload, dict) or not isinstance(signature, str):
        logger.warning("Arquivo de licença malformado.")
        return None
    if not _verify_signature(payload, signature):
        logger.warning("Assinatura da licença inválida — ignorando arquivo local.")
        return None
    if payload.get("device") != device_fingerprint():
        logger.warning("Licença pertence a outro dispositivo — ignorando.")
        return None
    return data


def _license_state(payload: Dict[str, Any]) -> str:
    expires = _parse_dt(payload.get("expires_at"))
    if expires is None:
        return "active"  # perpétua
    grace = datetime.timedelta(days=int(payload.get("grace_days") or 0))
    if _now() <= expires + grace:
        return "active"
    return "expired"


# ---------------------------------------------------------------------------
# Trial local
# ---------------------------------------------------------------------------

def _load_trial() -> Dict[str, Any]:
    data = _read_json(TRIAL_PATH)
    if not data or "started_at" not in data:
        data = {"started_at": _now().isoformat(), "comparisons_used": 0}
        try:
            _write_json(TRIAL_PATH, data)
        except OSError:
            logger.warning("Não foi possível iniciar o registro da avaliação.")
    return data


def _trial_status() -> Dict[str, Any]:
    trial = _load_trial()
    started = _parse_dt(trial.get("started_at")) or _now()
    used = int(trial.get("comparisons_used") or 0)
    days_left = TRIAL_DAYS - (_now() - started).days
    comparisons_left = TRIAL_COMPARISONS - used
    return {
        "days_left": max(0, days_left),
        "comparisons_left": max(0, comparisons_left),
        "expired": days_left <= 0 or comparisons_left <= 0,
    }


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def status() -> Dict[str, Any]:
    if _UNLIMITED:
        return {
            "state": "active",
            "plan": "beta",
            "email": "teste@diffai.app",
            "key_hint": "BETA-UNLIMITED",
            "expires_at": None,
            "features": {"batch_max": None, "docx_export": True, "reports": True, "branding": True},
            "device": device_fingerprint(),
            "device_name": device_name(),
            "last_validated_at": None,
            "trial": None,
            "unlimited_build": True,
        }
    with _lock:
        stored = _load_license()
        if stored is not None:
            payload = stored["payload"]
            state = _license_state(payload)
            return {
                "state": state,
                "plan": payload.get("plan"),
                "email": payload.get("email"),
                "key_hint": payload.get("key_hint"),
                "expires_at": payload.get("expires_at"),
                "features": payload.get("features") or {},
                "device": device_fingerprint(),
                "device_name": device_name(),
                "last_validated_at": stored.get("last_validated_at"),
                "trial": None,
            }
        trial = _trial_status()
        return {
            "state": "locked" if trial["expired"] else "trial",
            "plan": "trial" if not trial["expired"] else None,
            "email": None,
            "key_hint": None,
            "expires_at": None,
            "features": {"batch_max": TRIAL_BATCH_MAX},
            "device": device_fingerprint(),
            "device_name": device_name(),
            "last_validated_at": None,
            "trial": trial,
        }


def _normalize_license_key(key: str) -> str:
    """Normaliza chave colada do e-mail (espaços, hífens tipográficos, sem hífens)."""
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


def activate(email: str, key: str) -> Dict[str, Any]:
    email = (email or "").strip()
    key = _normalize_license_key(key)
    if not email or "@" not in email:
        raise LicenseError("Informe o e-mail usado na compra da licença.")
    if not key.startswith("CDOC-") or len(key) < 20:
        raise LicenseError("Chave inválida. O formato é CDOC-XXXX-XXXX-XXXX-XXXX.")

    try:
        response = _server_post("/v1/activate", {
            "email": email,
            "key": key,
            "device": device_fingerprint(),
            "device_name": device_name(),
        })
    except ConnectionError:
        raise LicenseError(
            "Servidor de licenças inacessível. Verifique sua conexão e tente "
            "novamente."
        )
    payload = response.get("payload")
    signature = response.get("signature")
    if not isinstance(payload, dict) or not _verify_signature(payload, signature or ""):
        raise LicenseError(
            "Resposta de ativação inválida (assinatura não confere). "
            "Atualize o aplicativo e tente novamente."
        )
    with _lock:
        _write_json(LICENSE_PATH, {
            "payload": payload,
            "signature": signature,
            "key": key,  # necessário para revalidar/desativar
            "last_validated_at": _now().isoformat(),
        })
    logger.info("Licença ativada: plano %s", payload.get("plan"))
    return status()


def deactivate() -> Dict[str, Any]:
    with _lock:
        stored = _read_json(LICENSE_PATH) or {}
        key = stored.get("key")
    if key:
        try:
            _server_post("/v1/deactivate", {
                "key": key, "device": device_fingerprint(),
            })
        except (ConnectionError, LicenseError) as exc:
            logger.warning("Desativação remota falhou (%s); removendo local.", exc)
    with _lock:
        try:
            os.remove(LICENSE_PATH)
        except OSError:
            pass
    return status()


def revalidate_if_due() -> None:
    """Revalidação online oportunista (no máx. 1x/24h). Nunca lança exceção."""
    try:
        with _lock:
            stored = _load_license()
        if stored is None:
            return
        last = _parse_dt(stored.get("last_validated_at"))
        if last and _now() - last < datetime.timedelta(hours=REVALIDATE_HOURS):
            return
        key = (_read_json(LICENSE_PATH) or {}).get("key")
        if not key:
            return
        try:
            response = _server_post("/v1/validate", {
                "key": key, "device": device_fingerprint(),
            }, timeout=4.0)
        except ConnectionError:
            return  # offline: a licença assinada continua valendo até expirar
        except LicenseError as exc:
            # Servidor respondeu que a licença não vale mais (revogada/expirada).
            logger.warning("Licença rejeitada na revalidação: %s", exc)
            with _lock:
                try:
                    os.remove(LICENSE_PATH)
                except OSError:
                    pass
            return
        payload = response.get("payload")
        signature = response.get("signature")
        if isinstance(payload, dict) and _verify_signature(payload, signature or ""):
            with _lock:
                _write_json(LICENSE_PATH, {
                    "payload": payload,
                    "signature": signature,
                    "key": key,
                    "last_validated_at": _now().isoformat(),
                })
    except Exception:
        logger.exception("Erro inesperado na revalidação de licença")


def can_compare(pairs_count: int) -> Tuple[bool, Optional[str]]:
    """Gate de execução: (permitido, mensagem de erro pt-BR se bloqueado)."""
    if _UNLIMITED:
        return True, None
    st = status()
    if st["state"] == "active":
        batch_max = (st.get("features") or {}).get("batch_max")
        if batch_max is not None and pairs_count > int(batch_max):
            return False, (
                "Seu plano permite lotes de até %d pares." % int(batch_max)
            )
        return True, None
    if st["state"] == "trial":
        trial = st["trial"] or {}
        if pairs_count > TRIAL_BATCH_MAX:
            return False, (
                "Na avaliação gratuita o lote é limitado a %d pares. "
                "Ative uma licença para lotes maiores." % TRIAL_BATCH_MAX
            )
        if pairs_count > trial.get("comparisons_left", 0):
            return False, (
                "Restam %d comparações na sua avaliação gratuita. "
                "Ative uma licença para continuar."
                % trial.get("comparisons_left", 0)
            )
        return True, None
    if st["state"] == "expired":
        return False, (
            "Sua licença expirou. Renove a assinatura para continuar comparando."
        )
    return False, (
        "Sua avaliação gratuita terminou. Ative uma licença para continuar."
    )


def consume(pairs_count: int) -> None:
    """Debita comparações da avaliação (não faz nada com licença ativa)."""
    if _UNLIMITED:
        return
    with _lock:
        if _load_license() is not None:
            return
        trial = _load_trial()
        trial["comparisons_used"] = int(trial.get("comparisons_used") or 0) + int(
            pairs_count
        )
        try:
            _write_json(TRIAL_PATH, trial)
        except OSError:
            logger.warning("Não foi possível atualizar o contador da avaliação.")
