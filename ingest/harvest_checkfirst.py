#!/usr/bin/env python3
"""Harvest CheckFirst (checkfirst.network) investigations -> data/corpus/checkfirst.jsonl

Access path: public WordPress REST API https://checkfirst.network/wp-json/wp/v2/posts
(~72 posts; robots.txt + llms.txt explicitly welcome AI/RAG crawlers with attribution).
We keep investigations/publications (FIMI incident reports: Pravda/Portal Kombat network,
Operation Overload/Matryoshka, Meta ads, Doppelganger-type ops) and skip event replays/news.
Language: English (CheckFirst publishes in EN). source_type = "incident".
"""
from __future__ import annotations

import argparse
import html as htmlmod
import json
import re

import trafilatura

from common import JsonlWriter, PoliteSession, clean_text, iso_date, log, now_iso

SOURCE = "checkfirst"
API = "https://checkfirst.network/wp-json/wp/v2"
LICENSE = ("© Check First Oy. Site policy (robots.txt/llms.txt): AI systems & RAG pipelines welcome "
           "to read, index and cite with attribution to CheckFirst + link. Quoted propaganda in "
           "reports is evidence, not CheckFirst's claim.")
SKIP = re.compile(r"watch the replay|replay:|birthday|years of check|takes part|joins|join forces|"
                  r"chooses checkfirst|key takeaways|takeaways from|reflecting on|signs the|"
                  r"commissions checkfirst|presents? a new study|expands crossover|introducing tutki|"
                  r"cyber for good|immerse french journalists|to join|what we brought|webinar|hackathon", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=1.2)
    args = ap.parse_args()
    sess = PoliteSession(SOURCE, delay=args.delay)

    cats = json.loads(sess.get(f"{API}/categories", params={"per_page": 50, "_fields": "id,slug"},
                               use_cache=False) or "[]")
    cat_name = {c["id"]: c["slug"] for c in cats}
    posts = []
    page = 1
    while True:
        raw = sess.get(f"{API}/posts", params={"per_page": 100, "page": page,
                                               "_fields": "id,date,link,title,content,excerpt,categories,tags"},
                       use_cache=False)
        if not raw:
            break
        batch = json.loads(raw)
        if not isinstance(batch, list) or not batch:
            break
        posts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    log(f"[checkfirst] {len(posts)} posts via REST API")

    w = JsonlWriter(SOURCE)
    for p in posts:
        title = clean_text(htmlmod.unescape(re.sub(r"<[^>]+>", "", p["title"]["rendered"])))
        cslugs = [cat_name.get(c, str(c)) for c in p.get("categories", [])]
        if SKIP.search(title):
            continue
        if "publications" not in cslugs and not re.search(
                r"operation|pravda|kremlin|russia|propaganda|disinformation|election|gru|fsb|ads|"
                r"hustles|tiktok|youtube|google|meta|amazon|odysee|nazis|donbas|xinjiang", title, re.I):
            continue
        body = trafilatura.extract(f"<html><body>{p['content']['rendered']}</body></html>") or ""
        excerpt = clean_text(htmlmod.unescape(re.sub(r"<[^>]+>", " ", p["excerpt"]["rendered"])))
        text = body or excerpt
        if len(text) < 200:
            continue
        tags = ["checkfirst", "fimi"] + [f"kategoria:{c}" for c in cslugs]
        low = (title + " " + text).lower()
        for kw, tg in [("pravda", "pravda-network"), ("portal kombat", "portal-kombat"),
                       ("overload", "operation-overload"), ("matryoshka", "matryoshka"),
                       ("poland", "poland"), ("polish", "poland"), ("doppelg", "doppelganger"),
                       ("election", "elections"), ("llm", "llm-grooming"), ("wikipedia", "wikipedia")]:
            if kw in low:
                tags.append(tg)
        w.write({
            "id": f"{SOURCE}:{p['id']}",
            "source_type": "incident",
            "publisher": "CheckFirst",
            "domain": "checkfirst.network",
            "url": p["link"],
            "title": title,
            "published_at": iso_date(p.get("date")),
            "retrieved_at": now_iso(),
            "language": "en",
            "license": LICENSE,
            "text": text,
            "claim": None,
            "claim_author": None,
            "verdict_raw": None,
            "verdict": None,
            "tags": tags,
        })
    w.close()
    log(f"[checkfirst] stats {sess.stats}")


if __name__ == "__main__":
    main()
