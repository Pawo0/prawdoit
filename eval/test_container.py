"""Smoke test a running container, without ML libraries on the host.

Usage: python3 eval/test_container.py --base http://localhost:8000
"""
from __future__ import annotations

import argparse
import json
import uuid
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:8000")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    def call(path: str, *, method: str = "GET", body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        request = Request(base + path, data=data, method=method,
                          headers={"Content-Type": "application/json"} if data else {})
        with urlopen(request, timeout=120) as response:
            return response.read()

    health = json.loads(call("/api/health"))
    assert health["ok"] and health["corpus"]["documents"] > 0, health
    assert b"PRAWDOWID" in call("/")
    assert len(call("/static/fonts/GeistPixel-Square.woff2")) > 1000
    session = "container-test-" + uuid.uuid4().hex
    try:
        result = json.loads(call("/api/check", method="POST", body={
            "text": "Szczepionki przeciw COVID-19 zawierają mikroczipy.",
            "session": session, "channel": "container-smoke-test",
        }))
        assert result["status"] == "ok" and result["claims"], result
        assert all(c["verdict"] in {"falszywe", "potwierdzone", "wprowadzajace_w_blad", "brak_dowodow", "nie_podlega_weryfikacji"} for c in result["claims"])
        saved = json.loads(call("/api/check/" + result["id"]))
        assert saved["id"] == result["id"], saved
        print(f"PASS: {health['corpus']['documents']} documents, website/font, real inference and SQLite round-trip.")
    finally:
        call("/api/session/" + session, method="DELETE")


if __name__ == "__main__":
    main()
