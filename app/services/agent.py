"""El agente: procesa la cola, decide, deja borrador o resumen para el humano y escribe el log."""
import csv
import json
import logging
import time

from app.data import database as store
from app.engine.classifier import ESCALATE, IGNORE, RESPOND, classify
from app.engine.drafts import ComplianceError, build_draft, draft_document
from app.engine.handoff import ACTIONS, build_summary
from app.engine.rules import RulesError

log = logging.getLogger("alivio.agent")

ROOT = store.ROOT
DRAFTS_DIR = ROOT / "runtime" / "drafts"
LOG_FILE = ROOT / "runtime" / "decisions_log.csv"
LOG_FIELDS = ["timestamp", "lead_id", "decision", "reason", "draft_link", "handoff_id", "rules_version"]
MAX_ATTEMPTS = 3


def _escalate(d, reason, explanation):
    """Cambia una decisión a escalar_humano (los candados del sistema: ante la duda, una persona)."""
    d.decision, d.reason, d.explanation, d.prequal = ESCALATE, reason, explanation, None
    return d


def _append_log(row: dict):
    """Una línea por decisión. Si el log falla no se pierde nada: la decisión ya está en la base."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        is_new = not LOG_FILE.exists()
        with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, LOG_FIELDS)
            if is_new:
                writer.writeheader()
            writer.writerow(row)
    except OSError as e:
        log.error("No se pudo escribir el log: %s", e)


def process_message(database, rules: dict, msg: dict):
    """Clasifica un mensaje y guarda todo el resultado en una sola transacción."""
    lead_id = msg["lead_id"]
    d = classify(msg["text"], rules)
    draft_link, handoff_id = "", ""

    with database.tx() as c:
        # alguien que pidió la baja y vuelve a escribir: nunca se le prepara borrador
        if d.decision == RESPOND and store.is_dnc(c, lead_id):
            _escalate(d, "no_contactar_previo", "Este lead pidió no recibir mensajes y volvió a escribir.")

        if d.decision == RESPOND:
            try:
                body = build_draft(d, rules)
            except ComplianceError as e:
                _escalate(d, "borrador_incumple_compliance", str(e))
            else:
                draft_id = store.add_draft(c, msg["id"], lead_id, body)
                DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
                path = DRAFTS_DIR / f"borrador_{draft_id}.md"
                path.write_text(draft_document(d, lead_id, body), encoding="utf-8")
                draft_link = path.relative_to(ROOT).as_posix()
                store.set_draft_path(c, draft_id, draft_link)

        if d.decision == ESCALATE:
            summary = build_summary(d, lead_id, msg["text"], msg["creator"], msg["channel"])
            handoff_id = store.add_handoff(c, msg["id"], lead_id, d.reason, summary)

        if d.decision == IGNORE and d.do_not_contact:
            store.mark_dnc(c, lead_id)

        store.add_decision(c, msg["id"], lead_id, d.decision, d.reason, d.explanation, d.rules_version,
                           json.dumps(d.to_dict(), ensure_ascii=False, default=str))
        store.mark_processed(c, msg["id"])

    _append_log({"timestamp": store.now(), "lead_id": lead_id, "decision": d.decision, "reason": d.reason,
                 "draft_link": draft_link, "handoff_id": handoff_id, "rules_version": d.rules_version})
    return d


def _handle_failure(database, msg: dict, error: Exception):
    """Reintenta hasta MAX_ATTEMPTS; después lo escala a un humano para que el lead no se pierda."""
    log.exception("Falló el mensaje %s", msg["id"])
    handoff_id = ""
    with database.tx() as c:
        attempts = store.mark_error(c, msg["id"], error)
        if attempts >= MAX_ATTEMPTS:
            excerpt = " ".join(msg["text"].split())[:240]
            summary = (f"Lead: {msg['lead_id']}\nMotivo: error_procesamiento\n"
                       f"Por qué: el sistema falló {attempts} veces ({error}).\nMensaje: \"{excerpt}\"\n"
                       f"Qué hacer: {ACTIONS['error_procesamiento']}")
            handoff_id = store.add_handoff(c, msg["id"], msg["lead_id"], "error_procesamiento", summary)
            store.add_decision(c, msg["id"], msg["lead_id"], ESCALATE, "error_procesamiento",
                               f"Falló {attempts} veces: {error}", "", "{}")
            store.mark_escalated_by_error(c, msg["id"])
    if handoff_id:
        _append_log({"timestamp": store.now(), "lead_id": msg["lead_id"], "decision": ESCALATE,
                     "reason": "error_procesamiento", "draft_link": "", "handoff_id": handoff_id,
                     "rules_version": ""})


def process_pending(database, rules_store, limit=50) -> int:
    """Procesa los mensajes pendientes. Devuelve cuántos salieron bien."""
    with database.tx() as c:
        batch = [dict(r) for r in store.pending(c, limit, MAX_ATTEMPTS)]
    done = 0
    for msg in batch:
        try:
            rules = rules_store.get()   # recarga en caliente: cada mensaje usa las reglas vigentes
        except (RulesError, OSError) as e:
            log.error("Sin reglas válidas, se detiene el procesamiento: %s", e)
            break
        try:
            process_message(database, rules, msg)
            done += 1
        except Exception as e:
            _handle_failure(database, msg, e)
    return done


def run_forever(database, rules_store, interval=2.0, stop_event=None):
    """Revisa la cola cada pocos segundos. stop_event (threading.Event) permite detenerlo limpio."""
    while not (stop_event and stop_event.is_set()):
        if process_pending(database, rules_store) == 0:
            if stop_event:
                stop_event.wait(interval)
            else:
                time.sleep(interval)