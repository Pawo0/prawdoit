#!/usr/bin/env python3
"""Harvest Stowarzyszenie Pravda (pravda.org.pl, EFCSN-verified) -> data/corpus/pravda.jsonl

Access path: Ghost CMS, robots.txt allows everything except /ghost/, /members/... ;
post list from https://pravda.org.pl/sitemap-posts.xml (~480 posts). Article pages carry
schema.org Article JSON-LD (headline, datePublished, description = verdict summary) but no
ClaimReview; the ClaimReviews Pravda entered via Google's Fact Check Markup Tool come from
the Data Commons feed (data/raw/claimreview_feed_pl.jsonl, produced by
harvest_claimreview_feed.py) and are joined by URL -> claim, claim author, verdict.

Licence: no open licence stated on the site (default: all rights reserved) -> claim + verdict
+ excerpt (≤2500 chars) + link.
"""
from __future__ import annotations

import argparse
import json

import trafilatura

from common import (RAW_DIR, JsonlWriter, PoliteSession, clean_text, clip, iso_date, jsonld_blocks,
                    log, map_verdict, now_iso, sitemap_urls)

SOURCE = "pravda"
BASE = "https://pravda.org.pl"
LICENSE = ("© Stowarzyszenie Pravda; no open licence stated (all rights reserved). Stored claim, "
           "verdict, excerpt (≤2500 chars) + link for citation. Claim/verdict from Pravda's own "
           "ClaimReview markup (Google Fact Check Tools feed).")


def norm(u: str) -> str:
    return u.split("?")[0].rstrip("/").replace("http://", "https://").replace("://www.", "://")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra-recent", type=int, default=60, help="newest posts without ClaimReview")
    ap.add_argument("--max-chars", type=int, default=2500)
    ap.add_argument("--delay", type=float, default=1.5)
    args = ap.parse_args()

    feed = {}
    fp = RAW_DIR / "claimreview_feed_pl.jsonl"
    if fp.exists():
        for line in fp.open(encoding="utf-8"):
            r = json.loads(line)
            if r["domain"].endswith("pravda.org.pl"):
                feed[norm(r["url"])] = r
    log(f"[pravda] {len(feed)} ClaimReviews from feed")

    sess = PoliteSession(SOURCE, delay=args.delay)
    posts = sitemap_urls(sess.get(f"{BASE}/sitemap-posts.xml", use_cache=False))
    posts = [u for u in posts if u.startswith(BASE)]
    in_feed = [u for u in posts if norm(u) in feed]
    others = [u for u in posts if norm(u) not in feed][: args.extra_recent]  # sitemap is newest-first
    # feed URLs missing from sitemap (renamed slugs) are tried directly
    missing = [r["url"] for k, r in feed.items() if k not in {norm(u) for u in posts}]
    urls = list(dict.fromkeys(in_feed + others + missing))
    log(f"[pravda] sitemap {len(posts)} posts; with ClaimReview {len(in_feed)}; extra {len(others)}; "
        f"feed-only urls {len(missing)}")

    w = JsonlWriter(SOURCE)
    for i, url in enumerate(urls, 1):
        html = sess.get(url)
        if not html:
            continue
        art = next((b for b in jsonld_blocks(html) if b.get("@type") in ("Article", "NewsArticle")), {})
        title = clean_text(art.get("headline") or "")
        if not title:
            m = trafilatura.extract_metadata(html)
            title = clean_text(m.title if m else "")
        if not title:
            continue
        body = trafilatura.extract(html) or ""
        cr = feed.get(norm(url), {})
        claim = cr.get("claim")
        verdict_raw = cr.get("verdict_raw")
        tags = ["pravda.org.pl"]
        kw = art.get("keywords")
        if isinstance(kw, str):
            tags += [k.strip().lower() for k in kw.split(",") if k.strip()]
        elif isinstance(kw, list):
            tags += [str(k).lower() for k in kw]
        if cr:
            tags.append("claimreview")
        w.write({
            "id": f"{SOURCE}:{url.rstrip('/').rsplit('/', 1)[-1]}",
            "source_type": "factcheck",
            "publisher": "Stowarzyszenie Pravda",
            "domain": "pravda.org.pl",
            "url": url,
            "title": title,
            "published_at": iso_date(art.get("datePublished")) or cr.get("review_date"),
            "retrieved_at": now_iso(),
            "language": "pl",
            "license": LICENSE,
            "text": clip(body, args.max_chars),
            "claim": claim[:1000] if claim else None,
            "claim_author": cr.get("claim_author"),
            "verdict_raw": verdict_raw,
            "verdict": map_verdict(verdict_raw),
            "tags": tags,
        })
        if i % 50 == 0:
            log(f"  {i}/{len(urls)} written={w.n} {sess.stats}")
    w.close()
    log(f"[pravda] stats {sess.stats}")


if __name__ == "__main__":
    main()
