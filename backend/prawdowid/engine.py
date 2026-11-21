"""Verification engine: claim -> evidence -> stance -> explicit, ordered rules -> verdict with premises.

Design principle (challenge requirement): the language model never decides what is true. Verdicts come from
transparent, versioned rules (R1–R6, see /metodologia) over retrieved, cited evidence. Models are used only to
*understand* text: embeddings for retrieval / claim matching, NLI for stance.

Source tiers (by source type and process — never by political orientation or domain reputation):
  A (1) źródło pierwotne / urzędowe   B (2) fact-checking IFCN/EFCSN, bazy incydentów   C (3) media
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

import numpy as np

from . import measures
from .agreement import disagreement, fold, same_word, specificity
from .claims import Claim
from .config import settings
from .index import INDEX, TIER, TIER_LABEL
from .nli import NLI_MODEL, NLIScore
from .schemas import VERDICT_LABEL_PL, ClaimResult, Evidence, Premise
from .textutil import amounts, is_time_sensitive, normalize_ws, same_amount, short, split_sentences, tokens

log = logging.getLogger("prawdowid.engine")

FC_TO_VERDICT = {"false": "falszywe", "misleading": "wprowadzajace_w_blad", "mixed": "wprowadzajace_w_blad",
                 "true": "potwierdzone", "unverifiable": "brak_dowodow"}
HIGH_RISK = re.compile(
    r"\b(ewakuac\w*|wojn\w*|mobilizac\w*|pob[oó]r\w*|atak\w*|zamach\w*|skażon\w*|zatru\w*|alarm\w*|schron\w*|"
    r"blackout\w*|epidemi\w*|pandemi\w*|szczepion\w*|jodek|upadł\w* bank\w*|wybor\w*|głosowani\w*|referend\w*|"
    r"rakiet\w*|dron\w*|sabota\w*|sankcj\w*|wojsk\w*|armi\w*|nato)\b", re.IGNORECASE)


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
    nli_claim: object | None = None  # NLI(user claim -> fact-checked claim): does the user assert the checked claim?
    nli_claim_rev: object | None = None  # NLI(fact-checked claim -> user claim): used only for negation detection
    numeric: str | None = None  # deterministic number check vs. an official fact card: "zgodne" | "niezgodne"
    extra_irrelevant: bool = False  # official card about another period / currency / act
    # number differs, but the claim may use another definition of the indicator (measures.py): the note saying why
    definitional: str = ""
    # one sentence of a multi-sentence checked claim (see _claim_units): the user often repeats only the rated core
    unit: str = ""
    unit_cos: float = 0.0
    nli_unit: object | None = None  # NLI(user claim -> unit)
    nli_unit_rev: object | None = None  # NLI(unit -> user claim)
    nli_head_unit: object | None = None  # NLI(fact-checker's headline -> unit): does the headline deny / affirm it?
    explains: bool = False  # fragment = the passage giving the number the user asks about (asked_number_fragment)
    archival: tuple[int, int] | None = None  # (year of the material per the analysis, year it is presented as)
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


def _best_fragment(doc_idx: int, q_emb: np.ndarray, q_tokens: set[str]) -> tuple[str, float]:
    """Pick the quoted fragment WITHOUT re-encoding: best chunk of the document by (cached) embedding similarity,
    then the 1–2 consecutive sentences with the highest lexical overlap with the claim, cut verbatim out of the
    stored source text (see _fragment_windows). This exact span is both quoted to the user and judged by NLI."""
    ids = [i for i in INDEX.doc_chunks[doc_idx] if i not in INDEX.synthetic]
    d = INDEX.docs[doc_idx]
    if not ids:
        return (d.text or d.title)[:400], 0.0
    sims = INDEX.chunk_emb[ids] @ q_emb
    j = int(np.argmax(sims))
    text, cos = INDEX.chunks[ids[j]].text, float(sims[j])
    windows = _fragment_windows(text, d.text or "")
    head_tokens: set[str] = set()
    if d.claim and d.source_type in ("factcheck", "incident"):
        # A fact-check's text starts by restating the checked claim, which always overlaps the user's words most and
        # wins the best chunk. Quoting it back proves nothing: the quote must be the analysis' finding. So the whole
        # analysis is searched (the claim's own sentences left out) for the passage that shares most words with the
        # user's claim AND with the fact-checker's headline, which states the finding ("Depesza PAP nie została
        # usunięta"). The claim itself is quoted only when the record has nothing else.
        own = [w for k in ids for w in _fragment_windows(INDEX.chunks[k].text, d.text or "") if not _restates(w, d.claim)]
        if own:
            windows, head_tokens = list(dict.fromkeys(own)), set(tokens(d.title))
    if not windows:  # nothing of this passage can be found in the stored text (e.g. a title-only document): gate V2 decides
        windows = [([x for x in split_sentences(text) if len(x) > 15] or [text])[0][:520]]

    def score(w: str) -> float:
        wt = set(tokens(w))
        head = len(head_tokens & wt) / len(head_tokens) if head_tokens else 0.0
        return len(q_tokens & wt) / max(1, len(q_tokens)) + head - len(w) / 5000  # prefer shorter on ties

    best = max(windows, key=score)
    if head_tokens:  # a leading list bullet of the analysis is not part of the quote (fact-checks: never judged by NLI)
        best = best.lstrip("-–•* ") or best
    return best, cos


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
    """Whitespace-normalised text: the form in which gate V2 compares a quote with its source."""
    return re.sub(r"\s+", " ", normalize_ws(s)).strip()


def _fragment_windows(passage: str, source: str, max_len: int = 520, min_len: int = 16, max_gap: int = 6) -> list[str]:
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
        windows = [src[a:a + max_len]]
    return windows


_YEAR_RX = re.compile(r"\b(19|20)\d\d\b")


def asked_number_fragment(text: str, claim_text: str, asked: list[tuple]) -> str | None:
    """'Dlaczego w analizie jest 650 mln zł?': the verbatim passage of the analysis that gives the asked number.
    Sentences of the checked claim itself are skipped. Among the passages that contain the number, the one that also
    states its period (a year) is preferred, so the quote shows what the figure refers to; then the shortest."""
    in_claim = _squash(claim_text)
    hits = [w for w in _fragment_windows(text, text)
            if w not in in_claim and any(same_amount(a, x) for a in asked for x in amounts(w))]
    return min(hits, key=lambda w: (not _YEAR_RX.search(w), len(w))) if hits else None


# ------------------------------------------------------------------ old material presented as current (rule R3a)
# "Czy film udostępniony przez X w 2026 r. pokazywał ówczesny protest pod Y?" — a claim that a recording / photo shows
# an event of the time it was shared. A fact-check about that material that dates it to an EARLIER year refutes it
# deterministically (the NLI model reads almost every sentence of such an analysis as a contradiction, so it cannot
# be used here). Same material = the analysis names at least two of the claim's proper names.
_MATERIAL = re.compile(r"\b(film\w*|nagra\w*|wideo|video|klip\w*|zdjęci\w*|zdjęć|fotografi\w*|materiał\w*)\b", re.I)
_PRESENTED_NOW = re.compile(r"\b(ówczesn\w*|aktualn\w*|bieżąc\w*|obecn\w*|dzisiejsz\w*|tegoroczn\w*|teraz|dziś|"
                            r"dzisiaj|niedawn\w*)\b", re.I)
_ORIGIN = re.compile(r"\b(pochodz\w*|nagran\w*|nakręcon\w*|zarejestrowan\w*|wykonan\w*|zrobion\w*|powstał\w*)\b"
                     r"[^.]{0,40}?\b(?:z|w|we)\s+(?:[^\W\d]+\s+){0,2}?((?:19|20)\d\d)\b", re.I)
_PROPER = re.compile(r"(?<=[\s(„\"])[A-ZĄĆĘŁŃÓŚŹŻ][\wąćęłńóśźż-]{2,}")


def presented_year(claim: str, published_at: str | None) -> int | None:
    """The year a claim about a material presents it as from: an explicit year, or — for 'ówczesny / aktualny /
    teraz' without one — the year the fact-check was published (when the material was being shared)."""
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
        m = next((m for s in split_sentences(w) if _MATERIAL.search(s) for m in [_ORIGIN.search(s)] if m), None)
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
    """Validity gate V2: the quoted fragment must be a verbatim substring of the stored source text."""
    return _squash(fragment) in _squash(doc_text)


def _evidence(c: _Cand, stance: str, score: float, same: bool | None) -> Evidence:
    d = INDEX.docs[c.doc_idx]
    return Evidence(
        doc_id=d.id, title=d.title, publisher=d.publisher, domain=d.domain, url=d.url, source_type=d.source_type,
        tier=TIER[d.source_type], published_at=d.published_at, retrieved_at=d.retrieved_at, age_days=INDEX.doc_age(d),
        fragment=c.fragment, factcheck_claim=d.claim, factcheck_verdict_raw=d.verdict_raw, factcheck_verdict=d.verdict,
        retrieval_score=round(c.retrieval, 4), similarity=round(max(c.claim_cos, c.frag_cos), 3), stance=stance,
        stance_score=round(score, 3), same_claim=same, license=d.license)


def _would_settle(claim: str) -> str:
    c = claim.lower()
    if re.search(r"ustaw|przepis|rozporządz|prawo|zakaz|nakaz|kodeks|dyrektyw|unijn|ue\b|bruksel", c):
        return "akt prawny w ISAP (Dziennik Ustaw) lub EUR-Lex albo komunikat właściwego ministerstwa"
    if re.search(r"\d|procent|%|mln|mld|tys|wzrost|spad|inflac|cen|płac|emerytur|świadcze", c):
        return "aktualne dane GUS, NBP, Eurostatu lub komunikat ZUS/właściwego ministerstwa"
    if re.search(r"szczepion|chorob|lek|zdrow|wirus|szpital", c):
        return "komunikat Ministerstwa Zdrowia / GIS lub analiza organizacji fact-checkingowej"
    if re.search(r"wojsk|armi|nato|ukrain|rosj|granic|ambasad|msz|dyplomac", c):
        return "komunikat MSZ, MON lub RCB albo analiza organizacji fact-checkingowej"
    return "komunikat właściwej instytucji lub analiza organizacji fact-checkingowej (IFCN/EFCSN)"


_NUM = re.compile(r"(\d+(?:[.,]\d+)?)\s*(%|proc\w*|zł\b|złotych|zl\b|mln|mld|tys)", re.I)
_MONTHS = ["stycz", "lut", "marc|marz", "kwie", "maj", "czerw", "lip", "sierp", "wrze", "paźdz|pazdz", "listop", "grud"]
_MONTHS_STEMS = ["stycz", "luty", "lute", "marz", "marc", "kwie", "maj", "czerw", "lipi", "sier", "wrze", "pazd", "listo", "grud"]


def _unit(u: str) -> str:
    u = u.lower()
    return "%" if u.startswith(("%", "proc")) else "zł" if u.startswith(("zł", "zl")) else u


def _numbers(s: str) -> list[tuple[float, str]]:
    return [(float(v.replace(",", ".")), _unit(u)) for v, u in _NUM.findall(s)]


_ORDINAL = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "1": 1, "2": 2, "3": 3, "4": 4, "pierwsz": 1, "drug": 2, "trzeci": 3,
            "czwart": 4}
_QUARTER_RX = re.compile(r"\b(i{1,3}|iv|[1-4])\s*(?:kw\.|kwarta\w*)|\bq([1-4])\b|\b(pierwsz|drug|trzeci|czwart)\w*\s+kwarta\w*")
_HALF_RX = re.compile(r"\b(i{1,2}|[12])\s*półrocz\w*|\b(pierwsz|drug)\w*\s+(?:półrocz\w*|połow\w*\s+(?:roku|20\d\d))"
                      r"|\b20\d\d-s([12])\b")


def _date_keys(s: str) -> tuple[set[str], set[int]]:
    """Years and months a text refers to. Months come from month names, YYYY-MM, MM.YYYY / MM/YYYY, quarters
    ("III kwartał", "Q3", "w trzecim kwartale") and halves ("I półrocze", "w pierwszej połowie roku", "2026-S1")."""
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


_MEASURES = [  # (source marker, words that must appear in the claim for the comparison to be meaningful)
    (re.compile(r"\bHICP\b"), re.compile(r"hicp|eurostat|zharmonizowan", re.I)),
    (re.compile(r"\bCPI\b"), re.compile(r"\bcpi\b|gus|inflacj(?!.*hicp)", re.I)),
    (re.compile(r"\bEUR\b"), re.compile(r"euro|\beur\b", re.I)),
    (re.compile(r"\bUSD\b"), re.compile(r"dolar|\busd\b", re.I)),
    (re.compile(r"\bCHF\b"), re.compile(r"frank|\bchf\b", re.I)),
    (re.compile(r"\bGBP\b"), re.compile(r"funt|\bgbp\b", re.I)),
]


def _compatible(claim: str, source_title: str, source_text: str = "") -> bool:
    if not measures.compatible(claim, source_title, source_text):  # claim names another definition (HICP vs CPI…)
        return False
    return all(rx_claim.search(claim) for rx_src, rx_claim in _MEASURES if rx_src.search(source_title))


_PL_MONTHS = {"stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6, "lipca": 7, "sierpnia": 8,
              "września": 9, "października": 10, "listopada": 11, "grudnia": 12}
_DATE_RX = re.compile(r"\b(\d{1,2})\s+(" + "|".join(_PL_MONTHS) + r")\s+(\d{4})|\b(\d{4})-(\d{2})-(\d{2})\b|\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", re.I)


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
_CURR_NAMES = {  # currency names in any inflected form; the crowns and the dollars only with their country
    "EUR": r"\beuro\b|\beur\b", "USD": rf"\bdolar\w*\b{_OTHER_DOLLARS}", "CHF": r"\bfrank(?:a|i|ów|ow|om|ami|ach|iem)?\b",
    "GBP": r"\bfunt\w*\b", "NOK": r"\bkoron\w*\s+norwe", "SEK": r"\bkoron\w*\s+szwedz", "DKK": r"\bkoron\w*\s+du[nń]s",
    "CZK": r"\bkoron\w*\s+czes", "JPY": r"\bjen(?:a|y|ów|ow|om|ami|ach|ie)?\b", "HUF": r"\bforint\w*", "UAH": r"\bhrywn\w*",
    "CNY": r"\bjuan\w*|\byuan\w*|\brenminbi", "CAD": r"\bdolar\w*\s+kanadyj", "AUD": r"\bdolar\w*\s+australij"}


def _names_currency(claim: str, code: str) -> bool:
    return bool(re.search(rf"\b{code}\b", claim, re.I) or (code in _CURR_NAMES and re.search(_CURR_NAMES[code], claim, re.I)))


# the same indicator or subject named differently in a claim and in an official card's title: synonyms, abbreviations
# and inflected forms (general Polish vocabulary of statistics and law). Both texts are rewritten to one word per
# subject before the subject gate compares stems ("płaca minimalna" ~ "minimalne wynagrodzenie", "zmarło" ~ "zgonów").
_SUBJECT_SYNONYMS = [(re.compile(rf"\b(?:{p})\b", re.I), w) for p, w in (
    (r"produkt\w* krajow\w* brutto", "PKB"),
    (r"wynagrodze\w*|płac(?:a|y|ę|e|om|ach|ami)|plac[ay]|pensj\w*|zarobk\w*|zarabia\w*|zarobi\w*", "wynagrodzenie"),
    (r"zgon\w*|zmar[łl]\w*|umar[łl]\w*|umiera\w*|śmier[cć]\w*|smierc\w*|śmiertelnoś\w*|smiertelnos\w*", "zgon"),
    (r"urodze\w*|urodzi\w*|narodzin\w*", "urodzenie"),
    (r"ludnoś\w*|ludnos\w*|mieszkańc\w*|mieszkanc\w*|populacj\w*", "ludność"),
    (r"inflacj\w*|inflacyjn\w*|drożyzn\w*|drozyzn\w*", "inflacja"),
    (r"bezroboci\w*|bezrobotn\w*", "bezrobocie"),
    (r"zadłużeni\w*|zadluzeni\w*|zadłużon\w*|zadluzon\w*|dług(?:u|iem|i|ów|ow|om|ach|ami)?|dlug(?:u|iem|i|ow|om|ach|ami)?",
     "dług"),
    (r"emerytur\w*|emeryt(?:a|ów|ow|om|ami|ach|y|ka|ki)?", "emerytura"),
    (r"azyl\w*|ochron\w* międzynarodow\w*", "azyl"),
    (r"prąd\w*|prad(?:u|em)?|energi\w* elektryczn\w*", "prąd"),
)]


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
    the card does not decide the claim (another definition gives the claimed number, or no card for it is indexed)."""
    open_dims = measures.unnamed(claim, d.title, d.text)
    if not open_dims:
        return ""
    m = measures.measure_of(d.title, d.text)
    missing: list[str] = []
    for dim, own in open_dims:
        for alt in dim.variants:
            if alt.name == own.name:
                continue
            cards = [o for o in INDEX.docs if o.source_type == "official" and o is not d
                     and measures.uses(o.title, o.text, m.key, dim.key) == alt.name
                     and measures.compatible(claim, o.title, o.text) and same_subject(claim, o.title)]
            agree = next((o for o in cards if numeric_stance(claim, f"{o.title}. {o.text[:6000]}") == "zgodne"), None)
            if agree is not None:
                return (f"Wartość zależy od przyjętej miary: {agree.publisher} („{short(agree.title, 80)}”) podaje tę "
                        f"liczbę według definicji {alt.name}, a {d.publisher} („{short(d.title, 80)}”) inną według "
                        f"definicji {own.name}. Twierdzenie nie mówi, o którą miarę chodzi.")
            if not cards:
                missing.append(alt.name)
    if missing:
        return (f"Wartość zależy od przyjętej miary: {d.publisher} („{short(d.title, 80)}”) podaje inną liczbę według "
                f"definicji {open_dims[0][1].name}; dla innej definicji ({', '.join(missing)}) nie mam danych za ten "
                "okres, a twierdzenie nie mówi, o którą miarę chodzi.")
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
        subj_years = set(re.findall(r"\bw\s+((?:19|20)\d\d)\s*r", title))  # "…stawki godzinowej w 2027 r."
        claim_years = set(re.findall(r"\b((?:19|20)\d\d)\b", claim))
        if subj_years and claim_years and not (subj_years & claim_years):
            return False  # the act regulates another year
        nums = re.findall(r"\b(\d{4}/\d{1,5})\b", claim)
        if nums:
            return any(n in title for n in nums)
        m = re.search(r"\b(?:o|w sprawie)\s+(.+)$", title)
        subject = set(tokens(_subject_text(m.group(1) if m else title), stem=5))
        return len(subject & set(tokens(_subject_text(claim), stem=5))) / max(1, len(subject)) >= 0.4
    head = re.split(r"[:—–]\s*\d", title)[0]  # e.g. "Ceny — transport — wrzesień 2026" / "Inflacja CPI w Polsce — marzec 2026"
    subj = _anchors(_subject_text(re.sub(r"\b(19|20)\d\d(-\d\d)?(-\d\d)?\b", " ", head))) - {t for t in tokens(" ".join(_PL_MONTHS))}
    subj = {t for t in subj if not any(t.startswith(m[:4]) for m in _MONTHS_STEMS)}
    if subj and not (_alt_stems(subj) & _alt_stems(tokens(_subject_text(claim)))) and not re.search(r"\b[A-Z]{3}/PLN\b", title):
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
    if explicit or (about_law and re.search(r"^\s*od\s+\d{1,2}\s+\w+\s+\d{4}|obowiązuje od", claim, re.I)):
        m = re.search(r"wejście w życie:\s*(\d{4}-\d{2}-\d{2})", text)
        if m:
            return "zgodne" if _dates(m.group(1))[0] in cd else "niezgodne"
    if re.search(r"przyję\w*|przyjęt\w*|uchwal\w*|z dnia|podpisan\w*|wydan\w*", claim, re.I):
        m = re.search(r"z dnia\s+(\d{1,2}\s+\w+\s+\d{4})", title)
        if m and _dates(m.group(1)):
            return "zgodne" if _dates(m.group(1))[0] in cd else "niezgodne"
    return None


_GENERIC = set(tokens("polsce polska polski gus nbp eurostat kurs średni dane wskaźnik według wyniósł wyniosła wynosi "
                     "procent proc r/r rok roku miesiąc ceny obwieszczenie państwowej komisji wyborczej dnia"))


def _anchors(claim: str) -> set[str]:
    return {t for t in tokens(claim) if not t[0].isdigit() and t not in _GENERIC and len(t) > 2}


def _anchor_text(claim: str, d) -> str:
    """Sentences of the source that mention the claim's subject (e.g. 'frekwencja', 'Nawrocki'), for number checks."""
    anchors = _anchors(claim)
    scored = [(len(anchors & set(tokens(x))), i, x) for i, x in enumerate(split_sentences(d.text[:6000]))]
    best = sorted([t for t in scored if t[0] > 0], key=lambda t: (-t[0], t[1]))[:3]
    return " ".join(x for _, _, x in sorted(best, key=lambda t: t[1]))


_WORD = re.compile(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+")


def _bound_values(keys: set[str], source: str, unit: str) -> list[float]:
    """Numbers (in `unit`) that directly follow the MOST SPECIFIC of `keys` in the source — key->value binding,
    e.g. 'stopa referencyjna: 3,75%', so a value printed elsewhere on the card (lombard 4,25%) cannot match."""
    from .textutil import strip_pl
    occ: dict[str, list[int]] = {}
    for m in _WORD.finditer(source):
        st = strip_pl(m.group(0))[:6]
        if st in keys:
            occ.setdefault(st, []).append(m.end())
    nums = [(m.start(), float(m.group(1).replace(",", ".")), _unit(m.group(2))) for m in _NUM.finditer(source)]
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
        keys = _anchors(claim[prev:m.start()]) or _anchors(claim)
        prev = m.end()
        cands = _bound_values(keys, source, u)
        if not cands and len(source) < 700:  # short single-value fact card: any same-unit value
            cands = [x for x, su in sn if su == u]
        if not cands:
            continue
        window = claim[max(0, m.start() - 40): m.start()]
        op = ">" if re.search(r"przekrocz\w*|ponad|powyżej|więcej niż|wyższ\w* niż", window, re.I) else \
             "<" if re.search(r"poniżej|mniej niż|niższ\w* niż|nie przekrocz\w*", window, re.I) else "="
        if op == "=":
            ok = any(abs(x - v) <= max(0.051, abs(v) * 0.005) for x in cands)
        else:
            ok = cands[0] > v if op == ">" else cands[0] < v
        verdicts.append(ok)
    if not verdicts:
        return None
    return "zgodne" if all(verdicts) else "niezgodne"


def claim_match(cos: float, fwd, rev, checked_claim: str, user_text: str, source_type: str) -> tuple[bool | None, str | None]:
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
        if ((cos >= 0.86 and fwd.entail >= (0.8 if incident else 0.5))
                or (not incident and cos >= 0.80 and fwd.entail >= 0.8 and lex >= 0.4)):
            return True, None
        if cos >= 0.88 and not incident:  # similarity alone
            try:
                note = disagreement(user_text, checked_claim)
            except Exception:  # noqa: BLE001 — a failing text heuristic must not fail the check; keep the old behaviour
                log.exception("agreement guard failed")
                note = None
            return (None, note) if note else (True, None)
    return None, None


def same_claim(cos: float, fwd, rev, checked_claim: str, user_text: str, source_type: str) -> bool | None:
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
    keep = [s for s in split_sentences(title or "") if not s.rstrip().endswith("?") and len(tokens(s)) >= 3]
    return " ".join(keep)


def _claim_units(ranked: list[_Cand], q_emb: np.ndarray) -> None:
    """Best sentence unit (by cosine) for every candidate fact-check that can inherit its rating per sentence."""
    todo = []
    for c in ranked:
        d = INDEX.docs[c.doc_idx]
        if not (c.is_claim_match and d.claim and d.source_type == "factcheck" and d.verdict in UNIT_RATINGS
                and headline_statement(d.title)):
            continue
        units = claim_units(d.claim)
        if units:
            todo.append((c, units))
    if not todo:
        return
    embs = INDEX.encode_query([u for _, units in todo for u in units])
    pos = 0
    for c, units in todo:
        sims = embs[pos:pos + len(units)] @ q_emb
        pos += len(units)
        j = int(np.argmax(sims))
        c.unit, c.unit_cos = units[j], float(sims[j])


def unit_match(c: _Cand, d, user_text: str) -> bool | None:
    """Decision of the sentence route (see claim_units): None unless the fact-checker's headline rules on the unit."""
    if not c.unit or c.nli_unit is None or c.nli_head_unit is None:
        return None
    if getattr(c.nli_head_unit, UNIT_RATINGS[d.verdict]) < UNIT_HEADLINE_NLI:
        return None
    return same_claim(c.unit_cos, c.nli_unit, c.nli_unit_rev or c.nli_unit, c.unit, user_text, d.source_type)


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
    (rating, claim, headline, link) does not: there is no passage of the analysis to quote as the finding, and the
    organisers' rule is that every verdict rests on a source quoted verbatim."""
    return bool(set(tokens(d.text or "")) - set(tokens(d.title or "")) - set(tokens(d.claim or "")))


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
    return len(small) >= 3 and small <= big and bool(_NEGATION.search(a)) == bool(_NEGATION.search(b))


def consistent_matches(support: list, refute: list, misleading: list, evidence: list[Evidence]) -> list[str]:
    """Reconcile the fact-check matches (see above) in place; returns audit notes for the polarity conflicts it
    resolved (duplicates are collapsed silently)."""
    buckets = {"falszywe": refute, "potwierdzone": support, "wprowadzajace_w_blad": misleading}
    matched = [c for b in buckets.values() for c in b if c.same is not None and c.implied in buckets]
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
                notes.append(f"Analizy „{short(dk.claim or dk.title, 90)}” i „{short(d.claim or d.title, 90)}” "
                             f"({d.publisher}) mają tę samą ocenę, a dopasowania wskazywały przeciwne wnioski; przyjęto "
                             "dopasowanie lepiej potwierdzone przez model NLI (pierwsze), drugie pokazano jako kontekst.")
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
def verify_claim(claim: Claim, timings: dict[str, float]) -> ClaimResult:
    high_risk = bool(HIGH_RISK.search(claim.text))
    # ---- R1: opinions / predictions are not verifiable
    if claim.kind in ("opinia", "prognoza"):
        what = "opinię lub ocenę" if claim.kind == "opinia" else "przewidywanie dotyczące przyszłości"
        return ClaimResult(
            claim=claim.text, kind=claim.kind, verdict="nie_podlega_weryfikacji",
            verdict_label=VERDICT_LABEL_PL["nie_podlega_weryfikacji"], strength=0.0, strength_label="nie dotyczy",
            premises=[Premise(label="Rodzaj wypowiedzi", value=f"wypowiedź zawiera {what}", effect="0")],
            rules_fired=["R1:NIE_PODLEGA_WERYFIKACJI"], high_risk=high_risk,
            explanation=(f"To {what} — nie da się jej potwierdzić ani obalić faktami. Możemy sprawdzić konkretne fakty, "
                         "na których się opiera: wpisz je osobno (np. liczby, daty, decyzje)."),
            limitations=["Rozpoznanie opinii opiera się na sygnałach językowych i może się mylić."])

    # ---- retrieval
    t0 = time.perf_counter()
    q_emb = INDEX.encode_query([claim.query])[0]
    cands: dict[int, _Cand] = {}
    for doc_idx, cos in INDEX.match_claims(q_emb, claim.query, k=8):
        if cos >= settings.claim_match_soft - 0.06:
            # cos: closest row (checked claim or headline) — finds and ranks the analysis; claim_cos: the checked
            # claim itself — what claim matching rules on (a headline may state the correction, not the claim)
            ccos = INDEX.checked_claim_cos(doc_idx, q_emb)
            cands[doc_idx] = _Cand(doc_idx, "", cos, cos, is_claim_match=True, claim_cos=ccos)
    for chunk_idx, fused, cos in INDEX.search_chunks(claim.query, q_emb, k=settings.top_k_retrieval):
        ch = INDEX.chunks[chunk_idx]
        if cos < 0.55:  # dense-similarity floor: below it the passage is off-topic
            continue
        c = cands.setdefault(ch.doc_idx, _Cand(ch.doc_idx, ch.text, fused, cos))
        if cos >= c.cos or not c.chunk_text:
            c.chunk_text, c.cos, c.retrieval = ch.text, max(c.cos, cos), max(c.retrieval, fused)
    ranked = sorted(cands.values(), key=lambda c: -max(c.claim_cos, c.cos))[: settings.top_k_evidence + 2]
    timings["retrieval_ms"] = timings.get("retrieval_ms", 0) + (time.perf_counter() - t0) * 1000

    # ---- fragments (verbatim) + stance (NLI on exactly the quoted fragment)
    t0 = time.perf_counter()
    q_tokens = set(tokens(claim.query))
    for c in ranked:
        c.fragment, c.frag_cos = _best_fragment(c.doc_idx, q_emb, q_tokens)
    # "Czy X wydaje 700 mln zł? Dlaczego w analizie jest 650 mln zł?": an analysis of a statement that gave the user's
    # number quotes the passage with the asked number instead (the answer layer explains the two figures)
    stated = amounts(claim.query)
    asked = [a for a in amounts(getattr(claim, "meta", "")) if not any(same_amount(a, x) for x in stated)]
    for c in ranked if asked and stated else []:
        d = INDEX.docs[c.doc_idx]
        if d.source_type == "factcheck" and d.claim and any(same_amount(x, y) for x in stated for y in amounts(d.claim)):
            frag = asked_number_fragment(d.text or "", d.claim, asked)
            if frag:
                c.fragment, c.explains = frag, True
    for c in ranked:  # rule R3a: old material presented as current
        d = INDEX.docs[c.doc_idx]
        if d.source_type == "factcheck" and (year := presented_year(claim.query, d.published_at)):
            hit = archival_origin(d, claim.query, year)
            if hit:
                c.fragment, c.archival = hit[0], (hit[1], year)
    _claim_units(ranked, q_emb)
    timings["fragments_ms"] = timings.get("fragments_ms", 0) + (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    pairs, owners = [], []
    for c in ranked:
        d = INDEX.docs[c.doc_idx]
        if c.is_claim_match and d.claim and c.claim_cos >= 0.78:
            pairs.append((claim.query, d.claim)); owners.append((c, "claim"))
            if c.claim_cos >= 0.85:  # reverse direction only needed for the negation test
                pairs.append((d.claim, claim.query)); owners.append((c, "claim_rev"))
        if c.unit and c.unit_cos >= UNIT_MIN_COS:  # sentence route (claim_units)
            pairs.append((claim.query, c.unit)); owners.append((c, "unit"))
            if c.unit_cos >= 0.85:
                pairs.append((c.unit, claim.query)); owners.append((c, "unit_rev"))
            pairs.append((headline_statement(d.title), c.unit)); owners.append((c, "head_unit"))
        if d.source_type == "official" and not same_subject(claim.query, d.title):
            c.extra_irrelevant = True  # another period/currency/act — not evidence either way
            continue
        if d.source_type in ("official", "media") and _relevance(q_tokens, f"{d.title} {c.fragment}") >= 0.4:
            pairs.append((c.fragment, claim.query)); owners.append((c, "frag"))
    for (c, kind), s_ in zip(owners, NLI_MODEL.score(pairs)):
        setattr(c, {"claim": "nli_claim", "claim_rev": "nli_claim_rev", "frag": "nli", "unit": "nli_unit",
                    "unit_rev": "nli_unit_rev", "head_unit": "nli_head_unit"}[kind], s_)
    # deterministic checks override NLI for structured official cards (NLI is weak at numbers and dates)
    for c in ranked:
        d = INDEX.docs[c.doc_idx]
        if d.source_type != "official" or max(c.frag_cos, c.cos) < 0.65 or c.extra_irrelevant:
            continue
        num = None
        if _compatible(claim.query, d.title, d.text):
            num = numeric_stance(claim.query, f"{d.title}. {d.text[:6000]}")
            if num == "niezgodne":
                c.definitional = _other_definition(claim.query, d)
                if c.definitional:  # e.g. CPI vs HICP: the claim may use the other measure — not a contradiction
                    num = None
        num = num or legal_date_stance(claim.query, d.title, d.text)
        if num:
            c.numeric = num
            c.nli = NLIScore(0.95, 0.03, 0.02) if num == "zgodne" else NLIScore(0.02, 0.03, 0.95)
    timings["nli_ms"] = timings.get("nli_ms", 0) + (time.perf_counter() - t0) * 1000

    # ---- evidence validity gates + stance classification
    support, refute, misleading, unverif, evidence, definitional = [], [], [], [], [], []
    quote_failures = 0
    guarded: list[tuple[object, str]] = []  # G1: very similar checked claims not accepted, with what differed
    by_unit: list[tuple[object, str]] = []  # matched through one sentence of the checked claim (claim_units)
    metadata_only: list[str] = []  # V3: matched records with no text of their own (see has_own_text)
    for c in ranked:
        d = INDEX.docs[c.doc_idx]
        if c.extra_irrelevant:
            continue
        if not _quote_ok(c.fragment, d.text or ""):
            quote_failures += 1  # V2 failed: never show a quote we cannot find verbatim in the source
            continue
        if d.source_type in ("factcheck", "incident"):
            nc, same, differs = c.nli_claim, None, None
            if c.is_claim_match and nc is not None:
                same, differs = claim_match(c.claim_cos, nc, c.nli_claim_rev or nc, d.claim or "", claim.query, d.source_type)
            if same is None and c.is_claim_match:
                same = unit_match(c, d, claim.query)
                if same is not None:
                    differs = None  # the whole quote differed, the sentence the fact-checker ruled on does not
                    c.claim_cos = max(c.claim_cos, c.unit_cos)
                    c.via_unit = True
                    by_unit.append((d, c.unit))
            if differs:
                guarded.append((d, differs))
            mapped = FC_TO_VERDICT.get(d.verdict or "") if same is not None else None
            if mapped and same is False:
                mapped = {"falszywe": "potwierdzone", "potwierdzone": "falszywe"}.get(mapped)
            c.same, c.implied = same, mapped
            if mapped in ("falszywe", "potwierdzone", "wprowadzajace_w_blad") and not has_own_text(d):
                # V3: no passage of its own carries the finding (a ClaimReview metadata entry: headline + checked
                # claim only), so the record is listed as related and never decides
                metadata_only.append(d.id)
                evidence.append(_evidence(c, "kontekst", c.claim_cos, same)); continue
            if mapped is None and same is None and c.archival:  # R3a: the analysis dates the material earlier
                refute.append(c); evidence.append(_evidence(c, "przeczy", max(c.claim_cos, c.cos), None)); continue
            if mapped == "falszywe":
                refute.append(c); evidence.append(_evidence(c, "przeczy", c.claim_cos, same)); continue
            if mapped == "potwierdzone":
                support.append(c); evidence.append(_evidence(c, "popiera", c.claim_cos, same)); continue
            if mapped == "wprowadzajace_w_blad":
                misleading.append(c); evidence.append(_evidence(c, "kontekst", c.claim_cos, same)); continue
            if mapped == "brak_dowodow":
                unverif.append(c)
            if max(c.claim_cos, c.frag_cos) >= 0.70 or c.explains:
                evidence.append(_evidence(c, "kontekst", max(c.claim_cos, c.frag_cos), same))
        elif c.definitional:
            evidence.append(_evidence(c, "kontekst", c.frag_cos, None))
            definitional.append(c)
        elif c.nli is not None:
            s_ = c.nli
            strong_topic = c.numeric is not None or c.frag_cos >= 0.72
            if s_.entail >= settings.nli_strong and s_.entail > s_.contra and strong_topic:
                support.append(c); evidence.append(_evidence(c, "popiera", s_.entail, None))
            elif s_.contra >= settings.nli_strong and s_.contra > s_.entail and strong_topic and (
                    c.numeric or _relevance(q_tokens, f"{d.title} {c.fragment}") >= 0.5):
                refute.append(c); evidence.append(_evidence(c, "przeczy", s_.contra, None))
            elif c.frag_cos >= 0.72:
                evidence.append(_evidence(c, "kontekst", c.frag_cos, None))
    resolved = consistent_matches(support, refute, misleading, evidence)
    res = _decide(claim, support, refute, misleading, unverif, evidence, high_risk,
                  keep={INDEX.docs[c.doc_idx].id for c in ranked if c.explains})
    res.meta_question = getattr(claim, "meta", "") or None
    if metadata_only:
        res.rules_fired.append("V3:TYLKO_METADANE")
    if resolved:
        res.rules_fired.append("P1:SPOJNE_DOPASOWANIA")
        res.premises.append(Premise(label="Spójność dopasowań do analiz tego samego twierdzenia lub wydawcy",
                                    value=" ".join(resolved), effect="0"))
    if definitional:
        note = definitional[0].definitional
        res.premises.append(Premise(label="Różne definicje wskaźnika", value=note, effect="-"))
        if res.verdict == "potwierdzone":
            res.missing_context = note
        elif res.verdict == "brak_dowodow":
            res.reason_codes.append("ROZNE_DEFINICJE")
            res.what_unknown = note
    if by_unit and res.verdict in ("falszywe", "potwierdzone"):  # audit trail of the sentence route (claim_units)
        d, unit = by_unit[0]
        res.rules_fired.append("M1:ZDANIE_SPRAWDZONEJ_WYPOWIEDZI")
        res.premises.insert(0, Premise(
            label="Dopasowanie do jednego zdania sprawdzonej wypowiedzi",
            value=(f"Twoje zdanie odpowiada zdaniu „{short(unit, 140)}” z wypowiedzi sprawdzonej przez {d.publisher}; "
                   f"nagłówek analizy („{short(headline_statement(d.title), 100)}”) "
                   f"{'zaprzecza' if d.verdict == 'false' else 'potwierdza'} właśnie temu zdaniu."), effect="+"))
    if guarded:  # audit trail: similarity alone would have matched these; the names or numbers differ
        res.rules_fired.append("G1:ROZNE_NAZWY_LUB_LICZBY")
        for d, differs in guarded[:2]:
            res.limitations.append(f"Bardzo podobnego twierdzenia sprawdzonego przez {d.publisher} („{short(d.claim or d.title, 110)}”) "
                                   f"nie uznano za to samo: różni się nazwą lub liczbą ({differs}) (reguła G1).")
    if quote_failures:
        res.limitations.append(f"Pominięto {quote_failures} materiał(y), których cytatu nie dało się dosłownie "
                               "odnaleźć w źródle (bramka V2).")
    return res


def _specificity(query: str, c: _Cand) -> int:
    """agreement.specificity against what the source states about the claim: its title, the checked claim and who
    made it, and the quoted fragment (not the whole body, so a long article does not win by length)."""
    d = INDEX.docs[c.doc_idx]
    return specificity(query, ". ".join(x for x in (d.title, d.claim, d.claim_author, c.fragment) if x))


def _groups(cands: list[_Cand]) -> set[str]:
    """Independence groups: one per publisher (several articles of one publisher count once)."""
    return {INDEX.docs[c.doc_idx].publisher for c in cands}


def _tiers(cands: list[_Cand]) -> set[int]:
    return {TIER[INDEX.docs[c.doc_idx].source_type] for c in cands}


def _score(c: _Cand) -> float:
    if c.nli is not None:
        return max(c.nli.entail, c.nli.contra)
    return c.claim_cos


def _decide(claim: Claim, support, refute, misleading, unverif, evidence: list[Evidence], high_risk: bool,
            keep: set[str] = frozenset()) -> ClaimResult:
    """keep: doc ids of context items that answer the user's question about the check (asked_number_fragment);
    they are listed before other context items, so the evidence cut cannot drop them."""
    premises: list[Premise] = []
    rules: list[str] = []
    reasons: list[str] = []
    limitations: list[str] = []
    missing_context = context_type = None
    conflicting = False
    time_sensitive = is_time_sensitive(claim.text)
    sup_ab = [c for c in support if TIER[INDEX.docs[c.doc_idx].source_type] <= 2]
    ref_ab = [c for c in refute if TIER[INDEX.docs[c.doc_idx].source_type] <= 2]

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
        context_type = "MIESZANE" if any(INDEX.docs[c.doc_idx].verdict == "mixed" for c in misleading) else "WYBIORCZOSC_LUB_KONTEKST"
        rules.append("R4:WPROWADZAJACE_W_BLAD(fact-check)")
    # ---- R5: confirmed
    elif sup_ab and not ref_ab:
        verdict, decisive = "potwierdzone", sup_ab
        rules.append("R5:POTWIERDZONE")
    if unverif and verdict == "brak_dowodow":
        reasons.append("FACTCHECK_NIEWERYFIKOWALNE")

    if decisive:
        # the source about THIS claim, not only a similar one: primary/official first, then the most concrete
        # details of the claim it shares (who, where, kind of event and of material, year), then the strongest match
        main = max(decisive, key=lambda c: (TIER[INDEX.docs[c.doc_idx].source_type] == 1,
                                            _specificity(claim.query, c), _score(c)))
        d = INDEX.docs[main.doc_idx]
        age = INDEX.doc_age(d)
        if main.archival and verdict == "falszywe":  # R3a
            rules.append("R3a:STARY_MATERIAL")
            context_type = "FALSZYWY_KONTEKST"
            missing_context = (f"Materiał pochodzi z {main.archival[0]} r., a twierdzenie przedstawia go jako z "
                               f"{main.archival[1]} r. (źródło: {d.publisher}).")
        # R4 (archival context): supported, but presented as current while the evidence is old
        if verdict == "potwierdzone" and time_sensitive and age is not None and age > settings.stale_days:
            verdict, context_type = "wprowadzajace_w_blad", "NIEAKTUALNE"
            missing_context = (f"Opisane zdarzenie/dane pochodzą z {_fmt_date(d.published_at)}, a treść przedstawia je "
                               "jako bieżące.")
            rules.append("R4:WPROWADZAJACE_W_BLAD(NIEAKTUALNE)")

    # ---- premises (shown as the "Dlaczego taki wynik?" checklist)
    groups = _groups(decisive)
    tiers = _tiers(decisive)
    if main is not None:
        d = INDEX.docs[main.doc_idx]
        if main.archival:
            premises.append(Premise(label="Data materiału według analizy fact-checkingowej (reguła deterministyczna)",
                                    value=f"materiał pochodzi z {main.archival[0]} r., a twierdzenie przedstawia go "
                                          f"jako z {main.archival[1]} r.", effect="+"))
        elif main.numeric:
            premises.append(Premise(label="Porównanie liczb ze źródłem urzędowym (reguła deterministyczna)",
                                    value=("liczba z twierdzenia zgadza się z danymi źródła" if main.numeric == "zgodne"
                                           else "liczba z twierdzenia NIE zgadza się z danymi źródła za ten sam okres"),
                                    effect="+"))
        elif main.nli is not None:
            premises.append(Premise(label="Zgodność fragmentu z twierdzeniem (model NLI)",
                                    value=f"fragment {'przeczy' if main in refute else 'potwierdza'} twierdzeniu "
                                          f"(ocena modelu {_score(main):.2f}, próg {settings.nli_strong})", effect="+"))
        else:
            premises.append(Premise(label="Dopasowanie do twierdzenia już sprawdzonego",
                                    value=f"podobieństwo {main.claim_cos:.2f} do twierdzenia ocenionego przez {d.publisher} "
                                          f"jako „{d.verdict_raw}”" + (" — Twoje zdanie jest jego zaprzeczeniem"
                                                                      if main.nli_claim and main.nli_claim.contra >= 0.8 else
                                                                      f"; model NLI: Twoja treść zawiera to twierdzenie ({main.nli_claim.entail:.2f})"
                                                                      if main.nli_claim else ""),
                                    effect="+"))
        premises.append(Premise(label="Źródło pierwotne / urzędowe", value="tak" if 1 in tiers else "nie",
                                effect="+" if 1 in tiers else "0"))
        premises.append(Premise(label="Niezależne potwierdzenia (wydawcy)", value=f"{len(groups)}: {', '.join(sorted(groups))}",
                                effect="+" if len(groups) > 1 else "0"))
        age = INDEX.doc_age(d)
        stale = time_sensitive and age is not None and age > settings.stale_days
        premises.append(Premise(label="Najnowszy dowód", value=f"{_fmt_date(d.published_at)}" + (f" ({age} dni temu)" if age is not None else ""),
                                effect="-" if stale or age is None else "0"))
    premises.append(Premise(label="Sprzeczne źródła", value="tak" if conflicting else "nie", effect="-" if conflicting else "0"))

    # ---- strength of the basis (text, derived from premises)
    if verdict in ("falszywe", "potwierdzone", "wprowadzajace_w_blad"):
        strong = (1 in tiers and len(groups) >= 2) or (len(groups) >= 2 and max(_score(c) for c in decisive) >= 0.85)
        strength_label = "mocna" if strong and not conflicting else "umiarkowana"
        strength = 0.85 if strength_label == "mocna" else 0.6
        # stricter rule for high-risk topics: a single tier-B group is not enough to stand alone
        if high_risk and 1 not in tiers and len(groups) < 2:
            rules.append("HR:JEDNO_ZRODLO_ESKALACJA")
            limitations.append("Temat wysokiego ryzyka, a ocena opiera się na jednym źródle — zalecamy sprawdzenie "
                               "komunikatów właściwych instytucji; sprawa trafia do analityka.")
    else:
        strength_label, strength = "niewystarczająca", 0.0
        if not reasons:
            reasons.append("BRAK_MATERIALOW" if not evidence else "TYLKO_MATERIALY_POKREWNE")
        rules.append("R6:BRAK_DOWODOW")

    order = {"przeczy": 0, "popiera": 0, "kontekst": 1, "neutralne": 2}
    evidence.sort(key=lambda e: (order[e.stance], e.doc_id not in keep, e.tier, -e.similarity))
    evidence = evidence[: settings.top_k_evidence]
    limitations.append("Odpowiedź opiera się wyłącznie na jawnym katalogu źródeł (zob. „Źródła”); brak wyniku nie oznacza, "
                       "że informacja jest prawdziwa lub fałszywa.")
    explanation, unknown = _explain(verdict, main, evidence, conflicting, missing_context)
    return ClaimResult(
        claim=claim.text, kind=claim.kind, verdict=verdict, verdict_label=VERDICT_LABEL_PL[verdict], strength=strength,
        strength_label=strength_label, premises=premises, explanation=explanation, missing_context=missing_context,
        conflicting=conflicting, what_unknown=unknown, evidence=evidence, limitations=limitations, rules_fired=rules,
        reason_codes=reasons, context_type=context_type, high_risk=high_risk,
        would_settle=_would_settle(claim.text) if verdict == "brak_dowodow" else None)


def _explain(verdict: str, main: _Cand | None, evidence: list[Evidence], conflicting: bool,
             missing_context: str | None) -> tuple[str, str | None]:
    """Deterministic plain-Polish explanation ('truth sandwich' order: fact -> what was claimed -> source)."""
    if verdict == "brak_dowodow":
        if conflicting:
            return ("Wiarygodne źródła podają w tej sprawie różne informacje, więc nie wydajemy werdyktu. Poniżej "
                    "pokazujemy obie strony — porównaj ich daty i zakres.",
                    "Nie da się rozstrzygnąć, które źródło opisuje stan aktualny lub pełniejszy.")
        txt = ("Nie znaleźliśmy w naszym katalogu źródeł wystarczających materiałów, by potwierdzić albo obalić tę "
               "informację. To nie znaczy, że jest prawdziwa, ani że jest fałszywa.")
        related = [e for e in evidence if e.stance == "kontekst"][:2]
        if related:
            txt += " Znaleźliśmy tylko materiały na pokrewny temat: " + "; ".join(
                f"„{short(e.title, 90)}” ({e.publisher})" for e in related) + "."
        return txt, ("Brak źródła pierwotnego (np. komunikatu urzędu, aktu prawnego, danych) i brak analizy "
                     "fact-checkingowej dotyczącej dokładnie tego twierdzenia.")
    d = INDEX.docs[main.doc_idx]
    who, when = d.publisher, _fmt_date(d.published_at)
    lead = {"falszywe": "Źródła przeczą tej informacji.",
            "potwierdzone": "Źródła potwierdzają tę informację.",
            "wprowadzajace_w_blad": "Ta informacja wprowadza w błąd."}[verdict]
    if main.archival:
        body = f" Według źródła: {who} ({when})."
    elif main.nli is None and d.verdict_raw:
        body = (f" {who} ({when}) sprawdził bardzo podobne twierdzenie: „{short(d.claim or d.title, 160)}” i ocenił je "
                f"jako „{d.verdict_raw}”.")
        if main.nli_claim is not None and main.nli_claim.contra >= 0.8:
            body += " Twoje zdanie mówi coś przeciwnego niż to sprawdzone twierdzenie."
        if d.verdict == "mixed":
            body += " Część twierdzenia jest prawdziwa, ale całość daje mylny obraz."
    else:
        body = f" Według źródła: {who} ({when})."
    body += f" Fragment źródła: „{short(main.fragment, 260)}”"
    if missing_context:
        body += f" Brakujący kontekst: {missing_context}"
    return lead + body, None
