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

One record per ClaimReview block (2026-11-22): a page that rates several claims (~200 fake_news pages, up to 10
blocks) yields its main record `demagog:<section>/<slug>` plus `…#<n>` for each further block, each with its own
claim, rating, claimant and date (parse_page). Before, only the first block was kept. `--reparse-cache` rebuilds the
corpus file from the raw cache without any network request.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

import trafilatura
from selectolax.lexbor import LexborHTMLParser

from common import (IncrementalCorpus, PoliteSession, RunLock, canonical_url, clean_text, clip, iso_date,
                    jsonld_blocks, log, map_verdict, normalize_record, now_iso, sitemap_entries, sitemap_urls)

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


def claimreview_blocks(html: str) -> list[dict]:
    """Every schema.org ClaimReview of a page, in document order. (`jsonld_blocks` walks a JSON-LD list from its
    end, so its first ClaimReview is the *last* one on a page whose blocks sit in one list.)"""
    out: list[dict] = []

    def walk(x):
        if isinstance(x, list):
            for y in x:
                walk(y)
        elif isinstance(x, dict):
            if x.get("@type") == "ClaimReview":
                out.append(x)
            if "@graph" in x:
                walk(x["@graph"])

    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            walk(json.loads(m.group(1).strip()))
        except Exception:  # noqa: BLE001 - a broken JSON-LD script is skipped, as in jsonld_blocks
            continue
    return out


_FOLD = str.maketrans("ąćęłńóśźż", "acelnoszz")
_STOP = {"nie", "jest", "sa", "to", "sie", "jak", "czy", "na", "do", "od", "ze", "za", "po", "przez", "dla", "tak",
         "oraz", "lub", "ale", "ten", "ta", "te", "tym", "tego", "tej", "jego", "ich", "juz", "tylko", "byc", "bedzie",
         "moze", "ma", "maja", "co", "ktore", "ktory", "ktora", "jako", "przy", "pod", "nad", "o", "w", "z", "i", "a"}


def _stems(s: str | None) -> set[str]:
    """Crude Polish stems for matching a sub-claim to a heading: folded diacritics, 5-letter prefixes."""
    words = re.findall(r"[a-z0-9]+", (s or "").lower().translate(_FOLD))
    return {w[:5] for w in words if w not in _STOP and (len(w) >= 3 or w.isdigit())}


def _overlap(claim: set[str], other: set[str]) -> float:
    return len(claim & other) / len(claim) if claim else 0.0


_SKIP_IN_SECTION = (".dg-post-support", ".wp-caption", "figure", "table", "script", "style", "iframe",
                    "blockquote.twitter-tweet", ".summary-text", "p.title")


def _sections(inner) -> list[dict]:
    """Split the article body (direct children of .dg-post-content__inner) at its h2/h3/h4 headings.
    Returns [{level, head, lines}] in page order; level 0 is the part before the first heading."""
    secs = [{"level": 0, "head": "", "lines": []}]
    for node in inner.iter():
        tag = node.tag
        if tag in ("h2", "h3", "h4"):
            head = clean_text(node.text(deep=True))
            if head:
                secs.append({"level": int(tag[1]), "head": head, "lines": []})
            continue
        if any(node.css_matches(sel) for sel in _SKIP_IN_SECTION):
            continue
        if tag in ("ul", "ol"):
            items = [clean_text(li.text(deep=True)) for li in node.css("li")]
            secs[-1]["lines"].extend(t for t in items if t)
            continue
        t = clean_text(node.text(deep=True))
        if t:
            secs[-1]["lines"].extend(t.split("\n"))
    return secs


def block_excerpt(claim: str | None, secs: list[dict], lead: str = "") -> str | None:
    """The section of a multi-claim article that discusses `claim`: the lead, then the best-matching heading and its
    text up to the next heading of the same or a higher level. None when no section clearly matches (the caller then
    uses the page excerpt). Matching: share of the claim's stems found in heading+text, the heading counted twice;
    the winner must cover half of the claim and beat the runner-up, and "Podsumowanie" (which names every claim)
    is never chosen."""
    c = _stems(claim)
    if len(c) < 2:
        return None
    scored = []
    for i, s in enumerate(secs):
        if s["level"] == 0 or s["head"].lower().startswith("podsumow"):
            continue
        body = " ".join(s["lines"])[:1500]
        head_ov = _overlap(c, _stems(s["head"]))
        cover = _overlap(c, _stems(s["head"] + " " + body))
        scored.append((cover + head_ov, cover, i))
    if not scored:
        return None
    scored.sort(reverse=True)
    best, cover, i = scored[0]
    if cover < 0.5 or (len(scored) > 1 and best - scored[1][0] < 0.1):
        return None
    lines = [secs[i]["head"]] + secs[i]["lines"]
    for s in secs[i + 1:]:
        if s["level"] <= secs[i]["level"]:
            break
        lines += [s["head"]] + s["lines"]
    return "\n".join(([lead] if lead else []) + lines)


def _block_fields(cr: dict) -> tuple[str | None, str | None, str | None, str | None]:
    """(claim, claim_author, verdict_raw, review date) of one ClaimReview block."""
    claim = clean_text(cr.get("claimReviewed")) or None
    item = cr.get("itemReviewed") or {}
    au = item.get("author") or {}
    if isinstance(au, list):
        au = au[0] if au else {}
    claim_author = clean_text(au.get("name")) if isinstance(au, dict) else ""
    rr = cr.get("reviewRating") or {}
    verdict_raw = clean_text(rr.get("alternateName") or rr.get("name")) or None
    if claim and len(claim) > 1000:
        claim = claim[:1000] + " […]"
    return claim, claim_author or None, verdict_raw, iso_date(cr.get("datePublished"))


def parse(url: str, html: str) -> dict | None:
    """The page's main record (the id and ClaimReview every earlier harvest stored); see parse_page for all."""
    recs = parse_page(url, html)
    return recs[0] if recs else None


def parse_page(url: str, html: str) -> list[dict]:
    """One record per ClaimReview block of a page (198 of ~3k fact-checks rate several claims, e.g. four
    statements of one video, often with different ratings).

    - The first record is the page's main record: id `demagog:<section>/<slug>`, with the block earlier harvests kept
      (the first ClaimReview in `jsonld_blocks` order), so existing ids, links and eval gold stay valid.
    - Every other block becomes `<page id>#<n>`, n = its 1-based position among the page's ClaimReview blocks.
    - Each record has its block's claimReviewed, rating, claimant and review date, and shares the URL, title and tags.
    - Text: the block whose claim best matches the headline keeps the page excerpt (lead + summary box + start). Any
      other block gets the lead plus the section that discusses it (block_excerpt) when the headings allow,
      otherwise the page excerpt. Same clip limit for all (applied by the caller), so no record stores more text.
    - A block repeating an earlier block's claim and rating is dropped.
    """
    blocks = jsonld_blocks(html)
    legacy = next((b for b in blocks if b.get("@type") == "ClaimReview"), None)
    wp = next((b for b in blocks if b.get("@type") == "WebPage"), {})
    crs = claimreview_blocks(html)
    if legacy is not None and legacy not in crs:  # cannot happen (same scripts), but never lose the stored block
        crs.append(legacy)
    page = _parse_page_common(url, html, wp)
    if page is None:
        return []
    base, secs, lead = page
    if not crs:
        return [dict(base, claim=None, claim_author=None, verdict_raw=None, verdict=None)]

    fields = [_block_fields(cr) for cr in crs]
    main_i = crs.index(legacy) if legacy is not None else 0
    t_stems = _stems(base["title"])
    head_i = main_i
    if len(crs) > 1:
        ovs = [_overlap(_stems(f[0]), t_stems) for f in fields]
        if ovs[main_i] < max(ovs):
            head_i = ovs.index(max(ovs))
    out, seen = [], set()
    for i in [main_i] + [j for j in range(len(crs)) if j != main_i]:
        claim, claim_author, verdict_raw, reviewed = fields[i]
        key = ((claim or "").lower(), (verdict_raw or "").lower().rstrip("."))
        if key in seen:
            continue
        seen.add(key)
        text = base["text"]
        if i != head_i:
            text = block_excerpt(claim, secs, lead) or text
        out.append(dict(base, id=base["id"] if i == main_i else f"{base['id']}#{i + 1}",
                        published_at=reviewed or base["published_at"], text=text, claim=claim,
                        claim_author=claim_author, verdict_raw=verdict_raw, verdict=map_verdict(verdict_raw)))
    return out


def _parse_page_common(url: str, html: str, wp: dict) -> tuple[dict, list[dict], str] | None:
    """Fields every record of a page shares (id, url, title, tags, page excerpt), the article's heading sections and
    its lead."""
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

    def keep(ln: str) -> bool:
        return not any(b in ln for b in BOILERPLATE) and ln.strip() != title

    text = "\n".join(ln for ln in clean_text(text).split("\n") if keep(ln))
    inner = center.css_first(".dg-post-content__inner") if center else None
    secs = _sections(inner) if inner else []
    for s in secs:
        s["lines"] = [ln for ln in s["lines"] if keep(ln)]
    lead_node = center.css_first(".dg-post-content__lead") if center else None
    lead = clean_text(lead_node.text(deep=True)) if lead_node else ""
    lead = " ".join(ln for ln in lead.split("\n") if keep(ln))

    slug = url.rstrip("/").rsplit("/", 1)[-1]
    base = {
        "id": f"{SOURCE}:{section}/{slug}",
        "source_type": "factcheck",
        "publisher": "Demagog",
        "domain": "demagog.org.pl",
        "url": url,
        "title": title,
        "published_at": iso_date(wp.get("datePublished")),
        "retrieved_at": now_iso(),
        "language": "pl",
        "license": LICENSE,
        "text": text,
        "tags": tags,
    }
    return base, secs, lead


def reparse_cache(path=None, raw_dir=None, max_chars: int = 3000) -> int:
    """Offline rebuild of the corpus file from the raw page cache: every page is parsed again with parse_page, so a
    page rating several claims yields all of them. Makes no network request: only pages found in the cache are
    parsed (PoliteSession.get is never reached for a missing page). Each rebuilt record keeps the retrieved_at of
    the stored record (it comes from the same fetch); a page that is not cached, or no longer parses, keeps its
    stored records unchanged."""
    corpus = IncrementalCorpus(SOURCE, path)
    sess = PoliteSession(SOURCE)
    if raw_dir is not None:
        sess.raw_dir = raw_dir
    by_url: dict[str, list[dict]] = {}
    for r in corpus.records:
        by_url.setdefault(canonical_url(r.get("url") or ""), []).append(r)
    out: list[dict] = []
    st = {"pages": len(by_url), "not_cached": 0, "parse_failed": 0, "multi_block_pages": 0, "main_changed": 0}
    for old in by_url.values():
        main = next((r for r in old if "#" not in r["id"]), old[0])
        url = main["url"]
        recs = []
        if sess.is_cached(url):
            try:
                recs = parse_page(url, sess.get(url))
            except Exception as e:  # noqa: BLE001
                log(f"[parse error] {url}: {e}")
        else:
            st["not_cached"] += 1
        if not recs or recs[0]["id"] != main["id"]:
            st["parse_failed"] += sess.is_cached(url)
            out.extend(old)
            continue
        st["multi_block_pages"] += len(recs) > 1
        for rec in recs:
            rec["text"] = clip(rec["text"], max_chars)
            rec["retrieved_at"] = main.get("retrieved_at") or rec["retrieved_at"]
            out.append(normalize_record(rec))
        new_main = out[-len(recs)]
        st["main_changed"] += any(new_main.get(k) != main.get(k) for k in ("claim", "verdict_raw", "verdict"))
    corpus.records = out
    corpus.save(force=True)
    log(f"[demagog] reparse-cache: {corpus.n_existing} -> {len(out)} records; {st}")
    return 0


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
    ap.add_argument("--reparse-cache", action="store_true",
                    help="offline: rebuild the records of --out from their cached raw pages (no network request); "
                         "pages without a cached copy keep their records unchanged")
    ap.add_argument("--raw-dir", default=None, help="raw page cache to read (default data/raw/demagog)")
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

        if args.reparse_cache:
            return reparse_cache(Path(args.out) if args.out else None, Path(args.raw_dir) if args.raw_dir else None,
                                 args.max_chars)
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
                    recs = parse_page(u, html)
                except Exception as e:  # noqa: BLE001 - one odd page must not stop a long harvest
                    log(f"[parse error] {u}: {e}")
                    continue
                for k, rec in enumerate(recs):
                    rec["text"] = clip(rec["text"], args.max_chars)
                    if not corpus.add(rec, same_page=k > 0) and k == 0:
                        break  # page already stored: its other blocks are too
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
