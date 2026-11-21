"""Choice of the main evidence by specificity (agreement.specificity, engine._decide). All publishers, people
and places are invented. Pure text, no models.

Run:  backend/.venv/bin/python backend/tests/test_main_evidence.py      (or pytest backend/tests)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401

from prawdowid import engine  # noqa: E402
from prawdowid.agreement import specificity  # noqa: E402
from prawdowid.claims import Claim  # noqa: E402
from prawdowid.schemas import SourceDoc  # noqa: E402

USER = "Czy film udostępniony przez Jana Kowalczyka w 2031 r. pokazywał protest pod Pałacem Zimowym?"


def fc(id_, publisher, title, claim, text=None, author=None, published="2031-05-01") -> SourceDoc:
    return SourceDoc(id=id_, source_type="factcheck", publisher=publisher, domain="example.invalid",
                     url=f"https://example.invalid/{id_}", title=title, claim=claim, claim_author=author,
                     verdict="false", verdict_raw="Fałsz", text=text or f"{title}\n{claim}", published_at=published)


SPECIFIC = fc("s", "Redakcja A", "Kowalczyk udostępnia stare nagranie z protestu",
              "Policja rozgania protestujących pod Pałacem Zimowym.", author="Jan Kowalczyk",
              text="Policja rozgania protestujących pod Pałacem Zimowym. Nagranie pochodzi z 2024 roku.")
SIMILAR = fc("g", "Redakcja B", "Nagranie z koncertu krąży jako protest",
             "Nagranie pokazuje protestujących pod Pałacem Zimowym")


class Specificity(unittest.TestCase):
    def test_counts_shared_details(self):
        self.assertGreater(specificity(USER, f"{SPECIFIC.title}. {SPECIFIC.claim}. {SPECIFIC.claim_author}"),
                           specificity(USER, f"{SIMILAR.title}. {SIMILAR.claim}"))

    def test_another_date_does_not_count_against(self):
        base = "Nagranie pokazuje protestujących pod Pałacem Zimowym"
        self.assertEqual(specificity(USER, base + " w 2024 r."), specificity(USER, base))
        self.assertEqual(specificity(USER, base + " w 2031 r."), specificity(USER, base) + 1)

    def test_media_and_event_kinds(self):
        self.assertEqual(specificity("Zdjęcie pokazuje powódź", "To zdjęcie nie przedstawia powodzi"), 2)
        self.assertEqual(specificity("Zdjęcie pokazuje powódź", "Film z koncertu"), 0)
        self.assertEqual(specificity("Marszałek powiedział", "marsz przeszedł ulicami"), 0)  # not a march


class MainEvidence(unittest.TestCase):
    def setUp(self):
        self._docs = engine.INDEX.docs

    def tearDown(self):
        engine.INDEX.docs = self._docs

    def test_more_specific_source_is_main_even_if_less_similar(self):
        engine.INDEX.docs = [SIMILAR, SPECIFIC]
        cands = [engine._Cand(doc_idx=0, chunk_text="", retrieval=0.84, cos=0.84, is_claim_match=True, claim_cos=0.84,
                              fragment=SIMILAR.claim),
                 engine._Cand(doc_idx=1, chunk_text="", retrieval=0.82, cos=0.82, is_claim_match=True, claim_cos=0.82,
                              fragment=SPECIFIC.claim)]
        claim = Claim(text=USER, query=USER, kind="fakt", score=1.0)
        res = engine._decide(claim, [], cands, [], [], [], False)
        self.assertEqual(res.verdict, "falszywe")
        self.assertIn("Redakcja A", res.explanation)

    def test_without_specific_details_the_stronger_match_stays_main(self):
        a = fc("a", "Redakcja A", "Szczepionka Q zawiera mikroczipy", "Szczepionka Q zawiera mikroczipy")
        b = fc("b", "Redakcja B", "Szczepionka Q zawiera mikroczipy", "Szczepionka Q zawiera mikroczipy")
        engine.INDEX.docs = [a, b]
        cands = [engine._Cand(doc_idx=0, chunk_text="", retrieval=0.8, cos=0.8, is_claim_match=True, claim_cos=0.80),
                 engine._Cand(doc_idx=1, chunk_text="", retrieval=0.9, cos=0.9, is_claim_match=True, claim_cos=0.93)]
        claim = Claim(text="Szczepionka Q zawiera mikroczipy", query="Szczepionka Q zawiera mikroczipy", kind="fakt", score=1.0)
        res = engine._decide(claim, [], cands, [], [], [], False)
        self.assertIn("Redakcja B", res.explanation)


if __name__ == "__main__":
    unittest.main()
