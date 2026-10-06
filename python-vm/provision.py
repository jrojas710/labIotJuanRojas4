"""Resuelve el hostname del IoT Hub que IoT Central asignó al dispositivo, vía DPS por HTTPS.

Solo hace falta si no tienes IOTHUB_HOSTNAME (en el Lab 3 ya se obtuvo:
iotc-....azure-devices.net). Uso directo: python provision.py  -> imprime el hostname.
Requiere ID_SCOPE, DEVICE_ID, DEVICE_KEY en el entorno.
"""
import os
import time

import requests

from common import generate_sas_token

DPS = "https://global.azure-devices-provisioning.net"
API = "2021-06-01"


def provision_hostname(id_scope: str, device_id: str, key: str) -> str:
    token = generate_sas_token(f"{id_scope}/registrations/{device_id}", key, key_name="registration")
    h = {"Authorization": token, "Content-Type": "application/json"}
    base = f"{DPS}/{id_scope}/registrations/{device_id}"
    r = requests.put(f"{base}/register?api-version={API}", json={"registrationId": device_id}, headers=h, timeout=20)
    r.raise_for_status()
    op = r.json()
    while op.get("status") == "assigning":
        time.sleep(2)
        r = requests.get(f"{base}/operations/{op['operationId']}?api-version={API}", headers=h, timeout=20)
        r.raise_for_status()
        op = r.json()
    state = op.get("registrationState", {})
    if op.get("status") != "assigned":
        raise RuntimeError(f"DPS no asignó el dispositivo: {op}")
    return state["assignedHub"]


if __name__ == "__main__":
    print(provision_hostname(os.environ["ID_SCOPE"], os.environ["DEVICE_ID"], os.environ["DEVICE_KEY"]))
