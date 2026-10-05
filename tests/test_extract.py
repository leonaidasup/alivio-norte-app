"""Pruebas del Paso 1 con los 40 leads reales.  Ejecutar:  python -m unittest -v"""
import json
import unittest
from pathlib import Path

from app.engine.extract import detect_debt_types, extract_amount, has_debt_signal, wants_counselor
from app.engine.rules import load_rules
from app.engine.textutils import find_terms

ROOT = Path(__file__).resolve().parent.parent
RULES = load_rules(ROOT / "config" / "rules.yaml")
LEADS = {l["id"]: l for l in json.load(open(ROOT / "data" / "leads_chat.json", encoding="utf-8"))}

ESPERADO = {
    1001: 8500, 1002: 12000, 1003: 15000, 1004: None, 1005: 6200, 1006: 1200, 1007: 120000,
    1008: 9000, 1009: None, 1010: 22000, 1011: 7400, 1012: 5500, 1013: None, 1014: 18000,
    1015: 3000, 1016: 11000, 1017: 14000, 1018: 8900, 1019: None, 1020: 25000, 1021: 6800,
    1022: 5000, 1023: 9500, 1024: None, 1025: 13400, 1026: 2500, 1027: 16000, 1028: None,
    1029: 7100, 1030: 30000, 1031: 10500, 1032: 8000, 1033: 4800, 1034: 21000, 1035: 40000,
    1036: 9200, 1037: None, 1038: 11800, 1039: 5900, 1040: 7000,
}


class TestMonto(unittest.TestCase):
    def test_los_40_leads(self):
        for n, esperado in ESPERADO.items():
            with self.subTest(lead=n):
                self.assertEqual(extract_amount(LEADS[f"LEAD-{n}"]["mensaje"]).total, esperado)

    def test_formatos_variados(self):
        casos = {"debo 12 mil en tarjetas": 12000, "unos 40k": 40000, "como 6500 en total": 6500,
                 "tengo $8k": 8000, "$1.200 de tienda": 1200, "debo $5,000 y me faltan $200": 5000}
        for txt, esp in casos.items():
            with self.subTest(txt=txt):
                self.assertEqual(extract_amount(txt).total, esp)

    def test_total_declarado_y_suma(self):
        self.assertEqual(extract_amount(LEADS["LEAD-1020"]["mensaje"]).method, "total_declarado")
        self.assertEqual(extract_amount("Tarjeta A $3,000 y tarjeta B $4,000").total, 7000)


class TestTipos(unittest.TestCase):
    def test_no_elegibles(self):
        t = detect_debt_types(LEADS["LEAD-1007"]["mensaje"], RULES)
        self.assertIn("hipoteca", t.get("ineligible", t.get("no_elegibles", {})))
        t = detect_debt_types(LEADS["LEAD-1020"]["mensaje"], RULES)
        self.assertIn("prestamo_estudiantil", t.get("ineligible", t.get("no_elegibles", {})))
        self.assertIn("tarjeta_credito", t.get("eligible", t.get("elegibles", {})))

    def test_elegibles(self):
        t = detect_debt_types(LEADS["LEAD-1011"]["mensaje"], RULES)
        self.assertIn("gastos_medicos", t.get("eligible", t.get("elegibles", {})))
        t = detect_debt_types(LEADS["LEAD-1025"]["mensaje"], RULES)
        self.assertIn("tarjeta_credito", t.get("eligible", t.get("elegibles", {})))

    def test_vehiculo_mencionado_no_es_deuda_de_auto(self):
        t = detect_debt_types(LEADS["LEAD-1008"]["mensaje"], RULES)
        self.assertEqual(t.get("ineligible", t.get("no_elegibles", {})), {})


class TestSenales(unittest.TestCase):
    def test_trabajo_con_deuda_no_es_fuera_de_alcance(self):
        m = LEADS["LEAD-1011"]["mensaje"]
        monto, tipos = extract_amount(m), detect_debt_types(m, RULES)
        self.assertTrue(has_debt_signal(m, RULES, monto, tipos))

    def test_vacantes_sin_deuda(self):
        m = LEADS["LEAD-1004"]["mensaje"]
        monto, tipos = extract_amount(m), detect_debt_types(m, RULES)
        self.assertFalse(has_debt_signal(m, RULES, monto, tipos))

    def test_quiere_consejero(self):
        quieren = {n for n in range(1001, 1041) if wants_counselor(LEADS[f"LEAD-{n}"]["mensaje"], RULES)}
        self.assertTrue({1002, 1012, 1016, 1031, 1038} <= quieren, quieren)

    def test_tolera_errores_de_tipeo(self):
        self.assertTrue(find_terms("quiero declarar bancarrrota", ["bancarrota"]))
        self.assertTrue(find_terms("es fraudulenta", ["fraud"]))
        self.assertFalse(find_terms("hola buenas", ["abogad"]))


if __name__ == "__main__":
    unittest.main()