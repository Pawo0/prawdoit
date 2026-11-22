"""Tier-1 router (`service.quick_score`): states, the NLI gate, the conflict rule and the inference cap.

Model-free: the index and the NLI model are replaced by stubs with scripted similarities and scores, so the tests
pin down the routing logic itself. `engine.same_claim` is the real one. Numbers on real data come from
eval/measure_router.py.

Run:  backend/.venv/bin/python backend/tests/test_router_quick.py
"""
from __future__ import annotations

import dataclasses
import itertools
import threading
import unittest
from unittest import mock

import _testenv  # noqa: F401  (must come before prawdowid imports)
import numpy as np

from prawdowid import service  # noqa: E402
from prawdowid.engine import same_claim  # noqa: E402
from prawdowid.nli import NLIScore  # noqa: E402
from prawdowid.schemas import QuickItem, QuickRequest, SourceDoc  # noqa: E402

FACT = "Rząd podniósł w 2025 roku stawkę podatku VAT do 25 procent w całej Polsce."
FACT2 = "Ministerstwo Finansów wypłaciło w marcu 2026 roku 14 miliardów złotych dopłat dla rolników."
OPINION = "Moim zdaniem ta władza jest najgorsza od lat i nic jej się nie udaje."
RISKY = "W poniedziałek rząd ogłosił powszechną mobilizację i ewakuację mieszkańców Warszawy."


def doc(i: int, verdict: str | None, publisher: str, date: str | None = "2026-03-02") -> SourceDoc:
    raw = {"false": "Fałsz", "true": "Prawda", "misleading": "Manipulacja"}.get(verdict or "")
    return SourceDoc(id=f"d{i}", source_type="factcheck", publisher=publisher, domain="example.org",
                     url=f"https://example.org/{i}", title=f"Tytuł {i}", published_at=date, claim=f"Twierdzenie {i}",
                     verdict=verdict, verdict_raw=raw)


class FakeIndex:
    """docs[0] debunked (Demagog), docs[1] rated true (Pravda), docs[2] debunked but without a publication date."""

    def __init__(self) -> None:
        self.loaded_at = "2026-11-21T10:00:00"
        self.docs = [doc(0, "false", "Demagog"), doc(1, "true", "Stowarzyszenie Pravda"), doc(2, "false", "FakeNews.pl", None)]
        self.debunked: dict[str, tuple[int, float]] = {}  # segment text -> (doc index, cosine)
        self.true: dict[str, float] = {}  # segment text -> cosine to docs[1]
        self.encoded: list[list[str]] = []
        self._last: list[str] = []

    def encode_query(self, texts):
        self.encoded.append(list(texts))
        self._last = list(texts)
        return np.arange(len(texts))

    def match_claims_batch(self, embs, verdicts=("false", "misleading", "mixed")):
        if verdicts == ("true",):
            return np.ones(len(embs), dtype=int), np.array([self.true.get(self._last[int(i)], 0.0) for i in embs])
        hits = [self.debunked.get(self._last[int(i)], (0, 0.0)) for i in embs]
        return np.array([h[0] for h in hits]), np.array([h[1] for h in hits])


class FakeNLI:
    name = "stub"

    def __init__(self) -> None:
        self.calls: list[list[tuple[str, str]]] = []
        self.scores: dict[str, NLIScore] = {}  # premise -> score; default: clear entailment

    def score(self, pairs):
        if pairs:
            self.calls.append(list(pairs))
        return [self.scores.get(p, NLIScore(0.95, 0.04, 0.01)) for p, _ in pairs]

    @property
    def n_pairs(self) -> int:
        return sum(len(c) for c in self.calls)


class RouterCase(unittest.TestCase):
    def setUp(self) -> None:
        self.index, self.nli = FakeIndex(), FakeNLI()
        for p in (mock.patch.object(service, "INDEX", self.index), mock.patch.object(service, "NLI_MODEL", self.nli)):
            p.start()
            self.addCleanup(p.stop)
        service._QCACHE.clear()

    def quick(self, *texts: str, **kw):
        req = QuickRequest(items=[QuickItem(id=f"i{n}", text=t) for n, t in enumerate(texts)])
        return service.quick_score(req, **kw)

    def near(self, text: str, sim: float, doc_idx: int = 0, true_sim: float = 0.0) -> None:
        self.index.debunked[text] = (doc_idx, sim)
        self.index.true[text] = true_sim


class States(RouterCase):
    def test_match_is_visible_and_names_the_publication(self):
        self.near(FACT, 0.93)
        r = self.quick(FACT)[0]
        self.assertEqual((r.state, r.level, r.reasons), ("match", "wysokie", ["RATED_CLAIM_MATCH"]))
        self.assertEqual((r.match.publisher, r.match.verdict_raw, r.match.published_at, r.match.url),
                         ("Demagog", "Fałsz", "2026-03-02", "https://example.org/0"))
        self.assertIsNone(r.conflict)

    def test_near_miss_is_a_candidate_and_never_visible(self):
        self.near(FACT, 0.78)
        r = self.quick(FACT)[0]
        self.assertEqual((r.state, r.level, r.risk), ("candidate", "brak", 0.0))
        self.assertIn("NEAR_MISS", r.reasons)
        self.assertGreaterEqual(r.priority, 0.6)
        self.assertEqual(r.match.publisher, "Demagog")  # nearest rated claim, as before; not a statement about the text

    def test_related_but_not_the_same_claim_is_a_candidate(self):
        self.near(FACT, 0.84)
        self.nli.scores[FACT] = NLIScore(0.10, 0.85, 0.05)  # neutral: same topic, different statement
        r = self.quick(FACT)[0]
        self.assertEqual((r.state, r.level), ("candidate", "brak"))
        self.assertIn("NEAR_MISS", r.reasons)

    def test_factual_sentence_without_a_rated_neighbour_is_a_low_priority_candidate(self):
        r = self.quick(FACT)[0]
        self.assertEqual((r.state, r.level, r.match), ("candidate", "brak", None))
        self.assertEqual(r.reasons, ["FACTUAL_SENTENCE"])
        self.assertLess(r.priority, 0.4)

    def test_priority_order_near_miss_over_high_risk_over_plain_fact(self):
        self.near(FACT2, 0.76)
        near, risky, plain = self.quick(FACT2, RISKY, FACT)
        self.assertIn("HIGH_RISK_TOPIC", risky.reasons)
        self.assertGreater(near.priority, risky.priority)
        self.assertGreater(risky.priority, plain.priority)

    def test_one_high_risk_list_for_the_router_and_the_engine(self):
        from prawdowid import engine, textutil
        self.assertIs(service.HIGH_RISK, textutil.HIGH_RISK)
        self.assertIs(engine.HIGH_RISK, textutil.HIGH_RISK)
        for text in ("Rozdają jod w szkołach.", "Apteki sprzedają jodek potasu.",  # were only in one of the two lists
                     "Szczepionka zawiera mikroczipy.", "NATO wysyła wojsko na granicę."):
            self.assertTrue(textutil.HIGH_RISK.search(text), text)
        self.assertFalse(textutil.HIGH_RISK.search("Jodła rośnie w Tatrach."))

    def test_opinion_and_short_text_are_none(self):
        opinion, short = self.quick(OPINION, "Za krótko.")
        self.assertEqual((opinion.state, opinion.level, opinion.priority), ("none", "brak", 0.0))
        self.assertEqual((short.state, short.reason), ("none", "za krótki tekst"))
        self.assertEqual(self.nli.n_pairs, 0)

    def test_text_that_denies_the_rated_claim_is_not_a_near_miss(self):
        self.near(FACT, 0.92)
        self.nli.scores[FACT] = NLIScore(0.02, 0.03, 0.95)
        self.nli.scores["Twierdzenie 0"] = NLIScore(0.02, 0.03, 0.95)  # reverse direction
        r = self.quick(FACT)[0]
        self.assertEqual(r.level, "brak")
        self.assertNotIn("NEAR_MISS", r.reasons)
        self.assertLess(r.priority, 0.6)

    def test_match_without_a_publication_date_is_not_shown(self):
        self.near(FACT, 0.93, doc_idx=2)
        r = self.quick(FACT)[0]
        self.assertEqual((r.state, r.level), ("candidate", "brak"))

    def test_level_is_set_exactly_when_state_is_match(self):
        self.near(FACT, 0.93)
        self.near(FACT2, 0.93, true_sim=0.93)
        self.near(RISKY, 0.77)
        for r in self.quick(FACT, FACT2, RISKY, OPINION):
            self.assertEqual(r.level != "brak", r.state == "match", r)


class Conflict(RouterCase):
    def test_equally_close_true_rated_claim_suppresses_the_tag(self):
        self.near(FACT, 0.90, true_sim=0.88)
        r = self.quick(FACT)[0]
        self.assertEqual((r.state, r.level, r.risk), ("candidate", "brak", 0.0))
        self.assertEqual(r.reasons[0], "CONFLICTING_RATINGS")
        self.assertEqual((r.conflict.publisher, r.conflict.verdict_raw), ("Stowarzyszenie Pravda", "Prawda"))
        self.assertGreaterEqual(r.priority, 0.6)  # the full check sees both ratings, so it goes first

    def test_true_rated_claim_further_than_the_margin_does_not(self):
        self.near(FACT, 0.93, true_sim=0.93 - service.CONFLICT_MARGIN - 0.01)
        r = self.quick(FACT)[0]
        self.assertEqual((r.state, r.conflict), ("match", None))

    def test_suppression_can_be_switched_off_for_measurement(self):
        self.near(FACT, 0.90, true_sim=0.95)
        self.assertEqual(self.quick(FACT, suppress_conflicts=False, use_cache=False)[0].state, "match")


class Gate(RouterCase):
    def test_no_nli_below_the_gate(self):
        self.near(FACT, 0.7999)
        self.near(FACT2, 0.74)
        self.quick(FACT, FACT2)
        self.assertEqual(self.nli.n_pairs, 0)

    def test_nli_from_the_gate_up(self):
        self.near(FACT, 0.80)
        self.quick(FACT)
        self.assertEqual(self.nli.n_pairs, 1)

    def test_same_legacy_output_as_the_old_gate_with_fewer_nli_calls(self):
        texts = [f"{FACT} Wariant numer {n} tego samego doniesienia prasowego." for n in range(8)]
        for t, sim in zip(texts, (0.50, 0.74, 0.77, 0.7999, 0.80, 0.84, 0.87, 0.95)):
            self.near(t, sim)
        legacy = lambda rs: [(r.risk, r.level, r.match, r.reason) for r in rs]  # noqa: E731
        old = legacy(self.quick(*texts, nli_gate=service.settings.claim_match_soft, suppress_conflicts=False, use_cache=False))
        old_pairs = self.nli.n_pairs
        self.nli.calls.clear()
        new = legacy(self.quick(*texts, suppress_conflicts=False, use_cache=False))
        self.assertEqual(old, new)
        self.assertEqual((old_pairs, self.nli.n_pairs), (7, 4))

    def test_engine_rule_cannot_decide_below_the_gate(self):
        """The gate is only safe while engine.same_claim needs cosine >= QUICK_NLI_GATE. If the engine rule is
        loosened, this fails and the gate has to move with it."""
        best, worst = NLIScore(1.0, 0.0, 0.0), NLIScore(0.0, 0.0, 1.0)
        claim = "Rząd podniósł stawkę podatku VAT do 25 procent."
        for cos in (0.74, 0.77, 0.79, service.QUICK_NLI_GATE - 1e-6):
            for fwd, rev, kind in itertools.product((best, worst), (best, worst), ("factcheck", "incident")):
                self.assertIsNone(same_claim(cos, fwd, rev, claim, claim, kind), (cos, fwd, rev, kind))


class CacheAndCap(RouterCase):
    def test_cache_is_per_index_load(self):
        self.near(FACT, 0.93)
        first = self.quick(FACT)[0]
        again = self.quick(FACT)[0]
        self.assertEqual(len(self.index.encoded), 1)
        self.assertEqual(first.state, again.state)
        self.index.loaded_at = "2026-11-21T12:00:00"  # index reloaded: the rated claims may have changed
        self.quick(FACT)
        self.assertEqual(len(self.index.encoded), 2)

    def test_busy_slot_is_reported_not_queued(self):
        fast = dataclasses.replace(service.settings, quick_wait_s=0.05)
        with mock.patch.object(service, "settings", fast):
            self.assertTrue(service._QUICK_SEM.acquire(timeout=1))
            try:
                with self.assertRaises(service.QuickBusy):
                    self.quick(FACT)
            finally:
                service._QUICK_SEM.release()
            self.assertEqual(self.quick(FACT)[0].state, "candidate")  # free again

    def test_only_one_batch_infers_at_a_time(self):
        active, peak, lock = [0], [0], threading.Lock()
        real = self.index.encode_query

        def slow(texts):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            threading.Event().wait(0.05)
            with lock:
                active[0] -= 1
            return real(texts)

        self.index.encode_query = slow
        threads = [threading.Thread(target=self.quick, args=(f"{FACT} Kopia {n} do testu równoległego.",)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(peak[0], service.settings.quick_concurrency)


if __name__ == "__main__":
    unittest.main(verbosity=2)
