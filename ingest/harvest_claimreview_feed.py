#!/usr/bin/env python3
"""Polish ClaimReviews from the Google Fact Check Tools / Data Commons ClaimReview feed.

Feed: https://storage.googleapis.com/datacommons-feeds/claimreview/latest/data.json
(~200 MB schema.org DataFeed, ~100k ClaimReviews, refreshed daily; sdPublisher
"Google Fact Check Tools" -> i.e. reviews entered via Google's Fact Check Markup Tool).
We STREAM it (ijson, nothing big stored) and keep ClaimReviews whose review URL is on an
allow-listed Polish fact-checker domain.

Finding (2026-11-21): the feed contains Polish reviews ONLY from pravda.org.pl (~211) and one
from oko.press; AFP Sprawdzam, Demagog, FakeNews.pl, Konkret24 do not use the Markup Tool,
so they are absent. Polish-language reviews from non-allow-listed domains are SEO spam
(seo-sreo.pl, synergiczni.pl) and are only counted.

Output: data/raw/claimreview_feed_pl.jsonl (intermediate lookup, one raw-ish record per review)
consumed by harvest_pravda.py (which adds the article text from pravda.org.pl).
"""
from __future__ import annotations

import json
import re
from collections import Counter
from urllib.parse import urlsplit

import ijson
import requests

from common import RAW_DIR, UA, clean_text, iso_date, log, now_iso

FEED = "https://storage.googleapis.com/datacommons-feeds/claimreview/latest/data.json"
OUT = RAW_DIR / "claimreview_feed_pl.jsonl"

PL_DOMAINS = {
    "sprawdzam.afp.com": "AFP Sprawdzam",
    "demagog.org.pl": "Demagog",
    "fakenews.pl": "FakeNews.pl",
    "konkret24.tvn24.pl": "Konkret24 (TVN24)",
    "pap.pl": "PAP FakeHunter",
    "fakehunter.pap.pl": "PAP FakeHunter",
    "oko.press": "OKO.press",
    "wojownicyklawiatury.pl": "Wojownicy Klawiatury",
    "pravda.org.pl": "Stowarzyszenie Pravda",
}
PL_CHARS = re.compile(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
PL_WORDS = re.compile(r"\b(nie|jest|się|że|oraz|przez|polsk\w*|który|która|będzie)\b", re.I)


def is_polish(s: str) -> bool:
    return len(PL_CHARS.findall(s)) >= 2 and len(PL_WORDS.findall(s)) >= 2


def host(u: str) -> str:
    h = urlsplit(u).netloc.lower()
    return h[4:] if h.startswith("www.") else h


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    hits: Counter = Counter()
    spam: Counter = Counter()
    n_total = n_out = 0
    with requests.get(FEED, stream=True, timeout=120, headers={"User-Agent": UA}) as r, \
            OUT.open("w", encoding="utf-8") as f:
        r.raise_for_status()
        r.raw.decode_content = True
        for el in ijson.items(r.raw, "dataFeedElement.item"):
            for cr in el.get("item") or []:
                n_total += 1
                url = cr.get("url") or ""
                h = host(url)
                claim = clean_text(cr.get("claimReviewed") or "")
                if not url or not claim:
                    continue
                key = next((d for d in PL_DOMAINS if h == d or h.endswith("." + d)), None)
                if key is None:
                    if is_polish(claim):
                        spam[h] += 1
                    continue
                hits[h] += 1
                rr = cr.get("reviewRating") or {}
                item = cr.get("itemReviewed") or {}
                au = item.get("author") or {}
                if isinstance(au, list):
                    au = au[0] if au else {}
                rec = {
                    "url": url, "domain": h, "publisher": PL_DOMAINS[key],
                    "claim": claim,
                    "claim_lang": "pl" if is_polish(claim) else "other",
                    "claim_author": clean_text(au.get("name") or "") or None,
                    "claim_date": iso_date(str(item.get("datePublished") or "")),
                    "appearances": [a.get("url") for a in (item.get("appearance") or [])
                                    if isinstance(a, dict) and a.get("url")][:5],
                    "verdict_raw": clean_text(rr.get("alternateName") or rr.get("name") or "") or None,
                    "rating_explanation": clean_text(rr.get("ratingExplanation") or "") or None,
                    "review_date": iso_date(str(cr.get("datePublished") or "")),
                    "feed_retrieved_at": now_iso(),
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_out += 1
    log(f"[feed] scanned {n_total} ClaimReviews -> {n_out} allow-listed Polish reviews in {OUT}")
    log(f"[feed] by domain: {hits.most_common()}")
    log(f"[feed] Polish-language reviews on non-allow-listed domains (ignored): {spam.most_common(10)}")


if __name__ == "__main__":
    main()
