# Laboratorio 4: AMQP + HTTPS vs MQTT hacia Azure IoT Central

**Estudiante:** Juan Camilo Rojas Guerrero
**Materia:** IoT + Cloud + Sistemas Distribuidos — Universidad Autónoma de Bucaramanga (UNAB)
**Plantilla:** `ContenedorVacunas` · variables `temperatura`, `humedad`, `nivel_bateria`
**Baseline:** Lab 3 (MQTT explícito con paho-mqtt + SDK + Wokwi ESP32) → https://github.com/jrojas710/labIotJuanRojas3

## Forma rápida (un comando)

```bash
cd python-vm
python3 correr_todo.py
```

Pide hostname, device ID y primary key; corre AMQP (20 msgs), la traza de tramas, HTTPS (con y sin keep-alive)
y deja todo en `evidencias/`, incluido `RESULTADOS.txt` con las latencias para la tabla.

## Contenido

```
labIotJuanRojas4/
├── README.md
├── evidencias/                 # logs .jsonl generados automáticamente + capturas
└── python-vm/
    ├── common.py               # credenciales por env, SAS token, sensor simulado, logger
    ├── device_amqp.py          # Etapa 1: AMQP 1.0 (Qpid Proton) -> IoT Central, puerto 5671
    ├── device_https.py         # Etapa 2: tercer protocolo, HTTPS REST -> IoT Central, puerto 443
    ├── provision.py            # (opcional) obtiene el hostname del hub vía DPS por HTTPS
    ├── resumen.py              # mediana / p95 de latencia por protocolo para la tabla comparativa
    └── requirements.txt
```

## Por qué AMQP no usa `azure-iot-device`

El SDK de dispositivo de Python **solo implementa MQTT y MQTT sobre WebSockets**; la documentación de IoT Hub
indica explícitamente que AMQP no está soportado en el SDK de Python (en C#, Java y Node sí existe
`TransportType.Amqp` / `Amqp_WebSocket_Only`). Por eso el cliente AMQP se escribió directamente sobre
**Apache Qpid Proton**, igual que en el Lab 3 se hizo MQTT a mano con paho-mqtt:

| Paso | Valor |
|---|---|
| Transporte | `amqps://{hub}:5671` (TLS 1.2) |
| Autenticación | SASL PLAIN · usuario `{deviceId}@sas.{hubName}` · contraseña = SAS token del dispositivo |
| Link (sender) | `/devices/{deviceId}/messages/events` |
| Propiedades | `content_type=application/json`, `content_encoding=utf-8` (sin ellas Central no decodifica el JSON) |
| Confirmación | `Disposition: accepted` por cada mensaje (equivale al PUBACK de MQTT QoS 1) |

> Qpid Proton no implementa AMQP sobre WebSockets. Si el 5671 está bloqueado en la red de la VM, el
> fallback AMQP_WS (443) requiere el SDK de C#/Java/Node; documentarlo en el informe.

## Instalación

```bash
cd python-vm
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Credenciales (variables de entorno, nunca en el repo)

```bash
export IOTHUB_HOSTNAME="iotc-xxxxxxxx-xxxx.azure-devices.net"   # el mismo host del Lab 3
export DEVICE_ID="Vacuna-VM-Python"
export DEVICE_KEY="<clave primaria del dispositivo>"
# Alternativa si no tienes el hostname: export ID_SCOPE="0ne00XXXXXX" (se resuelve por DPS)
```

En IoT Central: **Devices → Vacuna-VM-Python → Connect** muestra ID scope, Device ID y Primary key.

## Ejecución

```bash
# Etapa 1 — AMQP (20 mensajes cada 5 s)
python device_amqp.py --count 20 --interval 5

# Ver las tramas AMQP (Open/Begin/Attach/Flow/Transfer/Disposition) para el informe
PN_TRACE_FRM=1 python device_amqp.py --count 3 --interval 2 2> ../evidencias/03_amqp_frames.txt

# Etapa 2 — HTTPS REST
python device_https.py --count 20 --interval 5
python device_https.py --count 10 --interval 5 --no-keepalive   # TLS nuevo por mensaje

# Etapa 3 — números para la tabla comparativa
python resumen.py
```

Cada ejecución deja un `evidencias/<protocolo>_<fecha>.jsonl` con latencia, tamaño de payload y estado por mensaje.

## Verificación en IoT Central

**Devices → ContenedorVacunas → Vacuna-VM-Python → Raw data**: deben aparecer las tres columnas
(Temperatura, Humedad, Nivel de Batería) con timestamps a ~5 s, tanto en la corrida AMQP como en la HTTPS.
Con HTTPS el dispositivo puede figurar como *Disconnected* aunque los datos llegan: no hay conexión persistente.

## Evidencias esperadas en `/evidencias`

| Archivo | Qué muestra |
|---|---|
| `01_amqp_terminal.png` | salida de `device_amqp.py` con `Disposition: ACCEPTED` |
| `02_amqp_raw_data.png` | Raw data de Central con las 3 variables durante la corrida AMQP |
| `03_amqp_frames.txt` | traza `PN_TRACE_FRM` (crédito y disposiciones) |
| `04_https_terminal.png` | salida de `device_https.py` con `HTTP 204` |
| `05_https_raw_data.png` | Raw data de Central durante la corrida HTTPS |
| `amqp_*.jsonl`, `https_*.jsonl` | logs crudos usados en la tabla |
