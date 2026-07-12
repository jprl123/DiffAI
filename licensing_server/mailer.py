"""Envio de e-mail com a chave de licença.

Backends:
- console (default): imprime no log — ideal para sandbox/dev
- resend: HTTP API (RESEND_API_KEY)
"""
from __future__ import annotations

import logging
import os
import urllib.error
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

PLAN_LABELS = {
    "pro": "Pro",
    "team": "Equipe",
    "perpetual": "Perpétuo",
}


def send_license_email(email: str, key: str, plan: str) -> None:
    """Envia a chave. O e-mail do corpo/ativação continua sendo o do cliente;
    MAIL_TO_OVERRIDE (dev) redireciona a entrega para o seu endereço."""
    deliver_to = (os.environ.get("MAIL_TO_OVERRIDE") or "").strip() or email
    backend = (os.environ.get("MAIL_BACKEND") or "console").strip().lower()
    subject, body = _compose(email, key, plan)
    if deliver_to != email:
        logger.info("MAIL_TO_OVERRIDE ativo: entrega em %s (cliente=%s)", deliver_to, email)
    if backend == "resend":
        _send_resend(deliver_to, subject, body)
    else:
        _send_console(deliver_to, subject, body)


def _compose(email: str, key: str, plan: str) -> tuple:
    label = PLAN_LABELS.get(plan, plan)
    subject = "Sua chave Compare Docs — plano %s" % label
    body = (
        "Olá,\n\n"
        "Seu pagamento foi confirmado. Aqui está a chave do plano %s:\n\n"
        "    %s\n\n"
        "Como ativar:\n"
        "  1. Abra o Compare Docs\n"
        "  2. Clique em Ativar licença\n"
        "  3. Informe este e-mail (%s) e a chave acima\n\n"
        "A chave vale para o período da assinatura e renova automaticamente "
        "enquanto o pagamento estiver em dia.\n\n"
        "Dúvidas: vendas@comparedocs.app\n"
        "— Equipe Compare Docs\n"
    ) % (label, key, email)
    return subject, body


def _send_console(email: str, subject: str, body: str) -> None:
    logger.info(
        "=== E-MAIL LICENÇA (console) ===\nPara: %s\nAssunto: %s\n\n%s\n=== fim ===",
        email,
        subject,
        body,
    )


def _send_resend(email: str, subject: str, body: str) -> None:
    import json

    api_key = (os.environ.get("RESEND_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("RESEND_API_KEY não configurada.")
    from_addr = (
        os.environ.get("MAIL_FROM") or "Compare Docs <onboarding@resend.dev>"
    ).strip()
    payload = json.dumps(
        {
            "from": from_addr,
            "to": [email],
            "subject": subject,
            "text": body,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json",
            "User-Agent": "CompareDocs-Licensing/1.0",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            logger.info("E-mail enviado via Resend para %s (%s)", email, resp.status)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError("Resend falhou (%s): %s" % (exc.code, detail)) from exc
