"""claim_kind must read text typed without Polish diacritics the way it reads the same text typed with them.

Run:  backend/.venv/bin/python backend/tests/test_claim_kind_diacritics.py      (or pytest backend/tests)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prawdowid.textutil import claim_kind  # noqa: E402

PLAIN = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")

CASES = [
    # past tense next to a future form: a report, not a prediction
    ("Policjant, który dopuścił się przestępstwa, zostanie zwolniony z aresztu i wróci do pracy.", "fakt"),
    ("Rząd ogłosił, że od stycznia będzie nowy podatek.", "fakt"),
    ("Ministerstwo wprowadziło opłatę, która wkrótce obejmie wszystkich kierowców.", "fakt"),
    # predictions
    ("Wkrótce benzyna będzie po dziesięć złotych.", "prognoza"),
    ("Za rok bezrobocie będzie rosło.", "prognoza"),
    ("W przyszłym roku ceny prądu zostaną zamrożone.", "prognoza"),
    # opinions
    ("Uważam, że ten rząd jest najgorszy w historii.", "opinia"),
    ("Moim zdaniem to żenujące widowisko.", "opinia"),
    ("To był głupi i okropny pomysł.", "opinia"),
    # questions and plain facts
    ("Czy rząd zlikwidował ulgę na dzieci?", "pytanie"),
    ("Inflacja w marcu wyniosła 3 procent.", "fakt"),
    ("Skandal we Wrocławiu! Będzie nowy podatek od deszczu, a radni przyjęli go bez dyskusji.", "fakt"),
]


class ClaimKindWithoutDiacritics(unittest.TestCase):
    def test_same_kind_with_and_without_diacritics(self):
        for text, kind in CASES:
            self.assertEqual(claim_kind(text), kind, text)
            self.assertEqual(claim_kind(text.translate(PLAIN)), kind, text.translate(PLAIN))
            self.assertEqual(claim_kind(text.translate(PLAIN).lower()), kind, text.translate(PLAIN).lower())

    def test_text_with_diacritics_keeps_the_exact_patterns(self):
        # "czuje" (he feels) is not the opinion marker "czuję" (I feel); "3 maja" is not the verb "mają"
        self.assertEqual(claim_kind("Premier czuje się już dobrze i wróci jutro do pracy, będzie konferencja."), "prognoza")
        self.assertEqual(claim_kind("Minister czuje się dobrze po operacji, którą przeszedł w środę."), "fakt")


if __name__ == "__main__":
    unittest.main()
