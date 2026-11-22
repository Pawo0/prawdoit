"""Evidence preparation and ordered verdict rules for one extracted claim.

Verification engine: claim -> evidence -> stance -> explicit, ordered rules -> verdict with premises.

Design principle (challenge requirement): the language model never decides what is true. Verdicts come from
transparent, versioned rules (R1–R6, see /metodologia) over retrieved, cited evidence. Models are used only to
*understand* text: embeddings for retrieval / claim matching, NLI for stance.

Source tiers (by source type and process — never by political orientation or domain reputation):
  A (1) źródło pierwotne / urzędowe   B (2) fact-checking IFCN/EFCSN   B (3) baza incydentów   C (4) media
Only tiers 1 and 2 settle a verdict alone; a catalogue entry is context unless a tier 1-2 source agrees.

Reading guide: docs/backend/ENGINE.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

import numpy as np

from . import grounding, measures
from .agreement import disagreement, fold, same_word
from .claims import Claim
from .config import settings
from .index import INDEX, TIER
from .nli import NLI_MODEL, NLIScore
from .schemas import VERDICT_LABEL_PL, ClaimResult, Evidence, Premise
from .textutil import (
    HIGH_RISK,
    amounts,
    is_time_sensitive,
    normalize_ws,
    rule_scope,
    same_amount,
    short,
    split_sentences,
    tokens,
    unmark_excerpt,
    years_in,
)

log = logging.getLogger("prawdowid.engine")

FC_TO_VERDICT = {
    "false": "falszywe",
    "misleading": "wprowadzajace_w_blad",
    "mixed": "wprowadzajace_w_blad",
    "true": "potwierdzone",
    "unverifiable": "brak_dowodow",
}


@dataclass
class _Cand:
    doc_idx: int
    chunk_text: str
    retrieval: float
    cos: float
    fragment: str = ""
    frag_cos: float = 0.0
    is_claim_match: bool = False
    claim_cos: float = 0.0
    nli: object | None = None  # NLI(fragment -> claim) for tier A/C
    nli_claim: object | None = (
        None  # NLI(user claim -> fact-checked claim): does the user assert the checked claim?
    )
    nli_claim_rev: object | None = (
        None  # NLI(fact-checked claim -> user claim): used only for negation detection
    )
    numeric: str | None = (
        None  # deterministic number check vs. an official fact card: "zgodne" | "niezgodne"
    )
    extra_irrelevant: bool = False  # official card about another period / currency / act
    # number differs, but the claim may use another definition of the indicator (measures.py): the note saying why
    definitional: str = ""
    # one sentence of a multi-sentence checked claim (see _claim_units): the user often repeats only the rated core
    unit: str = ""
    unit_cos: float = 0.0
    nli_unit: object | None = None  # NLI(user claim -> unit)
    nli_unit_rev: object | None = None  # NLI(unit -> user claim)
    nli_head_unit: object | None = (
        None  # NLI(fact-checker's headline -> unit): does the headline deny / affirm it?
    )
    explains: bool = (
        False  # fragment = the passage giving the number the user asks about (asked_number_fragment)
    )
    archival: tuple[int, int] | None = (
        None  # (year of the material per the analysis, year it is presented as)
    )
    alternatives: tuple[
        tuple[str, float], ...
    ] = ()  # fact-checks: the best-scoring quotable windows, best first
    # fact-check match: same (True = the user asserts the checked claim, False = its opposite), the verdict it implies
    # for the user's claim, and whether it was matched through one sentence of the checked claim (claim_units)
    same: bool | None = None
    implied: str | None = None
    via_unit: bool = False


def _fmt_date(s: str | None) -> str:
    if not s:
        return "brak daty"
    y, m, d = (s[:10].split("-") + ["", ""])[:3]
    return f"{d}.{m}.{y}" if d else s


# How a fact-check states its finding, as opposed to the sentences that retell the viral claim (genre cues, not topics)
_FINDING = re.compile(
    r"\b(?:w rzeczywistości|w istocie|tak naprawdę|faktycznie|w praktyce|wyrwan\w* z kontekstu|nie (?:jest|są|był\w*|"
    r"został\w*|ma|mają|dotycz\w*|pokazuj\w*|przedstawia\w*|oznacza|wynika|potwierdza\w*)|nigdy nie|nie ma (?:żadnych )?"
    r"(?:dowod\w*|danych|informacji|podstaw)|brak (?:jest )?(?:dowod\w*|potwierdzeni\w*)|pochodz\w* z|sprzed|"
    r"archiwaln\w*|(?:nagrani\w*|film\w*|wideo|zdjęci\w*|materiał\w*) (?:z|sprzed) |"
    r"(?:dane|statystyk\w*|badani\w*|raport\w*|analiz\w*)\b[^.]{0,80}\b(?:pokazuj\w*|wskazuj\w*|wynika|potwierdzaj\w*)|"
    r"wynika z|według (?:danych|ekspert\w*|naukowc\w*)|wbrew|nie potwierdz\w*|zaprzecz\w*|zdementowa\w*|dementuj\w*|"
    r"(?:poprawn|prawidłow|błędn|nieścisł|zawyżon|zaniżon)\w*)",
    re.I,
)
# The fact-checker's verdict words ("to nieprawda", "fałsz", "manipulacja", "zgodne z prawdą"): a finding cue too, but
# one about the CHECKED claim. When the user asserts the opposite of that claim (claim match with same=False), the
# words describe the claim the user denies, so a window that carries only them is no finding for the user's claim.
_VERDICT_WORD = re.compile(
    r"\b(?:nieprawd\w*|fałsz\w*|manipulac\w*|zmanipulowan\w*|wprowadza\w* w błąd|zgodn\w* z prawdą|częściow\w* prawd\w*|nie oznacza|nie dowodzi)",
    re.I,
)
_RETELLS = re.compile(
    r"\b(?:rzekom\w*|krąż\w*|pojawi\w* się\s+(?:\w+\s+){0,3}?(?:wpis\w*|post\w*|nagrani\w*|film\w*|informacj\w*|"
    r"zdjęci\w*|artykuł\w*|grafik\w*|materiał\w*)|internau\w*|autorzy?\s+(?:post\w*|wpis\w*|nagrani\w*|materiał\w*)|"
    r"twierdz\w*|sugeruj\w*|przekonuj\w*|alarmuj\w*|w mediach społecznościowych|w sieci)\b",
    re.I,
)


def _finding_score(
    w: str, q_tokens: set[str], fc_tokens: set[str], claim_text: str, opposite: bool = False
) -> float:
    """Bonus for a fact-check window that carries the finding rather than the claim: a finding cue, a year earlier
    than the one the claim speaks of, an amount that differs from the claim's; a penalty for retelling the claim
    ("Na Facebooku pojawiło się nagranie rzekomo…") and for a near-restatement (hardly a word beyond the user's claim
    and the checked claim). opposite: the analysis rated the opposite of the user's claim, so its verdict words
    (_VERDICT_WORD) earn nothing."""
    wt = set(tokens(w))
    bonus = 0.3 if _FINDING.search(w) or (not opposite and _VERDICT_WORD.search(w)) else 0.0
    if _RETELLS.search(w):
        bonus -= 0.25
    if wt and len(wt - q_tokens - fc_tokens) / len(wt) < 0.3:
        bonus -= 0.4
    claim_years = years_in(claim_text)
    if claim_years and any(y < min(claim_years) for y in years_in(w)):
        bonus += 0.15
    stated = amounts(claim_text)
    if stated and any(a[1] == x[1] and not same_amount(a, x) for a in amounts(w) for x in stated):
        bonus += 0.15
    return bonus


_QUOTE_OPENERS = "-–•* „\"'«("
MID_SENTENCE_PENALTY = (
    0.4  # as heavy as a near-restatement (_finding_score): a cut quote is as weak a quote
)


def _starts_mid_sentence(window: str, source: str) -> bool:
    """Does this quote begin inside a sentence of the source? The sentence splitter also breaks at a line break
    inside a sentence and after an abbreviation it did not recognise, so a window can start mid-sentence: with a
    lowercase letter, with a closing bracket it never opened, inside a word, or right after a comma or semicolon.
    `source` is the whitespace-squashed text the window was cut from."""
    w = window.lstrip(_QUOTE_OPENERS)
    if not w:
        return False
    if w[0].islower():
        return True
    close, opening = w.find(")"), w.find("(")
    if close >= 0 and (opening < 0 or close < opening):
        return True
    i = source.find(window)
    if i <= 0:
        return False
    return source[i - 1].isalnum() or source[:i].rstrip().endswith((",", ";"))


def _best_fragment(
    doc_idx: int,
    q_emb: np.ndarray,
    q_tokens: set[str],
    claim_text: str = "",
    opposite: bool = False,
) -> tuple[str, float, tuple[tuple[str, float], ...]]:
    """Pick the quoted fragment WITHOUT re-encoding: best chunk of the document by (cached) embedding similarity,
    then the 1–2 consecutive sentences with the highest lexical overlap with the claim, cut verbatim out of the
    stored source text (see _fragment_windows). This exact span is both quoted to the user and judged by NLI.
    Returns (fragment, chunk similarity, the best few windows with their scores: fact-checks only, for the NLI
    re-ranking in verify_claim). opposite: see _finding_score (known only after claim matching, see verify_claim).
    """
    ids = [i for i in INDEX.doc_chunks[doc_idx] if i not in INDEX.synthetic]
    d = INDEX.docs[doc_idx]
    if not ids:
        return (d.text or d.title)[:400], 0.0, ()
    sims = INDEX.chunk_emb[ids] @ q_emb
    j = int(np.argmax(sims))
    text, cos = INDEX.chunks[ids[j]].text, float(sims[j])
    windows = _fragment_windows(text, d.text or "")
    head_tokens: set[str] = set()
    if d.claim and d.source_type in ("factcheck", "incident"):
        # A fact-check's text starts by restating the checked claim, which always overlaps the user's words most and
        # wins the best chunk. Quoting it back proves nothing: the quote must be the analysis' finding. So the whole
        # analysis is searched (the claim's own sentences left out) for the passage that shares most words with the
        # user's claim AND with the fact-checker's headline, which states the finding ("Szkoła w gminie nie została
        # zamknięta"), and that reads as a finding (_finding_score). The claim itself is quoted only when the record
        # has nothing else.
        own = [
            w for w in _fragment_windows(d.text or "", d.text or "") if not _restates(w, d.claim)
        ]
        if own:
            findings = [window for window in own if grounding.has_finding(window)]
            windows, head_tokens = list(dict.fromkeys(findings or own)), set(tokens(d.title))
    if (
        not windows
    ):  # nothing of this passage can be found in the stored text (e.g. a title-only document)
        windows = [([x for x in split_sentences(text) if len(x) > 15] or [text])[0][:520]]
    fc_tokens = set(tokens(d.claim or ""))
    src = _squash(d.text or "")

    def score(w: str) -> float:
        wt = set(tokens(w))
        head = len(head_tokens & wt) / len(head_tokens) if head_tokens else 0.0
        base = (
            len(q_tokens & wt) / max(1, len(q_tokens)) + head - len(w) / 5000
        )  # prefer shorter on ties
        if not head_tokens:
            return base
        cut = (
            MID_SENTENCE_PENALTY if _starts_mid_sentence(w, src) else 0.0
        )  # a whole-sentence quote of the finding
        return base + _finding_score(w, q_tokens, fc_tokens, claim_text, opposite) - cut

    ranked = sorted(((w, score(w)) for w in windows), key=lambda x: -x[1])
    if not head_tokens:
        return ranked[0][0], cos, ()
    # a leading list bullet of the analysis is not part of the quote
    ranked = [((w.lstrip("-–•* ") or w), sc) for w, sc in ranked]
    shortlist = ranked[:3]
    findings = sorted(
        ranked,
        key=lambda item: -_finding_score(item[0], q_tokens, fc_tokens, claim_text, opposite),
    )
    if findings and findings[0] not in shortlist:
        shortlist.append(findings[0])
    contextual = [
        item
        for item in ranked
        if _VERDICT_WORD.search(item[0])
        and _finding_score(item[0], q_tokens, fc_tokens, claim_text, opposite) > 0
    ]
    if contextual and contextual[0] not in shortlist:
        shortlist.append(contextual[0])
    if re.search(r"\d", claim_text):
        complete = [
            item for item in ranked if grounding.numeric_support_complete(claim_text, item[0])
        ]
        if complete and complete[0] not in shortlist:
            shortlist.append(complete[0])
    return ranked[0][0], cos, tuple(shortlist)


def _ground_factchecks(claim, support, refute, misleading, evidence) -> list[str]:
    """Verify displayed findings, including misleading ratings, before R2–R5.

    No semantic inference from the rating itself. Direct support/refutation uses
    NLI on the quote, its matched checked claim, or a refuting headline. A
    misleading finding must show a limitation or an explicit contextual judgment.
    Both routes reject questions, allegation-only passages and mismatched scope.
    The per-document budget is bounded and cannot be consumed by earlier docs.
    """
    work, pairs, best = [], [], {}
    for group, direction in ((support, "entail"), (refute, "contra"), (misleading, "context")):
        for candidate in group:
            document = INDEX.docs[candidate.doc_idx]
            if document.source_type not in ("factcheck", "incident") or candidate.archival:
                continue
            windows = list(
                dict.fromkeys([candidate.fragment, *(w for w, _ in candidate.alternatives)])
            )[:6]
            for window in windows:
                if not (_quote_ok(window, document.text or "") and grounding.has_finding(window)):
                    continue
                if not grounding.comparable_scope(claim.query, window):
                    continue
                if direction == "entail" and not grounding.numeric_support_complete(
                    claim.query, window
                ):
                    continue
                if direction in ("contra", "context") and not grounding.has_numeric_comparison(
                    claim.query, window
                ):
                    continue
                # The checked claim can be a clearer wording of the same claim.
                # Matching has already checked polarity, entities and quantities;
                # the excerpt must still justify the corresponding relation.
                hypotheses = [(claim.query, direction)]
                checked = candidate.unit if candidate.via_unit else document.claim
                if checked and candidate.same is not None and direction != "context":
                    checked_direction = (
                        direction
                        if candidate.same
                        else {"contra": "entail", "entail": "contra"}[direction]
                    )
                    hypotheses.append((checked, checked_direction))
                headline = headline_statement(document.title)
                if headline and (
                    direction == "context" or (direction == "contra" and candidate.same is True)
                ):
                    hypotheses.append((headline, "entail"))
                if direction == "context":
                    # Partial truth needs evidence of a limitation, not an NLI
                    # entailment of the allegation as retold in the article.
                    hypotheses = [(claim.query, "contra")]
                    if headline:
                        hypotheses.append((headline, "entail"))
                    if (
                        _VERDICT_WORD.search(window)
                        and _finding_score(
                            window,
                            set(tokens(claim.query)),
                            set(tokens(document.claim or "")),
                            claim.query,
                        )
                        > 0
                    ):
                        # An explicit contextualised finding of the matched analysis.
                        # This is a deterministic finding rule, not a model score.
                        best.setdefault(candidate.doc_idx, (1.0, window))
                for hypothesis, relation in dict.fromkeys(hypotheses):
                    work.append((candidate, relation, window))
                    pairs.append((window, hypothesis))
    for (candidate, direction, window), stance in zip(work, NLI_MODEL.score(pairs)):
        wanted = stance.contra if direction == "contra" else stance.entail
        opposite = stance.entail if direction == "contra" else stance.contra
        if wanted >= settings.nli_strong and wanted > max(opposite, stance.neutral):
            old = best.get(candidate.doc_idx)
            if old is None or wanted > old[0]:
                best[candidate.doc_idx] = (wanted, window)
    rejected = []
    for group in (support, refute, misleading):
        for candidate in group[:]:
            document = INDEX.docs[candidate.doc_idx]
            if document.source_type not in ("factcheck", "incident") or candidate.archival:
                continue
            accepted = best.get(candidate.doc_idx)
            if accepted:
                candidate.fragment = accepted[1]
            else:
                group.remove(candidate)
                # _decisive in answer.py also uses the rating + same_claim, so
                # clear that match as well as the engine's stance.
                candidate.implied = None
                rejected.append(document.id)
            for item in evidence:
                if item.doc_id == document.id:
                    if accepted:
                        item.fragment = shown_fragment(candidate.fragment, document.text or "")
                    else:
                        item.stance = "kontekst"
                        item.same_claim = None
    return rejected


def _words(s: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", (s or "").lower()))


def _restates(window: str, claim: str) -> bool:
    """Is this quote (part of) the checked claim? Compared word by word, so a hyphen in the claim field and an en dash
    in the text do not matter."""
    w, c = _words(window), _words(claim)
    if not w or w in c:
        return True
    return any(len(s) >= 20 and s in w for s in (_words(x) for x in split_sentences(claim)))


def _squash(s: str) -> str:
    """Whitespace-normalised text: the form in which a quote is compared with its source (_quote_ok)."""
    return re.sub(r"\s+", " ", normalize_ws(s)).strip()


def _fragment_windows(
    passage: str, source: str, max_len: int = 520, min_len: int = 16, max_gap: int = 6
) -> list[str]:
    """Candidate quotes for a passage: every sentence, and every two NEIGHBOURING sentences, cut out of `source`.

    The sentence splitter is only used to find where sentences start and end. Each window is then a slice of the
    (whitespace-normalised) source text, so it is verbatim by construction: joining sentence strings instead would
    lose the closing quotation mark or bracket that the splitter consumes between two sentences, and joining the
    neighbours that remain after short sentences were filtered out would glue together sentences that are not
    adjacent in the source ("… – przyp." + "Po wojnie …", skipping "Demagog]."). Sentences shorter than `min_len` are
    not quoted on their own but do take part in pairs. A sentence the splitter has altered, so that it is no longer
    found in the source, is left out together with its pairs."""
    src = _squash(source)
    spans: list[tuple[int, int] | None] = []
    pos = 0
    for s in split_sentences(passage):
        s = _squash(s)
        i = src.find(s, pos) if s else -1
        if i < 0:
            spans.append(None)
            continue
        spans.append((i, i + len(s)))
        pos = i + len(s)
    singles = [(a, b) for sp in spans if sp for a, b in [sp] if b - a >= min_len]
    pairs = [(x[0], y[1]) for x, y in zip(spans, spans[1:]) if x and y and y[0] - x[1] <= max_gap]
    windows = [src[a:b] for a, b in singles + pairs if min_len <= b - a <= max_len]
    if not windows and singles:
        a, b = singles[0]
        windows = [src[a : a + max_len]]
    return windows


_YEAR_RX = re.compile(r"\b(19|20)\d\d\b")


def asked_number_fragment(text: str, claim_text: str, asked: list[tuple]) -> str | None:
    """'Skąd w analizie 36 mln zł?': the verbatim passage of the analysis that gives the asked number.
    Sentences of the checked claim itself are skipped. Among the passages that contain the number, the one that also
    states its period (a year) is preferred, so the quote shows what the figure refers to; then the shortest.
    """
    in_claim = _squash(claim_text)
    hits = [
        w
        for w in _fragment_windows(text, text)
        if w not in in_claim and any(same_amount(a, x) for a in asked for x in amounts(w))
    ]
    return min(hits, key=lambda w: (not _YEAR_RX.search(w), len(w))) if hits else None


# ------------------------------------------------------------------ old material presented as current (rule R3a)
# "Nagranie z wczorajszej demonstracji w X pokazuje Y" — a claim that a recording / photo shows an event of the time it
# was shared (a common misinformation pattern: real but old material re-shared as current). A fact-check about that material that dates it to an EARLIER year refutes it
# deterministically (the NLI model reads almost every sentence of such an analysis as a contradiction, so it cannot
# be used here). Same material = the analysis names at least two of the claim's proper names.
_MATERIAL = re.compile(
    r"\b(film\w*|nagra\w*|wideo|video|klip\w*|zdjęci\w*|zdjęć|fotografi\w*|materiał\w*)\b", re.I
)
# time markers that place the material at the time it was shared (used only when the claim gives no year)
_PRESENTED_NOW = re.compile(
    r"\b(ówczesn\w*|wówczas|aktualn\w*|bieżąc\w*|obecn\w*|dzisiejsz\w*|wczorajsz\w*|tegoroczn\w*|"
    r"najnowsz\w*|śwież\w*|teraz|dziś|dzisiaj|wczoraj|niedawn\w*|w tym roku)\b",
    re.I,
)
_ORIGIN = re.compile(
    r"\b(pochodz\w*|nagran\w*|nakręcon\w*|zarejestrowan\w*|wykonan\w*|zrobion\w*|powstał\w*)\b"
    r"[^.]{0,40}?\b(?:z|w|we)\s+(?:[^\W\d]+\s+){0,2}?((?:19|20)\d\d)\b",
    re.I,
)
_PROPER = re.compile(r"(?<=[\s(„\"])[A-ZĄĆĘŁŃÓŚŹŻ][\wąćęłńóśźż-]{2,}")


def presented_year(claim: str, published_at: str | None) -> int | None:
    """The year a claim about a material presents it as from: an explicit year, or — for 'ówczesny / aktualny /
    teraz' without one — the year the fact-check was published (when the material was being shared).
    """
    if not _MATERIAL.search(claim):
        return None
    years = [int(y) for y in re.findall(r"\b((?:19|20)\d\d)\b", claim)]
    if years:
        return max(years)
    if _PRESENTED_NOW.search(claim) and (published_at or "")[:4].isdigit():
        return int(published_at[:4])
    return None


def _names_shared(claim: str, text: str) -> int:
    names = {fold(w) for w in _PROPER.findall(f" {claim}")}
    words = {fold(w) for w in re.findall(r"[^\W\d_]+", text)}
    return sum(1 for n in names if any(same_word(n, w) for w in words))


def archival_origin(d, claim: str, year: int) -> tuple[str, int] | None:
    """(verbatim passage, year of the material) when the analysis says the material comes from before `year`."""
    names = {fold(w) for w in _PROPER.findall(f" {claim}")}
    if not names:
        return None
    in_claim = _squash(d.claim or "")
    best = None
    for w in _fragment_windows(d.text or "", d.text or ""):
        if w in in_claim:
            continue
        m = next(
            (
                m
                for s in split_sentences(w)
                if _MATERIAL.search(s)
                for m in [_ORIGIN.search(s)]
                if m
            ),
            None,
        )
        if not m or int(m.group(2)) >= year:
            continue
        shared = _names_shared(claim, f"{d.title} {d.claim or ''} {w}")
        if shared < min(2, len(names)):
            continue
        key = (_names_shared(claim, w), -len(w))
        if best is None or key > best[0]:
            best = (key, w.lstrip("-–•* "), int(m.group(2)))  # a leading bullet is not quoted
    return (best[1], best[2]) if best else None


def _relevance(q_tokens: set[str], text: str) -> float:
    """Validity gate V4: share of the claim's content words present in the source fragment/title."""
    return len(q_tokens & set(tokens(text))) / max(1, len(q_tokens))


def _quote_ok(fragment: str, doc_text: str) -> bool:
    """V2: the quoted fragment is a verbatim substring of the stored source text. _fragment_windows cuts every
    quote out of that text, so this holds by construction; it is asserted in tests/test_fragment_windows.py rather
    than re-checked on every answer (a runtime gate never fired: 0 of 145 eval cases)."""
    return _squash(fragment) in _squash(doc_text)


def shown_fragment(fragment: str, doc_text: str) -> str:
    """The fragment as the answer, the API and the UI show it: without the ELI ingest marker ("[fragment: „…”]"),
    which is not the publisher's text. What is left must still pass gate V2 (a verbatim slice of the stored text);
    if it did not, the fragment is shown as stored."""
    out = unmark_excerpt(fragment)
    return out if out == fragment or (out and _quote_ok(out, doc_text)) else fragment


def _evidence(c: _Cand, stance: str, score: float, same: bool | None) -> Evidence:
    d = INDEX.docs[c.doc_idx]
    return Evidence(
        doc_id=d.id,
        title=d.title,
        publisher=d.publisher,
        domain=d.domain,
        url=d.url,
        source_type=d.source_type,
        tier=TIER[d.source_type],
        published_at=d.published_at,
        retrieved_at=d.retrieved_at,
        age_days=INDEX.doc_age(d),
        fragment=shown_fragment(c.fragment, d.text or ""),
        factcheck_claim=d.claim,
        factcheck_verdict_raw=d.verdict_raw,
        factcheck_verdict=d.verdict,
        retrieval_score=round(c.retrieval, 4),
        similarity=round(max(c.claim_cos, c.frag_cos), 3),
        stance=stance,
        stance_score=round(score, 3),
        same_claim=same,
        license=d.license,
    )


# ---- "what would settle it" (an abstention names the kind of source that would decide the claim)
# Stems are anchored at a word start: a bare "cen" matched "centrum" and "lek" matched "lekko".
_LAW = re.compile(
    r"\b(?:ustaw(?:a|y|ie|ę|ą|om|ami|ach)?|przepis\w*|rozporządz\w*|praw(?:o|a|em)|kodeks\w*|"
    r"dyrektyw\w*|unijn\w*|ue|bruksel\w*)\b"
)
_NUMBERS = re.compile(
    r"\d|%|\b(?:procent\w*|mln|mld|tys|wzro(?:st\w*|sł\w*|śnie|sną|sn\w*)|"
    r"spad(?:ek|ku|ki|kiem|ł\w*|nie|ną|a|ają)|inflacj\w*|cen(?:a|y|ie|ę|ą|om|ami|ach)?|cenow\w*|"
    r"płac(?:a|y|e|ą|ę|ami)?|wynagrodze\w*|pensj\w*|emerytur\w*|świadcze\w*|zasił\w*|"
    r"bezroboci\w*|pkb)\b"
)
_HEALTH = re.compile(
    r"\b(?:szczepi\w*|szczepion\w*|chorob\w*|lek(?:i|u|ów|iem|ami|arstw\w*|arz\w*)?|zdrow\w*|"
    r"wirus\w*|szpital\w*|epidemi\w*|pandemi\w*)\b"
)
_SECURITY = re.compile(
    r"\b(?:wojsk\w*|wojn\w*|armi\w*|nato|ukrain\w*|rosj\w*|rosyjsk\w*|granic\w*|ambasad\w*|"
    r"msz|mon|dyplomac\w*|żołnierz\w*)\b"
)


# A rule is settled by the act that makes it, which states the area (or the people and things) it covers and the date
# it enters into force. Which act depends on who could adopt it (textutil.rule_scope).
_RULE_SETTLE = {
    "eu": (
        "akt prawny UE w EUR-Lex (rozporządzenie, dyrektywa lub decyzja) — z zakresem, którego dotyczy, i datą "
        "wejścia w życie; dyrektywa wiąże obywateli dopiero przez polską ustawę (ISAP)"
    ),
    "local": (
        "uchwała rady gminy lub miasta (akt prawa miejscowego, ogłaszany w wojewódzkim dzienniku urzędowym) — "
        "z opisem obszaru, który obejmuje, i datą wejścia w życie"
    ),
    "national": (
        "ustawa lub rozporządzenie w Dzienniku Ustaw (wyszukiwarka ISAP Sejmu) — z zakresem, którego dotyczy, "
        "i datą wejścia w życie"
    ),
}


def _would_settle(claim: str) -> str:
    c = claim.lower()
    scope = rule_scope(c)
    if scope:
        return _RULE_SETTLE[scope]
    if _LAW.search(c):
        return (
            "akt prawny w ISAP (Dziennik Ustaw) lub EUR-Lex albo komunikat właściwego ministerstwa"
        )
    if _NUMBERS.search(c):
        return "aktualne dane GUS, NBP, Eurostatu lub komunikat ZUS/właściwego ministerstwa"
    if _HEALTH.search(c):
        return "komunikat Ministerstwa Zdrowia / GIS lub analiza organizacji fact-checkingowej"
    if _SECURITY.search(c):
        return "komunikat MSZ, MON lub RCB albo analiza organizacji fact-checkingowej"
    return "komunikat właściwej instytucji lub analiza organizacji fact-checkingowej (IFCN/EFCSN)"


_NUM = re.compile(r"(\d+(?:[.,]\d+)?)\s*(%|proc\w*|zł\b|złotych|zl\b|mln|mld|tys)", re.I)
_MONTHS = [
    "stycz",
    "lut",
    "marc|marz",
    "kwie",
    "maj",
    "czerw",
    "lip",
    "sierp",
    "wrze",
    "paźdz|pazdz",
    "listop",
    "grud",
]
_MONTHS_STEMS = [
    "stycz",
    "luty",
    "lute",
    "marz",
    "marc",
    "kwie",
    "maj",
    "czerw",
    "lipi",
    "sier",
    "wrze",
    "pazd",
    "listo",
    "grud",
]


def _unit(u: str) -> str:
    u = u.lower()
    return "%" if u.startswith(("%", "proc")) else "zł" if u.startswith(("zł", "zl")) else u


def _numbers(s: str) -> list[tuple[float, str]]:
    return [(float(v.replace(",", ".")), _unit(u)) for v, u in _NUM.findall(s)]


_ORDINAL = {
    "i": 1,
    "ii": 2,
    "iii": 3,
    "iv": 4,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "pierwsz": 1,
    "drug": 2,
    "trzeci": 3,
    "czwart": 4,
}
_QUARTER_RX = re.compile(
    r"\b(i{1,3}|iv|[1-4])\s*(?:kw\.|kwarta\w*)|\bq([1-4])\b|\b(pierwsz|drug|trzeci|czwart)\w*\s+kwarta\w*"
)
_HALF_RX = re.compile(
    r"\b(i{1,2}|[12])\s*półrocz\w*|\b(pierwsz|drug)\w*\s+(?:półrocz\w*|połow\w*\s+(?:roku|20\d\d))"
    r"|\b20\d\d-s([12])\b"
)


def _date_keys(s: str) -> tuple[set[str], set[int]]:
    """Years and months a text refers to. Months come from month names, YYYY-MM, MM.YYYY / MM/YYYY, quarters
    ("III kwartał", "Q3", "w trzecim kwartale") and halves ("I półrocze", "w pierwszej połowie roku", "2026-S1").
    """
    low = s.lower()
    years = {y for y in re.findall(r"\b(20\d\d)\b", low)}
    months = {i + 1 for i, m in enumerate(_MONTHS) if re.search(rf"\b({m})\w*", low)}
    months |= {int(m) for _, m in re.findall(r"\b(20\d\d)-(\d\d)\b", low)}
    months |= {int(m) for m, _ in re.findall(r"(?<![\d,])(0?[1-9]|1[0-2])[./](20\d\d)\b", low)}
    for m in _QUARTER_RX.finditer(low):
        q = _ORDINAL[next(g for g in m.groups() if g)]
        months |= {3 * q - 2, 3 * q - 1, 3 * q}
    for m in _HALF_RX.finditer(low):
        h = _ORDINAL[next(g for g in m.groups() if g)]
        months |= set(range(6 * h - 5, 6 * h + 1))
    return years, months


_MEASURES = (
    [  # (source marker, words that must appear in the claim for the comparison to be meaningful)
        (re.compile(r"\bHICP\b"), re.compile(r"hicp|eurostat|zharmonizowan", re.I)),
        (re.compile(r"\bCPI\b"), re.compile(r"\bcpi\b|gus|inflacj(?!.*hicp)", re.I)),
        (re.compile(r"\bEUR\b"), re.compile(r"euro|\beur\b", re.I)),
        (re.compile(r"\bUSD\b"), re.compile(r"dolar|\busd\b", re.I)),
        (re.compile(r"\bCHF\b"), re.compile(r"frank|\bchf\b", re.I)),
        (re.compile(r"\bGBP\b"), re.compile(r"funt|\bgbp\b", re.I)),
    ]
)


def _compatible(claim: str, source_title: str, source_text: str = "") -> bool:
    if not measures.compatible(
        claim, source_title, source_text
    ):  # claim names another definition (HICP vs CPI…)
        return False
    return all(
        rx_claim.search(claim) for rx_src, rx_claim in _MEASURES if rx_src.search(source_title)
    )


_PL_MONTHS = {
    "stycznia": 1,
    "lutego": 2,
    "marca": 3,
    "kwietnia": 4,
    "maja": 5,
    "czerwca": 6,
    "lipca": 7,
    "sierpnia": 8,
    "września": 9,
    "października": 10,
    "listopada": 11,
    "grudnia": 12,
}
_DATE_RX = re.compile(
    r"\b(\d{1,2})\s+("
    + "|".join(_PL_MONTHS)
    + r")\s+(\d{4})|\b(\d{4})-(\d{2})-(\d{2})\b|\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b",
    re.I,
)


def _dates(s: str) -> list[tuple[int, int, int]]:
    out = []
    for m in _DATE_RX.finditer(s):
        if m.group(1):
            out.append((int(m.group(3)), _PL_MONTHS[m.group(2).lower()], int(m.group(1))))
        elif m.group(4):
            out.append((int(m.group(4)), int(m.group(5)), int(m.group(6))))
        else:
            out.append((int(m.group(9)), int(m.group(8)), int(m.group(7))))
    return out


_OTHER_DOLLARS = r"(?!\s+(?:kanadyj|australij|nowozeland|hongkoń|hongkon|singapur|tajwań|tajwan))"
_CURR_NAMES = (
    {  # currency names in any inflected form; the crowns and the dollars only with their country
        "EUR": r"\beuro\b|\beur\b",
        "USD": rf"\bdolar\w*\b{_OTHER_DOLLARS}",
        "CHF": r"\bfrank(?:a|i|ów|ow|om|ami|ach|iem)?\b",
        "GBP": r"\bfunt\w*\b",
        "NOK": r"\bkoron\w*\s+norwe",
        "SEK": r"\bkoron\w*\s+szwedz",
        "DKK": r"\bkoron\w*\s+du[nń]s",
        "CZK": r"\bkoron\w*\s+czes",
        "JPY": r"\bjen(?:a|y|ów|ow|om|ami|ach|ie)?\b",
        "HUF": r"\bforint\w*",
        "UAH": r"\bhrywn\w*",
        "CNY": r"\bjuan\w*|\byuan\w*|\brenminbi",
        "CAD": r"\bdolar\w*\s+kanadyj",
        "AUD": r"\bdolar\w*\s+australij",
    }
)


def _names_currency(claim: str, code: str) -> bool:
    return bool(
        re.search(rf"\b{code}\b", claim, re.I)
        or (code in _CURR_NAMES and re.search(_CURR_NAMES[code], claim, re.I))
    )


# the same indicator or subject named differently in a claim and in an official card's title: synonyms, abbreviations
# and inflected forms (general Polish vocabulary of statistics and law). Both texts are rewritten to one word per
# subject before the subject gate compares stems ("płaca minimalna" ~ "minimalne wynagrodzenie", "zmarło" ~ "zgonów").
_SUBJECT_SYNONYMS = [
    (re.compile(rf"\b(?:{p})\b", re.I), w)
    for p, w in (
        (r"produkt\w* krajow\w* brutto", "PKB"),
        (
            r"wynagrodze\w*|płac(?:a|y|ę|e|om|ach|ami)|plac[ay]|pensj\w*|zarobk\w*|zarabia\w*|zarobi\w*",
            "wynagrodzenie",
        ),
        (
            r"zgon\w*|zmar[łl]\w*|umar[łl]\w*|umiera\w*|śmier[cć]\w*|smierc\w*|śmiertelnoś\w*|smiertelnos\w*",
            "zgon",
        ),
        (r"urodze\w*|urodzi\w*|narodzin\w*", "urodzenie"),
        (r"ludnoś\w*|ludnos\w*|mieszkańc\w*|mieszkanc\w*|populacj\w*", "ludność"),
        (r"inflacj\w*|inflacyjn\w*|drożyzn\w*|drozyzn\w*", "inflacja"),
        (r"bezroboci\w*|bezrobotn\w*", "bezrobocie"),
        (
            r"zadłużeni\w*|zadluzeni\w*|zadłużon\w*|zadluzon\w*|dług(?:u|iem|i|ów|ow|om|ach|ami)?|dlug(?:u|iem|i|ow|om|ach|ami)?",
            "dług",
        ),
        (r"emerytur\w*|emeryt(?:a|ów|ow|om|ami|ach|y|ka|ki)?", "emerytura"),
        (r"azyl\w*|ochron\w* międzynarodow\w*", "azyl"),
        (r"prąd\w*|prad(?:u|em)?|energi\w* elektryczn\w*", "prąd"),
    )
]


def _subject_text(s: str) -> str:
    for rx, word in _SUBJECT_SYNONYMS:
        s = rx.sub(word, s)
    return s


_ACT = re.compile(r"^(Ustawa|Rozporządzenie|Dyrektywa|Decyzja|Konstytucja|Uchwała)\b", re.I)


def _other_definition(claim: str, d) -> str:
    """After a numeric mismatch with official card `d`: could the claim be using another definition of the same
    indicator (CPI vs HICP, registered vs LFS unemployment, real vs nominal GDP — see measures.py)?
    Returns "" when the mismatch stands: the claim names the card's definition, or for every other definition a card
    for the same period is indexed and none of them gives the claimed number. Otherwise returns the note saying why
    the card does not decide the claim (another definition gives the claimed number, or no card for it is indexed).
    """
    open_dims = measures.unnamed(claim, d.title, d.text)
    if not open_dims:
        return ""
    m = measures.measure_of(d.title, d.text)
    missing: list[str] = []
    for dim, own in open_dims:
        for alt in dim.variants:
            if alt.name == own.name:
                continue
            cards = [
                o
                for o in INDEX.docs
                if o.source_type == "official"
                and o is not d
                and measures.uses(o.title, o.text, m.key, dim.key) == alt.name
                and measures.compatible(claim, o.title, o.text)
                and same_subject(claim, o.title)
            ]
            agree = next(
                (
                    o
                    for o in cards
                    if numeric_stance(claim, f"{o.title}. {o.text[:6000]}") == "zgodne"
                ),
                None,
            )
            if agree is not None:
                return (
                    f"Wartość zależy od przyjętej miary: {agree.publisher} („{short(agree.title, 80)}”) podaje tę "
                    f"liczbę według definicji {alt.name}, a {d.publisher} („{short(d.title, 80)}”) inną według "
                    f"definicji {own.name}. Twierdzenie nie mówi, o którą miarę chodzi."
                )
            if not cards:
                missing.append(alt.name)
    if missing:
        return (
            f"Wartość zależy od przyjętej miary: {d.publisher} („{short(d.title, 80)}”) podaje inną liczbę według "
            f"definicji {open_dims[0][1].name}; dla innej definicji ({', '.join(missing)}) nie mam danych za ten "
            "okres, a twierdzenie nie mówi, o którą miarę chodzi."
        )
    return ""


_ALTERNATIONS = (("sz", "ch"), ("cz", "c"), ("rz", "r"))


def _alt_stems(toks) -> set[str]:
    """Polish inflection changes stem consonants (Włochy → we Włoszech, Niemcy → w Niemczech, Węgry → na Węgrzech),
    so prefix stems alone miss the match. Undo the common alternations, then compare 4-character prefixes.
    Numbers are kept whole."""
    out = set()
    for t in toks:
        if t[:1].isdigit():
            out.add(t)
            continue
        for a, b in _ALTERNATIONS:
            t = t.replace(a, b)
        out.add(t[:4])
    return out


def same_subject(claim: str, title: str) -> bool:
    """Gate for structured official cards: a card about another period, currency or legal act is IRRELEVANT
    to the claim (not contradicting it)."""
    if _ACT.search(title):
        subj_years = set(
            re.findall(r"\bw\s+((?:19|20)\d\d)\s*r", title)
        )  # "…stawki godzinowej w 2027 r."
        claim_years = set(re.findall(r"\b((?:19|20)\d\d)\b", claim))
        if subj_years and claim_years and not (subj_years & claim_years):
            return False  # the act regulates another year
        nums = re.findall(r"\b(\d{4}/\d{1,5})\b", claim)
        if nums:
            return any(n in title for n in nums)
        m = re.search(r"\b(?:o|w sprawie)\s+(.+)$", title)
        subject = set(tokens(_subject_text(m.group(1) if m else title), stem=5))
        return (
            len(subject & set(tokens(_subject_text(claim), stem=5))) / max(1, len(subject)) >= 0.4
        )
    head = re.split(r"[:—–]\s*\d", title)[
        0
    ]  # e.g. "Ceny — transport — wrzesień 2026" / "Inflacja CPI w Polsce — marzec 2026"
    subj = _anchors(_subject_text(re.sub(r"\b(19|20)\d\d(-\d\d)?(-\d\d)?\b", " ", head))) - {
        t for t in tokens(" ".join(_PL_MONTHS))
    }
    subj = {t for t in subj if not any(t.startswith(m[:4]) for m in _MONTHS_STEMS)}
    if (
        subj
        and not (_alt_stems(subj) & _alt_stems(tokens(_subject_text(claim))))
        and not re.search(r"\b[A-Z]{3}/PLN\b", title)
    ):
        return False  # the card is about another indicator (e.g. transport prices vs. headline inflation)
    cur = re.search(r"\b([A-Z]{3})/PLN\b", title)
    if cur and not _names_currency(claim, cur.group(1)):
        return False
    cy, cm = _date_keys(claim)
    ty, tm = _date_keys(title)
    if cy and ty and not (cy & ty):
        return False
    if cm and tm and not (cm & tm):
        return False
    return True


def legal_date_stance(claim: str, title: str, text: str) -> str | None:
    """Structured check for legal acts (ELI / EUR-Lex cards): entry-into-force and adoption dates."""
    cd = _dates(claim)
    if not cd:
        return None
    explicit = re.search(r"wesz\w* w życie|wchodzi w życie|wejdzie w życie", claim, re.I)
    # "od <data>" / "obowiązuje od" may mean "applies from" (≠ entry into force) — only for claims about the law itself
    about_law = re.search(r"ustaw\w*|rozporządz\w*|przepis\w*|kodeks\w*|obowiązuje od", claim, re.I)
    if explicit or (
        about_law and re.search(r"^\s*od\s+\d{1,2}\s+\w+\s+\d{4}|obowiązuje od", claim, re.I)
    ):
        m = re.search(r"wejście w życie:\s*(\d{4}-\d{2}-\d{2})", text)
        if m:
            return "zgodne" if _dates(m.group(1))[0] in cd else "niezgodne"
    if re.search(r"przyję\w*|przyjęt\w*|uchwal\w*|z dnia|podpisan\w*|wydan\w*", claim, re.I):
        m = re.search(r"z dnia\s+(\d{1,2}\s+\w+\s+\d{4})", title)
        if m and _dates(m.group(1)):
            return "zgodne" if _dates(m.group(1))[0] in cd else "niezgodne"
    return None


_GENERIC = set(
    tokens(
        "polsce polska polski gus nbp eurostat kurs średni dane wskaźnik według wyniósł wyniosła wynosi "
        "procent proc r/r rok roku miesiąc ceny obwieszczenie państwowej komisji wyborczej dnia"
    )
)


def _anchors(claim: str) -> set[str]:
    return {t for t in tokens(claim) if not t[0].isdigit() and t not in _GENERIC and len(t) > 2}


_WORD = re.compile(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+")


def _bound_values(keys: set[str], source: str, unit: str) -> list[float]:
    """Numbers (in `unit`) that directly follow the MOST SPECIFIC of `keys` in the source — key->value binding,
    e.g. 'stopa referencyjna: 3,75%', so a value printed elsewhere on the card (lombard 4,25%) cannot match.
    """
    from .textutil import strip_pl

    occ: dict[str, list[int]] = {}
    for m in _WORD.finditer(source):
        st = strip_pl(m.group(0))[:6]
        if st in keys:
            occ.setdefault(st, []).append(m.end())
    nums = [
        (m.start(), float(m.group(1).replace(",", ".")), _unit(m.group(2)))
        for m in _NUM.finditer(source)
    ]
    bound: dict[str, list[float]] = {}
    for k, ends in occ.items():
        for e in ends:
            nxt = next((v for p, v, u in nums if e <= p <= e + 90 and u == unit), None)
            if nxt is not None:
                bound.setdefault(k, []).append(nxt)
    if not bound:
        return []
    rarest = min(len(occ[k]) for k in bound)
    return [v for k in bound if len(occ[k]) == rarest for v in bound[k]]


def numeric_stance(claim: str, source: str) -> str | None:
    """Deterministic check of numbers in a claim against an official card/act for the SAME period.
    Each claimed number is paired with the words preceding it in the claim (its key) and compared only with numbers
    bound to the same key in the source. Every checkable number must agree."""
    cy, cm = _date_keys(claim)
    sy, sm = _date_keys(source)
    if not cy or not cy <= sy or (cm and not cm <= sm):
        return None
    sn = _numbers(source)
    verdicts, prev = [], 0
    for m in _NUM.finditer(claim):
        v, u = float(m.group(1).replace(",", ".")), _unit(m.group(2))
        keys = _anchors(claim[prev : m.start()]) or _anchors(claim)
        prev = m.end()
        cands = _bound_values(keys, source, u)
        if not cands and len(source) < 700:  # short single-value fact card: any same-unit value
            cands = [x for x, su in sn if su == u]
        if not cands:
            continue
        window = claim[max(0, m.start() - 40) : m.start()]
        op = (
            ">"
            if re.search(r"przekrocz\w*|ponad|powyżej|więcej niż|wyższ\w* niż", window, re.I)
            else (
                "<"
                if re.search(r"poniżej|mniej niż|niższ\w* niż|nie przekrocz\w*", window, re.I)
                else "="
            )
        )
        if op == "=":
            ok = any(abs(x - v) <= max(0.051, abs(v) * 0.005) for x in cands)
        else:
            ok = cands[0] > v if op == ">" else cands[0] < v
        verdicts.append(ok)
    if not verdicts:
        return None
    return "zgodne" if all(verdicts) else "niezgodne"


def claim_match(
    cos: float, fwd, rev, checked_claim: str, user_text: str, source_type: str
) -> tuple[bool | None, str | None]:
    """(decision, guard note). Decision: True = the user asserts the checked claim; False = the user asserts its
    opposite; None = only related (context, never a verdict or a flag).

    Guard G1 (names and numbers): very high similarity alone (`cos >= 0.88`) is accepted as "the same claim" only
    while the two texts do not disagree on a name or a number (agreement.disagreement). If they do, the pair has to
    qualify through one of the routes backed by NLI entailment; when it does not, the decision is None and the note
    says what differed (it goes to the audit trail). The guard never rejects a pair that entailment supports. It
    is not applied to the negation rule, which already requires NLI contradiction in both directions: the guard
    exists to demand NLI support where similarity is the only evidence."""
    incident = source_type == "incident"  # long, multi-part (often English) narratives -> stricter
    lex = _relevance(set(tokens(checked_claim)), user_text)
    if cos >= 0.85 and min(fwd.contra, rev.contra) >= 0.80:
        return False, None
    if max(fwd.contra, rev.contra) < 0.5:
        if (cos >= 0.86 and fwd.entail >= (0.8 if incident else 0.5)) or (
            not incident and cos >= 0.80 and fwd.entail >= 0.8 and lex >= 0.4
        ):
            return True, None
        if cos >= 0.88 and not incident:  # similarity alone
            try:
                note = disagreement(user_text, checked_claim)
            except (
                Exception
            ):  # noqa: BLE001 — a failing text heuristic must not fail the check; keep the old behaviour
                log.exception("agreement guard failed")
                note = None
            return (None, note) if note else (True, None)
    return None, None


def same_claim(
    cos: float, fwd, rev, checked_claim: str, user_text: str, source_type: str
) -> bool | None:
    """Single decision used by BOTH the full analysis and the browser extension, so the extension never flags
    content that the full analysis would not match. See claim_match."""
    return claim_match(cos, fwd, rev, checked_claim, user_text, source_type)[0]


# ------------------------------------------------------------------ sentence units of a checked claim
# A fact-checked statement is often a quote of several sentences ("X została usunięta. Tusk wszedł w buty …"), and a
# user repeats only the one that was rated. Matched as a whole, the other sentences add content the user never stated
# and can make NLI read a contradiction (e.g. a year in the second sentence). A single sentence, however, inherits
# the rating only when it is the part the fact-checker ruled on: its own headline must deny it (rating "false") or
# state it (rating "true"). Mixed / misleading ratings are about the combination and never transfer to one sentence.
UNIT_RATINGS = {"false": "contra", "true": "entail"}
UNIT_MIN_COS = 0.80
UNIT_HEADLINE_NLI = 0.80


def claim_units(claim: str) -> list[str]:
    """Declarative sentences of a checked claim with at least four content words (rhetorical questions and
    exclamations like 'W jakim kraju my żyjemy?!' are not units). Fewer than two -> no units."""
    units = [s for s in split_sentences(claim) if len(tokens(s)) >= 4 and "?" not in s[-3:]]
    return units if len(units) >= 2 else []


def headline_statement(title: str) -> str:
    """The declarative part of a fact-check headline: question segments ('Darmowa komunikacja tylko we Wrocławiu?')
    and one-word tags ('Sprawdzamy') are dropped. Empty if nothing declarative remains."""
    keep = [
        s
        for s in split_sentences(title or "")
        if not s.rstrip().endswith("?") and len(tokens(s)) >= 3
    ]
    return " ".join(keep)


def _claim_units(ranked: list[_Cand], q_emb: np.ndarray) -> None:
    """Best sentence unit (by cosine) for every candidate fact-check that can inherit its rating per sentence."""
    todo = []
    for c in ranked:
        d = INDEX.docs[c.doc_idx]
        if not (
            c.is_claim_match
            and d.claim
            and d.source_type == "factcheck"
            and d.verdict in UNIT_RATINGS
            and headline_statement(d.title)
        ):
            continue
        units = claim_units(d.claim)
        if units:
            todo.append((c, units))
    if not todo:
        return
    embs = INDEX.encode_query([u for _, units in todo for u in units])
    pos = 0
    for c, units in todo:
        sims = embs[pos : pos + len(units)] @ q_emb
        pos += len(units)
        j = int(np.argmax(sims))
        c.unit, c.unit_cos = units[j], float(sims[j])


def unit_match(c: _Cand, d, user_text: str) -> bool | None:
    """Decision of the sentence route (see claim_units): None unless the fact-checker's headline rules on the unit."""
    if not c.unit or c.nli_unit is None or c.nli_head_unit is None:
        return None
    if getattr(c.nli_head_unit, UNIT_RATINGS[d.verdict]) < UNIT_HEADLINE_NLI:
        return None
    return same_claim(
        c.unit_cos, c.nli_unit, c.nli_unit_rev or c.nli_unit, c.unit, user_text, d.source_type
    )


# ------------------------------------------------------------------ consistency of fact-check matches
# Each fact-check is matched to the user's text on its own (claim_match), so two analyses of ONE narrative can be read
# with opposite polarity: one as "the user repeats it" (similarity alone), the other as "the user denies it" (NLI
# contradiction both ways). Both are rated the same, so they then imply opposite verdicts and R2 reports a conflict that
# no source holds. Analyses of one publisher, and analyses of the same checked claim, are therefore reconciled before
# R1–R6: the match best backed by NLI decides; a weaker match that implies the opposite verdict from the same rating,
# and a weaker same-publisher match that implies the same verdict (a duplicate), become context. Different ratings are
# never reconciled (a true and a false rating are a real conflict), and agreeing analyses of different publishers stay
# separate (independent confirmations).
_NEGATION = re.compile(r"\b(nie|nigdy|żadn\w*|zadn\w*|bez)\b", re.I)


def has_own_text(d) -> bool:
    """Does the record carry text of its own beyond its headline and the checked claim? A ClaimReview metadata entry
    (rating, claim, headline, link; its text is the headline and the claim joined) does not: there is no passage of
    the analysis to quote as the finding, and the organisers' rule is that every verdict rests on a source quoted
    verbatim. The headline and the claim are removed as whole passages, not word by word: a sentence of the article
    that restates the finding in the headline's words ("Polecenie … jest prawdziwe") is the publisher's text and
    counts as its own (the stored excerpt of a source kept as facts + one excerpt is often exactly that sentence).
    """
    rest = normalize_ws(d.text or "").lower()
    for part in sorted(
        {normalize_ws(d.title or "").lower(), normalize_ws(d.claim or "").lower()},
        key=len,
        reverse=True,
    ):
        if part:
            rest = rest.replace(part, " ")
    return bool(tokens(rest))


def match_support(c: _Cand) -> tuple[int, float]:
    """How well a fact-check match is backed: the number of NLI directions (user -> checked claim, checked claim ->
    user) that state its polarity — entailment for "same", contradiction for "opposite" (a direction not computed
    counts as not stating it) — then the similarity."""
    fwd, rev = (c.nli_unit, c.nli_unit_rev) if c.via_unit else (c.nli_claim, c.nli_claim_rev)
    key = "entail" if c.same else "contra"
    return sum(1 for s in (fwd, rev) if s is not None and getattr(s, key) >= 0.5), c.claim_cos


def same_checked_claim(a: str, b: str) -> bool:
    """One checked claim restates the other: the content words of one contain the other's (a time or place
    qualifier added, "Od 2025 roku X" / "X"), and both or neither are negated."""
    ta, tb = set(tokens(a)), set(tokens(b))
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return (
        len(small) >= 3 and small <= big and bool(_NEGATION.search(a)) == bool(_NEGATION.search(b))
    )


def consistent_matches(
    support: list, refute: list, misleading: list, evidence: list[Evidence]
) -> list[str]:
    """Reconcile the fact-check matches (see above) in place; returns audit notes for the polarity conflicts it
    resolved (duplicates are collapsed silently)."""
    buckets = {"falszywe": refute, "potwierdzone": support, "wprowadzajace_w_blad": misleading}
    matched = [
        c for b in buckets.values() for c in b if c.same is not None and c.implied in buckets
    ]
    kept: list[_Cand] = []
    notes: list[str] = []
    for c in sorted(matched, key=match_support, reverse=True):
        d = INDEX.docs[c.doc_idx]
        drop = None
        for k in kept:
            dk = INDEX.docs[k.doc_idx]
            same_pub = dk.publisher == d.publisher
            if not (same_pub or same_checked_claim(dk.claim or "", d.claim or "")):
                continue
            if {k.implied, c.implied} == {"falszywe", "potwierdzone"} and dk.verdict == d.verdict:
                drop = k
                notes.append(
                    f"Analizy „{short(dk.claim or dk.title, 90)}” i „{short(d.claim or d.title, 90)}” "
                    f"({d.publisher}) mają tę samą ocenę, a dopasowania wskazywały przeciwne wnioski; przyjęto "
                    "dopasowanie lepiej potwierdzone przez model NLI (pierwsze), drugie pokazano jako kontekst."
                )
                break
            if same_pub and k.implied == c.implied:
                drop = k
                break
        if drop is None:
            kept.append(c)
            continue
        buckets[c.implied].remove(c)
        for e in evidence:
            if e.doc_id == d.id and e.stance in ("przeczy", "popiera"):
                e.stance = "kontekst"
    return notes


# ======================================================================================================== main
def _retrieve_candidates(claim: Claim, timings: dict[str, float]) -> tuple[np.ndarray, list[_Cand]]:
    """Merge checked-claim matches with hybrid passage search, preserving the current ranking."""
    # ---- retrieval
    stage_started_at = time.perf_counter()
    query_embedding = INDEX.encode_query([claim.query])[0]
    candidates_by_document: dict[int, _Cand] = {}
    for doc_idx, cos in INDEX.match_claims(query_embedding, claim.query, k=8):
        if cos >= settings.claim_match_soft - 0.06:
            # cos: closest row (checked claim or headline) — finds and ranks the analysis; claim_cos: the checked
            # claim itself — what claim matching rules on (a headline may state the correction, not the claim)
            checked_claim_similarity = INDEX.checked_claim_cos(doc_idx, query_embedding)
            candidates_by_document[doc_idx] = _Cand(
                doc_idx, "", cos, cos, is_claim_match=True, claim_cos=checked_claim_similarity
            )
    for chunk_idx, fused, cos in INDEX.search_chunks(
        claim.query, query_embedding, k=settings.top_k_retrieval
    ):
        ch = INDEX.chunks[chunk_idx]
        if cos < 0.55:  # dense-similarity floor: below it the passage is off-topic
            continue
        candidate = candidates_by_document.setdefault(
            ch.doc_idx, _Cand(ch.doc_idx, ch.text, fused, cos)
        )
        if cos >= candidate.cos or not candidate.chunk_text:
            candidate.chunk_text, candidate.cos, candidate.retrieval = (
                ch.text,
                max(candidate.cos, cos),
                max(candidate.retrieval, fused),
            )
    candidates = sorted(
        candidates_by_document.values(),
        key=lambda candidate: -max(candidate.claim_cos, candidate.cos),
    )[: settings.top_k_evidence + 2]
    timings["retrieval_ms"] = (
        timings.get("retrieval_ms", 0) + (time.perf_counter() - stage_started_at) * 1000
    )

    return query_embedding, candidates


def _select_candidate_fragments(
    claim: Claim, ranked: list[_Cand], q_emb: np.ndarray, timings: dict[str, float]
) -> set[str]:
    """Choose literal excerpts, including asked numbers and the original year of old material."""
    # ---- fragments (verbatim) + stance (NLI on exactly the quoted fragment)
    stage_started_at = time.perf_counter()
    query_tokens = set(tokens(claim.query))
    for candidate in ranked:
        candidate.fragment, candidate.frag_cos, candidate.alternatives = _best_fragment(
            candidate.doc_idx, q_emb, query_tokens, claim.query
        )
    # "Czy X kosztuje 40 mln zł? Skąd w analizie 36 mln zł?": an analysis of a statement that gave the user's
    # number quotes the passage with the asked number instead (the answer layer explains the two figures)
    stated = amounts(claim.query)
    asked = [
        a for a in amounts(getattr(claim, "meta", "")) if not any(same_amount(a, x) for x in stated)
    ]
    for candidate in ranked if asked and stated else []:
        document = INDEX.docs[candidate.doc_idx]
        if (
            document.source_type == "factcheck"
            and document.claim
            and any(same_amount(x, y) for x in stated for y in amounts(document.claim))
        ):
            fragment = asked_number_fragment(document.text or "", document.claim, asked)
            if fragment:
                candidate.fragment, candidate.explains = fragment, True
    for candidate in ranked:  # rule R3a: old material presented as current
        document = INDEX.docs[candidate.doc_idx]
        if document.source_type == "factcheck" and (
            year := presented_year(claim.query, document.published_at)
        ):
            hit = archival_origin(document, claim.query, year)
            if hit:
                candidate.fragment, candidate.archival = hit[0], (hit[1], year)
    _claim_units(ranked, q_emb)
    timings["fragments_ms"] = (
        timings.get("fragments_ms", 0) + (time.perf_counter() - stage_started_at) * 1000
    )
    return query_tokens


def _score_candidate_stances(
    claim: Claim, ranked: list[_Cand], q_tokens: set[str], timings: dict[str, float]
) -> None:
    """Score the exact excerpts with NLI, then apply structured number and date comparisons."""
    stage_started_at = time.perf_counter()
    pairs, owners = [], []
    for candidate in ranked:
        document = INDEX.docs[candidate.doc_idx]
        if candidate.is_claim_match and document.claim and candidate.claim_cos >= 0.78:
            pairs.append((claim.query, document.claim))
            owners.append((candidate, "claim"))
            if candidate.claim_cos >= 0.85:  # reverse direction only needed for the negation test
                pairs.append((document.claim, claim.query))
                owners.append((candidate, "claim_rev"))
        if candidate.unit and candidate.unit_cos >= UNIT_MIN_COS:  # sentence route (claim_units)
            pairs.append((claim.query, candidate.unit))
            owners.append((candidate, "unit"))
            if candidate.unit_cos >= 0.85:
                pairs.append((candidate.unit, claim.query))
                owners.append((candidate, "unit_rev"))
            pairs.append((headline_statement(document.title), candidate.unit))
            owners.append((candidate, "head_unit"))
        if document.source_type == "official" and not same_subject(claim.query, document.title):
            candidate.extra_irrelevant = (
                True  # another period/currency/act — not evidence either way
            )
            continue
        if (
            document.source_type in ("official", "media")
            and _relevance(q_tokens, f"{document.title} {candidate.fragment}") >= 0.4
        ):
            pairs.append((candidate.fragment, claim.query))
            owners.append((candidate, "frag"))
    for (candidate, kind), stance in zip(owners, NLI_MODEL.score(pairs)):
        setattr(
            candidate,
            {
                "claim": "nli_claim",
                "claim_rev": "nli_claim_rev",
                "frag": "nli",
                "unit": "nli_unit",
                "unit_rev": "nli_unit_rev",
                "head_unit": "nli_head_unit",
            }[kind],
            stance,
        )
    # deterministic checks override NLI for structured official cards (NLI is weak at numbers and dates)
    for candidate in ranked:
        document = INDEX.docs[candidate.doc_idx]
        if (
            document.source_type != "official"
            or max(candidate.frag_cos, candidate.cos) < 0.65
            or candidate.extra_irrelevant
        ):
            continue
        numeric_result = None
        if _compatible(claim.query, document.title, document.text):
            numeric_result = numeric_stance(
                claim.query, f"{document.title}. {document.text[:6000]}"
            )
            if numeric_result == "niezgodne":
                candidate.definitional = _other_definition(claim.query, document)
                if (
                    candidate.definitional
                ):  # e.g. CPI vs HICP: the claim may use the other measure — not a contradiction
                    numeric_result = None
        numeric_result = numeric_result or legal_date_stance(
            claim.query, document.title, document.text
        )
        if numeric_result:
            candidate.numeric = numeric_result
            candidate.nli = (
                NLIScore(0.95, 0.03, 0.02)
                if numeric_result == "zgodne"
                else NLIScore(0.02, 0.03, 0.95)
            )
    timings["nli_ms"] = timings.get("nli_ms", 0) + (time.perf_counter() - stage_started_at) * 1000


def verify_claim(claim: Claim, timings: dict[str, float]) -> ClaimResult:
    """Verify one claim: retrieve, quote, score, group evidence, then apply ordered rules.

    This function owns the rule sequence. Retrieval and NLI helpers only prepare
    candidates; they do not publish a verdict. Existing rule IDs are audit contracts.
    """
    high_risk = bool(HIGH_RISK.search(claim.text))
    # ---- R1: opinions / predictions are not verifiable
    if claim.kind in ("opinia", "prognoza"):
        what = (
            "opinię lub ocenę" if claim.kind == "opinia" else "przewidywanie dotyczące przyszłości"
        )
        return ClaimResult(
            claim=claim.text,
            kind=claim.kind,
            verdict="nie_podlega_weryfikacji",
            verdict_label=VERDICT_LABEL_PL["nie_podlega_weryfikacji"],
            strength=0.0,
            strength_label="nie dotyczy",
            premises=[
                Premise(label="Rodzaj wypowiedzi", value=f"wypowiedź zawiera {what}", effect="0")
            ],
            rules_fired=["R1:NIE_PODLEGA_WERYFIKACJI"],
            high_risk=high_risk,
            explanation=(
                f"To {what} — nie da się jej potwierdzić ani obalić faktami. Możemy sprawdzić konkretne fakty, "
                "na których się opiera: wpisz je osobno (np. liczby, daty, decyzje)."
            ),
            limitations=["Rozpoznanie opinii opiera się na sygnałach językowych i może się mylić."],
        )

    query_embedding, candidates = _retrieve_candidates(claim, timings)
    query_tokens = _select_candidate_fragments(claim, candidates, query_embedding, timings)
    _score_candidate_stances(claim, candidates, query_tokens, timings)

    # Evidence validity gates and stance classification retain their original order.
    support, refute, misleading, unverifiable, evidence, definitional = [], [], [], [], [], []
    guarded: list[tuple[object, str]] = (
        []
    )  # G1: very similar checked claims not accepted, with what differed
    by_unit: list[tuple[object, str]] = (
        []
    )  # matched through one sentence of the checked claim (claim_units)
    metadata_only: list[str] = (
        []
    )  # V3: matched records with no text of their own (see has_own_text)
    for candidate in candidates:
        document = INDEX.docs[candidate.doc_idx]
        if candidate.extra_irrelevant:
            continue
        if document.source_type in ("factcheck", "incident"):
            claim_stance, same, differs = candidate.nli_claim, None, None
            if candidate.is_claim_match and claim_stance is not None:
                same, differs = claim_match(
                    candidate.claim_cos,
                    claim_stance,
                    candidate.nli_claim_rev or claim_stance,
                    document.claim or "",
                    claim.query,
                    document.source_type,
                )
            if same is None and candidate.is_claim_match:
                same = unit_match(candidate, document, claim.query)
                if same is not None:
                    differs = None  # the whole quote differed, the sentence the fact-checker ruled on does not
                    candidate.claim_cos = max(candidate.claim_cos, candidate.unit_cos)
                    candidate.via_unit = True
                    by_unit.append((document, candidate.unit))
            if differs:
                guarded.append((document, differs))
            mapped = FC_TO_VERDICT.get(document.verdict or "") if same is not None else None
            if mapped and same is False:
                mapped = {"falszywe": "potwierdzone", "potwierdzone": "falszywe"}.get(mapped)
            candidate.same, candidate.implied = same, mapped
            if mapped in ("falszywe", "potwierdzone", "wprowadzajace_w_blad") and not has_own_text(
                document
            ):
                # V3: no passage of its own carries the finding (a ClaimReview metadata entry: headline + checked
                # claim only), so the record is listed as related and never decides
                metadata_only.append(document.id)
                evidence.append(_evidence(candidate, "kontekst", candidate.claim_cos, same))
                continue
            if (
                mapped is None and same is None and candidate.archival
            ):  # R3a: the analysis dates the material earlier
                refute.append(candidate)
                evidence.append(
                    _evidence(candidate, "przeczy", max(candidate.claim_cos, candidate.cos), None)
                )
                continue
            if mapped == "falszywe":
                refute.append(candidate)
                evidence.append(_evidence(candidate, "przeczy", candidate.claim_cos, same))
                continue
            if mapped == "potwierdzone":
                support.append(candidate)
                evidence.append(_evidence(candidate, "popiera", candidate.claim_cos, same))
                continue
            if mapped == "wprowadzajace_w_blad":
                misleading.append(candidate)
                evidence.append(_evidence(candidate, "kontekst", candidate.claim_cos, same))
                continue
            if mapped == "brak_dowodow":
                unverifiable.append(candidate)
            if max(candidate.claim_cos, candidate.frag_cos) >= 0.70 or candidate.explains:
                evidence.append(
                    _evidence(
                        candidate, "kontekst", max(candidate.claim_cos, candidate.frag_cos), same
                    )
                )
        elif candidate.definitional:
            evidence.append(_evidence(candidate, "kontekst", candidate.frag_cos, None))
            definitional.append(candidate)
        elif candidate.nli is not None:
            stance = candidate.nli
            if not candidate.numeric and not grounding.comparable_scope(
                claim.query, candidate.fragment
            ):
                evidence.append(_evidence(candidate, "kontekst", candidate.frag_cos, None))
                continue
            strong_topic = candidate.numeric is not None or candidate.frag_cos >= 0.72
            if (
                stance.entail >= settings.nli_strong
                and stance.entail > stance.contra
                and strong_topic
                and (
                    candidate.numeric
                    or grounding.numeric_support_complete(claim.query, candidate.fragment)
                )
            ):
                support.append(candidate)
                evidence.append(_evidence(candidate, "popiera", stance.entail, None))
            elif (
                stance.contra >= settings.nli_strong
                and stance.contra > stance.entail
                and strong_topic
                and (
                    candidate.numeric
                    or grounding.has_numeric_comparison(claim.query, candidate.fragment)
                )
                and (
                    candidate.numeric
                    or _relevance(query_tokens, f"{document.title} {candidate.fragment}") >= 0.5
                )
            ):
                refute.append(candidate)
                evidence.append(_evidence(candidate, "przeczy", stance.contra, None))
            elif candidate.frag_cos >= 0.72:
                evidence.append(_evidence(candidate, "kontekst", candidate.frag_cos, None))
    resolved = consistent_matches(support, refute, misleading, evidence)
    # a match on the OPPOSITE claim (same=False): the quote was chosen before matching, with the analysis' verdict
    # words ("to nieprawda") counted as a finding; they are about the claim the user denies, so choose again without
    for candidate in candidates:
        document = INDEX.docs[candidate.doc_idx]
        if (
            candidate.same is not False
            or document.source_type not in ("factcheck", "incident")
            or candidate.archival
            or candidate.explains
        ):
            continue
        fragment, _, alternatives = _best_fragment(
            candidate.doc_idx, query_embedding, query_tokens, claim.query, opposite=True
        )
        if fragment != candidate.fragment and _quote_ok(fragment, document.text or ""):
            candidate.fragment, candidate.alternatives = fragment, alternatives
            for e in evidence:
                if e.doc_id == document.id:
                    e.fragment = fragment
    # Claim matching identifies the publication, but only a verified displayed
    # finding may decide the user's claim (V5). Rejected items remain context.
    stage_started_at = time.perf_counter()
    ungrounded = _ground_factchecks(claim, support, refute, misleading, evidence)
    timings["nli_ms"] = timings.get("nli_ms", 0) + (time.perf_counter() - stage_started_at) * 1000
    result = _decide(
        claim,
        support,
        refute,
        misleading,
        unverifiable,
        evidence,
        high_risk,
        keep={INDEX.docs[candidate.doc_idx].id for candidate in candidates if candidate.explains},
    )
    if ungrounded:
        result.rules_fired.append("V5:CYTAT_NIE_UZASADNIA_TEZY")
        if result.verdict == "brak_dowodow":
            result.reason_codes.append("BRAK_UZASADNIAJACEGO_CYTATU")
            result.what_unknown = (
                "Znaleziono podobne analizy, ale dostępne fragmenty nie uzasadniają "
                "rozstrzygnięcia całej tezy w podanym zakresie."
            )
    result.meta_question = getattr(claim, "meta", "") or None
    if metadata_only:
        result.rules_fired.append("V3:TYLKO_METADANE")
    if resolved:
        result.rules_fired.append("P1:SPOJNE_DOPASOWANIA")
        result.premises.append(
            Premise(
                label="Spójność dopasowań do analiz tego samego twierdzenia lub wydawcy",
                value=" ".join(resolved),
                effect="0",
            )
        )
    if definitional:
        note = definitional[0].definitional
        result.premises.append(Premise(label="Różne definicje wskaźnika", value=note, effect="-"))
        if result.verdict == "potwierdzone":
            result.missing_context = note
        elif result.verdict == "brak_dowodow":
            result.reason_codes.append("ROZNE_DEFINICJE")
            result.what_unknown = note
    if by_unit and result.verdict in (
        "falszywe",
        "potwierdzone",
    ):  # audit trail of the sentence route (claim_units)
        document, unit = by_unit[0]
        result.rules_fired.append("M1:ZDANIE_SPRAWDZONEJ_WYPOWIEDZI")
        result.premises.insert(
            0,
            Premise(
                label="Dopasowanie do jednego zdania sprawdzonej wypowiedzi",
                value=(
                    f"Twoje zdanie odpowiada zdaniu „{short(unit, 140)}” z wypowiedzi sprawdzonej przez {document.publisher}; "
                    f"nagłówek analizy („{short(headline_statement(document.title), 100)}”) "
                    f"{'zaprzecza' if document.verdict == 'false' else 'potwierdza'} właśnie temu zdaniu."
                ),
                effect="+",
            ),
        )
    if (
        guarded
    ):  # audit trail: similarity alone would have matched these; the names or numbers differ
        result.rules_fired.append("G1:ROZNE_NAZWY_LUB_LICZBY")
        for document, differs in guarded[:2]:
            result.limitations.append(
                f"Bardzo podobnego twierdzenia sprawdzonego przez {document.publisher} („{short(document.claim or document.title, 110)}”) "
                f"nie uznano za to samo: różni się nazwą lub liczbą ({differs}) (reguła G1)."
            )
    return result


def _groups(cands: list[_Cand]) -> set[str]:
    """Independence groups: one per publisher (several articles of one publisher count once)."""
    return {INDEX.docs[c.doc_idx].publisher for c in cands}


def _tiers(cands: list[_Cand]) -> set[int]:
    return {TIER[INDEX.docs[c.doc_idx].source_type] for c in cands}


def _score(c: _Cand) -> float:
    if c.nli is not None:
        return max(c.nli.entail, c.nli.contra)
    return c.claim_cos


def _decide(
    claim: Claim,
    support,
    refute,
    misleading,
    unverif,
    evidence: list[Evidence],
    high_risk: bool,
    keep: set[str] = frozenset(),
) -> ClaimResult:
    """keep: doc ids of context items that answer the user's question about the check (asked_number_fragment);
    they are listed before other context items, so the evidence cut cannot drop them."""
    premises: list[Premise] = []
    rules: list[str] = []
    reasons: list[str] = []
    limitations: list[str] = []
    missing_context = context_type = None
    conflicting = False
    time_sensitive = is_time_sensitive(claim.text)
    sup_ab = [
        candidate for candidate in support if TIER[INDEX.docs[candidate.doc_idx].source_type] <= 2
    ]
    ref_ab = [
        candidate for candidate in refute if TIER[INDEX.docs[candidate.doc_idx].source_type] <= 2
    ]
    misleading = [
        candidate
        for candidate in misleading
        if TIER[INDEX.docs[candidate.doc_idx].source_type] <= 2
    ]  # a catalogue entry alone never decides

    verdict, main, decisive = "brak_dowodow", None, []
    # ---- R2: conflict guard
    if sup_ab and ref_ab:
        conflicting = True
        rules.append("R2:ZRODLA_SPRZECZNE")
        reasons.append("ZRODLA_SPRZECZNE")
    # ---- R3: refuted
    elif refute and not sup_ab and (1 in _tiers(refute) or 2 in _tiers(refute)):
        verdict, decisive = "falszywe", refute
        rules.append("R3:FALSZYWE")
    # ---- R4: misleading (fact-checker rated it so, or true content presented as current while archival)
    elif misleading and not ref_ab:
        verdict, decisive = "wprowadzajace_w_blad", misleading
        context_type = (
            "MIESZANE"
            if any(INDEX.docs[candidate.doc_idx].verdict == "mixed" for candidate in misleading)
            else "WYBIORCZOSC_LUB_KONTEKST"
        )
        rules.append("R4:WPROWADZAJACE_W_BLAD(fact-check)")
    # ---- R5: confirmed
    elif sup_ab and not ref_ab:
        verdict, decisive = "potwierdzone", sup_ab
        rules.append("R5:POTWIERDZONE")
    if unverif and verdict == "brak_dowodow":
        reasons.append("FACTCHECK_NIEWERYFIKOWALNE")

    if decisive:
        main = max(
            decisive,
            key=lambda candidate: (
                TIER[INDEX.docs[candidate.doc_idx].source_type] == 1,
                _score(candidate),
            ),
        )
        document = INDEX.docs[main.doc_idx]
        age = INDEX.doc_age(document)
        if main.archival and verdict == "falszywe":  # R3a
            rules.append("R3a:STARY_MATERIAL")
            context_type = "FALSZYWY_KONTEKST"
            missing_context = (
                f"Materiał pochodzi z {main.archival[0]} r., a twierdzenie przedstawia go jako z "
                f"{main.archival[1]} r. (źródło: {document.publisher})."
            )
        # R4 (archival context): supported, but presented as current while the evidence is old
        if (
            verdict == "potwierdzone"
            and time_sensitive
            and age is not None
            and age > settings.stale_days
        ):
            verdict, context_type = "wprowadzajace_w_blad", "NIEAKTUALNE"
            missing_context = (
                f"Opisane zdarzenie/dane pochodzą z {_fmt_date(document.published_at)}, a treść przedstawia je "
                "jako bieżące."
            )
            rules.append("R4:WPROWADZAJACE_W_BLAD(NIEAKTUALNE)")

    # ---- premises (shown as the "Dlaczego taki wynik?" checklist)
    groups = _groups(decisive)
    tiers = _tiers(decisive)
    if main is not None:
        document = INDEX.docs[main.doc_idx]
        if main.archival:
            premises.append(
                Premise(
                    label="Data materiału według analizy fact-checkingowej (reguła deterministyczna)",
                    value=f"materiał pochodzi z {main.archival[0]} r., a twierdzenie przedstawia go "
                    f"jako z {main.archival[1]} r.",
                    effect="+",
                )
            )
        elif main.numeric:
            premises.append(
                Premise(
                    label="Porównanie liczb ze źródłem urzędowym (reguła deterministyczna)",
                    value=(
                        "liczba z twierdzenia zgadza się z danymi źródła"
                        if main.numeric == "zgodne"
                        else "liczba z twierdzenia NIE zgadza się z danymi źródła za ten sam okres"
                    ),
                    effect="+",
                )
            )
        elif main.nli is not None:
            premises.append(
                Premise(
                    label="Zgodność fragmentu z twierdzeniem (model NLI)",
                    value=f"fragment {'przeczy' if main in refute else 'potwierdza'} twierdzeniu "
                    f"(ocena modelu {_score(main):.2f}, próg {settings.nli_strong})",
                    effect="+",
                )
            )
        else:
            premises.append(
                Premise(
                    label="Dopasowanie do twierdzenia już sprawdzonego",
                    value=f"podobieństwo {main.claim_cos:.2f} do twierdzenia ocenionego przez {document.publisher} "
                    f"jako „{document.verdict_raw}”"
                    + (
                        " — Twoje zdanie jest jego zaprzeczeniem"
                        if main.nli_claim and main.nli_claim.contra >= 0.8
                        else (
                            f"; model NLI: Twoja treść zawiera to twierdzenie ({main.nli_claim.entail:.2f})"
                            if main.nli_claim
                            else ""
                        )
                    ),
                    effect="+",
                )
            )
        premises.append(
            Premise(
                label="Źródło pierwotne / urzędowe",
                value="tak" if 1 in tiers else "nie",
                effect="+" if 1 in tiers else "0",
            )
        )
        premises.append(
            Premise(
                label="Niezależne potwierdzenia (wydawcy)",
                value=f"{len(groups)}: {', '.join(sorted(groups))}",
                effect="+" if len(groups) > 1 else "0",
            )
        )
        age = INDEX.doc_age(document)
        stale = time_sensitive and age is not None and age > settings.stale_days
        premises.append(
            Premise(
                label="Najnowszy dowód",
                value=f"{_fmt_date(document.published_at)}"
                + (f" ({age} dni temu)" if age is not None else ""),
                effect="-" if stale or age is None else "0",
            )
        )
    premises.append(
        Premise(
            label="Sprzeczne źródła",
            value="tak" if conflicting else "nie",
            effect="-" if conflicting else "0",
        )
    )

    # ---- strength of the basis (text, derived from premises)
    if verdict in ("falszywe", "potwierdzone", "wprowadzajace_w_blad"):
        strong = (1 in tiers and len(groups) >= 2) or (
            len(groups) >= 2 and max(_score(candidate) for candidate in decisive) >= 0.85
        )
        strength_label = "mocna" if strong and not conflicting else "umiarkowana"
        strength = 0.85 if strength_label == "mocna" else 0.6
        # stricter rule for high-risk topics: a single tier-B group is not enough to stand alone
        if high_risk and 1 not in tiers and len(groups) < 2:
            rules.append("HR:JEDNO_ZRODLO_ESKALACJA")
            limitations.append(
                "Temat wysokiego ryzyka, a ocena opiera się na jednym źródle — zalecamy sprawdzenie "
                "komunikatów właściwych instytucji; sprawa trafia do analityka."
            )
    else:
        strength_label, strength = "niewystarczająca", 0.0
        if not reasons:
            reasons.append("BRAK_MATERIALOW" if not evidence else "TYLKO_MATERIALY_POKREWNE")
        rules.append("R6:BRAK_DOWODOW")

    order = {"przeczy": 0, "popiera": 0, "kontekst": 1, "neutralne": 2}
    evidence.sort(key=lambda e: (order[e.stance], e.doc_id not in keep, e.tier, -e.similarity))
    evidence = evidence[: settings.top_k_evidence]
    limitations.append(
        "Odpowiedź opiera się wyłącznie na jawnym katalogu źródeł (zob. „Źródła”); brak wyniku nie oznacza, "
        "że informacja jest prawdziwa lub fałszywa."
    )
    explanation, unknown = _explain(verdict, main, evidence, conflicting, missing_context)
    return ClaimResult(
        claim=claim.text,
        kind=claim.kind,
        verdict=verdict,
        verdict_label=VERDICT_LABEL_PL[verdict],
        strength=strength,
        strength_label=strength_label,
        premises=premises,
        explanation=explanation,
        missing_context=missing_context,
        conflicting=conflicting,
        what_unknown=unknown,
        evidence=evidence,
        limitations=limitations,
        rules_fired=rules,
        reason_codes=reasons,
        context_type=context_type,
        high_risk=high_risk,
        would_settle=_would_settle(claim.text) if verdict == "brak_dowodow" else None,
    )


def _explain(
    verdict: str,
    main: _Cand | None,
    evidence: list[Evidence],
    conflicting: bool,
    missing_context: str | None,
) -> tuple[str, str | None]:
    """Deterministic plain-Polish explanation ('truth sandwich' order: fact -> what was claimed -> source)."""
    if verdict == "brak_dowodow":
        if conflicting:
            return (
                "Wiarygodne źródła podają w tej sprawie różne informacje, więc nie wydajemy werdyktu. Poniżej "
                "pokazujemy obie strony — porównaj ich daty i zakres.",
                "Nie da się rozstrzygnąć, które źródło opisuje stan aktualny lub pełniejszy.",
            )
        txt = (
            "Nie znaleźliśmy w naszym katalogu źródeł wystarczających materiałów, by potwierdzić albo obalić tę "
            "informację. To nie znaczy, że jest prawdziwa, ani że jest fałszywa."
        )
        related = [e for e in evidence if e.stance == "kontekst"][:2]
        if related:
            txt += (
                " Znaleźliśmy tylko materiały na pokrewny temat: "
                + "; ".join(f"„{short(e.title, 90)}” ({e.publisher})" for e in related)
                + "."
            )
        return txt, (
            "Brak źródła pierwotnego (np. komunikatu urzędu, aktu prawnego, danych) i brak analizy "
            "fact-checkingowej dotyczącej dokładnie tego twierdzenia."
        )
    d = INDEX.docs[main.doc_idx]
    who, when = d.publisher, _fmt_date(d.published_at)
    lead = {
        "falszywe": "Źródła przeczą tej informacji.",
        "potwierdzone": "Źródła potwierdzają tę informację.",
        "wprowadzajace_w_blad": "Ta informacja wprowadza w błąd.",
    }[verdict]
    if main.archival:
        body = f" Według źródła: {who} ({when})."
    elif main.nli is None and d.verdict_raw:
        body = (
            f" {who} ({when}) sprawdził bardzo podobne twierdzenie: „{short(d.claim or d.title, 160)}” i ocenił je "
            f"jako „{d.verdict_raw}”."
        )
        if main.nli_claim is not None and main.nli_claim.contra >= 0.8:
            body += " Twoje zdanie mówi coś przeciwnego niż to sprawdzone twierdzenie."
    else:
        body = f" Według źródła: {who} ({when})."
    body += f" Fragment źródła: „{shown_fragment(main.fragment, d.text or '')}”"
    if missing_context:
        body += f" Brakujący kontekst: {missing_context}"
    return lead + body, None
