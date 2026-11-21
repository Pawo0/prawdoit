"""Model-free check of the name/number agreement guard (backend/prawdowid/agreement.py) on every Polish fact-checked
claim of the corpus — not on benchmark items. Runs in about half a minute, loads no model.

    backend/.venv/bin/python eval/bench_polish/guard_check.py

Part 1, benign rewrites: a claim compared with a harmless rewrite of itself (lower case, no diacritics, capitals,
one sentence only, surnames only, numbers respelled, question form) must NOT be read as a disagreement.
Part 2, synthetic swaps: a claim compared with a copy in which one name, or one number, was replaced MUST be.
The swaps are in place (the rest of the sentence is untouched), which is the case the guard is built for; they say
nothing about swaps inside a reworded sentence.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from prawdowid import agreement as ag  # noqa: E402
from prawdowid.textutil import split_sentences  # noqa: E402

PLAIN = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def load_claims() -> list[str]:
    claims = []
    for f in sorted((ROOT / "data" / "corpus").glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("claim") and d.get("source_type") == "factcheck" and d.get("language", "pl") == "pl":
                claims.append(d["claim"])
    return list(dict.fromkeys(claims))


def surnames_only(c: str) -> str:
    side = ag._read(c)
    for si, first, last, sure in side.groups:
        toks = side.sentences[si]
        if last > first and sure:
            c = c.replace(" ".join(t.text for t in toks[first:last + 1]), toks[last].text, 1)
    return c


def numbers_respelled(c: str) -> str:
    c = re.sub(r"(?<![\d,.])(\d+) tys\.", lambda m: f"{m.group(1)} 000", c)
    c = re.sub(r"(\d) proc\.", r"\1%", c)
    return re.sub(r"(?<![\d,.])(\d+) mln\b", lambda m: f"{m.group(1)} milionów", c)


BENIGN = {
    "identical": lambda c: c,
    "lower case, no diacritics": lambda c: c.translate(PLAIN).lower(),
    "lower case": lambda c: c.lower(),
    "no diacritics": lambda c: c.translate(PLAIN),
    "CAPITALS": lambda c: c.upper(),
    "first sentence only": lambda c: split_sentences(c)[0],
    "last sentence only": lambda c: split_sentences(c)[-1],
    "surnames only": surnames_only,
    "numbers respelled (tys.→000, proc.→%, mln→milionów)": numbers_respelled,
    "as a question": lambda c: "czy to prawda, że " + c[0].lower() + c[1:].rstrip(".") + "?",
}


def main() -> None:
    claims = load_claims()
    print(f"{len(claims)} Polish fact-checked claims\n\nbenign rewrites — read as disagreement (should be 0):")
    for name, fn in BENIGN.items():
        pairs = [(c, fn(c)) for c in claims if name == "identical" or fn(c) != c]
        fires = [(u, c, ag.disagreement(u, c)) for c, u in pairs if ag.disagreement(u, c)]
        print(f"  {name:52} {len(fires):4} of {len(pairs):5}")
        for u, c, note in fires[:2]:
            print(f"      {note} | {u[:90]}")

    named = []  # (claim, first sure name that does not open a sentence)
    for c in claims:
        side = ag._read(c)
        g = [(si, a, b) for si, a, b, sure in side.groups if sure and a > 0]
        if g:
            si, a, b = g[0]
            named.append((c, " ".join(t.text for t in side.sentences[si][a:b + 1])))
    swaps = []
    for i, (c, name) in enumerate(named):
        for j in range(1, len(named)):  # a name from another claim that this claim does not mention
            other = named[(i + j * 7) % len(named)][1]
            if not ag.same_word(ag.fold(other.split()[-1]), ag.fold(name.split()[-1])) \
                    and not ag._group_mentioned(other.split(), ag._read(c)):
                swaps.append((c, c.replace(name, other, 1)))
                break
    print("\nsynthetic swaps — detected (should be high):")
    for label, fn in (("one name replaced", lambda u: u), ("one name replaced, lower case, no diacritics", lambda u: u.translate(PLAIN).lower())):
        hit = sum(1 for c, u in swaps if ag.names_disagree(fn(u), c))
        print(f"  {label:52} {hit:4} of {len(swaps):5} ({100 * hit / max(1, len(swaps)):.1f}%)")
    numbered = [(c, m) for c in claims for m in [re.search(r"(?<![\w-])(\d{2,4})(?![\d.,])", c)] if m and ag.quantities(c)]
    nswaps = [(c, c[:m.start(1)] + str(int(m.group(1)) * 3 + 7) + c[m.end(1):]) for c, m in numbered]
    hit = sum(1 for c, u in nswaps if ag.numbers_disagree(u, c))
    print(f"  {'one number n replaced by 3n+7':52} {hit:4} of {len(nswaps):5} ({100 * hit / max(1, len(nswaps)):.1f}%)")


if __name__ == "__main__":
    main()
