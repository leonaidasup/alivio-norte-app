import unittest
from pathlib import Path

from app.rules import load_rules
from app.textutils import find_terms, neutralizar

RULES = load_rules(Path(__file__).resolve().parent.parent / "config" / "rules.yaml")
LEGAL = RULES["categorias_escalar_humano"]["legal"]["terminos"]
NEUTRAS = RULES["frases_neutras"]


def legal_hits(txt):
    return find_terms(neutralizar(txt, NEUTRAS), LEGAL)


class TestFrasesNeutras(unittest.TestCase):
    def test_sin_embargo_no_dispara(self):
        self.assertEqual(legal_hits("Debo $8,000 en tarjetas, sin embargo puedo pagar algo"), [])
        self.assertEqual(legal_hits("Sin Embargo, quiero saber más"), [])

    def test_embargo_real_si_dispara(self):
        self.assertTrue(legal_hits("me van a embargar el sueldo"))
        self.assertTrue(legal_hits("tengo orden de embargo"))

    def test_frase_neutra_no_tapa_riesgo_real(self):
        self.assertTrue(legal_hits("sin embargo me van a embargar la cuenta"))

    def test_otras_frases(self):
        self.assertEqual(legal_hits("es cuestión de oferta y demanda"), [])
        self.assertTrue(legal_hits("el banco puso una demanda"))


if __name__ == "__main__":
    unittest.main()
