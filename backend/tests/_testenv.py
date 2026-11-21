"""Shared setup for the model-free tests: a throw-away runtime directory (SQLite audit log) and no scheduler.
Import this before anything from `prawdowid` — config.py reads the environment once, at import time."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("PRAWDOWID_RUNTIME_DIR", tempfile.mkdtemp(prefix="prawdowid-test-"))
os.environ.setdefault("PRAWDOWID_SCHEDULER", "0")
BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
