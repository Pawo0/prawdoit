"""Probe readiness without importing the ML application into a second process."""
import json
import os
from urllib.request import urlopen

port = os.environ.get("PORT", os.environ.get("UVICORN_PORT", "8000"))
with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=3) as response:
    health = json.load(response)
    if not health.get("ok") or not health.get("corpus", {}).get("documents", 0):
        raise SystemExit(1)
