#!/usr/bin/env python3
"""Harvest Konkret24 (TVN24 fact-checking desk) articles -> data/corpus/konkret24.jsonl

Access path: no sitemap, RSS feed (najwazniejsze.xml) is empty, no ClaimReview markup,
pagination (`?page=`) is disallowed by robots.txt. We therefore read the section landing
pages (polska, polityka, swiat, zdrowie, tech, nauka) and follow "related" article links
found on article pages (bounded BFS), reading NewsArticle JSON-LD (headline,
datePublished, description, author).

Licence: © TVN S.A. — all rights reserved. We keep ONLY title, lead/description, a short
excerpt (<= 700 chars) and the link (quotation/right-to-cite style use). No verdict labels
are published by Konkret24, so verdict = null.

Incremental (2026-11-21): records already in data/corpus/konkret24.jsonl are kept verbatim (the file never shrinks);
their pages come from the raw cache (no request) and are still used to discover related links, so every run widens
the crawl frontier. --max caps the number of NEW articles per run; progress is saved at checkpoints.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import deque
from pathlib import Path

import trafilatura

from common import (IncrementalCorpus, PoliteSession, RunLock, clean_text, clip, iso_date, jsonld_blocks, log,
                    now_iso)

SOURCE = "konkret24"
BASE = "https://konkret24.tvn24.pl"
SECTIONS = ["polska", "polityka", "swiat", "zdrowie", "tech", "nauka"]
ART_RE = re.compile(r"https://konkret24\.tvn24\.pl/([a-z-]+)/([a-z0-9-]+-st(\d+))")
LICENSE = ("© TVN S.A. (Konkret24/TVN24), all rights reserved. Stored only title, lead and a short "
           "excerpt (≤700 chars) with link, for citation; full text must be read at source.")
NEG = re.compile(r"\b(fałsz|fake|nieprawd|manipulac|nie jest prawd|nie zgadza|nie ma dowodów|"
                 r"dezinformac|zmanipulowan|wygenerowan|przerobion|mit\b|rzekom)", re.I)


def links(html: str) -> list[str]:
    seen = []
    for m in ART_RE.finditer(html):
        u = m.group(0)
        if u not in seen:
            seen.append(u)
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=120)
    ap.add_argument("--excerpt", type=int, default=700)
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--out", default=None, help="corpus file (default data/corpus/konkret24.jsonl)")
    args = ap.parse_args()
    with RunLock(SOURCE) as got:
        if not got:
            log("[konkret24] another run holds the lock - nothing to do")
            return 0
        corpus = IncrementalCorpus(SOURCE, Path(args.out) if args.out else None)
        try:
            crawl(args, corpus)
        finally:
            corpus.save()
        log(f"[konkret24] done: +{corpus.n_new} new, {len(corpus.records)} total")
    return 0


def crawl(args, corpus: IncrementalCorpus) -> None:
    sess = PoliteSession(SOURCE, delay=args.delay)
    queue: deque[str] = deque()
    seen: set[str] = set()
    for sec in [""] + SECTIONS:
        html = sess.get(f"{BASE}/{sec}", use_cache=False)
        for u in links(html or ""):
            if u not in seen:
                seen.add(u)
                queue.append(u)
    for r in corpus.records:  # known articles: their (cached) pages still lead to related links
        u = r.get("url") or ""
        if ART_RE.match(u) and u not in seen:
            seen.add(u)
            queue.append(u)
    log(f"[konkret24] {len(queue)} seed article urls ({corpus.n_existing} already stored)")

    while queue and corpus.n_new < args.max:
        url = queue.popleft()
        known = corpus.has_url(url)
        if known and not sess.is_cached(url):
            continue  # stored, page not cached: do not spend a request only on link discovery
        html = sess.get(url)
        if not html:
            continue
        for u in links(html):
            if u not in seen:
                seen.add(u)
                queue.append(u)
        if known:
            continue
        art = next((b for b in jsonld_blocks(html) if b.get("@type") in ("NewsArticle", "Article")), {})
        title = clean_text(art.get("headline") or "")
        if not title:
            m = trafilatura.extract_metadata(html)
            title = clean_text(m.title if m else "")
        if not title:
            continue
        lead = clean_text(art.get("description") or "")
        body = trafilatura.extract(html, favor_precision=True) or ""
        body = "\n".join(ln for ln in clean_text(body).split("\n") if ln != lead)
        text = clip((lead + "\n" + body).strip(), args.excerpt)
        au = art.get("author") or {}
        if isinstance(au, list):
            au = au[0] if au else {}
        m = ART_RE.match(url)
        section, slug, num = m.group(1), m.group(2), m.group(3)
        tags = ["konkret24", f"sekcja:{section}"]
        if au.get("name"):
            tags.append(f"autor:{au['name']}")
        if NEG.search(title + " " + lead):
            tags.append("debunk-signal-in-headline")
        corpus.add({
            "id": f"{SOURCE}:{num}",
            "source_type": "factcheck",
            "publisher": "Konkret24 (TVN24)",
            "domain": "konkret24.tvn24.pl",
            "url": url,
            "title": title,
            "published_at": iso_date(art.get("datePublished")),
            "retrieved_at": now_iso(),
            "language": "pl",
            "license": LICENSE,
            "text": text,
            "claim": None,
            "claim_author": None,
            "verdict_raw": None,
            "verdict": None,
            "tags": tags,
        })
        if corpus._unsaved >= 100:
            corpus.save()
            log(f"  new={corpus.n_new} queue={len(queue)} {sess.stats}")
    log(f"[konkret24] stats {sess.stats}")


if __name__ == "__main__":
    sys.exit(main())
