"""Build eval/bench_polish/bench.jsonl = seeded, stratified sample of Demagog claims  x  hand-written variants.

    backend/.venv/bin/python eval/bench_polish/build_dataset.py              # v1, the tuning split (default)
    backend/.venv/bin/python eval/bench_polish/build_dataset.py --set v2     # v2, the held-out split (*_v2 files)

The sample is deterministic (SEED, quotas per rating, round-robin over periods 2026 / 2025 / older). The variants in
variants.tsv were written by hand before any system output was inspected; they are joined to the sample by seed number.
Re-running after the corpus changed may pick different claims — then variants.tsv no longer matches and the script
refuses to write (the frozen sample is kept in seeds.json; pass --frozen to rebuild from it).

v2 is a second sample on different claims (other seed, v1 documents and near-duplicates excluded, see sample_v2). Its
seed numbers start at 101 so item ids never collide with v1. A hard negative in variants_v2.tsv carries its sub-type
after a colon ("hardneg:person"); the item type stays "hardneg" and the sub-type is stored in the "subtype" field.
"""
from __future__ import annotations

import collections
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SEED = 20261121
QUOTA = {"false": 12, "misleading": 7, "mixed": 4, "true": 7, "unverifiable": 2}
FC_TO_VERDICT = {"false": "falszywe", "misleading": "wprowadzajace_w_blad", "mixed": "wprowadzajace_w_blad",
                 "true": "potwierdzone", "unverifiable": "brak_dowodow"}
FLIP = {"falszywe": "potwierdzone", "potwierdzone": "falszywe"}
# v2: same proportions as v1 scaled to 48 claims. The corpus holds only 3 "Nieweryfikowalne" claims and v1 uses 2 of
# them, so v2 can have 1; the two missing slots go to "mixed" and "misleading"/"true" (the scarce ratings).
SEED_V2 = 20261122
QUOTA_V2 = {"false": 18, "misleading": 11, "mixed": 7, "true": 11, "unverifiable": 1}
FIRST_NO_V2 = 101
HARDNEG_SUBTYPES = {"person", "place", "number", "predicate", "neighbour", "othercov"}
SUFFIX = {"v1": "", "v2": "_v2"}


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


_DUP_STOP = {"ktory", "ktora", "ktore", "ktorzy", "ktorych", "ktorym", "jest", "byly", "bylo", "byla", "bedzie", "oraz",
             "przez", "przyp", "demagog", "tylko", "jako", "takze", "rowniez", "ktos", "tego", "tych", "jego", "ich"}


def stems(text: str) -> set[str]:
    """Crude content-word set for the near-duplicate check: lower-case, diacritics stripped, words of 4+ letters cut
    to 5 characters (enough to conflate most Polish inflections), numbers kept whole."""
    t = unicodedata.normalize("NFKD", text.lower().replace("ł", "l"))
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return {w if w[0].isdigit() else w[:5] for w in re.findall(r"[a-z0-9]+", t)
            if (len(w) >= 4 or w[0].isdigit()) and w not in _DUP_STOP}


def near_dup(a: dict, b: dict) -> bool:
    """Same story checked twice? Lexical overlap of claim vs claim, or of claim+title vs claim+title."""
    for fa, fb in ((a["claim"], b["claim"]), (a["claim"] + " " + a["title"], b["claim"] + " " + b["title"])):
        x, y = stems(fa), stems(fb)
        inter = len(x & y)
        if inter >= 3 and (inter / len(x | y) >= 0.35 or inter / min(len(x), len(y)) >= 0.6):
            return True
    return False


def load_skips() -> dict[str, str]:
    """Manual exclusions for v2 (id|reason): claims that are not self-contained statements, or the same story as a v1
    seed / another v2 seed that the lexical check did not catch. Decided from the claim text alone, before any run."""
    path, out = HERE / "sample_skips_v2.tsv", {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                doc_id, reason = line.split("|", 1)
                out[doc_id.strip()] = reason.strip()
    return out


def sample_v2(rows: list[dict], v1_seeds: list[dict], log: list | None = None) -> list[dict]:
    """Same stratification as sample() (quota per rating, round-robin over 2026 / 2025 / older), other seed, and three
    exclusions applied while walking the shuffled strata: v1 seed documents, near-duplicates of a v1 seed or of an
    already picked v2 claim (near_dup), and the manual skip list (load_skips). The shuffle does not depend on the
    exclusions, so adding a skip only replaces that claim with the next one of its stratum."""
    rng = random.Random(SEED_V2)
    v1_ids = {s["id"] for s in v1_seeds}
    skips = load_skips()
    log = log if log is not None else []
    picked: list[dict] = []
    for v, n in QUOTA_V2.items():
        by = {"2026": [], "2025": [], "old": []}
        for r in sorted((r for r in rows if eligible(r) and r["verdict"] == v), key=lambda r: r["id"]):
            y = (r.get("published_at") or "")[:4]
            by[y if y in ("2026", "2025") else "old"].append(r)
        for k in by:
            rng.shuffle(by[k])
        order, i, got = ["2026", "2025", "old"], 0, 0
        while got < n and any(by.values()):
            k = order[i % 3]
            i += 1
            while by[k]:
                r = by[k].pop()
                dup = next((s for s in v1_seeds + picked if near_dup(r, s)), None)
                if r["id"] in v1_ids:
                    log.append((r["id"], "v1 seed"))
                elif r["id"] in skips:
                    log.append((r["id"], "manual: " + skips[r["id"]]))
                elif dup:
                    log.append((r["id"], "near-duplicate of " + dup["id"]))
                else:
                    picked.append(r)
                    got += 1
                    break
    return picked


def main() -> None:
    which = sys.argv[sys.argv.index("--set") + 1] if "--set" in sys.argv else "v1"
    if which not in SUFFIX:
        sys.exit("--set must be v1 or v2")
    sfx = SUFFIX[which]
    rows = [json.loads(l) for l in (ROOT / "data/corpus/demagog.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    by_id = {r["id"]: r for r in rows}
    seeds_path = HERE / f"seeds{sfx}.json"
    if "--frozen" in sys.argv or seeds_path.exists():
        seeds = json.loads(seeds_path.read_text(encoding="utf-8"))
        missing = [s["id"] for s in seeds if s["id"] not in by_id]
        if missing:
            sys.exit(f"seed documents no longer in data/corpus/demagog.jsonl: {missing}")
    else:
        if which == "v2":
            log: list = []
            chosen, first = sample_v2(rows, json.loads((HERE / "seeds.json").read_text(encoding="utf-8")), log), FIRST_NO_V2
            for doc_id, reason in log:
                print(f"skipped {doc_id}: {reason}")
        else:
            chosen, first = sample(rows), 1
        seeds = [{"no": i + first, "id": r["id"], "claim": r["claim"], "rating": r["verdict"], "rating_raw": r["verdict_raw"],
                  "published_at": r.get("published_at"), "title": r["title"]} for i, r in enumerate(chosen)]
        seeds_path.write_text(json.dumps(seeds, ensure_ascii=False, indent=1), encoding="utf-8")
    by_no = {s["no"]: s for s in seeds}
    out, n = [], collections.Counter()
    variants_path = HERE / f"variants{sfx}.tsv"
    if not variants_path.exists():
        sys.exit(f"{seeds_path.name} written ({len(seeds)} claims); {variants_path.name} does not exist yet")
    for line in variants_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        no, typ, text = line.split("|", 2)
        typ, _, subtype = typ.partition(":")
        if subtype and (typ != "hardneg" or subtype not in HARDNEG_SUBTYPES):
            sys.exit(f"bad type in {variants_path.name}: {line[:60]}")
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
        if subtype:
            out[-1]["subtype"] = subtype
    assert len({o["id"] for o in out}) == len(out)
    (HERE / f"bench{sfx}.jsonl").write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in out) + "\n", encoding="utf-8")
    print(f"{len(out)} items from {len(seeds)} seed claims:", dict(n))


if __name__ == "__main__":
    main()
