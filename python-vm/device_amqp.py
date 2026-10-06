"""Lab 4 · Etapa 1 — Telemetría AMQP 1.0 hacia Azure IoT Central (IoT Hub).

Por qué no se usa azure-iot-device:
  El SDK de Python para dispositivos SOLO soporta MQTT y MQTT sobre WebSockets
  ("AMQP isn't supported in the Python SDK" — docs de IoT Hub). Por eso el
  cliente AMQP se implementa con Apache Qpid Proton (python-qpid-proton),
  igual que en el Lab 3 se hizo MQTT "a mano" con paho-mqtt.

Flujo AMQP 1.0 (lo que se ve en el log):
  TCP 5671 -> TLS -> SASL PLAIN (user={device}@sas.{hub}, pass=SAS token)
  -> Open (conexión) -> Begin (sesión) -> Attach (link sender a
  /devices/{id}/messages/events) -> Flow (el hub concede CRÉDITO) -> Transfer
  -> Disposition(accepted)  <== confirmación por mensaje (equivale al PUBACK)

Uso:
  python device_amqp.py --count 20 --interval 5
"""
import argparse
import time

from proton import Message, symbol
from proton.handlers import MessagingHandler
from proton.reactor import Container

from common import (ColdChainSensor, RunLogger, banner, generate_sas_token,
                    load_credentials, new_message_id, to_payload)

AMQPS_PORT = 5671


class AmqpTelemetrySender(MessagingHandler):
    def __init__(self, host, device_id, key, count, interval):
        super().__init__(auto_settle=True)
        self.host, self.device_id, self.key = host, device_id, key
        self.count, self.interval = count, interval
        self.sensor = ColdChainSensor()
        self.logger = RunLogger("amqp")
        self.sent = self.confirmed = 0
        self.inflight = {}  # delivery -> (n, t0, size, body)
        self.sender = None
        self.t_connect = None

    # ---- ciclo de vida AMQP ---------------------------------------------
    def on_start(self, event):
        hub_name = self.host.split(".")[0]
        resource = f"{self.host}/devices/{self.device_id}"
        user = f"{self.device_id}@sas.{hub_name}"
        banner("Cliente AMQP 1.0 (Qpid Proton) -> Azure IoT Central", {
            "Host": f"{self.host}:{AMQPS_PORT} (amqps / TLS)",
            "SASL": f"PLAIN  user={user}",
            "Link target": f"/devices/{self.device_id}/messages/events",
            "Mensajes": f"{self.count} cada {self.interval}s",
        })
        self.t_connect = time.perf_counter()
        conn = event.container.connect(
            url=f"amqps://{self.host}:{AMQPS_PORT}",
            user=user,
            password=generate_sas_token(resource, self.key),
            allowed_mechs="PLAIN",
            sasl_enabled=True,
        )
        self.sender = event.container.create_sender(conn, f"/devices/{self.device_id}/messages/events")

    def on_connection_opened(self, event):
        ms = (time.perf_counter() - self.t_connect) * 1000
        print(f"[+] Conexión AMQP abierta (TCP+TLS+SASL+Open) en {ms:.1f} ms")
        self.logger.log(event="connection_opened", handshake_ms=round(ms, 2))

    def on_link_opened(self, event):
        if event.link.is_sender:
            print(f"[+] Link sender adjuntado: {event.link.target.address}")

    def on_sendable(self, event):
        # Proton llama aquí cuando el hub concedió crédito (flow control).
        if self.sent == 0:
            print(f"[+] Crédito concedido por el hub: {event.sender.credit} mensajes")
            self.logger.log(event="credit", credit=event.sender.credit)
            self._send(event.sender)

    def _send(self, sender):
        if self.sent >= self.count or sender.credit <= 0:
            return
        data = self.sensor.read()
        body = to_payload(data)
        msg = Message(
            id=new_message_id(),
            body=body,
            inferred=True,  # body como binario (data section), no como string AMQP
            content_type=symbol("application/json"),
            content_encoding=symbol("utf-8"),  # IoT Central lo necesita para decodificar el JSON
        )
        self.sent += 1
        t0 = time.perf_counter()
        dlv = sender.send(msg)
        self.inflight[dlv] = (self.sent, t0, len(body), data)

    def on_accepted(self, event):
        n, t0, size, data = self.inflight.pop(event.delivery)
        lat = (time.perf_counter() - t0) * 1000
        self.confirmed += 1
        print(f"[Msg #{n:02d}] {data} | Payload: {size} B | Disposition: ACCEPTED | Latencia: {lat:.2f} ms")
        self.logger.log(event="accepted", n=n, payload_bytes=size, latency_ms=round(lat, 2), data=data)
        self._next(event)

    def on_rejected(self, event):
        n, *_ = self.inflight.pop(event.delivery)
        cond = event.delivery.remote.condition
        print(f"[!] Msg #{n} RECHAZADO por el hub: {cond}")
        self.logger.log(event="rejected", n=n, condition=str(cond))
        self._next(event)

    def on_released(self, event):
        n, *_ = self.inflight.pop(event.delivery, (None,))
        print(f"[!] Msg #{n} RELEASED (el hub no lo procesó)")
        self.logger.log(event="released", n=n)
        self._next(event)

    def _next(self, event):
        if self.sent >= self.count:
            event.connection.close()
            return
        event.container.schedule(self.interval, self)  # -> on_timer_task

    def on_timer_task(self, event):
        self._send(self.sender)

    def on_transport_error(self, event):
        cond = event.transport.condition
        print(f"[!] Error de transporte: {cond}")
        self.logger.log(event="transport_error", condition=str(cond))

    def on_connection_closed(self, event):
        print(f"[*] Conexión cerrada. Enviados={self.sent} Confirmados={self.confirmed}")
        print(f"[*] Log: {self.logger.path}")
        self.logger.log(event="closed", sent=self.sent, confirmed=self.confirmed)
        self.logger.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=20)
    ap.add_argument("--interval", type=float, default=5.0)
    args = ap.parse_args()
    host, device_id, key = load_credentials()
    Container(AmqpTelemetrySender(host, device_id, key, args.count, args.interval)).run()


if __name__ == "__main__":
    main()
