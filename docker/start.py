"""Initialize writable container state, then replace this process with the server."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def prepare(seed: Path = Path("/app/data/index")) -> None:
    token = os.environ.get("PRAWDOWID_MODERATOR_TOKEN", "").strip()
    if not token or token == "demo-moderator":
        raise SystemExit("Set PRAWDOWID_MODERATOR_TOKEN to a private value before starting the container.")
    runtime = Path(os.environ["PRAWDOWID_RUNTIME_DIR"])
    index = Path(os.environ["PRAWDOWID_INDEX_DIR"])
    cache = Path(os.environ["HF_HOME"])
    for folder in (runtime, index, cache):
        folder.mkdir(parents=True, exist_ok=True)
    # Seed an empty volume with the shipped embeddings. Preserve caches from later corpus updates.
    for pattern in ("*.npy", "*.keys.json"):
        for source in seed.glob(pattern):
            destination = index / source.name
            if not destination.exists():
                temporary = destination.with_suffix(destination.suffix + ".tmp")
                shutil.copyfile(source, temporary)
                temporary.replace(destination)
    # PaaS platforms conventionally inject PORT; uvicorn reads UVICORN_PORT.
    os.environ["UVICORN_PORT"] = os.environ.get("PORT", os.environ.get("UVICORN_PORT", "8000"))


if __name__ == "__main__":
    prepare()
    if len(sys.argv) < 2:
        raise SystemExit("Missing server command")
    os.execvp(sys.argv[1], sys.argv[1:])
