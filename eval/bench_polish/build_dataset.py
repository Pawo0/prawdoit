"""Build eval/bench_polish/bench.jsonl = seeded, stratified sample of Demagog claims  x  hand-written variants.

    backend/.venv/bin/python eval/bench_polish/build_dataset.py

The sample is deterministic (SEED, quotas per rating, round-robin over periods 2026 / 2025 / older). The variants in
variants.tsv were written by hand before any system output was inspected; they are joined to the sample by seed number.
Re-running after the corpus changed may pick different claims — then variants.tsv no longer matches and the script
refuses to write (the frozen sample is kept in seeds.json; pass --frozen to rebuild from it).
"""
from __future__ import annotations

import collections
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SEED = 20261121
QUOTA = {"false": 12, "misleading": 7, "mixed": 4, "true": 7, "unverifiable": 2}
FC_TO_VERDICT = {"false": "falszywe", "misleading": "wprowadzajace_w_blad", "mixed": "wprowadzajace_w_blad",
                 "true": "potwierdzone", "unverifiable": "brak_dowodow"}
FLIP = {"falszywe": "potwierdzone", "potwierdzone": "falszywe"}


def eligible(r: dict) -> bool:
    c = r.get("claim") or ""
    if not (35 <= len(c) <= 190) or r.get("verdict") not in QUOTA:
        return False
    if re.search(r"przerobion", (r.get("verdict_raw") or "").lower()):
        return False  # doctored photo/video: the "claim" describes an image, not a statement about the world
    return not re.search(r"\b(nagrani|zdjęci|film|wideo|grafik|fotografi|screen|zrzut)", c.lower())


def sample(rows: list[dict]) -> list[dict]:
    random.seed(SEED)
    el = [r for r in rows if eligible(r)]
    picked = []
    for v, n in QUOTA.items():
        by = collections.defaultdict(list)
        for r in (r for r in el if r["verdict"] == v):
            y = (r.get("published_at") or "")[:4]
            by["2026" if y == "2026" else "2025" if y == "2025" else "old"].append(r)
        for k in by:
            random.shuffle(by[k])
        order, i, got = ["2026", "2025", "old"], 0, []
        while len(got) < n and any(by.values()):
            k = order[i % 3]
            i += 1
            if by[k]:
                got.append(by[k].pop())
        picked += got
    return picked


def main() -> None:
    rows = [json.loads(l) for l in (ROOT / "data/corpus/demagog.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    by_id = {r["id"]: r for r in rows}
    seeds_path = HERE / "seeds.json"
    if "--frozen" in sys.argv or seeds_path.exists():
        seeds = json.loads(seeds_path.read_text(encoding="utf-8"))
        missing = [s["id"] for s in seeds if s["id"] not in by_id]
        if missing:
            sys.exit(f"seed documents no longer in data/corpus/demagog.jsonl: {missing}")
    else:
        seeds = [{"no": i + 1, "id": r["id"], "claim": r["claim"], "rating": r["verdict"], "rating_raw": r["verdict_raw"],
                  "published_at": r.get("published_at"), "title": r["title"]} for i, r in enumerate(sample(rows))]
        seeds_path.write_text(json.dumps(seeds, ensure_ascii=False, indent=1), encoding="utf-8")
    by_no = {s["no"]: s for s in seeds}
    out, n = [], collections.Counter()
    for line in (HERE / "variants.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        no, typ, text = line.split("|", 2)
        s = by_no[int(no)]
        gold = FC_TO_VERDICT[s["rating"]]
        if typ == "neg":
            expected, group = FLIP[gold], "neg"
        elif typ == "hardneg":
            expected, group = "brak_dowodow", "hardneg"
        else:
            expected, group = gold, ("unverifiable" if gold == "brak_dowodow" else "pos")
        n[typ] += 1
        out.append({"id": f"{int(no):02d}-{typ}", "seed": int(no), "type": typ, "group": group, "text": text.strip(),
                    "expected": expected, "gold_doc": s["id"], "gold_claim": s["claim"], "rating": s["rating"]})
    assert len({o["id"] for o in out}) == len(out)
    (HERE / "bench.jsonl").write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in out) + "\n", encoding="utf-8")
    print(f"{len(out)} items from {len(seeds)} seed claims:", dict(n))


if __name__ == "__main__":
    main()
