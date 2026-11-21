"""Subject gate for official cards (engine.same_subject): synonyms, abbreviations, inflected forms, period
expressions and currency names. All titles, claims, periods and numbers are invented. Pure text, no models.

Run:  backend/.venv/bin/python backend/tests/test_subject_gate.py      (or pytest backend/tests)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401

from prawdowid.engine import _date_keys, same_subject  # noqa: E402


class Synonyms(unittest.TestCase):
    def test_same_indicator_named_differently(self):
        for claim, title in [
            ("W 2031 r. w Polsce zmarło 401 000 osób.", "Liczba zgonów w Polsce — 2031: 401 000 (GUS BDL)"),
            ("W 2031 roku umarło w Polsce ponad 400 tys. ludzi", "Liczba zgonów w Polsce — 2031: 401 000 (GUS BDL)"),
            ("W 2031 r. urodziło się 200 tys. dzieci", "Liczba urodzeń żywych w Polsce — 2031: 200 100 (GUS BDL)"),
            ("Polska miała w 2031 r. 36 mln mieszkańców", "Liczba ludności Polski — 2031: 36 000 000 osób (GUS BDL)"),
            ("Produkt krajowy brutto wzrósł w 2031 r. o 2%", "Wzrost PKB 2031: Polska 2,2% vs UE 1,1% (Eurostat)"),
            ("Zadłużenie Polski w 2031 r. przekroczyło 70% PKB", "Dług publiczny (EDP) 2031: Polska 71,0% PKB (Eurostat)"),
            ("Średnia pensja w marcu 2031 to 12 000 zł", "Przeciętne wynagrodzenie w sektorze przedsiębiorstw — marzec 2031: 12 345,67 zł (GUS)"),
        ]:
            self.assertTrue(same_subject(claim, title), (claim, title))

    def test_legal_act_named_by_its_common_name(self):
        act = ("Rozporządzenie Rady Ministrów z dnia 1 września 2031 r. w sprawie wysokości minimalnego wynagrodzenia "
               "za pracę oraz wysokości minimalnej stawki godzinowej w 2032 r.")
        self.assertTrue(same_subject("Płaca minimalna od stycznia 2032 roku wyniesie 7100 zł brutto", act))
        self.assertFalse(same_subject("Płaca minimalna od stycznia 2031 roku wyniesie 7100 zł brutto", act))  # other year

    def test_different_indicators_stay_apart(self):
        for claim, title in [
            ("W 2031 r. urodziło się 200 tys. dzieci", "Liczba zgonów w Polsce — 2031: 401 000 (GUS BDL)"),
            ("Bezrobocie w marcu 2031 wynosiło 5%", "Inflacja CPI w Polsce — marzec 2031: 2,4% r/r (GUS)"),
            ("Ukraina nie płaci za gaz od marca 2031", "Przeciętne wynagrodzenie w sektorze przedsiębiorstw — marzec 2031: 12 345,67 zł (GUS)"),
        ]:
            self.assertFalse(same_subject(claim, title), (claim, title))


class Currencies(unittest.TestCase):
    NOK = "Kurs średni NBP NOK/PLN z 2031-01-05: 0,4000 zł"
    CZK = "Kurs średni NBP CZK/PLN z 2031-01-05: 0,2000 zł"
    USD = "Kurs średni NBP USD/PLN z 2031-01-05: 3,9000 zł"
    CHF = "Kurs średni NBP CHF/PLN z 2031-01-05: 4,7000 zł"

    def test_crowns_need_their_country(self):
        self.assertTrue(same_subject("5 stycznia 2031 r. korona norweska kosztowała 0,40 zł", self.NOK))
        self.assertFalse(same_subject("5 stycznia 2031 r. korona czeska kosztowała 0,40 zł", self.NOK))
        self.assertTrue(same_subject("5 stycznia 2031 r. za koronę czeską płacono 0,20 zł", self.CZK))

    def test_other_dollars_are_not_usd(self):
        self.assertTrue(same_subject("Kurs dolara 5 stycznia 2031 r. wynosił 3,90 zł", self.USD))
        self.assertTrue(same_subject("5 stycznia 2031 r. dolar amerykański kosztował 3,90 zł", self.USD))
        self.assertFalse(same_subject("5 stycznia 2031 r. dolar kanadyjski kosztował 2,90 zł", self.USD))

    def test_inflected_names_and_codes(self):
        self.assertTrue(same_subject("Za franka szwajcarskiego 5 stycznia 2031 r. płacono 4,70 zł", self.CHF))
        self.assertTrue(same_subject("Kurs CHF 5 stycznia 2031 r. to 4,70 zł", self.CHF))
        self.assertFalse(same_subject("Kurs franka 5 stycznia 2030 r. to 4,70 zł", self.CHF))  # other year


class Periods(unittest.TestCase):
    def test_month_forms(self):
        self.assertEqual(_date_keys("dane za 09.2031")[1], {9})
        self.assertEqual(_date_keys("dane za 9/2031")[1], {9})
        self.assertEqual(_date_keys("14.09.2031 r.")[1], {9})
        self.assertEqual(_date_keys("w III kwartale 2031 r.")[1], {7, 8, 9})
        self.assertEqual(_date_keys("w I kw. 2031")[1], {1, 2, 3})
        self.assertEqual(_date_keys("Q4 2031")[1], {10, 11, 12})
        self.assertEqual(_date_keys("w drugim kwartale 2031 roku")[1], {4, 5, 6})
        self.assertEqual(_date_keys("w pierwszym półroczu 2031")[1], set(range(1, 7)))
        self.assertEqual(_date_keys("w drugiej połowie roku 2031")[1], set(range(7, 13)))
        self.assertEqual(_date_keys("Ceny prądu 2031-S1 (EUR/kWh)")[1], set(range(1, 7)))
        self.assertEqual(_date_keys("2031 rok, 4,5/2031")[1], set())  # a decimal before a slash is not a month

    def test_quarter_against_monthly_card(self):
        card = "Inflacja CPI w Polsce — wrzesień 2031: 2,4% r/r (GUS)"
        self.assertTrue(same_subject("W III kwartale 2031 r. inflacja wyniosła 2,4%", card))
        self.assertFalse(same_subject("W I kwartale 2031 r. inflacja wyniosła 2,4%", card))


if __name__ == "__main__":
    unittest.main()
