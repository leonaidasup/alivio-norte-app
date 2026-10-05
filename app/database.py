import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = ROOT / "db" / "schema.sql"
DEFAULT_DB = Path(os.environ.get("ALIVIO_DB", ROOT / "runtime" / "alivio.db"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DB:
    """Abre una conexión por operación, así el webhook y el worker pueden usarla a la vez."""

    def __init__(self, path=DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.tx() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))

    @contextmanager
    def tx(self):
        """Todo lo que se haga dentro se guarda junto, o no se guarda nada si algo falla."""
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


# ---- mensajes (la cola) ----
def enqueue(c, external_id, lead_id, text, received_at=None, creator="", channel="", phone="") -> bool:
    """True si es nuevo, False si ya existía (duplicado)."""
    cur = c.execute(
        "INSERT OR IGNORE INTO messages(external_id, lead_id, received_at, creator, channel, phone, text) "
        "VALUES (?,?,?,?,?,?,?)",
        (external_id, lead_id, received_at or now(), creator, channel, phone, text))
    return cur.rowcount == 1


def pending(c, limit=50, max_attempts=3):
    return c.execute(
        "SELECT * FROM messages WHERE status IN ('nuevo','error') AND attempts < ? ORDER BY id LIMIT ?",
        (max_attempts, limit)).fetchall()


def mark_processed(c, message_id):
    c.execute("UPDATE messages SET status='procesado', last_error='' WHERE id=?", (message_id,))


def mark_error(c, message_id, error) -> int:
    """Suma un intento fallido y devuelve cuántos lleva."""
    c.execute("UPDATE messages SET status='error', attempts=attempts+1, last_error=? WHERE id=?",
              (str(error)[:500], message_id))
    return c.execute("SELECT attempts FROM messages WHERE id=?", (message_id,)).fetchone()["attempts"]


def mark_escalated_by_error(c, message_id):
    c.execute("UPDATE messages SET status='escalado_por_error' WHERE id=?", (message_id,))


# ---- resultados ----
def add_decision(c, message_id, lead_id, decision, reason, explanation, rules_version, payload_json):
    c.execute(
        "INSERT INTO decisions(message_id, lead_id, decided_at, decision, reason, explanation, rules_version, payload) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (message_id, lead_id, now(), decision, reason, explanation, rules_version, payload_json))


def add_draft(c, message_id, lead_id, body) -> int:
    cur = c.execute("INSERT INTO drafts(message_id, lead_id, body, created_at) VALUES (?,?,?,?)",
                    (message_id, lead_id, body, now()))
    return cur.lastrowid


def set_draft_path(c, draft_id, path):
    c.execute("UPDATE drafts SET path=? WHERE id=?", (str(path), draft_id))


def add_handoff(c, message_id, lead_id, reason, summary) -> int:
    cur = c.execute("INSERT INTO handoffs(message_id, lead_id, reason, summary, created_at) VALUES (?,?,?,?,?)",
                    (message_id, lead_id, reason, summary, now()))
    return cur.lastrowid


# ---- no contactar ----
def mark_dnc(c, lead_id):
    c.execute("INSERT OR IGNORE INTO do_not_contact(lead_id, since) VALUES (?,?)", (lead_id, now()))


def is_dnc(c, lead_id) -> bool:
    return c.execute("SELECT 1 FROM do_not_contact WHERE lead_id=?", (lead_id,)).fetchone() is not None


def enqueue(c, external_id, lead_id, text, received_at=None, creator="", channel="", phone="") -> bool:
    """True si es nuevo, False si ya existía (duplicado). También crea o actualiza el lead."""
    cur = c.execute(
        "INSERT OR IGNORE INTO messages(external_id, lead_id, received_at, creator, channel, phone, text) "
        "VALUES (?,?,?,?,?,?,?)",
        (external_id, lead_id, received_at or now(), creator, channel, phone, text))
    c.execute(
        "INSERT INTO leads(lead_id, phone, stage, stage_changed_at, created_at) VALUES (?,?,'nuevo',?,?) "
        "ON CONFLICT(lead_id) DO UPDATE SET phone = CASE WHEN excluded.phone <> '' "
        "THEN excluded.phone ELSE leads.phone END",
        (lead_id, phone, now(), now()))
    return cur.rowcount == 1

# ---- leads, audit trail, outbox y fallos (Ejercicio B) ----
def get_lead(c, lead_id):
    return c.execute("SELECT * FROM leads WHERE lead_id=?", (lead_id,)).fetchone()


def set_stage(c, lead_id, stage):
    c.execute("UPDATE leads SET stage=?, stage_changed_at=? WHERE lead_id=?", (stage, now(), lead_id))


def add_audit(c, lead_id, actor, action, from_stage="", to_stage="", detail=""):
    c.execute(
        "INSERT INTO audit_trail(at, lead_id, actor, action, from_stage, to_stage, detail) VALUES (?,?,?,?,?,?,?)",
        (now(), lead_id, actor, action, from_stage, to_stage, detail))


def add_outbox(c, lead_id, phone, body, disposition) -> int:
    cur = c.execute(
        "INSERT INTO outbox(lead_id, phone, body, disposition, next_attempt_at, created_at) VALUES (?,?,?,?,?,?)",
        (lead_id, phone, body, disposition, now(), now()))
    return cur.lastrowid


def add_failure(c, lead_id, kind, detail, outbox_id=None):
    c.execute("INSERT INTO failures(at, lead_id, kind, detail, outbox_id) VALUES (?,?,?,?,?)",
              (now(), lead_id, kind, detail, outbox_id))

# ---- envío de WhatsApp (outbox) ----
def due_outbox(c, limit=50, ignore_wait=False):
    """WhatsApp pendientes cuyo momento de (re)intento ya llegó."""
    return c.execute(
        "SELECT * FROM outbox WHERE status='pendiente' AND (? OR next_attempt_at <= ?) ORDER BY id LIMIT ?",
        (1 if ignore_wait else 0, now(), limit)).fetchall()


def outbox_sent(c, outbox_id, phone):
    c.execute("UPDATE outbox SET status='enviado', phone=?, sent_at=?, last_error='' WHERE id=?",
              (phone, now(), outbox_id))


def outbox_attempt_failed(c, outbox_id, error, next_at) -> int:
    """Suma un intento fallido, agenda el siguiente y devuelve cuántos lleva."""
    c.execute("UPDATE outbox SET attempts=attempts+1, last_error=?, next_attempt_at=? WHERE id=?",
              (str(error)[:500], next_at, outbox_id))
    return c.execute("SELECT attempts FROM outbox WHERE id=?", (outbox_id,)).fetchone()["attempts"]


def outbox_mark(c, outbox_id, status, error=""):
    c.execute("UPDATE outbox SET status=?, last_error=? WHERE id=?", (status, str(error)[:500], outbox_id))