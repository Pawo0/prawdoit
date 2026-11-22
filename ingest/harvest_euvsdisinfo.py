#!/usr/bin/env python3
"""Harvest EUvsDisinfo disinformation cases relevant to Poland -> data/corpus/euvsdisinfo.jsonl

Access path (no public API / bulk export found; WP REST API returns 401):
  1. Database listing https://euvsdisinfo.eu/disinformation-cases/?text=<q>&date=<dd.mm.yyyy - dd.mm.yyyy>
     robots.txt disallows */page/*, *sort=, *?numberposts= -> we never paginate; instead we
     slice by keyword x date window so every slice fits on the first (20-item) page.
  2. Case page in the site's Polish AI translation: https://euvsdisinfo.eu/pl/report/<slug>/
     (falls back to the English canonical /report/<slug>/ if no PL version).
Each case -> source_type "incident", verdict "false" (verdict_raw "Disinformation (EUvsDisinfo)"),
claim = SUMMARY (the pro-Kremlin claim), text = RESPONSE (the disproof).

Licence: EUvsDisinfo / EEAS East StratCom TF - reuse authorised with attribution (EEAS legal notice,
Commission Decision 2011/833/EU reuse policy) — see research/02_factcheck_sources.md.
"""
from __future__ import annotations

import argparse
import re
from datetime import date

from selectolax.lexbor import LexborHTMLParser

from common import JsonlWriter, PoliteSession, clean_text, iso_date, log, now_iso

SOURCE = "euvsdisinfo"
BASE = "https://euvsdisinfo.eu"
LIST = f"{BASE}/disinformation-cases/"
LICENSE = ("EUvsDisinfo (EEAS East StratCom Task Force). Reuse authorised provided the source is "
           "acknowledged (EEAS legal notice, Decision 2011/833/EU); third-party content excluded.")
LICENSE_PL = LICENSE + " PL text = EUvsDisinfo's own AI translation of the English case."
LICENSE_HF = LICENSE + (" Case texts taken from the Hugging Face copy NLP-UniBW/eu_vs_disinfo of the euvsdisinfo.eu "
                        "case database, because the site serves a Cloudflare challenge, which we do not circumvent.")

TOPIC_QUERIES = [
    "Polish", "Warsaw", "Tusk", "Duda", "Nawrocki", "Poles", "Polish army", "Belarus border",
    "Ukrainian refugees", "refugees Poland", "vaccine", "COVID vaccine", "5G", "Green Deal",
    "migration pact", "energy prices", "gas prices", "elections Poland", "biolab", "chemtrails",
    "grain", "farmers", "Rzeszow", "Lviv Poland", "partition of Ukraine", "Volhynia",
    "Kraków", "NATO Poland", "LGBT Poland", "euro Poland",
]


def month_windows(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        ny, nm = (y + (m == 12), 1 if m == 12 else m + 1)
        last = (date(ny, nm, 1) - date.resolution)
        yield date(y, m, 1), last
        y, m = ny, nm


def quarter_windows(y0: int, y1: int):
    for y in range(y0, y1 + 1):
        for q in range(4):
            a = date(y, 3 * q + 1, 1)
            b = (date(y + (q == 3), 1 if q == 3 else 3 * q + 4, 1) - date.resolution)
            yield a, b


def fmt(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def parse_listing(html: str) -> list[tuple[str, str | None, str]]:
    t = LexborHTMLParser(html)
    out = []
    for a in t.css("a.b-archive__database-item"):
        href = a.attributes.get("href") or ""
        m = re.search(r"/report/([^/]+)/?", href)
        if not m:
            continue
        d = a.css_first(".b-archive__database-item-date")
        ti = a.css_first(".b-archive__database-item-title")
        title = clean_text(ti.text(separator=" ")) if ti else m.group(1)
        title = re.sub(r"^DISINFO:\s*", "", title)
        out.append((m.group(1), iso_date(d.text()) if d else None, title))
    return out


def total_cases(html: str) -> int | None:
    m = re.search(r"([\d,]+)\s+cases", html)
    return int(m.group(1).replace(",", "")) if m else None


def parse_case(html: str) -> dict:
    t = LexborHTMLParser(html)
    title = t.css_first(".b-report__title")
    title = clean_text(title.text(separator=" ")) if title else ""
    title = re.sub(r"^DISINFO:\s*", "", title)
    skip = ("Read similar", "Przeczytaj podobne", "Zobacz podobne", "Przeczytaj inne", "Przeczytaj też")

    def paras(sel: str) -> list[str]:
        box = t.css_first(sel)
        if not box:
            return []
        out = []
        for n in box.css("p, li"):
            tx = " ".join(n.text(separator="").split())
            if tx and not tx.startswith(skip):
                out.append(tx)
        if not out:  # no <p>: take the text block minus heading
            for h in box.css("h3"):
                h.decompose()
            tx = clean_text(box.text(separator=""))
            if tx:
                out.append(tx)
        return out

    summary = paras(".b-report__summary")
    response = paras(".b-report__response")
    outlet, countries = None, []
    for li in t.css(".b-report__details-list li"):
        tx = clean_text(li.text(separator=" "))
        if tx.lower().startswith(("outlet", "źródło")):
            names = [a.text(strip=True) for a in li.css(".outlet-group > a:first-child")]
            outlet = ", ".join(dict.fromkeys(n for n in names if n)) or None
        elif "kraje" in tx.lower() or "countries" in tx.lower():
            countries = [c.strip() for c in tx.split(":", 1)[-1].split(",") if c.strip()]
    tags = [a.text(strip=True) for a in t.css(".b-report__keywords a") if a.text(strip=True)]
    return {"title": title, "summary": "\n".join(summary), "response": "\n".join(response),
            "outlet": outlet, "countries": countries, "tags": tags}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-cases", type=int, default=400)
    ap.add_argument("--from-year", type=int, default=2022, help="monthly slicing from this year")
    ap.add_argument("--quarterly-from", type=int, default=2015)
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--no-topics", action="store_true")
    ap.add_argument("--hf", default=None, help="path to NLP-UniBW/eu_vs_disinfo parquet (fallback)")
    ap.add_argument("--offline", action="store_true", help="never hit the site for case pages")
    ap.add_argument("--max-site", type=int, default=80, help="max uncached case-page requests to the site")
    args = ap.parse_args()

    sess = PoliteSession(SOURCE, delay=args.delay)
    cases: dict[str, tuple[str | None, str, str]] = {}  # slug -> (date, title, query)

    def run_query(q: str, win: tuple[date, date] | None):
        params = {"text": q}
        if win:
            params["date"] = f"{fmt(win[0])} - {fmt(win[1])}"
        html = sess.get(LIST, params=params)
        if not html:
            return 0, 0
        items = parse_listing(html)
        for slug, d, ti in items:
            cases.setdefault(slug, (d, ti, q))
        return len(items), total_cases(html) or 0

    today = date.today()
    # 1) "Poland" sliced by month (recent) and quarter (older)
    wins = list(month_windows(date(args.from_year, 1, 1), today))[::-1]
    wins += list(quarter_windows(args.quarterly_from, args.from_year - 1))[::-1]
    for w in wins:
        got, tot = run_query("Poland", w)
        if tot > 20:
            log(f"  [slice overflow] Poland {fmt(w[0])}: {tot} cases, only first 20 visible")
        log(f"[list] Poland {fmt(w[0])}-{fmt(w[1])}: {got}/{tot}  unique={len(cases)}")
        if len(cases) >= args.max_cases * 0.8:
            break
    # 2) topical queries (first page only, relevance order)
    if not args.no_topics:
        for q in TOPIC_QUERIES:
            if len(cases) >= args.max_cases:
                break
            got, tot = run_query(q, None)
            log(f"[list] '{q}': {got}/{tot} unique={len(cases)}")

    # 3) optional offline fallback: HF mirror of the EUvsDisinfo database (NLP-UniBW/eu_vs_disinfo,
    #    19,202 English cases up to 2025-07-15) - used when the site serves a Cloudflare challenge.
    hf = load_hf(args.hf) if args.hf else {}
    if hf:
        pl_rel = [k for k, r in hf.items() if "Poland" in (r["countries"] or [])
                  or "Polish" in (r["article_language"] or [])]
        pl_rel.sort(key=lambda k: hf[k]["publication_date"] or "", reverse=True)
        log(f"[hf] {len(hf)} cases, {len(pl_rel)} about Poland / in Polish")
        for k in pl_rel:
            cases.setdefault(k, (iso_date(hf[k]["publication_date"]), hf[k]["title"], "hf:Poland"))

    slugs = list(cases)
    log(f"[euvsdisinfo] {len(slugs)} candidate cases, writing up to {args.max_cases} (PL AI translation where reachable)")
    w = JsonlWriter(SOURCE)
    fails, tripped, site_req = 0, args.offline, 0
    for i, slug in enumerate(slugs, 1):
        if w.n >= args.max_cases:
            break
        d, list_title, q = cases[slug]
        url_pl = f"{BASE}/pl/report/{slug}/"
        url_en = f"{BASE}/report/{slug}/"
        c, lang, url = None, "pl", url_pl
        for u, lg in ((url_pl, "pl"), (url_en, "en")):
            cached = sess.is_cached(u)
            if tripped and not cached:
                continue
            if not cached:
                site_req += 1
                if site_req > args.max_site:
                    tripped = True
                    continue
            html = sess.get(u)
            if html is None and not cached:
                fails += 1
                if fails >= 3 and not tripped:
                    tripped = True
                    log("[euvsdisinfo] site keeps refusing (Cloudflare challenge) -> offline/HF mode")
                continue
            fails = 0
            c = parse_case(html) if html else None
            if c and c["response"]:
                lang, url = lg, u
                break
            c = None
        if c is None and slug in hf:
            r = hf[slug]
            c = {"title": r["title"], "summary": r["summary"] or "", "response": r["response"],
                 "outlet": ", ".join(r["outlet"] or []) or None, "countries": r["countries"] or [],
                 "tags": r["tags"] or []}
            lang, url = "en", url_en
            q = q + ";via:hf-mirror"
        if not c or not (c["response"] or c["summary"]):
            continue
        tags = ["euvsdisinfo", "pro-kremlin-disinformation"] + c["tags"] + [
            "kraj:" + x for x in c["countries"]] + [f"query:{q}"]
        if lang == "pl":
            tags.append("ai-translation")
        claim = c["summary"]
        if len(claim) > 1200:
            claim = claim[:1200].rsplit(" ", 1)[0] + " […]"
        w.write({
            "id": f"{SOURCE}:{slug}",
            "source_type": "incident",
            "publisher": "EUvsDisinfo (EEAS East StratCom Task Force)",
            "domain": "euvsdisinfo.eu",
            "url": url,
            "title": c["title"] or list_title,
            "published_at": d,
            "retrieved_at": now_iso(),
            "language": lang,
            "license": LICENSE_HF if q.endswith("via:hf-mirror") else LICENSE_PL if lang == "pl" else LICENSE,
            "text": c["response"] or c["summary"],
            "claim": claim or None,
            "claim_author": c["outlet"],
            "verdict_raw": "Disinformation (EUvsDisinfo)",
            "verdict": "false",
            "tags": tags,
        })
        if i % 25 == 0:
            log(f"  {i}/{len(slugs)} written={w.n} {sess.stats}")
    w.close()
    log(f"[euvsdisinfo] stats {sess.stats}")


def load_hf(path: str) -> dict[str, dict]:
    import pyarrow.parquet as pq
    t = pq.read_table(path, columns=["title", "summary", "response", "response_html", "link", "outlet",
                                      "publication_date", "article_language", "countries", "tags"])
    out = {}
    for r in t.to_pylist():
        m = re.search(r"/report/([^/?#]+)", r.get("link") or "")
        if not m:
            continue
        resp = r.get("response") or ""
        if r.get("response_html"):  # keep paragraph breaks
            tree = LexborHTMLParser(r["response_html"])
            ps = [" ".join(p.text(separator="").split()) for p in tree.css("p")]
            ps = [p for p in ps if p and not p.startswith(("Read similar", "See other examples"))]
            if ps:
                resp = "\n".join(ps)
        r["response"] = resp
        r["title"] = re.sub(r"^DISINFO:\s*", "", clean_text(r.get("title") or ""))
        out[m.group(1)] = r
    return out


if __name__ == "__main__":
    main()
