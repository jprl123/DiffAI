"""Banco do servidor de licenças (SQLite, stdlib).

Tabelas:
- licenses: uma linha por chave vendida (plano, validade, limite de dispositivos)
- activations: dispositivos ativos por chave
- stripe_subscriptions: mapeamento subscription_id ↔ chave
- stripe_events: idempotência de webhooks
"""
from __future__ import annotations

import datetime
import os
import secrets
import sqlite3
import threading
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = os.environ.get(
    "COMPAREDOCS_LICENSE_DB",
    os.path.join(os.path.expanduser("~"), ".comparedocs-server", "licenses.db"),
)

_KEY_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sem 0/O/1/I/L


def generate_key() -> str:
    groups = [
        "".join(secrets.choice(_KEY_ALPHABET) for _ in range(4)) for _ in range(4)
    ]
    return "CDOC-" + "-".join(groups)


class LicenseDB:
    def __init__(self, path: Optional[str] = None) -> None:
        self._path = os.path.abspath(path or DEFAULT_DB_PATH)
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS licenses (
                    key TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    max_devices INTEGER NOT NULL DEFAULT 1,
                    expires_at TEXT,              -- ISO; NULL = perpétua
                    status TEXT NOT NULL DEFAULT 'active',  -- active|revoked
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS activations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL REFERENCES licenses(key),
                    device TEXT NOT NULL,
                    device_name TEXT,
                    activated_at TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    UNIQUE (key, device)
                );
                CREATE TABLE IF NOT EXISTS stripe_subscriptions (
                    subscription_id TEXT PRIMARY KEY,
                    license_key TEXT NOT NULL REFERENCES licenses(key),
                    customer_id TEXT,
                    plan TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS stripe_events (
                    event_id TEXT PRIMARY KEY,
                    processed_at TEXT NOT NULL
                );
                """
            )

    # -- emissão ---------------------------------------------------------------

    def issue(
        self,
        email: str,
        plan: str,
        max_devices: int,
        months: Optional[int],
    ) -> Dict[str, Any]:
        key = generate_key()
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = None
        if months is not None:
            expires_at = (now + datetime.timedelta(days=31 * months)).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO licenses (key, email, plan, max_devices, expires_at,"
                " status, created_at) VALUES (?, ?, ?, ?, ?, 'active', ?)",
                (key, email.strip().lower(), plan, max_devices, expires_at,
                 now.isoformat()),
            )
        return self.get_license(key)  # type: ignore[return-value]

    def extend(self, key: str, months: int) -> Optional[Dict[str, Any]]:
        """Estende expires_at em +months (a partir do maior entre agora e a validade atual)."""
        if months <= 0:
            raise ValueError("months deve ser > 0")
        key = key.strip().upper()
        now = datetime.datetime.now(datetime.timezone.utc)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT expires_at FROM licenses WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return None
            current = row["expires_at"]
            base = now
            if current:
                try:
                    expires = datetime.datetime.fromisoformat(current)
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=datetime.timezone.utc)
                    if expires > base:
                        base = expires
                except ValueError:
                    pass
            new_expires = (base + datetime.timedelta(days=31 * months)).isoformat()
            conn.execute(
                "UPDATE licenses SET expires_at = ?, status = 'active' WHERE key = ?",
                (new_expires, key),
            )
        return self.get_license(key)

    # -- consulta --------------------------------------------------------------

    def get_license(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM licenses WHERE key = ?", (key,)
            ).fetchone()
        return dict(row) if row else None

    def list_activations(self, key: str) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM activations WHERE key = ? ORDER BY activated_at",
                (key,),
            ).fetchall()
        return [dict(r) for r in rows]

    # -- ativação --------------------------------------------------------------

    def upsert_activation(self, key: str, device: str, device_name: str) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO activations (key, device, device_name, activated_at,"
                " last_seen) VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT (key, device) DO UPDATE SET last_seen = excluded.last_seen,"
                " device_name = excluded.device_name",
                (key, device, device_name, now, now),
            )

    def remove_activation(self, key: str, device: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM activations WHERE key = ? AND device = ?", (key, device)
            )
        return cur.rowcount > 0

    def revoke(self, key: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE licenses SET status = 'revoked' WHERE key = ?", (key,)
            )
        return cur.rowcount > 0

    # -- Stripe ----------------------------------------------------------------

    def link_subscription(
        self,
        subscription_id: str,
        license_key: str,
        plan: str,
        customer_id: Optional[str] = None,
    ) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO stripe_subscriptions"
                " (subscription_id, license_key, customer_id, plan, created_at)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT (subscription_id) DO UPDATE SET"
                " license_key = excluded.license_key,"
                " customer_id = excluded.customer_id,"
                " plan = excluded.plan",
                (
                    subscription_id,
                    license_key.strip().upper(),
                    customer_id,
                    plan,
                    now,
                ),
            )

    def get_key_by_subscription(self, subscription_id: str) -> Optional[str]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT license_key FROM stripe_subscriptions WHERE subscription_id = ?",
                (subscription_id,),
            ).fetchone()
        return row["license_key"] if row else None

    def get_key_by_customer(self, customer_id: str) -> Optional[str]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT license_key FROM stripe_subscriptions"
                " WHERE customer_id = ? ORDER BY created_at DESC LIMIT 1",
                (customer_id,),
            ).fetchone()
        return row["license_key"] if row else None

    def mark_event_processed(self, event_id: str) -> bool:
        """Registra event_id. Retorna True se era novo; False se já processado."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO stripe_events (event_id, processed_at) VALUES (?, ?)",
                    (event_id, now),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def event_seen(self, event_id: str) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM stripe_events WHERE event_id = ?", (event_id,)
            ).fetchone()
        return row is not None
