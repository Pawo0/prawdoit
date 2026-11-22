"""Extract checkable claims and distinguish facts, opinions and predictions.

Claim detection: which sentences of the input need checking (check-worthiness) and what kind they are.

Reading guide: docs/backend/REQUEST_FLOW.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .linefilter import drop_metadata_lines
from .textutil import (
    _FACTUAL_CUE,
    checked_question,
    checkworthiness,
    claim_kind,
    content_words,
    drop_pii_tags,
    is_meta_sentence,
    is_question,
    normalize_ws,
    question_to_claim,
    split_meta,
    split_sentences,
    strip_preamble,
    tokens,
)

# "pilne!+" inside \b…\b never matched (no word boundary after "!"), so "PILNE!!" stayed in the query
_NOISE = re.compile(
    r"(https?://\S+|#\w+|@\w+|\b(udostępnij|udostępniaj|przekaż dalej|share|zobacz)\b|\bpilne\s*[!:]+)",
    re.I,
)


@dataclass
class Claim:
    text: str  # as shown to the user (original sentence)
    query: str  # normalised form used for retrieval (questions turned into statements)
    kind: str  # fakt | opinia | pytanie | prognoza
    score: float
    meta: str = (
        ""  # sentences about the check itself ("Skąd w tym raporcie 12 tys. osób?"), not in the query
    )
    span: tuple[int, int] | None = (
        None  # where the claim's sentence(s) stand in the (whitespace-normalised) input
    )


# A sentence that leans on the one before it: it opens with an anaphor or a connective ("To…", "Wtedy…", "Dlatego…",
# "Ale…", also after a light "A"/"I"), or a personal pronoun stands among its first words. Such a sentence is part of
# the previous claim, not a claim of its own.
_DEPENDENT_OPENER = re.compile(
    r"^(?:(?:a|i|oraz)\s+)?(?:to|ten|ta|te|tego|tej|temu|tym|tę|tą|ci|tam|tu|tutaj|stąd|wtedy|wówczas|potem|później|"
    r"następnie|dlatego|więc|zatem|toteż|ale|jednak|lecz|natomiast|ponadto|poza\s+tym|co\s+więcej|również|także|też|"
    r"tymczasem|przez\s+to|dzięki\s+temu|mimo\s+to|mimo\s+tego|w\s+dodatku|na\s+dodatek|dodatkowo|zresztą|czyli|"
    r"bo|ponieważ|gdyż|albowiem|tak|taki|taka|takie|właśnie|nawet|przecież|wcześniej|owszem|stąd)\b",
    re.I,
)
_PRONOUN = re.compile(
    r"^(?:on|ona|ono|oni|one|jego|jej|ich|go|mu|nim|niej|nich|niego|niemu|jemu|tam|tu|tutaj|wtedy|"
    r"wówczas)$",
    re.I,
)
_PAST_WORD = re.compile(r"^\w{3,}(?:ł|ła|ło|li|ły)$", re.I)
_VERB_OPENER = re.compile(
    r"^(?:jest|są|był|była|było|były|będzie|będą|ma|mają|istnieje|istnieją|krąży|krążą|widać|"
    r"można|trzeba|chodzi|wychodzi|okazuje|wiadomo|mówi|mówią|piszą|pisze)$",
    re.I,
)


def _depends_on_previous(sent: str, prev: str) -> bool:
    """True when `sent` cannot stand as a claim without `prev`: an anaphoric / connective opening, a pronoun among the
    first three words, or no word of its own (every content word repeats `prev`, or it opens with a past-tense verb
    whose subject was in `prev`: "Podpisał ją w maju.")."""
    s = sent.strip(" „\"'(-–—")
    if _DEPENDENT_OPENER.match(s):
        return True
    words = re.findall(r"[^\W\d_]+", s)
    if any(_PRONOUN.match(w) for w in words[:3]):
        return True
    prev_stems = set(tokens(prev))
    own = [
        w
        for w in content_words(s)
        if not w.isdigit() and tokens(w) and tokens(w)[0] not in prev_stems
    ]
    own_nouns = [w for w in own if not _PAST_WORD.match(w)]
    if not own_nouns:
        return True
    # verb first ("Podpisał ją w maju.", "Zarobił na tym 2 mln zł.", "Jest nagranie w sieci."): the subject is the
    # previous sentence's, unless the sentence names an entity of its own (a capitalised word after the verb)
    rest = re.sub(r"^(?:a|i|oraz)\s+", "", s, flags=re.I)
    first = rest.split(" ")[0]
    verb_first = bool(
        _PAST_WORD.match(first)
        or _VERB_OPENER.match(first)
        or _FACTUAL_CUE.fullmatch(first.lower())
    )
    return verb_first and not any(w[:1].isupper() for w in rest.split()[1:])


def _standalone(core: str) -> tuple[str, str, float] | None:
    """(query, kind, score) when the sentence is a check-worthy factual statement on its own, else None."""
    kind = claim_kind(core)
    if kind not in ("fakt", "pytanie"):
        return None
    q = question_to_claim(core) if is_question(core) else core
    score = checkworthiness(q)
    if score < 0.4 or len(content_words(q)) < 2:
        return None
    return q, "fakt", score


def _locate(sent: str, text: str, start: int = 0) -> tuple[int, int] | None:
    """Character span of `sent` in `text` (at or after `start`); the splitter may have dropped a closing quote between
    sentences, so a word-by-word match is the fallback."""
    i = text.find(sent, start)
    if i >= 0:
        return i, i + len(sent)
    words = re.findall(r"\w+", sent)
    if not words:
        return None
    m = re.compile(r"\W+".join(map(re.escape, words))).search(text, start)
    return (m.start(), m.end()) if m else None


def _spans(sents: list[str], text: str) -> list[tuple[int, int] | None]:
    out, pos = [], 0
    for s in sents:
        sp = _locate(s, text, pos)
        out.append(sp)
        if sp:
            pos = sp[1]
    return out


def extract_claims(text: str, max_claims: int = 3) -> list[Claim]:
    """PII placeholders left by the early masking (service.run_check) stay in the claim text shown to the user, but
    never in the query used for retrieval and sent to live search."""
    claims = _extract(text, max_claims)
    for c in claims:
        c.query = drop_pii_tags(c.query)
    return claims


def _extract(text: str, max_claims: int) -> list[Claim]:
    base = normalize_ws(text)
    text = drop_metadata_lines(
        base
    )  # author / date / handle / interface / OCR-debris lines are not claims
    if not text:
        return []
    sents = [s.strip() for s in split_sentences(text) if len(s.strip()) > 3]
    spans = _spans(sents, base)
    clean = lambda s: normalize_ws(_NOISE.sub(" ", s)).strip(" -–—•*")  # noqa: E731

    # Short inputs (typical chat question / single rumour): one claim, unless each sentence is a factual statement
    # of its own ("<claim about A>? A <claim about B>.") — then one claim per sentence, at most max_claims.
    if len(sents) <= 2 and len(text) <= 400:
        joined = clean(" ".join(sents)) or text
        if len(content_words(joined)) < 2:
            return []  # greeting / meta request without a checkable statement -> ask to clarify
        separate = []
        for i, s in enumerate(sents):
            c = clean(s)
            found = None if is_meta_sentence(c) else _standalone(strip_preamble(c))
            if not found or (i and _depends_on_previous(c, clean(sents[i - 1]))):
                separate = []
                break
            query = re.sub(
                r"^(?:a|i|oraz)\s+", "", found[0], flags=re.I
            )  # "A <claim>": the conjunction is not the claim
            separate.append(Claim(c, query, found[1], found[2], span=spans[i]))
        if len(separate) > 1:
            return separate[:max_claims]
        # a sentence about the check itself ("Skąd w raporcie … 12 tys. osób?") is not part of the claim
        kept, meta = split_meta(" ".join(sents))
        core = strip_preamble(clean(kept) or joined)
        kind = claim_kind(core)
        q = question_to_claim(core) if is_question(core) else core
        k = (
            "fakt" if kind == "pytanie" else kind
        )  # a yes/no question about a fact is checked as a fact
        known = [sp for sp in spans if sp]
        return [
            Claim(
                joined,
                q,
                k,
                checkworthiness(q),
                meta,
                (known[0][0], known[-1][1]) if known else None,
            )
        ]

    cands: list[Claim] = []
    for s, sp in zip(sents, spans):
        c = clean(s)
        if len(c.split()) < 4 or is_meta_sentence(c):
            continue
        kind = claim_kind(c)
        q = question_to_claim(c) if kind == "pytanie" else c
        score = checkworthiness(q)
        cands.append(Claim(c, q, "fakt" if kind == "pytanie" else kind, score, span=sp))
    facts = sorted([c for c in cands if c.kind == "fakt"], key=lambda c: -c.score)
    chosen = [c for c in facts if c.score >= 0.4][:max_claims]
    if not chosen and cands:
        chosen = sorted(cands, key=lambda c: -c.score)[:1]
    # keep original order for readability
    order = {id(c): i for i, c in enumerate(cands)}
    chosen = sorted(chosen, key=lambda c: order[id(c)])
    # "Czy ktoś to sprawdzał? <claim> <date>": the question about who checked it stays out of the query, but is
    # kept in the text shown with each claim, so the answer can say who checked it (answer.py)
    asked = next((clean(s) for s in sents if checked_question(clean(s)) is not None), None)
    if asked:
        chosen = [Claim(f"{asked} {c.text}", c.query, c.kind, c.score, span=c.span) for c in chosen]
    meta = " ".join(
        clean(s) for s in sents if is_meta_sentence(clean(s)) and checked_question(clean(s)) is None
    )
    if meta:
        chosen = [Claim(c.text, c.query, c.kind, c.score, meta, c.span) for c in chosen]
    return chosen
