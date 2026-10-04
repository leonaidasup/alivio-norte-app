"""Genera datos 100% ficticios para Alivio Norte.

Uso:  python scripts/generate_data.py
Salida: data/leads.csv, data/partner_enrollments.csv, data/content_sources.csv

Todo es inventado: nombres, teléfonos (rango 555-01xx reservado para ficción) y montos.
Es determinista (seed fija) para que el README sea reproducible.
"""
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
DATA.mkdir(exist_ok=True)
random.seed(42)

BASE = datetime(2026, 10, 2, 12, 0)  # "ahora" de referencia del dataset

CREATORS = {
    "CR-001": "@marta_finanzas",
    "CR-002": "@donjuan_cuentas",
    "CR-003": "@lau.ahorra",
    "CR-004": "@pepe_contador",
}
C = {v: k for k, v in CREATORS.items()}
M, D, L, P = "@marta_finanzas", "@donjuan_cuentas", "@lau.ahorra", "@pepe_contador"
CTWA, ORG = "CTWA", "organico"

# (creador, canal, mensaje del lead)  -> 45 leads con mezcla de casos
LEADS = [
    (M, CTWA, "Hola, vi su video. Debo como 12 mil en tarjetas de crédito y ya no puedo pagar los mínimos, ¿me pueden ayudar?"),
    (D, CTWA, "Info"),
    (L, ORG, "hola"),
    (L, CTWA, "Tengo deudas de hospital, unos $8,500. ¿Qué opciones hay?"),
    (P, CTWA, "¿Esto es una estafa? ¿Cuánto cobran?"),
    (D, ORG, "Quiero que me GARANTICEN que me van a bajar la deuda a la mitad"),
    (M, CTWA, "me van a embargar el sueldo la próxima semana, ayuda urgente"),
    (D, CTWA, "Tengo un préstamo personal de $15,000 y 3 tarjetas. Sí quiero hablar con un asesor"),
    (P, ORG, "GANA DINERO RÁPIDO con cripto, escríbeme ya al privado"),
    (L, CTWA, "Debo $2,000 de una tarjeta"),
    (P, CTWA, "No tengo papeles, ¿igual pueden ayudarme?"),
    (D, ORG, "me llamó un cobrador y me amenazó con demandarme"),
    (M, CTWA, "Tengo 25 mil en tarjetas y 9 mil de un carro, quiero un Consejero"),
    (D, CTWA, "ok"),
    (L, ORG, "Hello, do you speak English?"),
    (L, CTWA, "¿Estoy en bancarrota?? o esto es diferente a bancarrota"),
    (P, CTWA, "Mis deudas son como 40k entre tarjetas y préstamos médicos"),
    (M, CTWA, "Cuánto interés me van a quitar?"),
    (M, ORG, "Quiero darme de baja de sus mensajes"),
    (D, CTWA, "tengo deuda de tarjetas como 6500 y quiero saber si podría pagar menos al mes"),
    (L, CTWA, "Mi esposo no sabe que debo tanto, no le digan nada"),
    (P, CTWA, "Les pasé mi número de seguro social por aquí 123-45-6789"),
    (L, ORG, "buenas, vi a Lau en tiktok, tengo unos 11,000 en tarjetas"),
    (M, CTWA, "Quiero cancelar mi inscripción y que me devuelvan el dinero"),
    (D, CTWA, "Me siento muy mal, ya no quiero seguir con esto, estoy desesperado"),
    (D, ORG, "Cuánto tiempo tarda? me dijeron 3 años"),
    (L, CTWA, "Deudas: tarjeta Visa 7k, tarjeta Mastercard 4k, hospital 3k"),
    (P, CTWA, "Debo 150 mil de un negocio que quebró"),
    (L, ORG, "👍"),
    (M, CTWA, "me interesa, pero mi deuda es de un préstamo estudiantil de 30 mil"),
    (D, CTWA, "Hola buenas tardes, quisiera info sobre cómo funciona"),
    (P, ORG, "Mi hermano debe mucho, ¿puedo preguntar por él?"),
    (L, CTWA, "Tengo 9,800 en deudas médicas, ¿en muchos casos pueden reducirse los pagos?"),
    (P, CTWA, "Quiero hablar ya con una persona"),
    (M, ORG, "jajaja"),
    (M, CTWA, "Debo 18 mil en 4 tarjetas, tengo trabajo estable"),
    (D, CTWA, "¿Cuál es la diferencia con una consolidación de deuda?"),
    (L, CTWA, "Ya hablé con ustedes ayer y nadie me llamó"),
    (P, ORG, "Préstamos rapidos 24h sin buró, escribe ya"),
    (P, CTWA, "Tengo 5 mil de tarjeta y 2 mil de una tienda"),
    (M, CTWA, "Me dijeron que mi crédito va a quedar destruido, ¿es cierto?"),
    (D, ORG, "buen día, deuda de tarjeta unos 13 mil, trabajo en construcción, ¿me llaman por la tarde?"),
    (D, CTWA, "¿Necesito tener ahorros para empezar?"),
    (L, CTWA, "Debo 22,500 entre 5 tarjetas y un préstamo, sí quiero que me contacte un Consejero"),
    (P, CTWA, "Quiero hablar con un asesor legal"),
]
assert len(LEADS) == 45

OLD_STATUSES = ["info_enviada", "call_back", "transferido", "no_answer", "nuevo"]


def phone(i):
    return f"+1555555{100 + i:04d}"  # +1 555 555 01xx -> ficticio


def build_leads():
    rows = []
    for i, (creator, canal, msg) in enumerate(LEADS, start=1):
        hours_ago = 330 - i * 7                       # L001 = hace ~14 días, L045 = hace ~1 día
        ts = BASE - timedelta(hours=hours_ago, minutes=random.randint(0, 59))
        status = OLD_STATUSES[i % 5] if hours_ago > 168 else "nuevo"
        rows.append({
            "lead_id": f"L{i:03d}",
            "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S"),
            "creador": creator,
            "canal": canal,
            "mensaje": msg,
            "telefono": phone(i),
            "estado_inicial": status,
        })
    return rows


NAMES = ["Ana Pérez", "Luis Rojas", "Carmen Díaz", "José Márquez", "Rosa Villa", "Miguel Soto",
         "Elena Cruz", "Pablo Rey", "Marisol Vega", "Hugo Peña", "Sandra Ortiz", "Tomás Luna",
         "Gloria Paz", "Iván Ríos", "Nora Campos", "Raúl Mora", "Dora Salas", "Félix Ibarra",
         "Yolanda Nieto", "Óscar Bravo", "Silvia Lara", "Andrés Cano", "Mirta Gil", "Beto Ramos",
         "Teresa Fonseca", "Víctor Lozano", "Paola Duarte", "Jorge Mena"]


def build_enrollments(leads):
    by_idx = {i: leads[i - 1] for i in range(1, 46)}
    base_leads = [1, 4, 5, 8, 10, 12, 13, 16, 17, 20, 21, 23, 26, 27, 28, 31, 33]
    rows = []
    for n, li in enumerate(base_leads):
        ld = by_idx[li]
        lead_ts = datetime.fromisoformat(ld["timestamp"])
        rows.append({
            "enrollment_id": f"E{n + 1:03d}",
            "enrolled_at": (lead_ts + timedelta(days=random.randint(1, 3))).strftime("%Y-%m-%d"),
            "client_name": NAMES[n],
            "phone": ld["telefono"],
            "creator_id": C[ld["creador"]],
            "program_status": random.choice(["Inscrito", "Inscrito", "Pendiente", "Cancelado"]),
            "_lead": ld["lead_id"],
        })

    # --- Errores a propósito ---
    rows[3]["phone"] = "(555) 555-" + rows[3]["phone"][-4:]          # formato distinto (recuperable)
    rows[6]["phone"] = rows[6]["phone"][:-1] + "9"                    # último dígito distinto (mismatch real)
    rows[9]["phone"] = rows[9]["phone"][:-2]                          # número incompleto
    rows[12]["phone"] = rows[12]["phone"].replace("+1", "")           # sin código de país
    for k in (2, 7, 11):
        rows[k]["creator_id"] = ""                                    # creator_id vacío
    rows[14]["creator_id"] = "CR-009"                                 # creator que no existe
    rows[1]["enrolled_at"] = "31/02/2026"                             # fecha imposible
    rows[5]["enrolled_at"] = "2026-13-01"                             # mes 13
    rows[8]["enrolled_at"] = "ayer"                                   # texto
    rows[10]["enrolled_at"] = "01/10/26"                              # formato ambiguo
    rows[15]["enrolled_at"] = "2099-01-01"                            # futuro
    rows[16]["enrolled_at"] = "2026-09-01"                            # antes de que el lead escribiera

    # --- Duplicados ---
    nxt = len(rows) + 1
    for src in (0, 4, 9):                                             # mismo teléfono, otra fecha
        d = dict(rows[src])
        d["enrollment_id"] = f"E{nxt:03d}"
        d["enrolled_at"] = "2026-09-28"
        rows.append(d)
        nxt += 1
    d = dict(rows[13])                                                # duplicado exacto (otro id)
    d["enrollment_id"] = f"E{nxt:03d}"
    rows.append(d)
    nxt += 1

    # --- Inscritos que nunca estuvieron en la base de leads ---
    extras = [("CR-001", "2026-09-25", "Inscrito"), ("", "2026-09-26", "Inscrito"),
              ("CR-002", "2026-09-27", "Pendiente"), ("CR-004", "2026-09-27", "Inscrito"),
              ("", "2026-09-29", "Cancelado"), ("CR-003", "2026-09-29", "Inscrito"),
              ("CR-001", "2026-09-30", "Inscrito")]
    for k, (cr, dt, st) in enumerate(extras):
        rows.append({
            "enrollment_id": f"E{nxt:03d}", "enrolled_at": dt,
            "client_name": NAMES[17 + k], "phone": f"+1555555{900 + k:04d}",
            "creator_id": cr, "program_status": st, "_lead": "",
        })
        nxt += 1
    random.shuffle(rows)
    return rows


SOURCES = [
    ("S01", "pregunta", "¿Esto es una estafa? ¿Cómo sé que no me van a quitar plata?", "@pepe_contador", 14),
    ("S02", "objecion", "Me da pena que mi familia sepa cuánto debo", "@lau.ahorra", 9),
    ("S03", "pregunta", "¿Qué pasa si ya me llamó un cobrador? ¿Es tarde para pedir ayuda?", "@donjuan_cuentas", 11),
    ("S04", "objecion", "Ya intenté pagar solo y no pude, ¿para qué voy a intentarlo otra vez?", "@marta_finanzas", 8),
    ("S05", "tendencia", "Videos de 'mi primer mes pagando sin ahogarme' tienen mucha retención entre hispanos", "@lau.ahorra", 6),
    ("S06", "pregunta", "¿Qué es un Consejero y en qué se diferencia de un banco?", "@donjuan_cuentas", 7),
    ("S07", "objecion", "Escuché que esto arruina mi crédito para siempre", "@marta_finanzas", 12),
    ("S08", "tendencia", "Mitos vs. realidades sobre las deudas médicas (formato de tarjetas rápidas)", "@pepe_contador", 5),
    ("S09", "pregunta", "No hablo bien inglés, ¿me atienden en español?", "@donjuan_cuentas", 4),
    ("S10", "objecion", "No sé cuánto debo en total, me da miedo sumarlo", "@lau.ahorra", 10),
]


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


if __name__ == "__main__":
    leads = build_leads()
    write_csv(DATA / "leads.csv", leads,
              ["lead_id", "timestamp", "creador", "canal", "mensaje", "telefono", "estado_inicial"])
    enr = build_enrollments(leads)
    # _lead es solo para depurar el generador; no se exporta al CSV
    write_csv(DATA / "partner_enrollments.csv", enr,
              ["enrollment_id", "enrolled_at", "client_name", "phone", "creator_id", "program_status"])
    with open(DATA / "content_sources.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source_id", "tipo", "texto", "origen_creador", "veces_visto"])
        w.writerows(SOURCES)
    print(f"leads: {len(leads)} | inscripciones: {len(enr)} | fuentes: {len(SOURCES)}")
