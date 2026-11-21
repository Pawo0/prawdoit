"""Consistency of fact-check matches (engine.consistent_matches): analyses of one publisher, or of the same checked
claim, must not imply opposite verdicts from the same rating; duplicates of one publisher collapse into one decisive
item. All publishers, claims and scores are invented. Pure text, no models.

Run:  backend/.venv/bin/python backend/tests/test_match_consistency.py      (or pytest backend/tests)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401

from prawdowid import engine  # noqa: E402
from prawdowid.nli import NLIScore  # noqa: E402
from prawdowid.schemas import Evidence, SourceDoc  # noqa: E402

ENTAIL, CONTRA, NEUTRAL = NLIScore(0.95, 0.03, 0.02), NLIScore(0.02, 0.03, 0.95), NLIScore(0.02, 0.96, 0.02)


def fc(id_, publisher, claim, verdict="false") -> SourceDoc:
    return SourceDoc(id=id_, source_type="factcheck", publisher=publisher, domain="example.invalid",
                     url=f"https://example.invalid/{id_}", title=claim, claim=claim, verdict=verdict,
                     verdict_raw={"false": "Fałsz", "true": "Prawda"}[verdict], text=claim)


class Consistency(unittest.TestCase):
    def setUp(self):
        self._docs = engine.INDEX.docs

    def tearDown(self):
        engine.INDEX.docs = self._docs

    def run_case(self, cands):
        """cands: (doc, same, fwd, rev, cos). Returns (support ids, refute ids, stances by id, notes)."""
        engine.INDEX.docs = [d for d, *_ in cands]
        support, refute, misleading, evidence = [], [], [], []
        for i, (d, same, fwd, rev, cos) in enumerate(cands):
            c = engine._Cand(doc_idx=i, chunk_text="", retrieval=cos, cos=cos, is_claim_match=True, claim_cos=cos,
                             nli_claim=fwd, nli_claim_rev=rev)
            mapped = engine.FC_TO_VERDICT[d.verdict]
            if same is False:
                mapped = {"falszywe": "potwierdzone", "potwierdzone": "falszywe"}[mapped]
            c.same, c.implied = same, mapped
            (refute if mapped == "falszywe" else support).append(c)
            evidence.append(Evidence(doc_id=d.id, title=d.title, publisher=d.publisher, domain=d.domain, url=d.url,
                                     source_type="factcheck", tier=2, fragment=d.claim,
                                     stance="przeczy" if mapped == "falszywe" else "popiera", same_claim=same))
        notes = engine.consistent_matches(support, refute, misleading, evidence)
        ids = lambda cs: sorted(engine.INDEX.docs[c.doc_idx].id for c in cs)  # noqa: E731
        return ids(support), ids(refute), {e.doc_id: e.stance for e in evidence}, notes

    def test_similarity_only_match_yields_to_nli_backed_negation(self):
        # the user denies the narrative; one analysis is matched as a denial (NLI both ways), a restatement of it
        # with a date only by similarity — same publisher, same rating
        a = fc("a", "Redakcja A", "Miasto X nie płaci spółce Y za wodę.")
        b = fc("b", "Redakcja A", "Od 2030 roku miasto X nie płaci spółce Y za wodę.")
        sup, ref, st, notes = self.run_case([(a, False, CONTRA, CONTRA, 0.91), (b, True, NEUTRAL, NEUTRAL, 0.89)])
        self.assertEqual((sup, ref), (["a"], []))
        self.assertEqual(st["b"], "kontekst")
        self.assertEqual(len(notes), 1)

    def test_same_checked_claim_across_publishers(self):
        a = fc("a", "Redakcja A", "Miasto X nie płaci spółce Y za wodę.")
        b = fc("b", "Redakcja B", "Od 2030 roku miasto X nie płaci spółce Y za wodę.")
        sup, ref, _, notes = self.run_case([(a, False, CONTRA, CONTRA, 0.91), (b, True, NEUTRAL, NEUTRAL, 0.89)])
        self.assertEqual((sup, ref), (["a"], []))
        self.assertTrue(notes)

    def test_tie_on_nli_support_broken_by_similarity(self):
        a = fc("a", "Redakcja A", "Państwo X zapowiedziało odwet po ataku na port Z.")
        c = fc("c", "Redakcja A", "Incydent nad granicą był prowokacją państwa W.")
        sup, ref, _, _ = self.run_case([(a, True, ENTAIL, ENTAIL, 0.97), (c, False, CONTRA, CONTRA, 0.86)])
        self.assertEqual((sup, ref), ([], ["a"]))

    def test_duplicates_of_one_publisher_collapse(self):
        a = fc("a", "Redakcja A", "Szczepionka Q zawiera mikroczipy.")
        b = fc("b", "Redakcja A", "Szczepionka Q zawiera mikroczipy śledzące.")
        sup, ref, st, notes = self.run_case([(a, True, ENTAIL, ENTAIL, 0.95), (b, True, ENTAIL, NEUTRAL, 0.93)])
        self.assertEqual(ref, ["a"])
        self.assertEqual(st["b"], "kontekst")
        self.assertEqual(notes, [])  # a duplicate is not a conflict

    def test_independent_publishers_stay_separate(self):
        a = fc("a", "Redakcja A", "Szczepionka Q zawiera mikroczipy.")
        b = fc("b", "Redakcja B", "Szczepionka Q zawiera mikroczipy.")
        _, ref, _, _ = self.run_case([(a, True, ENTAIL, ENTAIL, 0.95), (b, True, ENTAIL, ENTAIL, 0.94)])
        self.assertEqual(ref, ["a", "b"])

    def test_different_ratings_are_a_real_conflict(self):
        # one publisher rated the claim true, another false: R2 must still see both
        a = fc("a", "Redakcja A", "Pięć milionów osób wyjechało do kraju K.", "true")
        b = fc("b", "Redakcja B", "Pięć milionów osób wyjechało do kraju K.", "false")
        sup, ref, _, notes = self.run_case([(a, True, ENTAIL, ENTAIL, 0.93), (b, True, ENTAIL, ENTAIL, 0.91)])
        self.assertEqual((sup, ref, notes), (["a"], ["b"], []))
        a2 = fc("a", "Redakcja A", "Pięć milionów osób wyjechało do kraju K.", "true")
        b2 = fc("b", "Redakcja A", "Ponad pięć milionów osób wyjechało w tym roku do kraju K.", "false")
        sup, ref, _, _ = self.run_case([(a2, True, ENTAIL, ENTAIL, 0.93), (b2, True, ENTAIL, ENTAIL, 0.91)])
        self.assertEqual((sup, ref), (["a"], ["b"]))  # same publisher, different ratings: not reconciled

    def test_unrelated_claims_of_different_publishers_are_not_reconciled(self):
        a = fc("a", "Redakcja A", "Miasto X nie płaci spółce Y za wodę.")
        c = fc("c", "Redakcja B", "Spółka Y podniosła ceny wody o połowę.")
        sup, ref, _, _ = self.run_case([(a, False, CONTRA, CONTRA, 0.91), (c, True, NEUTRAL, NEUTRAL, 0.89)])
        self.assertEqual((sup, ref), (["a"], ["c"]))


class Helpers(unittest.TestCase):
    def test_same_checked_claim(self):
        self.assertTrue(engine.same_checked_claim("Miasto X nie płaci za wodę.", "Od 2030 r. miasto X nie płaci za wodę."))
        self.assertFalse(engine.same_checked_claim("Miasto X płaci za wodę.", "Miasto X nie płaci za wodę."))
        self.assertFalse(engine.same_checked_claim("Miasto X płaci za wodę.", "Miasto X płaci za prąd."))
        self.assertFalse(engine.same_checked_claim("To fałsz.", "To fałsz, a nie prawda."))  # too short to compare

    def test_match_support(self):
        c = engine._Cand(doc_idx=0, chunk_text="", retrieval=0.9, cos=0.9, claim_cos=0.9, nli_claim=CONTRA)
        c.same = False
        self.assertEqual(engine.match_support(c), (1, 0.9))  # reverse direction not computed
        c.nli_claim_rev = CONTRA
        self.assertEqual(engine.match_support(c), (2, 0.9))
        c.same = True
        self.assertEqual(engine.match_support(c), (0, 0.9))


if __name__ == "__main__":
    unittest.main()
