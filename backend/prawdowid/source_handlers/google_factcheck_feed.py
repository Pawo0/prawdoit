"""Reviews of one fact-checker from the Google Fact Check Tools API — "Demagog through the API".

  GET https://factchecktools.googleapis.com/v1alpha1/claims:search
      ?reviewPublisherSiteFilter=<site>&languageCode=pl&maxAgeDays=<n>&pageSize=<≤100>[&pageToken=…]
      header X-Goog-Api-Key: <API key>
  ->{claims: [{text, claimant, claimDate, claimReview: [{publisher: {name, site}, url, title, reviewDate,
                textualRating, languageCode}]}], nextPageToken}

`query` may be omitted when the site filter is set, so the call lists a publisher's reviews, newest first (roughly:
not strictly sorted) and paginated; `maxAgeDays` keeps it to recent material. This is the database the organisers
name in rules/resources.txt ("Baza weryfikatorów faktów"); Demagog's own REST API answers 401. Measured 2026-11-21:
demagog.org.pl 429 reviews in the last 200 days in 5 calls, sprawdzam.afp.com 74 in the last 400 days in 1 call,
0.2–1.0 s per call, no throttling and no quota headers.

What a record holds — and what may be quoted. The API gives the publisher's own ClaimReview fields and NO article
text. A record's `text` is therefore exactly two verbatim strings written by the fact-checker: the review title and
the claim it reviewed (`claimReviewed`); `verdict_raw` is its rating label. A quotation taken from such a record is
the fact-checker's title or its wording of the checked claim, shown next to the rating and the link — it documents
THAT the publisher checked this claim and how it rated it. It is not a passage of the article's reasoning, and the
record says so in its tags (`claimreview-only`). Where the article itself is in the corpus (Demagog page harvest),
that fuller record is used instead: URLs already present in the corpora named in `params.dedupe_against` are
skipped, and Demagog records get the same id as the page harvest (`demagog:<section>/<slug>`), so the index keeps
only the first one even if both files end up holding the same review.

Key: environment variable named in `params.key_env` (default PRAWDOWID_GOOGLE_FACTCHECK_KEY) — never in a file,
never in a log line or an error message. Without it the run ends with a plain "brak klucza" status.

params: site (required, e.g. "demagog.org.pl"), max_age_days (200), page_size (100), max_pages (10), delay (1.0 s
between calls), key_env, dedupe_against (corpus ids whose URLs are skipped), id_prefix (see fetchers.normalize_record).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import date, timedelta
from urllib.parse import urlsplit

import httpx

from ..config import settings

log = logging.getLogger("prawdowid.sources.google_factcheck_feed")

API = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
UA = "PrawdowidHackathonBot/0.1 (research prototype)"
MAX_PAGES_CAP = 30


class ApiError(RuntimeError):
    """The API cannot be used right now (message is shown to the admin; it never contains the key)."""


EXPECTED_ERRORS = (ApiError,)


def _host(url: str) -> str:
    h = (urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def _ws(s: object) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def restates_title(claim: str, title: str) -> bool:
    """The 'claim' is (nearly) the review's declarative headline: at least 60% of the words of both are shared.
    A headline that asks a question ("…tylko dla Ukraińców? Przepisy są inne") repeats the claim in order to
    answer it and is not a restated conclusion. Measured 2026-11-21: 2 of 74 AFP reviews, 0 of 408 Demagog."""
    if "?" in title:
        return False
    a, b = (set(re.findall(r"\w{3,}", s.lower())) for s in (claim, title))
    return bool(a and b) and len(a & b) / len(a | b) >= 0.6


def _known_urls(corpus_ids: list[str]) -> set[str]:
    out: set[str] = set()
    for cid in corpus_ids:
        f = settings.corpus_dir / f"{cid}.jsonl"
        if not re.fullmatch(r"[a-z0-9_]{2,64}", str(cid)) or not f.exists():
            continue
        for line in f.open(encoding="utf-8"):
            try:
                out.add((json.loads(line).get("url") or "").rstrip("/"))
            except json.JSONDecodeError:
                continue
    return out


def call(site: str, key: str, *, max_age_days: int, page_size: int, page_token: str = "", timeout: float = 20.0,
         get=httpx.get) -> dict:
    """One page. Raises ApiError with a message that cannot contain the key."""
    params = {"reviewPublisherSiteFilter": site, "languageCode": "pl", "pageSize": page_size}
    if max_age_days:
        params["maxAgeDays"] = max_age_days
    if page_token:
        params["pageToken"] = page_token
    try:
        # the key travels in a header, not in the URL: httpx logs every request URL at INFO level
        r = get(API, params=params, timeout=timeout, headers={"User-Agent": UA, "X-Goog-Api-Key": key})
    except httpx.HTTPError as e:
        raise ApiError(f"Google Fact Check Tools API: błąd połączenia ({type(e).__name__}).") from None
    if r.status_code in (400, 401, 403):
        raise ApiError(f"Google Fact Check Tools API odrzuciło zapytanie (HTTP {r.status_code}) — sprawdź klucz i czy "
                       "w projekcie Google Cloud włączono „Fact Check Tools API”.")
    if r.status_code == 429:
        raise ApiError("Google Fact Check Tools API: przekroczony limit zapytań (HTTP 429) — spróbujemy później.")
    if r.status_code != 200:
        raise ApiError(f"Google Fact Check Tools API: HTTP {r.status_code}.")
    try:
        return r.json()
    except ValueError:
        raise ApiError("Google Fact Check Tools API: odpowiedź nie jest poprawnym JSON.") from None


def to_record(claim: dict, review: dict, site: str) -> dict | None:
    """One ClaimReview of `site` -> corpus record (None when it is another publisher's or has no rating/claim)."""
    from ..websearch import map_rating  # the same rating rules as the harvested corpus

    url = _ws(review.get("url"))
    host = _host(url)
    if not url or not (host == site or host.endswith("." + site)):
        return None  # a claim can carry reviews by several publishers; only the filtered one belongs here
    claim_text = _ws(claim.get("text"))
    rating = _ws(review.get("textualRating"))
    if not claim_text or not rating:
        return None
    title = _ws(review.get("title")) or claim_text
    rec = {
        "url": url, "title": title,
        # verbatim ClaimReview fields of the publisher: review title + the claim it reviewed (no article text)
        "text": title if title == claim_text else f"{title}\n{claim_text}",
        "published_at": (_ws(review.get("reviewDate")) or _ws(claim.get("claimDate")))[:10] or None,
        "language": _ws(review.get("languageCode"))[:2] or "pl",
        "claim": claim_text, "claim_author": _ws(claim.get("claimant")) or None,
        "verdict_raw": rating[:1].upper() + rating[1:], "verdict": map_rating(rating),
        "tags": ["google_factcheck", "via:api", "claimreview-only"],
    }
    if restates_title(claim_text, title):
        # Some publishers put their own conclusion into claimReviewed ("Nagranie nie pokazuje…", rated "Fałsz").
        # The rating then cannot be attached to that sentence — it would call the debunk itself false. Such a
        # record stays as context (title, label, link) without a claim or a verdict class.
        rec["claim"], rec["verdict"] = None, None
        rec["tags"].append("claim-restates-title")
    if site == "demagog.org.pl":  # same id as ingest/harvest_demagog.py, so the index never holds both copies
        m = re.match(r"^/(wypowiedzi|fake_news)/([^/]+)/?$", urlsplit(url).path)
        if m:
            rec["id"] = f"demagog:{m.group(1)}/{m.group(2)}"
    return rec


def fetch(source: dict, get=httpx.get) -> list[dict]:
    p = source.get("params") or {}
    site = _host(f"https://{p.get('site')}") if p.get("site") else ""
    if not site:
        raise ApiError("params.site: podaj domenę wydawcy, np. demagog.org.pl.")
    key_env = str(p.get("key_env") or "PRAWDOWID_GOOGLE_FACTCHECK_KEY")
    key = os.environ.get(key_env, "").strip()
    if not key:
        raise ApiError(f"brak klucza: zmienna środowiskowa {key_env} nie jest ustawiona — nic nie wysłano.")
    limit = int(p.get("max_items") or 0)  # dry run ("Testuj") asks for a few records only
    page_size = max(1, min(int(p.get("page_size") or 100), 100)) if not limit else min(20, max(5, 2 * limit))
    max_pages = 1 if limit else max(1, min(int(p.get("max_pages") or 10), MAX_PAGES_CAP))
    delay = max(0.5, float(p.get("delay") or 1.0))
    skip = {u.rstrip("/") for u in source.get("_known_urls") or []} | _known_urls(list(p.get("dedupe_against") or []))
    max_age = int(p.get("max_age_days") or 200)
    # maxAgeDays counts from the newer of claim date and review date, so the API also returns old reviews of claims
    # that resurfaced; the knowledge base wants recent reviews, hence the same limit on the review date here
    oldest = (date.today() - timedelta(days=max_age)).isoformat()
    out, seen, token, n_reviews = [], set(), "", 0
    for page in range(max_pages):
        if page:
            time.sleep(delay)
        data = call(site, key, max_age_days=max_age, page_size=page_size, page_token=token, get=get)
        for claim in data.get("claims") or []:
            for review in claim.get("claimReview") or []:
                rec = to_record(claim, review, site)
                if not rec:
                    continue
                n_reviews += 1
                u = rec["url"].rstrip("/")
                if u in skip or u in seen or (rec["published_at"] or "9999") < oldest:
                    continue
                seen.add(u)
                rec["tags"] = sorted({source.get("id", "google_factcheck"), *(source.get("topics") or []), *rec["tags"]})
                out.append(rec)
        token = data.get("nextPageToken") or ""
        if not token or (limit and len(out) >= limit):
            break
    log.info("google_factcheck_feed %s: %d reviews seen, %d new records, %d call(s)", site, n_reviews, len(out), page + 1)
    return out[:limit] if limit else out
