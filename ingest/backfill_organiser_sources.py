#!/usr/bin/env python3
"""One-off deep fetch of organiser-listed news sources: the last few months, newest first.

Why: a scheduled run (`python -m prawdowid.sources run <id>`) looks only at the newest `max_items` entries of a
listing or feed, so a source added today holds 10–30 documents. This script follows the pagination the sites offer
and fills data/corpus/<id>.jsonl back by roughly three to six months. It is the SAME code path as the scheduled run
(backend/prawdowid/sources/fetchers.py: robots.txt for every URL, fixed User-Agent, >= 1.5 s between requests to a
host, no protection bypass, stored URLs skipped, merge capped at `max_docs`, excerpt length `max_chars`); only
`params` are overridden in memory for this run. Run ONE process per group — the delay is kept per host per process.

Usage (backend venv, repo root):  backend/.venv/bin/python ingest/backfill_organiser_sources.py <group> [<group>…]
Groups: govpl | policja | kwp | cert | umgdy | kgsok          (runs of 2026-11-21: research/10_organiser_sources.md;
kwp and kgsok were run a second time with 4 more listing/feed pages, to cover at least the last three months)

Police sites (policja.pl, mazowiecka.policja.gov.pl): the article pages carry no publication date, so after the fetch
the listing pages are read once more and `published_at` of every record found there is set from the listing's
`<time datetime="…">` (without this ~6% of the records got a year found somewhere in the body text).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from prawdowid.sources import fetchers as F, registry as R  # noqa: E402

POLICJA = "https://policja.pl/pol/aktualnosci?page={}"
KWP = "https://mazowiecka.policja.gov.pl/ra/aktualnosci/aktualnosci?page={}"


def pages(tpl: str, a: int, b: int) -> list[str]:
    return [tpl.format(n) for n in range(a, b + 1)]


def html_list(tpl: str, rx: str, a: int, b: int) -> dict:
    return dict(method="html_list", params={"list_urls": pages(tpl, a, b), "link_regex": rx, "max_items": 200,
                                            "min_text_chars": 200})


# source id -> runs; each run = overrides of the registry entry (fetchers cap one run at 200 entries)
GROUPS: dict[str, list[tuple[str, list[dict]]]] = {
    "govpl": [(sid, [dict(params={"max_items": n})]) for sid, n in (
        ("rcb_komunikaty", 180), ("kgpsp_aktualnosci", 200), ("mon_aktualnosci", 200), ("mswia_aktualnosci", 150),
        ("kprm_wydarzenia", 200), ("mi_aktualnosci", 150), ("gis_ostrzezenia", 80), ("paa_aktualnosci", 60))],
    "policja": [("policja_aktualnosci", [
        html_list(POLICJA, r"^https://policja\.pl/pol/aktualnosci/\d+,[^/]+\.html$", a, b) for a, b in ((1, 20), (21, 40))])],
    "kwp": [("kwp_radom_aktualnosci", [
        html_list(KWP, r"^https://mazowiecka\.policja\.gov\.pl/ra/aktualnosci/aktualnosci/\d+,[^/]+\.html$", a, b)
        for a, b in ((1, 10), (11, 20))])],
    "cert": [("cert_komunikaty", [dict(params={"list_urls": pages("https://moje.cert.pl/komunikaty/?page={}", 1, 12),
                                               "max_items": 120})])],
    "umgdy": [("umgdy_aktualnosci", [dict(params={
        "list_urls": ["https://www.umgdy.gov.pl/aktualnosci/"] + pages("https://www.umgdy.gov.pl/aktualnosci/strona/{}/", 2, 6),
        "max_items": 60})])],
    "kgsok": [("kgsok_aktualnosci", [dict(params={"feed_url": f"https://kgsok.pl/feed/?paged={n}", "max_items": 20})
                                     for n in range(2, 20)])],
}
SINCE = (date.today() - timedelta(days=200)).isoformat()  # newly fetched records older than this are not kept
LISTING_DATES = {"policja_aktualnosci": (POLICJA, 40), "kwp_radom_aktualnosci": (KWP, 20)}
KEEP = ("max_docs", "max_chars", "delay_s", "date_regex")  # registry params that also apply to an overridden method


def write_corpus(sid: str, rows: list[dict]) -> None:
    rows.sort(key=lambda r: (r.get("published_at") or "", r.get("retrieved_at") or ""), reverse=True)
    path = R.corpus_path(sid)
    tmp = path.with_name(f".{path.name}.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def dates_from_listing(sid: str) -> int:
    tpl, last = LISTING_DATES[sid]
    dates: dict[str, str] = {}
    for n in range(1, last + 1):
        final, body, ctype = F.http_get(tpl.format(n))
        for m in re.finditer(r'<a href="([^"]+\.html)"[^>]*>(.*?)</a>', F._decode(body, ctype), flags=re.S):
            t = re.search(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})"', m.group(2))
            if t:
                dates[F.canonical(urljoin(final, m.group(1)))] = t.group(1)
    rows, changed = F.read_corpus(sid), 0
    for r in rows:
        d = dates.get(F.canonical(r.get("url") or ""))
        if d and d != r.get("published_at"):
            r["published_at"], changed = d, changed + 1
    write_corpus(sid, rows)
    return changed


def backfill(sid: str, runs: list[dict]) -> dict:
    base = R.get(sid)
    old_ids = {r.get("id") for r in F.read_corpus(sid)}
    before, new, requests, notes, error, t0 = len(old_ids), 0, 0, [], None, time.time()
    for ov in runs:
        same_method = ov.get("method", base["method"]) == base["method"]
        params = {**(base["params"] if same_method else {k: v for k, v in base["params"].items() if k in KEEP}),
                  **ov.get("params", {})}
        src = R.validate({**base, "method": ov.get("method", base["method"]), "params": params}, strict=False)
        ctx = F.Ctx(known_urls={F.canonical(r.get("url") or "") for r in F.read_corpus(sid)})
        try:
            recs = F.fetch_source(src, ctx)
        except F.FetchError as e:  # robots.txt, bot protection, HTTP error: stop this source, never work around it
            error, recs = f"{type(e).__name__}: {e}", []
        requests += ctx.pages
        notes += ctx.notes
        if recs:
            new += F.merge_into_corpus(base, recs)[0]
        if error:
            break
    redated = dates_from_listing(sid) if sid in LISTING_DATES and not error else 0
    # Some listings also carry old items (policja.pl: pages 18–25 go back to 2013): the knowledge base should hold
    # recent material, so newly fetched records older than SINCE are not kept. Records stored before are untouched.
    rows = F.read_corpus(sid)
    keep = [r for r in rows if r.get("id") in old_ids or (r.get("published_at") or "9999") >= SINCE]
    if len(keep) != len(rows):
        write_corpus(sid, keep)
    dates = sorted((r.get("published_at") or "")[:10] for r in keep if r.get("published_at"))
    return dict(source=sid, before=before, after=len(keep), new=new - (len(rows) - len(keep)), requests=requests,
                error=error, oldest=dates[0] if dates else None, newest=dates[-1] if dates else None,
                skipped=len(notes), dates_from_listing=redated, older_than_since_dropped=len(rows) - len(keep),
                elapsed_s=round(time.time() - t0))


if __name__ == "__main__":
    groups = sys.argv[1:]
    if not groups or any(g not in GROUPS for g in groups):
        sys.exit(f"usage: backfill_organiser_sources.py <{' | '.join(GROUPS)}> …")
    for g in groups:
        for sid, runs in GROUPS[g]:
            print(json.dumps(backfill(sid, runs), ensure_ascii=False), flush=True)
