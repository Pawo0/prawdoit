"""Requests to produce or transform text (a poem, a translation, code) are out of scope: status `poza_zakresem`, no
claims, no verdict, and the engine is never asked. A fact-check request phrased with the same verbs is still checked.

Model-free (engine and index are stubs; the real run_check, claim extraction and answer layer run).
Run:  backend/.venv/bin/python backend/tests/test_out_of_scope.py
"""
from __future__ import annotations

import os
import types
import unittest
from unittest import mock

import _testenv  # noqa: F401  (must come before prawdowid imports)
import numpy as np

from prawdowid import service  # noqa: E402
from prawdowid.schemas import CheckRequest, ClaimResult  # noqa: E402
from prawdowid.textutil import is_task_request  # noqa: E402

TASKS = [
    "Napisz mi wiersz o jesieni w Bieszczadach.",
    "Czy możesz ułożyć piosenkę na urodziny babci?",
    "Proszę, przetłumacz na niemiecki: spotkanie przesunięto na czwartek.",
    "Wygeneruj kod w JavaScript, który liczy silnię.",
    "Opowiedz dowcip o programistach.",
    "Please write a short story about a lighthouse keeper.",
    "Stwórz slogan reklamowy dla piekarni.",
]
CHECKS = [
    "Napisz, czy to prawda, że akcyza na paliwo spadnie w 2027 roku o połowę.",
    "Czy możesz sprawdzić, czy Sejm przyjął ustawę o zakazie gotówki?",
    "Stwórz post, że nowe dowody osobiste mają chipy śledzące — czy to fałsz?",
    "Rząd napisał nowy program wsparcia dla rolników o wartości 2 mld zł.",
    "Opowiadano, że w Gdyni zamknięto port dla statków pasażerskich.",
    "Ministerstwo przygotowało list do rodziców o zmianach w maturze 2027.",
]


class Detector(unittest.TestCase):
    def test_tasks(self):
        for text in TASKS:
            with self.subTest(text=text):
                self.assertTrue(is_task_request(text))

    def test_fact_check_requests_and_claims_are_not_tasks(self):
        for text in CHECKS:
            with self.subTest(text=text):
                self.assertFalse(is_task_request(text))


class AnyVocab:
    def __contains__(self, token) -> bool:
        return True


class FakeIndex:
    bm25 = types.SimpleNamespace(postings=AnyVocab())
    stats = {"documents": 3}
    loaded_at = "2026-11-21T10:00:00"

    def encode_query(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)


class RunCheck(unittest.TestCase):
    def setUp(self) -> None:
        self.engine_calls = []

        def verify(claim, timings):
            self.engine_calls.append(claim.text)
            return ClaimResult(claim=claim.text, kind="fakt", verdict="brak_dowodow",
                               verdict_label="Brak wystarczających dowodów", strength=0.0,
                               strength_label="niewystarczająca", explanation="—")

        env = {k: v for k, v in os.environ.items() if not k.startswith("PRAWDOWID_GOOGLE")}
        env["PRAWDOWID_LIVE_SEARCH"] = "0"
        for p in (mock.patch.dict(os.environ, env, clear=True),
                  mock.patch.object(service, "INDEX", FakeIndex()),
                  mock.patch.object(service, "verify_claim", verify),
                  mock.patch.object(service.llm, "enabled", lambda: False)):
            p.start()
            self.addCleanup(p.stop)

    def test_task_gets_no_verdict(self):
        for text in TASKS:
            with self.subTest(text=text):
                res = service.run_check(CheckRequest(text=text, channel="web"))
                self.assertEqual(res.status, "poza_zakresem")
                self.assertEqual(res.claims, [])
                self.assertIn("nie wydajemy werdyktu", res.status_message)
        self.assertEqual(self.engine_calls, [])

    def test_fact_check_request_is_checked(self):
        res = service.run_check(CheckRequest(text=CHECKS[0], channel="web"))
        self.assertEqual(res.status, "ok")
        self.assertEqual(len(self.engine_calls), 1)


if __name__ == "__main__":
    unittest.main()
