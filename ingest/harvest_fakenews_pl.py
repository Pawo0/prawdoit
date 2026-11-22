#!/usr/bin/env python3
"""Harvest FakeNews.pl (Fundacja "Przeciwdziałamy Dezinformacji") -> data/corpus/fakenews_pl.jsonl

Access path: open WordPress REST API https://fakenews.pl/wp-json/wp/v2/posts (~950 posts),
robots.txt `Disallow:` (nothing disallowed). Each fact-check exposes ACF fields
`teza` (claim), `autor` (claim author), `ocena` (verdict label), `url` (claim appearance),
`data` (claim date) - the same data as the page's ClaimReview JSON-LD.
Licence: © fakenews.pl, no open licence -> claim, rating, title, dates, link + ONE verbatim excerpt (≤300 chars,
the passage stating the finding; common.excerpt). The article itself is not stored.

Incremental (2026-11-21): first a cheap id-only listing of every fact-check post (`_fields=id`, 100 per page), then
full content only for ids not yet in data/corpus/fakenews_pl.jsonl (`include=` batches of 100). Existing records are
kept verbatim, so a run never shrinks the file. --max caps the number of NEW posts per run (0 = all).
"""
from __future__ import annotations

import argparse
import html as htmlmod
import json
import re
import sys
from pathlib import Path

import trafilatura

from common import IncrementalCorpus, PoliteSession, RunLock, clean_text, excerpt, iso_date, log, map_verdict, now_iso

SOURCE = "fakenews_pl"
API = "https://fakenews.pl/wp-json/wp/v2"
LICENSE = ("© fakenews.pl / Fundacja „Przeciwdziałamy Dezinformacji”, all rights reserved (no open "
           "licence). Stored: checked claim, rating, title, dates and link, plus one verbatim excerpt (≤300 chars) "
           "quoted with attribution; the article is read at its link.")
# fact-check categories (skip blog=12, badania=213)
FC_CATS = {2: "polityka", 3: "spoleczenstwo", 5: "zdrowie", 1: "srodowisko", 4: "technologia", 6: "rozrywka"}


FIELDS = "id,date,link,title,content,excerpt,categories,tags,acf"


def list_ids(sess: PoliteSession) -> list[int]:
    ids, page = [], 1
    while True:
        raw = sess.get(f"{API}/posts", params={"per_page": 100, "page": page, "categories": ",".join(map(str, FC_CATS)),
                                               "_fields": "id"}, use_cache=False)
        try:
            batch = json.loads(raw) if raw else []
        except ValueError:
            batch = []
        if not isinstance(batch, list) or not batch:
            break
        ids += [p["id"] for p in batch if isinstance(p, dict) and "id" in p]
        if len(batch) < 100:
            break
        page += 1
    log(f"[fakenews.pl] {len(ids)} fact-check post ids listed")
    return ids


def record(p: dict, tag_name: dict[int, str], max_chars: int = 300) -> dict:
    acf = p.get("acf") or {}
    if not isinstance(acf, dict):
        acf = {}
    title = clean_text(htmlmod.unescape(re.sub(r"<[^>]+>", "", p["title"]["rendered"])))
    body = trafilatura.extract(f"<html><body>{p['content']['rendered']}</body></html>") or ""
    if not body:
        body = clean_text(htmlmod.unescape(re.sub(r"<[^>]+>", " ", p["content"]["rendered"])))
    verdict_raw = clean_text(acf.get("ocena") or "") or None
    if verdict_raw:
        verdict_raw = verdict_raw[0].upper() + verdict_raw[1:]
    claim = clean_text(acf.get("teza") or "") or None
    cats = [FC_CATS.get(c, str(c)) for c in p.get("categories", [])]
    tags = (["fakenews.pl"] + [f"kategoria:{c}" for c in cats] + [tag_name.get(t, "") for t in p.get("tags", [])]
            + [f"excerpt:finding{max_chars}"])
    return {
        "id": f"{SOURCE}:{p['id']}",
        "source_type": "factcheck",
        "publisher": "FakeNews.pl",
        "domain": "fakenews.pl",
        "url": p["link"],
        "title": title,
        "published_at": iso_date(p.get("date")),
        "retrieved_at": now_iso(),
        "language": "pl",
        "license": LICENSE,
        "text": excerpt(body, title, claim, max_chars),
        "claim": claim[:1000] if claim else None,
        "claim_author": clean_text(acf.get("autor") or "") or None,
        "verdict_raw": verdict_raw,
        "verdict": map_verdict(verdict_raw),
        "tags": tags,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=0, help="max NEW posts per run (0 = all)")
    ap.add_argument("--max-chars", type=int, default=300, help="excerpt length (no open licence: keep it short)")
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--out", default=None, help="corpus file (default data/corpus/fakenews_pl.jsonl)")
    args = ap.parse_args()
    with RunLock(SOURCE) as got:
        if not got:
            log("[fakenews.pl] another run holds the lock - nothing to do")
            return 0
        sess = PoliteSession(SOURCE, delay=args.delay)
        corpus = IncrementalCorpus(SOURCE, Path(args.out) if args.out else None)
        known = {r.get("id") for r in corpus.records}
        new_ids = [i for i in list_ids(sess) if f"{SOURCE}:{i}" not in known]
        if args.max:
            new_ids = new_ids[: args.max]
        log(f"[fakenews.pl] {corpus.n_existing} records already stored; fetching {len(new_ids)} new posts")
        try:
            for k in range(0, len(new_ids), 100):
                chunk = new_ids[k:k + 100]
                raw = sess.get(f"{API}/posts", params={"include": ",".join(map(str, chunk)), "per_page": 100,
                                                       "_fields": FIELDS}, use_cache=False)
                posts = json.loads(raw or "[]")
                tag_ids = sorted({t for p in posts for t in p.get("tags", [])})
                tag_name: dict[int, str] = {}
                for i in range(0, len(tag_ids), 100):
                    traw = sess.get(f"{API}/tags", params={"include": ",".join(map(str, tag_ids[i:i + 100])),
                                                           "per_page": 100, "_fields": "id,slug"}, use_cache=False)
                    for t in json.loads(traw or "[]"):
                        tag_name[t["id"]] = t["slug"]
                for p in posts:
                    try:
                        corpus.add(record(p, tag_name, args.max_chars))
                    except Exception as e:  # noqa: BLE001 - one odd post must not stop the run
                        log(f"[skip] post {p.get('id')}: {e}")
                corpus.save()
        finally:
            corpus.save()
        log(f"[fakenews.pl] done: +{corpus.n_new} new, {len(corpus.records)} total; stats {sess.stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
