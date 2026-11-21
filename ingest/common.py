"""Shared helpers for Prawdowid harvesters.

- polite HTTP session (fixed User-Agent, >=1 s per-host delay, robots.txt check
  with Google-style `*` / `$` wildcard support, simple retry)
- gzip raw-page cache in data/raw/<source>/ (so re-runs do not re-hit servers)
- verdict normalisation (Polish/English labels -> true/false/misleading/mixed/unverifiable)
- JSONL writer that enforces the corpus schema
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests

UA = "PrawdowidHackathonBot/0.1 (research prototype)"
ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "data" / "corpus"
RAW_DIR = ROOT / "data" / "raw"

SCHEMA_KEYS = [
    "id", "source_type", "publisher", "domain", "url", "title", "published_at",
    "retrieved_at", "language", "license", "text", "claim", "claim_author",
    "verdict_raw", "verdict", "tags",
]
SOURCE_TYPES = {"factcheck", "incident", "official", "media"}
VERDICTS = {"true", "false", "misleading", "mixed", "unverifiable", None}
MAX_TEXT = 4000


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# --------------------------------------------------------------------------- robots
class Robots:
    """Minimal robots.txt evaluator (longest-match, Allow wins ties, * and $ wildcards)."""

    def __init__(self, text: str | None, agent: str = UA):
        self.rules: list[tuple[bool, str]] = []
        if not text:
            return
        groups: list[tuple[list[str], list[tuple[bool, str]]]] = []
        agents: list[str] = []
        rules: list[tuple[bool, str]] = []
        last_was_agent = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            if k == "user-agent":
                if not last_was_agent and (agents or rules):
                    groups.append((agents, rules))
                    agents, rules = [], []
                agents.append(v.lower())
                last_was_agent = True
            elif k in ("allow", "disallow"):
                last_was_agent = False
                if v or k == "allow":
                    rules.append((k == "allow", v))
            else:
                last_was_agent = False
        if agents or rules:
            groups.append((agents, rules))
        token = agent.split("/")[0].lower()
        specific = [r for a, r in groups if any(x != "*" and x in token for x in a)]
        generic = [r for a, r in groups if "*" in a]
        chosen = specific or generic
        for r in chosen:
            self.rules.extend(r)

    @staticmethod
    def _match(pattern: str, path: str) -> bool:
        if not pattern:
            return True
        rx = re.escape(pattern).replace(r"\*", ".*")
        if rx.endswith(r"\$"):
            rx = rx[:-2] + "$"
        return re.match(rx, path) is not None

    def allowed(self, url: str) -> bool:
        p = urlsplit(url)
        path = p.path or "/"
        if p.query:
            path += "?" + p.query
        best: tuple[int, bool] | None = None
        for allow, pat in self.rules:
            if pat and self._match(pat, path):
                cand = (len(pat), allow)
                if best is None or cand[0] > best[0] or (cand[0] == best[0] and allow):
                    best = cand
        return True if best is None else best[1]


# --------------------------------------------------------------------------- HTTP
class PoliteSession:
    def __init__(self, source: str, delay: float = 1.2, cache: bool = True, timeout: int = 40):
        self.source = source
        self.delay = max(1.0, delay)
        self.cache = cache
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "pl,en;q=0.8"})
        self._last: dict[str, float] = {}
        self._robots: dict[str, Robots] = {}
        self.raw_dir = RAW_DIR / source
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.stats = {"fetched": 0, "cached": 0, "blocked_robots": 0, "errors": 0}
        self._ok_hosts: dict[str, int] = {}

    def _wait(self, host: str):
        t = self._last.get(host)
        if t is not None:
            dt = time.monotonic() - t
            if dt < self.delay:
                time.sleep(self.delay - dt)
        self._last[host] = time.monotonic()

    def robots(self, url: str) -> Robots:
        p = urlsplit(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            self._wait(p.netloc)
            try:
                r = self.s.get(base + "/robots.txt", timeout=self.timeout)
                txt = r.text if r.status_code == 200 else None
                if r.status_code in (401, 403):
                    # robots.txt itself forbidden -> treat whole host as disallowed
                    txt = "User-agent: *\nDisallow: /\n"
            except requests.RequestException:
                txt = None
            self._robots[base] = Robots(txt)
        return self._robots[base]

    def _cache_path(self, url: str) -> Path:
        h = hashlib.sha1(url.encode()).hexdigest()[:20]
        return self.raw_dir / f"{h}.gz"

    def is_cached(self, url: str, params: dict | None = None) -> bool:
        full = requests.Request("GET", url, params=params).prepare().url
        return self._cache_path(full).exists()

    def get(self, url: str, params: dict | None = None, use_cache: bool | None = None,
            headers: dict | None = None) -> str | None:
        full = requests.Request("GET", url, params=params).prepare().url
        use_cache = self.cache if use_cache is None else use_cache
        cp = self._cache_path(full)
        if use_cache and cp.exists():
            self.stats["cached"] += 1
            return gzip.decompress(cp.read_bytes()).decode("utf-8", "replace")
        if not self.robots(full).allowed(full):
            self.stats["blocked_robots"] += 1
            log(f"[robots] disallowed: {full}")
            return None
        host = urlsplit(full).netloc
        for attempt in range(3):
            self._wait(host)
            try:
                r = self.s.get(full, timeout=self.timeout, headers=headers)
            except requests.RequestException as e:
                log(f"[err] {full}: {e}")
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code == 200:
                self.stats["fetched"] += 1
                self._ok_hosts[host] = self._ok_hosts.get(host, 0) + 1
                r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
                txt = r.text
                if use_cache:
                    cp.write_bytes(gzip.compress(txt.encode("utf-8")))
                return txt
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code == 403 and self._ok_hosts.get(host, 0) > 0 and attempt == 0:
                # host served us fine before -> likely rate limiting (e.g. Cloudflare): back off once
                self.delay = min(self.delay * 1.5, 10.0)
                log(f"[http 403] {full} -> backing off 60 s, delay now {self.delay:.1f}s")
                time.sleep(60)
                continue
            log(f"[http {r.status_code}] {full}")
            break
        self.stats["errors"] += 1
        return None


# --------------------------------------------------------------------------- verdicts
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("ł", "l").strip(" .!:- ")


_VERDICT_RULES: list[tuple[str, str | None]] = [
    # order matters: more specific first
    ("czesciowa prawda", "mixed"), ("czesciowo prawda", "mixed"), ("czesciowy falsz", "mixed"),
    ("czesciowo falsz", "mixed"), ("polprawda", "mixed"), ("mostly true", "mixed"),
    ("partly false", "mixed"), ("partially false", "mixed"), ("half true", "mixed"), ("mixed", "mixed"),
    ("nieweryfikowal", "unverifiable"), ("unverifiable", "unverifiable"), ("niesprawdzal", "unverifiable"),
    ("brak dowodow", "unverifiable"), ("sie zweryfikowac", "unverifiable"), ("insufficient evidence", "unverifiable"),
    ("w wiekszosci", "mixed"),
    ("manipulac", "misleading"), ("wprowadza w blad", "misleading"), ("wprowadzajac", "misleading"),
    ("brak kontekstu", "misleading"), ("brakujacy kontekst", "misleading"), ("brakuje kontekstu", "misleading"), ("bez kontekstu", "misleading"), ("missing context", "misleading"),
    ("misleading", "misleading"), ("przesad", "misleading"), ("wyrwan", "misleading"),
    ("zmanipulowan", "false"), ("przerobion", "false"), ("wygenerowan", "false"), ("deepfake", "false"),
    ("przerobk", "false"), ("nieprawdziw", "false"), ("falszyw", "false"), ("falsz", "false"), ("fake", "false"), ("nieprawda", "false"),
    ("disinformation", "false"), ("dezinformac", "false"), ("false", "false"), ("oszustwo", "false"),
    ("scam", "false"), ("altered", "false"),
    ("prawda", "true"), ("prawdziw", "true"), ("true", "true"), ("correct", "true"),
]


def clean_label(raw: str | None) -> str | None:
    """Trim a verdict label: drop trailing dot; if a whole sentence was put in the rating field,
    keep only its first clause (e.g. 'Fałsz. Polska nie kupiła…' -> 'Fałsz')."""
    if not raw:
        return None
    s = clean_text(raw).strip()
    if len(s) > 60:
        s = re.split(r"[.:;!?]\s", s, maxsplit=1)[0]
        if len(s) > 60:
            s = s[:60].rsplit(" ", 1)[0] + " …"
    s = s.rstrip(". ")
    return (s[0].upper() + s[1:]) if s else None


def map_verdict(raw: str | None) -> str | None:
    if not raw:
        return None
    n = _norm(raw)
    if any(x in n for x in ("satyr", "satire", "wyjasniamy", "explain")):
        return None
    for key, val in _VERDICT_RULES:
        if key in n:
            return val
    return None


# --------------------------------------------------------------------------- text utils
_WS = re.compile(r"[ \t ]+")


def clean_text(s: str | None) -> str:
    if not s:
        return ""
    s = s.replace("\r", "")
    s = _WS.sub(" ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return "\n".join(line.strip() for line in s.split("\n") if line.strip())


def clip(s: str | None, n: int = MAX_TEXT) -> str:
    s = clean_text(s)
    if len(s) <= n:
        return s
    cut = s[: n - 4]
    sp = max(cut.rfind(". "), cut.rfind("\n"))
    if sp > n * 0.6:
        cut = cut[: sp + 1]
    return cut.rstrip() + " […]"


def iso_date(s: str | None) -> str | None:
    if not s:
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None


def jsonld_blocks(html: str) -> list:
    out = []
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            d = json.loads(m.group(1).strip())
        except Exception:
            continue
        stack = [d]
        while stack:
            x = stack.pop()
            if isinstance(x, list):
                stack.extend(x)
            elif isinstance(x, dict):
                out.append(x)
                if "@graph" in x:
                    stack.extend(x["@graph"] if isinstance(x["@graph"], list) else [x["@graph"]])
    return out


# --------------------------------------------------------------------------- output
def normalize_record(rec: dict) -> dict:
    """Enforce the corpus schema on one record (key set, enums, clipped text, cleaned verdict label)."""
    rec = {k: rec.get(k) for k in SCHEMA_KEYS}
    assert rec["source_type"] in SOURCE_TYPES, rec["source_type"]
    assert rec["verdict"] in VERDICTS, rec["verdict"]
    assert rec["id"] and rec["url"] and rec["title"], rec
    rec["tags"] = [t for t in dict.fromkeys(rec.get("tags") or []) if t]
    if rec["text"]:
        rec["text"] = clip(rec["text"], MAX_TEXT)
    if rec["verdict_raw"] and not rec["verdict_raw"].startswith("Disinformation"):
        full = rec["verdict_raw"]
        rec["verdict_raw"] = clean_label(full)
        if rec["verdict"] is None:
            rec["verdict"] = map_verdict(rec["verdict_raw"]) or map_verdict(full)
    return rec


class JsonlWriter:
    def __init__(self, source: str):
        CORPUS_DIR.mkdir(parents=True, exist_ok=True)
        self.path = CORPUS_DIR / f"{source}.jsonl"
        self.tmp = self.path.with_suffix(".jsonl.tmp")
        self.f = self.tmp.open("w", encoding="utf-8")
        self.ids: set[str] = set()
        self.n = 0

    def write(self, rec: dict) -> bool:
        rec = normalize_record(rec)
        if rec["id"] in self.ids:
            return False
        self.ids.add(rec["id"])
        self.f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.n += 1
        return True

    def close(self):
        self.f.close()
        self.tmp.replace(self.path)
        log(f"[done] wrote {self.n} records -> {self.path}")


def sitemap_urls(xml: str | None) -> list[str]:
    if not xml:
        return []
    return [u.strip() for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)]


def sitemap_entries(xml: str | None) -> list[tuple[str, str | None]]:
    """(loc, lastmod) pairs of a sitemap, in document order. lastmod may be None."""
    if not xml:
        return []
    out = []
    for m in re.finditer(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", m.group(1))
        if loc:
            lm = re.search(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", m.group(1))
            out.append((loc.group(1), lm.group(1) if lm else None))
    return out


# --------------------------------------------------------------------------- incremental corpus files
class IncrementalCorpus:
    """Append-only view of data/corpus/<source>.jsonl for incremental harvesters.

    Existing records are kept verbatim (a run never shrinks the file), new records are merged in, and the file is
    rewritten atomically (tmp + rename) at checkpoints and at the end, so an interrupted/timed-out run keeps what it
    already saved and a concurrent index load sees either the old or the new file, never a partial one.
    """

    def __init__(self, source: str, path: Path | None = None):
        self.path = path or CORPUS_DIR / f"{source}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records: list[dict] = []
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        self.records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        self.n_existing = len(self.records)
        self.ids = {r.get("id") for r in self.records}
        self.urls = {canonical_url(r.get("url") or "") for r in self.records}
        self.n_new = 0
        self._unsaved = 0

    def has_url(self, url: str) -> bool:
        return canonical_url(url) in self.urls

    def add(self, rec: dict) -> bool:
        rec = normalize_record(rec)
        if rec["id"] in self.ids or canonical_url(rec["url"]) in self.urls:
            return False
        self.records.append(rec)
        self.ids.add(rec["id"])
        self.urls.add(canonical_url(rec["url"]))
        self.n_new += 1
        self._unsaved += 1
        return True

    def save(self, force: bool = False) -> None:
        if not (self._unsaved or force):
            return
        # newest first; records without a date go last; stable for equal dates
        recs = sorted(self.records, key=lambda r: r.get("published_at") or "", reverse=True)
        tmp = self.path.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        tmp.replace(self.path)
        self._unsaved = 0
        log(f"[saved] {len(recs)} records ({self.n_existing} before, +{self.n_new} new) -> {self.path}")


def canonical_url(url: str) -> str:
    u = url.strip().split("#", 1)[0]
    u = re.sub(r"^http://", "https://", u)
    return u.rstrip("/")


class RunLock:
    """Non-blocking per-source lock (data/runtime/harvest_<source>.lock): a second concurrent run of the same
    harvester (CLI + scheduler) exits instead of hitting the site twice and racing on the corpus file."""

    def __init__(self, source: str):
        self.path = ROOT / "data" / "runtime" / f"harvest_{source}.lock"
        self.fh = None

    def __enter__(self) -> bool:
        import fcntl
        import signal

        # SIGTERM (e.g. a stopped scheduler/CLI) -> KeyboardInterrupt, so `finally: corpus.save()` still runs
        try:
            signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
        except ValueError:  # not in the main thread
            pass

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.path, "w")
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.fh.close()
            self.fh = None
            return False
        return True

    def __exit__(self, *exc):
        if self.fh:
            self.fh.close()
        return False
