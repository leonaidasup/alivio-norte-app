import re
from dataclasses import dataclass, field

from .textutils import find_terms, normalize

NUM = r"\d{1,3}(?:[,.]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d+)?"
RE_DOLLAR = re.compile(rf"\$\s?({NUM})(?:\s?(k|mil|K)\b)?")      # $8,500  $8k  $ 12 mil
RE_MULTIPLIER = re.compile(rf"(?<![\w$])({NUM})\s?(k|mil|K)\b")  # 12 mil  40k
RE_BARE = re.compile(r"(?<![\w$,.])(\d{4,6})(?![\w,.])")        # 6500
EXCLUDED_CONTEXT = re.compile(r"\b(?:falt|ahorr|ingreso|gano|gana|cuota|mensual|minimo)")
CLAUSE_BREAK = re.compile(r"[.,;:!?]|\b(?:pero|y|aunque|mientras|ademas)\b")  # el contexto termina aquí
YEAR_PRECEDERS = {"en", "del", "desde", "ano", "hasta", "para"}
FILLER = re.compile(r"(?:(?:en|de|es|son|suman|seria|serian)\s*)*")


@dataclass
class Amount:
    total: int | None                              # total dinero
    parts: list = field(default_factory=list)      # cifras válidas
    excluded: list = field(default_factory=list)   # cifras descartadas (no son deuda)
    method: str = "ninguno"                        # ninguno | unico | total_declarado | suma


def parse_amount(num: str, multiplier: str | None) -> int:
    """Convierte texto numérico en un número entero."""
    m = re.fullmatch(r"(\d{1,3}(?:[,.]\d{3})+)([.,]\d{1,2})?", num)
    if m:
        value = float(re.sub(r"[,.]", "", m.group(1)))   # cientos y miles
        if m.group(2):
            value += float(m.group(2).replace(",", "."))  # centavos
    else:
        value = float(num.replace(",", "."))
    if multiplier in ("k", "mil", "K"):
        value *= 1000
    return int(round(value))


def looks_like_year(s: str, start: int, end: int) -> bool:
    """Un número de 1990-2100 es año solo si el contexto lo sugiere ("desde 2024")."""
    before = re.findall(r"[a-z]+", s[max(0, start - 12):start])  # palabras antes del número
    after = re.findall(r"[a-z]+", s[end:end + 12])               # palabras después del número
    if after and after[0] in {"dolares", "usd", "pesos", "dls"}:
        return False
    return bool(before) and before[-1] in YEAR_PRECEDERS


def declared_total(s: str, parts: list):
    """Busca el "total" dicho por la persona entre todas las apariciones de la palabra,
    prefiriendo "$0000 en total" sobre "total ... $0000"."""
    candidates = []
    for t in re.finditer(r"\btotal\b", s):
        for start, end, value in parts:
            if end <= t.start() and FILLER.fullmatch(s[end:t.start()].strip()):  # cifra ANTES de "total"
                candidates.append((0, t.start() - end, value))
            elif start >= t.end() and start - t.end() <= 12:                    # cifra DESPUÉS, hasta 12 caracteres
                candidates.append((1, start - t.end(), value))
    return min(candidates)[2] if candidates else None


def extract_amount(text: str) -> Amount:
    """Extrae y consolida los montos de deuda de un texto, filtrando
    cifras irrelevantes por contexto y calculando el total final."""
    s = normalize(text)
    found, taken = [], []

    for rx in (RE_DOLLAR, RE_MULTIPLIER, RE_BARE):
        for m in rx.finditer(s):
            span = m.span()
            if not all(span[1] <= a or b <= span[0] for a, b in taken):   # una posición se procesa una sola vez
                continue
            multiplier = m.group(2) if rx is not RE_BARE else None
            value = parse_amount(m.group(1), multiplier)
            if rx is RE_BARE and 1990 <= value <= 2100 and looks_like_year(s, *span):
                continue
            taken.append(span)
            found.append((span[0], span[1], value))

    found.sort()
    parts, excluded = [], []
    for start, end, value in found:
        window = CLAUSE_BREAK.split(s[max(0, start - 40):start])[-1]
        (excluded if EXCLUDED_CONTEXT.search(window) else parts).append((start, end, value))

    values = [v for _, _, v in parts]
    excluded_values = [v for _, _, v in excluded]
    if not values:
        return Amount(None, [], excluded_values, "ninguno")
    if len(parts) == 1:
        return Amount(values[0], values, excluded_values, "unico")
    total = declared_total(s, parts)
    if total is not None:
        return Amount(total, values, excluded_values, "total_declarado")   # declarado por el usuario
    return Amount(sum(values), values, excluded_values, "suma")


def detect_debt_types(text: str, rules: dict) -> dict:
    """{'eligible': {'tarjeta_credito': ['visa']}, 'ineligible': {...}}"""
    out = {}
    for group, key in (("eligible", "deudas_elegibles"), ("ineligible", "deudas_no_elegibles")):
        hits = {}
        for debt_type, terms in rules[key].items():
            matched = find_terms(text, terms)
            if matched:
                hits[debt_type] = matched
        out[group] = hits
    return out


def has_debt_signal(text: str, rules: dict, amount: Amount, debt_types: dict) -> bool:
    return bool(amount.total or debt_types["eligible"] or debt_types["ineligible"]
                or find_terms(text, rules.get("senales_deuda", [])))


def wants_counselor(text: str, rules: dict) -> bool:
    return bool(find_terms(text, rules["precalificacion"]["quiere_consejero"]))