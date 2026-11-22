"""Indicators with competing definitions (measures.py) and the numeric-mismatch guard in engine._other_definition.
All cards, periods and numbers below are invented. Pure text, no models.

Run:  backend/.venv/bin/python backend/tests/test_definitional_measures.py      (or pytest backend/tests)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401

from prawdowid import engine, measures  # noqa: E402
from prawdowid.schemas import SourceDoc  # noqa: E402


def card(id_, publisher, title, text) -> SourceDoc:
    return SourceDoc(id=id_, source_type="official", publisher=publisher, domain="example.invalid",
                     url=f"https://example.invalid/{id_}", title=title, text=text, published_at="2031-05-01")


CPI = card("cpi", "Urząd Statystyczny", "Inflacja CPI w Polsce — marzec 2031: 2,4% r/r (GUS)",
           "Inflacja CPI w Polsce w marcu 2031 r. wyniosła 2,4% r/r (wskaźnik cen towarów i usług konsumpcyjnych "
           "102,4). Uwaga: to nie jest zharmonizowany wskaźnik HICP.")
HICP_SAME = card("hicp", "Urząd UE", "Inflacja HICP 2031-03: Polska 2,9% vs UE 2,0% (Eurostat)",
                 "Zharmonizowany wskaźnik cen konsumpcyjnych (HICP) — roczna stopa zmian w 2031-03: Polska 2,9%, "
                 "średnia UE-27 2,0%. Uwaga: HICP różni się metodologicznie od CPI GUS.")
HICP_OTHER_MONTH = card("hicp2", "Urząd UE", "Inflacja HICP 2031-07: Polska 2,9% vs UE 2,0% (Eurostat)",
                        "Zharmonizowany wskaźnik cen konsumpcyjnych (HICP) — roczna stopa zmian w 2031-07: Polska "
                        "2,9%, średnia UE-27 2,0%.")
REG = card("reg", "Urząd Statystyczny", "Stopa bezrobocia rejestrowanego w Polsce — marzec 2031: 7,7% (GUS)",
           "Stopa bezrobocia rejestrowanego w Polsce na koniec okresu (marzec 2031 r.) wyniosła 7,7%. Uwaga: to nie "
           "jest stopa bezrobocia BAEL/Eurostat.")
LFS = card("lfs", "Urząd UE", "Bezrobocie (Eurostat) 2031-03: Polska 4,1% vs UE 6,0%",
           "Stopa bezrobocia (metodologia BAEL/ILO, wyrównana sezonowo) w 2031-03: Polska 4,1%, UE-27 6,0%. "
           "Uwaga: to inna miara niż stopa bezrobocia rejestrowanego.")
WAGE = card("wage", "Urząd Statystyczny", "Przeciętne wynagrodzenie w sektorze przedsiębiorstw — marzec 2031: 12 345,67 zł (GUS)",
            "Przeciętne miesięczne nominalne wynagrodzenie brutto w sektorze przedsiębiorstw w marcu 2031 r. wyniosło "
            "12 345,67 zł. To nie jest przeciętne wynagrodzenie w całej gospodarce narodowej.")
DEBT = card("debt", "Urząd UE", "Dług publiczny (EDP) 2031: Polska 71,0% PKB (Eurostat)",
            "Dług sektora instytucji rządowych i samorządowych (dług publiczny wg definicji UE/EDP) w 2031: Polska "
            "71,0% PKB. Uwaga: definicja krajowa (konstytucyjna) różni się od unijnej.")
GDP = card("gdp", "Urząd UE", "Wzrost PKB 2031: Polska 2,2% vs UE 1,1% (Eurostat)",
           "Realny wzrost PKB w 2031: Polska 2,2%, UE-27 1,1%.")
FX = card("fx", "Bank centralny", "Kurs średni EUR/PLN z 2031-03-14: 4,1234 zł", "Kurs średni EUR/PLN z 2031-03-14: 4,1234 zł.")
ACT = card("act", "Dziennik Ustaw", "Rozporządzenie Rady Ministrów z dnia 1 września 2030 r. w sprawie wysokości "
           "minimalnego wynagrodzenia za pracę w 2031 r.", "Od dnia 1 stycznia 2031 r. minimalne wynagrodzenie za "
           "pracę wynosi 5555 zł.")


def variants(doc: SourceDoc) -> dict[str, str]:
    p = measures.card_profile(doc.title, doc.text)
    return {dim.key: v.name for dim, v in p[1]} if p else {}


class CardProfile(unittest.TestCase):
    def test_definition_read_from_title_and_first_sentence_only(self):
        # each card's later "Uwaga" sentence names the OTHER definition; it must not make the card ambiguous
        self.assertEqual(variants(CPI)["wskaźnik"], "CPI (GUS)")
        self.assertEqual(variants(HICP_SAME)["wskaźnik"], "HICP (Eurostat)")
        self.assertEqual(variants(REG)["metoda"], "bezrobocie rejestrowane (GUS, urzędy pracy)")
        self.assertEqual(variants(LFS)["metoda"], "bezrobocie wg BAEL/LFS (Eurostat)")
        self.assertEqual(variants(DEBT)["definicja"], "definicja unijna (EDP)")
        self.assertEqual(variants(GDP)["ceny"], "realnie (ceny stałe)")
        w = variants(WAGE)
        self.assertEqual((w["brutto_netto"], w["zakres"], w["statystyka"]), ("brutto", "sektor przedsiębiorstw", "średnia"))
        self.assertEqual(variants(CPI)["zakres"], "inflacja ogółem")  # no "bazowa" → headline

    def test_cards_outside_the_table(self):
        self.assertIsNone(measures.card_profile(FX.title, FX.text))
        self.assertIsNone(measures.card_profile(ACT.title, ACT.text))  # a legal act sets the amount by law


class ClaimNamesDefinition(unittest.TestCase):
    def test_other_definition_named_is_incompatible(self):
        self.assertFalse(measures.compatible("Inflacja HICP w marcu 2031 wyniosła 2,9%", CPI.title, CPI.text))
        self.assertFalse(measures.compatible("Inflacja bazowa w marcu 2031 wyniosła 1,8%", CPI.title, CPI.text))
        self.assertFalse(measures.compatible("Bezrobocie według BAEL w marcu 2031 wynosiło 7,7%", REG.title, REG.text))
        self.assertFalse(measures.compatible("Średnia pensja netto w marcu 2031 to 9000 zł", WAGE.title, WAGE.text))
        self.assertFalse(measures.compatible("Mediana wynagrodzeń w marcu 2031 to 9000 zł", WAGE.title, WAGE.text))
        self.assertFalse(measures.compatible("Państwowy dług publiczny w 2031 r. wyniósł 60% PKB", DEBT.title, DEBT.text))
        self.assertFalse(measures.compatible("PKB nominalnie wzrósł w 2031 r. o 6%", GDP.title, GDP.text))

    def test_same_or_no_definition_is_compatible(self):
        for claim, doc in [("Inflacja w marcu 2031 wyniosła 5%", CPI), ("GUS: inflacja w marcu 2031 to 2,4%", CPI),
                           ("Bezrobocie w marcu 2031 wynosiło 5%", LFS), ("Płace w marcu 2031 wynosiły 9000 zł", WAGE),
                           ("Kurs euro 14 marca 2031 wynosił 4,50 zł", FX)]:
            self.assertTrue(measures.compatible(claim, doc.title, doc.text), claim)

    def test_unnamed_dimensions(self):
        names = lambda claim, doc: [d.key for d, _ in measures.unnamed(claim, doc.title, doc.text)]  # noqa: E731
        self.assertEqual(names("Inflacja w marcu 2031 wyniosła 5%", CPI), ["wskaźnik"])
        self.assertEqual(names("Według GUS inflacja w marcu 2031 wyniosła 5%", CPI), [])
        self.assertEqual(names("Inflacja CPI w marcu 2031 wyniosła 5%", CPI), [])
        self.assertEqual(names("Bezrobocie w marcu 2031 wynosiło 5%", REG), ["metoda"])
        self.assertEqual(names("Bezrobocie rejestrowane w marcu 2031 wynosiło 5%", REG), [])
        self.assertEqual(names("Przeciętne wynagrodzenie brutto w marcu 2031 to 9000 zł", WAGE), ["zakres"])
        self.assertEqual(names("Kurs euro 14 marca 2031 wynosił 4,50 zł", FX), [])


class OtherDefinitionGuard(unittest.TestCase):
    """A mismatch with one definition's card refutes the claim only if the claim names that definition, or every
    other definition has a card for the same period and none gives the claimed number."""

    def setUp(self):
        self._docs = engine.INDEX.docs

    def tearDown(self):
        engine.INDEX.docs = self._docs

    def check(self, claim: str, doc: SourceDoc, indexed: list[SourceDoc]) -> str:
        engine.INDEX.docs = indexed
        self.assertEqual(engine.numeric_stance(claim, f"{doc.title}. {doc.text}"), "niezgodne", "precondition")
        return engine._other_definition(claim, doc)

    def test_no_card_for_the_other_definition_abstains(self):
        note = self.check("Inflacja w marcu 2031 r. wyniosła 2,9%", CPI, [CPI, REG, FX])
        self.assertIn("nie mam danych", note)
        self.assertIn("HICP", note)

    def test_other_definition_card_for_another_period_does_not_count(self):
        self.assertIn("nie mam danych", self.check("Inflacja w marcu 2031 r. wyniosła 2,9%", CPI, [CPI, HICP_OTHER_MONTH]))

    def test_other_definition_gives_the_number(self):
        note = self.check("Inflacja w marcu 2031 r. wyniosła 2,9%", CPI, [CPI, HICP_SAME])
        self.assertIn("HICP", note)
        self.assertNotIn("nie mam danych", note)
        note = self.check("Bezrobocie w marcu 2031 r. wynosiło 4,1%", REG, [REG, LFS])
        self.assertIn("BAEL", note)

    def test_no_definition_gives_the_number_mismatch_stands(self):
        self.assertEqual(self.check("Inflacja w marcu 2031 r. wyniosła 9,5%", CPI, [CPI, HICP_SAME]), "")
        self.assertEqual(self.check("Bezrobocie w marcu 2031 r. wynosiło 12%", REG, [REG, LFS]), "")

    def test_claim_names_the_definition_mismatch_stands(self):
        self.assertEqual(self.check("Według GUS inflacja w marcu 2031 r. wyniosła 2,9%", CPI, [CPI]), "")
        self.assertEqual(self.check("Stopa bezrobocia rejestrowanego w marcu 2031 r. wynosiła 4,1%", REG, [REG]), "")

    def test_indicator_without_competing_definitions(self):
        self.assertEqual(self.check("Kurs średni EUR/PLN z 2031-03-14 wynosił 4,50 zł", FX, [FX]), "")


if __name__ == "__main__":
    unittest.main()
