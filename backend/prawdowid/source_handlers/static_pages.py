"""Snapshots of fixed official pages that are not article lists (so html_list/govpl_list cannot express them):
info pages (passenger rights, hotlines), and pages whose content is replaced in place (RCB daily report, the
current navigation notices of Wody Polskie / Urząd Morski).

params:
  pages        list of URLs, or of {"url": ..., "title": ..., "tags": [...]} (required)
  history      "daily": one record per page per day (id <slug>:<YYYY-MM-DD>, url <page>?data=<YYYY-MM-DD>) so
               earlier versions stay citable (e.g. RCB "Raport dobowy"); default: one record per page,
               replaced on every run
  date_from_text  take published_at from the first Polish long date in the text ("21 listopada 2026 r.")
               instead of page metadata (default false); "latest" = the most recent date in the text that is not
               in the future (long or dd.mm.yyyy) — for pages of notices "in force" and gov.pl info pages, whose
               change-history table carries the last update. (Page metadata dates of such pages are unreliable:
               trafilatura guesses them from the content, e.g. "ustawa z 21 grudnia 2000" -> 2000-01-01.)
  min_text_chars  skip pages with less text (default 150)

Text: trafilatura (precision mode, tables kept); if the page's main container (<article>/<main>/#main-content)
holds clearly more text — e.g. collapsed accordions of notice titles — that text is used instead.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from urllib.parse import urlsplit

from ._common import clean_ws, delay_of, get_html, known_urls, pl_text_date, record, short_hash, text_dates

log = logging.getLogger("prawdowid.sources.static_pages")


def _main_text(html: str) -> str:
    import lxml.html

    try:
        doc = lxml.html.fromstring(html)
    except Exception:  # noqa: BLE001
        return ""
    for xp in ('//*[@id="main-content"]', "//article", "//main"):
        els = doc.xpath(xp)
        if els:
            el = els[0]
            for bad in el.xpath(".//script|.//style|.//nav|.//noscript|.//form"):
                bad.drop_tree()
            return clean_ws(el.text_content())
    return ""


def _extract(url: str, html: str) -> dict:
    import trafilatura

    meta = trafilatura.extract_metadata(html)
    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=True, favor_precision=True) or ""
    alt = _main_text(html)
    if len(alt) > 1.4 * len(text) + 200:
        text = alt
    return {"title": (meta.title if meta else None) or "", "date": (meta.date if meta else None), "text": text}


def _slug(url: str) -> str:
    p = urlsplit(url)
    s = re.sub(r"[^a-z0-9]+", "_", (p.netloc.removeprefix("www.") + p.path).lower()).strip("_")
    return s[-60:] if len(s) > 60 else s or short_hash(url)


def fetch(source: dict) -> list[dict]:
    from ..sources.fetchers import Protected

    p = source.get("params") or {}
    delay = delay_of(source)
    known = known_urls(source)
    daily = (p.get("history") or "") == "daily"
    min_chars = int(p.get("min_text_chars") or 150)
    today = dt.date.today().isoformat()
    out: list[dict] = []
    pages = p.get("pages") or []
    if p.get("max_items"):
        pages = pages[: int(p["max_items"])]
    for item in pages:
        page = item if isinstance(item, str) else item.get("url")
        if not page:
            continue
        try:
            final, html = get_html(page, delay=delay)
        except Protected:
            raise
        except Exception as e:  # noqa: BLE001 — one page must not kill the run
            log.info("page %s failed: %s", page, e)
            continue
        art = _extract(final, html)
        if len(art["text"]) < min_chars:
            log.info("page %s: too little text (%d chars)", page, len(art["text"]))
            continue
        mode = p.get("date_from_text")
        if mode == "latest":
            past = [d for d in text_dates(art["text"]) if "2000-01-01" < d <= today]
            text_date = max(past) if past else None
        else:
            text_date = pl_text_date(art["text"]) if mode else None
        date = text_date or (art["date"][:10] if art["date"] else None)
        title = (item.get("title") if isinstance(item, dict) else None) or art["title"] or page
        tags = list(item.get("tags") or []) if isinstance(item, dict) else []
        if daily:
            stamp = date or today
            url, sid = f"{page}?data={stamp}", f"{_slug(page)}:{stamp}"
            if stamp not in title:
                title = f"{title} ({stamp[8:10]}.{stamp[5:7]}.{stamp[:4]})"
        else:
            url, sid = page, _slug(page)
        if daily and url in known:
            continue  # today's version already stored
        out.append(record(source, sid=sid, url=url, title=title, text=art["text"], published_at=date, tags=tags))
    return out
