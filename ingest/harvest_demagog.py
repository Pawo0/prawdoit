#!/usr/bin/env python3
"""Harvest Demagog.org.pl fact-checks (fake_news + wypowiedzi) -> data/corpus/demagog.jsonl

Access path: WP REST API is closed (401, Kadence Security), so we use the public
Yoast sitemaps (fake_news-sitemap*.xml, wypowiedzi-sitemap*.xml) + article HTML,
reading the schema.org ClaimReview JSON-LD embedded in every fact-check
(claimReviewed, itemReviewed.author, reviewRating.alternateName, datePublished).

robots.txt: `User-agent: * Allow: /` with Cloudflare Content-Signal
`search=yes, ai-train=no, use=reference` -> we store claim + verdict + an excerpt
with a link back (reference use, RAG grounding), never for model training.

Selection (incremental, 2026-11-21): every Polish URL of both sections (`wypowiedzi` = statements of politicians,
`fake_news` = social-media fakes) whose sitemap <lastmod> is on/after --since (default 2022-01-01), or the whole
archive with --all. lastmod >= publication date, so the date filter is a superset of "published since". URLs
already present in data/corpus/demagog.jsonl are skipped (existing records are kept verbatim, the file never
shrinks); new pages are fetched newest first and saved at checkpoints (atomic tmp + rename), so a run that hits
the scheduler's timeout keeps its progress and the next run continues. --max-new caps network fetches per run.
Pages already in the raw cache (data/raw/demagog/) cost no request. Measured 2026-11-21: ~6.5k wypowiedzi +
~3.9k fake_news PL URLs; ~4.9k with lastmod >= 2022; ~1.45 s per uncached page (1.2 s polite delay + response) ->
since-2022 ≈ 1.8 h, full archive ≈ 4 h once — so the scheduled run (data/sources/demagog.json: --all --max-new 1500)
fills the archive newest-first in daily slices; after that a run fetches only the sitemaps + a handful of new pages.
"""
from __future__ import annotations

import argparse
import re
import sys

import trafilatura
from selectolax.lexbor import LexborHTMLParser

from common import (IncrementalCorpus, PoliteSession, RunLock, clean_text, clip, iso_date, jsonld_blocks, log,
                    map_verdict, now_iso, sitemap_entries, sitemap_urls)

SOURCE = "demagog"
BASE = "https://demagog.org.pl"
LICENSE = ("© Stowarzyszenie Demagog. 'Ogólne Warunki Licencji' (demagog.org.pl/zasady-udostepniania-tresci): "
           "non-commercial reuse allowed without modification (non-distorting shortening OK) with attribution "
           "'Źródło informacji: www.demagog.org.pl' + link; commercial use needs consent. robots Content-Signal: "
           "search=yes, ai-train=no, use=reference -> RAG/citation only, never training.")

BOILERPLATE = [
    "Obalamy fałszywe informacje pojawiające się w mediach społecznościowych",
    "Sprawdzamy wypowiedzi polityków i osób publicznych",
    "Od lat odróżniamy fałsz od prawdy",
    "przekaż 1,5% podatku",
    "Wpisz w PIT: KRS",
    "Pomóż nam działać dalej",
    "Wesprzyj Demagoga",
    "Fot. ",
]


SECTIONS = ("wypowiedzi", "fake_news")


def collect_urls(sess: PoliteSession, since: str | None) -> list[tuple[str, str]]:
    """All Polish article URLs of both sections as (url, lastmod), newest lastmod first."""
    idx = sitemap_urls(sess.get(f"{BASE}/sitemap_index.xml", use_cache=False))
    if not idx:
        raise RuntimeError("sitemap_index.xml unavailable")
    entries: dict[str, str] = {}
    for sm in idx:
        sec = next((x for x in SECTIONS if f"/{x}-sitemap" in sm), None)
        if not sec:
            continue
        n = 0
        for url, lastmod in sitemap_entries(sess.get(sm, use_cache=False)):
            # Polish only (skip /en/ and /ua/ translations) and skip archive roots
            if not url.startswith(f"{BASE}/{sec}/") or url.rstrip("/") == f"{BASE}/{sec}":
                continue
            n += 1
            entries.setdefault(url, lastmod or "")
        log(f"[sitemap] {sm.rsplit('/', 1)[-1]}: {n} PL urls")
    picked = [(u, lm) for u, lm in entries.items() if not since or not lm or lm[:10] >= since]
    log(f"[sitemap] {len(entries)} PL urls in total, {len(picked)} with lastmod >= {since or 'any'}")
    return sorted(picked, key=lambda x: x[1], reverse=True)


def parse(url: str, html: str) -> dict | None:
    blocks = jsonld_blocks(html)
    cr = next((b for b in blocks if b.get("@type") == "ClaimReview"), None)
    wp = next((b for b in blocks if b.get("@type") == "WebPage"), {})
    tree = LexborHTMLParser(html)

    title = None
    og = tree.css_first('meta[property="og:title"]')
    if og:
        title = og.attributes.get("content")
    title = clean_text(title or wp.get("name") or "")
    if not title:
        return None

    section = "fake_news" if "/fake_news/" in url else "wypowiedzi"
    tags = [section]
    for a in tree.css(".dg-post-content__tags--desktop a"):
        h = a.attributes.get("href", "")
        if "/tematy/" in h:
            tags.append(h.rstrip("/").rsplit("/", 1)[-1])

    center = tree.css_first(".dg-post-content__center")
    for sel in [".dg-post-content__title", ".dg-post-content__tags", ".dg-post-content__social",
                ".dg-post-content__image", ".dg-post-content__lead--mobile", ".dg-post-content__category",
                "script", "style", "blockquote.twitter-tweet", "iframe"]:
        if center:
            for n in center.css(sel):
                n.decompose()
    text = None
    if center:
        text = trafilatura.extract(f"<html><body>{center.html}</body></html>", favor_precision=False,
                                   include_tables=False, include_comments=False)
        if not text:
            text = center.text(separator="\n")
    if not text:
        text = trafilatura.extract(html) or ""
    lines = [ln for ln in clean_text(text).split("\n")
             if not any(b in ln for b in BOILERPLATE) and ln.strip() != title]
    text = "\n".join(lines)

    claim = claim_author = verdict_raw = None
    published = iso_date(wp.get("datePublished"))
    if cr:
        claim = clean_text(cr.get("claimReviewed")) or None
        item = cr.get("itemReviewed") or {}
        au = item.get("author") or {}
        if isinstance(au, list):
            au = au[0] if au else {}
        claim_author = clean_text(au.get("name")) or None
        if claim_author and claim_author.lower() in ("wiele źródeł", "internauci", "użytkownicy"):
            claim_author = claim_author  # keep: "multiple sources" is informative
        rr = cr.get("reviewRating") or {}
        verdict_raw = clean_text(rr.get("alternateName") or rr.get("name")) or None
        published = iso_date(cr.get("datePublished")) or published
    if claim and len(claim) > 1000:
        claim = claim[:1000] + " […]"
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    return {
        "id": f"{SOURCE}:{section}/{slug}",
        "source_type": "factcheck",
        "publisher": "Demagog",
        "domain": "demagog.org.pl",
        "url": url,
        "title": title,
        "published_at": published,
        "retrieved_at": now_iso(),
        "language": "pl",
        "license": LICENSE,
        "text": text,
        "claim": claim,
        "claim_author": claim_author,
        "verdict_raw": verdict_raw,
        "verdict": map_verdict(verdict_raw),
        "tags": tags,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default="2022-01-01", help="only sitemap entries with lastmod >= this date")
    ap.add_argument("--all", action="store_true", help="whole archive (ignores --since)")
    ap.add_argument("--max-new", type=int, default=0, help="cap on uncached page fetches per run (0 = no cap)")
    ap.add_argument("--checkpoint", type=int, default=100, help="save the corpus file every N new records")
    ap.add_argument("--max-chars", type=int, default=3000)
    ap.add_argument("--delay", type=float, default=1.2)
    ap.add_argument("--out", default=None, help="corpus file (default data/corpus/demagog.jsonl)")
    ap.add_argument("--dry-run", action="store_true", help="only list/estimate, fetch no articles")
    # pre-2026-11-21 sampling flags: accepted so old registry entries keep working, but a run is always incremental
    ap.add_argument("--recent", type=int, help=argparse.SUPPRESS)
    ap.add_argument("--topic", type=int, help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.recent is not None or args.topic is not None:
        log("[demagog] --recent/--topic are obsolete (sampling replaced by incremental harvest) - ignored")

    with RunLock(SOURCE) as got:
        if not got:
            log("[demagog] another harvest_demagog run holds the lock - nothing to do")
            return 0
        from pathlib import Path

        corpus = IncrementalCorpus(SOURCE, Path(args.out) if args.out else None)
        sess = PoliteSession(SOURCE, delay=args.delay)
        urls = collect_urls(sess, None if args.all else args.since)
        todo = [u for u, _ in urls if not corpus.has_url(u)]
        cached = sum(1 for u in todo if sess.is_cached(u))
        uncached = len(todo) - cached
        if args.max_new:
            uncached = min(uncached, args.max_new)
        log(f"[demagog] {corpus.n_existing} records already in {corpus.path.name}; {len(todo)} new urls "
            f"({cached} in raw cache); ~{uncached * sess.delay / 60:.0f} min of fetching at {sess.delay:.1f} s/page")
        if args.dry_run:
            return 0
        fetched = 0
        try:
            for i, u in enumerate(todo, 1):
                is_cached = sess.is_cached(u)
                if not is_cached and args.max_new and fetched >= args.max_new:
                    continue  # cap reached: still parse pages that are already cached
                html = sess.get(u)
                fetched += 0 if is_cached else 1
                if not html:
                    continue
                try:
                    rec = parse(u, html)
                except Exception as e:  # noqa: BLE001 - one odd page must not stop a long harvest
                    log(f"[parse error] {u}: {e}")
                    continue
                if rec:
                    rec["text"] = clip(rec["text"], args.max_chars)
                    corpus.add(rec)
                    if corpus._unsaved >= args.checkpoint:
                        corpus.save()
                if i % 100 == 0:
                    log(f"  {i}/{len(todo)} new={corpus.n_new} {sess.stats}")
        finally:
            corpus.save()
        log(f"[demagog] done: +{corpus.n_new} new, {len(corpus.records)} total; stats {sess.stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
