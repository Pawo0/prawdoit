"""Admin API for the source registry + the /admin page. Token-protected (X-Admin-Token, env PRAWDOWID_ADMIN_TOKEN).

Every change is written to data/sources/<id>.json (the contract, docs/SOURCE_REGISTRY.md) and to the
source_changes audit table (who/when/what). Fetching never blocks a request except for the 3-record dry run.
"""
from __future__ import annotations

import hmac
import logging
import shutil
from datetime import datetime, timezone
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse

from .config import settings
from .sources import fetchers, registry, scheduler, state

log = logging.getLogger("prawdowid.admin")

router = APIRouter()

def require_admin(x_admin_token: str | None = Header(default=None), x_admin_user: str | None = Header(default=None)) -> str:
    if not x_admin_token or not hmac.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(401, "Wymagany token administratora (nagłówek X-Admin-Token).")
    who = unquote(x_admin_user or "").strip()[:60]  # the panel sends it URL-encoded (headers are latin-1)
    return who or "administrator"


def _bad(e: registry.SourceError) -> HTTPException:
    return HTTPException(422, {"message": "Popraw pola formularza.", "errors": e.errors})


def _overview() -> list[dict]:
    sources, problems = registry.load_all()
    runs = state.last_runs()
    cur = scheduler.current()
    out = []
    for sid, s in sources.items():
        nd = scheduler.next_due(s, problems.get(sid))
        out.append({
            **s,
            "problems": problems.get(sid, []),
            "docs": registry.count_docs(sid),
            "last_run": runs.get(sid),
            "next_run": nd.isoformat(timespec="minutes") if nd else None,
            "running": cur.get("source_id") == sid,
        })
    return out


# ------------------------------------------------------------------ page
@router.get("/admin", include_in_schema=False)
def page_admin():
    return FileResponse(settings.web_dir / "admin.html", media_type="text/html")


@router.on_event("startup")
def _start_scheduler() -> None:
    if scheduler.start():
        log.info("source scheduler enabled (PRAWDOWID_SCHEDULER=0 to disable)")


# ------------------------------------------------------------------ read
@router.get("/api/admin/sources")
def admin_sources(who: str = Depends(require_admin)):
    from .index import INDEX

    return {"sources": _overview(), "scheduler": scheduler.status(),
            "vocab": {"categories": registry.CATEGORIES, "methods": registry.METHODS, "topics": registry.TOPICS,
                      "params": {m: {k: {"required": v[1], "default": v[2]} for k, v in spec.items()}
                                 for m, spec in registry.PARAM_SPEC.items()}},
            "index": {"documents": INDEX.stats.get("documents"), "loaded_at": INDEX.loaded_at,
                      "excluded_files": INDEX.stats.get("excluded_files", [])}}


@router.get("/api/admin/sources/{source_id}")
def admin_get(source_id: str, who: str = Depends(require_admin)):
    src = _get_or_404(source_id)
    return {"source": src, "docs": registry.count_docs(source_id), "runs": state.recent_runs(20, source_id),
            "changes": state.recent_changes(20, source_id)}


@router.get("/api/admin/runs")
def admin_runs(limit: int = 50, source_id: str | None = None, who: str = Depends(require_admin)):
    return {"runs": state.recent_runs(min(limit, 500), source_id), "scheduler": scheduler.status()}


@router.get("/api/admin/changes")
def admin_changes(limit: int = 50, who: str = Depends(require_admin)):
    return {"changes": state.recent_changes(min(limit, 500))}


def _get_or_404(source_id: str) -> dict:
    try:
        src = registry.get(source_id)
    except registry.SourceError as e:
        raise _bad(e) from e
    if not src:
        raise HTTPException(404, "Nie ma takiego źródła.")
    return src


# ------------------------------------------------------------------ write
@router.post("/api/admin/sources", status_code=201)
def admin_create(body: dict, who: str = Depends(require_admin)):
    body = {k: v for k, v in body.items() if not k.startswith("_")}
    sid = str(body.get("id") or "")
    try:
        if registry.ID_RE.match(sid) and registry.exists(sid):
            raise HTTPException(409, "Źródło o tym identyfikatorze już istnieje — wybierz inny id albo edytuj istniejące.")
        body.setdefault("added_by", who)
        body.setdefault("added_at", datetime.now(timezone.utc).date().isoformat())
        src = registry.save(body)
    except registry.SourceError as e:
        raise _bad(e) from e
    state.log_change(who, src["id"], "create", None, src)
    scheduler.reload_async()
    return {"source": src}


@router.put("/api/admin/sources/{source_id}")
def admin_update(source_id: str, body: dict, who: str = Depends(require_admin)):
    before = _get_or_404(source_id)
    merged = {**before, **{k: v for k, v in body.items() if not k.startswith("_")}, "id": source_id}
    merged["added_by"], merged["added_at"] = before.get("added_by"), before.get("added_at")
    try:
        src = registry.save(merged, strict=set(merged.get("topics") or []) != set(before.get("topics") or []))
    except registry.SourceError as e:
        raise _bad(e) from e
    state.log_change(who, source_id, "update", before, src)
    if before.get("enabled") != src.get("enabled"):
        scheduler.reload_async()
    return {"source": src}


def _set_enabled(source_id: str, value: bool, who: str) -> dict:
    before = _get_or_404(source_id)
    try:
        src = registry.save({**before, "enabled": value}, strict=False)
    except registry.SourceError as e:
        raise _bad(e) from e
    state.log_change(who, source_id, "enable" if value else "disable", before, src)
    scheduler.reload_async()
    return {"source": src, "message": "Indeks zostanie przeładowany w tle."}


@router.post("/api/admin/sources/{source_id}/enable")
def admin_enable(source_id: str, who: str = Depends(require_admin)):
    return _set_enabled(source_id, True, who)


@router.post("/api/admin/sources/{source_id}/disable")
def admin_disable(source_id: str, who: str = Depends(require_admin)):
    return _set_enabled(source_id, False, who)


@router.delete("/api/admin/sources/{source_id}")
def admin_delete(source_id: str, who: str = Depends(require_admin)):
    before = _get_or_404(source_id)
    archived = None
    corpus = registry.corpus_path(source_id)
    if corpus.exists():  # otherwise the file would be indexed as "corpus without a registry entry"
        arch = settings.corpus_dir / "archive"
        arch.mkdir(exist_ok=True)
        dest = arch / f"{source_id}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.jsonl"
        shutil.move(str(corpus), dest)
        archived = str(dest.relative_to(settings.root)) if dest.is_relative_to(settings.root) else str(dest)
    registry.delete(source_id)
    state.log_change(who, source_id, "delete", before, None)
    scheduler.reload_async()
    return {"deleted": source_id, "corpus_archived_to": archived}


# ------------------------------------------------------------------ actions
@router.post("/api/admin/test")
def admin_test_config(body: dict, who: str = Depends(require_admin)):
    """Dry run of an unsaved config from the form (3 sample records, nothing written)."""
    body = {k: v for k, v in body.items() if not k.startswith("_")}
    for k, default in (("id", "test_zrodla"), ("name", "test"), ("publisher", "test"), ("license", "?"),
                       ("qualification", "?"), ("category", "media")):
        body[k] = body.get(k) or default
    body["url"] = body.get("url") or next((v for v in (body.get("params") or {}).values()
                                           if isinstance(v, str) and v.startswith("http")), "https://example.org/")
    try:
        src = registry.validate(body, strict=False)
    except registry.SourceError as e:
        raise _bad(e) from e
    return fetchers.test_source(src)


@router.post("/api/admin/sources/{source_id}/test")
def admin_test(source_id: str, who: str = Depends(require_admin)):
    return fetchers.test_source(_get_or_404(source_id))


@router.post("/api/admin/sources/{source_id}/run", status_code=202)
def admin_run(source_id: str, who: str = Depends(require_admin)):
    src = _get_or_404(source_id)
    if src.get("method") in registry.NOOP_METHODS:
        raise HTTPException(422, f"Metoda {src['method']} nie pobiera dokumentów.")
    cur = scheduler.current()
    if cur:
        raise HTTPException(409, f"Trwa pobieranie źródła {cur.get('source_id')} — spróbuj za chwilę.")
    scheduler.run_now_async(source_id, who)
    return {"started": source_id, "message": "Pobieranie uruchomione w tle; wynik pojawi się w tabeli uruchomień."}


@router.post("/api/admin/suggest")
def admin_suggest(body: dict, who: str = Depends(require_admin)):
    url = str(body.get("url") or "").strip()
    if not url:
        raise HTTPException(422, "Podaj adres strony.")
    return fetchers.suggest_config(url)


@router.post("/api/admin/reload")
def admin_reload(who: str = Depends(require_admin)):
    stats = scheduler.maybe_reload(force=True)
    return {"reloaded": stats is not None, "documents": (stats or {}).get("documents")}


# ------------------------------------------------------------------ public (used by /zrodla via /api/sources)
def public_registry() -> list[dict]:
    """Registry entries for the public catalogue: no params/scheduling internals, only what a citizen may audit."""
    sources, problems = registry.load_all()
    runs = state.last_runs()
    keys = ("id", "name", "publisher", "url", "category", "tier", "enabled", "topics", "language", "license",
            "qualification", "schedule_hours", "method")
    out = []
    for sid, s in sources.items():
        if sid in problems:
            continue
        r = runs.get(sid) or {}
        mtime = scheduler._corpus_mtime(sid)
        out.append({**{k: s.get(k) for k in keys}, "docs": registry.count_docs(sid) if s.get("enabled") else 0,
                    "last_update": r.get("last_ok") or (mtime.isoformat(timespec="minutes") if mtime else None)})
    return sorted(out, key=lambda x: (not x["enabled"], x["tier"] or 9, x["name"] or ""))
