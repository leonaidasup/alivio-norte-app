"""Borrador para la cola humana. Nunca se envía solo; siempre pasa por revisión de compliance."""
import re

from .textutils import normalize

TIPOS = {"tarjeta_credito": "tarjetas de crédito", "prestamo_personal": "préstamo personal",
         "gastos_medicos": "gastos médicos"}


class ComplianceError(Exception):
    """El borrador contiene lenguaje prohibido por las reglas."""


def _money(n) -> str:
    return f"${n:,} USD"


def build_draft(d, rules: dict) -> str:
    """Texto del mensaje para el lead, según el resultado de la pre-calificación."""
    p = d.prequal
    partner, staff = rules["partner"], rules["termino_personal_partner"]
    estado = p["estado"]

    if estado == "califica_preliminar":
        tipos = ", ".join(TIPOS.get(t, t) for t in p["tipos_deuda"])
        cuerpo = (f"Por lo que nos cuentas ({_money(p['monto_usd'])} en {tipos}), tu caso podría ser "
                  f"candidato a revisión con {partner}. En muchos casos, dependiendo de tu perfil, es posible "
                  f"reducir pagos, pero eso lo define un {staff} al revisar tu situación.")
        cierre = (f"Dejamos tu solicitud para que un {staff} la revise y te contacte."
                  if p["quiere_consejero"] else f"¿Te gustaría que un {staff} te contacte?")
    elif estado == "faltan_datos":
        preguntas = []
        if "monto" in p["faltan"]:
            preguntas.append("¿Aproximadamente cuánto suman tus deudas?")
        if "tipo_deuda" in p["faltan"]:
            preguntas.append("¿Qué tipo de deuda es (tarjeta de crédito, préstamo personal o gastos médicos)?")
        cuerpo = "Para revisar tu caso necesitamos un par de datos:\n" + "\n".join(f"- {q}" for q in preguntas)
        cierre = f"Con eso, un {staff} podrá orientarte mejor."
    else:  # no_califica_monto
        cuerpo = (f"Con el monto que mencionas ({_money(p['monto_usd'])}), el programa de {partner} podría no "
                  f"ser la mejor opción por ahora: está pensado para deudas desde {_money(p['monto_minimo_usd'])}.")
        cierre = "Si tu deuda total es mayor, cuéntanos y lo revisamos."

    return enforce_compliance(f"Hola, gracias por escribirnos.\n\n{cuerpo}\n\n{cierre}", rules)


def enforce_compliance(body: str, rules: dict) -> str:
    """Reemplaza 'asesor' por 'Consejero' y rechaza promesas o datos que nunca se afirman."""
    c = rules["compliance"]
    for bad, good in c.get("reemplazos", {}).items():
        body = re.sub(rf"\b{re.escape(bad)}\b", good, body, flags=re.I)
    norm = normalize(body)
    prohibidas = list(c.get("garantias_prohibidas", [])) + list(c.get("nunca_afirmar", []))
    prohibidas.append(c.get("termino_prohibido", ""))
    found = [t for t in prohibidas if t and normalize(t) in norm]
    if found:
        raise ComplianceError(f"Borrador con lenguaje prohibido: {', '.join(found)}")
    return body


def draft_document(d, lead_id: str, body: str) -> str:
    """Archivo .md que ve el humano: contexto arriba, mensaje propuesto abajo."""
    p = d.prequal
    banderas = ", ".join(p["banderas"]) or "ninguna"
    return (f"# Borrador para lead {lead_id}\n\n"
            f"- Estado: {p['estado']}\n- Monto: {p['monto_usd'] if p['monto_usd'] is not None else 'no indicado'}\n"
            f"- Tipos de deuda: {', '.join(p['tipos_deuda']) or 'no indicado'}\n"
            f"- Quiere Consejero: {'sí' if p['quiere_consejero'] else 'no'}\n"
            f"- Urgente: {'sí' if p['urgente'] else 'no'}\n- Banderas leves: {banderas}\n"
            f"- Reglas versión: {d.rules_version}\n\n"
            f"## Mensaje propuesto\n\n{body}\n\n---\n"
            f"Estado: pendiente_revision. Este mensaje NO se envía automáticamente.\n")