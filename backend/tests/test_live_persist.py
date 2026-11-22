"""Live-search pages are not stored by default; when storing is switched on they expire with the audit retention.
Pure file handling, no models."""
from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import _testenv  # noqa: F401  (runtime dir, no scheduler)
from prawdowid import websearch as W  # noqa: E402
from prawdowid.schemas import SourceDoc  # noqa: E402


def _doc(url: str, days_ago: float) -> SourceDoc:
    t = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds").replace("+00:00", "Z")
    return SourceDoc(id="live_web:" + url[-6:], source_type="official", publisher="Urząd", domain="example.gov.pl",
                     url=url, title="Komunikat", retrieved_at=t, language="pl", license="l",
                     text="Urząd informuje o zmianie godzin pracy punktu obsługi mieszkańców.")


class LivePersistTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "live_web.jsonl"
        p = mock.patch.object(W, "LIVE_CORPUS", self.path)
        p.start()
        self.addCleanup(p.stop)

    def _settings(self, **kw):
        p = mock.patch.object(W, "settings", dataclasses.replace(W.settings, **kw))
        p.start()
        self.addCleanup(p.stop)

    def _urls(self) -> list[str]:
        return [json.loads(x)["url"] for x in self.path.read_text(encoding="utf-8").splitlines()] if self.path.exists() else []

    def test_off_by_default(self):
        self._settings(live_persist_days=0)
        self.assertEqual(W.persist([_doc("https://example.gov.pl/a", 0)]), 0)
        self.assertFalse(self.path.exists())

    def test_on_keeps_new_pages_and_drops_expired_ones(self):
        self._settings(live_persist_days=10, retention_days=30)
        self.path.write_text(json.dumps(_doc("https://example.gov.pl/stara", 12).model_dump()) + "\n"
                             + json.dumps(_doc("https://example.gov.pl/swieza", 2).model_dump()) + "\n", encoding="utf-8")
        self.assertEqual(W.persist([_doc("https://example.gov.pl/swieza", 0), _doc("https://example.gov.pl/nowa", 0)]), 1)
        self.assertEqual(self._urls(), ["https://example.gov.pl/swieza", "https://example.gov.pl/nowa"])

    def test_retention_is_capped_by_the_audit_retention(self):
        self._settings(live_persist_days=365, retention_days=30)
        self.assertEqual(W.persist_days(), 30)
        self.path.write_text(json.dumps(_doc("https://example.gov.pl/a", 31).model_dump()) + "\n"
                             + json.dumps(_doc("https://example.gov.pl/b", 29).model_dump()) + "\n", encoding="utf-8")
        self.assertEqual(W.purge_live_corpus(), 1)
        self.assertEqual(self._urls(), ["https://example.gov.pl/b"])

    def test_purge_with_persistence_off_empties_the_file(self):
        self._settings(live_persist_days=0)
        self.path.write_text(json.dumps(_doc("https://example.gov.pl/a", 1).model_dump()) + "\n", encoding="utf-8")
        self.assertEqual(W.purge_live_corpus(), 1)
        self.assertEqual(self._urls(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
