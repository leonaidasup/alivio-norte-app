"""Pruebas de la vista de estancados con los datos reales (leads + CSV sucio del partner)."""
import copy
import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.data.clean import clean_enrollments
from app.engine.rules import load_rules
from app.analytics.stalled import compute_stalled

ROOT = Path(__file__).resolve().parent.parent
LEADS = ROOT / "data" / "leads_chat.json"
PARTNER_CSV = ROOT / "data" / "partner_enrollments_dirty.csv"
RULES = load_rules(ROOT / "config" / "rules.yaml")
TODAY = date(2026, 10, 4)


class TestStalled(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        clean_enrollments(PARTNER_CSV, LEADS, today=TODAY, out_dir=cls.tmp.name)
        cls.clean = Path(cls.tmp.name) / "enrollments_clean.csv"
        cls.quarantine = Path(cls.tmp.name) / "enrollments_quarantine.csv"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def rows(self, today=TODAY, rules=RULES):
        return compute_stalled(LEADS, self.clean, self.quarantine, rules, today)[0]

    def ids(self, **kw):
        return {r["lead_id"] for r in self.rows(**kw)}

    def test_ignored_leads_never_appear(self):
        ignored = {f"LEAD-{n}" for n in (1004, 1009, 1019, 1024, 1028, 1037)}
        self.assertFalse(self.ids() & ignored)

    def test_closed_enrollments_never_appear(self):
        self.assertNotIn("LEAD-1001", self.ids())    # inscripción completada
        self.assertNotIn("LEAD-1032", self.ids())    # inscripción cancelada

    def test_enrollments_that_only_exist_in_quarantine(self):
        pending = {r["lead_id"] for r in self.rows() if r["situacion"] == "inscripcion_por_confirmar"}
        self.assertEqual(pending, {"LEAD-1008", "LEAD-1021", "LEAD-1027", "LEAD-1029"})
        self.assertTrue(all(r["prioridad"] == "alta" for r in self.rows() if r["situacion"] == "inscripcion_por_confirmar"))

    def test_emotional_risk_goes_first(self):
        rows = self.rows()
        self.assertEqual(rows[0]["lead_id"], "LEAD-1035")
        prios = [r["prioridad"] for r in rows[1:]]
        self.assertEqual(prios, sorted(prios, key=lambda p: {"alta": 0, "media": 1, "baja": 2}[p]))

    def test_in_process_respects_its_deadline(self):
        self.assertIn("LEAD-1011", self.ids())                             # en proceso desde el 28/09 (6 días)
        self.assertNotIn("LEAD-1011", self.ids(today=date(2026, 10, 1)))   # 3 días: todavía en plazo

    def test_recent_leads_are_not_stalled_yet(self):
        sin = lambda today: [r for r in self.rows(today=today) if r["situacion"] == "sin_inscripcion"]
        self.assertEqual(len(sin(date(2026, 9, 29))), 0)                   # todos escribieron hace 0-1 días
        self.assertEqual(len(sin(TODAY)), 15)

    def test_deadlines_come_from_the_rules(self):
        rules = copy.deepcopy(RULES)
        rules["estancados"] = {"dias_sin_contacto": 6}
        strict = [r for r in self.rows(rules=rules) if r["situacion"] == "sin_inscripcion"]
        self.assertTrue(strict)
        self.assertTrue(all(r["dias_sin_avance"] >= 6 for r in strict))
        self.assertLess(len(strict), 15)


if __name__ == "__main__":
    unittest.main()