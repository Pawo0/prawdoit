"""Audit log (przebieg sprawdzenia), security events, moderator cases (pętla informacji), retention.

SQLite keeps the prototype dependency-free; the interface is small enough to swap for Postgres.
Only PII-masked input is stored; sessions can be deleted on request; records expire after retention_days.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np

from .config import settings

_DB = settings.runtime_dir / "prawdowid.sqlite"
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


_db = _conn()
with _lock:
    _db.executescript(
        """
        CREATE TABLE IF NOT EXISTS checks (
            id TEXT PRIMARY KEY, created_at TEXT, channel TEXT, session TEXT, input_masked TEXT,
            status TEXT, verdicts TEXT, sources TEXT, result_json TEXT, total_ms REAL, case_id TEXT);
        CREATE TABLE IF NOT EXISTS security_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, check_id TEXT, kind TEXT, location TEXT, detail TEXT);
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, status TEXT, title TEXT, count INTEGER,
            channels TEXT, sample_check_ids TEXT, centroid BLOB, priority TEXT, note TEXT);
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, check_id TEXT, message TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, check_id TEXT, component TEXT, detail TEXT);
        """
    )
    _db.commit()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def save_check(result: dict, masked_input: str, session: str | None) -> None:
    verdicts = [c["verdict"] for c in result.get("claims", [])]
    sources = sorted({e["url"] for c in result.get("claims", []) for e in c.get("evidence", [])})
    with _lock:
        _db.execute(
            "INSERT OR REPLACE INTO checks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (result["id"], result["created_at"], result["channel"], session, masked_input, result["status"],
             json.dumps(verdicts), json.dumps(sources), json.dumps(result, ensure_ascii=False),
             result.get("timings_ms", {}).get("total_ms"), result.get("case_id")),
        )
        for ev in result.get("security_events", []):
            _db.execute("INSERT INTO security_events (created_at, check_id, kind, location, detail) VALUES (?,?,?,?,?)",
                        (result["created_at"], result["id"], ev["kind"], ev["where"], ev["detail"]))
        _db.commit()


def log_error(check_id: str | None, component: str, detail: str) -> None:
    with _lock:
        _db.execute("INSERT INTO errors (created_at, check_id, component, detail) VALUES (?,?,?,?)",
                    (now(), check_id, component, detail[:500]))
        _db.commit()


def get_check(check_id: str) -> dict | None:
    row = _db.execute("SELECT result_json FROM checks WHERE id=?", (check_id,)).fetchone()
    return json.loads(row["result_json"]) if row else None


def delete_session(session: str) -> int:
    with _lock:
        n = _db.execute("DELETE FROM checks WHERE session=?", (session,)).rowcount
        _db.commit()
    return n


def purge_expired() -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=settings.retention_days)).isoformat()
    with _lock:
        n = _db.execute("DELETE FROM checks WHERE created_at < ?", (cutoff,)).rowcount
        _db.commit()
    return n


# ------------------------------------------------------------------ moderator cases (pętla informacji)
CASE_SIM = 0.86  # cosine above which two unresolved questions are considered "the same case"


def upsert_case(check_id: str, claim_text: str, emb: np.ndarray, channel: str, high_risk: bool) -> tuple[str, int]:
    """Group similar unresolved submissions into one case. Returns (case_id, count)."""
    emb = emb.astype(np.float32)
    with _lock:
        rows = _db.execute("SELECT id, centroid, count, channels, sample_check_ids FROM cases WHERE status != 'zamknięta'"
                           ).fetchall()
        best, best_sim = None, 0.0
        for r in rows:
            c = np.frombuffer(r["centroid"], dtype=np.float32)
            sim = float(c @ emb / (np.linalg.norm(c) * np.linalg.norm(emb) + 1e-9))
            if sim > best_sim:
                best, best_sim = r, sim
        ts = now()
        if best is not None and best_sim >= CASE_SIM:
            count = best["count"] + 1
            centroid = (np.frombuffer(best["centroid"], dtype=np.float32) * best["count"] + emb) / count
            chans = sorted(set(json.loads(best["channels"])) | {channel})
            samples = (json.loads(best["sample_check_ids"]) + [check_id])[-20:]
            priority = "wysoki" if (high_risk or count >= 3) else "normalny"
            _db.execute("UPDATE cases SET updated_at=?, count=?, centroid=?, channels=?, sample_check_ids=?, priority=? "
                        "WHERE id=?", (ts, count, centroid.astype(np.float32).tobytes(), json.dumps(chans),
                                       json.dumps(samples), priority, best["id"]))
            _db.commit()
            return best["id"], count
        cid = "SPR-" + new_id()[:6].upper()
        _db.execute("INSERT INTO cases VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (cid, ts, ts, "nowa", claim_text[:300], 1, json.dumps([channel]), json.dumps([check_id]),
                     emb.tobytes(), "wysoki" if high_risk else "normalny", ""))
        _db.commit()
        return cid, 1


def list_cases() -> list[dict]:
    rows = _db.execute("SELECT id, created_at, updated_at, status, title, count, channels, sample_check_ids, priority, "
                       "note FROM cases ORDER BY (priority='wysoki') DESC, count DESC, updated_at DESC").fetchall()
    return [{**dict(r), "channels": json.loads(r["channels"]), "sample_check_ids": json.loads(r["sample_check_ids"])}
            for r in rows]


def update_case(case_id: str, status: str, note: str) -> bool:
    with _lock:
        n = _db.execute("UPDATE cases SET status=?, note=?, updated_at=? WHERE id=?",
                        (status, note[:1000], now(), case_id)).rowcount
        _db.commit()
    return n > 0


def stats() -> dict:
    q = lambda sql: _db.execute(sql).fetchall()  # noqa: E731
    total = q("SELECT COUNT(*) n FROM checks")[0]["n"]
    by_status = {r["status"]: r["n"] for r in q("SELECT status, COUNT(*) n FROM checks GROUP BY status")}
    by_channel = {r["channel"]: r["n"] for r in q("SELECT channel, COUNT(*) n FROM checks GROUP BY channel")}
    verdicts: dict[str, int] = {}
    for r in q("SELECT verdicts FROM checks"):
        for v in json.loads(r["verdicts"] or "[]"):
            verdicts[v] = verdicts.get(v, 0) + 1
    lat = [r["total_ms"] for r in q("SELECT total_ms FROM checks WHERE total_ms IS NOT NULL")]
    sec = q("SELECT kind, COUNT(*) n FROM security_events GROUP BY kind")
    errs = q("SELECT component, COUNT(*) n FROM errors GROUP BY component")
    return {
        "checks": total, "by_status": by_status, "by_channel": by_channel, "verdicts": verdicts,
        "abstentions": verdicts.get("brak_dowodow", 0),
        "latency_ms_median": float(np.median(lat)) if lat else None,
        "latency_ms_p95": float(np.percentile(lat, 95)) if lat else None,
        "security_events": {r["kind"]: r["n"] for r in sec},
        "errors": {r["component"]: r["n"] for r in errs},
        "open_cases": q("SELECT COUNT(*) n FROM cases WHERE status != 'zamknięta'")[0]["n"],
        # estimated marginal cost (CPU time × rate, docs/COSTS.md); LLM tokens are priced per check in result.engine
        "cost_estimate_pln": {"per_check_median": round(float(np.median(lat)) / 1000 * settings.cost_pln_per_cpu_s, 6) if lat else None,
                              "total": round(sum(lat) / 1000 * settings.cost_pln_per_cpu_s, 4)},
    }


def recent_security_events(limit: int = 50) -> list[dict]:
    return [dict(r) for r in _db.execute("SELECT * FROM security_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]


def add_feedback(check_id: str, message: str) -> None:
    from .textutil import mask_pii

    with _lock:
        _db.execute("INSERT INTO feedback (created_at, check_id, message, status) VALUES (?,?,?,?)",
                    (now(), check_id[:32], mask_pii(message)[:1000], "nowe"))
        _db.commit()


def list_feedback(limit: int = 50) -> list[dict]:
    return [dict(r) for r in _db.execute("SELECT * FROM feedback ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
