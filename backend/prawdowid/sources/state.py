"""Persist source-run history and administrative configuration changes.

Run state + admin audit trail for the source registry (SQLite, same DB/connection as store.py).

source_runs     one row per fetch attempt (scheduler, admin "run now", CLI)
source_changes  who changed which registry entry, when, and what changed (field-level diff)

Reading guide: docs/backend/SOURCES.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from .. import store

RUN_RETENTION_DAYS = 90

with store._lock:
    store._db.executescript(
        """
        CREATE TABLE IF NOT EXISTS source_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT NOT NULL, trigger TEXT, started TEXT, finished TEXT,
            status TEXT, n_new INTEGER, n_total INTEGER, message TEXT);
        CREATE INDEX IF NOT EXISTS ix_source_runs_source ON source_runs(source_id, started);
        CREATE TABLE IF NOT EXISTS source_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, who TEXT, source_id TEXT, action TEXT, diff TEXT);
        """
    )
    store._db.commit()


def start_run(source_id: str, trigger: str) -> int:
    with store._lock:
        cur = store._db.execute(
            "INSERT INTO source_runs (source_id, trigger, started, status) VALUES (?,?,?,?)",
            (source_id, trigger, store.now(), "running"),
        )
        store._db.commit()
        return int(cur.lastrowid)


def finish_run(
    run_id: int, status: str, n_new: int | None, n_total: int | None, message: str
) -> None:
    with store._lock:
        store._db.execute(
            "UPDATE source_runs SET finished=?, status=?, n_new=?, n_total=?, message=? WHERE id=?",
            (store.now(), status, n_new, n_total, message[:1000], run_id),
        )
        store._db.commit()


def record_skip(source_id: str, trigger: str, message: str) -> None:
    rid = start_run(source_id, trigger)
    finish_run(rid, "skipped", 0, None, message)


def mark_interrupted(older_than_hours: float = 0) -> int:
    """Rows left in 'running' by a process that died (restart during a fetch). Call only while holding the run
    lock (then no other process can be fetching)."""
    with store._lock:
        n = store._db.execute(
            "UPDATE source_runs SET status='error', finished=?, message='przerwane (restart serwera)' "
            "WHERE status='running' AND started < ?",
            (
                store.now(),
                (datetime.now(timezone.utc) - timedelta(hours=older_than_hours)).isoformat(),
            ),
        ).rowcount
        store._db.commit()
    return n


def last_runs() -> dict[str, dict]:
    """Latest run per source + the latest successful one (for 'last updated')."""
    rows = store._db.execute(
        "SELECT r.* FROM source_runs r JOIN (SELECT source_id, MAX(id) mid FROM source_runs GROUP BY source_id) m "
        "ON r.id = m.mid"
    ).fetchall()
    ok = {
        r["source_id"]: r["finished"]
        for r in store._db.execute(
            "SELECT source_id, MAX(finished) finished FROM source_runs WHERE status='ok' GROUP BY source_id"
        ).fetchall()
    }
    out = {}
    for r in rows:
        d = dict(r)
        d["last_ok"] = ok.get(r["source_id"])
        out[r["source_id"]] = d
    return out


def last_attempt(source_id: str) -> dict | None:
    """Latest non-skipped run (a 'skipped' row must not postpone the next real attempt)."""
    r = store._db.execute(
        "SELECT * FROM source_runs WHERE source_id=? AND status != 'skipped' ORDER BY id DESC LIMIT 1",
        (source_id,),
    ).fetchone()
    return dict(r) if r else None


def recent_runs(limit: int = 50, source_id: str | None = None) -> list[dict]:
    if source_id:
        rows = store._db.execute(
            "SELECT * FROM source_runs WHERE source_id=? ORDER BY id DESC LIMIT ?",
            (source_id, limit),
        ).fetchall()
    else:
        rows = store._db.execute(
            "SELECT * FROM source_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def diff(before: dict | None, after: dict | None) -> dict:
    before, after = before or {}, after or {}
    return {
        k: [before.get(k), after.get(k)]
        for k in sorted(set(before) | set(after))
        if before.get(k) != after.get(k)
    }


def log_change(
    who: str, source_id: str, action: str, before: dict | None, after: dict | None
) -> None:
    with store._lock:
        store._db.execute(
            "INSERT INTO source_changes (at, who, source_id, action, diff) VALUES (?,?,?,?,?)",
            (
                store.now(),
                who[:80],
                source_id,
                action,
                json.dumps(diff(before, after), ensure_ascii=False),
            ),
        )
        store._db.commit()


def recent_changes(limit: int = 50, source_id: str | None = None) -> list[dict]:
    q = (
        "SELECT * FROM source_changes"
        + (" WHERE source_id=?" if source_id else "")
        + " ORDER BY id DESC LIMIT ?"
    )
    rows = store._db.execute(q, (source_id, limit) if source_id else (limit,)).fetchall()
    return [{**dict(r), "diff": json.loads(r["diff"] or "{}")} for r in rows]


def purge_old_runs(days: int = RUN_RETENTION_DAYS) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with store._lock:
        n = store._db.execute("DELETE FROM source_runs WHERE started < ?", (cutoff,)).rowcount
        store._db.commit()
    return n
