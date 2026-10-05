"""Pruebas del clasificador con los 40 leads reales.

EXPECTED es mi juicio de negocio, escrito a mano ANTES de ver la salida del sistema.
Ejecutar:  python -m unittest -v
"""
import copy
import json
import unittest
from pathlib import Path

from app.classifier import ESCALATE, IGNORE, RESPOND, classify
from app.rules import load_rules

ROOT = Path(__file__).resolve().parent.parent
RULES = load_rules(ROOT / "config" / "rules.yaml")
LEADS = {int(l["id"].split("-")[1]): l["mensaje"] for l in json.load(open(ROOT / "data" / "leads_chat.json", encoding="utf-8"))}

R, I, E = RESPOND, IGNORE, ESCALATE
EXPECTED = {
    1001: R, 1002: R, 1003: E, 1004: I, 1005: E, 1006: R, 1007: E, 1008: R, 1009: I, 1010: E,
    1011: R, 1012: R, 1013: E, 1014: E, 1015: E, 1016: R, 1017: E, 1018: R, 1019: I, 1020: E,
    1021: R, 1022: R, 1023: E, 1024: I, 1025: R, 1026: R, 1027: R, 1028: I, 1029: E, 1030: E,
    1031: R, 1032: E, 1033: R, 1034: E, 1035: E, 1036: R, 1037: I, 1038: R, 1039: R, 1040: E,
}
# Motivos que quiero verificar explícitamente (los casos con más criterio)
EXPECTED_REASON = {
    1003: "legal", 1005: "promesa_de_ahorro", 1006: "monto_bajo", 1007: "deuda_no_elegible",
    1009: "spam", 1011: "precalificado", 1013: "fraude_o_desconfianza", 1014: "deuda_de_negocio",
    1020: "deuda_no_elegible", 1022: "precalificado", 1029: "programa_previo", 1032: "precio_o_tarifas",
    1033: "monto_bajo", 1034: "riesgo_emocional", 1035: "riesgo_emocional",
}


class TestLeads(unittest.TestCase):
    def test_decision_for_all_40_leads(self):
        for n, expected in EXPECTED.items():
            with self.subTest(lead=n):
                self.assertEqual(classify(LEADS[n], RULES).decision, expected)

    def test_reason_of_key_cases(self):
        for n, reason in EXPECTED_REASON.items():
            with self.subTest(lead=n):
                self.assertEqual(classify(LEADS[n], RULES).reason, reason)

    def test_prequalification_data(self):
        d = classify(LEADS[1012], RULES)
        self.assertEqual(d.prequal["monto_usd"], 5500)
        self.assertEqual(d.prequal["tipos_deuda"], ["tarjeta_credito"])
        self.assertTrue(d.prequal["quiere_consejero"])
        self.assertEqual(classify(LEADS[1038], RULES).prequal["faltan"], ["tipo_deuda"])

    def test_soft_risk_is_flagged_not_escalated(self):
        d = classify(LEADS[1008], RULES)                       # "no quiero perder mi casa"
        self.assertEqual(d.decision, RESPOND)
        self.assertIn("vivienda_en_riesgo", d.prequal["banderas"])


class TestExtraCases(unittest.TestCase):
    def check(self, text, decision, reason=None):
        d = classify(text, RULES)
        self.assertEqual(d.decision, decision, d.explanation)
        if reason:
            self.assertEqual(d.reason, reason)
        return d

    def test_sin_embargo_does_not_escalate(self):
        self.check("Debo $8,000 en tarjetas, sin embargo puedo pagar algo", RESPOND)

    def test_real_embargo_escalates(self):
        self.check("Debo $8,000 en tarjetas, sin embargo me van a embargar", ESCALATE, "legal")

    def test_greeting_is_answered_ambiguous_is_escalated(self):
        self.check("hola", RESPOND, "faltan_datos")
        self.check("info", RESPOND, "faltan_datos")
        self.check("asdfgh qwerty", ESCALATE, "mensaje_ambiguo")
        self.check("Hello, do you speak English?", ESCALATE, "mensaje_ambiguo")

    def test_noise_is_ignored(self):
        self.check("ok", IGNORE)
        self.check("👍", IGNORE, "sin_contenido")
        self.check("", IGNORE, "sin_contenido")

    def test_opt_out_marks_do_not_contact(self):
        d = self.check("Quiero darme de baja de sus mensajes", IGNORE, "baja_voluntaria")
        self.assertTrue(d.do_not_contact)

    def test_sensitive_data_is_never_echoed(self):
        d = self.check("Les pasé mi número de seguro social 123-45-6789", ESCALATE, "datos_sensibles")
        self.assertNotIn("123-45-6789", json.dumps(d.to_dict(), ensure_ascii=False))

    def test_typo_in_risk_word(self):
        self.check("me van a declarar bancarrrota", ESCALATE, "legal")


class TestRulesChangeBehavior(unittest.TestCase):
    """El 'cambio de regla' del video: mismo mensaje, otra decisión, solo cambiando reglas."""

    def test_lower_minimum_amount(self):
        rules = copy.deepcopy(RULES)
        self.assertEqual(classify(LEADS[1006], rules).reason, "monto_bajo")        # $1,200 con mínimo 5,000
        rules["reglas_monto"]["monto_minimo_usd"] = 1000
        self.assertEqual(classify(LEADS[1006], rules).reason, "precalificado")

    def test_low_amount_action(self):
        rules = copy.deepcopy(RULES)
        rules["reglas_monto"]["accion_monto_bajo"] = "ignorar"
        self.assertEqual(classify(LEADS[1006], rules).decision, IGNORE)
        rules["reglas_monto"]["accion_monto_bajo"] = "escalar_humano"
        self.assertEqual(classify(LEADS[1006], rules).decision, ESCALATE)

    def test_new_keyword_escalates(self):
        rules = copy.deepcopy(RULES)
        text = "Debo $9,000 en tarjetas y tengo una cita en el consulado"
        self.assertEqual(classify(text, rules).decision, RESPOND)
        rules["categorias_escalar_humano"]["inmigracion"] = {"peso": 7, "terminos": ["consulado"]}
        self.assertEqual(classify(text, rules).reason, "inmigracion")


if __name__ == "__main__":
    unittest.main()
