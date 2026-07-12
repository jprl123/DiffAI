"""Identificação estável do dispositivo (vinculação de licença).

Preferência: UUID de hardware do sistema (IOPlatformUUID no macOS,
/etc/machine-id no Linux). Fallback: UUID gerado uma vez e guardado em
``~/.comparedocs/device_id``. O valor exposto é um hash — o identificador
bruto da máquina nunca sai do dispositivo.
"""
from __future__ import annotations

import hashlib
import os
import platform
import re
import subprocess
import uuid
from typing import Optional

_FALLBACK_PATH = os.path.join(os.path.expanduser("~"), ".comparedocs", "device_id")


def _hardware_uuid() -> Optional[str]:
    try:
        if platform.system() == "Darwin":
            out = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5,
            ).stdout
            match = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out)
            if match:
                return match.group(1)
        elif platform.system() == "Linux":
            for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                if os.path.isfile(path):
                    with open(path, "r", encoding="ascii") as fh:
                        value = fh.read().strip()
                    if value:
                        return value
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _fallback_uuid() -> str:
    try:
        with open(_FALLBACK_PATH, "r", encoding="ascii") as fh:
            value = fh.read().strip()
        if value:
            return value
    except OSError:
        pass
    value = uuid.uuid4().hex
    try:
        os.makedirs(os.path.dirname(_FALLBACK_PATH), exist_ok=True)
        with open(_FALLBACK_PATH, "w", encoding="ascii") as fh:
            fh.write(value)
    except OSError:
        pass
    return value


def device_fingerprint() -> str:
    raw = _hardware_uuid() or _fallback_uuid()
    return hashlib.sha256(("comparedocs:" + raw).encode("utf-8")).hexdigest()[:32]


def device_name() -> str:
    return "%s (%s)" % (platform.node() or "dispositivo", platform.system())
