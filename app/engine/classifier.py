"""Clasificador: decide responder | ignorar | escalar_humano y explica por qué.

Orden de decisión (el mismo que está documentado en config/rules.yaml):
  1) riesgo crítico                      -> escalar_humano
  2) baja / spam / sin contenido / fuera de alcance -> ignorar
  3) riesgo acumulado >= umbral          -> escalar_humano
  4) deuda no elegible o monto muy alto  -> escalar_humano
  5) sin señal de deuda ni de interés    -> escalar_humano (ante la duda)
  6) monto bajo                          -> según reglas_monto.accion_monto_bajo
  7) en otro caso                        -> responder (pre-califica + borrador)
Todo viene de las reglas: aquí no hay palabras ni umbrales escritos a mano.
"""
import re
from dataclasses import asdict, dataclass, field

from app.engine.extract import Amount, detect_debt_types, extract_amount, has_debt_signal, wants_counselor
from app.engine.textutils import find_terms, neutralize, normalize

RESPOND, IGNORE, ESCALATE = "responder", "ignorar", "escalar_humano"
SENSITIVE_MASK = "[patrón sensible]"   # nunca se guarda el dato sensible en razones ni logs


@dataclass
class Risk:
    category: str
    weight: float
    terms: list


@dataclass
class Decision:
    decision: str                       # responder | ignorar | escalar_humano
    reason: str                         # código corto, ej. "legal", "monto_bajo"
    explanation: str                    # frase legible para el humano
    risk_score: float = 0
    risks: list = field(default_factory=list)
    amount: Amount | None = None
    debt_types: dict = field(default_factory=dict)
    wants_counselor: bool = False
    urgent: bool = False
    do_not_contact: bool = False
    prequal: dict | None = None         # solo si decision == responder
    rules_version: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def find_risks(text: str, rules: dict) -> list[Risk]:
    """Categorías de riesgo presentes, de mayor a menor peso."""
    cleaned = neutralize(text, rules.get("frases_neutras", []))
    risks = []
    for name, category in rules["categorias_escalar_humano"].items():
        terms = find_terms(cleaned, category.get("terminos", []))
        if any(re.search(pattern, cleaned) for pattern in category.get("regex", [])):
            terms.append(SENSITIVE_MASK)
        if terms:
            risks.append(Risk(name, category["peso"], terms))
    return sorted(risks, key=lambda r: -r.weight)   # estable: empate = orden del YAML


def _ignore_reason(text: str, rules: dict, has_signal: bool):
    """(motivo, explicación, no_contactar) si el mensaje se ignora; None si no."""
    cfg = rules["ignorar"]
    norm = normalize(text)
    if not re.search(r"[a-z0-9]", norm):
        return "sin_contenido", "Solo emojis o símbolos.", False
    if find_terms(text, cfg.get("baja_voluntaria", [])):
        return "baja_voluntaria", "La persona pidió no recibir más mensajes.", bool(cfg.get("baja_marca_no_contactar"))
    spam = find_terms(text, cfg.get("spam_siempre", []))
    if spam:
        return "spam", f"Spam o publicidad ajena: {', '.join(spam)}.", False
    plain = re.sub(r"[^a-z0-9 ]", "", norm).strip()
    if plain in {normalize(m) for m in cfg.get("mensajes_exactos", [])}:
        return "sin_contenido", "Mensaje sin contenido útil.", False
    off_topic = find_terms(text, cfg.get("fuera_de_alcance_si_sin_deuda", []))
    if off_topic and not has_signal:
        return "fuera_de_alcance", f"No trata de una deuda ({', '.join(off_topic)}).", False
    return None


def classify(text: str, rules: dict) -> Decision:
    thresholds, money = rules["riesgo"], rules["reglas_monto"]
    amount = extract_amount(text)
    debt_types = detect_debt_types(text, rules)
    has_signal = has_debt_signal(text, rules, amount, debt_types)
    risks = find_risks(text, rules)
    score = sum(r.weight for r in risks)
    top = risks[0] if risks else None
    counselor = wants_counselor(text, rules)
    urgent = bool(find_terms(text, rules["precalificacion"].get("urgencia", [])))

    def result(decision, reason, explanation, **extra):
        return Decision(decision, reason, explanation, risk_score=score, risks=risks, amount=amount,
                        debt_types=debt_types, wants_counselor=counselor, urgent=urgent,
                        rules_version=str(rules.get("version", "")), **extra)

    def risk_summary():
        return ", ".join(f"{r.category} (peso {r.weight:g}): {', '.join(r.terms)}" for r in risks)

    # 0) sin contenido: no hay nada que evaluar
    if not re.search(r"[a-z0-9]", normalize(text)):
        return result(IGNORE, "sin_contenido", "Solo emojis o símbolos.")

    # 1) riesgo crítico
    if top and top.weight >= thresholds["umbral_critico"]:
        return result(ESCALATE, top.category, f"Riesgo crítico -> {risk_summary()}")

    # 2) ignorar
    ignored = _ignore_reason(text, rules, has_signal)
    if ignored:
        reason, why, do_not_contact = ignored
        return result(IGNORE, reason, why, do_not_contact=do_not_contact)

    # 3) riesgo acumulado
    if score >= thresholds["umbral_escalar"]:
        return result(ESCALATE, top.category, f"Riesgo acumulado {score:g} >= {thresholds['umbral_escalar']:g} -> {risk_summary()}")

    # 4) deuda no elegible o monto muy alto
    if debt_types["ineligible"]:
        kinds = ", ".join(debt_types["ineligible"])
        return result(ESCALATE, "deuda_no_elegible", f"Menciona deuda no elegible ({kinds}); la revisa un humano.")
    if amount.total and amount.total >= money["monto_alto_revision_usd"]:
        return result(ESCALATE, "monto_alto", f"Monto {amount.total:,} USD supera el límite de revisión ({money['monto_alto_revision_usd']:,}).")

    # 5) ante la duda
    if not has_signal and not find_terms(text, rules.get("senales_interes", [])):
        return result(ESCALATE, "mensaje_ambiguo", "No se entiende de qué trata; ante la duda va a un humano.")

    # 6-7) responder: pre-calificación
    eligible = list(debt_types["eligible"])
    missing = (["monto"] if amount.total is None else []) + ([] if eligible else ["tipo_deuda"])
    low_amount = amount.total is not None and amount.total < money["monto_minimo_usd"]
    if low_amount:
        action = money["accion_monto_bajo"]
        if action == "ignorar":
            return result(IGNORE, "monto_bajo", f"Monto {amount.total:,} USD bajo el mínimo ({money['monto_minimo_usd']:,}).")
        if action == "escalar_humano":
            return result(ESCALATE, "monto_bajo", f"Monto {amount.total:,} USD bajo el mínimo ({money['monto_minimo_usd']:,}).")
    status = "no_califica_monto" if low_amount else ("faltan_datos" if missing else "califica_preliminar")
    reason = {"no_califica_monto": "monto_bajo", "faltan_datos": "faltan_datos", "califica_preliminar": "precalificado"}[status]
    prequal = {
        "estado": status, "monto_usd": amount.total, "tipos_deuda": eligible,
        "quiere_consejero": counselor, "urgente": urgent, "faltan": missing,
        "monto_minimo_usd": money["monto_minimo_usd"],
        "banderas": [r.category for r in risks],   # señales leves que el humano debe ver
    }
    return result(RESPOND, reason, f"Pre-calificación: {status}.", prequal=prequal)