"""Demagog pages that rate several claims: one corpus record per ClaimReview block (ingest/harvest_demagog.py).

The fixture is a small synthetic page in the layout of a Demagog fact-check (JSON-LD ClaimReview blocks,
.dg-post-content__center / __inner, a lead, a summary box, h2/h3 sections). Its text is invented for the test.

Run:  ingest/.venv/bin/python ingest/tests/test_harvest_demagog.py      (needs selectolax + trafilatura, the ingest
      venv of ingest/run_factchecks.sh; skipped where they are missing)
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import harvest_demagog as hd
    from common import IncrementalCorpus, normalize_record
except ImportError as e:  # selectolax / trafilatura are ingest-only dependencies
    hd = None
    _MISSING = str(e)

URL = "https://demagog.org.pl/fake_news/zielone-ksiezyce-i-inne-mity-test/"
TITLE = "Zielone księżyce nad Mazurami? Sprawdzamy trzy mity"


def claim_review(claim: str, rating: str, author: str = "Użytkownicy Facebooka", date: str = "2031-05-04") -> dict:
    return {"@context": "http://schema.org", "@type": "ClaimReview", "datePublished": date, "url": URL,
            "author": {"@type": "Organization", "name": "Demagog PL"}, "claimReviewed": claim,
            "itemReviewed": {"@type": "Claim", "author": {"@type": "Person", "name": author}},
            "reviewRating": {"@type": "Rating", "alternateName": rating}}


# page order: headline claim, a second claim, a third claim (rated differently, with another claimant and date)
BLOCKS = [
    claim_review("Nad Mazurami widać zielone księżyce.", "Fałsz."),
    claim_review("Kormorany przylatują nad jeziora tylko w nocy.", "Fałsz."),
    claim_review("Woda w jeziorze Testowym ma 30 stopni zimą.", "Brakujący kontekst",
                 author="Profil Pogodowy", date="2031-05-05"),
]
SECTIONS = """
<h2>Zielone księżyce to efekt filtra</h2>
<p>Zdjęcie zielonego księżyca nad Mazurami powstało w aplikacji z filtrem kolorów.</p>
<div class="wp-caption"><p class="wp-caption-text">Źródło: zrzut ekranu</p></div>
<h2>Kormorany i ich pory przelotów</h2>
<p>Kormorany przylatują nad jeziora o świcie i w dzień, a nie tylko w nocy, jak głosi wpis.</p>
<h3>Skąd wziął się mit o nocnych kormoranach</h3>
<p>Nocne nagranie kormoranów z jednego jeziora krążyło bez daty.</p>
<h2>Temperatura wody w jeziorze Testowym</h2>
<p>Pomiar 30 stopni w jeziorze Testowym dotyczył ujścia ciepłej wody z oczyszczalni, a nie całego jeziora zimą.</p>
<ul><li>Pomiar wykonano w jednym punkcie.</li><li>Średnia temperatura zimą wynosi 2 stopnie.</li></ul>
<h2>Podsumowanie</h2>
<p>Zielone księżyce, nocne kormorany i 30 stopni zimą w jeziorze Testowym to mity.</p>
"""


def page(blocks: list[dict] | None = None, sections: str = SECTIONS, separate_scripts: bool = False) -> str:
    blocks = BLOCKS if blocks is None else blocks
    webpage = {"@type": "WebPage", "name": TITLE, "datePublished": "2031-05-04T10:00:00+00:00"}
    if separate_scripts:
        ld = "".join(f'<script type="application/ld+json">{json.dumps(b, ensure_ascii=False)}</script>'
                     for b in blocks + [webpage])
    else:  # one list: jsonld_blocks() walks it from the end, so its first ClaimReview is the last on the page
        ld = f'<script type="application/ld+json">{json.dumps(blocks, ensure_ascii=False)}</script>' \
             f'<script type="application/ld+json">{json.dumps({"@graph": [webpage]})}</script>'
    return f"""<!doctype html><html><head><meta property="og:title" content="{TITLE}">{ld}</head><body>
<div class="dg-post-content__center">
 <div class="dg-post-content__title"><h2>{TITLE}</h2></div>
 <div class="dg-post-content__tags dg-post-content__tags--desktop"><a href="https://demagog.org.pl/tematy/przyroda/">Przyroda</a></div>
 <div class="dg-post-content__lead dg-post-content__lead--desktop"><p>Trzy wpisy o Mazurach nie mają oparcia w faktach.</p></div>
 <div class="dg-post-content__inner">
  <div class="dg-post-content__lead dg-post-content__lead--mobile"><p>Trzy wpisy o Mazurach nie mają oparcia w faktach.</p></div>
  <p class="title mb-4">fake news w pigułce</p>
  <div class="summary-text"><ul><li>W sieci krążą trzy wpisy o Mazurach.</li><li>Żaden nie jest prawdziwy.</li></ul></div>
  <p>Wpisy opublikowano w maju na kilku profilach w mediach społecznościowych.</p>
  {sections}
  <div class="dg-post-support"><h4>Kontroluj polityków!</h4><p>Patrz władzy na ręce i wspieraj niezależność.</p></div>
 </div>
</div></body></html>"""


@unittest.skipIf(hd is None, f"ingest dependencies missing: {globals().get('_MISSING')}")
class MultiClaimPage(unittest.TestCase):
    def setUp(self):
        self.recs = [normalize_record(r) for r in hd.parse_page(URL, page())]
        self.by_claim = {r["claim"]: r for r in self.recs}

    def test_one_record_per_block(self):
        self.assertEqual(len(self.recs), 3)
        self.assertEqual(set(self.by_claim), {b["claimReviewed"] for b in BLOCKS})

    def test_main_record_keeps_the_page_id_and_the_block_stored_so_far(self):
        legacy = next(b for b in hd.jsonld_blocks(page()) if b.get("@type") == "ClaimReview")
        main = self.recs[0]
        self.assertEqual(main["id"], "demagog:fake_news/zielone-ksiezyce-i-inne-mity-test")
        self.assertEqual(main["claim"], legacy["claimReviewed"])
        self.assertEqual(hd.parse(URL, page())["claim"], main["claim"])  # parse() = the main record, as before

    def test_other_blocks_get_suffixed_ids_by_page_position(self):
        ids = {r["claim"]: r["id"] for r in self.recs}
        base = self.recs[0]["id"]
        self.assertEqual(ids["Nad Mazurami widać zielone księżyce."], base + "#1")
        self.assertEqual(ids["Kormorany przylatują nad jeziora tylko w nocy."], base + "#2")
        self.assertEqual(len(set(ids.values())), 3)

    def test_ids_are_stable_across_runs(self):
        again = [r["id"] for r in hd.parse_page(URL, page())]
        self.assertEqual(again, [r["id"] for r in self.recs])

    def test_each_record_has_its_own_rating_claimant_and_date(self):
        water = self.by_claim["Woda w jeziorze Testowym ma 30 stopni zimą."]
        self.assertEqual((water["verdict_raw"], water["verdict"]), ("Brakujący kontekst", "misleading"))
        self.assertEqual(water["claim_author"], "Profil Pogodowy")
        self.assertEqual(water["published_at"], "2031-05-05")
        moon = self.by_claim["Nad Mazurami widać zielone księżyce."]
        self.assertEqual((moon["verdict_raw"], moon["verdict"]), ("Fałsz", "false"))
        self.assertEqual(moon["claim_author"], "Użytkownicy Facebooka")
        self.assertEqual(moon["published_at"], "2031-05-04")

    def test_page_fields_are_shared(self):
        for r in self.recs:
            self.assertEqual((r["url"], r["title"], r["license"]), (URL, TITLE, hd.LICENSE))
            self.assertEqual(r["tags"], ["fake_news", "przyroda"])

    def test_headline_block_keeps_the_page_excerpt(self):
        moon = self.by_claim["Nad Mazurami widać zielone księżyce."]
        self.assertTrue(moon["text"].startswith("Trzy wpisy o Mazurach nie mają oparcia w faktach."))
        self.assertIn("W sieci krążą trzy wpisy o Mazurach.", moon["text"])  # summary box

    def test_other_blocks_get_lead_plus_their_own_section(self):
        birds = self.by_claim["Kormorany przylatują nad jeziora tylko w nocy."]["text"].split("\n")
        self.assertEqual(birds[0], "Trzy wpisy o Mazurach nie mają oparcia w faktach.")
        self.assertEqual(birds[1], "Kormorany i ich pory przelotów")
        self.assertIn("Nocne nagranie kormoranów z jednego jeziora krążyło bez daty.", birds)  # its h3 subsection
        joined = "\n".join(birds)
        for other in ("zielonego księżyca", "oczyszczalni", "Podsumowanie", "fake news w pigułce", "Kontroluj"):
            self.assertNotIn(other, joined)
        water = self.by_claim["Woda w jeziorze Testowym ma 30 stopni zimą."]["text"]
        self.assertIn("Średnia temperatura zimą wynosi 2 stopnie.", water)  # list items kept
        self.assertNotIn("Kormorany", water)

    def test_excerpts_are_verbatim_page_text(self):
        flat = " ".join(page().split())
        for r in self.recs:
            for line in r["text"].split("\n"):
                self.assertIn(line.removeprefix("- "), flat)  # "- " = trafilatura's list marker (page excerpt)

    def test_separate_script_tags_give_the_same_records(self):
        recs = hd.parse_page(URL, page(separate_scripts=True))
        self.assertEqual({r["claim"] for r in recs}, set(self.by_claim))
        # with one script per block, jsonld_blocks() meets the first page block first: that one is the main record
        self.assertEqual(recs[0]["claim"], BLOCKS[0]["claimReviewed"])
        self.assertEqual(recs[0]["id"], "demagog:fake_news/zielone-ksiezyce-i-inne-mity-test")


@unittest.skipIf(hd is None, f"ingest dependencies missing: {globals().get('_MISSING')}")
class EdgeCases(unittest.TestCase):
    def test_single_block_page_is_one_record_with_the_page_excerpt(self):
        recs = hd.parse_page(URL, page(blocks=[BLOCKS[1]]))
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["id"], "demagog:fake_news/zielone-ksiezyce-i-inne-mity-test")
        self.assertIn("W sieci krążą trzy wpisy o Mazurach.", recs[0]["text"])

    def test_page_without_claimreview_is_one_record_without_claim(self):
        recs = hd.parse_page(URL, page(blocks=[]))
        self.assertEqual(len(recs), 1)
        self.assertIsNone(recs[0]["claim"])
        self.assertIsNone(recs[0]["verdict"])

    def test_repeated_block_is_dropped(self):
        recs = hd.parse_page(URL, page(blocks=BLOCKS + [dict(BLOCKS[1])], separate_scripts=True))
        self.assertEqual(len(recs), 3)

    def test_no_matching_section_falls_back_to_the_page_excerpt(self):
        flat = "<h2>Jedna sekcja o wszystkim</h2><p>Opis bez szczegółów.</p>"
        recs = hd.parse_page(URL, page(sections=flat))
        for r in recs:
            self.assertIn("W sieci krążą trzy wpisy o Mazurach.", r["text"])

    def test_ambiguous_sections_fall_back(self):
        secs = [{"level": 0, "head": "", "lines": []},
                {"level": 2, "head": "Kormorany nad jeziorem", "lines": ["Kormorany latają nocą nad jeziorem."]},
                {"level": 2, "head": "Kormorany nad jeziorem raz jeszcze", "lines": ["Kormorany latają nocą."]}]
        self.assertIsNone(hd.block_excerpt("Kormorany latają nad jeziorem nocą.", secs, "lead"))

    def test_text_limit_is_unchanged(self):
        long = "<h2>Kormorany i ich pory przelotów</h2>" + "<p>Kormorany przylatują nad jeziora w dzień.</p>" * 200
        recs = hd.parse_page(URL, page(sections=long))
        for r in recs:
            self.assertLessEqual(len(hd.clip(r["text"], 3000)), 3000)
            self.assertLessEqual(len(normalize_record(dict(r, text=hd.clip(r["text"], 3000)))["text"]), 3000)


@unittest.skipIf(hd is None, f"ingest dependencies missing: {globals().get('_MISSING')}")
class CorpusFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_incremental_corpus_accepts_blocks_of_the_page_just_added(self):
        corpus = IncrementalCorpus("demagog", self.dir / "demagog.jsonl")
        recs = hd.parse_page(URL, page())
        self.assertTrue(corpus.add(recs[0]))
        self.assertTrue(all(corpus.add(r, same_page=True) for r in recs[1:]))
        self.assertFalse(corpus.add(dict(recs[1], id="demagog:fake_news/other")))  # same URL, not a page block
        self.assertFalse(corpus.add(recs[1], same_page=True))  # same id twice
        corpus.save()
        self.assertEqual(len((self.dir / "demagog.jsonl").read_text().splitlines()), 3)

    def test_reparse_cache_is_offline_and_keeps_stored_records(self):
        import requests

        raw = self.dir / "raw"
        raw.mkdir()
        full = requests.Request("GET", URL).prepare().url
        (raw / f"{hashlib.sha1(full.encode()).hexdigest()[:20]}.gz").write_bytes(gzip.compress(page().encode()))
        old = normalize_record(dict(hd.parse(URL, page()), retrieved_at="2030-01-01T00:00:00Z"))
        uncached = normalize_record(dict(old, id="demagog:fake_news/bez-kopii", url=URL.replace("test", "inny"),
                                         claim="Inne twierdzenie."))
        path = self.dir / "demagog.jsonl"
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in (old, uncached)), encoding="utf-8")
        with mock.patch("requests.Session.request", side_effect=AssertionError("network request")), \
                mock.patch("requests.Session.get", side_effect=AssertionError("network request")):
            self.assertEqual(hd.reparse_cache(path, raw, 3000), 0)
            hd.reparse_cache(path, raw, 3000)  # a second run rebuilds the same file
        rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 4)
        self.assertEqual(len({r["id"] for r in rows}), 4)
        by_id = {r["id"]: r for r in rows}
        self.assertEqual(by_id[uncached["id"]], uncached)  # no cached page: kept verbatim
        self.assertEqual(by_id[old["id"]]["claim"], old["claim"])
        self.assertTrue(all(r["retrieved_at"] == "2030-01-01T00:00:00Z" for r in rows))
        self.assertTrue(all(len(r["text"]) <= 3000 for r in rows))


if __name__ == "__main__":
    unittest.main()
