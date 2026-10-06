"""Utilidades compartidas Lab 4: credenciales, SAS token, telemetría y logging.

Las credenciales SIEMPRE vienen de variables de entorno (nunca en el repo):
  IOTHUB_HOSTNAME   iotc-xxxxxxxx.azure-devices.net (el hub asignado por IoT Central/DPS)
  DEVICE_ID         Vacuna-VM-Python
  DEVICE_KEY        clave primaria del dispositivo (base64)
Opcional (si no conoces el hostname): ID_SCOPE -> se resuelve con DPS (ver provision.py).
"""
import base64
import hashlib
import hmac
import json
import os
import random
import sys
import time
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path

EVIDENCIAS = Path(__file__).resolve().parent.parent / "evidencias"


def load_credentials():
    host = os.getenv("IOTHUB_HOSTNAME")
    device_id = os.getenv("DEVICE_ID")
    key = os.getenv("DEVICE_KEY")
    if not host and os.getenv("ID_SCOPE") and device_id and key:
        from provision import provision_hostname
        host = provision_hostname(os.environ["ID_SCOPE"], device_id, key)
    missing = [n for n, v in (("IOTHUB_HOSTNAME", host), ("DEVICE_ID", device_id), ("DEVICE_KEY", key)) if not v]
    if missing:
        sys.exit(f"[!] Faltan variables de entorno: {', '.join(missing)}")
    return host, device_id, key


def generate_sas_token(resource_uri: str, key_b64: str, ttl_s: int = 3600, key_name: str = None) -> str:
    """SAS token RFC 2104 HMAC-SHA256 (mismo algoritmo del Lab 3)."""
    expiry = int(time.time()) + ttl_s
    encoded_uri = urllib.parse.quote(resource_uri, safe="")
    to_sign = f"{encoded_uri}\n{expiry}".encode("utf-8")
    sig = base64.b64encode(hmac.new(base64.b64decode(key_b64), to_sign, hashlib.sha256).digest())
    return (
        f"SharedAccessSignature sr={encoded_uri}"
        f"&sig={urllib.parse.quote(sig.decode(), safe='')}&se={expiry}"
    ) + (f"&skn={key_name}" if key_name else "")


class ColdChainSensor:
    """Simula las 3 variables de la plantilla ContenedorVacunas (cadena de frío 2-8 °C)."""

    def __init__(self):
        self.temperatura = 4.2
        self.humedad = 52.0
        self.nivel_bateria = 97.0

    def read(self) -> dict:
        self.temperatura = round(min(8.0, max(2.0, self.temperatura + random.uniform(-0.15, 0.15))), 2)
        self.humedad = round(min(70.0, max(40.0, self.humedad + random.uniform(-0.3, 0.3))), 2)
        self.nivel_bateria = round(max(0.0, self.nivel_bateria - 0.05), 2)
        return {"temperatura": self.temperatura, "humedad": self.humedad, "nivel_bateria": self.nivel_bateria}


def new_message_id() -> str:
    return str(uuid.uuid4())


def to_payload(data: dict) -> bytes:
    return json.dumps(data, separators=(",", ":")).encode("utf-8")


class RunLogger:
    """Escribe cada envío como una línea JSON en evidencias/<protocolo>_<fecha>.jsonl."""

    def __init__(self, protocol: str):
        EVIDENCIAS.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = EVIDENCIAS / f"{protocol}_{stamp}.jsonl"
        self.protocol = protocol
        self._fh = self.path.open("a", encoding="utf-8")

    def log(self, **fields):
        fields = {"ts": datetime.now(timezone.utc).isoformat(), "protocol": self.protocol, **fields}
        self._fh.write(json.dumps(fields, ensure_ascii=False) + "\n")
        self._fh.flush()

    def close(self):
        self._fh.close()


def banner(title: str, rows: dict):
    line = "=" * 64
    print(line)
    print(f"[*] {title}")
    for k, v in rows.items():
        print(f"[*] {k:<14}: {v}")
    print(line)
