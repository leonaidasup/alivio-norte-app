"""Vista de leads estancados: a quién hay que darle seguimiento y por qué.
Solo lee archivos (igual que metrics.py): no usa ni modifica la base de datos.

Como los archivos no traen historial de disposiciones, la situación de cada lead se infiere así:
  sin_inscripcion            el agente lo atendió (responder/escalar), no hay inscripción y ya pasaron
                             `dias_sin_contacto` desde que escribió
  inscripcion_por_confirmar  el partner reportó una inscripción, pero SOLO existe en cuarentena (datos rotos)
  en_proceso_sin_avance      inscripción "en_proceso" desde hace `dias_en_proceso` días o más
No aparecen: los ignorados (spam, bajas), ni los inscritos completados o cancelados (ya cerraron).
Los plazos se pueden cambiar en config/rules.yaml, sección opcional `estancados`.
"""
import csv
import json
from collections import defaultdict
from datetime import date

from .classifier import ESCALATE, IGNORE, classify
from .clean import parse_timestamp
from .handoff import ACTIONS, DEFAULT_ACTION

DEFAULTS = {"dias_sin_contacto": 2, "dias_en_proceso": 5}
URGENT = {"riesgo_emocional", "hostigamiento_cobranza", "legal", "datos_sensibles"}
PRIORITY_ORDER = {"alta": 0, "media": 1, "baja": 2}
FIELDS = ["prioridad", "lead_id", "creador", "canal", "decision_agente", "motivo_agente",
          "situacion", "dias_sin_avance", "detalle", "siguiente_accion"]
RESPOND_ACTIONS = {
    "califica_preliminar": "Revisar el borrador y contactar al lead.",
    "faltan_datos": "Pedir monto y tipo de deuda.",
    "no_califica_monto": "Revisar la respuesta de monto bajo y cerrar el caso; no insistir.",
}


def _read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _group(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[r["lead_id"]].append(r)
    return groups


def _priority(decision, situation) -> str:
    if situation == "inscripcion_por_confirmar" or decision.reason in URGENT:
        return "alta"
    if decision.decision == ESCALATE or (decision.prequal or {}).get("estado") == "califica_preliminar":
        return "media"
    return "baja"


def compute_stalled(leads_path, clean_path, quarantine_path, rules, today=None):
    """([filas estancadas ordenadas por prioridad], plazos usados)."""
    today = today or date.today()
    cfg = {**DEFAULTS, **(rules.get("estancados") or {})}
    with open(leads_path, encoding="utf-8-sig") as f:
        leads = json.load(f)
    clean, quarantine = _group(_read_csv(clean_path)), _group(_read_csv(quarantine_path))

    rows = []
    for lead in leads:
        lead_id = str(lead["id"])
        d = classify(lead.get("mensaje") or "", rules)
        if d.decision == IGNORE:
            continue
        ts, _, _ = parse_timestamp(str(lead.get("timestamp") or ""))
        age = (today - ts.date()).days if ts else None
        enrolled = clean.get(lead_id, [])
        statuses = {r["status"] for r in enrolled}
        if statuses & {"completado", "cancelado"}:
            continue                                            # ya cerró

        if "en_proceso" in statuses:
            when, _, _ = parse_timestamp(next(r["enrolled_at"] for r in enrolled if r["status"] == "en_proceso"))
            days = (today - when.date()).days if when else None
            if days is None or days < cfg["dias_en_proceso"]:
                continue                                        # todavía dentro del plazo
            situation, detail = "en_proceso_sin_avance", f"inscripción en proceso desde {when.date()}"
            action = "Preguntar al partner en qué paso está la inscripción."
        elif lead_id in quarantine:
            days = age
            motivos = "; ".join(sorted({r["motivos"] for r in quarantine[lead_id]}))
            situation, detail = "inscripcion_por_confirmar", f"datos con problemas: {motivos}"
            action = "Pedir al partner que confirme esos datos. No pagar comisión hasta resolverlo."
        else:
            if age is not None and age < cfg["dias_sin_contacto"]:
                continue                                        # todavía es reciente
            days = age
            situation, detail = "sin_inscripcion", "sin inscripción registrada"
            action = (ACTIONS.get(d.reason, DEFAULT_ACTION) if d.decision == ESCALATE
                      else RESPOND_ACTIONS.get((d.prequal or {}).get("estado"), "Revisar el borrador."))

        rows.append({"prioridad": _priority(d, situation), "lead_id": lead_id,
                     "creador": (lead.get("creador") or "").strip().lower(), "canal": lead.get("canal") or "",
                     "decision_agente": d.decision, "motivo_agente": d.reason, "situacion": situation,
                     "dias_sin_avance": "" if days is None else days, "detalle": detail,
                     "siguiente_accion": action})
    # riesgo emocional siempre primero; después prioridad, y dentro de cada una el que lleva más días esperando
    rows.sort(key=lambda r: (r["motivo_agente"] != "riesgo_emocional", PRIORITY_ORDER[r["prioridad"]],
                             -(r["dias_sin_avance"] if r["dias_sin_avance"] != "" else 0), r["lead_id"]))
    return rows, cfg


def stalled_report(rows, today, cfg) -> str:
    by_sit = {s: sum(1 for r in rows if r["situacion"] == s)
              for s in ("sin_inscripcion", "inscripcion_por_confirmar", "en_proceso_sin_avance")}
    by_prio = {p: sum(1 for r in rows if r["prioridad"] == p) for p in PRIORITY_ORDER}
    lines = [
        f"LEADS ESTANCADOS al {today} (sin contacto: {cfg['dias_sin_contacto']}+ días | en proceso: {cfg['dias_en_proceso']}+ días)",
        f"Total: {len(rows)} | alta: {by_prio['alta']} | media: {by_prio['media']} | baja: {by_prio['baja']}",
        "  " + " | ".join(f"{s}: {n}" for s, n in by_sit.items()),
        "",
        f"{'prio':<6}{'lead':<11}{'días':>4}  {'situación':<27}{'motivo del agente':<24}siguiente acción",
    ]
    for r in rows:
        lines.append(f"{r['prioridad']:<6}{r['lead_id']:<11}{r['dias_sin_avance']!s:>4}  {r['situacion']:<27}"
                     f"{r['motivo_agente']:<24}{r['siguiente_accion'][:70]}")
    return "\n".join(lines)


def write_stalled_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path