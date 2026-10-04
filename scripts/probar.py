"""Prueba rápida del Paso 1: qué detecta el sistema en un mensaje.

Uso:
  python scripts/probar.py "Debo $8,500 en tarjetas, sin embargo puedo pagar"
  python scripts/probar.py            # modo interactivo (escribe mensajes)
  python scripts/probar.py --leads    # recorre los 40 leads
(El clasificador responder/ignorar/escalar viene en el Paso 2.)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.extract import detectar_tipos_deuda, extraer_monto, quiere_consejero, tiene_senal_de_deuda  # noqa: E402
from app.rules import RulesStore  # noqa: E402
from app.textutils import find_terms, neutralizar  # noqa: E402

store = RulesStore(ROOT / "config" / "rules.yaml")


def riesgos(texto, reglas):
    limpio = neutralizar(texto, reglas.get("frases_neutras", []))
    hits = []
    for nombre, cat in reglas["categorias_escalar_humano"].items():
        terms = find_terms(limpio, cat.get("terminos", []))
        rx = [r for r in cat.get("regex", []) if re.search(r, texto)]
        if terms or rx:
            hits.append((nombre, cat["peso"], terms + rx))
    return sorted(hits, key=lambda h: -h[1])


def analizar(texto):
    reglas = store.get()           # recarga sola si editaste rules.yaml
    monto = extraer_monto(texto)
    tipos = detectar_tipos_deuda(texto, reglas)
    return {
        "monto": monto,
        "tipos": tipos,
        "senal_deuda": tiene_senal_de_deuda(texto, reglas, monto, tipos),
        "quiere_consejero": quiere_consejero(texto, reglas),
        "riesgos": riesgos(texto, reglas),
    }


def mostrar(texto):
    r = analizar(texto)
    m = r["monto"]
    print(f"\nMensaje: {texto}")
    print(f"  Monto:            {m.total if m.total else '(no encontrado)'}  [{m.metodo}]"
          + (f"  descartados: {m.excluidos}" if m.excluidos else ""))
    print(f"  Deuda elegible:   {list(r['tipos']['elegibles']) or '-'}")
    print(f"  Deuda NO elegible:{list(r['tipos']['no_elegibles']) or '-'}")
    print(f"  Señal de deuda:   {r['senal_deuda']}")
    print(f"  Pide Consejero:   {r['quiere_consejero']}")
    if r["riesgos"]:
        for nombre, peso, terms in r["riesgos"]:
            print(f"  RIESGO: {nombre} (peso {peso}) por {terms}")
    else:
        print("  Riesgos:          -")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--leads"]:
        leads = json.load(open(ROOT / "data" / "leads_chat.json", encoding="utf-8"))
        for l in leads:
            r = analizar(l["mensaje"])
            nombres = [f"{n}({p})" for n, p, _ in r["riesgos"]]
            print(f"{l['id']}  monto={str(r['monto'].total):>7}  riesgos={nombres or '-'}")
    elif args:
        mostrar(" ".join(args))
    else:
        print("Escribe un mensaje (vacío para salir). Puedes editar config/rules.yaml entre mensajes.")
        while (t := input("\n> ").strip()):
            mostrar(t)
