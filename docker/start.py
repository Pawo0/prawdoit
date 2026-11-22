"""Initialize state; run API alone or supervise API + optional Discord adapter."""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def copy_seed(source: Path, destination: Path) -> None:
    """Copy curated data without source security xattrs (e.g. a container's SELinux label)."""
    destination.mkdir()
    for entry in source.rglob("*"):
        target = destination / entry.relative_to(source)
        if entry.is_dir():
            target.mkdir(exist_ok=True)
        else:
            shutil.copyfile(entry, target)
            # Scheduler uses corpus mtime to avoid refetching every source at first startup.
            stat = entry.stat()
            os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))


def prepare(seed: Path = Path("/app/data/index"), data_seed: Path = Path("/app/seed")) -> None:
    # Both panel tokens are required; the public demo values are refused (they work only with PRAWDOWID_DEV_MODE=1
    # outside the container, see backend/prawdowid/config.py).
    for name, demo in (("PRAWDOWID_MODERATOR_TOKEN", "demo-moderator"), ("PRAWDOWID_ADMIN_TOKEN", "demo-admin")):
        token = os.environ.get(name, "").strip()
        if not token or token == demo:
            raise SystemExit(f"Set {name} to a private value before starting the container.")
    if os.environ.get("PRAWDOWID_DEV_MODE", "0") == "1":
        raise SystemExit("PRAWDOWID_DEV_MODE=1 is for local development only; unset it in the container.")
    runtime = Path(os.environ["PRAWDOWID_RUNTIME_DIR"])
    index = Path(os.environ["PRAWDOWID_INDEX_DIR"])
    cache = Path(os.environ["HF_HOME"])
    for folder in (runtime, index, cache):
        folder.mkdir(parents=True, exist_ok=True)
    # /app/data links point here, also for legacy scripts which use fixed paths.
    # Initialize once; preserve admin edits, source deletions and harvested documents on restarts.
    for name in ("corpus", "sources"):
        source, destination = data_seed / name, runtime.parent / name
        if source.is_dir() and not destination.exists():
            temporary = destination.with_name(name + ".bootstrap")
            if temporary.exists():
                shutil.rmtree(temporary)
            copy_seed(source, temporary)
            temporary.replace(destination)
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


def stop_children(children: list[subprocess.Popen]) -> None:
    for child in children:
        if child.poll() is None:
            child.terminate()
    deadline = time.monotonic() + 10
    for child in children:
        try:
            child.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def supervise(command: list[str]) -> int:
    """Keep the API alive independently of Discord outages; forward container shutdown."""
    stopping = False

    def shutdown(signum, frame):
        nonlocal stopping
        stopping = True

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, shutdown)
    children = []
    try:
        server = subprocess.Popen(command)
        children.append(server)
        bot = None
        restart_at = 0.0
        health_url = f"http://127.0.0.1:{os.environ['UVICORN_PORT']}/api/health"
        while not stopping:
            if server.poll() is not None:
                return server.returncode or 1  # unexpected API exit must trigger container restart
            if bot is not None and bot.poll() is not None:
                print(f"Discord adapter exited ({bot.returncode}); retrying in 30 s.", flush=True)
                children.remove(bot)
                bot = None
                restart_at = time.monotonic() + 30
            if bot is None and time.monotonic() >= restart_at:
                try:
                    with urlopen(health_url, timeout=1) as response:
                        ready = response.status == 200
                except (URLError, TimeoutError, OSError):
                    ready = False
                if ready and not stopping:
                    env = {**os.environ, "PRAWDOWID_API": f"http://127.0.0.1:{os.environ['UVICORN_PORT']}"}
                    bot = subprocess.Popen([sys.executable, "/app/bots/discord_bot.py"], env=env)
                    children.append(bot)
            time.sleep(0.5)
        return 0
    finally:
        stop_children(children)


def main() -> int:
    prepare()
    if len(sys.argv) < 2:
        raise SystemExit("Missing server command")
    if os.environ.get("PRAWDOWID_DISCORD_TOKEN", "").strip():
        return supervise(sys.argv[1:])
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
