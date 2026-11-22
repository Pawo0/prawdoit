"""Process-local rate limits keyed by client address and operation.

Per-client request limits: a sliding one-minute window per (bucket, client address), in process memory.

Buckets (limits in config.py, all PRAWDOWID_* variables):
  check  POST /api/check, /api/check/async       RATE_LIMIT        120/min
  quick  POST /api/quick (batches, tier 1)       RATE_LIMIT_QUICK   60/min
  auto   checks with mode="auto" (also counted in `check`)  RATE_LIMIT_AUTO  20/min

The client address is `request.client.host`. Behind a reverse proxy that is the proxy's address unless uvicorn trusts
the proxy: uvicorn rewrites the client from X-Forwarded-For only for peers listed in FORWARDED_ALLOW_IPS
(--forwarded-allow-ips; default 127.0.0.1,::1). compose.yaml sets it from PRAWDOWID_TRUSTED_PROXY_IPS. Without it,
everyone behind the proxy shares one bucket. One process only — a second replica needs a shared store.

Reading guide: docs/backend/API.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

WINDOW_S = 60.0
MAX_KEYS = 20_000
MESSAGE = "Za dużo zapytań — spróbuj za chwilę."
_hits: dict[tuple[str, str], deque] = {}
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def hit(bucket: str, ip: str, limit: int, now: float | None = None) -> int | None:
    """Record one request. Returns None when it is allowed, otherwise the seconds until the next one will be."""
    now = time.monotonic() if now is None else now
    with _lock:
        q = _hits.setdefault((bucket, ip), deque())
        while q and now - q[0] >= WINDOW_S:
            q.popleft()
        if len(q) >= limit:
            return max(1, math.ceil(WINDOW_S - (now - q[0]))) if q else int(WINDOW_S)
        q.append(now)
        if len(_hits) > MAX_KEYS:  # forget clients that have been idle for a whole window
            for key in [k for k, v in _hits.items() if not v or now - v[-1] >= WINDOW_S]:
                del _hits[key]
    return None


def enforce(bucket: str, request: Request, limit: int) -> None:
    wait = hit(bucket, client_ip(request), limit)
    if wait is not None:
        raise HTTPException(429, MESSAGE, headers={"Retry-After": str(wait)})


def reset() -> None:
    with _lock:
        _hits.clear()
