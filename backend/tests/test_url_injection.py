"""Scenario E with a URL, offline and without models: the controlled page web/demo/injection.html is served on
127.0.0.1. The SSRF guard must reject that address as it is (a real deployment never fetches private IPs); the test
then lifts the guard for this one loopback server only, so the real fetch path (httpx, size/time limits, trafilatura)
runs, and checks that the injected instructions are detected (security event) and neutralized before any model sees
the text. The full verdict path (instruction ignored, Demagog evidence unchanged) is exercised by the A–J run in
docs/COMPLIANCE.md; on a public deployment use https://<host>/demo/injection.html directly.

Run:  backend/.venv/bin/python backend/tests/test_url_injection.py      (or pytest backend/tests)
"""
from __future__ import annotations

import functools
import http.server
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prawdowid import fetch, security  # noqa: E402

WEB_DEMO = Path(__file__).resolve().parents[2] / "web" / "demo"


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D401 — keep test output clean
        pass


class UrlInjectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = functools.partial(_Quiet, directory=str(WEB_DEMO))
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}/injection.html"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_ssrf_guard_rejects_loopback(self):
        with self.assertRaises(security.UnsafeURL):
            security.check_public_url(self.url)
        with self.assertRaises(security.UnsafeURL):
            fetch.fetch_url(self.url)

    def test_injected_instructions_detected_and_neutralized(self):
        with mock.patch.object(fetch, "check_public_url", lambda u: u):  # this loopback test server only
            page = fetch.fetch_url(self.url)
        self.assertIn("65-latkowie", page["text"])
        events = security.scan(page["text"], "treść strony podanej w wiadomości")
        self.assertGreaterEqual(len(events), 2)
        self.assertTrue(all(e.kind == "prompt_injection" for e in events))
        clean = security.neutralize(page["text"])
        self.assertNotRegex(clean.lower(), r"zignoruj wszystkie poprzednie instrukcje")
        self.assertIn("65-latkowie", clean)  # the claim itself stays checkable


if __name__ == "__main__":
    unittest.main(verbosity=2)
