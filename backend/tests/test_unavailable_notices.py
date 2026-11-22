"""A dependency that did not run (no key, switched off, outage, rejected output) is said out loud and never looks like
a result (rules §5). Checks the result (`engine.unavailable`, `live_search.steps`) and the chat text.

Model-free (engine, index and LLM are stubs; run_check, the live-stage wiring and the formatting are real).
Run:  backend/.venv/bin/python backend/tests/test_unavailable_notices.py
"""
from __future__ import annotations

import os
import types
import unittest
from unittest import mock

import _testenv  # noqa: F401  (must come before prawdowid imports)
import numpy as np

from prawdowid import service, websearch  # noqa: E402
from prawdowid.channels.formatting import chat_text  # noqa: E402
from prawdowid.schemas import CheckRequest, ClaimResult, Evidence  # noqa: E402

TEXT = "Czy to prawda, że od lutego 2027 r. bilet miesięczny w Toruniu będzie kosztował 250 zł?"
EV = Evidence(doc_id="test:bilet", title="Ceny biletów bez zmian", publisher="Testowy wydawca", domain="example.org",
              url="https://example.org/bilet", source_type="official", tier=1, published_at="2026-10-01",
              fragment="Dosłowny fragment.", stance="przeczy")


class AnyVocab:
    def __contains__(self, token) -> bool:
        return True


class FakeIndex:
    bm25 = types.SimpleNamespace(postings=AnyVocab())
    stats = {"documents": 3}
    loaded_at = "2026-11-21T10:00:00"

    def encode_query(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)

    def add_docs(self, docs):
        return 0


class Unavailable(unittest.TestCase):
    verdict = "brak_dowodow"
    llm_result: tuple = (None, {"used": False})

    def start(self, **env_over):
        def verify(claim, timings):
            decisive = self.verdict == "falszywe"
            return ClaimResult(claim=claim.text, kind="fakt", verdict=self.verdict,
                               verdict_label="Fałszywe" if decisive else "Brak wystarczających dowodów",
                               strength=0.8 if decisive else 0.0,
                               strength_label="mocna" if decisive else "niewystarczająca",
                               explanation="Wyjaśnienie z szablonu.", evidence=[EV] if decisive else [])

        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("PRAWDOWID_GOOGLE", "PRAWDOWID_FORCE_FAIL", "PRAWDOWID_LIVE"))}
        env.update(env_over)
        for p in (mock.patch.dict(os.environ, env, clear=True),
                  mock.patch.object(service, "INDEX", FakeIndex()),
                  mock.patch.object(service, "verify_claim", verify),
                  mock.patch.object(websearch, "search_trusted",
                                    lambda q, deadline, check_id=None: websearch.SearchOutcome()),
                  mock.patch.object(service.llm, "enabled", lambda: True),
                  mock.patch.object(service.llm, "simplify", lambda e, label: self.llm_result)):
            p.start()
            self.addCleanup(p.stop)
        return service.run_check(CheckRequest(text=TEXT, channel="web"))

    def test_missing_google_key_is_reported(self):
        res = self.start(PRAWDOWID_LIVE_SEARCH="1")
        steps = {s["provider"]: s for s in res.live_search.steps}
        self.assertEqual(steps["google_factcheck"]["status"], "nieaktywne")
        self.assertIn(websearch.NOTICE_GOOGLE_OFF, res.engine["unavailable"])
        self.assertNotIn(websearch.NOTICE_GOOGLE_OFF, res.warnings)  # a configuration note, not a warning about content
        self.assertIn("klucza API", chat_text(res))                 # abstention: the reader is told what was not searched
        self.assertIn("brak klucza", res.engine["processing"])
        self.assertEqual(res.engine["cost_estimate"]["external_calls"], 1)  # the site search only

    def test_live_search_switched_off_is_reported(self):
        res = self.start(PRAWDOWID_LIVE_SEARCH="0")
        self.assertIsNone(res.live_search)
        self.assertEqual(res.engine["unavailable"], [websearch.NOTICE_LIVE_OFF])
        self.assertIn("wyłączone na tym serwerze", chat_text(res))
        self.assertIn("przeszukano tylko katalog", res.claims[0].limitation_line)

    def test_llm_outage_is_reported_and_template_kept(self):
        self.verdict, self.llm_result = "falszywe", (None, {"used": False, "error": "ConnectTimeout"})
        res = self.start(PRAWDOWID_LIVE_SEARCH="0")
        self.assertEqual(res.claims[0].verdict, "falszywe")
        self.assertEqual(res.claims[0].explanation, "Wyjaśnienie z szablonu.")
        self.assertTrue(any("Model językowy był niedostępny (błąd techniczny: ConnectTimeout)" in u
                            for u in res.engine["unavailable"]))

    def test_llm_rejection_is_reported(self):
        self.verdict, self.llm_result = "falszywe", (None, {"used": False, "rejected": True})
        res = self.start(PRAWDOWID_LIVE_SEARCH="0")
        self.assertTrue(any("odrzucono w walidacji" in u for u in res.engine["unavailable"]))

    def test_llm_status_in_engine_info(self):
        res = self.start(PRAWDOWID_LIVE_SEARCH="0")
        self.assertIn("llm_status", res.engine)


if __name__ == "__main__":
    unittest.main()
