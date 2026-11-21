"""Claim detection: which sentences of the input need checking (check-worthiness) and what kind they are."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .textutil import (checkworthiness, claim_kind, content_words, is_meta_sentence, is_question, normalize_ws,
                       question_to_claim, split_meta, split_sentences, strip_preamble)

_NOISE = re.compile(r"(https?://\S+|#\w+|@\w+|\b(udostępnij|udostępniaj|przekaż dalej|share|pilne!+|zobacz)\b)", re.I)


@dataclass
class Claim:
    text: str  # as shown to the user (original sentence)
    query: str  # normalised form used for retrieval (questions turned into statements)
    kind: str  # fakt | opinia | pytanie | prognoza
    score: float


def extract_claims(text: str, max_claims: int = 3) -> list[Claim]:
    text = normalize_ws(text)
    if not text:
        return []
    sents = [s.strip() for s in split_sentences(text) if len(s.strip()) > 3]
    clean = lambda s: normalize_ws(_NOISE.sub(" ", s)).strip(" -–—•*")  # noqa: E731

    # Short inputs (typical chat question / single rumour): treat as one claim.
    if len(sents) <= 2 and len(text) <= 400:
        joined = clean(" ".join(sents)) or text
        if len(content_words(joined)) < 2:
            return []  # greeting / meta request without a checkable statement -> ask to clarify
        # a sentence about the check itself ("Dlaczego w analizie … jest 650 mln zł?") is not part of the claim
        kept, _meta = split_meta(" ".join(sents))
        core = strip_preamble(clean(kept) or joined)
        kind = claim_kind(core)
        q = question_to_claim(core) if is_question(core) else core
        k = "fakt" if kind == "pytanie" else kind  # a yes/no question about a fact is checked as a fact
        return [Claim(joined, q, k, checkworthiness(q))]

    cands: list[Claim] = []
    for s in sents:
        c = clean(s)
        if len(c.split()) < 4 or is_meta_sentence(c):
            continue
        kind = claim_kind(c)
        q = question_to_claim(c) if kind == "pytanie" else c
        score = checkworthiness(q)
        cands.append(Claim(c, q, "fakt" if kind == "pytanie" else kind, score))
    facts = sorted([c for c in cands if c.kind == "fakt"], key=lambda c: -c.score)
    chosen = [c for c in facts if c.score >= 0.4][:max_claims]
    if not chosen and cands:
        chosen = sorted(cands, key=lambda c: -c.score)[:1]
    # keep original order for readability
    order = {id(c): i for i, c in enumerate(cands)}
    return sorted(chosen, key=lambda c: order[id(c)])
