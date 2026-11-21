"""Router end to end on the real index and models (embedder + NLI, about 3 GB RAM, ~1 min). Skipped unless
PRAWDOWID_MODEL_TESTS=1, so the default test run stays model-free.

    PRAWDOWID_MODEL_TESTS=1 backend/.venv/bin/python backend/tests/test_router_models.py

Uses the same isolated work directory as eval/measure_router.py (index cache, corpus snapshot, SQLite), so nothing
in the repo is written. Live search is off.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENABLED = os.environ.get("PRAWDOWID_MODEL_TESTS") == "1"

DEBUNKED = ("Gwałtu na policjantce nie zakwalifikowano jako przestępstwo. Policjant, który dopuścił się gwałtu, "
            "zostanie zwolniony z aresztu i wróci do pracy.")  # Demagog: Fałsz (eval/bench_polish seed 1)
ORDINARY = "Piękna pogoda dziś w Krakowie, idziemy z dziećmi na Planty i polecam lody przy Rynku."
UNKNOWN = "Burmistrz Pcimia Dolnego Zenon Wąsik ogłosił w lipcu 2026 roku budowę lotniska dla sterowców."


@unittest.skipUnless(ENABLED, "set PRAWDOWID_MODEL_TESTS=1 to run the model-backed router tests")
class RouterWithModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT / "eval"))
        import measure_router

        measure_router.setup_env()
        from prawdowid import service, store
        from prawdowid.index import INDEX

        INDEX.load()
        cls.service, cls.store, cls.index = service, store, INDEX

    def quick(self, *texts):
        from prawdowid.schemas import QuickItem, QuickRequest

        return self.service.quick_score(QuickRequest(items=[QuickItem(id=str(i), text=t) for i, t in enumerate(texts)]))

    def test_states_on_real_data(self):
        match, ordinary, unknown = self.quick(DEBUNKED, ORDINARY, UNKNOWN)
        self.assertEqual(match.state, "match")
        self.assertEqual(match.match.publisher, "Demagog")
        self.assertTrue(match.match.url.startswith("https://") and match.match.published_at and match.match.verdict_raw)
        self.assertNotEqual(ordinary.state, "match")
        self.assertEqual((unknown.state, unknown.level), ("candidate", "brak"))  # checkable, nothing to show

    def test_claims_rated_true_get_no_visible_tag_when_a_debunked_twin_is_close(self):
        """research/09 §3.2: two true/debunked pairs sit above cosine 0.86 in the corpus."""
        true_claims = [d.claim for d in self.index.docs if d.source_type == "factcheck" and d.verdict == "true" and d.claim]
        results = self.quick(*true_claims[:40])
        tagged = [(r.match.claim, r.match.similarity) for r in results if r.state == "match"]
        self.assertEqual(tagged, [], "a claim a fact-checker rated true must not carry a 'rated false' tag")

    def test_auto_check_matches_manual_verdict_and_leaves_no_text(self):
        from prawdowid.schemas import CheckRequest

        cases_before = self.store._db.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        auto = self.service.run_check(CheckRequest(text=DEBUNKED, channel="extension", mode="auto"))
        auto_unknown = self.service.run_check(CheckRequest(text=UNKNOWN, channel="extension", mode="auto"))
        self.assertEqual(self.store._db.execute("SELECT COUNT(*) FROM cases").fetchone()[0], cases_before)
        dump = "\n".join(repr(tuple(r)) for t in ("checks", "security_events", "cases", "errors")
                         for r in self.store._db.execute(f"SELECT * FROM {t}").fetchall())  # noqa: S608
        # the audit rows name the sources that were used (their titles and links), never the checked text:
        # no run of four consecutive words of either input may appear anywhere in the database
        for text in (DEBUNKED, UNKNOWN):
            words = text.split()
            for i in range(len(words) - 3):
                self.assertNotIn(" ".join(words[i:i + 4]), dump)
        for word in ("policjantce", "Pcimia", "sterowców"):
            self.assertNotIn(word, dump)
        self.assertEqual(auto_unknown.claims[0].verdict, "brak_dowodow")
        self.assertIsNone(auto_unknown.case_id)
        manual = self.service.run_check(CheckRequest(text=DEBUNKED, channel="extension"))  # live search off by env
        self.assertEqual([c.verdict for c in auto.claims], [c.verdict for c in manual.claims])
        self.assertEqual([[e.url for e in c.evidence] for c in auto.claims], [[e.url for e in c.evidence] for c in manual.claims])
        self.assertEqual(auto.claims[0].verdict, "falszywe")
        ev = auto.claims[0].evidence[auto.claims[0].main_evidence or 0]
        self.assertTrue(ev.publisher and ev.url.startswith("http") and ev.fragment)


if __name__ == "__main__":
    unittest.main(verbosity=2)
