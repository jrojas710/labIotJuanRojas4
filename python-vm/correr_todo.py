"""Lab 4 en UN comando: instala, pide credenciales, corre AMQP + HTTPS y genera RESULTADOS.txt.

Uso (desde la carpeta python-vm):
    python3 correr_todo.py

Tarda ~4 minutos. Al final copia el contenido de evidencias/RESULTADOS.txt al chat.
"""
import getpass
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVID = HERE.parent / "evidencias"
PY = sys.executable


def paso(t):
    print(f"\n{'#' * 64}\n# {t}\n{'#' * 64}")


def run(args, env, out_file=None, err_file=None):
    so = open(out_file, "w", encoding="utf-8") if out_file else None
    se = open(err_file, "w", encoding="utf-8") if err_file else None
    try:
        if so:  # mostrar en pantalla y guardar a la vez
            p = subprocess.Popen(args, cwd=HERE, env=env, stdout=subprocess.PIPE, stderr=se or subprocess.STDOUT, text=True)
            for line in p.stdout:
                print(line, end="")
                so.write(line)
            return p.wait()
        return subprocess.call(args, cwd=HERE, env=env, stderr=se)
    finally:
        for f in (so, se):
            if f:
                f.close()


def main():
    EVID.mkdir(exist_ok=True)
    paso("1/6 Instalando dependencias")
    base = [PY, "-m", "pip", "install", "-q", "python-qpid-proton", "requests"]
    if subprocess.call(base) != 0:
        subprocess.call(base + ["--break-system-packages"])

    paso("2/6 Datos de la ventana 'Connect' de IoT Central (Devices > Vacuna-VM-Python > Connect)")
    env = dict(os.environ)
    if not env.get("IOTHUB_HOSTNAME") and not env.get("ID_SCOPE"):
        env["ID_SCOPE"] = input("  ID scope (empieza por 0ne...): ").strip()
    if not env.get("DEVICE_ID"):
        env["DEVICE_ID"] = input("  Device ID [Enter = Vacuna-VM-Python]: ").strip() or "Vacuna-VM-Python"
    if not env.get("DEVICE_KEY"):
        env["DEVICE_KEY"] = getpass.getpass("  Primary key (pégala; NO se ve al pegar, es normal) y Enter: ").strip()
    if not env.get("IOTHUB_HOSTNAME"):
        print("  Buscando el hub asignado al dispositivo (DPS)...")
        try:
            from provision import provision_hostname
            env["IOTHUB_HOSTNAME"] = provision_hostname(env["ID_SCOPE"], env["DEVICE_ID"], env["DEVICE_KEY"])
        except Exception as e:
            sys.exit(f"[!] No se pudo conectar con esos datos. Revisa ID scope / Device ID / Primary key.\n    Detalle: {e}")
        print(f"  [OK] Hub: {env['IOTHUB_HOSTNAME']}")

    paso("3/6 AMQP: 20 mensajes cada 5 s  (TOMA CAPTURA de esta terminal y del Raw data en Central)")
    run([PY, "device_amqp.py", "--count", "20", "--interval", "5"], env, EVID / "01_amqp_terminal.txt")

    paso("4/6 AMQP: traza de tramas (3 mensajes)")
    env_t = dict(env, PN_TRACE_FRM="1")
    run([PY, "device_amqp.py", "--count", "3", "--interval", "2"], env_t, None, EVID / "03_amqp_frames.txt")
    print(f"  -> guardado en {EVID / '03_amqp_frames.txt'}")

    paso("5/6 HTTPS: 20 mensajes con keep-alive + 10 sin keep-alive  (TOMA CAPTURA)")
    run([PY, "device_https.py", "--count", "20", "--interval", "5"], env, EVID / "04_https_terminal.txt")
    run([PY, "device_https.py", "--count", "10", "--interval", "5", "--no-keepalive"], env, EVID / "04b_https_nokeepalive.txt")

    paso("6/6 Resumen")
    resumen = subprocess.run([PY, "resumen.py", "--all"], cwd=HERE, env=env, capture_output=True, text=True).stdout
    frames = (EVID / "03_amqp_frames.txt").read_text(encoding="utf-8", errors="ignore").splitlines()
    flow = [l for l in frames if "@flow" in l][:2]
    disp = [l for l in frames if "@disposition" in l][:2]
    txt = (
        "===== RESULTADOS LAB 4 (pegar en el chat) =====\n"
        f"Hub: {env.get('IOTHUB_HOSTNAME', 'via DPS')}\n"
        + resumen
        + "\n--- Tramas AMQP (muestra) ---\n" + "\n".join(flow + disp)
        + "\n\n--- Primeras líneas AMQP ---\n"
        + "\n".join((EVID / "01_amqp_terminal.txt").read_text(encoding="utf-8").splitlines()[:12])
        + "\n\n--- Primeras líneas HTTPS ---\n"
        + "\n".join((EVID / "04_https_terminal.txt").read_text(encoding="utf-8").splitlines()[:10])
        + "\n"
    )
    (EVID / "RESULTADOS.txt").write_text(txt, encoding="utf-8")
    print(txt)
    print(f"Listo. Copia TODO lo de arriba (o el archivo {EVID / 'RESULTADOS.txt'}) y pégalo en el chat.")


if __name__ == "__main__":
    main()
