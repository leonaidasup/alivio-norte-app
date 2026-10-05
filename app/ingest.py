"""Ingesta: redacta datos sensibles y mete el mensaje a la cola (webhook o CSV)."""
import csv
import hashlib
import json
import os
import re
from http.server import BaseHTTPRequestHandler

from . import database as store

SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD = re.compile(r"\b(?:\d{4}[ -]){3}\d{4}\b|\b\d{16}\b")
MAX_BODY = 10_000   # bytes


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def redact(text: str) -> str:
    """Quita SSN y números de tarjeta ANTES de guardar. Deja una palabra clave ("ssn",
    "numero de tarjeta") para que el clasificador siga detectando el riesgo."""
    text = SSN.sub("ssn [dato redactado]", text)

    def card(m):
        digits = re.sub(r"\D", "", m.group())
        return "numero de tarjeta [dato redactado]" if _luhn(digits) else m.group()

    return CARD.sub(card, text)


def ingest(database, lead_id, text, *, external_id=None, received_at=None,
           creator="", channel="", phone="") -> bool:
    """True si es nuevo, False si es duplicado. ValueError si faltan lead_id o texto."""
    lead_id, text = str(lead_id or "").strip(), str(text or "").strip()
    if not lead_id or not text:
        raise ValueError("lead_id y text son obligatorios")
    clean = redact(text)
    received_at = received_at or store.now()
    external_id = str(external_id) if external_id else \
        hashlib.sha1(f"{lead_id}|{received_at}|{clean}".encode()).hexdigest()[:16]
    with database.tx() as c:
        return store.enqueue(c, external_id, lead_id, clean, received_at, creator, channel, phone)


def _read_rows(path) -> list:
    """Lee leads desde .json (lista de objetos) o .csv."""
    if str(path).lower().endswith(".json"):
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("el JSON debe ser una lista de leads")
        return data
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def import_leads(database, path):
    """Carga leads desde JSON o CSV (id, timestamp, creador, canal, mensaje, telefono o telefono_ficticio).
    Devuelve (nuevos, duplicados, omitidos)."""
    new = dup = skipped = 0
    for row in _read_rows(path):
        lead_id, ts = str(row.get("id") or ""), str(row.get("timestamp") or "")
        phone = row.get("telefono") or row.get("telefono_ficticio") or ""
        try:
            ok = ingest(database, lead_id, row.get("mensaje"),
                        external_id=f"file:{lead_id}:{ts}", received_at=ts or None,
                        creator=row.get("creador") or "", channel=row.get("canal") or "", phone=phone)
        except ValueError:
            skipped += 1
            continue
        if ok:
            new += 1
        else:
            dup += 1
    return new, dup, skipped

def make_handler(database):
    """Webhook: POST /webhook con JSON {lead_id, text, message_id?, timestamp?, creator?, channel?, phone?}."""
    token = os.environ.get("WEBHOOK_TOKEN")   # opcional: si existe, se exige en el header X-Webhook-Token

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                return self._send(200, {"status": "ok"})
            self._send(404, {"error": "no encontrado"})

        def do_POST(self):
            if self.path != "/webhook":
                return self._send(404, {"error": "no encontrado"})
            if token and self.headers.get("X-Webhook-Token") != token:
                return self._send(401, {"error": "token inválido"})
            try:
                length = int(self.headers.get("Content-Length", 0))
            except ValueError:
                length = 0
            if not 0 < length <= MAX_BODY:
                return self._send(400, {"error": "cuerpo vacío o demasiado grande"})
            try:
                d = json.loads(self.rfile.read(length))
                new = ingest(database, d["lead_id"], d["text"], external_id=d.get("message_id"),
                             received_at=d.get("timestamp"), creator=d.get("creator", ""),
                             channel=d.get("channel", ""), phone=d.get("phone", ""))
            except (ValueError, KeyError, TypeError):
                return self._send(400, {"error": "se requiere JSON con lead_id y text"})
            self._send(202, {"status": "encolado" if new else "duplicado"})

        def log_message(self, *args):   # sin ruido en consola
            pass

    return Handler