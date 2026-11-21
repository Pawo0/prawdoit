"""Rate limits, the client address behind a proxy, and the API side of the router (503 when busy, auto-mode jobs).

Model-free: the app is used without its startup hook (no index, no models) and the engine entry points are stubs.
The proxy tests wrap the app in uvicorn's own ProxyHeadersMiddleware — the class uvicorn installs when it runs with
proxy headers on (its default) — to show which client address the limiter sees with and without a trusted proxy.

Run:  backend/.venv/bin/python backend/tests/test_rate_limit.py
"""
from __future__ import annotations

import logging
import os
import threading
import time
import unittest
from unittest import mock

import _testenv  # noqa: F401  (must come before prawdowid imports)
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from prawdowid import api, jobs, ratelimit, service  # noqa: E402
from prawdowid.config import settings  # noqa: E402
from prawdowid.schemas import CheckResult  # noqa: E402

logging.disable(logging.INFO)  # one access-log line per request otherwise

QUICK = {"items":[{"id": "a", "text": "Dowolny tekst do sprawdzenia w szybkiej ścieżce wtyczki."}]}
CHECK = {"text": "Rząd podniósł w 2025 roku stawkę podatku VAT do 25 procent.", "channel": "extension"}


def fake_check(req, progress=None):
    return CheckResult(id="stub", created_at="2026-11-21T10:00:00+00:00", channel=req.channel, status="ok",
                       input_kind="text", input_excerpt="", mode=req.mode)


class ApiCase(unittest.TestCase):
    def setUp(self) -> None:
        ratelimit.reset()
        with jobs._LOCK:
            jobs._JOBS.clear()
        for p in (mock.patch.object(api, "quick_score", lambda req: []), mock.patch.object(api, "run_check", fake_check),
                  mock.patch.object(service, "run_check", fake_check)):
            p.start()
            self.addCleanup(p.stop)
        self.client = TestClient(api.app)  # not used as a context manager: the startup hook (models) does not run

    def burst(self, client, path, body, n, **kw):
        return [client.post(path, json=body, **kw).status_code for _ in range(n)]

    def wait_done(self, job_id: str, client=None) -> dict:
        for _ in range(200):
            view = (client or self.client).get(f"/api/jobs/{job_id}").json()
            if view.get("state") != "running":
                return view
            time.sleep(0.01)
        self.fail("job did not finish")


class Limits(ApiCase):
    def test_defaults(self):
        if "PRAWDOWID_RATE_LIMIT" not in os.environ:
            self.assertEqual(settings.rate_limit_per_min, 120)  # a jury set has 30+ cases; 30/min was too tight
        if "PRAWDOWID_RATE_LIMIT_QUICK" not in os.environ:
            self.assertEqual(settings.rate_limit_quick_per_min, 60)

    def test_quick_is_limited_per_minute_with_retry_after(self):
        n = settings.rate_limit_quick_per_min
        self.assertEqual(set(self.burst(self.client, "/api/quick", QUICK, n)), {200})
        r = self.client.post("/api/quick", json=QUICK)
        self.assertEqual(r.status_code, 429)
        self.assertGreaterEqual(int(r.headers["retry-after"]), 1)
        self.assertEqual(self.client.post("/api/check", json=CHECK).status_code, 200, "checks have their own bucket")

    def test_check_limit_covers_sync_and_async(self):
        n = settings.rate_limit_per_min
        codes = self.burst(self.client, "/api/check", CHECK, n - 1) + self.burst(self.client, "/api/check/async", CHECK, 1)
        self.assertEqual(set(codes), {200})
        self.assertEqual(self.client.post("/api/check", json=CHECK).status_code, 429)
        self.assertEqual(self.client.post("/api/check/async", json=CHECK).status_code, 429)
        self.assertEqual(self.client.post("/api/quick", json=QUICK).status_code, 200, "scanning has its own bucket")
        self.assertEqual(self.client.get("/api/jobs/unknown").status_code, 404, "polling is not rate limited")

    def test_window_slides_and_rejected_requests_do_not_extend_it(self):
        self.assertIsNone(ratelimit.hit("t", "1.1.1.1", 2, now=0.0))
        self.assertIsNone(ratelimit.hit("t", "1.1.1.1", 2, now=10.0))
        self.assertEqual(ratelimit.hit("t", "1.1.1.1", 2, now=20.0), 40)
        self.assertEqual(ratelimit.hit("t", "1.1.1.1", 2, now=59.0), 1)
        self.assertIsNone(ratelimit.hit("t", "1.1.1.1", 2, now=60.0))
        self.assertIsNone(ratelimit.hit("t", "2.2.2.2", 2, now=20.0), "another client is unaffected")

    def test_idle_clients_are_forgotten(self):
        with mock.patch.object(ratelimit, "MAX_KEYS", 50):
            for i in range(200):
                ratelimit.hit("t", f"10.0.0.{i}", 5, now=float(i))
            ratelimit.hit("t", "10.9.9.9", 5, now=500.0)
        self.assertLessEqual(len(ratelimit._hits), 51)


class ProxyAddress(ApiCase):
    """Behind a proxy the socket peer is the proxy. uvicorn replaces it with X-Forwarded-For only for trusted peers."""

    def test_trusted_proxy_gives_each_user_a_bucket(self):
        behind = TestClient(ProxyHeadersMiddleware(api.app, trusted_hosts="*"))  # FORWARDED_ALLOW_IPS=*
        n = settings.rate_limit_quick_per_min
        alice, bob = {"X-Forwarded-For": "203.0.113.7"}, {"X-Forwarded-For": "198.51.100.9"}
        self.assertEqual(set(self.burst(behind, "/api/quick", QUICK, n, headers=alice)), {200})
        self.assertEqual(behind.post("/api/quick", json=QUICK, headers=alice).status_code, 429)
        self.assertEqual(behind.post("/api/quick", json=QUICK, headers=bob).status_code, 200)
        self.assertIn(("quick", "203.0.113.7"), ratelimit._hits)

    def test_untrusted_peer_cannot_pick_its_own_bucket(self):
        direct = TestClient(ProxyHeadersMiddleware(api.app, trusted_hosts="127.0.0.1"))  # peer here: "testclient"
        n = settings.rate_limit_quick_per_min
        codes = [direct.post("/api/quick", json=QUICK, headers={"X-Forwarded-For": f"203.0.113.{i}"}).status_code
                 for i in range(n + 1)]
        self.assertEqual(codes[-1], 429, "a spoofed header must not create a fresh bucket per request")
        self.assertEqual(list(ratelimit._hits), [("quick", "testclient")])


class Router(ApiCase):
    def test_busy_quick_path_is_503_with_retry_after_not_a_result(self):
        def busy(req):
            raise service.QuickBusy("busy")

        with mock.patch.object(api, "quick_score", busy):
            r = self.client.post("/api/quick", json=QUICK)
        self.assertEqual((r.status_code, r.json()["status"]), (503, "blad_techniczny"))
        self.assertGreaterEqual(int(r.headers["retry-after"]), 1)

    def test_auto_checks_have_their_own_lower_limit(self):
        auto = {**CHECK, "mode": "auto"}
        n = settings.rate_limit_auto_per_min
        self.assertEqual(set(self.burst(self.client, "/api/check/async", auto, n)), {200})
        r = self.client.post("/api/check/async", json=auto)
        self.assertEqual(r.status_code, 429)
        self.assertIn("retry-after", r.headers)
        self.assertEqual(self.client.post("/api/check", json=auto).status_code, 429, "same bucket on the sync route")
        self.assertEqual(self.client.post("/api/check/async", json=CHECK).status_code, 200, "manual checks still pass")

    def test_auto_takes_text_only(self):
        r = self.client.post("/api/check/async", json={"url": "https://example.org/a", "mode": "auto"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(self.client.post("/api/check", json={"url": "https://example.org/a", "mode": "auto"}).status_code, 422)
        self.assertEqual(self.client.post("/api/check/async", json={**CHECK, "mode": "sideways"}).status_code, 422)

    def test_auto_job_runs_in_its_own_worker_and_is_delivered_once(self):
        threads = {}

        def check(req, progress=None):
            threads[req.mode] = threading.current_thread().name
            return fake_check(req)

        with mock.patch.object(service, "run_check", check):
            started = self.client.post("/api/check/async", json={**CHECK, "mode": "auto"}).json()
            self.assertEqual(started["mode"], "auto")
            view = self.wait_done(started["job_id"])
            manual = self.client.post("/api/check/async", json=CHECK).json()
            self.assertEqual(manual["mode"], "manual")
            manual_view = self.wait_done(manual["job_id"])
        self.assertEqual((view["state"], view["result"]["mode"]), ("done", "auto"))
        self.assertEqual(self.client.get(f"/api/jobs/{started['job_id']}").status_code, 404, "auto result is not kept")
        self.assertEqual(manual_view["result"]["mode"], "manual")
        self.assertEqual(self.client.get(f"/api/jobs/{manual['job_id']}").status_code, 200, "manual result stays 10 min")
        self.assertTrue(threads["auto"].startswith("job-auto"))
        self.assertFalse(threads["manual"].startswith("job-auto"))

    def test_background_checks_cannot_block_a_manual_check(self):
        release = threading.Event()

        def check(req, progress=None):
            if req.mode == "auto":
                release.wait(10)
            return fake_check(req)

        try:
            with mock.patch.object(service, "run_check", check):
                auto = {**CHECK, "mode": "auto"}
                self.assertEqual(set(self.burst(self.client, "/api/check/async", auto, jobs.MAX_AUTO_WAITING)), {200})
                r = self.client.post("/api/check/async", json=auto)
                self.assertEqual((r.status_code, r.headers.get("retry-after")), (429, "5"), "short queue, then back off")
                manual = self.client.post("/api/check/async", json=CHECK).json()
                self.assertEqual(self.wait_done(manual["job_id"])["state"], "done", "manual check finished meanwhile")
        finally:
            release.set()


if __name__ == "__main__":
    unittest.main(verbosity=2)
