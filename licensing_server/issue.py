"""CLI de emissão de chaves de licença.

Exemplos:
  .venv/bin/python -m licensing_server.issue --email cliente@firma.com --plan pro
  .venv/bin/python -m licensing_server.issue --email x@y.com --plan team --devices 5 --months 12
  .venv/bin/python -m licensing_server.issue --email x@y.com --plan perpetual --devices 2
"""
from __future__ import annotations

import argparse

from licensing_server.db import LicenseDB

PLAN_DEFAULTS = {
    "pro": {"devices": 2, "months": 12},
    "team": {"devices": 5, "months": 12},
    "perpetual": {"devices": 2, "months": None},
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Emite uma chave de licença.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--plan", choices=sorted(PLAN_DEFAULTS), default="pro")
    parser.add_argument("--devices", type=int, default=None,
                        help="limite de dispositivos (default do plano)")
    parser.add_argument("--months", type=int, default=None,
                        help="validade em meses (default do plano; perpetual ignora)")
    args = parser.parse_args()

    defaults = PLAN_DEFAULTS[args.plan]
    devices = args.devices if args.devices is not None else defaults["devices"]
    months = defaults["months"] if args.months is None else args.months
    if args.plan == "perpetual":
        months = None

    lic = LicenseDB().issue(
        email=args.email, plan=args.plan, max_devices=devices, months=months
    )
    print("Chave emitida:")
    print("  Chave:        %s" % lic["key"])
    print("  E-mail:       %s" % lic["email"])
    print("  Plano:        %s" % lic["plan"])
    print("  Dispositivos: %s" % lic["max_devices"])
    print("  Expira em:    %s" % (lic["expires_at"] or "nunca (perpétua)"))


if __name__ == "__main__":
    main()
