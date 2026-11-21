"""Paired comparison of two benchmark runs:  compare.py <baseline-name> <variant-name>

Prints aggregate numbers, items FIXED / BROKEN by the variant (paired flips), new false verdicts, per-type deltas and an
exact two-sided sign test (McNemar) on the discordant pairs. With ~170 items only the flips are informative.
"""
from __future__ import annotations

import json
import sys
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name: str) -> dict:
    return json.loads((HERE / "results" / f"{name}.json").read_text(encoding="utf-8"))


def sign_test(b: int, c: int) -> float:
    n, k = b + c, min(b, c)
    return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def main() -> None:
    a_name, b_name = sys.argv[1], sys.argv[2]
    a, b = load(a_name), load(b_name)
    ra, rb = {r["id"]: r for r in a["rows"]}, {r["id"]: r for r in b["rows"]}
    for k in ("accuracy", "macro_f1", "correct", "abstain_miss", "false_verdicts"):
        print(f"{k:16} {a['summary'][k]!s:>8} -> {b['summary'][k]!s:>8}")
    for key, v in a["summary"]["retrieval"].items():
        w = b["summary"]["retrieval"][key]
        print(f"{key:18} R@1 {v['R@1']:.3f}->{w['R@1']:.3f}  R@5 {v['R@5']:.3f}->{w['R@5']:.3f}  MRR {v['MRR']:.3f}->{w['MRR']:.3f}")
    print("latency", a["summary"]["latency_ms"], "->", b["summary"]["latency_ms"])
    fixed = [i for i in ra if ra[i]["outcome"] != "correct" and rb[i]["outcome"] == "correct"]
    broken = [i for i in ra if ra[i]["outcome"] == "correct" and rb[i]["outcome"] != "correct"]
    new_fv = [i for i in ra if ra[i]["outcome"] != "false_verdict" and rb[i]["outcome"] == "false_verdict"]
    gone_fv = [i for i in ra if ra[i]["outcome"] == "false_verdict" and rb[i]["outcome"] != "false_verdict"]
    print(f"\nfixed {len(fixed)}: {fixed}\nbroken {len(broken)}: {broken}")
    print(f"new false verdicts {len(new_fv)}: {new_fv}\nremoved false verdicts {len(gone_fv)}: {gone_fv}")
    print(f"exact sign test on {len(fixed) + len(broken)} discordant pairs: p = {sign_test(len(fixed), len(broken)):.3f}")
    print("\nper type (correct):")
    for t, v in a["summary"]["by_type"].items():
        w = b["summary"]["by_type"][t]
        print(f"  {t:9} n={v['n']:3}  correct {v['correct']:3} -> {w['correct']:3}   false verdicts {v['false_verdict']} -> {w['false_verdict']}")
    # rank flips on the lexical side (the only place an analyzer can act)
    for key in ("claim_bm25_rank", "chunk_bm25_rank"):
        up = down = 0
        for i in ra:
            x, y = ra[i].get("trace", {}).get(key, 0), rb[i].get("trace", {}).get(key, 0)
            if x == 0 and y == 0:
                continue
            x, y = x or 999, y or 999
            up += y < x
            down += y > x
        print(f"{key}: gold doc ranked better in {up} items, worse in {down} (sign test p = {sign_test(up, down):.3f})")


if __name__ == "__main__":
    main()
