"""Source registry: one human-readable JSON file per source in data/sources/<id>.json.

The data contract is docs/SOURCE_REGISTRY.md. This module loads, validates and saves those files and answers
the question "which corpus files should the index load?" (enabled sources + files without a registry entry).
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from ..config import settings

log = logging.getLogger("prawdowid.sources")

ID_RE = re.compile(r"^[a-z0-9_]{2,64}$")
HANDLER_RE = re.compile(r"^[a-z0-9_]{1,64}$")
SCRIPT_RE = re.compile(r"^ingest/[A-Za-z0-9_\-]+\.py$")

CATEGORIES = ("official", "factcheck", "incident", "media")
DEFAULT_TIER = {"official": 1, "factcheck": 2, "incident": 3, "media": 4}
FETCH_METHODS = ("rss", "sitemap", "html_list", "govpl_list", "custom", "legacy_script")  # run by the scheduler
NOOP_METHODS = ("live_search", "google_factcheck", "reference_only")                    # never fetched on schedule
METHODS = FETCH_METHODS + NOOP_METHODS
TOPICS = ("podroze", "pogoda", "woda_powodz", "drogi", "kolej", "lotnictwo", "morze", "transport", "zdrowie",
          "zywnosc", "promieniowanie", "powietrze", "cyber", "oszustwa", "bezpieczenstwo", "obronnosc", "pozary",
          "prawo", "statystyka", "finanse", "wybory", "ue", "dezinformacja", "zagranica", "rzad")
FIELD_ORDER = ("id", "name", "publisher", "url", "category", "tier", "method", "params", "enabled", "schedule_hours",
               "web_search", "topics", "language", "license", "qualification", "added_by", "added_at")
DEFAULT_MAX_DOCS = 500

# params per method: name -> (type, required, default). Unknown params are kept (custom handlers use them).
PARAM_SPEC: dict[str, dict[str, tuple[type | tuple, bool, object]]] = {
    "rss": {"feed_url": (str, True, None), "max_items": (int, False, 30), "fetch_full_text": (bool, False, True)},
    "sitemap": {"sitemap_url": (str, True, None), "url_regex": (str, False, ""), "max_items": (int, False, 30),
                "date_regex": (str, False, None)},
    "html_list": {"list_urls": (list, True, None), "link_regex": (str, True, None), "max_items": (int, False, 30),
                  "min_text_chars": (int, False, 300), "date_regex": (str, False, None)},
    "govpl_list": {"list_url": (str, True, None), "max_items": (int, False, 30)},
    "custom": {"handler": (str, True, None)},
    "legacy_script": {"script": (str, True, None), "args": (list, False, []), "timeout_s": (int, False, 3600)},
}
COMMON_PARAMS = {"max_docs": (int, False, DEFAULT_MAX_DOCS),   # cap on records kept in data/corpus/<id>.jsonl
                 "max_chars": (int, False, None),               # cap on stored text per record (default 4000)
                 "delay_s": ((int, float), False, None)}        # min. seconds between requests to one host (≥ 1)


class SourceError(ValueError):
    """Validation error; `errors` holds human-readable (Polish) messages, one per problem."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def sources_dir() -> Path:
    return settings.sources_dir


def path_for(source_id: str) -> Path:
    if not ID_RE.match(source_id or ""):
        raise SourceError([f"Niepoprawny identyfikator źródła: {source_id!r} (dozwolone: a-z, 0-9, _)."])
    return sources_dir() / f"{source_id}.json"


def corpus_path(source_id: str) -> Path:
    return settings.corpus_dir / f"{source_id}.jsonl"


def _is_http_url(u: object) -> bool:
    if not isinstance(u, str):
        return False
    p = urlparse(u)
    return p.scheme in ("http", "https") and bool(p.hostname)


def _check_regex(errors: list[str], name: str, value: str) -> None:
    try:
        re.compile(value)
    except re.error as e:
        errors.append(f"params.{name}: niepoprawne wyrażenie regularne ({e}).")


def validate(raw: dict, *, strict: bool = True) -> dict:
    """Return a normalised copy (contract field order, defaults filled) or raise SourceError.

    strict=False (used when loading files written by hand or by other tools) tolerates unknown topics.
    """
    if not isinstance(raw, dict):
        raise SourceError(["Opis źródła musi być obiektem JSON."])
    e: list[str] = []
    d = dict(raw)
    sid = d.get("id")
    if not isinstance(sid, str) or not ID_RE.match(sid):
        e.append("id: wymagany, 2–64 znaki: małe litery, cyfry, podkreślnik (np. kgpsp_aktualnosci).")
    for k in ("name", "publisher"):
        if not isinstance(d.get(k), str) or not d[k].strip():
            e.append(f"{k}: pole wymagane.")
    if not _is_http_url(d.get("url")):
        e.append("url: wymagany adres http(s) strony wejściowej.")
    cat = d.get("category")
    if cat not in CATEGORIES:
        e.append(f"category: jedna z {', '.join(CATEGORIES)}.")
    tier = d.get("tier", DEFAULT_TIER.get(cat, 4))
    if isinstance(tier, bool) or not isinstance(tier, int) or tier not in (1, 2, 3, 4):
        e.append("tier: liczba 1–4.")
    d["tier"] = tier
    method = d.get("method")
    if method not in METHODS:
        e.append(f"method: jedna z {', '.join(METHODS)}.")
    params = d.get("params") or {}
    if not isinstance(params, dict):
        e.append("params: musi być obiektem JSON.")
        params = {}
    params = dict(params)
    spec = {**PARAM_SPEC.get(method, {}), **COMMON_PARAMS}
    for name, (typ, required, default) in spec.items():
        if name not in params or params[name] in (None, ""):
            if required:
                e.append(f"params.{name}: wymagany dla metody {method}.")
            elif default is not None and name != "max_docs":
                params[name] = default
            continue
        v = params[name]
        if (typ is int and (isinstance(v, bool) or not isinstance(v, int))) or not isinstance(v, typ):
            e.append(f"params.{name}: zły typ (oczekiwano {getattr(typ, '__name__', 'liczby')}).")
        elif typ is int and v < 0:
            e.append(f"params.{name}: wartość nie może być ujemna.")
    if method == "rss" and params.get("feed_url") and not _is_http_url(params["feed_url"]):
        e.append("params.feed_url: adres http(s).")
    if method == "sitemap":
        if params.get("sitemap_url") and not _is_http_url(params["sitemap_url"]):
            e.append("params.sitemap_url: adres http(s).")
        if params.get("url_regex"):
            _check_regex(e, "url_regex", params["url_regex"])
    if method == "html_list":
        lu = params.get("list_urls")
        if isinstance(lu, list) and (not lu or not all(_is_http_url(u) for u in lu)):
            e.append("params.list_urls: niepusta lista adresów http(s).")
        if isinstance(params.get("link_regex"), str):
            _check_regex(e, "link_regex", params["link_regex"])
    if method in ("sitemap", "html_list") and isinstance(params.get("date_regex"), str) and params["date_regex"]:
        _check_regex(e, "date_regex", params["date_regex"])
    if method == "govpl_list" and params.get("list_url"):
        p = urlparse(params["list_url"])
        if p.scheme != "https" or p.hostname not in ("www.gov.pl", "gov.pl"):
            e.append("params.list_url: metoda govpl_list działa tylko dla stron https://www.gov.pl/web/…")
    if method == "custom" and isinstance(params.get("handler"), str) and not HANDLER_RE.match(params["handler"]):
        e.append("params.handler: nazwa modułu (a-z, 0-9, _).")
    if method == "legacy_script" and isinstance(params.get("script"), str):
        if not SCRIPT_RE.match(params["script"]):
            e.append("params.script: ścieżka w katalogu ingest/, np. ingest/official_gus.py.")
        elif not (settings.root / params["script"]).is_file():
            e.append(f"params.script: plik {params['script']} nie istnieje.")
        if not all(isinstance(a, str) for a in params.get("args") or []):
            e.append("params.args: lista napisów.")
    d["params"] = params
    for k, default in (("enabled", False), ("web_search", False)):
        v = d.get(k, default)
        if not isinstance(v, bool):
            e.append(f"{k}: true albo false.")
        d[k] = v
    sh = d.get("schedule_hours", 0)
    if isinstance(sh, bool) or not isinstance(sh, (int, float)) or sh < 0:
        e.append("schedule_hours: liczba ≥ 0 (0 = tylko ręcznie).")
    d["schedule_hours"] = sh
    topics = d.get("topics") or []
    if not isinstance(topics, list) or not all(isinstance(t, str) for t in topics):
        e.append("topics: lista tematów.")
        topics = []
    unknown = [t for t in topics if t not in TOPICS]
    if unknown and strict:
        e.append(f"topics: nieznane tematy {', '.join(unknown)} (słownik w docs/SOURCE_REGISTRY.md).")
    d["topics"] = list(dict.fromkeys(topics))
    d["language"] = d.get("language") or "pl"
    if not isinstance(d["language"], str) or not re.match(r"^[a-z]{2}$", d["language"]):
        e.append("language: kod języka ISO 639-1, np. pl.")
    for k in ("license", "qualification"):
        if not isinstance(d.get(k), str) or not d[k].strip():
            e.append(f"{k}: pole wymagane — źródło bez opisu licencji i kwalifikacji nie może być dodane.")
    d["added_by"] = str(d.get("added_by") or "administrator")
    d["added_at"] = str(d.get("added_at") or date.today().isoformat())
    if e:
        raise SourceError(e)
    ordered = {k: d[k] for k in FIELD_ORDER if k in d}
    ordered.update({k: v for k, v in d.items() if k not in ordered and not k.startswith("_")})  # keep extra keys
    return ordered


# ------------------------------------------------------------------ load / save
def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_all() -> tuple[dict[str, dict], dict[str, list[str]]]:
    """All registry entries. Returns (sources by id, problems by id). Invalid files are reported, never fatal."""
    out: dict[str, dict] = {}
    problems: dict[str, list[str]] = {}
    d = sources_dir()
    if not d.is_dir():
        return out, problems
    for f in sorted(d.glob("*.json")):
        sid = f.stem
        try:
            raw = _read(f)
        except (OSError, json.JSONDecodeError) as ex:
            problems[sid] = [f"Plik nie jest poprawnym JSON: {ex}"]
            continue
        try:
            src = validate(raw, strict=False)
            if src["id"] != sid:
                raise SourceError([f"id ({src['id']}) różni się od nazwy pliku ({sid}.json)."])
            out[sid] = src
        except SourceError as ex:
            problems[sid] = ex.errors
            if isinstance(raw, dict):
                out[sid] = {**raw, "id": sid}  # keep it visible in the admin panel; never scheduled
    return out, problems


def get(source_id: str) -> dict | None:
    p = path_for(source_id)
    if not p.exists():
        return None
    raw = _read(p)
    try:
        return validate(raw, strict=False)
    except SourceError:
        return {**raw, "id": source_id}


def exists(source_id: str) -> bool:
    return path_for(source_id).exists()


def save(source: dict, *, strict: bool = True) -> dict:
    """Validate and write atomically (tmp file + rename). Returns the normalised source."""
    src = validate(source, strict=strict)
    p = path_for(src["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{src['id']}.", suffix=".tmp", dir=p.parent)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(src, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, p)
    return src


def delete(source_id: str) -> bool:
    p = path_for(source_id)
    if not p.exists():
        return False
    p.unlink()
    return True


# ------------------------------------------------------------------ index filter
def corpus_files_for_index(corpus_dir: Path | None = None) -> tuple[list[Path], list[str]]:
    """Corpus files the index should load: enabled registry sources + files with no registry entry.

    Returns (files to load, names of excluded files). Reads only the `enabled` flag, so a registry file with
    other validation problems still controls whether its corpus is indexed.
    """
    corpus_dir = corpus_dir or settings.corpus_dir
    enabled: dict[str, bool] = {}
    d = sources_dir()
    if d.is_dir():
        for f in d.glob("*.json"):
            try:
                enabled[f.stem] = _read(f).get("enabled") is True
            except Exception:  # noqa: BLE001 — unreadable registry file: keep the corpus visible
                continue
    keep, skip = [], []
    for f in sorted(corpus_dir.glob("*.jsonl")):
        if enabled.get(f.stem, True):
            keep.append(f)
        else:
            skip.append(f.name)
    return keep, skip


def count_docs(source_id: str) -> int:
    p = corpus_path(source_id)
    if not p.exists():
        return 0
    with p.open("rb") as fh:
        return sum(1 for line in fh if line.strip())
