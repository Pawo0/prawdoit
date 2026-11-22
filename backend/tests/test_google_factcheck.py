"""Demagog "through the API" = Google Fact Check Tools API (claims:search), offline and without models.

Nobody can call the real API without PRAWDOWID_GOOGLE_FACTCHECK_KEY, so this test fixes the contract with a mocked
response shaped like Google's public reference (developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/
claims): Claim{text, claimant, claimDate, claimReview[]} and ClaimReview{publisher{name, site}, url, title,
reviewDate, textualRating, languageCode}. It checks that
  * the request carries query, languageCode=pl, the key, and — for the configured fact-checker sites — the
    reviewPublisherSiteFilter parameter (one extra query per site, so Demagog is not crowded out of 10 results);
  * only reviews published on a domain of an ENABLED registry source become evidence (SEO spam, foreign publishers
    and disabled sources are merely counted);
  * `textualRating` is mapped with exactly the rules used for the harvested corpus (ingest/common.py), including the
    Demagog labels that differ from plain true/false;
  * an outage is reported as a technical notice ("Indeks Google Fact Check jest teraz niedostępny…"), never as "no such
    article", and a missing key leaves the provider inactive without any request — reported as `nieaktywne`;
  * the key never appears in an error message.

Run:  backend/.venv/bin/python backend/tests/test_google_factcheck.py      (or pytest backend/tests)
"""
from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_TMP = tempfile.TemporaryDirectory()
os.environ.setdefault("PRAWDOWID_RUNTIME_DIR", _TMP.name)  # the audit store opens its SQLite file on import
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prawdowid import websearch as W  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
KEY = "test-key-123"
WROCLAW = "https://demagog.org.pl/wypowiedzi/darmowa-komunikacja-dla-65-latkow-tylko-we-wroclawiu-sprawdzamy/"

# Shape per Google's reference; the Demagog review is the one from the organisers' scenarios G and J.
RESPONSE = {"claims": [
    {"text": "Wrocław był jedynym miastem w Polsce, w którym 65-latkowie jeździli komunikacją miejską za darmo.",
     "claimant": "Polityk", "claimDate": "2026-10-01T00:00:00Z",
     "claimReview": [{"publisher": {"name": "Demagog", "site": "demagog.org.pl"}, "url": WROCLAW,
                      "title": "Darmowa komunikacja dla 65-latków tylko we Wrocławiu? Sprawdzamy",
                      "reviewDate": "2026-10-03T00:00:00Z", "textualRating": "Fałsz", "languageCode": "pl"}]},
    {"text": "Darmowa komunikacja dla seniorów — ranking miast",
     "claimReview": [{"publisher": {"name": "seo-sreo.pl", "site": "seo-sreo.pl"}, "url": "https://seo-sreo.pl/ranking",
                      "title": "Ranking", "textualRating": "Prawda", "languageCode": "pl"}]},
    {"text": "Seniors ride for free only in Wrocław",
     "claimReview": [{"publisher": {"name": "Example Fact Check", "site": "example.org"},
                      "url": "https://example.org/fact-check/1", "textualRating": "False", "languageCode": "en"}]},
    {"text": "Twierdzenie sprawdzone przez wyłączone źródło",
     "claimReview": [{"publisher": {"name": "FakeNews.pl", "site": "fakenews.pl"}, "url": "https://fakenews.pl/x/",
                      "title": "X", "textualRating": "Fałsz", "languageCode": "pl"}]},
]}

# Every distinct rating label in data/corpus/demagog.jsonl on 2026-11-21 (1,294 records) → class stored in the corpus.
DEMAGOG_LABELS = {
    "Fałsz": "false", "Falsz": "false", "Fałśz": "false", "Manipulacja": "misleading",
    "Brakujący kontekst": "misleading", "Brak kontekstu": "misleading", "Prawda": "true",
    "Częściowy fałsz": "mixed", "Częściowy Fałsz": "mixed", "Częściowa prawda": "mixed",
    "Nieweryfikowalne": "unverifiable", "Przerobione zdjęcie": "false", "Przerobiony film": "false",
    "Przerobione wideo": "false", "Przerobione nagranie": "false", "Przerobiony obraz": "false",
    "Przerobione zdjęcia": "false", "Przerobione zdjęcie lub film": "false", "Przerobiona grafika": "false",
    "Scam": "false", "Satyra": None,
}

# Every distinct `textualRating` the API itself returned on 2026-11-21 for the three Polish publishers it covers
# (claims:search, reviewPublisherSiteFilter=<site>, languageCode=pl, maxAgeDays=200: 429 + 19 + 39 reviews). The
# labels are free text in mixed case; each must land in the class the harvested corpus gives the same wording.
API_LABELS = {
    "demagog.org.pl": {
        "Fałsz": "false", "fałsz": "false", "Falsz": "false", "Fałśz": "false",
        "Manipulacja": "misleading", "manipulacja": "misleading",
        "Brakujący kontekst": "misleading", "brakujący kontekst": "misleading",
        "Brak kontekstu": "misleading", "brak kontekstu": "misleading",
        "Częściowa prawda": "mixed", "częściowa prawda": "mixed",
        "Częściowy fałsz": "mixed", "częściowy fałsz": "mixed", "Częściowy Fałsz": "mixed",
        "Prawda": "true", "prawda": "true", "Nieweryfikowalne": "unverifiable",
        "Przerobione zdjęcie": "false", "przerobione zdjęcie": "false", "Przerobione zdjęcia": "false",
        "Przerobiony film": "false", "przerobiony film": "false", "Przerobione wideo": "false",
        "przerobione zdjęcie lub film": "false", "Satyra": None},
    "fakenews.pl": {"Fałsz": "false", "fałsz": "false", "manipulacja": "misleading", "Brak kontekstu": "misleading"},
    "sprawdzam.afp.com": {"Fałsz": "false", "Obraz AI": "false", "Mylące": "misleading",
                          "Przerobione wideo": "false", "Brak kontekstu": "misleading"},
}


def _source(sid: str, url: str, category: str, enabled: bool = True, **params) -> dict:
    return {"id": sid, "name": sid, "publisher": sid.capitalize(), "url": url, "category": category,
            "tier": 2 if category == "factcheck" else 1, "method": "reference_only", "params": params,
            "enabled": enabled, "web_search": True, "license": f"licencja {sid}", "qualification": "test"}


class _Resp:
    def __init__(self, status: int = 200, body: dict | None = None):
        self.status_code, self._body = status, body

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class GoogleFactCheckTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        d = Path(self.dir.name)
        for s in (_source("demagog", "https://demagog.org.pl/", "factcheck"),
                  _source("fakenews_pl", "https://fakenews.pl/", "factcheck", enabled=False),
                  _source("gov", "https://www.gov.pl/", "official"),
                  {**_source("google_factcheck", "https://toolbox.google.com/factcheck/explorer", "factcheck",
                             publisher_sites=["demagog.org.pl", "fakenews.pl"]), "method": "google_factcheck"}):
            (d / f"{s['id']}.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
        self.calls: list[dict] = []
        self.response = _Resp(200, RESPONSE)

        def fake_get(url, **kw):
            self.calls.append({"url": url, **kw})
            return self.response

        patches = [mock.patch.object(W, "SOURCES_DIR", d), mock.patch.object(W.httpx, "get", fake_get),
                   mock.patch.object(W.store, "log_error", lambda *a, **k: None),
                   mock.patch.dict(os.environ, {"PRAWDOWID_GOOGLE_FACTCHECK_KEY": KEY, "PRAWDOWID_LIVE_SEARCH": "1",
                                                "PRAWDOWID_FORCE_FAIL": ""})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.dir.cleanup)
        W._REG_CACHE.update(key=None, sources=[])
        W._GFC_CACHE.clear()

    # ---------------------------------------------------------------- rating labels
    def test_rating_rules_are_the_ingest_rules(self):
        tree = ast.parse((ROOT / "ingest" / "common.py").read_text(encoding="utf-8"))
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.AnnAssign)
                    and getattr(n.target, "id", "") == "_VERDICT_RULES")
        self.assertEqual([tuple(x) for x in ast.literal_eval(node.value)], W._VERDICT_RULES)

    def test_demagog_labels_map_to_the_corpus_classes(self):
        for label, expected in DEMAGOG_LABELS.items():
            self.assertEqual(W.map_rating(label), expected, label)
        for label, expected in (("W większości fałsz", "mixed"), ("W większości prawda", "mixed"),
                                ("Brak dowodów", "unverifiable"), ("Mostly false", "mixed"), ("", None), (None, None)):
            self.assertEqual(W.map_rating(label), expected, label)

    def test_every_label_the_api_returned_maps_to_its_class(self):
        self.assertEqual(len(API_LABELS["demagog.org.pl"]), 26)
        for site, labels in API_LABELS.items():
            for label, expected in labels.items():
                self.assertEqual(W.map_rating(label), expected, f"{site}: {label!r}")
        # a lower-case API label means the same as the capitalised corpus label
        for label, expected in DEMAGOG_LABELS.items():
            self.assertEqual(W.map_rating(label.lower()), expected, label.lower())

    # ---------------------------------------------------------------- request
    def test_request_parameters(self):
        claims = W.google_factcheck("Czy Wrocław był jedynym miastem z darmowymi przejazdami dla 65-latków?")
        self.assertEqual(len(claims), 4)
        call = self.calls[0]
        self.assertEqual(call["url"], "https://factchecktools.googleapis.com/v1alpha1/claims:search")
        self.assertEqual(call["params"]["languageCode"], "pl")
        self.assertEqual(call["headers"]["X-Goog-Api-Key"], KEY)
        self.assertNotIn("key", call["params"])  # never in the URL: request URLs are logged
        self.assertIn("65-latków", call["params"]["query"])
        self.assertNotIn("reviewPublisherSiteFilter", call["params"])
        W.google_factcheck("darmowe przejazdy 65-latków", site="demagog.org.pl")
        self.assertEqual(self.calls[1]["params"]["reviewPublisherSiteFilter"], "demagog.org.pl")

    def test_publisher_sites_come_from_enabled_registry_sources_only(self):
        self.assertEqual(W.google_publisher_sites(), ["demagog.org.pl"])  # fakenews.pl is disabled in this registry

    # ---------------------------------------------------------------- evidence
    def test_only_reviews_from_enabled_registry_domains_become_evidence(self):
        docs, other = W.google_docs(RESPONSE["claims"] + RESPONSE["claims"][:1])  # duplicate review: kept once
        self.assertEqual(other, 3)  # SEO spam, foreign publisher, disabled source
        self.assertEqual(len(docs), 1)
        d = docs[0]
        self.assertEqual((d.domain, d.url, d.source_type, d.publisher), ("demagog.org.pl", WROCLAW, "factcheck", "Demagog"))
        self.assertEqual((d.verdict_raw, d.verdict, d.published_at, d.language), ("Fałsz", "false", "2026-10-03", "pl"))
        self.assertIn("65-latkowie", d.claim)
        self.assertIn(d.claim, d.text)  # the quoted fragment is the publisher's own ClaimReview text
        self.assertEqual(d.license, "licencja demagog")
        self.assertTrue({"google_factcheck", "live_search", "registry:demagog", "tier:2"} <= set(d.tags))
        self.assertTrue(d.retrieved_at)

    def test_review_without_a_rating_is_not_evidence(self):
        claim = json.loads(json.dumps(RESPONSE["claims"][0]))
        claim["claimReview"][0].pop("textualRating")
        self.assertEqual(W.google_docs([claim]), ([], 0))

    # ---------------------------------------------------------------- orchestration (scenario J)
    def _stage(self):
        stage = W.LiveStage("test-check")
        stage.start_google([SimpleNamespace(query="Wrocław jedynym miastem z darmowymi przejazdami dla 65-latków",
                                            kind="fakt"),
                            SimpleNamespace(query="Uważam, że to dobra decyzja", kind="opinia")])
        return stage

    def test_live_stage_sends_keywords_and_stops_at_the_first_hit(self):
        stage = self._stage()
        docs = stage._join_google()
        self.assertEqual(len(self.calls), 1)  # first round answered; the opinion is never sent
        q = self.calls[0]["params"]["query"]
        self.assertLessEqual(len(q.split()), 4)  # keywords, not the sentence: the API returns nothing for sentences
        self.assertIn("Wrocław", q)
        self.assertNotIn("reviewPublisherSiteFilter", self.calls[0]["params"])
        self.assertEqual([d.url for d in docs], [WROCLAW])
        self.assertEqual((stage.google["status"], stage.google["n_results"]), ("ok", 1))
        self.assertEqual(stage.warnings, [])

    def test_query_rounds_go_from_specific_to_loose(self):
        rounds = W.google_queries("Czy PAP usunęła depeszę o wypowiedzi Donalda Tuska przed powodzią?")
        self.assertEqual(len(rounds[0]), 1)
        self.assertEqual(len(rounds[0][0].split()), 4)
        self.assertIn(["PAP usunęła depeszę o"], rounds)  # the claim's opening words, question particle dropped
        self.assertTrue(all(len(q.split()) == 2 for q in rounds[-1]))
        flat = [q for r in rounds for q in r]
        self.assertEqual(len(flat), len(set(flat)))

    def test_no_result_rounds_continue_and_a_crowded_page_is_repeated_for_the_publisher(self):
        spam = {"claims": [RESPONSE["claims"][1]] * 10}

        def fake_get(url, **kw):
            self.calls.append({"url": url, **kw})
            if kw["params"].get("reviewPublisherSiteFilter") == "demagog.org.pl":
                return _Resp(200, {"claims": RESPONSE["claims"][:1]})
            return _Resp(200, {} if len(self.calls) == 1 else spam)  # round 1: nothing; round 2: 10 other publishers

        with mock.patch.object(W.httpx, "get", fake_get):
            claims = W.google_search("Wrocław był jedynym miastem z darmowymi przejazdami dla 65-latków")
        self.assertEqual([c["params"].get("reviewPublisherSiteFilter", "") for c in self.calls], ["", "", "demagog.org.pl"])
        docs, other = W.google_docs(claims)
        self.assertEqual(([d.url for d in docs], other), ([WROCLAW], 1))

    def test_outage_is_a_notice_not_a_verdict(self):
        self.response = _Resp(403, {"error": {"message": f"API key not valid: {KEY}"}})
        stage = self._stage()
        self.assertEqual(stage._join_google(), [])
        self.assertEqual(stage.google["status"], "blad")
        self.assertEqual(stage.warnings, [W.NOTICE_GOOGLE_FAIL])
        self.assertIn("niedostępny (błąd techniczny)", W.NOTICE_GOOGLE_FAIL)
        with self.assertRaises(W.LiveError) as ctx:
            W.google_factcheck("inne pytanie")
        self.assertNotIn(KEY, str(ctx.exception))

    def test_forced_failure_switch(self):
        with mock.patch.dict(os.environ, {"PRAWDOWID_FORCE_FAIL": "google_factcheck", "PRAWDOWID_GOOGLE_FACTCHECK_KEY": ""}):
            stage = self._stage()
            self.assertEqual(stage._join_google(), [])
        self.assertEqual(self.calls, [])
        self.assertEqual(stage.warnings, [W.NOTICE_GOOGLE_FAIL])

    def test_without_a_key_nothing_is_sent(self):
        with mock.patch.dict(os.environ, {"PRAWDOWID_GOOGLE_FACTCHECK_KEY": ""}):
            stage = self._stage()
            self.assertEqual(stage._join_google(), [])
        self.assertEqual(self.calls, [])
        # provider inactive: no request and no "no reviews" result, but the result says why (rules §5: a missing key
        # must not look like a result) — a `nieaktywne` step and a line for engine.unavailable, not a user warning
        self.assertEqual(stage.google["status"], "nieaktywne")
        self.assertEqual(stage.google["notice"], W.NOTICE_GOOGLE_OFF)
        self.assertEqual(stage.inactive(), [W.NOTICE_GOOGLE_OFF])
        self.assertEqual(stage.warnings, [])
        self.assertEqual(stage.info().status, "nieaktywne")


class GoogleFactCheckFeedTest(unittest.TestCase):
    """The registry source that lists one publisher's recent reviews (source_handlers/google_factcheck_feed.py)."""

    def setUp(self):
        from datetime import date, timedelta

        from prawdowid.source_handlers import google_factcheck_feed as G

        self.G = G
        self.today = date.today()
        day = lambda n: (self.today - timedelta(days=n)).isoformat() + "T00:00:00Z"  # noqa: E731

        def review(slug, title, claim, rating, age, site="demagog.org.pl", section="fake_news"):
            url = (f"https://demagog.org.pl/{section}/{slug}/" if site == "demagog.org.pl"
                   else f"https://{site}/{slug}")
            return {"text": claim, "claimant": "użytkownicy", "claimDate": day(age + 3),
                    "claimReview": [{"publisher": {"name": "X", "site": site}, "url": url, "title": title,
                                     "reviewDate": day(age), "textualRating": rating, "languageCode": "pl"}]}

        self.page1 = {"claims": [
            review("most-krymski", "Zniszczony Most Krymski. Uważaj na przerobione zdjęcie", "Zniszczono most krymski.",
                   "przerobione zdjęcie", 1),
            review("juz-w-korpusie", "Tytuł", "Twierdzenie, które jest już w korpusie stron.", "Fałsz", 2),
            review("stara-ocena", "Stara ocena", "Twierdzenie sprzed lat, które wróciło.", "Fałsz", 900),
            {**review("inna", "Inny wydawca", "Twierdzenie ocenione przez dwóch wydawców.", "Fałsz", 2, site="fakenews.pl")},
        ], "nextPageToken": "CGQ"}
        self.page2 = {"claims": [
            review("czesciowy", "Czy to prawda? Sprawdzamy", "Wypowiedź polityka o budżecie.", "częściowy fałsz", 5,
                   section="wypowiedzi"),
            review("bez-oceny", "Bez oceny", "Twierdzenie bez etykiety.", "", 5),
        ]}
        self.calls: list[dict] = []

        def get(url, **kw):
            self.calls.append({"url": url, **kw})
            return _Resp(200, self.page2 if kw["params"].get("pageToken") else self.page1)

        self.get = get
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        (Path(self.tmp.name) / "demagog.jsonl").write_text(
            json.dumps({"url": "https://demagog.org.pl/fake_news/juz-w-korpusie/"}) + "\n", encoding="utf-8")
        self.source = {"id": "demagog_google_api", "topics": ["dezinformacja"],
                       "params": {"site": "demagog.org.pl", "max_age_days": 200, "delay": 0.5,
                                  "dedupe_against": ["demagog"], "id_prefix": "demagog"}}
        from prawdowid.sources import registry

        # no registry file for "demagog" in this directory = a corpus file the index loads anyway
        tmp_dirs = SimpleNamespace(corpus_dir=Path(self.tmp.name), sources_dir=Path(self.tmp.name))
        for p in (mock.patch.object(registry, "settings", tmp_dirs),
                  mock.patch.object(G.time, "sleep", lambda s: None),
                  mock.patch.dict(os.environ, {"PRAWDOWID_GOOGLE_FACTCHECK_KEY": KEY})):
            p.start()
            self.addCleanup(p.stop)

    def test_pages_filters_and_record_shape(self):
        recs = self.G.fetch(self.source, get=self.get)
        self.assertEqual([c["params"].get("pageToken", "") for c in self.calls], ["", "CGQ"])
        for c in self.calls:
            self.assertEqual(c["params"]["reviewPublisherSiteFilter"], "demagog.org.pl")
            self.assertEqual((c["params"]["languageCode"], c["params"]["maxAgeDays"]), ("pl", 200))
            self.assertEqual(c["headers"]["X-Goog-Api-Key"], KEY)
            self.assertNotIn("key", c["params"])
        # kept: the new review of each page; dropped: already harvested page, old review, other publisher, no rating
        self.assertEqual([r["id"] for r in recs], ["demagog:fake_news/most-krymski", "demagog:wypowiedzi/czesciowy"])
        r = recs[0]
        self.assertEqual(r["text"], "Zniszczony Most Krymski. Uważaj na przerobione zdjęcie\nZniszczono most krymski.")
        self.assertEqual((r["claim"], r["verdict_raw"], r["verdict"]), ("Zniszczono most krymski.", "Przerobione zdjęcie", "false"))
        self.assertEqual(recs[1]["verdict"], "mixed")
        self.assertTrue({"claimreview-only", "via:api", "google_factcheck", "demagog_google_api"} <= set(r["tags"]))
        self.assertEqual(r["published_at"], (self.today.fromordinal(self.today.toordinal() - 1)).isoformat())

    def test_records_pass_the_corpus_schema_and_keep_the_shared_id(self):
        from prawdowid.sources import fetchers

        src = {**self.source, "category": "factcheck", "publisher": "Demagog", "license": "licencja", "language": "pl"}
        out = [fetchers.normalize_record(r, src) for r in self.G.fetch(self.source, get=self.get)]
        self.assertTrue(all(out))
        self.assertEqual(out[0]["id"], "demagog:fake_news/most-krymski")  # same id as the page harvest → one copy
        self.assertEqual((out[0]["publisher"], out[0]["source_type"], out[0]["domain"]),
                         ("Demagog", "factcheck", "demagog.org.pl"))
        other = fetchers.normalize_record({"id": "x:1", "url": "https://example.org/a", "text": "t"}, src)
        self.assertEqual(other["id"], "demagog_google_api:x:1")  # foreign namespaces are still prefixed

    def test_a_claim_that_restates_the_headline_gets_no_verdict(self):
        claim = {"text": "Nagranie nie pokazuje uwolnienia czternastolatka rzekomo więzionego w piwnicy pod Kijowem"}
        review = {"url": "https://sprawdzam.afp.com/doc.afp.com.X", "textualRating": "Fałsz", "reviewDate": "2026-11-18T00:00:00Z",
                  "title": "Wideo nie pokazuje uwolnienia czternastolatka rzekomo więzionego w piwnicy pod Kijowem"}
        rec = self.G.to_record(claim, review, "sprawdzam.afp.com")
        self.assertEqual((rec["claim"], rec["verdict"], rec["verdict_raw"]), (None, None, "Fałsz"))
        self.assertIn("claim-restates-title", rec["tags"])
        asked = self.G.to_record({"text": "Kamizelki kuloodporne tylko dla Ukraińców"},
                                 {**review, "title": "Kamizelki kuloodporne tylko dla Ukraińców? Przepisy są inne"},
                                 "sprawdzam.afp.com")
        self.assertEqual(asked["verdict"], "false")  # a question headline repeats the claim in order to answer it

    def test_missing_key_and_refused_key_are_plain_errors_without_the_key(self):
        with mock.patch.dict(os.environ, {"PRAWDOWID_GOOGLE_FACTCHECK_KEY": ""}):
            with self.assertRaises(self.G.ApiError) as ctx:
                self.G.fetch(self.source, get=self.get)
        self.assertIn("brak klucza", str(ctx.exception))
        self.assertEqual(self.calls, [])
        with self.assertRaises(self.G.ApiError) as ctx:
            self.G.fetch(self.source, get=lambda url, **kw: _Resp(403, {"error": {"message": KEY}}))
        self.assertNotIn(KEY, str(ctx.exception))
        self.assertIn(self.G.ApiError, self.G.EXPECTED_ERRORS)

    def test_a_scheduled_run_stores_nothing_but_the_dry_run_still_previews(self):
        from prawdowid.sources import fetchers

        src = {**self.source, "category": "factcheck", "publisher": "Demagog", "license": "l", "language": "pl",
               "method": "custom", "params": {**self.source["params"], "handler": "google_factcheck_feed"}}
        with mock.patch.object(self.G, "call", lambda *a, **kw: self.page1):
            with self.assertRaises(fetchers.FetchError) as ctx:
                fetchers.fetch_custom(src, fetchers.Ctx())
            self.assertIn("nie są zapisywane", str(ctx.exception))
            self.assertIs(self.G.PERSIST, False)
            self.assertTrue(fetchers.fetch_custom(src, fetchers.Ctx(limit=2)))  # preview only, nothing written

    def test_lower_case_label_is_stored_capitalised_with_the_same_class(self):
        for label in ("fałsz", "manipulacja", "brakujący kontekst", "przerobione zdjęcie lub film"):
            rec = self.G.to_record({"text": "Minister zapowiedział podwyżkę podatku od wszystkich samochodów."},
                                   {"url": "https://fakenews.pl/polityka/x/", "textualRating": label,
                                    "title": "Czy minister zapowiedział podwyżkę?", "reviewDate": "2026-10-01T00:00:00Z"},
                                   "fakenews.pl")
            self.assertEqual(rec["verdict_raw"], label[0].upper() + label[1:])
            self.assertEqual(rec["verdict"], W.map_rating(label))

    def test_demagog_id_keeps_the_harvests_lower_case_escapes(self):
        # the page harvest stores "demagog:wypowiedzi/emisja-co%e2%82%82-…"; the API sends the URL with "%E2%82%82"
        rec = self.G.to_record({"text": "Emisja dwutlenku węgla na mieszkańca w Polsce jest najniższa w Unii."},
                               {"url": "https://demagog.org.pl/wypowiedzi/emisja-co%E2%82%82-w-przeliczeniu/",
                                "textualRating": "Fałsz", "title": "Emisja CO₂ w przeliczeniu na mieszkańca",
                                "reviewDate": "2026-10-01T00:00:00Z"}, "demagog.org.pl")
        self.assertEqual(rec["id"], "demagog:wypowiedzi/emisja-co%e2%82%82-w-przeliczeniu")


class SecondRouteDedupeTest(unittest.TestCase):
    """A publisher reached through the API AND by a page harvest with ids of its own (fakenews.pl: numeric post ids,
    the API gives only the URL). Only sources the index loads count; their URLs are skipped at fetch time and pruned
    from the API feed's file at merge time, so one review is indexed once in every registry configuration."""

    def setUp(self):
        from prawdowid.source_handlers import google_factcheck_feed as G
        from prawdowid.sources import fetchers, registry

        self.F, self.G = fetchers, G
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.src_dir, self.corpus = root / "sources", root / "corpus"
        self.src_dir.mkdir()
        self.corpus.mkdir()
        for p in (mock.patch.object(registry, "settings", SimpleNamespace(sources_dir=self.src_dir, corpus_dir=self.corpus)),
                  mock.patch.object(G.time, "sleep", lambda s: None),
                  mock.patch.dict(os.environ, {"PRAWDOWID_GOOGLE_FACTCHECK_KEY": KEY})):
            p.start()
            self.addCleanup(p.stop)
        self._harvest(enabled=True)
        (self.corpus / "fakenews_pl.jsonl").write_text(
            json.dumps({"id": "fakenews_pl:25674", "url": "https://fakenews.pl/srodowisko/farmy/"}) + "\n", encoding="utf-8")
        self.feed = {"id": "fakenews_google_api", "category": "factcheck", "publisher": "FakeNews.pl", "license": "l",
                     "language": "pl", "params": {"site": "fakenews.pl", "dedupe_against": ["fakenews_pl"],
                                                  "max_age_days": 200, "max_docs": 100}}

    def _harvest(self, enabled: bool) -> None:
        (self.src_dir / "fakenews_pl.json").write_text(json.dumps({"id": "fakenews_pl", "enabled": enabled}), encoding="utf-8")

    def _api(self, *slugs):
        from datetime import date

        claims = [{"text": f"Twierdzenie numer {i} krążące w sieci.", "claimReview": [{
            "url": f"https://fakenews.pl/srodowisko/{s}/", "title": f"Ocena {i}", "textualRating": "fałsz",
            "reviewDate": date.today().isoformat() + "T00:00:00Z", "languageCode": "pl"}]} for i, s in enumerate(slugs)]
        return lambda url, **kw: _Resp(200, {"claims": claims})

    def test_only_sources_the_index_loads_count(self):
        self.assertEqual(self.F.urls_held_by(["fakenews_pl"]), {"https://fakenews.pl/srodowisko/farmy"})
        self._harvest(enabled=False)
        self.assertEqual(self.F.urls_held_by(["fakenews_pl"]), set())
        (self.corpus / "bez_wpisu.jsonl").write_text(json.dumps({"url": "https://FakeNews.pl/x/#a"}) + "\n", encoding="utf-8")
        self.assertEqual(self.F.urls_held_by(["bez_wpisu", "../etc", None]), {"https://fakenews.pl/x"})

    def test_fetch_skips_the_harvested_review_unless_the_harvest_is_off(self):
        get = self._api("farmy", "nowa")
        self.assertEqual([r["url"] for r in self.G.fetch(self.feed, get=get)], ["https://fakenews.pl/srodowisko/nowa/"])
        self._harvest(enabled=False)
        self.assertEqual(len(self.G.fetch(self.feed, get=get)), 2)

    def test_percent_escapes_in_either_case_are_the_same_page(self):
        # measured 2026-11-21: fakenews_pl held ".../emisji-co%e2%82%82-…/", the API listed ".../emisji-co%E2%82%82-…/"
        (self.corpus / "fakenews_pl.jsonl").write_text(
            json.dumps({"id": "fakenews_pl:1", "url": "https://fakenews.pl/srodowisko/emisji-co%e2%82%82/"}) + "\n",
            encoding="utf-8")
        self.assertEqual(self.G.fetch(self.feed, get=self._api("emisji-co%E2%82%82")), [])
        self.assertEqual(self.F.url_key("https://fakenews.pl/a/co%E2%82%82/"), self.F.url_key("https://fakenews.pl/a/co₂"))
        self.assertNotEqual(self.F.url_key("https://fakenews.pl/a/?p=1"), self.F.url_key("https://fakenews.pl/a/?p=2"))

    def test_merge_prunes_a_stored_copy_once_the_harvest_has_it(self):
        row = lambda slug, d: {"id": f"fakenews_google_api:{slug}", "url": f"https://fakenews.pl/srodowisko/{slug}/",  # noqa: E731
                               "published_at": d}
        (self.corpus / "fakenews_google_api.jsonl").write_text(
            json.dumps(row("farmy", "2026-11-13")) + "\n" + json.dumps(row("starsza", "2026-09-01")) + "\n", encoding="utf-8")
        self.assertEqual(self.F.merge_into_corpus(self.feed, [row("nowa", "2026-11-20")]), (1, 2))
        self.assertEqual([r["id"] for r in self.F.read_corpus("fakenews_google_api")],
                         ["fakenews_google_api:nowa", "fakenews_google_api:starsza"])  # newest first, harvested copy gone


if __name__ == "__main__":
    unittest.main(verbosity=2)
