#!/usr/bin/env python3
"""Harvest FakeNews.pl (Fundacja "Przeciwdziałamy Dezinformacji") -> data/corpus/fakenews_pl.jsonl

Access path: open WordPress REST API https://fakenews.pl/wp-json/wp/v2/posts (~950 posts),
robots.txt `Disallow:` (nothing disallowed). Each fact-check exposes ACF fields
`teza` (claim), `autor` (claim author), `ocena` (verdict label), `url` (claim appearance),
`data` (claim date) - the same data as the page's ClaimReview JSON-LD.
Licence: © fakenews.pl, no open licence -> claim + verdict + excerpt (≤2500 chars) + link.
"""
from __future__ import annotations

import argparse
import html as htmlmod
import json
import re

import trafilatura

from common import JsonlWriter, PoliteSession, clean_text, clip, iso_date, log, map_verdict, now_iso

SOURCE = "fakenews_pl"
API = "https://fakenews.pl/wp-json/wp/v2"
LICENSE = ("© fakenews.pl / Fundacja „Przeciwdziałamy Dezinformacji”, all rights reserved (no open "
           "licence). Stored claim, verdict, excerpt (≤2500 chars) + link for citation.")
# fact-check categories (skip blog=12, badania=213)
FC_CATS = {2: "polityka", 3: "spoleczenstwo", 5: "zdrowie", 1: "srodowisko", 4: "technologia", 6: "rozrywka"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=500)
    ap.add_argument("--max-chars", type=int, default=2500)
    ap.add_argument("--delay", type=float, default=1.5)
    args = ap.parse_args()
    sess = PoliteSession(SOURCE, delay=args.delay)

    posts, page = [], 1
    while len(posts) < args.max:
        raw = sess.get(f"{API}/posts", params={
            "per_page": 100, "page": page, "categories": ",".join(map(str, FC_CATS)),
            "_fields": "id,date,link,title,content,excerpt,categories,tags,acf"}, use_cache=False)
        if not raw:
            break
        batch = json.loads(raw)
        if not isinstance(batch, list) or not batch:
            break
        posts.extend(batch)
        log(f"[fakenews.pl] page {page}: +{len(batch)} (total {len(posts)})")
        if len(batch) < 100:
            break
        page += 1

    tag_ids = sorted({t for p in posts for t in p.get("tags", [])})
    tag_name: dict[int, str] = {}
    for i in range(0, len(tag_ids), 100):
        chunk = tag_ids[i:i + 100]
        raw = sess.get(f"{API}/tags", params={"include": ",".join(map(str, chunk)), "per_page": 100,
                                              "_fields": "id,slug"}, use_cache=False)
        for t in json.loads(raw or "[]"):
            tag_name[t["id"]] = t["slug"]

    w = JsonlWriter(SOURCE)
    for p in posts[: args.max]:
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
        tags = ["fakenews.pl"] + [f"kategoria:{c}" for c in cats] + [tag_name.get(t, "") for t in p.get("tags", [])]
        w.write({
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
            "text": clip(body, args.max_chars),
            "claim": claim[:1000] if claim else None,
            "claim_author": clean_text(acf.get("autor") or "") or None,
            "verdict_raw": verdict_raw,
            "verdict": map_verdict(verdict_raw),
            "tags": tags,
        })
    w.close()
    log(f"[fakenews.pl] stats {sess.stats}")


if __name__ == "__main__":
    main()
