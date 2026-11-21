"""Async job API for the waiting window: the UI starts a check and polls its stage.

  POST /api/check/async   (same body as /api/check)  -> {"job_id": "..."}
  GET  /api/jobs/{job_id}                             -> {"state": "running|done|error", "stage", "stage_label",
                                                          "elapsed_s", "result"?}

Stages are reported from inside service.run_check through its `progress` callback (labels: websearch.STAGES), so the
window only shows what is really happening. Small thread pool, jobs expire 10 minutes after they finish.
/api/check stays synchronous and unchanged for the other channels.
"""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException

from . import store
from .schemas import CheckRequest
from .websearch import STAGES

log = logging.getLogger("prawdowid.jobs")
router = APIRouter()

JOB_TTL_S = 600
MAX_JOBS = 500
_POOL = ThreadPoolExecutor(max_workers=int(os.environ.get("PRAWDOWID_JOB_WORKERS", "2")), thread_name_prefix="job")
_JOBS: dict[str, "Job"] = {}
_LOCK = threading.Lock()


@dataclass
class Job:
    id: str
    created: float = field(default_factory=time.monotonic)
    started: float | None = None
    finished: float | None = None
    state: str = "running"
    stage: str = "kolejka"
    stage_label: str = STAGES["kolejka"]
    result: dict | None = None
    error: str | None = None

    def view(self) -> dict:
        end = self.finished or time.monotonic()
        out = {"job_id": self.id, "state": self.state, "stage": self.stage, "stage_label": self.stage_label,
               "elapsed_s": round(end - self.created, 1)}
        if self.result is not None:
            out["result"] = self.result
        if self.error:
            out["error"] = self.error
        return out


def _purge() -> None:
    now = time.monotonic()
    with _LOCK:
        for jid in [j.id for j in _JOBS.values() if now - (j.finished or j.created) > JOB_TTL_S]:
            _JOBS.pop(jid, None)


def _run(job: Job, req: CheckRequest) -> None:
    from .service import run_check  # local import: service loads models

    job.started = time.monotonic()

    def progress(stage: str, label: str) -> None:
        job.stage, job.stage_label = stage, label

    try:
        res = run_check(req, progress=progress)
        job.result = res.model_dump()
        job.stage, job.stage_label = "gotowe", "Gotowe."
        job.state = "done"
    except Exception as e:  # noqa: BLE001
        log.exception("async check failed")
        store.log_error(None, "jobs", repr(e)[:400])
        job.state, job.stage, job.stage_label = "error", "blad", "Wystąpił błąd techniczny."
        job.error = "Wystąpił błąd techniczny podczas analizy. To nie jest ocena treści — spróbuj ponownie."
    finally:
        job.finished = time.monotonic()


@router.post("/api/check/async")
def api_check_async(req: CheckRequest):
    if not (req.text or req.url):
        raise HTTPException(422, "Podaj tekst lub adres URL.")
    _purge()
    with _LOCK:
        if sum(1 for j in _JOBS.values() if j.state == "running") >= MAX_JOBS:
            raise HTTPException(429, "Za dużo trwających sprawdzeń — spróbuj za chwilę.")
        job = Job(id=uuid.uuid4().hex[:16])
        _JOBS[job.id] = job
    _POOL.submit(_run, job, req)
    return {"job_id": job.id}


@router.get("/api/jobs/{job_id}")
def api_job(job_id: str):
    _purge()
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "Nie znaleziono zadania (mogło wygasnąć po 10 minutach).")
    return job.view()
