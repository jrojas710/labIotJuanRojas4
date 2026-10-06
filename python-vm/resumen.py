"""Resume los logs de evidencias/*.jsonl para llenar la tabla comparativa.

Uso: python resumen.py            -> tabla por protocolo (último log de cada uno)
     python resumen.py --all      -> todos los logs
"""
import json
import statistics
import sys
from pathlib import Path

from common import EVIDENCIAS


def pct(values, p):
    v = sorted(values)
    return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]


def summarize(path: Path):
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    ok = [r for r in rows if r.get("event") == "accepted" or (r.get("event") == "post" and r.get("status") == 204)]
    fails = [r for r in rows if r.get("event") in ("rejected", "released", "error", "transport_error")
             or (r.get("event") == "post" and r.get("status") != 204)]
    lat = [r["latency_ms"] for r in ok]
    hs = next((r["handshake_ms"] for r in rows if r.get("event") == "connection_opened"), None)
    out = {
        "log": path.name, "ok": len(ok), "fallos": len(fails),
        "payload_B": ok[0]["payload_bytes"] if ok else None,
        "lat_mediana_ms": round(statistics.median(lat), 1) if lat else None,
        "lat_p95_ms": round(pct(lat, 95), 1) if lat else None,
        "lat_min_ms": round(min(lat), 1) if lat else None,
        "lat_max_ms": round(max(lat), 1) if lat else None,
        "handshake_ms": hs,
    }
    hdr = [r["http_header_bytes"] for r in ok if "http_header_bytes" in r]
    if hdr:
        out["http_headers_B"] = round(statistics.mean(hdr))
    return out


def main():
    logs = sorted(EVIDENCIAS.glob("*.jsonl"))
    if not logs:
        sys.exit("No hay logs en evidencias/. Ejecuta primero device_amqp.py / device_https.py")
    if "--all" not in sys.argv:
        latest = {}
        for p in logs:
            latest[p.name.split("_")[0]] = p
        logs = list(latest.values())
    for p in logs:
        s = summarize(p)
        print(f"\n== {p.name.split('_')[0].upper()} ==")
        for k, v in s.items():
            print(f"  {k:<15} {v}")


if __name__ == "__main__":
    main()
