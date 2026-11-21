#!/usr/bin/env python3
"""Validate data/corpus/official_*.jsonl against the shared corpus schema and print counts."""
from __future__ import annotations

import collections
import glob
import json
import re
import sys
from pathlib import Path

KEYS = ["id", "source_type", "publisher", "domain", "url", "title", "published_at", "retrieved_at", "language",
        "license", "text", "claim", "claim_author", "verdict_raw", "verdict", "tags"]
ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    errors, ids = [], collections.Counter()
    per_file, per_domain = {}, collections.Counter()
    for f in sorted(glob.glob(str(ROOT / "data/corpus/official_*.jsonl"))):
        n = 0
        for i, line in enumerate(open(f, encoding="utf-8"), 1):
            try:
                r = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"{f}:{i} bad json {e}")
                continue
            n += 1
            ids[r.get("id")] += 1
            per_domain[r.get("domain")] += 1
            if list(r.keys()) != KEYS:
                errors.append(f"{f}:{i} keys {list(r.keys())}")
            if r.get("source_type") != "official" or r.get("language") != "pl":
                errors.append(f"{f}:{i} source_type/language")
            if r.get("published_at") is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["published_at"]):
                errors.append(f"{f}:{i} published_at {r['published_at']!r}")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", r.get("retrieved_at") or ""):
                errors.append(f"{f}:{i} retrieved_at")
            if not r.get("text") or len(r["text"]) > 4000:
                errors.append(f"{f}:{i} text length {len(r.get('text') or '')}")
            if not (r.get("url") or "").startswith("https://"):
                errors.append(f"{f}:{i} url {r.get('url')}")
            if any(r.get(k) is not None for k in ("claim", "claim_author", "verdict_raw", "verdict")):
                errors.append(f"{f}:{i} claim/verdict fields must be null")
            if not isinstance(r.get("tags"), list):
                errors.append(f"{f}:{i} tags")
        per_file[Path(f).name] = n
    dups = [k for k, v in ids.items() if v > 1]
    if dups:
        errors.append(f"duplicate ids: {dups[:10]}")
    for k, v in per_file.items():
        print(f"{v:5d}  {k}")
    print(f"{sum(per_file.values()):5d}  TOTAL in {len(per_file)} files; {len(per_domain)} domains: "
          + ", ".join(f"{d}={c}" for d, c in per_domain.most_common()))
    for e in errors[:30]:
        print("ERROR", e, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
