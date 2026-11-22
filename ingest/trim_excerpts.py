#!/usr/bin/env python3
"""One-off: shrink the stored text of sources without an open licence to ONE verbatim excerpt (≤300 chars).

    python ingest/trim_excerpts.py fakenews_pl pravda            # rewrites data/corpus/<id>.jsonl in place
    python ingest/trim_excerpts.py --dry-run cert_komunikaty official_cert

Every record keeps its facts (id, claim, rating, title, dates, link, tags) and gets, instead of the article text, the
passage the harvesters now store (textutil.finding_excerpt: the sentence or two stating the finding, not the restated
claim; the opening when nothing fits). The licence string of each record is replaced by the registry entry's licence
(data/sources/<id>.json), which describes what is stored. Records already tagged excerpt:finding<N> are left alone, so
the script can be re-run. Stdlib only (no network, no models).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from prawdowid.textutil import finding_excerpt, normalize_ws  # noqa: E402  (stdlib-only module)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+", help="registry ids, e.g. fakenews_pl pravda")
    ap.add_argument("--max-len", type=int, default=300)
    ap.add_argument("--corpus-dir", type=Path, default=ROOT / "data" / "corpus")
    ap.add_argument("--sources-dir", type=Path, default=ROOT / "data" / "sources")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    tag = f"excerpt:finding{args.max_len}"
    for sid in args.sources:
        path = args.corpus_dir / f"{sid}.jsonl"
        lic = json.loads((args.sources_dir / f"{sid}.json").read_text(encoding="utf-8")).get("license") or ""
        recs = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
        before = [len(r.get("text") or "") for r in recs]
        for r in recs:
            tags = r.setdefault("tags", [])
            if tag in tags:
                continue
            text = normalize_ws(r.get("text") or "")
            if text:
                r["text"] = finding_excerpt(text, r.get("title") or "", r.get("claim") or "", args.max_len)
            if lic:
                r["license"] = lic
            tags.append(tag)
        after = [len(r.get("text") or "") for r in recs]
        print(f"{sid}: {len(recs)} records; text chars median {statistics.median(before or [0]):.0f} max "
              f"{max(before or [0])} -> median {statistics.median(after or [0]):.0f} max {max(after or [0])}")
        if not args.dry_run:
            path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")


if __name__ == "__main__":
    main()
