"""Shared helpers for the official-source harvesters (ingest/official_*.py).

Politeness rules enforced here:
  * fixed User-Agent "PrawdowidHackathonBot/0.1 (research prototype)"
  * robots.txt checked per host (urllib.robotparser) before every fetch
  * per-host minimum delay (default 1.2 s, raised to Crawl-delay when declared)
  * small retry with back-off on 429/5xx

Every harvester writes JSONL with the exact corpus schema (see make_record).
"""
from __future__ import annotations

import datetime as dt
import gzip
import html as htmllib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path

UA = "PrawdowidHackathonBot/0.1 (research prototype)"
ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "data" / "corpus"
MAX_TEXT = 4000
DEFAULT_DELAY = 1.2

_last_hit: dict[str, float] = {}
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_host_delay: dict[str, float] = {}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today() -> str:
    return dt.date.today().isoformat()


class RobotsDisallowed(Exception):
    pass


def _robots_for(url: str):
    p = urllib.parse.urlsplit(url)
    host = f"{p.scheme}://{p.netloc}"
    if host in _robots:
        return _robots[host]
    rp = urllib.robotparser.RobotFileParser()
    rurl = host + "/robots.txt"
    try:
        req = urllib.request.Request(rurl, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode("utf-8", "replace")
            # robots served as HTML (e.g. SPA fallback) -> treat as no rules
            if "<html" in body[:500].lower():
                body = ""
        rp.parse(body.splitlines())
        cd = rp.crawl_delay(UA)
        if cd:
            _host_delay[p.netloc] = max(float(cd), DEFAULT_DELAY)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            rp.disallow_all = True
        else:
            rp.allow_all = True
    except Exception:
        rp = None  # network issue: be permissive but keep delays
    _robots[host] = rp
    return rp


def allowed(url: str) -> bool:
    rp = _robots_for(url)
    return True if rp is None else rp.can_fetch(UA, url)


def _wait(netloc: str, min_delay: float):
    d = max(min_delay, _host_delay.get(netloc, DEFAULT_DELAY))
    last = _last_hit.get(netloc, 0.0)
    gap = time.time() - last
    if gap < d:
        time.sleep(d - gap)
    _last_hit[netloc] = time.time()


def fetch(url: str, *, accept: str | None = None, headers: dict | None = None,
          min_delay: float = DEFAULT_DELAY, retries: int = 3, check_robots: bool = True,
          timeout: int = 60) -> bytes:
    """GET with UA, robots check, per-host delay and back-off. Returns raw bytes."""
    if check_robots and not allowed(url):
        raise RobotsDisallowed(url)
    netloc = urllib.parse.urlsplit(url).netloc
    h = {"User-Agent": UA, "Accept-Encoding": "gzip"}
    if accept:
        h["Accept"] = accept
    if headers:
        h.update(headers)
    err = None
    for attempt in range(retries):
        _wait(netloc, min_delay)
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    data = gzip.decompress(data)
                return data
        except urllib.error.HTTPError as e:
            err = e
            if e.code in (429, 500, 502, 503, 504):
                back = 5 * (attempt + 1) * (3 if e.code == 429 else 1)
                log(f"  HTTP {e.code} {url} -> retry in {back}s")
                time.sleep(back)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            err = e
            time.sleep(3 * (attempt + 1))
    raise err  # type: ignore[misc]


def fetch_text(url: str, **kw) -> str:
    return fetch(url, **kw).decode("utf-8", "replace")


def fetch_json(url: str, **kw):
    kw.setdefault("accept", "application/json")
    return json.loads(fetch(url, **kw).decode("utf-8-sig"))


def pdf_to_text(data: bytes, layout: bool = False) -> str:
    """Extract text from PDF bytes using poppler's pdftotext (no Python deps)."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        try:
            cmd = ["pdftotext"] + (["-layout"] if layout else []) + ["-enc", "UTF-8", f.name, "-"]
            out = subprocess.run(cmd, capture_output=True, timeout=120)
            return out.stdout.decode("utf-8", "replace")
        except Exception as e:  # pragma: no cover
            log("pdftotext failed:", e)
            return ""


_ws = re.compile(r"[ \t ]+")


def clean_ws(s: str) -> str:
    s = htmllib.unescape(s or "")
    s = s.replace("\r", "")
    s = _ws.sub(" ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def html_to_text(fragment: str) -> str:
    """Cheap HTML -> text with paragraph breaks (no external deps)."""
    s = re.sub(r"(?is)<(script|style|noscript|svg|picture).*?</\1>", " ", fragment or "")
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|li|h[1-6]|tr|blockquote|section|article)>", "\n", s)
    s = re.sub(r"(?i)<li[^>]*>", "\n- ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return clean_ws(s)


def truncate(s: str, n: int = MAX_TEXT) -> str:
    s = s.strip()
    if len(s) <= n:
        return s
    n -= 4  # room for the " […]" marker so the result is always <= MAX_TEXT
    cut = s[:n]
    # cut at last sentence/paragraph boundary when reasonably close
    m = max(cut.rfind(". "), cut.rfind("\n"))
    if m > n * 0.7:
        cut = cut[: m + 1]
    return cut.rstrip() + " […]"


def pl_date(s: str | None) -> str | None:
    """'16.11.2026' / '2026-11-16' / RFC822 -> 'YYYY-MM-DD'."""
    if not s:
        return None
    s = s.strip()
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        d, mo, y = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return "-".join(m.groups())
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).date().isoformat()
    except Exception:
        return None


def make_record(*, source: str, sid: str, publisher: str, url: str, title: str,
                text: str, published_at: str | None, license: str, tags: list[str],
                domain: str | None = None, language: str = "pl") -> dict:
    """Build a record with EXACTLY the corpus schema (key order preserved)."""
    if domain is None:
        netloc = urllib.parse.urlsplit(url).netloc.lower()
        domain = netloc[4:] if netloc.startswith("www.") else netloc
    return {
        "id": f"{source}:{sid}",
        "source_type": "official",
        "publisher": publisher,
        "domain": domain,
        "url": url,
        "title": clean_ws(title)[:400],
        "published_at": published_at,
        "retrieved_at": now_iso(),
        "language": language,
        "license": license,
        "text": truncate(text),
        "claim": None,
        "claim_author": None,
        "verdict_raw": None,
        "verdict": None,
        "tags": sorted(set(t for t in tags if t)),
    }


class JsonlWriter:
    """Writes records atomically (tmp file + rename); de-duplicates by id."""

    def __init__(self, name: str):
        CORPUS_DIR.mkdir(parents=True, exist_ok=True)
        self.path = CORPUS_DIR / f"official_{name}.jsonl"
        self.tmp = self.path.with_suffix(".jsonl.tmp")
        self.f = open(self.tmp, "w", encoding="utf-8")
        self.ids: set[str] = set()
        self.n = 0

    def write(self, rec: dict):
        if rec["id"] in self.ids or not rec["text"].strip():
            return False
        self.ids.add(rec["id"])
        self.f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.n += 1
        return True

    def close(self):
        self.f.close()
        os.replace(self.tmp, self.path)
        log(f"[ok] {self.path.relative_to(ROOT)}: {self.n} records")

    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if et is None:
            self.close()
        else:
            self.f.close()
            log(f"[err] {et.__name__}: {ev} — partial output kept in {self.tmp}")
        return False


def fmt_num(x, decimals: int | None = None) -> str:
    """Polish number formatting: 1 234 567,8"""
    if x is None:
        return "b.d."
    if isinstance(x, str):
        try:
            x = float(x.replace(",", "."))
        except ValueError:
            return x
    if decimals is None:
        decimals = 0 if float(x).is_integer() else 1
    s = f"{x:,.{decimals}f}"
    return s.replace(",", " ").replace(".", ",")


PL_MONTHS = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień",
             "wrzesień", "październik", "listopad", "grudzień"]
PL_MONTHS_LOC = ["styczniu", "lutym", "marcu", "kwietniu", "maju", "czerwcu", "lipcu", "sierpniu",
                 "wrześniu", "październiku", "listopadzie", "grudniu"]
