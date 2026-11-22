"""Initialize state; run API alone or supervise API + optional Discord adapter."""
from __future__ import annotations

import hashlib
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


def seed_release(*folders: Path) -> str:
    """Digest of the curated data an image ships (corpus, source registry, embedding cache): file paths and contents.
    Written to /app/seed/RELEASE at build time; a different value on start means a new release of the data."""
    h = hashlib.sha256()
    for folder in folders:
        for f in sorted(p for p in folder.rglob("*") if p.is_file() and p.name != "RELEASE"):
            h.update(f"{folder.name}/{f.relative_to(folder)}\0".encode())
            with f.open("rb") as fh:
                for block in iter(lambda: fh.read(1 << 20), b""):
                    h.update(block)
    return h.hexdigest()[:16]


def install_seed(source: Path, destination: Path, previous: Path) -> None:
    """Replace destination with a fresh copy of source; the replaced folder is kept as previous (one generation)."""
    temporary = destination.with_name(destination.name + ".bootstrap")
    if temporary.exists():
        shutil.rmtree(temporary)
    copy_seed(source, temporary)
    if destination.exists():
        if previous.exists():
            shutil.rmtree(previous)
        previous.parent.mkdir(parents=True, exist_ok=True)
        destination.replace(previous)
    temporary.replace(destination)


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
    # Restarts keep the volume's data: admin edits, source deletions, harvested documents, the grown embedding cache.
    # A new image whose curated data differs (RELEASE) replaces corpus, registry and cache with what it ships, so a
    # redeploy serves the data that was tested; the replaced corpus and registry are kept under previous/.
    state = runtime.parent
    release_file, marker = data_seed / "RELEASE", state / "seed-release"
    release = release_file.read_text().strip() if release_file.exists() else ""
    installed = marker.read_text().strip() if marker.exists() else ""
    refresh = bool(release) and release != installed
    for name in ("corpus", "sources"):
        source, destination = data_seed / name, state / name
        if source.is_dir() and (refresh or not destination.exists()):
            install_seed(source, destination, state / "previous" / name)
    # The shipped embeddings fill an empty cache, and replace the cache on a new data release.
    for pattern in ("*.npy", "*.keys.json"):
        for source in seed.glob(pattern):
            destination = index / source.name
            if refresh or not destination.exists():
                temporary = destination.with_suffix(destination.suffix + ".tmp")
                shutil.copyfile(source, temporary)
                temporary.replace(destination)
    if refresh:
        if installed:
            print(f"New data release {release} (was {installed}): corpus, source registry and embedding cache "
                  f"replaced; the previous corpus and registry are in {state / 'previous'}.", flush=True)
        marker.write_text(release + "\n")
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
    if sys.argv[1:2] == ["--write-release"]:  # build time: start.py --write-release <RELEASE file> <data dir>...
        Path(sys.argv[2]).write_text(seed_release(*(Path(a) for a in sys.argv[3:])) + "\n")
        return 0
    prepare()
    if len(sys.argv) < 2:
        raise SystemExit("Missing server command")
    if os.environ.get("PRAWDOWID_DISCORD_TOKEN", "").strip():
        return supervise(sys.argv[1:])
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
