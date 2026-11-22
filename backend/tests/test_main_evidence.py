"""Choice of the main evidence (engine._decide: the strongest decisive match) and the headline rows of the claim index
(index.claim_rows, CorpusIndex.match_claims). All publishers, people, places and vectors are invented. Pure text and
small arrays, no models.

Run:  backend/.venv/bin/python backend/tests/test_main_evidence.py      (or pytest backend/tests)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401

import numpy as np  # noqa: E402

from prawdowid import engine  # noqa: E402
from prawdowid.claims import Claim  # noqa: E402
from prawdowid.index import CorpusIndex, claim_rows  # noqa: E402
from prawdowid.schemas import SourceDoc  # noqa: E402

def fc(id_, publisher, title, claim, text=None, author=None, published="2031-05-01") -> SourceDoc:
    return SourceDoc(id=id_, source_type="factcheck", publisher=publisher, domain="example.invalid",
                     url=f"https://example.invalid/{id_}", title=title, claim=claim, claim_author=author,
                     verdict="false", verdict_raw="Fałsz", text=text or f"{title}\n{claim}", published_at=published)


SPECIFIC = fc("s", "Redakcja A", "Kowalczyk udostępnia stare nagranie z protestu",
              "Policja rozgania protestujących pod Pałacem Zimowym.", author="Jan Kowalczyk",
              text="Policja rozgania protestujących pod Pałacem Zimowym. Nagranie pochodzi z 2024 roku.")
SIMILAR = fc("g", "Redakcja B", "Nagranie z koncertu krąży jako protest",
             "Nagranie pokazuje protestujących pod Pałacem Zimowym")


class MainEvidence(unittest.TestCase):
    def setUp(self):
        self._docs = engine.INDEX.docs

    def tearDown(self):
        engine.INDEX.docs = self._docs

    def test_the_stronger_match_is_main(self):
        a = fc("a", "Redakcja A", "Szczepionka Q zawiera mikroczipy", "Szczepionka Q zawiera mikroczipy")
        b = fc("b", "Redakcja B", "Szczepionka Q zawiera mikroczipy", "Szczepionka Q zawiera mikroczipy")
        engine.INDEX.docs = [a, b]
        cands = [engine._Cand(doc_idx=0, chunk_text="", retrieval=0.8, cos=0.8, is_claim_match=True, claim_cos=0.80),
                 engine._Cand(doc_idx=1, chunk_text="", retrieval=0.9, cos=0.9, is_claim_match=True, claim_cos=0.93)]
        claim = Claim(text="Szczepionka Q zawiera mikroczipy", query="Szczepionka Q zawiera mikroczipy", kind="fakt", score=1.0)
        res = engine._decide(claim, [], cands, [], [], [], False)
        self.assertIn("Redakcja B", res.explanation)


class HeadlineRows(unittest.TestCase):
    def test_rows(self):
        self.assertEqual(claim_rows(SPECIFIC), [SPECIFIC.claim, SPECIFIC.title])
        same = fc("x", "R", "Szczepionka Q zawiera mikroczipy", "Szczepionka Q zawiera mikroczipy.")
        self.assertEqual(claim_rows(same), ["Szczepionka Q zawiera mikroczipy."])  # headline adds nothing
        off = SourceDoc(id="o", source_type="official", publisher="U", domain="example.invalid", url="https://example.invalid/o",
                        title="Komunikat", text="Treść")
        self.assertEqual(claim_rows(off), [])

    def make_index(self):
        idx = CorpusIndex()
        idx.docs = [SPECIFIC, SIMILAR]
        # rows: doc 0 claim, doc 0 headline, doc 1 claim (unit vectors in 3-D)
        idx.claim_doc_idx = [0, 0, 1]
        idx.claim_row = {0: 0, 1: 2}
        idx.claim_emb = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.6, 0.8, 0.0]], dtype=np.float32)
        return idx

    def test_one_result_per_doc_best_row(self):
        idx = self.make_index()
        q = np.array([0.0, 1.0, 0.0], dtype=np.float32)  # closest to doc 0's headline
        res = idx.match_claims(q, "", k=8)
        self.assertEqual([d for d, _ in res], [0, 1])
        self.assertAlmostEqual(res[0][1], 1.0)
        self.assertAlmostEqual(idx.checked_claim_cos(0, q), 0.0)  # its checked claim is not close

    def test_lexical_hit_survives_fusion(self):
        # 10 docs; the query is closest (dense) to docs 0..8, while doc 9 is the only lexical hit: re-sorting the
        # union by cosine would cut doc 9 at k=8, rank fusion keeps it, with its own cosine
        idx = CorpusIndex()
        idx.docs = [SIMILAR] * 10
        idx.claim_doc_idx = list(range(10))
        idx.claim_row = {i: i for i in range(10)}
        q = np.array([1.0, 0.0], dtype=np.float32)
        idx.claim_emb = np.array([[1.0 - 0.01 * i, 0.1] for i in range(9)] + [[0.3, 0.95]], dtype=np.float32)

        class Lexical:
            def search(self, toks, k):
                return [(9, 5.0)]
        idx.claim_bm25 = Lexical()
        res = idx.match_claims(q, "słowo", k=8)
        self.assertIn(9, [d for d, _ in res])
        self.assertEqual(len(res), 8)
        self.assertAlmostEqual(dict(res)[9], 0.3, places=5)
        self.assertEqual([d for d, _ in res][0], 0)  # still sorted by cosine

    def test_batch_path_uses_checked_claims_only(self):
        idx = self.make_index()
        q = np.array([[0.0, 1.0, 0.0]], dtype=np.float32)
        doc, sim = idx.match_claims_batch(q)
        self.assertEqual(int(doc[0]), 1)
        self.assertAlmostEqual(float(sim[0]), 0.8, places=5)


class MetadataOnly(unittest.TestCase):
    def test_record_without_text_of_its_own(self):
        meta = fc("m", "Redakcja C", "Nagranie z koncertu krąży jako protest", "Nagranie pokazuje protest pod Pałacem")
        self.assertFalse(engine.has_own_text(meta))  # text = headline + checked claim
        self.assertTrue(engine.has_own_text(SPECIFIC))  # the analysis dates the recording
        empty = fc("e", "Redakcja C", "Tytuł analizy", "Twierdzenie", text="")
        self.assertFalse(engine.has_own_text(empty))
        # the stored excerpt restates the finding in the headline's words: still a passage of the article
        reworded = fc("r", "Redakcja C", "Polecenie spółki dotyczące informowania o awarii jest prawdziwe",
                      "Spółka kazała stacjom informować o awarii.",
                      text="Polecenie spółki dotyczące informowania o awarii jest prawdziwe, co spółka potwierdziła.")
        self.assertTrue(engine.has_own_text(reworded))
        reorder = fc("o", "Redakcja C", "Polecenie spółki dotyczące informowania o awarii jest prawdziwe",
                     "Spółka kazała stacjom informować o awarii.",
                     text="Prawdziwe jest polecenie spółki dotyczące informowania o awarii.")
        self.assertTrue(engine.has_own_text(reorder))
        headline_only = fc("h", "Redakcja C", "Tytuł analizy", "Twierdzenie", text="Tytuł analizy")
        self.assertFalse(engine.has_own_text(headline_only))


if __name__ == "__main__":
    unittest.main()
