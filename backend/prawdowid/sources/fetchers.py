"""Fetch methods for registry sources (see docs/SOURCE_REGISTRY.md) + the "auto-detect" helper for admins.

Politeness (same rules as ingest/official_common.py, a challenge requirement):
  * fixed User-Agent "PrawdowidHackathonBot/0.1 (research prototype)"
  * robots.txt checked for every URL (also after redirects); 401/403/5xx/unreachable robots.txt => do not fetch
  * per-host minimum delay (default 1.5 s; raised to Crawl-delay; params.delay_s can only make it slower)
  * back-off on 429/5xx; a CAPTCHA / bot-challenge page aborts the source — protections are never circumvented
  * already-stored URLs are not re-downloaded
Every URL is also SSRF-checked (public IPs only), because admins may enter arbitrary addresses.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib
import importlib.util
import json
import logging
import re
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from ..config import settings
from ..robots import RobotsTxt
from ..security import ResolveError, UnsafeURL, check_public_url
from . import registry

log = logging.getLogger("prawdowid.sources")

UA = "PrawdowidHackathonBot/0.1 (research prototype)"
INGEST_DIR = settings.root / "ingest"
DEFAULT_DELAY = 1.5
ROBOTS_TTL = 6 * 3600
MAX_ITEMS_CAP = 200          # hard cap per run, whatever params say
MAX_TEXT = 4000              # same as ingest/
HTML_MAX_BYTES = 3_000_000
XML_MAX_BYTES = 15_000_000
SCHEMA_KEYS = ("id", "source_type", "publisher", "domain", "url", "title", "published_at", "retrieved_at",
               "language", "license", "text", "claim", "claim_author", "verdict_raw", "verdict", "tags")


class FetchError(RuntimeError):
    """A source cannot be fetched (message is shown to the admin, in Polish)."""


class RobotsDisallowed(FetchError):
    pass


class Protected(FetchError):
    """The site actively blocks automated access (403/429 challenge, CAPTCHA). We stop, we do not work around it."""


# ------------------------------------------------------------------ polite HTTP client
_robots: dict[str, tuple[float, RobotsTxt | None, bool]] = {}
_host_delay: dict[str, float] = {}
_last_hit: dict[str, float] = {}
_host_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
_state_lock = threading.Lock()
_CHALLENGE = re.compile(r"cf-chl|challenge-platform|Just a moment\.\.\.|Attention Required! \| Cloudflare|"
                        r"Request unsuccessful\. Incapsula|ddos-guard", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _origin(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}"


def _robots_for(url: str) -> tuple[RobotsTxt | None, bool]:
    """(parser, reachable). Unreachable/5xx/401/403 robots.txt => treat as 'disallow' (conservative).
    Rules are matched per RFC 9309 (longest match wins, Allow wins ties) — see prawdowid/robots.py."""
    origin = _origin(url)
    with _state_lock:
        hit = _robots.get(origin)
        if hit and time.time() - hit[0] < (ROBOTS_TTL if hit[2] else 600):
            return hit[1], hit[2]
    rp = RobotsTxt()
    ok = True
    try:
        check_public_url(origin + "/robots.txt")
        with httpx.Client(timeout=15, follow_redirects=True, headers={"User-Agent": UA}) as c:
            r = c.get(origin + "/robots.txt")
        if r.status_code in (401, 403):
            rp.disallow_all = True
        elif r.status_code >= 500:
            rp, ok = None, False
        elif r.status_code >= 400:
            rp.allow_all = True
        else:
            body = r.text
            if "<html" in body[:500].lower():  # SPA fallback served as robots.txt => no rules
                body = ""
            rp.parse(body.splitlines())
            cd = rp.crawl_delay(UA)
            if cd:
                with _state_lock:
                    _host_delay[urlsplit(url).netloc] = max(float(cd), DEFAULT_DELAY)
    except (httpx.HTTPError, UnsafeURL, ResolveError, OSError):
        rp, ok = None, False
    with _state_lock:
        _robots[origin] = (time.time(), rp, ok)
    return rp, ok


def robots_allowed(url: str) -> bool:
    rp, ok = _robots_for(url)
    if not ok or rp is None:
        return False
    return rp.can_fetch(UA, url)


def robots_sitemaps(url: str) -> list[str]:
    rp, ok = _robots_for(url)
    return list(rp.site_maps() or []) if ok and rp else []


def _wait(netloc: str, min_delay: float) -> None:
    lock = _host_locks[netloc]
    with lock:
        d = max(min_delay, _host_delay.get(netloc, DEFAULT_DELAY))
        gap = time.time() - _last_hit.get(netloc, 0.0)
        if gap < d:
            time.sleep(d - gap)
        _last_hit[netloc] = time.time()


def http_get(url: str, *, delay: float = DEFAULT_DELAY, max_bytes: int = HTML_MAX_BYTES, retries: int = 3,
             accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.5") -> tuple[str, bytes, str]:
    """Polite GET. Returns (final_url, body, content_type). Raises FetchError subclasses."""
    delay = max(1.0, delay)
    for _hop in range(5):  # manual redirects: every hop is SSRF- and robots-checked
        try:
            url = check_public_url(url)
        except (UnsafeURL, ResolveError) as e:
            raise FetchError(str(e)) from e
        if not robots_allowed(url):
            raise RobotsDisallowed(f"robots.txt nie pozwala pobrać {url} (albo jest niedostępny) — pomijamy.")
        netloc = urlsplit(url).netloc
        err: Exception | None = None
        for attempt in range(retries):
            _wait(netloc, delay)
            try:
                with httpx.Client(timeout=20, follow_redirects=False,
                                  headers={"User-Agent": UA, "Accept": accept, "Accept-Language": "pl,en;q=0.5"}) as c:
                    with c.stream("GET", url) as r:
                        if r.is_redirect:
                            nxt = urljoin(url, r.headers.get("location", ""))
                            break
                        if r.status_code in (429, 500, 502, 503, 504):
                            ra = r.headers.get("retry-after", "")
                            back = min(60, int(ra)) if ra.isdigit() else 5 * (attempt + 1) * (3 if r.status_code == 429 else 1)
                            err = (Protected(f"{netloc} ogranicza liczbę zapytań (HTTP 429) — przerywamy, spróbujemy później.")
                                   if r.status_code == 429 else FetchError(f"HTTP {r.status_code} dla {url}"))
                            log.info("HTTP %s %s -> retry in %ss", r.status_code, url, back)
                            if attempt < retries - 1:
                                time.sleep(back)
                            continue
                        buf = bytearray()
                        for chunk in r.iter_bytes():
                            buf.extend(chunk)
                            if len(buf) > max_bytes:
                                break
                        body = bytes(buf)
                        ctype = r.headers.get("content-type", "")
                        head = body[:4000].decode("utf-8", "replace")
                        if r.status_code in (401, 403) or (r.status_code >= 400 and _CHALLENGE.search(head)):
                            raise Protected(f"Strona {netloc} blokuje automatyczny dostęp (HTTP {r.status_code}) — "
                                            "nie obchodzimy zabezpieczeń, źródło pominięte.")
                        if r.status_code >= 400:
                            raise FetchError(f"HTTP {r.status_code} dla {url}")
                        if "html" in ctype and _CHALLENGE.search(head) and len(body) < 30000:
                            raise Protected(f"Strona {netloc} pokazuje test antybotowy (CAPTCHA) — nie obchodzimy go.")
                        if body[:2] == b"\x1f\x8b":
                            body = gzip.decompress(body)[:max_bytes]
                        return url, body, ctype
            except httpx.HTTPError as e:
                err = FetchError(f"Błąd połączenia z {netloc} ({type(e).__name__}).")
                time.sleep(3 * (attempt + 1))
                continue
        else:
            raise err or FetchError(f"Nie udało się pobrać {url}")
        url = nxt
    raise FetchError("Zbyt wiele przekierowań.")


def _decode(body: bytes, ctype: str = "") -> str:
    m = re.search(r"charset=([\w\-]+)", ctype or "") or re.search(rb"<meta[^>]+charset=[\"']?([\w\-]+)", body[:3000], re.I)
    enc = m.group(1) if m else "utf-8"
    enc = enc.decode("ascii", "ignore") if isinstance(enc, bytes) else enc
    try:
        return body.decode(enc, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


# ------------------------------------------------------------------ helpers reused from ingest/
_ingest_mods: dict[str, object] = {}


def ingest_module(name: str):
    """Import ingest/<name>.py by path (ingest/ is not a package). official_common is registered under its own
    name because official_govpl.py does `from official_common import ...`."""
    if name in _ingest_mods:
        return _ingest_mods[name]
    if name != "official_common":
        ingest_module("official_common")
    if name in sys.modules and name == "official_common":
        mod = sys.modules[name]
    else:
        spec = importlib.util.spec_from_file_location(name, INGEST_DIR / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        if name == "official_common":
            sys.modules[name] = mod
        spec.loader.exec_module(mod)
    _ingest_mods[name] = mod
    return mod


def html_to_text(fragment: str) -> str:
    return ingest_module("official_common").html_to_text(fragment)


def to_date(s: str | None) -> str | None:
    """'16.11.2026' / '2026-11-16' / RFC 822 / Polish long date ('5 listopada 2026') -> 'YYYY-MM-DD'."""
    if not s:
        return None
    try:
        d = ingest_module("official_common").pl_date(str(s))
    except Exception:  # noqa: BLE001
        d = None
    if not d:
        from ..source_handlers._common import pl_text_date

        d = pl_text_date(str(s))
    return d


def date_from_html(source: dict, html: str) -> str | None:
    """Publication date via params.date_regex (group 1, else the whole match) — for sites whose metadata date
    is the site's modification date rather than the article's publication date."""
    rx = (source.get("params") or {}).get("date_regex")
    if not rx:
        return None
    m = re.search(rx, html, flags=re.S | re.I)
    return to_date(m.group(1) if m and m.groups() else (m.group(0) if m else None))


def truncate(s: str, n: int) -> str:
    return ingest_module("official_common").truncate(s, n)


def extract_article(url: str, html: str) -> dict:
    """Main text + metadata via trafilatura (as backend/prawdowid/fetch.py)."""
    import trafilatura

    meta = trafilatura.extract_metadata(html)
    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=False, favor_precision=True) or ""
    return {"title": (meta.title if meta else None) or "", "date": to_date(meta.date) if meta and meta.date else None,
            "sitename": (meta.sitename if meta else None) or "", "text": text}


def canonical(url: str) -> str:
    p = urlsplit(url.strip())
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", p.query, ""))


def _domain(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def make_record(source: dict, *, url: str, title: str, text: str, published_at: str | None,
                tags: list[str] | None = None) -> dict:
    url = canonical(url)
    max_chars = int(source.get("params", {}).get("max_chars") or MAX_TEXT)
    return {
        "id": f"{source['id']}:{hashlib.sha1(url.encode()).hexdigest()[:12]}",
        "source_type": source.get("category", "official"),
        "publisher": source.get("publisher") or source.get("name"),
        "domain": _domain(url),
        "url": url,
        "title": re.sub(r"\s+", " ", title or "").strip()[:400] or url,
        "published_at": published_at,
        "retrieved_at": now_iso(),
        "language": source.get("language", "pl"),
        "license": source.get("license", ""),
        "text": truncate(text or "", max_chars),
        "claim": None, "claim_author": None, "verdict_raw": None, "verdict": None,
        "tags": sorted(set([source["id"], *source.get("topics", []), *(tags or [])])),
    }


def normalize_record(rec: dict, source: dict) -> dict | None:
    """Make a handler-provided record match the corpus schema; None if unusable."""
    from ..schemas import SourceDoc

    if not isinstance(rec, dict) or not rec.get("url") or not (rec.get("text") or rec.get("claim")):
        return None
    base = make_record(source, url=rec["url"], title=rec.get("title") or "", text=rec.get("text") or "",
                       published_at=rec.get("published_at"), tags=list(rec.get("tags") or []))
    out = {k: (rec[k] if rec.get(k) not in (None, "") else base[k]) for k in SCHEMA_KEYS}
    if not str(out["id"]).startswith(f"{source['id']}:"):
        out["id"] = f"{source['id']}:{out['id']}"
    try:
        SourceDoc(**out)
    except Exception:  # noqa: BLE001
        return None
    return out


# ------------------------------------------------------------------ fetch context
@dataclass
class Ctx:
    limit: int | None = None              # dry run: stop after this many records
    known_urls: set[str] = field(default_factory=set)
    notes: list[str] = field(default_factory=list)
    pages: int = 0

    def want(self, source: dict) -> int:
        """How many list/feed entries to look at (dry run: a few spare ones in case some pages are too short)."""
        n = min(int(source.get("params", {}).get("max_items") or 30), MAX_ITEMS_CAP)
        return min(n, 2 * self.limit) if self.limit else n

    def done(self, out: list) -> bool:
        return bool(self.limit) and len(out) >= self.limit

    def delay(self, source: dict) -> float:
        return max(DEFAULT_DELAY, float(source.get("params", {}).get("delay_s") or 0))


def _get(ctx: Ctx, source: dict, url: str, **kw) -> tuple[str, bytes, str]:
    ctx.pages += 1
    return http_get(url, delay=ctx.delay(source), **kw)


def _fetch_article(ctx: Ctx, source: dict, url: str, *, title: str = "", date: str | None = None,
                   fallback_text: str = "", min_chars: int = 0, tags: list[str] | None = None) -> dict | None:
    try:
        final, body, ctype = _get(ctx, source, url)
    except Protected:
        raise
    except FetchError as e:
        ctx.notes.append(f"pominięto {url}: {e}")
        if fallback_text and len(fallback_text) >= max(min_chars, 80):
            return make_record(source, url=url, title=title, text=fallback_text, published_at=date, tags=tags)
        return None
    if "html" not in ctype and "xml" not in ctype and ctype:
        ctx.notes.append(f"pominięto {url}: typ treści {ctype}")
        return None
    html = _decode(body, ctype)
    art = extract_article(final, html)
    text = art["text"] if len(art["text"]) >= len(fallback_text or "") else fallback_text
    if len(text or "") < max(min_chars, 80):
        ctx.notes.append(f"pominięto {url}: za mało tekstu ({len(text or '')} znaków)")
        return None
    return make_record(source, url=url, title=title or art["title"], text=text,
                       published_at=date or date_from_html(source, html) or art["date"], tags=tags)


# ------------------------------------------------------------------ XML (RSS/Atom/sitemap) — XXE-safe
def _xml_root(body: bytes):
    from lxml import etree

    parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True, huge_tree=False)
    root = etree.fromstring(body.lstrip(), parser)
    if root is None:
        raise FetchError("Nie udało się odczytać XML.")
    return root


def _ln(el) -> str:
    t = el.tag if isinstance(el.tag, str) else ""
    return t.rsplit("}", 1)[-1].lower()


def _child_text(el, *names: str) -> str:
    for ch in el:
        if _ln(ch) in names:
            return "".join(ch.itertext()).strip()
    return ""


def parse_feed(body: bytes) -> list[dict]:
    root = _xml_root(body)
    items = []
    for el in root.iter():
        if _ln(el) not in ("item", "entry"):
            continue
        link = _child_text(el, "link")
        for ch in el:
            if _ln(ch) == "link" and ch.get("href") and ch.get("rel", "alternate") == "alternate":
                link = ch.get("href")
                break
        if not link:
            g = _child_text(el, "guid")
            link = g if g.startswith("http") else ""
        if not link:
            continue
        desc = _child_text(el, "encoded") or _child_text(el, "content") or _child_text(el, "description", "summary")
        items.append({"url": link.strip(), "title": html_to_text(_child_text(el, "title")),
                      "date": to_date(_child_text(el, "pubdate", "published", "updated", "date")),
                      "summary": html_to_text(desc)})
    return items


def parse_sitemap(body: bytes) -> tuple[str, list[tuple[str, str]]]:
    """('index'|'urlset', [(loc, lastmod)])."""
    root = _xml_root(body)
    kind = "index" if _ln(root) == "sitemapindex" else "urlset"
    out = []
    for el in root:
        if _ln(el) in ("url", "sitemap"):
            loc = _child_text(el, "loc")
            if loc:
                out.append((loc.strip(), _child_text(el, "lastmod")[:25]))
    return kind, out


# ------------------------------------------------------------------ methods
def fetch_rss(source: dict, ctx: Ctx) -> list[dict]:
    p = source["params"]
    _, body, _ = _get(ctx, source, p["feed_url"], max_bytes=XML_MAX_BYTES,
                      accept="application/rss+xml,application/atom+xml,application/xml;q=0.9,*/*;q=0.5")
    items = parse_feed(body)
    if not items:
        raise FetchError("Kanał RSS/Atom nie zawiera pozycji (albo to nie jest kanał).")
    out = []
    for it in items[: ctx.want(source)]:
        if ctx.done(out):
            break
        if canonical(it["url"]) in ctx.known_urls:
            continue
        if p.get("fetch_full_text", True):
            rec = _fetch_article(ctx, source, it["url"], title=it["title"], date=it["date"], fallback_text=it["summary"])
        elif len(it["summary"]) >= 40:
            rec = make_record(source, url=it["url"], title=it["title"], text=it["summary"], published_at=it["date"])
        else:
            rec = None
        if rec:
            out.append(rec)
    return out


def _sitemap_urls(ctx: Ctx, source: dict, sitemap_url: str, depth: int = 0) -> list[tuple[str, str]]:
    _, body, _ = _get(ctx, source, sitemap_url, max_bytes=XML_MAX_BYTES, accept="application/xml,text/xml;q=0.9,*/*;q=0.5")
    kind, entries = parse_sitemap(body)
    if kind == "urlset" or depth >= 1:
        return entries
    # sitemap index: follow the 3 most recently modified child sitemaps
    children = sorted(entries, key=lambda e: e[1] or "", reverse=True)[:3]
    out: list[tuple[str, str]] = []
    for loc, _ in children:
        try:
            out += _sitemap_urls(ctx, source, loc, depth + 1)
        except FetchError as e:
            ctx.notes.append(f"pominięto mapę {loc}: {e}")
    return out


def fetch_sitemap(source: dict, ctx: Ctx) -> list[dict]:
    p = source["params"]
    rx = re.compile(p["url_regex"]) if p.get("url_regex") else None
    entries = [(u, m) for u, m in _sitemap_urls(ctx, source, p["sitemap_url"]) if not rx or rx.search(u)]
    if not entries:
        raise FetchError("Mapa strony nie zawiera adresów pasujących do url_regex.")
    # newest first when lastmod is present (stable sort keeps document order otherwise)
    entries.sort(key=lambda e: e[1] or "", reverse=True)
    out = []
    for u, lastmod in entries[: ctx.want(source)]:
        if ctx.done(out):
            break
        if canonical(u) in ctx.known_urls:
            continue
        rec = _fetch_article(ctx, source, u, date=None, min_chars=200)
        if rec:
            rec["published_at"] = rec["published_at"] or to_date(lastmod)
            out.append(rec)
    return out


_CHROME_RX = re.compile(r"menu|nav|footer|breadcrumb|header|sidebar|cookie", re.I)


def _in_chrome(a) -> bool:
    """Link sits in page chrome (navigation, header, footer, sidebar) rather than in the content."""
    for anc in a.iterancestors():
        if anc.tag in ("nav", "header", "footer", "aside"):
            return True
        if _CHROME_RX.search(f"{anc.get('class', '')} {anc.get('id', '')} {anc.get('role', '')}"):
            return True
    return False


def extract_links(page_url: str, html: str, content_only: bool = False) -> list[str]:
    import lxml.html

    try:
        doc = lxml.html.fromstring(html)
    except Exception:  # noqa: BLE001
        return []
    doc.make_links_absolute(page_url, resolve_base_href=True)
    seen: dict[str, None] = {}
    for a in doc.iter("a"):
        href = (a.get("href") or "").strip()
        if href.startswith(("http://", "https://")) and not (content_only and _in_chrome(a)):
            seen.setdefault(canonical(href), None)
    return list(seen)


def fetch_html_list(source: dict, ctx: Ctx) -> list[dict]:
    p = source["params"]
    rx = re.compile(p["link_regex"])
    lists = {canonical(u) for u in p["list_urls"]}
    links: list[str] = []
    for lu in p["list_urls"]:
        try:
            final, body, ctype = _get(ctx, source, lu)
        except Protected:
            raise
        except FetchError as e:
            ctx.notes.append(f"lista {lu}: {e}")
            continue
        for u in extract_links(final, _decode(body, ctype)):
            if rx.search(u) and u not in lists and u not in links:
                links.append(u)
    if not links:
        raise FetchError("Na stronach listy nie znaleziono linków pasujących do link_regex.")
    out = []
    for u in links[: ctx.want(source)]:
        if ctx.done(out):
            break
        if u in ctx.known_urls:
            continue
        rec = _fetch_article(ctx, source, u, min_chars=int(p.get("min_text_chars") or 300))
        if rec:
            out.append(rec)
    return out


def fetch_govpl_list(source: dict, ctx: Ctx) -> list[dict]:
    """gov.pl news listing (markup parsed with ingest/official_govpl.py: parse_listing + parse_article)."""
    gp = ingest_module("official_govpl")
    p = source["params"]
    want = ctx.want(source)
    base = p["list_url"].split("?")[0].rstrip("/")
    items: list[dict] = []
    for page in range(1, 2 + want // 10):
        url = base if page == 1 else f"{base}?page={page}&size=10"
        _, body, ctype = _get(ctx, source, url)
        got = gp.parse_listing(_decode(body, ctype))
        new = [it for it in got if it["href"] not in {x["href"] for x in items}]
        if not new:
            break
        items += new
        if len(items) >= want:
            break
    if not items:
        raise FetchError("Nie rozpoznano listy aktualności gov.pl na tej stronie (zmieniony układ?).")
    out = []
    for it in items[:want]:
        if ctx.done(out):
            break
        url = urljoin(gp.BASE + "/", it["href"])
        if canonical(url) in ctx.known_urls:
            continue
        try:
            final, body, ctype = _get(ctx, source, url)
        except Protected:
            raise
        except FetchError as e:
            ctx.notes.append(f"pominięto {url}: {e}")
            continue
        html = _decode(body, ctype)
        a = gp.parse_article(html)
        intro, text = a.get("intro") or it.get("intro") or "", a.get("body") or ""
        if intro and text.startswith(intro[:80]):
            intro = ""
        text = (intro + "\n" + text).strip()
        if len(text) < 200:
            text = extract_article(final, html)["text"] or text
        if len(text) < 80:
            ctx.notes.append(f"pominięto {url}: za mało tekstu")
            continue
        out.append(make_record(source, url=url, title=a.get("title") or it["title"], text=text,
                               published_at=a.get("date") or it.get("date"), tags=["gov.pl"]))
    return out


def fetch_custom(source: dict, ctx: Ctx) -> list[dict]:
    handler = source["params"]["handler"]
    try:
        mod = importlib.import_module(f"prawdowid.source_handlers.{handler}")
    except ImportError as e:
        raise FetchError(f"Brak modułu obsługi prawdowid.source_handlers.{handler} ({e}).") from e
    if not hasattr(mod, "fetch"):
        raise FetchError(f"Moduł prawdowid.source_handlers.{handler} nie ma funkcji fetch(source).")
    src = json.loads(json.dumps(source))
    if ctx.limit:
        src["params"]["max_items"] = ctx.limit
    src["_known_urls"] = sorted(ctx.known_urls)[:5000]  # handlers may skip already-stored pages
    # A handler may declare EXPECTED_ERRORS (e.g. "brak tokenu"): shown as a plain status message, no traceback.
    expected = tuple(getattr(mod, "EXPECTED_ERRORS", ()) or ())
    try:
        raw = mod.fetch(src) or []
    except FetchError:
        raise
    except expected as e:  # type: ignore[misc]
        raise FetchError(str(e)) from e
    out, bad = [], 0
    for r in raw:
        rec = normalize_record(r, source)
        if rec:
            out.append(rec)
        else:
            bad += 1
    if bad:
        ctx.notes.append(f"{bad} rekordów z modułu obsługi odrzucono (brak url/tekstu lub zły schemat)")
    return out[: ctx.limit] if ctx.limit else out


def legacy_python(script: str) -> str:
    name = Path(script).name
    for venv, prefix in ((".venv_official", "official_"), (".venv", "harvest_")):
        py = INGEST_DIR / venv / "bin" / "python"
        if name.startswith(prefix) and py.exists():
            return str(py)
    return sys.executable


def run_legacy_script(source: dict) -> str:
    """Run the existing ingest script (it rewrites data/corpus/<id>.jsonl itself). Returns the log tail."""
    p = source["params"]
    script = settings.root / p["script"]
    cmd = [legacy_python(p["script"]), "-W", "ignore", script.name, *[str(a) for a in p.get("args") or []]]
    try:
        r = subprocess.run(cmd, cwd=INGEST_DIR, capture_output=True, text=True, timeout=int(p.get("timeout_s") or 3600))
    except subprocess.TimeoutExpired as e:
        raise FetchError(f"Skrypt {p['script']} przekroczył limit czasu ({e.timeout} s).") from e
    tail = (r.stderr or r.stdout or "").strip().splitlines()[-3:]
    if r.returncode != 0:
        raise FetchError(f"Skrypt {p['script']} zakończył się błędem (kod {r.returncode}): " + " | ".join(tail)[-400:])
    return " | ".join(tail)[-400:]


METHOD_FN = {"rss": fetch_rss, "sitemap": fetch_sitemap, "html_list": fetch_html_list,
             "govpl_list": fetch_govpl_list, "custom": fetch_custom}


# ------------------------------------------------------------------ corpus file
def read_corpus(source_id: str) -> list[dict]:
    p = registry.corpus_path(source_id)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def merge_into_corpus(source: dict, records: list[dict]) -> tuple[int, int]:
    """Merge new records into data/corpus/<id>.jsonl: dedupe by id and url, newest first, cap at max_docs.
    Atomic write (tmp + rename) so a concurrent index load sees either the old or the new file."""
    import os

    existing = read_corpus(source["id"])
    old_ids = {r.get("id") for r in existing}
    seen_ids, seen_urls, merged = set(), set(), []
    for r in records + existing:
        u = canonical(r.get("url") or "")
        if r.get("id") in seen_ids or u in seen_urls:
            continue
        seen_ids.add(r.get("id"))
        seen_urls.add(u)
        merged.append(r)
    merged.sort(key=lambda r: (r.get("published_at") or "", r.get("retrieved_at") or ""), reverse=True)
    cap = int(source.get("params", {}).get("max_docs") or registry.DEFAULT_MAX_DOCS)
    merged = merged[:cap]
    n_new = sum(1 for r in merged if r.get("id") not in old_ids)
    path = registry.corpus_path(source["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in merged:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return n_new, len(merged)


def fetch_source(source: dict, ctx: Ctx) -> list[dict]:
    """Records for a source (no writing). legacy_script/no-op methods are handled by the caller."""
    fn = METHOD_FN.get(source.get("method"))
    if not fn:
        raise FetchError(f"Metoda {source.get('method')} nie pobiera dokumentów samodzielnie.")
    return fn(source, ctx)


def test_source(source: dict, n: int = 3) -> dict:
    """Dry run: up to n sample records, nothing is written."""
    t0 = time.time()
    method = source.get("method")
    ctx = Ctx(limit=n)
    res: dict = {"ok": True, "method": method, "records": [], "notes": ctx.notes}
    try:
        if method in registry.NOOP_METHODS:
            res["notes"].append("Ta metoda nie pobiera dokumentów według harmonogramu (źródło służy jako zaufany link "
                                "lub do wyszukiwania na żywo) — nie ma czego testować.")
        elif method == "legacy_script":
            res["records"] = read_corpus(source["id"])[:n]
            res["notes"].append("Metoda legacy_script: test nie uruchamia skryptu (trwa kilka minut i nadpisuje plik); "
                                "pokazujemy ostatnie rekordy z pliku korpusu.")
        else:
            res["records"] = fetch_source(source, ctx)[:n]
            if not res["records"]:
                res["ok"] = False
                res["notes"].append("Nie udało się uzyskać żadnego dokumentu — sprawdź parametry.")
    except FetchError as e:
        res.update(ok=False, error=str(e))
    except Exception as e:  # noqa: BLE001 — shown to the admin, never crashes the panel
        log.exception("test failed")
        res.update(ok=False, error=f"Nieoczekiwany błąd: {type(e).__name__}: {e}")
    res["pages_fetched"] = ctx.pages
    res["elapsed_s"] = round(time.time() - t0, 1)
    for r in res["records"]:
        r["text_chars"] = len(r.get("text") or "")
        r["text"] = (r.get("text") or "")[:600]
    return res


# ------------------------------------------------------------------ auto-detect for admins
GOV_LICENSE = "CC BY-SA 4.0 — treści gov.pl (gov.pl/web/gov/warunki-korzystania); podać źródło"
EU_LICENSE = "© Unia Europejska, CC BY 4.0 (informacja prawna Komisji Europejskiej); podać źródło"
_SKIP_EXT = re.compile(r"\.(pdf|jpe?g|png|gif|svg|webp|zip|docx?|xlsx?|pptx?|mp[34]|avi|rss|xml|css|js)$", re.I)


def _slugish(seg: str) -> bool:
    return (seg.count("-") >= 2 and len(seg) >= 20) or bool(re.search(r"\d{3,}", seg) and re.search(r"[a-z]", seg, re.I))


def guess_link_regex(page_url: str, links: list[str]) -> tuple[str | None, list[str]]:
    """Heuristic: article links share a parent path and end in a long slug or a numeric id."""
    host = urlsplit(page_url).netloc.lower()
    page = canonical(page_url)
    groups: dict[str, list[str]] = defaultdict(list)
    for u in links:
        p = urlsplit(u)
        if p.netloc.lower() != host or u == page or _SKIP_EXT.search(p.path) or p.query:
            continue
        segs = [s for s in p.path.split("/") if s]
        if not segs or not _slugish(segs[-1]):
            continue
        groups["/" + "/".join(segs[:-1])].append(u)
    if not groups:
        return None, []
    parent, members = max(groups.items(), key=lambda kv: (len(kv[1]), len(kv[0])))
    if len(members) < 3:
        return None, members
    scheme = urlsplit(page_url).scheme
    prefix = f"{scheme}://{host}{parent.rstrip('/')}/"
    return "^" + re.escape(prefix).replace(r"\-", "-") + r"[^/?#]+/?$", members


def _suggest_id(url: str) -> str:
    p = urlsplit(url)
    host = (p.hostname or "").lower().removeprefix("www.")
    segs = [s for s in p.path.split("/") if s]
    if host == "gov.pl" and segs[:1] == ["web"]:
        base = "govpl_" + "_".join(segs[1:3])
    else:
        base = host.rsplit(".", 1)[0] + ("_" + "_".join(segs[:2]) if segs else "")
    s = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")
    s = s[:48].strip("_")
    return s if registry.ID_RE.match(s) else ("zrodlo_" + s).strip("_")[:48] if s else "nowe_zrodlo"


def suggest_config(url: str) -> dict:
    """Detect a fetch method for a page: gov.pl listing -> RSS (link rel=alternate) -> sitemap -> html_list."""
    checked: list[dict] = []
    try:
        url = check_public_url(url)
    except (UnsafeURL, ResolveError) as e:
        return {"ok": False, "error": str(e), "checked": checked}
    ctx = Ctx()
    src_stub = {"id": "auto", "params": {}}
    try:
        final, body, ctype = http_get(url)
    except FetchError as e:
        return {"ok": False, "error": str(e), "checked": checked}
    html = _decode(body, ctype)
    import lxml.html

    try:
        doc = lxml.html.fromstring(html)
    except Exception:  # noqa: BLE001
        doc = None
    meta = lambda prop: (doc.xpath(f'string(//meta[@property="{prop}" or @name="{prop}"]/@content)') if doc is not None else "")  # noqa: E731
    title = (meta("og:title") or (doc.findtext(".//title") if doc is not None else "") or "").strip()
    site = (meta("og:site_name") or "").strip()
    host = (urlsplit(final).hostname or "").lower()
    is_gov = host == "gov.pl" or host.endswith(".gov.pl")
    is_eu = host.endswith("europa.eu")
    lang = ((doc.get("lang") if doc is not None else "") or "pl")[:2].lower()
    parts = [x.strip() for x in re.split(r"\s+[-|–—]\s+", title) if x.strip() and "portal gov.pl" not in x.lower()]
    if site and parts and parts[0].lower() != site.lower() and site.lower() not in parts[0].lower():
        name = f"{site} — {parts[0]}"
    else:
        name = parts[0] if parts else (site or host)
    cfg: dict = {
        "id": _suggest_id(final), "name": name[:120], "publisher": site or host, "url": final,
        "category": "official" if (is_gov or is_eu) else "media", "method": "reference_only", "params": {},
        "enabled": True, "schedule_hours": 6, "web_search": True, "topics": [], "language": lang if re.match(r"^[a-z]{2}$", lang) else "pl",
        "license": GOV_LICENSE if host.endswith("gov.pl") and host in ("www.gov.pl", "gov.pl") else (EU_LICENSE if is_eu else ""),
        "qualification": ("Organ administracji publicznej — komunikaty urzędowe w zakresie swoich kompetencji (kategoria A)."
                          if is_gov else ""),
    }
    cfg["tier"] = registry.DEFAULT_TIER[cfg["category"]]
    sample: list[str] = []

    # 1. gov.pl news listing
    if host in ("www.gov.pl", "gov.pl"):
        items = ingest_module("official_govpl").parse_listing(html)
        checked.append({"method": "govpl_list", "found": len(items)})
        if len(items) >= 3:
            cfg.update(method="govpl_list", params={"list_url": final.split("?")[0], "max_items": 30})
            sample = [urljoin("https://www.gov.pl/", it["href"]) for it in items[:5]]
            return _suggestion(cfg, "Rozpoznano listę aktualności w serwisie gov.pl.", checked, sample)

    # 2. RSS / Atom advertised by <link rel="alternate">
    feeds = []
    if doc is not None:
        for ln in doc.xpath('//link[@rel="alternate"][@href]'):
            if re.search(r"rss|atom", ln.get("type") or "", re.I):
                feeds.append(urljoin(final, ln.get("href")))
    for f in feeds[:3]:
        try:
            _, fb, _ = http_get(f, max_bytes=XML_MAX_BYTES)
            items = parse_feed(fb)
        except FetchError as e:
            checked.append({"method": "rss", "url": f, "error": str(e)})
            continue
        checked.append({"method": "rss", "url": f, "found": len(items)})
        if items:
            cfg.update(method="rss", params={"feed_url": f, "max_items": 30, "fetch_full_text": True})
            return _suggestion(cfg, f"Strona wskazuje kanał RSS/Atom ({len(items)} pozycji).", checked,
                               [it["url"] for it in items[:5]])
    if not feeds:
        checked.append({"method": "rss", "found": 0, "note": "brak <link rel=alternate> z kanałem"})

    # 3. sitemap (robots.txt Sitemap: lines, else /sitemap.xml)
    link_rx, link_members = guess_link_regex(final, extract_links(final, html, content_only=True))
    if not link_rx:  # some sites wrap the whole page in a "header"/"nav"-classed container
        link_rx, link_members = guess_link_regex(final, extract_links(final, html))
    page_rx = "^" + re.escape(canonical(final).rstrip("/") + "/").replace(r"\-", "-") + r"[^?#]+$"
    for sm in (robots_sitemaps(final) or [_origin(final) + "/sitemap.xml"])[:2]:
        try:
            entries = _sitemap_urls(ctx, src_stub, sm)
        except FetchError as e:
            checked.append({"method": "sitemap", "url": sm, "error": str(e)})
            continue
        urls = [canonical(u) for u, _ in entries]
        under = [u for u in urls if re.search(page_rx, u)]
        if len(under) >= 3:                       # articles live under the page the admin entered
            rx, members = page_rx, under
        elif link_rx:                             # the page's own article-link pattern, found in the sitemap
            rx, members = link_rx, [u for u in urls if re.search(link_rx, u)]
        elif urlsplit(final).path.strip("/") == "":  # site root: largest group of article-like URLs
            rx, members = guess_link_regex(final, urls)
        else:
            rx, members = None, []
        checked.append({"method": "sitemap", "url": sm, "found": len(urls), "matching": len(members)})
        if rx and len(members) >= 3:
            cfg.update(method="sitemap", params={"sitemap_url": sm, "url_regex": rx, "max_items": 30})
            return _suggestion(cfg, f"Znaleziono mapę strony ({len(urls)} adresów, {len(members)} pasuje do wzorca).",
                               checked, members[:5])

    # 4. html_list: links on the page that look like articles
    rx, members = link_rx, link_members
    checked.append({"method": "html_list", "found": len(members)})
    if rx:
        cfg.update(method="html_list", params={"list_urls": [final], "link_regex": rx, "max_items": 30,
                                                "min_text_chars": 300})
        return _suggestion(cfg, f"Na stronie jest {len(members)} linków wyglądających na artykuły.", checked, members[:5])
    cfg["schedule_hours"] = 0
    return _suggestion(cfg, "Nie wykryto listy artykułów — proponujemy reference_only (zaufany link, bez pobierania). "
                            "Można też wpisać parametry ręcznie albo użyć metody custom.", checked, sample)


def _suggestion(cfg: dict, why: str, checked: list[dict], sample: list[str]) -> dict:
    missing = [k for k in ("license", "qualification") if not cfg.get(k)]
    hint = (" Uzupełnij: " + ", ".join({"license": "licencję / warunki", "qualification": "uzasadnienie kwalifikacji"}[k]
                                       for k in missing) + ".") if missing else ""
    return {"ok": True, "config": cfg, "explanation": why + hint, "checked": checked, "sample_urls": sample,
            "exists": registry.exists(cfg["id"])}
