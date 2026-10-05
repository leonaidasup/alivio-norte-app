"""Envío de WhatsApp con reintentos y cola de fallos. Es un paso explícito: nada sale sin ejecutarlo."""
import json
import logging
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone

from . import database as store

log = logging.getLogger("alivio.whatsapp")

RUNTIME = store.ROOT / "runtime"
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = [60, 300]   # espera tras el 1.er y el 2.º fallo


class GatewayError(Exception):
    """El servicio de mensajería no pudo recibir el mensaje."""


class SimulatedGateway:
    """Gateway falso para la demo. Escribe en runtime/whatsapp_sent.jsonl.
    Si existe el archivo runtime/gateway_down, simula que el servicio está caído."""

    def send(self, phone, body):
        if (RUNTIME / "gateway_down").exists():
            raise GatewayError("gateway caído (simulado)")
        RUNTIME.mkdir(parents=True, exist_ok=True)
        with open(RUNTIME / "whatsapp_sent.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": store.now(), "phone": phone, "body": body}, ensure_ascii=False) + "\n")


class HttpGateway:
    """Gateway real: POST JSON {to, text} a la URL indicada en WHATSAPP_URL."""

    def __init__(self, url, token=""):
        self.url, self.token = url, token

    def send(self, phone, body):
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.url, data=json.dumps({"to": phone, "text": body}).encode(),
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status >= 300:
                    raise GatewayError(f"HTTP {resp.status}")
        except OSError as e:   # sin conexión, timeout, HTTP 4xx/5xx
            raise GatewayError(str(e)) from e


def get_gateway():
    url = os.environ.get("WHATSAPP_URL")
    return HttpGateway(url, os.environ.get("WHATSAPP_TOKEN", "")) if url else SimulatedGateway()


def clean_phone(raw) -> str:
    """Solo dígitos; válido si tiene entre 10 y 15. Si no, texto vacío."""
    digits = re.sub(r"\D", "", raw or "")
    return digits if 10 <= len(digits) <= 15 else ""


def _no_phone(database, row, stats):
    with database.tx() as c:
        store.outbox_mark(c, row["id"], "fallido", "sin_telefono")
        store.add_failure(c, row["lead_id"], "sin_telefono",
                          f"WhatsApp #{row['id']} ({row['disposition']}): el lead no tiene teléfono válido", row["id"])
        store.add_audit(c, row["lead_id"], "sistema", "whatsapp_fallido", detail="sin teléfono")
    stats["fallidos"] += 1


def _gateway_failed(database, row, error, stats):
    """Reintenta con espera creciente; al tercer fallo pasa a la cola de fallos."""
    wait = BACKOFF_SECONDS[min(row["attempts"], len(BACKOFF_SECONDS) - 1)]
    next_at = (datetime.now(timezone.utc) + timedelta(seconds=wait)).isoformat(timespec="seconds")
    with database.tx() as c:
        attempts = store.outbox_attempt_failed(c, row["id"], error, next_at)
        if attempts >= MAX_ATTEMPTS:
            store.outbox_mark(c, row["id"], "fallido", error)
            store.add_failure(c, row["lead_id"], "gateway_caido",
                              f"WhatsApp #{row['id']}: {error} (tras {attempts} intentos)", row["id"])
            store.add_audit(c, row["lead_id"], "sistema", "whatsapp_fallido", detail=f"{attempts} intentos: {error}")
            stats["fallidos"] += 1
        else:
            store.add_audit(c, row["lead_id"], "sistema", "whatsapp_reintento_programado",
                            detail=f"intento {attempts}/{MAX_ATTEMPTS}: {error}")
            stats["reintentos"] += 1


def process_outbox(database, gateway=None, limit=50, ignore_wait=False) -> dict:
    """Envía los WhatsApp pendientes. ignore_wait=True salta la espera entre reintentos."""
    gateway = gateway or get_gateway()
    stats = {"enviados": 0, "reintentos": 0, "fallidos": 0}
    with database.tx() as c:
        rows = [dict(r) for r in store.due_outbox(c, limit, ignore_wait)]
    for row in rows:
        with database.tx() as c:
            lead = store.get_lead(c, row["lead_id"])
        # el teléfono pudo llegar después de preparar el mensaje: se usa el más reciente
        phone = clean_phone(row["phone"]) or clean_phone(lead["phone"] if lead else "")
        if not phone:
            _no_phone(database, row, stats)
            continue
        try:
            gateway.send(phone, row["body"])
        except Exception as e:   # cualquier fallo del gateway se trata igual
            log.warning("WhatsApp #%s falló: %s", row["id"], e)
            _gateway_failed(database, row, e, stats)
            continue
        with database.tx() as c:
            store.outbox_sent(c, row["id"], phone)
            store.add_audit(c, row["lead_id"], "sistema", "whatsapp_enviado", detail=row["disposition"])
        stats["enviados"] += 1
    return stats