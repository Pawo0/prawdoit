#!/usr/bin/env python3
"""Harvest Demagog.org.pl fact-checks (fake_news + wypowiedzi) -> data/corpus/demagog.jsonl

Access path: WP REST API is closed (401, Kadence Security), so we use the public
Yoast sitemaps (fake_news-sitemap*.xml, wypowiedzi-sitemap*.xml) + article HTML,
reading the schema.org ClaimReview JSON-LD embedded in every fact-check
(claimReviewed, itemReviewed.author, reviewRating.alternateName, datePublished).

robots.txt: `User-agent: * Allow: /` with Cloudflare Content-Signal
`search=yes, ai-train=no, use=reference` -> we store claim + verdict + an excerpt
with a link back (reference use, RAG grounding), never for model training.

Selection: newest N from each section + older items whose slug matches popular
myth topics (vaccines, 5G, refugees, Green Deal, migration pact, energy, elections...).
"""
from __future__ import annotations

import argparse
import re

import trafilatura
from selectolax.lexbor import LexborHTMLParser

from common import (JsonlWriter, PoliteSession, clean_text, clip, iso_date, jsonld_blocks, log,
                    map_verdict, now_iso, sitemap_urls)

SOURCE = "demagog"
BASE = "https://demagog.org.pl"
LICENSE = ("© Stowarzyszenie Demagog. 'Ogólne Warunki Licencji' (demagog.org.pl/zasady-udostepniania-tresci): "
           "non-commercial reuse allowed without modification (non-distorting shortening OK) with attribution "
           "'Źródło informacji: www.demagog.org.pl' + link; commercial use needs consent. robots Content-Signal: "
           "search=yes, ai-train=no, use=reference -> RAG/citation only, never training.")

TOPIC_RE = re.compile(
    r"szczepi|covid|koronawir|pandemi|5g|uchodz|ukrain|zielon\w*-lad|green-deal|pakt\w*-migr|migra|"
    r"imigr|ceny-pradu|prad|energi|gaz|wegiel|ets|klimat|wybor|wyborcz|glosowan|nato|rosj|"
    r"bialorus|granic|euro|unia|ue-|-ue|bruksel|inflac|podatk|emeryt|aborc|smog|chemtrail|"
    r"mrna|wht|who|grypa|ptasia|afryk|islam|mieszkan|800|ziemniak|owady|robak|cpk|elektrow|"
    r"atom|samochod|spalin|zakaz|cenzur|dsa|ai-|sztuczn|deepfake|oszust|zboz|rolni", re.I)

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


def pick_urls(sess: PoliteSession, n_recent: int, n_topic: int) -> list[str]:
    idx = sitemap_urls(sess.get(f"{BASE}/sitemap_index.xml", use_cache=False))
    sections: dict[str, list[str]] = {"fake_news": [], "wypowiedzi": []}
    for sm in idx:
        for sec in sections:
            if f"/{sec}-sitemap" in sm:
                urls = sitemap_urls(sess.get(sm, use_cache=False))
                # Polish only (skip /en/ and /ua/ translations) and skip archive roots
                urls = [u for u in urls if u.startswith(f"{BASE}/{sec}/") and u.rstrip("/") != f"{BASE}/{sec}"]
                sections[sec].extend(urls)
    chosen: list[str] = []
    for sec, urls in sections.items():
        log(f"[sitemap] {sec}: {len(urls)} PL urls")
        # sitemap order is ascending by post id -> tail = newest
        recent = urls[-n_recent:][::-1]
        older = [u for u in urls[:-n_recent] if TOPIC_RE.search(u.rsplit("/", 2)[-2])]
        # spread topical picks across the whole archive
        step = max(1, len(older) // max(1, n_topic))
        topical = older[::step][:n_topic]
        chosen.extend(recent + topical)
    return list(dict.fromkeys(chosen))


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--recent", type=int, default=130, help="newest items per section")
    ap.add_argument("--topic", type=int, default=60, help="older topical items per section")
    ap.add_argument("--max-chars", type=int, default=3000)
    ap.add_argument("--delay", type=float, default=1.2)
    args = ap.parse_args()

    sess = PoliteSession(SOURCE, delay=args.delay)
    urls = pick_urls(sess, args.recent, args.topic)
    log(f"[demagog] {len(urls)} urls selected")
    w = JsonlWriter(SOURCE)
    for i, u in enumerate(urls, 1):
        html = sess.get(u)
        if not html:
            continue
        rec = parse(u, html)
        if rec:
            rec["text"] = clip(rec["text"], args.max_chars)
            w.write(rec)
        if i % 25 == 0:
            log(f"  {i}/{len(urls)} written={w.n} {sess.stats}")
    w.close()
    log(f"[demagog] stats {sess.stats}")


if __name__ == "__main__":
    main()
