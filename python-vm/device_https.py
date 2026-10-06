"""Lab 4 · Etapa 2 — Tercer protocolo: HTTPS (REST) hacia Azure IoT Central (IoT Hub).

Justificación de negocio (cadena de frío):
  Los registradores de temperatura de los contenedores de vacunas pasan la mayor
  parte del viaje sin cobertura y, al llegar a una bodega/IPS, descargan lo
  acumulado a través de la red corporativa, que normalmente SOLO deja salir
  tráfico HTTPS por el 443 y a menudo con proxy. Un POST REST sin conexión
  persistente encaja con ese patrón "conectar-descargar-desconectar" y además
  es el único de los tres protocolos que se depura con curl/Postman.

Endpoint (sin SDK, solo requests):
  POST https://{hub}/devices/{id}/messages/events?api-version=2021-04-12
  Authorization: SharedAccessSignature ...   -> 204 No Content = aceptado

Uso:
  python device_https.py --count 20 --interval 5
"""
import argparse
import time

import requests

from common import (ColdChainSensor, RunLogger, banner, generate_sas_token,
                    load_credentials, new_message_id, to_payload)

API_VERSION = "2021-04-12"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=20)
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--no-keepalive", action="store_true",
                    help="abre una conexión TLS nueva por mensaje (patrón de dispositivo real sin sesión)")
    args = ap.parse_args()

    host, device_id, key = load_credentials()
    url = f"https://{host}/devices/{device_id}/messages/events?api-version={API_VERSION}"
    token = generate_sas_token(f"{host}/devices/{device_id}", key)
    banner("Cliente HTTPS REST -> Azure IoT Central", {
        "Endpoint": f"POST {url.split('?')[0]}",
        "Puerto": "443 (TLS)",
        "Keep-alive": "NO (TLS por mensaje)" if args.no_keepalive else "sí (requests.Session)",
        "Mensajes": f"{args.count} cada {args.interval}s",
    })

    logger = RunLogger("https")
    sensor = ColdChainSensor()
    session = requests.Session()
    ok = 0
    for n in range(1, args.count + 1):
        data = sensor.read()
        body = to_payload(data)
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "iothub-contenttype": "application/json",
            "iothub-contentencoding": "utf-8",
            "iothub-messageid": new_message_id(),
        }
        client = requests if args.no_keepalive else session
        t0 = time.perf_counter()
        try:
            r = client.post(url, data=body, headers=headers, timeout=15)
            lat = (time.perf_counter() - t0) * 1000
            # bytes de cabeceras HTTP de la petición (aprox.) para comparar overhead
            req_hdr = sum(len(k) + len(v) + 4 for k, v in r.request.headers.items()) + len(r.request.path_url) + 20
            status = r.status_code
            if status == 204:
                ok += 1
            print(f"[Msg #{n:02d}] {data} | Payload: {len(body)} B | Headers HTTP: ~{req_hdr} B "
                  f"| HTTP {status} | Latencia: {lat:.2f} ms")
            logger.log(event="post", n=n, status=status, payload_bytes=len(body),
                       http_header_bytes=req_hdr, latency_ms=round(lat, 2), data=data,
                       error=None if status == 204 else r.text[:300])
        except requests.RequestException as e:
            print(f"[!] Msg #{n} falló: {e}")
            logger.log(event="error", n=n, error=str(e))
        if n < args.count:
            time.sleep(args.interval)

    print(f"[*] Fin. Aceptados (204) = {ok}/{args.count}. Log: {logger.path}")
    logger.close()


if __name__ == "__main__":
    main()
