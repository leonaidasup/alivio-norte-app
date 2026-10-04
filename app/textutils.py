import re
import unicodedata
from difflib import SequenceMatcher

def normalize(text: str) -> str:
    """Convierte el texto en minusculas y sin tildes/ñ. Conserva signos ($ , . dígitos) para extraer montos."""
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    """Tokenizar el texto"""
    return re.findall(r"[a-z0-9]+", normalize(text))


def match_term(norm_text: str, toks: list[str], term: str, fuzzy: bool = True) -> bool:
    """Buscamos "term" en el texto

    - Terminos con simbolos (ej. ".com") busqueda literal.
    - Frases dentro del texto (buscar mas de una palabra).
    - Una palabra que se comporta como raiz ("demand" -> atrapa demanda, demandarme).
    - Tolera errores de tipeo en palabras grandes (>= 8 letras): "bancarrrota".
    """
    term = normalize(term).strip()
    if not term:
        return False
    if re.search(r"[^a-z0-9 ]", term): # busqueda literal en el texto (recuerda que la normalizacion elimina signos de puntuacion)
        return term in norm_text
    if " " in term: # buscar cuando es una frase pero dentro del token
        return (" " + term) in (" " + " ".join(toks))
    if any(t.startswith(term) for t in toks): # buscar palabras que se comportan como raices
        return True
    if fuzzy and len(term) >= 8:
        return any(
            (abs(len(t) - len(term)) <= 2 and # que la diferencia entre palabras no sea mayor a 2 letras
            SequenceMatcher(None, t[: len(term)], term).ratio() >= 0.88) # palabras con similitud textual >= 88%
            for t in toks
        )
    return False


def find_terms(text: str, terms: list[str]) -> list[str]:
    """Devuelve los terminos de la lista que aparecen en el texto."""
    norm, toks = normalize(text), tokens(text)
    return [t for t in terms if match_term(norm, toks, t)]


def neutralize(text: str, frases: list[str]) -> str:
    """Quita frases neutrales (ej. "sin embargo") que contienen raices de riesgo.
    Devuelve el texto normalizado (minusculas, sin tildes) sin esas frases.
    """
    out = normalize(text)
    for f in sorted(frases, key=len, reverse=True):
        out = out.replace(normalize(f), " ")
    return out
