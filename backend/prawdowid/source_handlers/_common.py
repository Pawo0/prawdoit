"""Shared connector HTTP helpers, corpus records and refresh utilities.

Small helpers shared by the custom source handlers (msz_odyseusz, rso_ostrzezenia, imgw_ostrzezenia,
static_pages).

All HTTP goes through prawdowid.sources.fetchers.http_get, so handlers get the same politeness rules as the
built-in methods: User-Agent "PrawdowidHackathonBot/0.1 (research prototype)", robots.txt checked for every URL,
per-host delay (>= 1.5 s by default, never below 1.2 s), back-off on 429/5xx, and a hard stop on CAPTCHA /
bot-challenge pages (protections are never circumvented). Every URL is SSRF-checked as well.

Record URLs: the scheduler de-duplicates corpus records by canonical URL, and canonical() drops the #fragment.
Handlers that emit several records for one page therefore keep them apart with a harmless query parameter
(e.g. https://odyseusz.gov.pl/IT?sekcja=bezpieczenstwo); the link still opens the right page.

Reading guide: docs/backend/SOURCES.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from urllib.parse import urljoin

MAX_TEXT = 4000
JSON_ACCEPT = "application/json,text/plain;q=0.8,*/*;q=0.5"

PL_MONTHS = {
    "stycznia": 1,
    "lutego": 2,
    "marca": 3,
    "kwietnia": 4,
    "maja": 5,
    "czerwca": 6,
    "lipca": 7,
    "sierpnia": 8,
    "września": 9,
    "wrzesnia": 9,
    "października": 10,
    "pazdziernika": 10,
    "listopada": 11,
    "grudnia": 12,
}

# TERYT voivodeship codes (first two digits of a powiat/gmina code)
TERYT_WOJ = {
    "02": "dolnośląskie",
    "04": "kujawsko-pomorskie",
    "06": "lubelskie",
    "08": "lubuskie",
    "10": "łódzkie",
    "12": "małopolskie",
    "14": "mazowieckie",
    "16": "opolskie",
    "18": "podkarpackie",
    "20": "podlaskie",
    "22": "pomorskie",
    "24": "śląskie",
    "26": "świętokrzyskie",
    "28": "warmińsko-mazurskie",
    "30": "wielkopolskie",
    "32": "zachodniopomorskie",
}


def http_get(
    url: str, *, max_bytes: int = 3_000_000, accept: str | None = None, delay: float = 1.5
):
    """(final_url, body bytes, content-type) via the framework's polite client."""
    from ..sources.fetchers import http_get as _get

    kw = {"delay": max(1.2, float(delay)), "max_bytes": max_bytes}
    if accept:
        kw["accept"] = accept
    return _get(url, **kw)


def get_json(url: str, *, max_bytes: int = 5_000_000, delay: float = 1.5):
    _, body, _ = http_get(url, max_bytes=max_bytes, accept=JSON_ACCEPT, delay=delay)
    return json.loads(body.decode("utf-8", errors="replace"))


def get_html(url: str, *, delay: float = 1.5) -> tuple[str, str]:
    from ..sources.fetchers import _decode

    final, body, ctype = http_get(url, delay=delay)
    return final, _decode(body, ctype)


def delay_of(source: dict) -> float:
    return float((source.get("params") or {}).get("delay_s") or 1.5)


def max_chars(source: dict) -> int:
    return int((source.get("params") or {}).get("max_chars") or MAX_TEXT)


def known_urls(source: dict) -> set[str]:
    return set(source.get("_known_urls") or [])


def canonical(url: str) -> str:
    from ..sources.fetchers import canonical as _c

    return _c(url)


def now_iso() -> str:
    return (
        dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def clean_ws(s: str) -> str:
    s = (s or "").replace("\r", "").replace(" ", " ").replace("​", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def truncate(s: str, n: int) -> str:
    s = s or ""
    if len(s) <= n:
        return s
    cut = s[:n]
    i = max(cut.rfind(". "), cut.rfind("\n"))
    return (cut[: i + 1] if i > n * 0.6 else cut).rstrip() + " […]"


def md_to_text(s: str, base: str = "") -> str:
    """Markdown-ish CMS text -> plain text; links become 'label (https://…)' so the URL stays citable."""
    if not s:
        return ""

    def link(m: re.Match) -> str:
        label, href = m.group(1).strip(), m.group(2).strip()
        if base and not href.startswith(("http://", "https://", "mailto:")):
            href = urljoin(base, href)
        return f"{label} ({href})" if label and label != href else href

    s = re.sub(r"\[([^\]]*)\]\(([^)\s]+)\)", link, s)
    s = re.sub(r"(\*\*|__)(.+?)\1", r"\2", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return clean_ws(s)


def pl_text_date(text: str) -> str | None:
    """First Polish long date in text ('21 listopada 2026 r.') -> '2026-11-21'."""
    m = re.search(r"\b(\d{1,2})\s+(" + "|".join(PL_MONTHS) + r")\s+(\d{4})", text or "", re.I)
    if not m:
        return None
    try:
        return dt.date(int(m.group(3)), PL_MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
    except ValueError:
        return None


def text_dates(text: str) -> list[str]:
    """Every date written in the text — Polish long dates ('3 listopada 2026') and dd.mm.yyyy — as ISO strings."""
    out = []
    for m in re.finditer(
        r"\b(\d{1,2})\s+(" + "|".join(PL_MONTHS) + r")\s+(\d{4})", text or "", re.I
    ):
        try:
            out.append(
                dt.date(int(m.group(3)), PL_MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
            )
        except ValueError:
            pass
    for m in re.finditer(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text or ""):
        try:
            out.append(dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat())
        except ValueError:
            pass
    return out


def iso_date(s: str | None) -> str | None:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s or "")
    return m.group(1) if m else None


def short_hash(*parts: object) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12]


def record(
    source: dict,
    *,
    sid: str,
    url: str,
    title: str,
    text: str,
    published_at: str | None,
    tags: list[str] | None = None,
    domain: str | None = None,
) -> dict:
    """A corpus record with exactly the SourceDoc schema (docs/SOURCE_REGISTRY.md)."""
    from urllib.parse import urlsplit

    host = (urlsplit(url).hostname or "").lower()
    return {
        "id": f"{source['id']}:{sid}",
        "source_type": source.get("category", "official"),
        "publisher": source.get("publisher") or source.get("name") or "",
        "domain": domain or (host[4:] if host.startswith("www.") else host),
        "url": url,
        "title": re.sub(r"\s+", " ", title or "").strip()[:400] or url,
        "published_at": published_at,
        "retrieved_at": now_iso(),
        "language": source.get("language", "pl"),
        "license": source.get("license", ""),
        "text": truncate(clean_ws(text), max_chars(source)),
        "claim": None,
        "claim_author": None,
        "verdict_raw": None,
        "verdict": None,
        "tags": sorted(
            {t for t in [source["id"], *(source.get("topics") or []), *(tags or [])] if t}
        ),
    }
