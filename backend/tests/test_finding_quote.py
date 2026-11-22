"""Quote of a fact-check that carries the finding (engine._finding_score, engine._rerank_findings). No models: NLI and the
index are replaced by stubs. Every text is invented."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _testenv  # noqa: E402,F401

from prawdowid import engine  # noqa: E402
from prawdowid.nli import NLIScore  # noqa: E402
from prawdowid.textutil import tokens  # noqa: E402

CLAIM = "Gmina Zielonka zamknęła w 2025 r. wszystkie trzy szkoły podstawowe"
FC_CLAIM = "W gminie Zielonka zamknięto wszystkie szkoły podstawowe"


def fs(w, claim=CLAIM):
    return engine._finding_score(w, set(tokens(claim)), set(tokens(FC_CLAIM)), claim)


class FindingScore(unittest.TestCase):
    def test_finding_beats_retelling(self):
        retell = "W mediach społecznościowych krąży wpis, według którego gmina rzekomo zamknęła szkoły podstawowe."
        finding = "W rzeczywistości zamknięto jedną szkołę, a dwie pozostałe połączono w zespół szkół."
        self.assertGreater(fs(finding), fs(retell))
        self.assertLess(fs(retell), 0)

    def test_near_restatement_is_penalised(self):
        self.assertLess(fs("Gmina Zielonka zamknęła wszystkie szkoły podstawowe."), 0)

    def test_earlier_year_and_different_amount(self):
        plain = "Decyzję podjęła rada gminy po konsultacjach z rodzicami uczniów."
        older = "Decyzję podjęła rada gminy w 2019 r. po konsultacjach z rodzicami uczniów."
        self.assertGreater(fs(older), fs(plain))
        money = "Gmina wydaje na oświatę 12 mln zł rocznie"
        self.assertGreater(fs("Budżet szkół wynosi 9 mln zł, czyli mniej niż podano.", money),
                           fs("Budżet szkół jest uchwalany co roku przez radę gminy.", money))


class Rerank(unittest.TestCase):
    def setUp(self):
        self.text = ("Wpis o zamknięciu szkół krąży od tygodnia. Gmina zamknęła tylko jedną szkołę. "
                     "Dwie pozostałe szkoły działają bez zmian.")
        self.docs = [SimpleNamespace(text=self.text)]

    def cand(self, alternatives):
        return SimpleNamespace(doc_idx=0, alternatives=tuple(alternatives))

    def run_rerank(self, cand, want, scores):
        with mock.patch.object(engine, "INDEX", SimpleNamespace(docs=self.docs)), \
                mock.patch.object(engine.NLI_MODEL, "score", return_value=scores):
            return engine._rerank_findings(CLAIM, [(cand, want)])

    def test_refuting_item_prefers_contradiction(self):
        c = self.cand([("Wpis o zamknięciu szkół krąży od tygodnia.", 1.0),
                       ("Gmina zamknęła tylko jedną szkołę.", 0.9)])
        got = self.run_rerank(c, "contra", [NLIScore(0.6, 0.3, 0.1), NLIScore(0.02, 0.08, 0.9)])
        self.assertEqual(got, {0: "Gmina zamknęła tylko jedną szkołę."})

    def test_supporting_item_prefers_entailment(self):
        c = self.cand([("Gmina zamknęła tylko jedną szkołę.", 1.0),
                       ("Dwie pozostałe szkoły działają bez zmian.", 0.95)])
        got = self.run_rerank(c, "entail", [NLIScore(0.05, 0.15, 0.8), NLIScore(0.85, 0.1, 0.05)])
        self.assertEqual(got, {0: "Dwie pozostałe szkoły działają bez zmian."})

    def test_lexical_score_still_counts(self):
        # a small NLI edge does not outweigh a clearly better lexical / finding score
        c = self.cand([("Gmina zamknęła tylko jedną szkołę.", 1.6),
                       ("Dwie pozostałe szkoły działają bez zmian.", 0.9)])
        got = self.run_rerank(c, "contra", [NLIScore(0.2, 0.4, 0.4), NLIScore(0.1, 0.3, 0.6)])
        self.assertEqual(got, {0: "Gmina zamknęła tylko jedną szkołę."})

    def test_quote_must_be_verbatim(self):
        c = self.cand([("Gmina zamknęła tylko jedną szkołę.", 1.0), ("Tego zdania nie ma w źródle.", 0.9)])
        got = self.run_rerank(c, "contra", [NLIScore(0.3, 0.4, 0.3), NLIScore(0.0, 0.0, 1.0)])
        self.assertEqual(got, {})

    def test_budget(self):
        many = [(f"Zdanie numer {i}.", 1.0) for i in range(5)]
        cands = [(SimpleNamespace(doc_idx=0, alternatives=tuple(many)), "contra") for _ in range(4)]
        with mock.patch.object(engine, "INDEX", SimpleNamespace(docs=self.docs)), \
                mock.patch.object(engine.NLI_MODEL, "score", side_effect=lambda p: [NLIScore(0.3, 0.4, 0.3)] * len(p)) as m:
            engine._rerank_findings(CLAIM, cands)
        self.assertLessEqual(len(m.call_args[0][0]), engine.FINDING_NLI_BUDGET)
        self.assertEqual(m.call_count, 1)


if __name__ == "__main__":
    unittest.main()
