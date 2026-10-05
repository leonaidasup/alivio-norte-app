"""Comandos: serve | once | import-csv | queue."""
import argparse
import logging
import threading
from http.server import ThreadingHTTPServer
from datetime import date
from time import time

from .data import database as store
from .services.agent import process_pending, run_forever
from .data.ingest import import_leads, make_handler
from .engine.rules import RulesStore
from .services.crm import apply_disposition
from .services.whatsapp import process_outbox
from .data.clean import clean_enrollments
from .analytics.metrics import compute, report, write_csv
from .analytics.stalled import compute_stalled, stalled_report, write_stalled_csv

RULES_PATH = store.ROOT / "config" / "rules.yaml"


def _process_all(database, rules_store) -> int:
    total = 0
    while True:
        n = process_pending(database, rules_store)
        total += n
        if n == 0:
            return total


def cmd_serve(args):
    database, rules_store = store.DB(), RulesStore(RULES_PATH)
    stop = threading.Event()
    worker = threading.Thread(target=run_forever, args=(database, rules_store, 2.0, stop), daemon=True)
    worker.start()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(database))
    print(f"Webhook en http://{args.host}:{args.port}/webhook  (Ctrl+C para salir)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        worker.join(timeout=5)


def cmd_once(args):
    t = time()
    n = _process_all(store.DB(), RulesStore(RULES_PATH))
    print("procesados:", n)
    if n > 0:
        print(f'Promedio tiempo de ejecucion: {(time() - t) / n}s')


def cmd_import(args):
    database = store.DB()
    new, dup, skipped = import_leads(database, args.file)
    print(f"nuevos: {new} | duplicados: {dup} | omitidos (sin id o sin mensaje): {skipped}")
    if args.process:
        print("procesados:", _process_all(database, RulesStore(RULES_PATH)))

def cmd_disposition(args):
    res = apply_disposition(store.DB(), RulesStore(RULES_PATH).get(), args.lead_id, args.name, args.actor)
    if res["ok"]:
        extra = f" | WhatsApp #{res['outbox_id']} en cola" if res["outbox_id"] else " | sin WhatsApp (ver audit trail)"
        print(f"Aplicada: {res['from']} -> {res['to']}{extra}")
    else:
        print("Rechazada:", res["detail"])

def cmd_clean(args):
    today = date.fromisoformat(args.hoy) if args.hoy else None
    r = clean_enrollments(args.file, args.leads, today)
    print(f"Filas leídas: {r['leidas']}")
    print(f"Limpias: {r['limpias']} | En cuarentena: {r['cuarentena']} | "
          f"Duplicados descartados: {r['duplicados']} | Correcciones: {r['correcciones']}")
    print("Motivos de cuarentena:")
    for reason, n in r["motivos"].most_common():
        print(f"  {reason}: {n}")
    if r["leads_inusuales"]:
        print("Leads con teléfono de formato inusual:", ", ".join(r["leads_inusuales"]))
    print("Reportes en", r["carpeta"])

def cmd_metrics(args):
    try:
        leads, pending = compute(args.leads, args.clean, args.quarantine, RulesStore(RULES_PATH).get())
    except FileNotFoundError as e:
        raise SystemExit(f"Falta un archivo ({e.filename}). Ejecuta primero: python -m app clean data\\partner_enrollments_dirty.csv")
    print(report(leads, pending))
    print("\nTabla guardada en", write_csv(leads, store.ROOT / "reports" / "funnel_metrics.csv"))

def cmd_stalled(args):
    today = date.fromisoformat(args.hoy) if args.hoy else None
    try:
        rows, cfg = compute_stalled(args.leads, args.clean, args.quarantine, RulesStore(RULES_PATH).get(), today)
    except FileNotFoundError as e:
        raise SystemExit(f"Falta un archivo ({e.filename}). Ejecuta primero: python -m app clean data\\partner_enrollments_dirty.csv")
    print(stalled_report(rows, today or date.today(), cfg))
    print("\nTabla guardada en", write_stalled_csv(rows, store.ROOT / "reports" / "stalled_leads.csv"))

def cmd_send(args):
    print(process_outbox(store.DB(), ignore_wait=args.now))

def cmd_queue(args):
    with store.DB().tx() as c:
        waiting = c.execute("SELECT COUNT(*) FROM messages WHERE status IN ('nuevo','error')").fetchone()[0]
        drafts = c.execute("SELECT id, lead_id, path FROM drafts WHERE status='pendiente_revision' ORDER BY id").fetchall()
        handoffs = c.execute("SELECT id, lead_id, reason FROM handoffs WHERE status='pendiente' ORDER BY id").fetchall()
        outbox = c.execute("SELECT status, COUNT(*) AS n FROM outbox GROUP BY status").fetchall()
        failures = c.execute("SELECT id, lead_id, kind, detail FROM failures WHERE status='abierto' ORDER BY id").fetchall()
    print(f"Mensajes sin procesar: {waiting}")
    print(f"\nBorradores para revisar ({len(drafts)}):")
    for r in drafts:
        print(f"  #{r['id']}  lead {r['lead_id']}  ->  {r['path']}")
    print(f"\nEscalados a un agente ({len(handoffs)}):")
    for r in handoffs:
        print(f"  #{r['id']}  lead {r['lead_id']}  motivo: {r['reason']}")
    print("\nWhatsApp: " + (", ".join(f"{r['n']} {r['status']}" for r in outbox) or "ninguno"))
    print(f"\nCola de fallos ({len(failures)}):")
    for r in failures:
        print(f"  #{r['id']}  lead {r['lead_id']}  {r['kind']}: {r['detail']}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="python -m app", description="Agente de pre-calificación Alivio Norte")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("serve", help="webhook + worker")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)

    sub.add_parser("once", help="procesa lo pendiente y termina").set_defaults(func=cmd_once)

    p = sub.add_parser("import-leads", help="carga leads desde un JSON o CSV")
    p.add_argument("file")
    p.add_argument("--process", action="store_true", help="procesarlos de inmediato")
    p.set_defaults(func=cmd_import)

    sub.add_parser("queue", help="muestra lo que espera a una persona").set_defaults(func=cmd_queue)

    p = sub.add_parser("disposition", help="aplica una disposición a un lead")
    p.add_argument("lead_id")
    p.add_argument("name", help='ej. "Info Sent"')
    p.add_argument("--actor", default="agente", help="quién la aplica (queda en el audit trail)")
    p.set_defaults(func=cmd_disposition)

    p = sub.add_parser("send", help="envía los WhatsApp pendientes")
    p.add_argument("--now", action="store_true", help="salta la espera entre reintentos")
    p.set_defaults(func=cmd_send)

    p = sub.add_parser("clean", help="limpia el CSV de inscripciones del partner")
    p.add_argument("file")
    p.add_argument("--leads", default=str(store.ROOT / "data" / "leads_chat.json"))
    p.add_argument("--hoy", help="fecha de referencia AAAA-MM-DD (por defecto, hoy)")
    p.set_defaults(func=cmd_clean)

    p = sub.add_parser("metrics", help="métricas del funnel (lee leads y reportes de limpieza)")
    p.add_argument("--leads", default=str(store.ROOT / "data" / "leads_chat.json"))
    p.add_argument("--clean", default=str(store.ROOT / "reports" / "enrollments_clean.csv"))
    p.add_argument("--quarantine", default=str(store.ROOT / "reports" / "enrollments_quarantine.csv"))
    p.set_defaults(func=cmd_metrics)

    p = sub.add_parser("stalled", help="leads estancados que necesitan seguimiento")
    p.add_argument("--leads", default=str(store.ROOT / "data" / "leads_chat.json"))
    p.add_argument("--clean", default=str(store.ROOT / "reports" / "enrollments_clean.csv"))
    p.add_argument("--quarantine", default=str(store.ROOT / "reports" / "enrollments_quarantine.csv"))
    p.add_argument("--hoy", help="fecha de referencia AAAA-MM-DD (por defecto, hoy)")
    p.set_defaults(func=cmd_stalled)

    args = parser.parse_args()
    args.func(args)