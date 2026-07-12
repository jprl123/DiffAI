"""Ponte Stripe → emissão de licença → e-mail.

Checkout Sessions (subscription) + webhook com verificação de assinatura,
idempotência por event_id e mapeamento subscription_id ↔ chave.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import stripe

from licensing_server.db import LicenseDB
from licensing_server.mailer import send_license_email

logger = logging.getLogger(__name__)

PLAN_DEVICES = {"pro": 2, "team": 5}
PLAN_MONTHS = {"pro": 1, "team": 1}


def _configure_stripe() -> None:
    key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY não configurada.")
    stripe.api_key = key


def price_id_for_plan(plan: str) -> str:
    plan = plan.strip().lower()
    env_key = "STRIPE_PRICE_%s" % plan.upper()
    price_id = (os.environ.get(env_key) or "").strip()
    if not price_id:
        raise RuntimeError(
            "Preço Stripe não configurado para o plano '%s' (%s)." % (plan, env_key)
        )
    return price_id


def plan_from_price_id(price_id: Optional[str]) -> Optional[str]:
    if not price_id:
        return None
    for plan in ("pro", "team"):
        if (os.environ.get("STRIPE_PRICE_%s" % plan.upper()) or "").strip() == price_id:
            return plan
    return None


def create_checkout_session(plan: str) -> str:
    """Cria Checkout Session em mode=subscription e devolve a URL."""
    plan = plan.strip().lower()
    if plan not in PLAN_DEVICES:
        raise ValueError("Plano inválido: %s (use pro ou team)." % plan)
    _configure_stripe()
    price_id = price_id_for_plan(plan)
    success = (
        os.environ.get("SUCCESS_URL")
        or "http://127.0.0.1:8390/v1/checkout/success?session_id={CHECKOUT_SESSION_ID}"
    )
    cancel = os.environ.get("CANCEL_URL") or "http://127.0.0.1:8390/v1/checkout/cancel"
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success,
        cancel_url=cancel,
        metadata={"plan": plan},
        subscription_data={"metadata": {"plan": plan}},
        allow_promotion_codes=True,
    )
    if not session.url:
        raise RuntimeError("Stripe não retornou URL de checkout.")
    return session.url


def construct_event(payload: bytes, sig_header: str) -> Any:
    secret = (os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()
    if not secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET não configurada.")
    return stripe.Webhook.construct_event(payload, sig_header, secret)


def handle_webhook_event(event: Dict[str, Any], db: LicenseDB) -> Dict[str, Any]:
    """Processa um evento Stripe já verificado. Idempotente."""
    event_id = event.get("id") or ""
    event_type = event.get("type") or ""
    if not event_id:
        raise ValueError("Evento sem id.")

    if db.event_seen(event_id):
        logger.info("Evento Stripe já processado: %s", event_id)
        return {"ok": True, "duplicate": True}

    data_object = (event.get("data") or {}).get("object") or {}

    try:
        if event_type == "checkout.session.completed":
            _on_checkout_completed(data_object, db)
        elif event_type == "invoice.paid":
            _on_invoice_paid(data_object, db)
        elif event_type == "customer.subscription.deleted":
            _on_subscription_deleted(data_object, db)
        elif event_type == "charge.refunded":
            _on_charge_refunded(data_object, db)
        else:
            logger.info("Evento Stripe ignorado: %s", event_type)
    except Exception:
        # Não marca como processado — Stripe reenvia.
        raise

    db.mark_event_processed(event_id)
    return {"ok": True, "type": event_type}


def _on_checkout_completed(session: Dict[str, Any], db: LicenseDB) -> None:
    email = (
        (session.get("customer_details") or {}).get("email")
        or session.get("customer_email")
        or ""
    ).strip().lower()
    if not email:
        raise ValueError("checkout.session.completed sem e-mail do cliente.")

    metadata = session.get("metadata") or {}
    plan = (metadata.get("plan") or "").strip().lower()
    if plan not in PLAN_DEVICES:
        # fallback: tentar pelo price da linha (se expandido) — senão falha
        raise ValueError("Plano ausente/inválido no metadata do checkout: %r" % plan)

    subscription_id = session.get("subscription")
    if isinstance(subscription_id, dict):
        subscription_id = subscription_id.get("id")
    customer_id = session.get("customer")
    if isinstance(customer_id, dict):
        customer_id = customer_id.get("id")

    # Idempotência extra: se já há chave para esta subscription, não reemite.
    if subscription_id:
        existing = db.get_key_by_subscription(str(subscription_id))
        if existing:
            logger.info(
                "Checkout já vinculado à chave %s (sub %s)", existing, subscription_id
            )
            return

    lic = db.issue(
        email=email,
        plan=plan,
        max_devices=PLAN_DEVICES[plan],
        months=PLAN_MONTHS[plan],
    )
    key = lic["key"]
    if subscription_id:
        db.link_subscription(
            str(subscription_id), key, plan, customer_id=str(customer_id) if customer_id else None
        )
    send_license_email(email, key, plan)
    logger.info("Licença emitida via Stripe: %s → %s (%s)", key, email, plan)


def _months_from_invoice(invoice: Dict[str, Any]) -> int:
    """Infere meses a estender a partir do price (default 1)."""
    lines = (invoice.get("lines") or {}).get("data") or []
    for line in lines:
        price = line.get("price") or {}
        if isinstance(price, str):
            plan = plan_from_price_id(price)
        else:
            plan = plan_from_price_id(price.get("id"))
            recurring = price.get("recurring") or {}
            interval = recurring.get("interval")
            count = int(recurring.get("interval_count") or 1)
            if interval == "year":
                return 12 * count
            if interval == "month":
                return count
        if plan:
            return PLAN_MONTHS.get(plan, 1)
    return 1


def _on_invoice_paid(invoice: Dict[str, Any], db: LicenseDB) -> None:
    # Primeira fatura do checkout já cobre o período inicial via issue().
    billing_reason = invoice.get("billing_reason") or ""
    if billing_reason in ("subscription_create",):
        logger.info("invoice.paid inicial ignorado (já coberto pelo checkout).")
        return

    subscription_id = invoice.get("subscription")
    if isinstance(subscription_id, dict):
        subscription_id = subscription_id.get("id")
    if not subscription_id:
        logger.info("invoice.paid sem subscription — ignorado.")
        return

    key = db.get_key_by_subscription(str(subscription_id))
    if not key:
        logger.warning(
            "invoice.paid: subscription %s sem chave vinculada.", subscription_id
        )
        return

    months = _months_from_invoice(invoice)
    updated = db.extend(key, months)
    if updated:
        logger.info(
            "Licença %s estendida +%d mês(es) → %s",
            key,
            months,
            updated.get("expires_at"),
        )


def _on_subscription_deleted(subscription: Dict[str, Any], db: LicenseDB) -> None:
    sub_id = subscription.get("id")
    if not sub_id:
        return
    key = db.get_key_by_subscription(str(sub_id))
    if not key:
        logger.warning("subscription.deleted: %s sem chave vinculada.", sub_id)
        return
    db.revoke(key)
    logger.info("Licença %s revogada (subscription.deleted).", key)


def _on_charge_refunded(charge: Dict[str, Any], db: LicenseDB) -> None:
    customer_id = charge.get("customer")
    if isinstance(customer_id, dict):
        customer_id = customer_id.get("id")
    key = None
    if customer_id:
        key = db.get_key_by_customer(str(customer_id))
    if not key:
        # tenta via invoice → subscription se presente
        invoice = charge.get("invoice")
        if isinstance(invoice, dict):
            sub = invoice.get("subscription")
            if isinstance(sub, dict):
                sub = sub.get("id")
            if sub:
                key = db.get_key_by_subscription(str(sub))
    if not key:
        logger.warning("charge.refunded sem chave vinculada.")
        return
    db.revoke(key)
    logger.info("Licença %s revogada (charge.refunded).", key)
