"""Testes da ponte Stripe (webhooks mockados — sem API real).

Roda com: .venv/bin/python -m tests.test_stripe
"""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

_TMP = tempfile.mkdtemp(prefix="comparedocs-stripe-test-")
os.environ["COMPAREDOCS_LICENSE_DB"] = os.path.join(_TMP, "licenses.db")
os.environ["MAIL_BACKEND"] = "console"
os.environ["STRIPE_PRICE_PRO"] = "price_test_pro"
os.environ["STRIPE_PRICE_TEAM"] = "price_test_team"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_dummy"

from fastapi.testclient import TestClient  # noqa: E402

from licensing_server.db import LicenseDB  # noqa: E402
from licensing_server import stripe_integration  # noqa: E402
from licensing_server.server import app as server_app  # noqa: E402


class TestLicenseExtend(unittest.TestCase):
    def setUp(self) -> None:
        self.db = LicenseDB(path=os.path.join(_TMP, "extend-%s.db" % self.id()))

    def test_extend_from_now_when_expired(self) -> None:
        lic = self.db.issue("a@b.com", "pro", 2, months=1)
        # força expiração no passado
        import datetime

        past = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=10)
        ).isoformat()
        with self.db._lock, self.db._connect() as conn:
            conn.execute(
                "UPDATE licenses SET expires_at = ? WHERE key = ?",
                (past, lic["key"]),
            )
        updated = self.db.extend(lic["key"], 1)
        self.assertIsNotNone(updated)
        expires = datetime.datetime.fromisoformat(updated["expires_at"])
        now = datetime.datetime.now(datetime.timezone.utc)
        self.assertGreater(expires, now + datetime.timedelta(days=20))

    def test_extend_from_current_when_still_valid(self) -> None:
        import datetime

        lic = self.db.issue("a@b.com", "pro", 2, months=1)
        before = datetime.datetime.fromisoformat(lic["expires_at"])
        updated = self.db.extend(lic["key"], 1)
        after = datetime.datetime.fromisoformat(updated["expires_at"])
        delta = (after - before).days
        self.assertGreaterEqual(delta, 30)
        self.assertLessEqual(delta, 32)


class TestStripeWebhookHandlers(unittest.TestCase):
    def setUp(self) -> None:
        self.db = LicenseDB(path=os.path.join(_TMP, "wh-%s.db" % self.id()))

    def test_checkout_completed_issues_key_and_email(self) -> None:
        event = {
            "id": "evt_checkout_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer_details": {"email": "cliente@firma.com"},
                    "customer": "cus_123",
                    "subscription": "sub_123",
                    "metadata": {"plan": "pro"},
                }
            },
        }
        with mock.patch(
            "licensing_server.stripe_integration.send_license_email"
        ) as mail:
            result = stripe_integration.handle_webhook_event(event, self.db)
        self.assertTrue(result["ok"])
        mail.assert_called_once()
        email, key, plan = mail.call_args[0]
        self.assertEqual(email, "cliente@firma.com")
        self.assertEqual(plan, "pro")
        self.assertTrue(key.startswith("CDOC-"))
        lic = self.db.get_license(key)
        self.assertEqual(lic["status"], "active")
        self.assertEqual(lic["max_devices"], 2)
        self.assertEqual(self.db.get_key_by_subscription("sub_123"), key)

    def test_duplicate_event_is_noop(self) -> None:
        event = {
            "id": "evt_dup_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer_details": {"email": "x@y.com"},
                    "subscription": "sub_dup",
                    "metadata": {"plan": "pro"},
                }
            },
        }
        with mock.patch("licensing_server.stripe_integration.send_license_email"):
            stripe_integration.handle_webhook_event(event, self.db)
            result = stripe_integration.handle_webhook_event(event, self.db)
        self.assertTrue(result.get("duplicate"))
        # só uma licença
        key = self.db.get_key_by_subscription("sub_dup")
        self.assertIsNotNone(key)

    def test_invoice_paid_extends(self) -> None:
        lic = self.db.issue("r@x.com", "pro", 2, months=1)
        self.db.link_subscription("sub_ren", lic["key"], "pro", "cus_ren")
        before = lic["expires_at"]
        event = {
            "id": "evt_inv_1",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "billing_reason": "subscription_cycle",
                    "subscription": "sub_ren",
                    "lines": {
                        "data": [
                            {
                                "price": {
                                    "id": "price_test_pro",
                                    "recurring": {
                                        "interval": "month",
                                        "interval_count": 1,
                                    },
                                }
                            }
                        ]
                    },
                }
            },
        }
        stripe_integration.handle_webhook_event(event, self.db)
        after = self.db.get_license(lic["key"])["expires_at"]
        self.assertGreater(after, before)

    def test_subscription_deleted_revokes(self) -> None:
        lic = self.db.issue("r@x.com", "team", 5, months=1)
        self.db.link_subscription("sub_del", lic["key"], "team")
        event = {
            "id": "evt_del_1",
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": "sub_del"}},
        }
        stripe_integration.handle_webhook_event(event, self.db)
        self.assertEqual(self.db.get_license(lic["key"])["status"], "revoked")

    def test_charge_refunded_revokes(self) -> None:
        lic = self.db.issue("r@x.com", "pro", 2, months=1)
        self.db.link_subscription("sub_ref", lic["key"], "pro", "cus_ref")
        event = {
            "id": "evt_ref_1",
            "type": "charge.refunded",
            "data": {"object": {"customer": "cus_ref"}},
        }
        stripe_integration.handle_webhook_event(event, self.db)
        self.assertEqual(self.db.get_license(lic["key"])["status"], "revoked")


class TestStripeWebhookRoute(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(server_app)

    def test_missing_signature_400(self) -> None:
        resp = self.client.post(
            "/v1/stripe/webhook",
            content=b"{}",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_invalid_signature_400(self) -> None:
        with mock.patch(
            "licensing_server.stripe_integration.construct_event",
            side_effect=ValueError("bad sig"),
        ):
            resp = self.client.post(
                "/v1/stripe/webhook",
                content=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "stripe-signature": "t=1,v1=x",
                },
            )
        self.assertEqual(resp.status_code, 400)

    def test_valid_event_200(self) -> None:
        fake_event = {
            "id": "evt_route_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer_details": {"email": "route@test.com"},
                    "subscription": "sub_route",
                    "metadata": {"plan": "team"},
                }
            },
        }

        class _Obj(dict):
            def to_dict(self):
                return dict(self)

        with mock.patch(
            "licensing_server.stripe_integration.construct_event",
            return_value=_Obj(fake_event),
        ), mock.patch(
            "licensing_server.stripe_integration.send_license_email"
        ):
            resp = self.client.post(
                "/v1/stripe/webhook",
                content=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "stripe-signature": "t=1,v1=ok",
                },
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get("ok"))


if __name__ == "__main__":
    unittest.main()
