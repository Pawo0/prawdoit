"""Live stage: Google Fact Check Tools API + search restricted to trusted (whitelisted) domains.

Used by service.run_check. Two providers:

1. **Google Fact Check Tools API** (`claims:search`, languageCode=pl, key in `PRAWDOWID_GOOGLE_FACTCHECK_KEY`).
   Called for every factual claim when the key is set (short timeout, in-memory cache): one general query plus one
   per fact-checker site listed in `params.publisher_sites` of data/sources/google_factcheck.json (Demagog), sent
   with `reviewPublisherSiteFilter` — this is the API route to Demagog's reviews. Only reviews published on a
   domain from the source registry become evidence (the Polish part of Google's ClaimReview index also contains SEO
   spam — see ingest/harvest_claimreview_feed.py); others are only counted. Missing key = silently inactive.

2. **Trusted-domain web search**, used only when the corpus (and Google) produced no usable evidence for a factual
   claim. Allowed domains = hosts of `data/sources/*.json` entries with `enabled` and `web_search` true (small
   hardcoded fallback when the registry is empty). Results are fetched with the SSRF-safe `fetch.fetch_url`, scanned
   for prompt injection (`security.scan` / `neutralize` — fetched pages are untrusted data) and become SourceDoc
   records tagged `live_search`; the engine then applies exactly the same rules (verbatim quote gate, NLI, R1–R6).
   A domain alone never decides anything: a page must contain a passage that supports/refutes the claim.

Provider choice for the keyless default (decided 2026-11-21): **site-native search endpoints of the whitelisted
sites themselves** (provider `sitesearch`):
  * gov.pl — the JSON endpoint behind the public search page www.gov.pl/web/gov/szukaj (`/api/data/search`);
    www.gov.pl/robots.txt: `User-Agent: * / Allow: /`.
  * WordPress sites (demagog.org.pl, fakenews.pl, checkfirst.network) — the public WordPress REST search
    `/wp-json/wp/v2/search`; their robots.txt allows it.
  Why: results are on the whitelist by construction, the function is offered publicly by the operator, no API key,
  no third party sees the user's question, and robots.txt is checked (cached) before every request and fetch.
  Rejected: DuckDuckGo HTML — duckduckgo.com/robots.txt has `Disallow: /html` and `Disallow: /lite` for all agents and
  the service blocks automated clients with a CAPTCHA (we never circumvent protections); Odyseusz (odyseusz.gov.pl)
  is a SPA with a private, credentialed API and no public search; cert.pl disallows `/szukaj/` in robots.txt.
  Optional, better recall when configured: self-hosted SearXNG (`PRAWDOWID_SEARXNG_URL`, JSON API) and Brave Search
  API (`PRAWDOWID_BRAVE_KEY`), both queried with `site:` filters and strictly post-filtered on the whitelist.

Failures are never verdicts: an error/timeout yields a notice ("Nie mogę teraz…") and the local answer stays as it is;
every failure is logged with store.log_error. Demo/eval switches:
  PRAWDOWID_FORCE_FAIL=google_factcheck,websearch  simulate an outage (also without a key)
  PRAWDOWID_LIVE_SEARCH=0                          disable the whole live stage (reproducible eval)
Time budget for the whole live stage: LIVE_BUDGET_S (15 s); network work stops ~2 s earlier to leave time for NLI.
Search phase: hosts in parallel, each with one clock (robots.txt + query rounds) of SEARCH_TIMEOUT_S (7 s), ending
FETCH_RESERVE_S (4 s) before the deadline so the chosen pages can be fetched; a slow host returns what it has.
"""
from __future__ import annotations

import hashlib
import html as html_mod
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional
from urllib.parse import urljoin, urlparse

import httpx

from . import store
from .config import settings
from .fetch import UA, fetch_url
from .robots import RobotsTxt
from .schemas import ClaimResult, LiveSearchInfo, SecurityEvent, SourceDoc
from .security import check_public_url, neutralize, scan
from .textutil import STOP, normalize_ws, short, tokens

log = logging.getLogger("prawdowid.websearch")

LIVE_BUDGET_S = 15.0
NET_RESERVE_S = 2.0  # left for embedding + NLI of the fetched documents
GOOGLE_TIMEOUT_S = 4.0
SEARCH_TIMEOUT_S = 7.0  # per host incl. its robots.txt check, all query rounds (demagog.org.pl: 2–6 s per query)
FETCH_RESERVE_S = 4.0  # the search phase ends this much before the deadline, so the chosen pages can still be fetched
MAX_FETCH = 5
MAX_FALLBACK_CLAIMS = 2
ROBOTS_AGENT = "PrawdowidBot"
LIVE_CORPUS = settings.corpus_dir / "live_web.jsonl"
SOURCES_DIR = getattr(settings, "sources_dir", settings.root / "data" / "sources")

# ---------------------------------------------------------------- progress stages (plain Polish, reported truthfully)
STAGES: dict[str, str] = {
    "kolejka": "Czekam na wolne miejsce w kolejce…",
    "analiza": "Analizuję treść…",
    "pobieranie": "Pobieram stronę z podanego adresu…",
    "baza": "Szukam w bazie sprawdzonych informacji…",
    "internet": "Nie znalazłem w bazie — przeszukuję zaufane strony w internecie…",
    "porownanie": "Porównuję znalezione źródła…",
    "odpowiedz": "Przygotowuję odpowiedź…",
}

Progress = Optional[Callable[[str, str], None]]


def emit(progress: Progress, stage: str) -> None:
    if progress is None:
        return
    try:
        progress(stage, STAGES.get(stage, stage))
    except Exception:  # noqa: BLE001 — a broken UI callback must never break a check
        log.debug("progress callback failed", exc_info=True)


# ---------------------------------------------------------------- switches (read at call time: demo can toggle env)
def _env(name: str, default: str = "") -> str:
    return os.environ.get(f"PRAWDOWID_{name}", default).strip()


def live_enabled() -> bool:
    return _env("LIVE_SEARCH", "1") not in ("0", "false", "no", "off")


def forced_fail(provider: str) -> bool:
    return provider in {p.strip() for p in _env("FORCE_FAIL").split(",") if p.strip()}


class LiveError(RuntimeError):
    """Technical failure of a live provider (never a statement about the content)."""


# ---------------------------------------------------------------- source registry (read directly and tolerantly)
@dataclass(frozen=True)
class TrustedSource:
    id: str
    publisher: str
    host: str  # without "www."; subdomains are included (e.g. gov.pl covers *.gov.pl)
    url: str
    category: str  # official | factcheck | incident | media (= SourceDoc.source_type)
    tier: int
    license: str
    web_search: bool
    site_search: str = ""  # govpl | wordpress | none | "" (known default for the host)


_FALLBACK = [
    TrustedSource("gov_pl", "Serwis Rzeczypospolitej Polskiej gov.pl", "gov.pl", "https://www.gov.pl", "official", 1,
                  "CC BY-SA 4.0 — treści gov.pl (gov.pl/web/gov/warunki-korzystania); podać źródło", True),
    TrustedSource("demagog", "Demagog", "demagog.org.pl", "https://demagog.org.pl", "factcheck", 2,
                  "© Stowarzyszenie Demagog — krótkie fragmenty z podaniem źródła (prawo cytatu)", True),
    TrustedSource("fakenews_pl", "FakeNews.pl", "fakenews.pl", "https://fakenews.pl", "factcheck", 2,
                  "© fakenews.pl — krótkie fragmenty z podaniem źródła (prawo cytatu)", True),
    TrustedSource("konkret24", "Konkret24 (TVN24)", "konkret24.tvn24.pl", "https://konkret24.tvn24.pl", "factcheck", 2,
                  "© TVN S.A. — krótkie fragmenty z podaniem źródła (prawo cytatu)", True),
    TrustedSource("pravda", "Stowarzyszenie Pravda", "pravda.org.pl", "https://pravda.org.pl", "factcheck", 2,
                  "© Stowarzyszenie Pravda — krótkie fragmenty z podaniem źródła (prawo cytatu)", True),
    TrustedSource("cert", "CERT Polska (NASK)", "cert.pl", "https://cert.pl", "official", 1,
                  "© NASK / CERT Polska — krótkie fragmenty z podaniem źródła", True, "none"),
    TrustedSource("checkfirst", "CheckFirst", "checkfirst.network", "https://checkfirst.network", "incident", 3,
                  "© Check First Oy — krótkie fragmenty z podaniem źródła", True),
]
# site-native search endpoints we know to be public and robots-allowed
_KNOWN_SITE_SEARCH = {"gov.pl": "govpl", "demagog.org.pl": "wordpress", "fakenews.pl": "wordpress",
                      "checkfirst.network": "wordpress", "cert.pl": "none"}
_REG_CACHE: dict = {"key": None, "sources": []}
_TIER_BY_CAT = {"official": 1, "factcheck": 2, "incident": 3, "media": 4}


def _host(url: str) -> str:
    h = (urlparse(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def registry() -> list[TrustedSource]:
    """All enabled registry entries (any web_search value). Falls back to _FALLBACK when the dir is empty."""
    files = sorted(SOURCES_DIR.glob("*.json")) if SOURCES_DIR.exists() else []
    key = tuple((f.name, f.stat().st_mtime) for f in files)
    if key == _REG_CACHE["key"]:
        return _REG_CACHE["sources"]
    out: list[TrustedSource] = []
    parsed = 0
    for f in files:
        try:
            e = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(e, dict):
            continue
        parsed += 1
        host = _host(str(e.get("url") or ""))
        if not e.get("enabled", True) or not host or e.get("method") == "live_search":
            continue
        cat = e.get("category") if e.get("category") in _TIER_BY_CAT else "official"
        try:
            tier = int(e.get("tier") or _TIER_BY_CAT[cat])
        except (TypeError, ValueError):
            tier = _TIER_BY_CAT[cat]
        params = e.get("params") if isinstance(e.get("params"), dict) else {}
        out.append(TrustedSource(str(e.get("id") or f.stem), str(e.get("publisher") or e.get("name") or host), host,
                                 str(e.get("url")), cat, tier, str(e.get("license") or ""),
                                 bool(e.get("web_search", False)), str(params.get("site_search") or "")))
    if not parsed:
        out = list(_FALLBACK)
    _REG_CACHE.update(key=key, sources=out)
    return out


def match_source(url: str, web_search_only: bool = True) -> TrustedSource | None:
    """Registry entry covering this URL: same host or a subdomain; the entry whose URL is the longest prefix wins
    (e.g. gov.pl/web/kgpsp → KGPSP rather than the generic gov.pl entry)."""
    h = _host(url)
    if not h:
        return None
    cands = [s for s in registry() if (s.web_search or not web_search_only) and (h == s.host or h.endswith("." + s.host))]
    if not cands:
        return None
    norm = lambda u: re.sub(r"^https?://(www\.)?", "", u).rstrip("/")  # noqa: E731
    return max(cands, key=lambda s: (norm(url).startswith(norm(s.url)) * len(norm(s.url)), len(s.host), s.tier == 1))


def allowed_hosts() -> list[str]:
    hosts: dict[str, int] = {}
    for s in registry():
        if s.web_search:
            hosts[s.host] = min(hosts.get(s.host, 9), s.tier)
    return sorted(hosts, key=lambda h: (hosts[h], h))


# ---------------------------------------------------------------- HTTP helpers (SSRF-checked, robots-compliant)
_ROBOTS: dict[str, tuple[float, RobotsTxt | None]] = {}
_ROBOTS_LOCK = threading.Lock()


def _get(url: str, timeout: float, headers: dict | None = None, params: dict | None = None,
         check_ssrf: bool = True) -> httpx.Response:
    """GET with manual redirects; every hop is SSRF-checked. Raises httpx.HTTPError / UnsafeURL / ResolveError."""
    hdrs = {"User-Agent": UA, "Accept-Language": "pl,en;q=0.5"} | (headers or {})
    with httpx.Client(timeout=timeout, follow_redirects=False, headers=hdrs) as c:
        for _ in range(4):
            if check_ssrf:
                check_public_url(url)
            r = c.get(url, params=params)
            if r.is_redirect:
                url, params = urljoin(str(r.url), r.headers.get("location", "")), None
                continue
            return r
    raise LiveError("zbyt wiele przekierowań")


def robots_allowed(url: str, timeout: float = 3.0) -> bool:
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    with _ROBOTS_LOCK:
        ent = _ROBOTS.get(base)
    if ent is None or time.time() - ent[0] > 6 * 3600:
        rp: RobotsTxt | None = RobotsTxt()  # RFC 9309 longest-match (urllib.robotparser is first-match)
        try:
            r = _get(base + "/robots.txt", timeout)
            body = r.text if r.status_code == 200 else ""
            if r.status_code >= 500:
                rp = None  # server error on robots.txt: treat as "do not crawl" (RFC 9309 §2.3.1.4)
            elif "<html" in body[:500].lower():
                rp.parse([])  # SPA fallback page instead of robots.txt = no rules
            else:
                rp.parse(body.splitlines())
        except Exception:  # noqa: BLE001 — unreachable robots.txt: be conservative
            rp = None
        ent = (time.time(), rp)
        with _ROBOTS_LOCK:
            _ROBOTS[base] = ent
    return ent[1] is not None and ent[1].can_fetch(ROBOTS_AGENT, url)


# ---------------------------------------------------------------- query building
# Site search engines do not understand sentences, and they differ (probed 2026-11-21):
#   * WordPress core ANDs every term as a substring of title/excerpt/content (fakenews.pl, checkfirst.network);
#   * demagog.org.pl matches the WHOLE query as one phrase, in titles only ("Wrocław latk" → 0 hits, "Wrocław" → 75);
#   * gov.pl runs a full-text engine that ranks by any word.
# So we never send the claim itself. We pick its 2–4 most distinctive words — proper names and rare content words
# (rarity = IDF in the local corpus), never meta words ("czy Demagog sprawdzał…", fact-checker names) and only
# reluctantly verbs, which are usually paraphrased — and run several short variants in parallel: all top terms
# together (AND engines) and each top term alone (phrase/title engines). For substring engines the words are cut to
# a stem (Wrocławiu → Wrocław, 65-latkowie → latk, darmowymi → darmow), so other inflections still match. The union of
# hits is ranked locally by stem overlap between the title/snippet and the claim (_select), so whichever semantics a
# site's search has, a matching article surfaces. If the first round yields nothing relevant, the next terms are tried.
_SEARCH_STOP = set("""czy prawda prawdą nieprawda podobno ponoć słyszałem słyszałam odbył odbyła odbyło odbyły odbędzie
    zostało zostały została będą była było były jest są ma mają można mogą tylko już od wczoraj dziś dzisiaj jutro
    teraz obecnie nowy nowa nowe wszystkie wszyscy ludzie każdy około ponad prawie dlaczego czemu skąd kiedyś
    ostatnio naprawdę rzeczywiście faktycznie mln mld tys proc""".split())
# meta words: about checking, not about the topic ("Czy Demagog sprawdzał, czy…", "w analizie…", "to fałsz?")
# (matches surface words and 6-letter stems: sprawdzał/sprawd, weryfikował/weryfi, artykule/artyku)
_META_RX = re.compile(r"^(sprawd|weryfi|zweryf|analiz|przean|oceni|ocenił|fact|prawd|nieprawd|artyku|tekst|twierd|"
                      r"źródł|zrodl|tez[aęey]$|wpis$|wpisu$|post$|posta$|postu$|link|stron[aęeyi]?$|stronie$)", re.I)
_MONTHS = re.compile(r"^(stycz|lut|mar|kwie|maj|czerw|lip|sierp|wrze|paźdz|pazdz|listop|grud)", re.I)
_WORD = re.compile(r"[0-9]+(?:[.,][0-9]+)?%?|[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+(?:-[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+)?")
# verb forms (past tense, infinitive, common present endings): usually paraphrased by the article → lower weight
_VERBISH = re.compile(r"(ł|ła|ło|li|ły|łem|łam|łeś|łaś|liśmy|łyśmy|ć|uje|ują|ujemy|ujecie|ają|eją|iją)$")
# inflection endings stripped for substring engines (longest first); the stem keeps >= 4 letters
_ENDINGS = sorted("""owie ami ach ego emu ych ymi imi iej ów om em ie ia ią iu ej ym im ą ę a e i o u y""".split(),
                  key=len, reverse=True)


@dataclass(frozen=True)
class Term:
    word: str  # surface form (full-text engines)
    stem: str  # inflection-stripped prefix (substring engines)
    score: float


def substr_stem(word: str) -> str:
    """'Wrocławiu' → 'Wrocław', '65-latkowie' part 'latkowie' → 'latk', 'darmowymi' → 'darmow'; acronyms unchanged."""
    if word.isupper() or word[0].isdigit():
        return word
    w = word.split("-")[-1] if "-" in word else word
    for e in _ENDINGS:
        if w.lower().endswith(e) and len(w) - len(e) >= 4:
            return w[: len(w) - len(e)]
    return w


_IDF_CACHE: dict = {"bm": None, "idf": {}, "max": 0.0}


def _idf() -> tuple[dict, float]:
    """IDF of 6-letter stems in the local corpus (BM25 index) — how rare, i.e. distinctive, a word is."""
    try:
        from .index import INDEX

        bm = INDEX.bm25
    except Exception:  # noqa: BLE001 — index not loaded (unit use): fall back to surface heuristics
        bm = None
    if bm is None or not bm.N:
        return {}, 0.0
    if _IDF_CACHE["bm"] is not bm or _IDF_CACHE.get("n") != bm.N:
        import math

        _IDF_CACHE.update(bm=bm, n=bm.N, idf=bm.idf, max=math.log(1 + (bm.N + 0.5) / 0.5))
    return _IDF_CACHE["idf"], _IDF_CACHE["max"]


_NAMES_CACHE: dict = {"reg": None, "stems": set()}


def _name_stems() -> set[str]:
    """Stems of fact-checker names from the registry ('Demagoga' in a question is meta, not the topic)."""
    reg = registry()
    if _NAMES_CACHE["reg"] is not reg:
        out: set[str] = set()
        for s in reg:
            if s.category == "factcheck":
                out.update(t for t in tokens(s.publisher) if len(t) >= 4 and not t[0].isdigit())
        _NAMES_CACHE.update(reg=reg, stems=out)
    return _NAMES_CACHE["stems"]


def query_terms(text: str, n: int = 6) -> list[Term]:
    """Most distinctive words of a claim, best first (proper names and rare content words > verbs > years >
    months/plain numbers)."""
    idf, idf_max = _idf()
    meta = _name_stems()
    scored: list[tuple[float, int, Term]] = []
    seen: set[str] = set()
    for i, m in enumerate(_WORD.finditer(text)):
        w = m.group(0)
        lw = w.lower()
        if lw in STOP or lw in _SEARCH_STOP or (len(lw) < 3 and not lw.isdigit()) or _META_RX.match(lw):
            continue
        st = (tokens(lw) or [lw])[0]
        if st in seen or st in meta:
            continue
        seen.add(st)
        if lw.isdigit():
            s = 0.6 if len(lw) == 4 else 0.1
        elif _MONTHS.match(lw):
            s = 0.2
        else:
            cap = w[0].isupper() and not w.isupper() or (w.isupper() and len(w) >= 3)
            s = 1.0 + 0.5 * min(len(lw), 12) / 12 + (0.8 if cap and i > 0 else 0.5 if cap else 0)
            if idf_max:
                s += 0.8 * idf.get(st, idf_max) / idf_max  # rare in the corpus → distinctive
            if not cap and _VERBISH.search(lw):
                s -= 0.6
        scored.append((s, i, Term(w, substr_stem(w), round(s, 3))))
    return [t for _, _, t in sorted(scored, key=lambda x: (-x[0], x[1]))[:n]]


def keywords(text: str, n: int = 5) -> list[str]:
    """Most distinctive surface words, best first (see query_terms)."""
    return [t.word for t in query_terms(text, n)]


def _content_stems(text: str) -> set[str]:
    meta = _name_stems()
    return {t for t in tokens(text) if not (t[0].isdigit() and len(t) < 4) and (len(t) >= 3 or t[0].isdigit())
            and t not in meta and not _META_RX.match(t)}


def _overlap(q: set[str], t: set[str]) -> set[str]:
    """Claim stems found in the title: equal 6-letter stems, or sharing a 5-letter prefix (darmo/darmow,
    miaste/miasta) — Polish inflection changes word endings."""
    out = q & t
    pref = {x[:5] for x in t if len(x) >= 5 and not x[0].isdigit()}
    return out | {x for x in q - out if len(x) >= 5 and not x[0].isdigit() and x[:5] in pref}


def _is_date_stem(t: str) -> bool:
    return t[0].isdigit() or bool(_MONTHS.match(t))


# ---------------------------------------------------------------- providers: search
@dataclass
class Hit:
    url: str
    title: str
    snippet: str = ""
    date: str | None = None
    provider: str = ""
    all_terms: bool = False  # the engine already required every keyword (WordPress search)


def _strip_tags(s: str) -> str:
    return normalize_ws(html_mod.unescape(re.sub(r"<[^>]+>", " ", s or "")))


def _relevant(hits: list[Hit], claim: str) -> bool:
    """Would any hit pass the pre-ranking? (decides whether a fallback query round is needed)"""
    return bool(_select(hits, claim, k=1, whitelist=False))


def _rounds(variants: list[list[tuple[str, bool]]], run: Callable[[str, bool, float], list[Hit]], claim: str,
            timeout: float, label: str) -> list[Hit]:
    """Run query rounds (each round in parallel); stop after the first round that produced a relevant hit or when
    the time is up. Errors of single queries are tolerated as long as one query of the host answered."""
    t_end = time.monotonic() + timeout
    hits: list[Hit] = []
    answered, errors = 0, []
    for rnd in variants:
        left = t_end - time.monotonic()
        if left < 1.0 or not rnd:
            break
        pool = ThreadPoolExecutor(max_workers=min(4, len(rnd)), thread_name_prefix="live-q")
        try:
            futs = [pool.submit(run, q, combined, left) for q, combined in rnd]
            done, _ = wait(futs, timeout=left)
            for f in done:
                try:
                    hits += f.result()
                    answered += 1
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{type(e).__name__}: {str(e)[:80]}")
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        if _relevant(hits, claim):
            break
    if not answered and errors:
        raise LiveError(f"{label}: " + "; ".join(errors[:2]))
    return hits


def _search_govpl(terms: list[Term], claim: str, timeout: float) -> list[Hit]:
    url = "https://www.gov.pl/api/data/search"
    t_end = time.monotonic() + timeout  # one clock for robots.txt + all rounds
    if not robots_allowed(url, min(3.0, timeout)):
        raise LiveError("robots.txt gov.pl nie pozwala na wyszukiwanie")

    def run(q: str, _combined: bool, t: float) -> list[Hit]:
        r = _get(url, t, headers={"Accept": "application/json"}, params={"query": q, "page": 0, "size": 20})
        if r.status_code != 200:
            raise LiveError(f"gov.pl HTTP {r.status_code}")
        return [Hit(urljoin("https://www.gov.pl", str(it.get("url") or "")), _strip_tags(it.get("title") or ""),
                    _strip_tags(it.get("intro") or ""), (it.get("publishDate") or "")[:10] or None, "sitesearch:gov.pl")
                for it in (r.json().get("results") or [])[:20]]

    words = [t.word for t in terms]  # full-text engine: whole words, it does its own stemming/ranking
    rounds = [[(" ".join(words[:4]), True)], [(" ".join(words[:2]), True)]] if len(words) > 2 else [[(" ".join(words), True)]]
    return _rounds(rounds, run, claim, max(0.5, t_end - time.monotonic()), "gov.pl")


def _search_wordpress(host: str, terms: list[Term], claim: str, timeout: float) -> list[Hit]:
    url = f"https://{host}/wp-json/wp/v2/search"
    t_end = time.monotonic() + timeout  # one clock for robots.txt + all rounds
    if not robots_allowed(url, min(3.0, timeout)):
        raise LiveError(f"robots.txt {host} nie pozwala na wyszukiwanie")

    def run(q: str, combined: bool, t: float) -> list[Hit]:
        r = _get(url, t, headers={"Accept": "application/json"},
                 params={"search": q, "per_page": 10 if combined else 50, "type": "post"})
        if r.status_code != 200:
            raise LiveError(f"{host} HTTP {r.status_code}")
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else []
        return [Hit(str(it.get("url")), _strip_tags(it.get("title") or ""), "", None, f"sitesearch:{host}", combined)
                for it in data if isinstance(it, dict) and it.get("url")]

    stems = list(dict.fromkeys(t.stem for t in terms if not t.word[0].isdigit()))
    # single-term queries go rarest first: phrase/title engines (demagog.org.pl) return dozens of titles for a common
    # name ('Tusk') and the right one for a rare word ('depesz'); the first round must carry the distinctive words,
    # because a slow site leaves no time for a second round
    idf, idf_max = _idf()
    rarity = {t.stem: idf.get((tokens(t.word.lower()) or [""])[0], idf_max) for t in terms}
    singles = sorted((s for s in stems if len(s) >= 4),  # a 3-letter substring ('PAP' ⊂ 'papież') is too unspecific
                     key=lambda s: -rarity.get(s, 0.0))
    rnd1 = ([(" ".join(stems[:3]), True)] if len(stems) >= 2 else []) + [(s, False) for s in singles[:2]]
    rnd1 = rnd1 or ([(stems[0], True)] if stems else [])
    rnd2 = [(s, False) for s in singles[2:4]] + ([(" ".join(stems[:2]), True)] if len(stems) >= 3 else [])
    return _rounds([rnd1, rnd2], run, claim, max(0.5, t_end - time.monotonic()), host)


def _site_query(words: list[str], hosts: list[str]) -> str:
    return " ".join(words) + " (" + " OR ".join(f"site:{h}" for h in hosts[:8]) + ")"


def _search_searxng(words: list[str], hosts: list[str], timeout: float) -> list[Hit]:
    base = _env("SEARXNG_URL").rstrip("/")
    # operator-configured (may be self-hosted on a private address) → no SSRF check for the endpoint itself
    r = _get(f"{base}/search", timeout, headers={"Accept": "application/json"}, check_ssrf=False,
             params={"q": _site_query(words, hosts), "format": "json", "language": "pl"})
    if r.status_code != 200:
        raise LiveError(f"SearXNG HTTP {r.status_code}")
    return [Hit(str(it.get("url")), _strip_tags(it.get("title") or ""), _strip_tags(it.get("content") or ""),
                (it.get("publishedDate") or "")[:10] or None, "searxng")
            for it in r.json().get("results", []) if it.get("url")]


def _search_brave(words: list[str], hosts: list[str], timeout: float) -> list[Hit]:
    r = _get("https://api.search.brave.com/res/v1/web/search", timeout,
             headers={"Accept": "application/json", "X-Subscription-Token": _env("BRAVE_KEY")},
             params={"q": _site_query(words, hosts), "country": "pl", "search_lang": "pl", "count": 20})
    if r.status_code != 200:
        raise LiveError(f"Brave HTTP {r.status_code}")
    return [Hit(str(it.get("url")), _strip_tags(it.get("title") or ""), _strip_tags(it.get("description") or ""),
                None, "brave") for it in (r.json().get("web") or {}).get("results", []) if it.get("url")]


def _search_jobs(terms: list[Term], claim: str) -> list[tuple[str, Callable[[float], list[Hit]]]]:
    hosts = allowed_hosts()
    words = [t.word for t in terms[:4]]
    jobs: list[tuple[str, Callable[[float], list[Hit]]]] = []
    if _env("BRAVE_KEY"):
        jobs.append(("brave", lambda t: _search_brave(words, hosts, t)))
    if _env("SEARXNG_URL"):
        jobs.append(("searxng", lambda t: _search_searxng(words, hosts, t)))
    overrides = {s.host: s.site_search for s in registry() if s.web_search and s.site_search}
    for h in hosts:
        kind = overrides.get(h) or _KNOWN_SITE_SEARCH.get(h, "")
        if kind == "govpl":
            jobs.append((f"sitesearch:{h}", lambda t: _search_govpl(terms, claim, t)))
        elif kind == "wordpress":
            jobs.append((f"sitesearch:{h}", lambda t, h=h: _search_wordpress(h, terms, claim, t)))
    return jobs


def _select(hits: list[Hit], claim: str, k: int = MAX_FETCH, whitelist: bool = True) -> list[Hit]:
    """Whitelist filter + lexical pre-ranking (title/snippet vs claim) before anything is fetched."""
    q = _content_stems(claim)
    scored: dict[str, tuple[float, Hit]] = {}
    for h in hits:
        if not h.url.startswith(("http://", "https://")) or (whitelist and not match_source(h.url)):
            continue  # never use non-whitelisted domains
        shared = _overlap(q, _content_stems(f"{h.title} {h.snippet}"))
        ratio = len(shared) / max(1, len(q))
        if not any(not _is_date_stem(t) for t in shared):
            continue  # a shared month/year alone says nothing about the topic
        if not h.all_terms and not (len(shared) >= min(2, len(q)) and ratio >= 0.3):
            continue
        key = h.url.split("#")[0].rstrip("/")
        if key not in scored or ratio > scored[key][0]:
            scored[key] = (ratio + (0.05 if h.all_terms else 0), h)
    return [h for _, h in sorted(scored.values(), key=lambda x: -x[0])[:k]]


# ---------------------------------------------------------------- providers: Google Fact Check Tools
GFC_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
_GFC_CACHE: dict[str, tuple[float, list]] = {}
_GFC_TTL = 6 * 3600
# The SAME list as ingest/common.py::_VERDICT_RULES (order matters: more specific first), so a rating read live from
# Google (`textualRating` = the publisher's ClaimReview label) lands in the same class as the same label harvested
# into the corpus. backend/tests/test_google_factcheck.py fails when the two lists drift apart. Before 2026-11-21 this
# copy was shorter: Demagog's "Częściowy fałsz" became `false` instead of `mixed` and "Przerobione zdjęcie/film" had
# no class at all (measured on the 1,294 Demagog records: 104 labels mapped differently from the corpus).
_VERDICT_RULES = [
    ("czesciowa prawda", "mixed"), ("czesciowo prawda", "mixed"), ("czesciowy falsz", "mixed"),
    ("czesciowo falsz", "mixed"), ("polprawda", "mixed"), ("mostly true", "mixed"),
    ("mostly false", "mixed"), ("partly false", "mixed"), ("partially false", "mixed"), ("half true", "mixed"),
    ("mixed", "mixed"),
    ("nieweryfikowal", "unverifiable"), ("unverifiable", "unverifiable"), ("niesprawdzal", "unverifiable"),
    ("brak dowodow", "unverifiable"), ("sie zweryfikowac", "unverifiable"), ("insufficient evidence", "unverifiable"),
    ("w wiekszosci", "mixed"),
    ("manipulac", "misleading"), ("wprowadza w blad", "misleading"), ("wprowadzajac", "misleading"),
    ("brak kontekstu", "misleading"), ("brakujacy kontekst", "misleading"), ("brakuje kontekstu", "misleading"),
    ("bez kontekstu", "misleading"), ("missing context", "misleading"),
    ("misleading", "misleading"), ("przesad", "misleading"), ("wyrwan", "misleading"), ("mylac", "misleading"),
    ("zmanipulowan", "false"), ("przerobion", "false"), ("wygenerowan", "false"), ("deepfake", "false"),
    ("obraz ai", "false"),
    ("przerobk", "false"), ("nieprawdziw", "false"), ("falszyw", "false"), ("falsz", "false"), ("fake", "false"),
    ("nieprawda", "false"),
    ("disinformation", "false"), ("dezinformac", "false"), ("false", "false"), ("oszustwo", "false"),
    ("scam", "false"), ("altered", "false"),
    ("prawda", "true"), ("prawdziw", "true"), ("true", "true"), ("correct", "true"),
]
# labels that are not a rating of a claim (the same lists as ingest/common.py): substrings, then whole labels
_NO_VERDICT = ("satyr", "satire", "wyjasniamy", "explain")
_NOT_A_RATING = {"analiza", "raport", "fact-checked", "fact checked", "zrealizowane"}


def map_rating(raw: str | None) -> str | None:
    """Publisher's rating label → true | false | misleading | mixed | unverifiable | None (same as ingest map_verdict)."""
    if not raw:
        return None
    import unicodedata

    n = "".join(c for c in unicodedata.normalize("NFKD", raw.lower()) if not unicodedata.combining(c))
    n = n.replace("ł", "l").strip(" .!:- ")
    if n in _NOT_A_RATING or any(x in n for x in _NO_VERDICT):
        return None
    return next((v for k, v in _VERDICT_RULES if k in n), None)


def google_publisher_sites() -> list[str]:
    """Fact-checker sites asked for by name in an extra, site-filtered query (`reviewPublisherSiteFilter`), from
    `params.publisher_sites` of data/sources/google_factcheck.json. Only sites of enabled registry sources are used —
    a review from anywhere else could not become evidence anyway (see google_docs)."""
    try:
        e = json.loads((SOURCES_DIR / "google_factcheck.json").read_text(encoding="utf-8"))
        sites = (e.get("params") or {}).get("publisher_sites") or []
    except (OSError, ValueError, AttributeError):
        return []
    out = []
    for s in sites if isinstance(sites, list) else []:
        host = _host(s if "://" in str(s) else f"https://{s}")
        if host and host not in out and match_source(f"https://{host}/", web_search_only=False):
            out.append(host)
    return out[:3]


def google_factcheck(query: str, timeout: float = GOOGLE_TIMEOUT_S, site: str = "") -> list[dict]:
    """Raw `claims` from claims:search (cached). `site` adds reviewPublisherSiteFilter (one publisher's reviews only).
    Raises LiveError (message never contains the key)."""
    if forced_fail("google_factcheck"):
        raise LiveError("symulowana awaria (PRAWDOWID_FORCE_FAIL)")
    ck = f"{site}|{normalize_ws(query).lower()[:300]}"
    hit = _GFC_CACHE.get(ck)
    if hit and time.time() - hit[0] < _GFC_TTL:
        return hit[1]
    params = {"query": query[:300], "languageCode": "pl", "pageSize": 10}
    if site:
        params["reviewPublisherSiteFilter"] = site
    try:
        # the key goes in the X-Goog-Api-Key header (accepted by the API, checked 2026-11-21), not in the URL:
        # httpx logs request URLs at INFO level, and a key in the query string would end up in the server log
        r = httpx.get(GFC_URL, timeout=timeout, params=params,
                      headers={"User-Agent": UA, "X-Goog-Api-Key": _env("GOOGLE_FACTCHECK_KEY")})
    except httpx.HTTPError as e:
        raise LiveError(f"{type(e).__name__}") from None  # str(e) could include the URL with the key
    if r.status_code != 200:
        raise LiveError(f"HTTP {r.status_code}")
    try:
        claims = r.json().get("claims") or []
    except ValueError:
        raise LiveError("nieprawidłowa odpowiedź JSON") from None
    _GFC_CACHE[ck] = (time.time(), claims)
    if len(_GFC_CACHE) > 1000:
        _GFC_CACHE.pop(next(iter(_GFC_CACHE)))
    return claims


def google_queries(text: str) -> list[list[str]]:
    """Rounds of query forms for claims:search, most specific first.

    Measured against the real API (2026-11-21): the engine stems Polish words ('65-latkowie' finds '65-latków') but
    wants every query word in the review's claim or title, so a whole sentence or question returns nothing — 'Czy PAP
    usunęła depeszę o wypowiedzi Donalda Tuska przed powodzią?' → 0 results, 'Donalda Tuska PAP wypowiedzi powodzią'
    → the Demagog review. Rare proper names alone can fail ('Rzeszów IRINN' → 0) while the opening words of the
    claim as the fact-checker wrote it succeed ('Stacja IRINN pokazała mapę' → the AFP review). Hence rounds: the 4
    most distinctive words of the claim; its first words as written; the 3 most distinctive words; then pairs of the
    most distinctive word with each of the next three (a user rarely uses the fact-checker's exact wording)."""
    w = keywords(text, 4)
    lead = re.sub(r"^\s*(czy\s+(to\s+prawda,?\s+że\s+)?|to\s+prawda,?\s+że\s+)", "", normalize_ws(text), flags=re.I)
    lead = " ".join(lead.rstrip("?.! ").split()[:4])
    rounds = [[" ".join(w[:4])] if len(w) >= 4 else [], [lead] if len(lead.split()) >= 3 else [],
              [" ".join(w[:3])] if len(w) >= 3 else [], [f"{w[0]} {x}" for x in w[1:4]] if len(w) >= 2 else []]
    rounds = [r for r in rounds if r] or [[" ".join(w) or text[:300]]]
    seen: set[str] = set()
    return [r2 for r2 in ([q for q in r if not (q in seen or seen.add(q))] for r in rounds) if r2]


def _registry_reviews(claims: list[dict]) -> int:
    return sum(1 for c in claims for rv in c.get("claimReview") or []
               if match_source(str(rv.get("url") or ""), web_search_only=False))


def google_search(text: str, timeout: float = GOOGLE_TIMEOUT_S) -> list[dict]:
    """Raw claims for one user claim: keyword rounds, stopping at the first round that returns a review published on
    a registry domain. A general query whose page comes back full of other publishers is repeated for each
    configured fact-checker site (`reviewPublisherSiteFilter`), so Demagog is not crowded out of the 10 results.
    One clock for all rounds; if at least one call answered, failures of the others are tolerated — if none did,
    LiveError (an outage, never 'no such article')."""
    t_end = time.monotonic() + timeout
    out: list[dict] = []
    answered, last_err = 0, None

    def ask(q: str, site: str = "") -> list[dict]:
        nonlocal answered, last_err
        left = t_end - time.monotonic()
        if left < 0.3:
            return []
        try:
            got = google_factcheck(q, timeout=left, site=site)
            answered += 1
            return got
        except LiveError as e:
            last_err = e
            return []

    for rnd in google_queries(text):
        for q in rnd:
            got = ask(q)
            if len(got) >= 10 and not _registry_reviews(got):
                for site in google_publisher_sites():
                    got += ask(q, site)
            out += got
        if _registry_reviews(out):
            break
    if not answered:
        raise last_err or LiveError("przekroczony czas")
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _doc_id(url: str) -> str:
    return "live_web:" + hashlib.sha1(url.split("#")[0].rstrip("/").encode()).hexdigest()[:16]


def google_docs(claims: list[dict]) -> tuple[list[SourceDoc], int]:
    """ClaimReviews on registry domains → factcheck SourceDocs; returns (docs, n_other_publishers)."""
    docs, other, seen = [], 0, set()
    for c in claims:
        for rv in c.get("claimReview") or []:
            url = str(rv.get("url") or "")
            if url in seen:  # the same review can come back from the general and the site-filtered query
                continue
            seen.add(url)
            src = match_source(url, web_search_only=False)
            if not src:
                other += 1
                continue
            claim_text = neutralize(normalize_ws(c.get("text") or ""))
            title = neutralize(normalize_ws(rv.get("title") or "")) or claim_text
            rating = normalize_ws(rv.get("textualRating") or "")
            if not claim_text or not rating:
                continue
            docs.append(SourceDoc(
                id=_doc_id(url), source_type=src.category if src.category != "official" else "factcheck",
                publisher=normalize_ws((rv.get("publisher") or {}).get("name") or src.publisher), domain=_host(url),
                url=url, title=title[:300], published_at=(rv.get("reviewDate") or c.get("claimDate") or "")[:10] or None,
                retrieved_at=_now(), language=rv.get("languageCode") or "pl", license=src.license,
                # verbatim ClaimReview fields published by the fact-checker (title + claimReviewed)
                text=f"{title}. {claim_text}" if title != claim_text else claim_text,
                claim=claim_text, claim_author=c.get("claimant"), verdict_raw=rating, verdict=map_rating(rating),
                tags=["live_search", "google_factcheck", f"registry:{src.id}", f"tier:{src.tier}"]))
    return docs, other


# ---------------------------------------------------------------- trusted web search for one claim
@dataclass
class SearchOutcome:
    provider: str = ""
    query: str = ""
    n_hits: int = 0
    docs: list[SourceDoc] = field(default_factory=list)
    events: list[SecurityEvent] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    timed_out: bool = False
    providers_ok: int = 0
    searched: list[str] = field(default_factory=list)  # what was actually queried (hosts / engines)


def _fetch_doc(hit: Hit, deadline: float) -> tuple[SourceDoc | None, list[SecurityEvent]]:
    if not robots_allowed(hit.url, max(0.5, min(3.0, deadline - time.monotonic()))):
        return None, []
    page = fetch_url(hit.url)  # SSRF-safe, size/time limited, every redirect hop checked
    src = match_source(page["url"])  # the final URL (after redirects) must still be whitelisted
    if not src or len(page.get("text") or "") < 200:
        return None, []
    events = scan(page["text"], f"wyszukiwanie na żywo: {_host(page['url'])}")
    text = neutralize(page["text"])
    title = neutralize(hit.title or re.sub(r"\s+-\s+Portal Gov\.pl$", "", page.get("title") or ""))
    publisher = src.publisher
    if src.host == "gov.pl" and src.url.rstrip("/") in ("https://www.gov.pl", "https://gov.pl"):
        publisher = (page.get("sitename") or "").replace(" - Portal Gov.pl", "").strip() or src.publisher
    # a fact-checker's page carries its verdict as schema.org ClaimReview: use the reviewed claim + rating label, so the
    # page is matched like a corpus fact-check (same claim-matching and NLI rules), not only as related reading
    cr = page.get("claim_review") if src.category in ("factcheck", "incident") else None
    claim = author = rating = None
    if cr and map_rating(cr.get("rating")):
        claim = short(neutralize(normalize_ws(cr["claim"])), 1000)
        author = short(neutralize(normalize_ws(cr.get("author") or "")), 120) or None
        rating = short(normalize_ws(cr["rating"]), 80)
    tags = ["live_search", hit.provider.split(":")[0], f"registry:{src.id}", f"tier:{src.tier}"] + (["claimreview"] if claim else [])
    return SourceDoc(
        id=_doc_id(page["url"]), source_type=src.category, publisher=publisher, domain=_host(page["url"]),
        url=page["url"], title=short(title, 300),
        published_at=(hit.date or (cr or {}).get("date") or (page.get("date") or "")[:10]) or None,
        retrieved_at=_now(), language="pl", license=src.license, text=text[:6000], claim=claim, claim_author=author,
        verdict_raw=rating, verdict=map_rating(rating), tags=tags), events


def search_trusted(claim: str, deadline: float, check_id: str | None = None) -> SearchOutcome:
    out = SearchOutcome()
    if forced_fail("websearch"):
        raise LiveError("symulowana awaria (PRAWDOWID_FORCE_FAIL)")
    terms = query_terms(claim)
    out.query = " ".join(t.word for t in terms[:4])
    jobs = _search_jobs(terms, claim)
    if not terms or not jobs:
        return out
    out.provider = "+".join(dict.fromkeys(n.split(":")[0] for n, _ in jobs))
    out.searched = [n.split(":", 1)[-1] for n, _ in jobs]
    pool = ThreadPoolExecutor(max_workers=min(8, len(jobs) + MAX_FETCH), thread_name_prefix="live")
    try:
        t_left = lambda: deadline - time.monotonic()  # noqa: E731
        # hosts run in parallel; each returns what it has by its own deadline (slow sites never eat the fetch time)
        budget = max(0.5, min(SEARCH_TIMEOUT_S, t_left() - FETCH_RESERVE_S))
        futs = {pool.submit(fn, budget): name for name, fn in jobs}
        done, pending = wait(futs, timeout=max(0.1, min(budget + 0.5, t_left())))
        hits: list[Hit] = []
        for f in done:
            try:
                hits += f.result()
                out.providers_ok += 1
            except Exception as e:  # noqa: BLE001
                out.errors.append(f"{futs[f]}: {type(e).__name__}: {str(e)[:120]}")
        if pending:
            out.timed_out = True
            out.errors += [f"{futs[f]}: przekroczony czas" for f in pending]
        out.n_hits = len(hits)
        chosen = _select(hits, claim)
        if not chosen or t_left() <= 0.5:
            return out
        ffuts = {pool.submit(_fetch_doc, h, deadline): h for h in chosen}
        done, pending = wait(ffuts, timeout=max(0.1, t_left()))
        if pending:
            out.timed_out = True
            out.errors += [f"pobieranie {ffuts[f].url[:100]}: przekroczony czas" for f in pending]
        for f in done:
            try:
                doc, events = f.result()
            except Exception as e:  # noqa: BLE001 — one page failing is not a provider failure
                log.info("live fetch failed %s: %s", ffuts[f].url, e)
                continue
            if doc:
                out.docs.append(doc)
                out.events += events
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    if out.errors:
        store.log_error(check_id, "live_websearch", "; ".join(out.errors))
    return out


# ---------------------------------------------------------------- persistence (next identical question → corpus)
_PERSIST_LOCK = threading.Lock()


def persist(docs: list[SourceDoc]) -> int:
    if not docs:
        return 0
    with _PERSIST_LOCK:
        known: set[str] = set()
        if LIVE_CORPUS.exists():
            for line in LIVE_CORPUS.read_text(encoding="utf-8").splitlines():
                try:
                    known.add(json.loads(line)["url"].rstrip("/"))
                except (ValueError, KeyError, TypeError):
                    continue
        new = [d for d in docs if d.url.rstrip("/") not in known]
        if new:
            with LIVE_CORPUS.open("a", encoding="utf-8") as fh:
                for d in new:
                    fh.write(json.dumps(d.model_dump(), ensure_ascii=False) + "\n")
        return len(new)


# ---------------------------------------------------------------- orchestration used by service.run_check
NOTICE_GOOGLE_FAIL = ("Nie mogę teraz sprawdzić indeksu Google z powodu błędu dostępu. "
                      "Odpowiedź opiera się na lokalnej bazie źródeł.")
NOTICE_WEB_FAIL = ("Nie mogę teraz przeszukać zaufanych stron w internecie z powodu błędu dostępu. "
                   "Odpowiedź opiera się na lokalnej bazie źródeł.")
NOTICE_BOTH_FAIL = ("Nie mogę teraz sprawdzić indeksu Google ani przeszukać zaufanych stron w internecie z powodu błędu "
                    "dostępu. Odpowiedź opiera się na lokalnej bazie źródeł.")


def _usable(r: ClaimResult) -> bool:
    return (r.conflicting or any(e.stance in ("popiera", "przeczy") for e in r.evidence)
            or "FACTCHECK_NIEWERYFIKOWALNE" in r.reason_codes)


class LiveStage:
    """One per check. start_google() is non-blocking (runs while the local search works); finish() joins it,
    re-verifies claims that got Google evidence and runs the trusted-domain fallback. Never raises."""

    def __init__(self, check_id: str | None, progress: Progress = None):
        self.cid, self.progress = check_id, progress
        self.t0 = time.monotonic()
        self.deadline = self.t0 + LIVE_BUDGET_S - NET_RESERVE_S  # reset when the fallback starts (see finish)
        self.g_wait = 0.0  # time spent waiting for Google after the local search was done
        self.events: list[SecurityEvent] = []
        self.warnings: list[str] = []
        self._g_pool: ThreadPoolExecutor | None = None
        self.web: dict | None = None
        self.google: dict | None = None
        self.enabled = live_enabled()

    # -------------------------------------------------- Google (parallel to the local search)
    def start_google(self, claims: list) -> None:
        if not self.enabled or not (_env("GOOGLE_FACTCHECK_KEY") or forced_fail("google_factcheck")):
            return  # missing key = provider silently inactive
        queries = [c.query for c in claims if c.kind == "fakt"]
        if not queries:
            return
        # per claim: keyword rounds, each a general query + one per configured fact-checker site (Demagog), so the
        # publisher the organisers' scenarios rely on is not crowded out of the 10 results (see google_search)
        self._g_pool = ThreadPoolExecutor(max_workers=min(4, len(queries)), thread_name_prefix="gfc")
        self._g_queries = [" ".join(keywords(q, 4)) or q for q in queries]  # what is actually sent, for the audit log
        self._g_futs = [self._g_pool.submit(google_search, q) for q in queries]

    def _join_google(self) -> list[SourceDoc]:
        if self._g_pool is None:
            return []
        t = time.monotonic()
        done, pending = wait(self._g_futs, timeout=max(0.1, GOOGLE_TIMEOUT_S + 0.5 - (t - self.t0)))
        self._g_pool.shutdown(wait=False, cancel_futures=True)
        self.g_wait = time.monotonic() - t
        raw, errors = [], []
        for f in self._g_futs:
            if f in pending:
                errors.append("przekroczony czas")
                continue
            try:
                raw += f.result()
            except Exception as e:  # noqa: BLE001
                errors.append(str(e)[:120])
        docs, other = google_docs(raw)
        status = "blad" if errors and len(errors) == len(self._g_futs) else ("ok" if docs else "brak_wynikow")
        notice = NOTICE_GOOGLE_FAIL if status == "blad" else ""
        if errors:
            store.log_error(self.cid, "live_google_factcheck", "; ".join(errors))
        if notice:
            self.warnings.append(notice)
        self.google = dict(provider="google_factcheck", query=" | ".join(self._g_queries)[:300], n_results=len(docs),
                           status=status, notice=notice, other_publishers=other,
                           elapsed_ms=round((time.monotonic() - self.t0) * 1000, 1))
        return docs

    # -------------------------------------------------- after the local verification
    def finish(self, claims: list, results: list[ClaimResult], timings: dict) -> list[ClaimResult]:
        from .engine import verify_claim  # local import: engine pulls the index/NLI

        try:
            from .index import INDEX

            gdocs = self._join_google()
            if gdocs and INDEX.add_docs(gdocs):
                persist(gdocs)
                emit(self.progress, "porownanie")
                results = self._reverify(claims, results, timings, verify_claim,
                                         [i for i, c in enumerate(claims) if c.kind == "fakt"])
            if not self.enabled:
                return results
            todo = [i for i, (c, r) in enumerate(zip(claims, results))
                    if c.kind == "fakt" and r.verdict == "brak_dowodow" and not _usable(r)][:MAX_FALLBACK_CLAIMS]
            if not todo:
                return results
            emit(self.progress, "internet")
            # the live budget counts from here (Google ran in parallel with the local search; its wait is included)
            self.deadline = time.monotonic() + LIVE_BUDGET_S - NET_RESERVE_S - self.g_wait
            t = self.t_web = time.perf_counter()
            outcomes: dict[int, SearchOutcome] = {}
            error: str | None = None
            ex = ThreadPoolExecutor(max_workers=len(todo), thread_name_prefix="live-claim")
            try:
                futs = {ex.submit(search_trusted, claims[i].query, self.deadline, self.cid): i for i in todo}
                for f, i in futs.items():
                    try:
                        outcomes[i] = f.result(timeout=max(0.1, self.deadline - time.monotonic() + 1))
                    except Exception as e:  # noqa: BLE001
                        error = f"{type(e).__name__}: {str(e)[:150]}"
            finally:
                ex.shutdown(wait=False, cancel_futures=True)  # never wait past the budget
            timings["live_search_ms"] = (time.perf_counter() - t) * 1000
            docs = [d for o in outcomes.values() for d in o.docs]
            for o in outcomes.values():
                self.events += o.events
            added = INDEX.add_docs(docs) if docs else 0
            if docs:
                persist(docs)
            if added or docs:
                emit(self.progress, "porownanie")
                results = self._reverify(claims, results, timings, verify_claim, todo)
            self._web_info(claims, results, todo, outcomes, docs, error)
        except Exception as e:  # noqa: BLE001 — live stage must never break the local answer
            log.exception("live stage failed")
            store.log_error(self.cid, "live_stage", repr(e)[:400])
            if self.web is None:
                self.web = dict(provider="sitesearch", query="", n_results=0, status="blad", notice=NOTICE_WEB_FAIL)
                self.warnings.append(NOTICE_WEB_FAIL)
        if NOTICE_GOOGLE_FAIL in self.warnings and NOTICE_WEB_FAIL in self.warnings:  # one sentence, not two
            self.warnings = [w for w in self.warnings if w not in (NOTICE_GOOGLE_FAIL, NOTICE_WEB_FAIL)]
            self.warnings.append(NOTICE_BOTH_FAIL)
        return results

    def _reverify(self, claims, results, timings, verify_claim, idx: list[int]) -> list[ClaimResult]:
        results = list(results)
        for i in idx:
            try:
                r = verify_claim(claims[i], timings)
            except Exception as e:  # noqa: BLE001
                store.log_error(self.cid, "live_reverify", repr(e)[:400])
                continue
            if any(e.doc_id.startswith("live_web:") for e in r.evidence):
                r.limitations.append("Część materiałów pobrano na żywo z zaufanych serwisów (rejestr źródeł) w chwili "
                                     "sprawdzenia i oceniono tymi samymi regułami co bazę lokalną.")
            results[i] = r
        return results

    def _web_info(self, claims, results, todo, outcomes, docs, error) -> None:
        o_all = list(outcomes.values())
        provider = "+".join(dict.fromkeys(p for o in o_all for p in o.provider.split("+") if p)) or "sitesearch"
        query = " | ".join(o.query for o in o_all if o.query) or " | ".join(" ".join(keywords(claims[i].query))
                                                                           for i in todo)
        hosts = ", ".join(dict.fromkeys(h for o in o_all for h in o.searched)) or ", ".join(allowed_hosts()[:6])
        any_ok = any(o.providers_ok for o in o_all)
        used = any(e.doc_id.startswith("live_web:") and e.stance in ("popiera", "przeczy")
                   for i in todo for e in results[i].evidence)
        if error or (o_all and not any_ok and any(o.errors for o in o_all)):
            status, notice = "blad", NOTICE_WEB_FAIL
            if error:
                store.log_error(self.cid, "live_websearch", error)
        elif docs:
            status = "ok"
            notice = (f"Nie znaleźliśmy tego w lokalnej bazie, więc przeszukaliśmy zaufane strony ({hosts}). "
                      f"Pobrano {len(docs)} materiał(y) i oceniono je tymi samymi regułami.")
            if not used:
                notice += (" Żaden z nich nie potwierdza ani nie obala tej informacji wprost — "
                           "brak wyniku nie oznacza, że jest ona prawdziwa lub fałszywa.")
        elif any(o.timed_out for o in o_all):
            status = "blad"
            notice = ("Przeszukiwanie zaufanych stron trwało zbyt długo i zostało przerwane. "
                      "Odpowiedź opiera się na lokalnej bazie źródeł.")
        else:
            status = "brak_wynikow"
            notice = (f"Przeszukaliśmy także zaufane strony w internecie ({hosts}) — nie znaleziono materiałów na ten "
                      "temat. Brak wyniku nie oznacza, że informacja jest prawdziwa lub fałszywa.")
        self.web = dict(provider=provider, query=query[:300], n_results=len(docs), status=status, notice=notice,
                        searched=list(dict.fromkeys(h for o in o_all for h in o.searched)),
                        elapsed_ms=round((time.perf_counter() - self.t_web) * 1000, 1))
        self.warnings.append(notice)

    def info(self) -> LiveSearchInfo | None:
        steps = [s for s in (self.google, self.web) if s]
        if not steps:
            return None
        main = self.web or self.google
        notices = [s["notice"] for s in steps if s.get("notice")]
        if notices == [NOTICE_GOOGLE_FAIL, NOTICE_WEB_FAIL]:
            notices = [NOTICE_BOTH_FAIL]
        return LiveSearchInfo(provider=main["provider"], query=main["query"], n_results=main["n_results"],
                              status=main["status"], notice=" ".join(notices), steps=steps)
