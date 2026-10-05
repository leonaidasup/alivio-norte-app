"""Limpieza del CSV de inscripciones del partner.
No toca la base de datos ni el CSV original: lee archivos y escribe tres reportes en reports/."""
import csv
import json
import re
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from app.data import database as store

REPORTS = store.ROOT / "reports"

# Nombre de cada campo en el CSV del partner (acepta variantes)
COLUMNS = {
    "enrollment_id": ("enrollment_id",),
    "enrolled_at": ("partner_timestamp", "enrolled_at"),
    "lead_id": ("lead_id",),
    "phone": ("telefono", "phone"),
    "creator_id": ("creator_id",),
    "amount": ("monto_acordado_usd", "debt_usd"),
    "status": ("estado_inscripcion", "status"),
}
VALID_STATUS = {"completado", "en_proceso", "cancelado"}
STATUS_ALIASES = {"enrolled": "completado", "inscrito": "completado", "en proceso": "en_proceso",
                  "cancelled": "cancelado", "canceled": "cancelado"}
EMPTY = {"", "n/a", "na", "null", "none", "-"}

CLEAN_FIELDS = ["enrollment_id", "enrolled_at", "lead_id", "phone", "creator_id", "creator_source",
                "status", "amount_usd"]
QUARANTINE_FIELDS = ["linea", "enrollment_id", "enrolled_at", "lead_id", "phone", "telefono_del_lead",
                     "creator_id", "status", "amount_usd", "motivos"]
LOG_FIELDS = ["linea", "enrollment_id", "accion", "campo", "antes", "despues", "regla"]


def col(row: dict, key: str) -> str:
    for name in COLUMNS[key]:
        if name in row:
            return row[name]
    return ""


def canon_phone(raw) -> str:
    """Solo dígitos con prefijo +. Un número de 10 dígitos se asume de EE. UU. (+1)."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:
        digits = "1" + digits
    return "+" + digits if digits else ""


def parse_timestamp(raw):
    """(fecha UTC, tiene_hora, None) si es válida; (None, False, motivo) si no."""
    s = (raw or "").strip()
    if s.lower() in EMPTY:
        return None, False, "fecha_vacia"
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}):(\d{2}))?Z?", s)
    if m:
        y, mo, d, hh, mi, ss = (int(x) if x else 0 for x in m.groups())
        try:
            return datetime(y, mo, d, hh, mi, ss, tzinfo=timezone.utc), m.group(4) is not None, None
        except ValueError:
            return None, False, "fecha_invalida"
    if re.fullmatch(r"\d{10}", s):                       # segundos Unix
        return datetime.fromtimestamp(int(s), tz=timezone.utc), True, None
    m = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", s)
    if m:
        a, b, y = int(m[1]), int(m[2]), int(m[3])
        if a != b and a <= 12 and b <= 12:
            return None, False, "fecha_ambigua"          # 01-10-2026: ¿1 de octubre o 10 de enero?
        day, month = (a, b) if a > 12 else (b, a)        # si uno pasa de 12, solo puede ser el día
        try:
            return datetime(y, month, day, tzinfo=timezone.utc), False, None
        except ValueError:
            return None, False, "fecha_invalida"
    return None, False, "fecha_invalida"


def parse_amount(raw):
    """Entero en USD, o None si no es un monto válido ('$6,800' -> 6800, 'N/A' -> None)."""
    s = re.sub(r"[\s$]", "", str(raw or "")).replace(",", "")
    try:
        value = float(s)
    except ValueError:
        return None
    return int(round(value)) if 0 < value < 1e9 else None


def load_leads(path):
    """({lead_id: datos}, {teléfono: lead_id}, leads con teléfono de formato inusual)."""
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    by_id, owners, unusual = {}, {}, []
    for row in data:
        phone = canon_phone(row.get("telefono") or row.get("telefono_ficticio"))
        ts, _, _ = parse_timestamp(str(row.get("timestamp") or ""))
        by_id[str(row["id"])] = {"phone": phone, "creator": (row.get("creador") or "").strip().lower(), "ts": ts}
        if phone:
            owners.setdefault(phone, str(row["id"]))
            if len(phone) != 12:                          # "+" y 11 dígitos
                unusual.append(f"{row['id']} ({phone})")
    return by_id, owners, unusual


def clean_enrollments(csv_path, leads_path, today=None, out_dir=REPORTS):
    today = today or date.today()
    leads, _, unusual = load_leads(leads_path)
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    clean_rows, quarantine, log = [], [], []
    seen_raw, seen_ids, seen_leads = set(), {}, {}
    stats, reasons = Counter(), Counter()

    for line, raw in enumerate(rows, start=2):           # la línea 1 es el encabezado
        row = {(k or "").strip().lower(): (v.strip() if isinstance(v, str) else "") for k, v in raw.items()}
        eid = col(row, "enrollment_id")

        # 1) duplicado exacto: se descarta (y queda anotado)
        key = tuple(sorted(row.items()))
        if key in seen_raw:
            log.append({"linea": line, "enrollment_id": eid, "accion": "descartado", "campo": "",
                        "antes": "", "despues": "", "regla": "duplicado_exacto"})
            stats["duplicados"] += 1
            continue
        seen_raw.add(key)

        issues = []

        def note(campo, antes, despues, regla):
            log.append({"linea": line, "enrollment_id": eid, "accion": "corregido", "campo": campo,
                        "antes": antes, "despues": despues, "regla": regla})
            stats["correcciones"] += 1

        # 2) lead
        lead_id = col(row, "lead_id")
        lead = leads.get(lead_id)
        if not lead_id:
            issues.append("lead_id_vacio")
        elif lead is None:
            issues.append("lead_desconocido")

        # 3) teléfono: se normaliza el formato, pero un número distinto al del lead NO se corrige
        raw_phone = col(row, "phone")
        phone = canon_phone(raw_phone)
        if not phone:
            issues.append("telefono_vacio")
        else:
            if phone != raw_phone:
                note("telefono", raw_phone, phone, "formato_telefono")
            if lead and phone != lead["phone"]:
                issues.append("telefono_no_coincide")

        # 4) creator: solo se infiere del lead si el teléfono coincide
        raw_creator = col(row, "creator_id")
        creator, source = raw_creator.lower(), "csv"
        if creator and creator != raw_creator:
            note("creator_id", raw_creator, creator, "creator_normalizado")
        if not creator:
            if lead and lead["creator"] and phone and phone == lead["phone"]:
                creator, source = lead["creator"], "inferido_de_lead"
                note("creator_id", "", creator, "creator_inferido_de_lead")
            else:
                issues.append("creator_vacio")
        elif lead and creator != lead["creator"]:
            issues.append("creator_no_coincide")

        # 5) estado
        raw_status = col(row, "status")
        status = STATUS_ALIASES.get(raw_status.lower(), raw_status.lower())
        if status not in VALID_STATUS:
            issues.append("estado_desconocido")
        elif status != raw_status:
            note("estado", raw_status, status, "estado_normalizado")

        # 6) fecha
        raw_when = col(row, "enrolled_at")
        when, has_time, problem = parse_timestamp(raw_when)
        when_text = raw_when
        if problem:
            issues.append(problem)
        else:
            when_text = when.strftime("%Y-%m-%dT%H:%M:%SZ") if has_time else when.strftime("%Y-%m-%d")
            if when.date() > today:
                issues.append("fecha_futura")
            elif lead and lead["ts"] and when.date() < lead["ts"].date():
                issues.append("inscripcion_antes_del_lead")
            if when_text != raw_when:
                note("fecha", raw_when, when_text, "formato_fecha")

        # 7) monto
        raw_amount = col(row, "amount")
        amount = parse_amount(raw_amount)
        if amount is None:
            issues.append("monto_invalido")
        elif str(amount) != raw_amount:
            note("monto", raw_amount, amount, "formato_monto")

        record = {"enrollment_id": eid, "enrolled_at": when_text, "lead_id": lead_id, "phone": phone,
                  "creator_id": creator, "creator_source": source, "status": status,
                  "amount_usd": amount if amount is not None else raw_amount}

        # 8) mismo enrollment_id repetido
        if not eid:
            issues.append("id_vacio")
        else:
            fingerprint = tuple(record[k] for k in ("enrolled_at", "lead_id", "phone", "creator_id", "status", "amount_usd"))
            if eid in seen_ids:
                if seen_ids[eid] == fingerprint:         # igual tras normalizar: era un duplicado disfrazado
                    log.append({"linea": line, "enrollment_id": eid, "accion": "descartado", "campo": "",
                                "antes": "", "despues": "", "regla": "duplicado_tras_normalizar"})
                    stats["duplicados"] += 1
                    continue
                issues.append("id_repetido_con_datos_distintos")
            else:
                seen_ids[eid] = fingerprint

        # 9) mismo lead inscrito dos veces: la segunda iría a cuarentena (riesgo de doble comisión)
        if not issues and status != "cancelado":
            if lead_id in seen_leads:
                issues.append("lead_repetido")
            else:
                seen_leads[lead_id] = eid

        if issues:
            quarantine.append({"linea": line, "enrollment_id": eid, "enrolled_at": when_text, "lead_id": lead_id,
                               "phone": phone, "telefono_del_lead": lead["phone"] if lead else "",
                               "creator_id": creator, "status": status, "amount_usd": record["amount_usd"],
                               "motivos": "; ".join(issues)})
            for reason in issues:
                reasons[reason] += 1
            log.append({"linea": line, "enrollment_id": eid, "accion": "cuarentena", "campo": "",
                        "antes": "", "despues": "", "regla": "; ".join(issues)})
        else:
            clean_rows.append(record)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, fields, data in (("enrollments_clean.csv", CLEAN_FIELDS, clean_rows),
                               ("enrollments_quarantine.csv", QUARANTINE_FIELDS, quarantine),
                               ("cleaning_log.csv", LOG_FIELDS, log)):
        with open(out_dir / name, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fields)
            writer.writeheader()
            writer.writerows(data)

    return {"leidas": len(rows), "limpias": len(clean_rows), "cuarentena": len(quarantine),
            "duplicados": stats["duplicados"], "correcciones": stats["correcciones"],
            "motivos": reasons, "leads_inusuales": unusual, "carpeta": out_dir}