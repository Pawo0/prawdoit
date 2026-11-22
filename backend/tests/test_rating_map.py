"""Rating labels -> normalised class -> Prawdowid verdict, through all three maps: ingest/common.map_verdict (the
harvested corpus), websearch.map_rating (live Google ratings) and engine.FC_TO_VERDICT. The label vocabulary below is
every distinct rating label found in data/corpus on 2026-11-22 (publishers' own words, not eval answers); labels that
were whole sentences put into the rating field are replaced by invented sentences of the same shape.

Run:  backend/.venv/bin/python backend/tests/test_rating_map.py      (or pytest backend/tests)
"""
from __future__ import annotations

import ast
import sys
import types
import unicodedata
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401

from prawdowid import engine, websearch  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
# ingest/common.py needs the harvesters' dependencies; only its rating map is loaded (by name, from its source)
_NAMES = {"_norm", "_VERDICT_RULES", "_NO_VERDICT", "_NOT_A_RATING", "map_verdict"}
_tree = ast.parse((ROOT / "ingest" / "common.py").read_text(encoding="utf-8"))
_body = [n for n in _tree.body if getattr(n, "name", None) in _NAMES
         or any(getattr(t, "id", None) in _NAMES for t in getattr(n, "targets", [getattr(n, "target", None)]))]
_ns: dict = {"unicodedata": unicodedata}
exec(compile(ast.Module(body=_body, type_ignores=[]), "ingest/common.py", "exec"), _ns)  # noqa: S102
common = types.SimpleNamespace(**{k: _ns[k] for k in _NAMES})

LABELS = {
    # rating labels as they appear in the corpus
    "Fałsz": "false", "Falsz": "false", "Fałśz": "false", "Prawda": "true", "Manipulacja": "misleading",
    "Disinformation (EUvsDisinfo)": "false", "Brakujący kontekst": "misleading", "Brak kontekstu": "misleading",
    "Częściowa prawda": "mixed", "Częściowy fałsz": "mixed", "Częściowy Fałsz": "mixed", "Częściowo fałszywe": "mixed",
    "W większości fałsz": "mixed", "W większości prawda": "mixed", "Nieweryfikowalne": "unverifiable",
    "Brak dowodów": "unverifiable", "Niedające się zweryfikować": "unverifiable", "Mylące": "misleading",
    "Przerobione zdjęcie": "false", "Przerobione Zdjęcie": "false", "Przerobione zdjęcia": "false",
    "Przerobiony film": "false", "Przerobione wideo": "false", "Przerobione nagranie": "false",
    "Przerobiony obraz": "false", "Przerobiona grafika": "false", "Przerobione zdjęcie lub film": "false",
    "Obraz AI": "false", "Scam": "false", "Fake News": "false", "Oszustwo": "false",
    # not a rating of a claim: context only
    "Analiza": None, "Raport": None, "Satyra": None, "Satyra / Żart": None, "Satyra/Żart": None,
    "Fact-Checked": None, "Zrealizowane": None,
    # sentences in the rating field (invented, same shape as the corpus ones)
    "Fałsz, ta szczepionka nie powoduje opisanych skutków": "false",
    "Informację uznajemy za prawdziwą, ponieważ według raportu urzędu liczba wzrosła": "true",
    "Mieszkańcy nie powinni płacić za nową drogę z własnych podatków": None,
    # English labels (live Google ratings)
    "Mostly false": "mixed", "Mostly true": "mixed", "Partly false": "mixed", "False": "false", "True": "true",
    "Missing context": "misleading", "Satire": None,
    "": None, None: None,
}


class RatingMap(unittest.TestCase):
    def test_every_label_in_both_maps(self):
        for label, expected in LABELS.items():
            self.assertEqual(common.map_verdict(label), expected, f"ingest: {label!r}")
            self.assertEqual(websearch.map_rating(label), expected, f"websearch: {label!r}")

    def test_the_two_maps_use_the_same_lists(self):
        self.assertEqual([tuple(x) for x in common._VERDICT_RULES], websearch._VERDICT_RULES)
        self.assertEqual(tuple(common._NO_VERDICT), tuple(websearch._NO_VERDICT))
        self.assertEqual(common._NOT_A_RATING, websearch._NOT_A_RATING)

    def test_every_class_has_a_verdict_and_non_ratings_have_none(self):
        expected = {"false": "falszywe", "true": "potwierdzone", "misleading": "wprowadzajace_w_blad",
                    "mixed": "wprowadzajace_w_blad", "unverifiable": "brak_dowodow"}
        for cls in {v for v in LABELS.values() if v}:
            self.assertEqual(engine.FC_TO_VERDICT[cls], expected[cls], cls)
        self.assertIsNone(engine.FC_TO_VERDICT.get(""))  # a record without a class is never decisive

    def test_a_sentence_mentioning_a_report_still_rates(self):
        self.assertEqual(common.map_verdict("Raport"), None)
        self.assertEqual(common.map_verdict("Prawda, według raportu urzędu"), "true")


if __name__ == "__main__":
    unittest.main()
