"""Organiser scope of the source registry (field `scope`, docs/SOURCE_REGISTRY.md) — offline, without models.

  * every registry file is valid, carries a known scope and, when it claims to be an organiser source, says where
    the organisers name it (`scope_basis`);
  * every address in rules/resources.txt is covered by an entry marked `organiser_listed`;
  * the scope report counts what lies outside the organisers' scope, and the restriction disables (never deletes)
    exactly those sources.

Run:  backend/.venv/bin/python backend/tests/test_source_scope.py      (or pytest backend/tests)
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prawdowid.sources import registry  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


class RegistryScopeTest(unittest.TestCase):
    def test_every_source_has_a_scope_and_a_basis(self):
        sources, problems = registry.load_all()
        self.assertEqual(problems, {})
        self.assertGreaterEqual(len(sources), 50)
        for sid, s in sources.items():
            self.assertIn(s["scope"], registry.SCOPES, sid)
            if s["scope"] != "outside":
                self.assertTrue(s["scope_basis"].strip(), f"{sid}: organiser source without scope_basis")
        self.assertEqual(sources["demagog"]["scope"], "organiser_implied")
        self.assertEqual(sources["google_factcheck"]["scope"], "organiser_listed")

    def test_every_listed_address_is_covered_by_a_listed_entry(self):
        listed = [s for s in registry.load_all()[0].values() if s["scope"] == "organiser_listed"]
        haystack = " ".join(f"{_host(s['url'])} {s['url']} {s['scope_basis']}" for s in listed)
        urls = re.findall(r"https?://\S+", (ROOT / "rules" / "resources.txt").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(urls), 40)
        missing = [u for u in urls if _host(u) not in haystack
                   or (_host(u) == "gov.pl" and "/".join(urlsplit(u).path.split("/")[1:3]) not in haystack)]
        self.assertEqual(missing, [])  # for gov.pl the section (/web/<serwis>) must be named, not just the host

    def test_unmarked_source_is_outside_and_an_organiser_scope_needs_a_basis(self):
        base = {"id": "nowe", "name": "Nowe", "publisher": "X", "url": "https://example.org/", "category": "media",
                "method": "reference_only", "license": "l", "qualification": "q"}
        self.assertEqual(registry.validate(base)["scope"], "outside")
        with self.assertRaises(registry.SourceError):
            registry.validate({**base, "scope": "organiser_listed"})
        with self.assertRaises(registry.SourceError):
            registry.validate({**base, "scope": "something_else"})
        ok = registry.validate({**base, "scope": "organiser_listed", "scope_basis": "rules/resources.txt: example.org"})
        self.assertTrue(registry.in_organiser_scope(ok))


class RestrictionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src, self.corpus = Path(self.tmp.name) / "sources", Path(self.tmp.name) / "corpus"
        self.src.mkdir()
        self.corpus.mkdir()
        for sid, scope, enabled in (("lista", "organiser_listed", True), ("scenariusz", "organiser_implied", True),
                                    ("zadanie", "organiser_recommended", True), ("wlasne", "outside", True),
                                    ("wlasne_off", "outside", False), ("live_web", "organiser_implied", True)):
            (self.src / f"{sid}.json").write_text(json.dumps({
                "id": sid, "name": sid, "publisher": sid, "url": f"https://{sid.replace('_', '-')}.example.org/",
                "category": "official", "method": "live_search" if sid == "live_web" else "reference_only",
                "enabled": enabled, "license": "l", "qualification": "q", "scope": scope,
                "scope_basis": "" if scope == "outside" else "dokument organizatora"}), encoding="utf-8")
            (self.corpus / f"{sid}.jsonl").write_text("", encoding="utf-8")
        (self.corpus / "bez_wpisu.jsonl").write_text("{}\n", encoding="utf-8")
        (self.corpus / "live_web.jsonl").write_text(
            json.dumps({"id": "live_web:1", "tags": ["live_search", "registry:lista"]}) + "\n"
            + json.dumps({"id": "live_web:2", "tags": ["live_search", "registry:wlasne"]}) + "\n", encoding="utf-8")
        p = mock.patch.object(registry, "sources_dir", lambda: self.src)
        p.start()
        self.addCleanup(p.stop)

    def test_binary_macos_sidecars_do_not_change_registry_or_corpus(self):
        before_sources = registry.load_all()
        before_files = registry.corpus_files_for_index(self.corpus)
        before_scope = registry.scope_report(self.corpus)
        (self.src / "._lista.json").write_bytes(b"\x00\x05\x16\x07\xa3macOS metadata")
        (self.corpus / "._lista.jsonl").write_bytes(b"\x00\x05\x16\x07\xa3macOS metadata")
        self.assertEqual(registry.load_all(), before_sources)
        self.assertEqual(registry.corpus_files_for_index(self.corpus), before_files)
        self.assertEqual(registry.scope_report(self.corpus), before_scope)

    def test_report_names_everything_outside_the_scope(self):
        rep = registry.scope_report(self.corpus)
        self.assertEqual(rep["enabled_outside"], ["wlasne"])
        self.assertEqual(rep["orphan_corpus_files"], ["bez_wpisu"])
        self.assertEqual(rep["live_records_from_excluded_sources"], {"wlasne": 1})
        self.assertEqual(rep["violations"], 3)
        self.assertEqual(registry.scope_report(self.corpus, strict=True)["enabled_outside"], ["wlasne", "zadanie"])

    def test_restriction_disables_and_keeps_the_files(self):
        self.assertEqual(registry.restrict_to_organiser_scope("powód"), ["wlasne"])
        after = json.loads((self.src / "wlasne.json").read_text(encoding="utf-8"))
        self.assertEqual((after["enabled"], after["notes"]), (False, "powód"))
        self.assertTrue((self.corpus / "wlasne.jsonl").exists())  # nothing is deleted
        self.assertEqual(registry.scope_report(self.corpus)["enabled_outside"], [])
        keep, skip = registry.corpus_files_for_index(self.corpus)
        self.assertEqual(sorted(skip), ["wlasne.jsonl", "wlasne_off.jsonl"])
        self.assertIn("zadanie.jsonl", [f.name for f in keep])
        self.assertEqual(registry.restrict_to_organiser_scope("powód", strict=True), ["zadanie"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
