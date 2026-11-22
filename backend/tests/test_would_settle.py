"""engine._would_settle: the source an abstention names. Invented claims only (no eval or organiser wording).
engine imports the index module but no model is loaded."""
from __future__ import annotations

import unittest

import _testenv  # noqa: F401  (runtime dir, no scheduler)
from prawdowid.engine import _would_settle, is_rule_claim  # noqa: E402


class RuleClaims(unittest.TestCase):
    def test_local_rule_names_the_council_resolution_the_area_and_the_start_date(self):
        for claim in ("Od nowego roku na rynku w Zalesiu Dolnym nie będzie można parkować.",
                      "Rada miasta Brzozowo wprowadza strefę płatnego parkowania na całym osiedlu Słoneczne.",
                      "W centrum Lipowca zakaz grillowania na balkonach wchodzi w życie w maju."):
            hint = _would_settle(claim)
            self.assertTrue(is_rule_claim(claim), claim)
            self.assertIn("uchwała rady gminy lub miasta", hint, claim)
            self.assertIn("akt prawa miejscowego", hint)
            self.assertIn("obszaru", hint)
            self.assertIn("datą wejścia w życie", hint)

    def test_national_rule_names_the_journal_of_laws(self):
        for claim in ("Od 1 marca nie wolno będzie sprzedawać napojów energetycznych na stacjach paliw.",
                      "Kierowcy mają nowy obowiązek wożenia gaśnicy w każdym samochodzie.",
                      "Od przyszłego miesiąca sklepy nie sprzedadzą papierosów osobom poniżej 21 lat."):
            hint = _would_settle(claim)
            self.assertTrue(is_rule_claim(claim), claim)
            self.assertIn("Dzienniku Ustaw", hint, claim)
            self.assertIn("ISAP", hint)
            self.assertIn("datą wejścia w życie", hint)

    def test_eu_rule_names_eur_lex(self):
        claim = "Unia Europejska wprowadza zakaz sprzedaży plastikowych kubków od 2028 roku."
        hint = _would_settle(claim)
        self.assertIn("EUR-Lex", hint)
        self.assertIn("datą wejścia w życie", hint)

    def test_statements_that_are_not_rules(self):
        for claim in ("Do centrum Zalesia dojedziesz tramwajem w dwadzieścia minut.",
                      "Burmistrz Lipowca spotkał się wczoraj z mieszkańcami.",
                      "Piłkarz nie mógł zagrać w finale z powodu kontuzji."):
            self.assertFalse(is_rule_claim(claim), claim)


class TopicHints(unittest.TestCase):
    def test_word_starts_only(self):
        # "centrum" is not "cena", "lekko" is not "lek"
        self.assertNotIn("GUS", _would_settle("Do centrum Zalesia dojedziesz tramwajem."))
        self.assertNotIn("Zdrowia", _would_settle("Pociąg był lekko spóźniony."))
        self.assertIn("GUS", _would_settle("Ceny masła wzrosły w tym roku najbardziej w Europie."))
        self.assertIn("GUS", _would_settle("Średnia płaca w Polsce jest wyższa niż w Czechach."))
        self.assertIn("Zdrowia", _would_settle("Nowy lek na grypę jest refundowany."))
        self.assertIn("MSZ", _would_settle("Ambasada w Lizbonie została zamknięta."))
        self.assertIn("IFCN", _would_settle("Słynny aktor zamieszkał na wyspie."))


if __name__ == "__main__":
    unittest.main(verbosity=2)
