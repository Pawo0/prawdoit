"""The embedding-cache prune keeps exactly the vectors some corpus file can still produce. No models are loaded."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import _testenv  # noqa: F401  (runtime dir, no scheduler)
from prawdowid import index as I  # noqa: E402

TEXT = "Urząd informuje o zmianie godzin pracy punktu obsługi mieszkańców od przyszłego tygodnia."
CLAIM = "Na dworcu w Przykładowie zamknięto wszystkie kasy biletowe."


def _sha(t: str) -> str:
    return hashlib.sha1(t.encode("utf-8", "ignore")).hexdigest()


def _rec(i: str, **kw) -> str:
    base = dict(id=i, source_type="official", publisher="Urząd", domain="example.gov.pl", url=f"https://example.gov.pl/{i}",
                title="Komunikat", text=TEXT)
    return json.dumps(base | kw, ensure_ascii=False) + "\n"


class PruneTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.corpus, self.idx = root / "corpus", root / "index"
        self.corpus.mkdir()
        self.idx.mkdir()
        p = mock.patch.object(I, "settings", dataclasses.replace(I.settings, index_dir=self.idx, corpus_dir=self.corpus))
        p.start()
        self.addCleanup(p.stop)

    def _cache(self, prefix: str, texts: list[str]) -> np.ndarray:
        kpath, vpath = I._cache_paths(prefix)
        vecs = np.arange(len(texts) * 384, dtype=np.float32).reshape(len(texts), 384)
        np.save(vpath, vecs)
        kpath.write_text(json.dumps([_sha(t) for t in texts]))
        return vecs

    def _keys(self, prefix: str) -> list[str]:
        return json.loads(I._cache_paths(prefix)[0].read_text())

    def test_stale_vectors_go_and_live_ones_stay_with_their_rows(self):
        (self.corpus / "zrodlo.jsonl").write_text(_rec("zrodlo:1"), encoding="utf-8")
        # a file whose source may be disabled in the registry still counts
        (self.corpus / "wylaczone.jsonl").write_text(
            _rec("wylaczone:1", source_type="factcheck", text="", claim=CLAIM, verdict="false", verdict_raw="Fałsz"),
            encoding="utf-8")
        passage, query = I.settings.embed_passage_prefix, I.settings.embed_query_prefix
        pv = self._cache(passage, ["usunięty tekst", TEXT, "inny stary fragment"])
        qv = self._cache(query, [CLAIM, "stare twierdzenie"])
        out = I.prune_cache()
        self.assertEqual(self._keys(passage)[0], _sha(TEXT))
        self.assertNotIn(_sha("usunięty tekst"), self._keys(passage))
        self.assertEqual(self._keys(query), [_sha(CLAIM)])
        np.testing.assert_array_equal(np.load(I._cache_paths(passage)[1])[0], pv[1])
        np.testing.assert_array_equal(np.load(I._cache_paths(query)[1]), qv[:1])
        self.assertEqual(out[I._cache_paths(query)[0].name], {"before": 2, "after": 1})

    def test_nothing_to_drop_leaves_the_files_alone(self):
        (self.corpus / "zrodlo.jsonl").write_text(_rec("zrodlo:1"), encoding="utf-8")
        self._cache(I.settings.embed_passage_prefix, [TEXT])
        mtime = I._cache_paths(I.settings.embed_passage_prefix)[1].stat().st_mtime_ns
        I.prune_cache()
        self.assertEqual(I._cache_paths(I.settings.embed_passage_prefix)[1].stat().st_mtime_ns, mtime)


if __name__ == "__main__":
    unittest.main(verbosity=2)
