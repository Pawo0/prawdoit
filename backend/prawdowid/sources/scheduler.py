"""Schedule source runs, serialize fetches and reload the changed retrieval index.

Running registry sources: one source at a time, run state in SQLite, index hot-reload afterwards.

The scheduler is a daemon thread inside the API process (env PRAWDOWID_SCHEDULER=1, default). Every minute it:
  1. runs every enabled source whose `schedule_hours` has elapsed since its last attempt (oldest first),
  2. reloads the search index if the set of indexed corpus files changed (new documents, a source enabled or
     disabled, a CLI run in another process, a file edited by hand).

Reading guide: docs/backend/SOURCES.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import fcntl
import logging
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from ..config import settings
from . import fetchers, registry, state

log = logging.getLogger("prawdowid.sources")

TICK_S = 60
ERROR_RETRY_H = 2  # after a failed attempt retry sooner than schedule_hours
LOCK_FILE = settings.runtime_dir / "sources.lock"

_run_lock = threading.Lock()  # one fetch at a time inside this process
_current: dict = {}  # what is running now (for the admin panel)
_reload_lock = threading.Lock()
_last_sig: tuple | None = None
_stop = threading.Event()
_thread: threading.Thread | None = None


class Busy(RuntimeError):
    pass


@contextmanager
def _exclusive(blocking: bool):
    """Process-local + cross-process (flock) lock, so two servers / a CLI never fetch at the same time."""
    if not _run_lock.acquire(blocking=blocking):
        raise Busy("Trwa już pobieranie innego źródła.")
    fh = None
    try:
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        fh = open(LOCK_FILE, "w")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError as e:
            raise Busy("Inny proces Prawdowida właśnie pobiera źródło.") from e
        yield
    finally:
        if fh:
            fh.close()
        _run_lock.release()


def current() -> dict:
    return dict(_current)


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _corpus_mtime(source_id: str) -> datetime | None:
    p = registry.corpus_path(source_id)
    return datetime.fromtimestamp(p.stat().st_mtime, timezone.utc) if p.exists() else None


def next_due(src: dict, problems: list[str] | None = None) -> datetime | None:
    """When the source should run next (None = never automatically). Before the first registry run the corpus
    file's mtime counts as the last run, so migrated sources are not all re-harvested at server start.
    """
    if problems or not src.get("enabled") or src.get("method") not in registry.FETCH_METHODS:
        return None
    hours = float(src.get("schedule_hours") or 0)
    if hours <= 0:
        return None
    last = state.last_attempt(src["id"])
    if last:
        ref = _parse(last["started"])
        if last["status"] == "error":
            hours = min(hours, ERROR_RETRY_H)
    else:
        ref = _corpus_mtime(src["id"])
    if ref is None:  # never fetched: due immediately
        return datetime(2000, 1, 1, tzinfo=timezone.utc)
    return ref + timedelta(hours=hours)


def run_source(
    source_id: str, trigger: str = "cli", *, blocking: bool = False, source: dict | None = None
) -> dict:
    """Fetch one source and merge into data/corpus/<id>.jsonl. Never raises for fetch problems (they are stored)."""
    src = source or registry.get(source_id)
    if not src:
        return {"source_id": source_id, "status": "error", "message": "Nie ma takiego źródła."}
    try:
        src = registry.validate(src, strict=False)
    except registry.SourceError as e:
        state.record_skip(source_id, trigger, "błędna konfiguracja: " + str(e))
        return {"source_id": source_id, "status": "skipped", "message": str(e)}
    if src["method"] in registry.NOOP_METHODS:
        msg = f"metoda {src['method']} nie jest pobierana według harmonogramu"
        state.record_skip(source_id, trigger, msg)
        return {"source_id": source_id, "status": "skipped", "message": msg}
    try:
        with _exclusive(blocking):
            return _run_locked(src, trigger)
    except Busy as e:
        return {"source_id": source_id, "status": "busy", "message": str(e)}


def _run_locked(src: dict, trigger: str) -> dict:
    sid = src["id"]
    t0 = time.time()
    rid = state.start_run(sid, trigger)
    _current.update(
        source_id=sid,
        started=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        trigger=trigger,
    )
    status, n_new, n_total, msg = "ok", 0, None, ""
    try:
        if src["method"] == "legacy_script":
            before = {r.get("id") for r in fetchers.read_corpus(sid)}
            tail = fetchers.run_legacy_script(src)
            after = {r.get("id") for r in fetchers.read_corpus(sid)}
            n_new, n_total = len(after - before), len(after)
            msg = f"skrypt {src['params']['script']}: {n_new} nowych" + (
                f" · {tail}" if tail else ""
            )
        else:
            ctx = fetchers.Ctx(
                known_urls={
                    fetchers.canonical(r.get("url") or "") for r in fetchers.read_corpus(sid)
                }
            )
            recs = fetchers.fetch_source(src, ctx)
            if recs or (src.get("params") or {}).get(
                "dedupe_against"
            ):  # an empty run still prunes duplicates
                n_new, n_total = fetchers.merge_into_corpus(src, recs)
            else:
                n_total = registry.count_docs(sid)
            msg = f"{n_new} nowych, {ctx.pages} pobranych stron"
            if ctx.notes:
                msg += f"; uwagi ({len(ctx.notes)}): " + " | ".join(ctx.notes[:3])
    except fetchers.FetchError as e:
        status, msg = "error", str(e)
        n_total = registry.count_docs(sid)
    except Exception as e:  # noqa: BLE001 — a broken source must not kill the scheduler
        log.exception("source %s failed", sid)
        status, msg = "error", f"nieoczekiwany błąd: {type(e).__name__}: {e}"
        n_total = registry.count_docs(sid)
    finally:
        _current.clear()
    state.finish_run(rid, status, n_new, n_total, msg)
    log.info(
        "source %s: %s (%s new, %s total) in %.1fs — %s",
        sid,
        status,
        n_new,
        n_total,
        time.time() - t0,
        msg[:200],
    )
    return {
        "source_id": sid,
        "status": status,
        "n_new": n_new,
        "n_total": n_total,
        "message": msg,
        "seconds": round(time.time() - t0, 1),
    }


# ------------------------------------------------------------------ index hot reload
def index_signature() -> tuple:
    """(name, mtime, size) of the corpus files the index loads. Files of `live_search` sources are left out: their
    documents are already added in place by INDEX.add_docs(), so appending to them must not trigger a full reload.
    """
    files, excluded = registry.corpus_files_for_index()
    sources, _ = registry.load_all()
    live = {sid for sid, s in sources.items() if s.get("method") == "live_search"}
    sig = []
    for f in files:
        if f.stem in live:
            continue
        try:
            st = f.stat()
            sig.append((f.name, st.st_mtime_ns, st.st_size))
        except FileNotFoundError:
            continue
    return tuple(sig), tuple(
        excluded
    )  # excluded: enabling/disabling any source changes the signature


def maybe_reload(force: bool = False) -> dict | None:
    """Reload INDEX in place if the indexed corpus files changed. No-op in processes without a loaded index (CLI)."""
    global _last_sig
    from ..index import INDEX

    if not INDEX.loaded_at:
        return None
    with _reload_lock:
        sig = index_signature()
        if not force and sig == _last_sig:
            return None
        t0 = time.time()
        stats = INDEX.reload()
        _last_sig = sig
        log.info("index reloaded in %.1fs: %s documents", time.time() - t0, stats.get("documents"))
        return stats


def run_now_async(source_id: str, who: str) -> threading.Thread:
    """Admin 'Uruchom teraz': fetch in the background, then reload the index."""

    def work():
        res = run_source(source_id, trigger=f"admin:{who}")
        if res.get("status") == "ok":
            maybe_reload()

    t = threading.Thread(target=work, name=f"source-run-{source_id}", daemon=True)
    t.start()
    return t


def reload_async() -> None:
    threading.Thread(target=maybe_reload, name="index-reload", daemon=True).start()


# ------------------------------------------------------------------ background loop
def due_sources() -> list[dict]:
    sources, problems = registry.load_all()
    now = datetime.now(timezone.utc)
    due = []
    for sid, src in sources.items():
        nd = next_due(src, problems.get(sid))
        if nd is not None and nd <= now:
            due.append((nd, src))
    return [s for _, s in sorted(due, key=lambda x: x[0])]


def tick() -> list[dict]:
    results = []
    for src in due_sources():
        if _stop.is_set():
            break
        results.append(run_source(src["id"], trigger="harmonogram"))
    try:
        maybe_reload()
    except Exception:  # noqa: BLE001
        log.exception("index reload failed")
    return results


def _loop() -> None:
    global _last_sig
    from ..index import INDEX

    while not INDEX.loaded_at and not _stop.wait(2):  # wait for the startup index load
        pass
    try:
        with _exclusive(blocking=False):
            state.mark_interrupted()  # nobody else holds the lock => 'running' rows are leftovers
    except Busy:
        pass
    state.purge_old_runs()
    _last_sig = index_signature()
    log.info("source scheduler started (tick %ss)", TICK_S)
    while not _stop.wait(TICK_S):
        try:
            tick()
        except Exception:  # noqa: BLE001
            log.exception("scheduler tick failed")


def start() -> bool:
    global _thread
    if not settings.scheduler or (_thread and _thread.is_alive()):
        return False
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="source-scheduler", daemon=True)
    _thread.start()
    return True


def stop() -> None:
    _stop.set()


def status() -> dict:
    return {
        "enabled": settings.scheduler,
        "alive": bool(_thread and _thread.is_alive()),
        "tick_s": TICK_S,
        "running": current(),
    }
