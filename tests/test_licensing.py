"""Testes do licenciamento — servidor de licenças real + cliente do app.

Roda com: .venv/bin/python -m tests.test_licensing
Todos os caminhos (licença local, trial, banco do servidor) são isolados em
diretórios temporários via variáveis de ambiente definidas ANTES dos imports.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest

_TMP = tempfile.mkdtemp(prefix="comparedocs-lic-test-")
os.environ["COMPAREDOCS_LICENSE_PATH"] = os.path.join(_TMP, "license.json")
os.environ["COMPAREDOCS_TRIAL_PATH"] = os.path.join(_TMP, "trial.json")
os.environ["COMPAREDOCS_LICENSE_DB"] = os.path.join(_TMP, "licenses.db")
os.environ["COMPAREDOCS_LICENSE_SERVER"] = "http://127.0.0.1:8391"

from app.licensing import client as licensing  # noqa: E402
from licensing_server.db import LicenseDB  # noqa: E402
from licensing_server.server import app as server_app  # noqa: E402


def _start_server() -> None:
    import uvicorn

    config = uvicorn.Config(server_app, host="127.0.0.1", port=8391, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    import urllib.request

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8391/v1/health", timeout=1
            ) as resp:
                if resp.status == 200:
                    return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError("Servidor de licenças não subiu a tempo.")


class TestLicensing(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _start_server()
        cls.db = LicenseDB()

    def setUp(self) -> None:
        for env in ("COMPAREDOCS_LICENSE_PATH", "COMPAREDOCS_TRIAL_PATH"):
            try:
                os.remove(os.environ[env])
            except OSError:
                pass

    # -- trial -----------------------------------------------------------------

    def test_trial_lifecycle(self) -> None:
        st = licensing.status()
        self.assertEqual(st["state"], "trial")
        self.assertEqual(st["trial"]["comparisons_left"], licensing.TRIAL_COMPARISONS)

        ok, msg = licensing.can_compare(3)
        self.assertTrue(ok, msg)
        licensing.consume(3)
        self.assertEqual(
            licensing.status()["trial"]["comparisons_left"],
            licensing.TRIAL_COMPARISONS - 3,
        )

        ok, msg = licensing.can_compare(licensing.TRIAL_BATCH_MAX + 1)
        self.assertFalse(ok)
        self.assertIn("lote", (msg or "").lower())

        licensing.consume(licensing.TRIAL_COMPARISONS)  # esgota
        st = licensing.status()
        self.assertEqual(st["state"], "locked")
        ok, msg = licensing.can_compare(1)
        self.assertFalse(ok)
        self.assertIn("avaliação", (msg or "").lower())

    # -- ativação --------------------------------------------------------------

    def test_activate_validate_deactivate(self) -> None:
        lic = self.db.issue(
            email="cliente@firma.com", plan="pro", max_devices=2, months=12
        )
        st = licensing.activate("cliente@firma.com", lic["key"])
        self.assertEqual(st["state"], "active")
        self.assertEqual(st["plan"], "pro")
        self.assertIsNone(st["features"].get("batch_max"))

        ok, msg = licensing.can_compare(100)
        self.assertTrue(ok, msg)

        # licença sobrevive a "reinício" (releitura do disco) e é verificada
        st2 = licensing.status()
        self.assertEqual(st2["state"], "active")

        st3 = licensing.deactivate()
        self.assertIn(st3["state"], ("trial", "locked"))
        self.assertEqual(self.db.list_activations(lic["key"]), [])

    def test_activate_wrong_email(self) -> None:
        lic = self.db.issue(email="dono@x.com", plan="pro", max_devices=1, months=12)
        with self.assertRaises(licensing.LicenseError) as ctx:
            licensing.activate("intruso@y.com", lic["key"])
        self.assertIn("e-mail", str(ctx.exception).lower())

    def test_activate_unknown_key(self) -> None:
        with self.assertRaises(licensing.LicenseError):
            licensing.activate("a@b.com", "CDOC-AAAA-BBBB-CCCC-DDDD")

    def test_device_limit(self) -> None:
        import json
        import urllib.request

        lic = self.db.issue(email="a@b.com", plan="pro", max_devices=1, months=12)
        licensing.activate("a@b.com", lic["key"])  # ocupa o único slot

        req = urllib.request.Request(
            "http://127.0.0.1:8391/v1/activate",
            data=json.dumps({
                "email": "a@b.com", "key": lic["key"],
                "device": "outro-dispositivo-ficticio", "device_name": "PC 2",
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 409)

    def test_tampered_license_rejected(self) -> None:
        import json

        lic = self.db.issue(email="a@b.com", plan="pro", max_devices=2, months=12)
        licensing.activate("a@b.com", lic["key"])
        path = os.environ["COMPAREDOCS_LICENSE_PATH"]
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        data["payload"]["plan"] = "team"  # adulteração
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        st = licensing.status()
        self.assertIn(st["state"], ("trial", "locked"))  # assinatura não confere

    def test_expired_license_blocked_on_activate(self) -> None:
        lic = self.db.issue(email="a@b.com", plan="pro", max_devices=2, months=-1)
        with self.assertRaises(licensing.LicenseError) as ctx:
            licensing.activate("a@b.com", lic["key"])
        self.assertIn("expirada", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
