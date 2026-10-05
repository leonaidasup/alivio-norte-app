"""Métricas del funnel. Solo lee archivos: no usa ni modifica la base de datos."""
import csv
import json
from collections import Counter, defaultdict

from .classifier import ESCALATE, IGNORE, RESPOND, classify

RANK = {"completado": 3, "en_proceso": 2, "cancelado": 1}   # si un lead tiene varias, gana la más avanzada
GROUP_FIELDS = ["grupo", "valor", "leads", "responder", "escalar_humano", "ignorar", "completados", "conversion"]


def _read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def pct(a, b) -> str:
    return f"{a / b:.0%}" if b else "-"


def compute(leads_path, clean_path, quarantine_path, rules):
    """({lead_id: datos}, leads por confirmar)."""
    with open(leads_path, encoding="utf-8-sig") as f:
        raw = json.load(f)
    leads = {}
    for row in raw:
        d = classify(row.get("mensaje") or "", rules)
        leads[str(row["id"])] = {
            "creator": (row.get("creador") or "sin_creador").strip().lower(),
            "channel": row.get("canal") or "sin_canal",
            "decision": d.decision,
            "estado": d.prequal["estado"] if d.prequal else "",
            "enrollment": "",
        }
    for r in _read_csv(clean_path):
        lead = leads.get(r["lead_id"])
        if lead and RANK.get(r["status"], 0) > RANK.get(lead["enrollment"], 0):
            lead["enrollment"] = r["status"]
    quarantined = {r["lead_id"] for r in _read_csv(quarantine_path)}
    pending = {i for i in quarantined if i in leads and not leads[i]["enrollment"]}
    return leads, pending


def group_rows(leads, key_fn, label):
    groups = defaultdict(list)
    for lead in leads.values():
        groups[key_fn(lead)].append(lead)
    rows = []
    for value, items in sorted(groups.items()):
        c = Counter(i["decision"] for i in items)
        done = sum(1 for i in items if i["enrollment"] == "completado")
        rows.append({"grupo": label, "valor": value, "leads": len(items), "responder": c[RESPOND],
                     "escalar_humano": c[ESCALATE], "ignorar": c[IGNORE], "completados": done,
                     "conversion": pct(done, len(items))})
    return rows


def report(leads, pending) -> str:
    n = len(leads)
    dec = Counter(l["decision"] for l in leads.values())
    estados = Counter(l["estado"] for l in leads.values() if l["estado"])
    enr = Counter(l["enrollment"] for l in leads.values() if l["enrollment"])
    attendable = dec[RESPOND] + dec[ESCALATE]
    done = enr["completado"]
    missed = sorted(i for i, l in leads.items() if l["decision"] == IGNORE and l["enrollment"] == "completado")

    lines = [
        "FUNNEL",
        f"Leads recibidos: {n}",
        f"  Ignorados (spam, fuera de alcance, baja): {dec[IGNORE]} ({pct(dec[IGNORE], n)})",
        f"  Escalados a un humano: {dec[ESCALATE]} ({pct(dec[ESCALATE], n)})",
        f"  Pre-calificados por el agente: {dec[RESPOND]} ({pct(dec[RESPOND], n)})",
    ]
    for estado, count in estados.most_common():
        lines.append(f"      {estado}: {count}")
    lines += [
        "",
        "Inscripciones del partner (datos limpios):",
        f"  completadas: {done} | en proceso: {enr['en_proceso']} | canceladas: {enr['cancelado']}",
        f"  por confirmar (solo existen en cuarentena): {len(pending)} leads"
        + (f" -> {', '.join(sorted(pending))}" if pending else ""),
        "",
        "Conversión (inscripciones completadas):",
        f"  sobre leads recibidos: {pct(done, n)}",
        f"  sobre leads atendibles (pre-calificados + escalados): {pct(done, attendable)}",
        "",
        "Inscripciones completadas según lo que decidió el agente:",
        "  " + " | ".join(f"{d}: {sum(1 for l in leads.values() if l['decision'] == d and l['enrollment'] == 'completado')}"
                           for d in (RESPOND, ESCALATE, IGNORE)),
    ]
    if missed:
        lines.append(f"  ATENCIÓN: el agente ignoró leads que sí se inscribieron: {', '.join(missed)}")

    for label, key_fn in (("POR CREADOR", lambda l: l["creator"]), ("POR CANAL", lambda l: l["channel"])):
        lines += ["", label]
        for r in group_rows(leads, key_fn, label):
            lines.append(f"  {r['valor']:<12} leads {r['leads']:>2} | responder {r['responder']:>2} | "
                         f"escalar {r['escalar_humano']:>2} | ignorar {r['ignorar']:>2} | "
                         f"completados {r['completados']:>2} ({r['conversion']})")
    return "\n".join(lines)


def write_csv(leads, path):
    rows = (group_rows(leads, lambda l: "todos", "total")
            + group_rows(leads, lambda l: l["creator"], "creador")
            + group_rows(leads, lambda l: l["channel"], "canal"))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, GROUP_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path