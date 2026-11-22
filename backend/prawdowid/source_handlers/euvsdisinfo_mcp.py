"""Read organizer EUvsDisinfo MCP datasets with retries and corpus conversion.

EUvsDisinfo MCP client + ingest handler (registry: method "custom", params.handler "euvsdisinfo_mcp").

Server: https://euvsdisinfo-mcp-server.vercel.app/mcp — MCP over *streamable HTTP* (not legacy SSE), provided to
HackNation 2026 participants by the organisers; spec: rules/How_to_grab_all_Articles_and_Cases_from_disinfo.pdf.
Tools: `cases` (~19k disinformation cases) and `articles` (~6.7k EUvsDisinfo analyses), both {offset, limit<=100}.

Flow: initialize -> remember the `mcp-session-id` response header -> notifications/initialized -> tools/call,
paginated until hasNextPage=false. Responses come as application/json or text/event-stream (`data:` lines); both are
parsed. Retries with exponential backoff (network errors, 408/425/429/5xx, Retry-After honoured), a polite delay
between tool calls, one transparent re-initialisation if the server drops the session.

Token: env PRAWDOWID_EUVSDISINFO_TOKEN — never written to any file or log. No token -> MissingToken ("brak tokenu"),
token rejected (HTTP 401/403 or JSON-RPC -32001) -> AuthError. Stdlib only (urllib): runs outside the backend venv too.

Mapping (same id scheme as ingest/harvest_euvsdisinfo.py, so records dedupe against data/corpus/euvsdisinfo.jsonl):
  case    -> id "euvsdisinfo:<report slug>", source_type incident, claim = the disinformation claim, text = the
             disproof ("fact"), verdict false / "Disinformation (EUvsDisinfo)", published_at from the unix `date`,
             tags from keywords + "kraj:<country>"; claim_author = outlet domains (names only, no links).
  article -> id "euvsdisinfo:article/<url path>", source_type factcheck (EUvsDisinfo analysis), HTML stripped.
The links to the disinformation outlets (linksToDisinformation) are kept ONLY in the raw dump
data/raw/euvsdisinfo_mcp/<kind>.jsonl.gz — they are the debunked material, never evidence.

Licence: EUvsDisinfo / EEAS East StratCom Task Force — reuse authorised provided the source is acknowledged
(EEAS legal notice, Commission Decision 2011/833/EU reuse policy); third-party content excluded.

CLI (run from backend/):
  .venv/bin/python -m prawdowid.source_handlers.euvsdisinfo_mcp --probe
  .venv/bin/python -m prawdowid.source_handlers.euvsdisinfo_mcp --dump 200 /tmp/euvsdisinfo_mcp.jsonl

Reading guide: docs/backend/SOURCES.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import argparse
import gzip
import http.client
import json
import logging
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterator, Optional
from urllib.parse import urlparse

log = logging.getLogger("prawdowid.source_handlers.euvsdisinfo_mcp")

ENDPOINT = "https://euvsdisinfo-mcp-server.vercel.app/mcp"
TOKEN_ENV = "PRAWDOWID_EUVSDISINFO_TOKEN"
PROTOCOL_VERSION = (
    "2024-11-05"  # version documented by the server; the negotiated one is taken from its answer
)
CLIENT_INFO = {"name": "prawdowid-euvsdisinfo-ingest", "version": "0.1.0"}
USER_AGENT = "PrawdowidIngest/0.1 (HackNation 2026 research prototype; EUvsDisinfo MCP client)"
SOURCE_ID = "euvsdisinfo"  # id prefix shared with ingest/harvest_euvsdisinfo.py (dedupe!)
PUBLISHER = "EUvsDisinfo (EEAS East StratCom Task Force)"
DOMAIN = "euvsdisinfo.eu"
LICENSE = (
    "EUvsDisinfo (EEAS East StratCom Task Force). Reuse authorised provided the source is "
    "acknowledged (EEAS legal notice, Decision 2011/833/EU); third-party content excluded."
)
LICENSE_MCP = LICENSE + " Retrieved via the EUvsDisinfo MCP server (HackNation 2026 organisers)."
VERDICT_RAW = "Disinformation (EUvsDisinfo)"
KINDS = ("cases", "articles")
MAX_PAGE = 100
MAX_TEXT = 12000
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}
ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data" / "raw" / "euvsdisinfo_mcp"
REGISTRY_FILE = ROOT / "data" / "sources" / "euvsdisinfo_mcp.json"
DEFAULT_PARAMS = {
    "kinds": list(KINDS),
    "since": "2023-01-01",
    "max_records": None,
    "article_languages": ["pl", "en"],
}
ARCHIVE_HOSTS = {
    "web.archive.org",
    "archive.ph",
    "archive.today",
    "archive.is",
    "archive.org",
    "archive.euvsd.info",
}


# --------------------------------------------------------------------------- errors
class McpError(RuntimeError):
    """Failure talking to the MCP server. Messages are safe to show in the admin panel (never contain the token)."""


class MissingToken(McpError):
    """PRAWDOWID_EUVSDISINFO_TOKEN is not set — nothing was sent to the server."""


class AuthError(McpError):
    """The server rejected the token (HTTP 401/403 or JSON-RPC -32001)."""


class SessionExpired(McpError):
    """The server no longer knows our mcp-session-id (internal: triggers one re-initialisation)."""


# Registry contract: these are reported as a plain run status ("brak tokenu: …"), not as an unexpected crash.
EXPECTED_ERRORS = (McpError,)


# --------------------------------------------------------------------------- HTTP layer (injectable for tests)
@dataclass
class HttpResponse:
    status: int
    headers: dict  # lower-case header names
    body: bytes


Transport = Callable[
    [str, str, dict, Optional[bytes], float], HttpResponse
]  # (method, url, headers, body, timeout)


def urllib_transport(
    method: str, url: str, headers: dict, body: Optional[bytes], timeout: float
) -> HttpResponse:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return HttpResponse(r.status, {k.lower(): v for k, v in r.headers.items()}, r.read())
    except urllib.error.HTTPError as e:  # 4xx/5xx still carry a JSON-RPC error body worth reading
        try:
            data = e.read() or b""
        except Exception:  # noqa: BLE001
            data = b""
        return HttpResponse(e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, data)


def parse_messages(content_type: str, body: bytes) -> list[dict]:
    """JSON-RPC messages from a streamable-HTTP response: plain JSON (object or batch) or an SSE stream."""
    text = body.decode("utf-8", "replace").lstrip("﻿")
    if not text.strip():
        return []
    if "text/event-stream" in (content_type or "").lower() or re.match(
        r"\s*(event|data|id|retry)\s*:|:", text
    ):
        return _parse_sse(text)
    obj = json.loads(text)
    return [m for m in (obj if isinstance(obj, list) else [obj]) if isinstance(m, dict)]


def _parse_sse(text: str) -> list[dict]:
    out: list[dict] = []
    for block in re.split(r"\r?\n\r?\n", text.replace("\r\n", "\n")):
        data = [ln[5:].removeprefix(" ") for ln in block.split("\n") if ln.startswith("data:")]
        if not data:
            continue
        obj = None
        for joined in (
            "\n".join(data),
            "".join(data),
        ):  # spec: newline-joined; tolerate JSON split mid-string
            try:
                obj = json.loads(joined)
                break
            except ValueError:
                continue
        if obj is None:
            log.warning("EUvsDisinfo MCP: unparseable SSE event (%d B) skipped", len(block))
            continue
        out.extend(m for m in (obj if isinstance(obj, list) else [obj]) if isinstance(m, dict))
    return out


# --------------------------------------------------------------------------- MCP client
class McpClient:
    def __init__(
        self,
        token: Optional[str],
        url: str = ENDPOINT,
        *,
        transport: Optional[Transport] = None,
        timeout: float = 60.0,
        retries: int = 4,
        backoff: float = 2.0,
        delay: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.token = token or None
        self.url = url
        self.transport = transport or urllib_transport
        self.timeout, self.retries, self.backoff, self.delay, self.sleep = (
            timeout,
            retries,
            backoff,
            delay,
            sleep,
        )
        self.session_id: Optional[str] = None
        self.protocol_version: Optional[str] = None
        self.server_info: dict = {}
        self.totals: dict[str, int] = {}
        self.stats = {"requests": 0, "retries": 0, "reinit": 0}
        self._id = 0
        self._last_call = 0.0

    def __repr__(self) -> str:  # never leak the token through logs/tracebacks
        return f"McpClient(url={self.url!r}, token={'set' if self.token else 'missing'}, session={self.session_id!r})"

    # ---- low level
    def _headers(self, with_session: bool) -> dict:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": USER_AGENT,
        }
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if with_session and self.session_id:
            h["mcp-session-id"] = self.session_id
        if with_session and self.protocol_version:
            h["mcp-protocol-version"] = self.protocol_version
        return h

    def _send(self, payload: dict, *, with_session: bool = True) -> HttpResponse:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        attempt = 0
        while True:
            self.stats["requests"] += 1
            resp = None
            try:
                resp = self.transport(
                    "POST", self.url, self._headers(with_session), body, self.timeout
                )
            except (
                OSError,
                http.client.HTTPException,
            ) as e:  # URLError, timeouts, resets, bad status lines
                err = f"{type(e).__name__}: {e}"
            else:
                if resp.status not in RETRY_STATUS:
                    return resp
                err = f"HTTP {resp.status}"
            if attempt >= self.retries:
                raise McpError(
                    f"EUvsDisinfo MCP: brak poprawnej odpowiedzi po {attempt + 1} próbach "
                    f"({payload.get('method')}: {err})"
                )
            wait = self.backoff * (2**attempt) * (1 + 0.25 * random.random())
            ra = (resp.headers.get("retry-after", "") if resp is not None else "").strip()
            if ra.isdigit():
                wait = max(wait, min(float(ra), 120.0))
            log.warning(
                "EUvsDisinfo MCP: %s (%s) — retry %d/%d in %.1fs",
                payload.get("method"),
                err,
                attempt + 1,
                self.retries,
                wait,
            )
            self.stats["retries"] += 1
            self.sleep(wait)
            attempt += 1

    @staticmethod
    def _server_message(resp: HttpResponse) -> str:
        try:
            for m in parse_messages(resp.headers.get("content-type", ""), resp.body):
                if isinstance(m.get("error"), dict):
                    return str(m["error"].get("message", ""))[:300]
        except ValueError:
            pass
        return resp.body.decode("utf-8", "replace").strip()[:300]

    def _check_http(self, resp: HttpResponse, method: str) -> None:
        if resp.status in (401, 403):
            raise AuthError(
                f"EUvsDisinfo MCP odrzucił dostęp (HTTP {resp.status}): {self._server_message(resp)} "
                f"— sprawdź token w {TOKEN_ENV}"
            )
        if resp.status >= 400:
            msg = self._server_message(resp)
            if (
                method != "initialize"
                and self.session_id
                and (resp.status == 404 or (resp.status == 400 and "session" in msg.lower()))
            ):
                raise SessionExpired(msg or f"HTTP {resp.status}")
            raise McpError(f"EUvsDisinfo MCP: HTTP {resp.status} dla {method}: {msg}")

    def _request(self, method: str, params: Optional[dict]) -> dict:
        self._id += 1
        rid = self._id
        payload = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}
        resp = self._send(payload, with_session=method != "initialize")
        self._check_http(resp, method)
        if method == "initialize":
            self.session_id = resp.headers.get("mcp-session-id") or None  # None = stateless server
        msgs = parse_messages(resp.headers.get("content-type", ""), resp.body)
        replies = [m for m in msgs if "result" in m or "error" in m]
        msg = next((m for m in replies if m.get("id") == rid), replies[0] if replies else None)
        if msg is None:
            raise McpError(
                f"EUvsDisinfo MCP: brak odpowiedzi JSON-RPC na {method} "
                f"(HTTP {resp.status}, {len(resp.body)} B)"
            )
        if "error" in msg:
            e = msg["error"] if isinstance(msg["error"], dict) else {"message": str(msg["error"])}
            code, text = e.get("code"), str(e.get("message", ""))[:300]
            if code == -32001 or "unauthori" in text.lower():
                raise AuthError(
                    f"EUvsDisinfo MCP odrzucił dostęp ({code}): {text} — sprawdź token w {TOKEN_ENV}"
                )
            if method != "initialize" and "session" in text.lower():
                raise SessionExpired(text)
            raise McpError(f"EUvsDisinfo MCP: błąd {code} dla {method}: {text}")
        res = msg["result"]
        return res if isinstance(res, dict) else {"value": res}

    def request(self, method: str, params: Optional[dict] = None) -> dict:
        """JSON-RPC request -> `result`; re-initialises once if the server dropped our session."""
        try:
            return self._request(method, params)
        except SessionExpired as e:
            if method == "initialize":
                raise
            log.warning("EUvsDisinfo MCP: sesja wygasła (%s) — ponowna inicjalizacja", e)
            self.stats["reinit"] += 1
            self.session_id = None
            self.initialize()
            return self._request(method, params)

    def notify(self, method: str, params: Optional[dict] = None) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        if params:
            payload["params"] = params
        self._check_http(self._send(payload), method)  # expected: 202 Accepted, empty body

    # ---- MCP operations
    def initialize(self) -> dict:
        res = self._request(
            "initialize",
            {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO},
        )
        self.protocol_version = res.get("protocolVersion") or PROTOCOL_VERSION
        self.server_info = res.get("serverInfo") or {}
        self.notify("notifications/initialized")
        return res

    def list_tools(self) -> list[dict]:
        return self.request("tools/list").get("tools") or []

    def call_tool(self, name: str, arguments: dict) -> dict:
        """tools/call -> structuredContent (falls back to a JSON object inside content[].text)."""
        wait = self.delay - (time.monotonic() - self._last_call)
        if self._last_call and wait > 0:
            self.sleep(wait)
        self._last_call = time.monotonic()
        res = self.request("tools/call", {"name": name, "arguments": arguments})
        texts = [
            c.get("text", "")
            for c in res.get("content") or []
            if isinstance(c, dict) and c.get("type") == "text"
        ]
        if res.get("isError"):
            raise McpError(
                f"EUvsDisinfo MCP: narzędzie {name} zwróciło błąd: {' '.join(texts)[:300]}"
            )
        sc = res.get("structuredContent")
        if isinstance(sc, dict):
            return sc
        for t in texts:
            try:
                obj = json.loads(t)
            except ValueError:
                continue
            if isinstance(obj, dict):
                return obj
        raise McpError(
            f"EUvsDisinfo MCP: {name} — odpowiedź bez structuredContent ({' '.join(texts)[:120]})"
        )

    def iter_items(
        self, kind: str, *, page_size: int = MAX_PAGE, offset: int = 0
    ) -> Iterator[dict]:
        """All items of `cases` / `articles`, page by page (offset += len(page)) until hasNextPage is false."""
        if kind not in KINDS:
            raise ValueError(f"unknown kind {kind!r} (expected one of {KINDS})")
        page_size = max(1, min(int(page_size), MAX_PAGE))
        prev_first = None
        while True:
            sc = self.call_tool(kind, {"offset": offset, "limit": page_size})
            items = [x for x in (sc.get(kind) or []) if isinstance(x, dict)]
            total = sc.get("total")
            if isinstance(total, int):
                self.totals[kind] = total
            first = items[0].get("id") if items else None
            if first is not None and first == prev_first:
                raise McpError(
                    f"EUvsDisinfo MCP: {kind} offset {offset} zwrócił tę samą stronę — przerwano"
                )
            prev_first = first
            yield from items
            offset += len(items)
            log.info("EUvsDisinfo MCP: %s %d/%s", kind, offset, total if total is not None else "?")
            if (
                not items
                or sc.get("hasNextPage") is False
                or (isinstance(total, int) and offset >= total)
            ):
                return

    def close(self) -> None:
        """Best-effort session termination (HTTP DELETE, MCP spec); errors are ignored."""
        if not self.session_id:
            return
        try:
            self.transport("DELETE", self.url, self._headers(True), None, min(self.timeout, 10.0))
        except Exception:  # noqa: BLE001
            pass
        self.session_id = None


# --------------------------------------------------------------------------- text helpers
_BLOCK_TAGS = {
    "p",
    "div",
    "br",
    "li",
    "ul",
    "ol",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "tr",
    "table",
    "section",
    "article",
    "figure",
    "figcaption",
    "hr",
    "pre",
    "dd",
    "dt",
}
_SKIP_TAGS = {"script", "style", "noscript", "iframe", "svg"}
_SHORTCODE = re.compile(
    r"\[/?(?:caption|embed|video|audio|gallery|vc_[a-z_]+|et_pb_[a-z_]+)[^\]]*\]", re.I
)
_SKIP_LINES = (
    "Read similar",
    "See other examples",
    "Przeczytaj podobne",
    "Zobacz podobne",
    "Przeczytaj inne",
    "Przeczytaj też",
)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self.skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def strip_html(s: Optional[str]) -> str:
    """HTML/WordPress content -> plain text, one paragraph per line, 'Read similar' boilerplate dropped."""
    if not s:
        return ""
    s = _SHORTCODE.sub(" ", str(s))
    if "<" in s or "&" in s:
        p = _TextExtractor()
        p.feed(s)
        p.close()
        s = "".join(p.parts)
    lines = (" ".join(ln.split()) for ln in s.replace("\r", "").replace("\xa0", " ").split("\n"))
    return "\n".join(ln for ln in lines if ln and not ln.startswith(_SKIP_LINES))


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def to_date(v) -> Optional[str]:
    """Unix seconds/ms, 'YYYY-MM-DD hh:mm:ss' or ISO -> 'YYYY-MM-DD' (UTC)."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) or (isinstance(v, str) and re.fullmatch(r"\d{9,13}", v.strip())):
        ts = float(v)
        if ts > 1e11:  # milliseconds
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(v))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _titles(items) -> list[str]:
    out: list[str] = []
    for it in items or []:
        t = (
            it
            if isinstance(it, str)
            else (it.get("title") or it.get("name") or "") if isinstance(it, dict) else ""
        )
        t = " ".join(strip_html(t).split())
        if t and t not in out:
            out.append(t)
    return out


def _host(url) -> Optional[str]:
    try:
        h = (urlparse(str(url or "")).hostname or "").lower()
    except ValueError:
        return None
    h = h.removeprefix("www.")
    return h if h and h not in ARCHIVE_HOSTS else None


def _uniq(xs: list[str]) -> list[str]:
    return list(dict.fromkeys(x for x in xs if x))


# --------------------------------------------------------------------------- mapping -> corpus records
_REPORT_SLUG = re.compile(r"/report/([^/?#]+)")


def case_to_record(c: dict, retrieved_at: Optional[str] = None) -> Optional[dict]:
    m = _REPORT_SLUG.search(str(c.get("url") or ""))
    fact = strip_html(c.get("fact"))
    if (
        not m or not fact
    ):  # no citeable report page / no disproof -> useless (or harmful) as evidence
        return None
    slug = m.group(1)
    claim = strip_html(c.get("claim"))
    if len(claim) > 1200:
        claim = claim[:1200].rsplit(" ", 1)[0] + " […]"
    title = re.sub(r"^\s*DISINFO:\s*", "", " ".join(strip_html(c.get("title")).split()))
    outlets = _uniq(
        [
            _host(link.get("url"))
            for link in c.get("linksToDisinformation") or []
            if isinstance(link, dict)
        ]
    )
    tags = (
        ["euvsdisinfo", "pro-kremlin-disinformation"]
        + _titles(c.get("keywords"))
        + ["kraj:" + x for x in _titles(c.get("countries"))]
        + ["via:mcp"]
    )
    url = str(c["url"]).strip().replace("http://", "https://", 1)
    return {
        "id": f"{SOURCE_ID}:{slug}",
        "source_type": "incident",
        "publisher": PUBLISHER,
        "domain": DOMAIN,
        "url": url,
        "title": title or claim[:140] or slug,
        "published_at": to_date(c.get("date")),
        "retrieved_at": retrieved_at or now_iso(),
        "language": "en",
        "license": LICENSE_MCP,
        "text": fact[:MAX_TEXT],
        "claim": claim or None,
        "claim_author": ", ".join(outlets[:5]) or None,
        "verdict_raw": VERDICT_RAW,
        "verdict": "false",
        "tags": _uniq(tags),
    }


def _article_language(a: dict, path: str) -> str:
    langs = _titles(
        [{"title": x.get("slug")} for x in a.get("articleLanguage") or [] if isinstance(x, dict)]
    )
    if langs:
        return langs[0].lower()
    first = path.split("/", 1)[0]
    return (
        first if re.fullmatch(r"[a-z]{2}", first) else "en"
    )  # untranslated pages live at the root (English)


def article_to_record(a: dict, retrieved_at: Optional[str] = None) -> Optional[dict]:
    url = str(a.get("url") or "").strip().replace("http://", "https://", 1)
    path = urlparse(url).path.strip("/") if url.startswith("https://") else ""
    text = strip_html(a.get("content"))
    if not path or not text:
        return None
    title = " ".join(strip_html(a.get("title")).split())
    tags = (
        ["euvsdisinfo", "euvsdisinfo-analysis"]
        + _titles(a.get("keywords"))
        + ["kategoria:" + x for x in _titles(a.get("categories"))]
        + ["via:mcp"]
    )
    return {
        "id": f"{SOURCE_ID}:article/{path}",
        "source_type": "factcheck",
        "publisher": PUBLISHER,
        "domain": DOMAIN,
        "url": url,
        "title": title or path.rsplit("/", 1)[-1],
        "published_at": to_date(a.get("dateGmt") or a.get("date")),
        "retrieved_at": retrieved_at or now_iso(),
        "language": _article_language(a, path),
        "license": LICENSE_MCP,
        "text": text[:MAX_TEXT],
        "claim": None,
        "claim_author": None,
        "verdict_raw": None,
        "verdict": None,
        "tags": _uniq(tags),
    }


# --------------------------------------------------------------------------- raw dump
class _RawDump:
    """data/raw/euvsdisinfo_mcp/<kind>.jsonl.gz, written atomically; the previous dump survives failed runs.
    A run cut short by max_records writes <kind>.sample.jsonl.gz instead of replacing the full dump.
    """

    def __init__(self, raw_dir: Optional[Path], kind: str):
        self.raw_dir, self.kind, self.n, self._fh = raw_dir, kind, 0, None
        if raw_dir:
            raw_dir.mkdir(parents=True, exist_ok=True)
            self._tmp = raw_dir / f".{kind}.jsonl.gz.tmp"
            self._fh = gzip.open(self._tmp, "wt", encoding="utf-8")

    def write(self, item: dict) -> None:
        if self._fh:
            self._fh.write(json.dumps(item, ensure_ascii=False) + "\n")
            self.n += 1

    def finish(self, ok: bool, complete: bool) -> Optional[Path]:
        if not self._fh:
            return None
        self._fh.close()
        if not ok:
            self._tmp.unlink(missing_ok=True)
            return None
        dest = self.raw_dir / (
            f"{self.kind}.jsonl.gz" if complete else f"{self.kind}.sample.jsonl.gz"
        )
        os.replace(self._tmp, dest)
        return dest


# --------------------------------------------------------------------------- registry handler
def _as_list(v, default: list) -> list:
    if v is None or v == "" or v == []:
        return list(default)
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return list(v)


def fetch(
    source: dict,
    *,
    transport: Optional[Transport] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict]:
    """Registry contract: fetch(source) -> corpus records (SourceDoc dicts).

    source["params"]: kinds (["cases","articles"]), since ("2023-01-01"; null = no date filter), max_records
    (total cap, null = all), article_languages (["pl","en"]), optional countries (keep only cases tagged with one
    of them), page_size (100), delay (1.0 s between calls), endpoint, token_env, raw_dir, raw_dump (true).
    Raises MissingToken / AuthError / McpError (the scheduler keeps the previous corpus file on failure).
    """
    p = {**DEFAULT_PARAMS, **(source.get("params") or {})}
    token_env = p.get("token_env") or TOKEN_ENV
    token = os.environ.get(token_env, "").strip()
    if not token:
        raise MissingToken(
            f"brak tokenu: ustaw zmienną środowiskową {token_env} (EUvsDisinfo MCP) "
            "— źródło pominięte"
        )
    kinds = _as_list(p.get("kinds"), list(KINDS))
    bad = [k for k in kinds if k not in KINDS]
    if bad:
        raise McpError(f"EUvsDisinfo MCP: nieznane kinds {bad} (dozwolone: {list(KINDS)})")
    since = str(p["since"])[:10] if p.get("since") else None
    max_records = int(p["max_records"]) if p.get("max_records") else None
    langs = {x.lower() for x in _as_list(p.get("article_languages"), ["pl", "en"])}
    countries = {x.lower() for x in _as_list(p.get("countries"), [])}
    raw_dir = None if p.get("raw_dump") is False else Path(p.get("raw_dir") or RAW_DIR)

    client = McpClient(
        token,
        p.get("endpoint") or ENDPOINT,
        transport=transport,
        sleep=sleep,
        delay=float(p.get("delay", 1.0)),
        timeout=float(p.get("timeout", 60)),
        retries=int(p.get("retries", 4)),
    )
    retrieved_at = now_iso()
    out: list[dict] = []
    seen: set[str] = set()
    stats: dict[str, dict] = {}
    try:
        client.initialize()
        for kind in kinds:
            st = stats[kind] = {
                "fetched": 0,
                "kept": 0,
                "invalid": 0,
                "too_old": 0,
                "language": 0,
                "country": 0,
                "duplicate": 0,
            }
            if max_records and len(out) >= max_records:
                break
            dump, ok, capped = _RawDump(raw_dir, kind), False, False
            try:
                for item in client.iter_items(kind, page_size=int(p.get("page_size", MAX_PAGE))):
                    st["fetched"] += 1
                    dump.write(item)
                    rec = (
                        case_to_record(item, retrieved_at)
                        if kind == "cases"
                        else article_to_record(item, retrieved_at)
                    )
                    if rec is None:
                        st["invalid"] += 1
                    elif since and (rec["published_at"] or "") < since:
                        st["too_old"] += 1
                    elif kind == "articles" and langs and rec["language"] not in langs:
                        st["language"] += 1
                    elif (
                        kind == "cases"
                        and countries
                        and not countries
                        & {t[5:].lower() for t in rec["tags"] if t.startswith("kraj:")}
                    ):
                        st["country"] += 1
                    elif rec["id"] in seen:
                        st["duplicate"] += 1
                    else:
                        seen.add(rec["id"])
                        out.append(rec)
                        st["kept"] += 1
                        if max_records and len(out) >= max_records:
                            capped = True
                            break
                ok = True
            finally:
                st["raw_dump"] = str(dump.finish(ok, complete=not capped) or "")
            log.info("EUvsDisinfo MCP: %s %s", kind, st)
    finally:
        client.close()
    if raw_dir:
        try:
            (raw_dir / "last_run.json").write_text(
                json.dumps(
                    {
                        "finished_at": now_iso(),
                        "endpoint": client.url,
                        "server": client.server_info,
                        "protocol_version": client.protocol_version,
                        "totals": client.totals,
                        "stats": stats,
                        "http": client.stats,
                        "records": len(out),
                        "params": {
                            k: v
                            for k, v in p.items()
                            if k in DEFAULT_PARAMS or k in ("countries", "page_size")
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as e:
            log.warning("EUvsDisinfo MCP: last_run.json not written: %s", e)
    return out


# --------------------------------------------------------------------------- CLI
def _registry_params(path: Path) -> dict:
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")).get("params") or {})
    except (OSError, ValueError):
        return {}


def probe(url: str = ENDPOINT) -> int:
    """initialize + tools/list + 1 case + 1 article (+ the last item, to show the ordering). Exit code 0/1/2/3."""
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        print(
            f"brak tokenu: {TOKEN_ENV} nie jest ustawiony — sprawdzam tylko osiągalność serwera {url}"
        )
        try:
            McpClient(None, url, retries=1, backoff=1.0).initialize()
        except AuthError as e:
            print(f"  serwer osiągalny, bez tokenu odpowiada zgodnie z oczekiwaniem: {e}")
            return 2
        except McpError as e:
            print(f"  serwer nieosiągalny: {e}")
            return 1
        print("  UWAGA: serwer przyjął initialize bez tokenu")
        return 0
    c = McpClient(token, url)
    try:
        init = c.initialize()
        print(
            f"serwer: {c.server_info.get('name')} {c.server_info.get('version')} | protokół "
            f"{init.get('protocolVersion')} | sesja {(c.session_id or 'brak (bezstanowy)')[:8]}…"
        )
        for t in c.list_tools():
            props = (t.get("inputSchema") or {}).get("properties") or {}
            print(
                f"narzędzie {t.get('name')}: {t.get('description')} | argumenty: "
                + ", ".join(
                    f"{k}({v.get('type')}{', max ' + str(v['maximum']) if 'maximum' in v else ''})"
                    for k, v in props.items()
                )
            )
        for kind in KINDS:
            sc = c.call_tool(kind, {"offset": 0, "limit": 1})
            items, total = sc.get(kind) or [], sc.get("total")
            print(
                f"\n{kind}: total={total} hasNextPage={sc.get('hasNextPage')} totalPages={sc.get('totalPages')}"
            )
            if not items:
                continue
            print(f"  pola: {sorted(items[0])}")
            rec = (case_to_record if kind == "cases" else article_to_record)(items[0])
            if rec:
                print(
                    f"  -> {rec['id']} | {rec['published_at']} | {rec['language']} | {rec['title'][:80]!r} | "
                    f"text {len(rec['text'])} zn. | tags {rec['tags'][:6]}"
                )
            else:
                print("  -> rekord pominięty (brak url /report/ lub treści)")
            if isinstance(total, int) and total > 1:
                last = (c.call_tool(kind, {"offset": total - 1, "limit": 1}).get(kind) or [{}])[0]
                d0 = to_date(items[0].get("date") or items[0].get("dateGmt"))
                d1 = to_date(last.get("date") or last.get("dateGmt"))
                print(f"  kolejność: offset 0 = {d0}, offset {total - 1} = {d1}")
    except AuthError as e:
        print(f"błąd autoryzacji: {e}")
        return 3
    except McpError as e:
        print(f"błąd: {e}")
        return 1
    finally:
        c.close()
    print(f"\nOK ({c.stats['requests']} żądań)")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m prawdowid.source_handlers.euvsdisinfo_mcp",
        description=f"EUvsDisinfo MCP client (token from env {TOKEN_ENV}).",
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--probe", action="store_true", help="initialize + tools/list + 1 case + 1 article"
    )
    g.add_argument(
        "--dump", nargs=2, metavar=("N", "OUT"), help="fetch up to N records (0 = all) to OUT.jsonl"
    )
    ap.add_argument("--kinds", help="cases,articles")
    ap.add_argument("--since", help="YYYY-MM-DD; empty string = no date filter")
    ap.add_argument("--languages", help="article languages, e.g. pl,en")
    ap.add_argument("--countries", help="keep only cases tagged with these countries, e.g. Poland")
    ap.add_argument("--no-raw", action="store_true", help=f"do not write the raw dump to {RAW_DIR}")
    ap.add_argument("--endpoint", default=ENDPOINT)
    ap.add_argument(
        "--registry", default=str(REGISTRY_FILE), help="registry file whose params are the defaults"
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if a.verbose or a.dump else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    if a.probe:
        return probe(a.endpoint)

    params = _registry_params(Path(a.registry))
    params.update({"max_records": int(a.dump[0]) or None, "endpoint": a.endpoint})
    for key, val in (
        ("kinds", a.kinds),
        ("article_languages", a.languages),
        ("countries", a.countries),
    ):
        if val:
            params[key] = val
    if a.since is not None:
        params["since"] = a.since or None
    if a.no_raw:
        params["raw_dump"] = False
    try:
        recs = fetch({"id": "euvsdisinfo_mcp", "params": params})
    except MissingToken as e:
        print(e, file=sys.stderr)
        return 2
    except AuthError as e:
        print(e, file=sys.stderr)
        return 3
    except McpError as e:
        print(e, file=sys.stderr)
        return 1
    out = Path(a.dump[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(recs)} rekordów -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
