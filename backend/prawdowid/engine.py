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

from .claims import Claim
from .config import settings
from .index import INDEX, TIER, TIER_LABEL
from .nli import NLI_MODEL, NLIScore
from .schemas import VERDICT_LABEL_PL, ClaimResult, Evidence, Premise
from .textutil import is_time_sensitive, normalize_ws, short, split_sentences, tokens

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
    definitional: bool = False  # number differs, but the card uses a measure the claim did not name


def _fmt_date(s: str | None) -> str:
    if not s:
        return "brak daty"
    y, m, d = (s[:10].split("-") + ["", ""])[:3]
    return f"{d}.{m}.{y}" if d else s


def _best_fragment(doc_idx: int, q_emb: np.ndarray, q_tokens: set[str]) -> tuple[str, float]:
    """Pick the quoted fragment WITHOUT re-encoding: best verbatim chunk of the document by (cached) embedding
    similarity, then the 1–2 consecutive sentences with the highest lexical overlap with the claim.
    This exact span is both quoted to the user and judged by NLI."""
    ids = [i for i in INDEX.doc_chunks[doc_idx] if i not in INDEX.synthetic]
    d = INDEX.docs[doc_idx]
    if not ids:
        return (d.text or d.title)[:400], 0.0
    sims = INDEX.chunk_emb[ids] @ q_emb
    j = int(np.argmax(sims))
    text, cos = INDEX.chunks[ids[j]].text, float(sims[j])
    sents = [x for x in split_sentences(text) if len(x) > 15] or [text]
    windows = [w for w in sents + [f"{a} {b}" for a, b in zip(sents, sents[1:])] if len(w) <= 520] or [sents[0][:520]]

    def score(w: str) -> float:
        wt = set(tokens(w))
        return len(q_tokens & wt) / max(1, len(q_tokens)) - len(w) / 5000  # prefer shorter on ties

    return max(windows, key=score), cos


def _relevance(q_tokens: set[str], text: str) -> float:
    """Validity gate V4: share of the claim's content words present in the source fragment/title."""
    return len(q_tokens & set(tokens(text))) / max(1, len(q_tokens))


def _quote_ok(fragment: str, doc_text: str) -> bool:
    """Validity gate V2: the quoted fragment must be a verbatim substring of the stored source text."""
    squash = lambda s: re.sub(r"\s+", " ", normalize_ws(s)).strip()  # noqa: E731
    return squash(fragment) in squash(doc_text)


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


def _date_keys(s: str) -> tuple[set[str], set[int]]:
    low = s.lower()
    years = {y for y in re.findall(r"\b(20\d\d)\b", low)}
    months = {i + 1 for i, m in enumerate(_MONTHS) if re.search(rf"\b({m})\w*", low)}
    months |= {int(m) for _, m in re.findall(r"\b(20\d\d)-(\d\d)\b", low)}
    return years, months


_MEASURES = [  # (source marker, words that must appear in the claim for the comparison to be meaningful)
    (re.compile(r"\bHICP\b"), re.compile(r"hicp|eurostat|zharmonizowan", re.I)),
    (re.compile(r"\bCPI\b"), re.compile(r"\bcpi\b|gus|inflacj(?!.*hicp)", re.I)),
    (re.compile(r"\bEUR\b"), re.compile(r"euro|\beur\b", re.I)),
    (re.compile(r"\bUSD\b"), re.compile(r"dolar|\busd\b", re.I)),
    (re.compile(r"\bCHF\b"), re.compile(r"frank|\bchf\b", re.I)),
    (re.compile(r"\bGBP\b"), re.compile(r"funt|\bgbp\b", re.I)),
]


def _compatible(claim: str, source_title: str) -> bool:
    if re.search(r"hicp", claim, re.I) and re.search(r"\bCPI\b", source_title):
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


_CURR_NAMES = {"EUR": "euro", "USD": "dolar", "CHF": "frank", "GBP": "funt", "NOK": "koron", "SEK": "koron", "DKK": "koron",
               "CZK": "koron", "JPY": "jen", "HUF": "forint", "UAH": "hrywn", "CNY": "juan", "CAD": "dolar kanad",
               "AUD": "dolar austral"}
_ACT = re.compile(r"^(Ustawa|Rozporządzenie|Dyrektywa|Decyzja|Konstytucja|Uchwała)\b", re.I)
_QUALIFIED = [  # measures whose value depends on the definition; a mismatch is only meaningful if the claim names it
    (re.compile(r"\bCPI\b"), re.compile(r"\bcpi\b|\bgus\b", re.I)),
    (re.compile(r"\bHICP\b"), re.compile(r"hicp|eurostat|zharmonizowan", re.I)),
    (re.compile(r"rejestrowan", re.I), re.compile(r"rejestrowan|\bgus\b|urzęd\w* pracy", re.I)),
    (re.compile(r"\b(BAEL|LFS)\b|Eurostat", re.I), re.compile(r"bael|lfs|eurostat", re.I)),
]


_ALT = {"CPI": r"\bHICP\b", "HICP": r"\bCPI\b", "rejestrowan": r"\b(BAEL|LFS)\b|bezroboci\w* .*Eurostat|Eurostat.*bezroboci"}


def _competing_measure(claim: str, title: str) -> bool:
    """Does the claimed number match ANOTHER official card for the same period that measures the same thing with a
    different definition (CPI vs HICP, registered vs LFS unemployment)? Then the mismatch is definitional, not false.
    If the number matches no definition at all, it stays 'niezgodne'."""
    for key, alt in _ALT.items():
        if re.search(key, title, re.I):
            rx = re.compile(alt, re.I)
            return any(d.source_type == "official" and rx.search(d.title) and same_subject(claim, d.title)
                       and numeric_stance(claim, f"{d.title}. {_anchor_text(claim, d)}") == "zgodne"
                       for d in INDEX.docs)
    return False


def measure_named(claim: str, title: str) -> bool:
    """False if the card measures something definition-dependent (CPI vs HICP, registered vs LFS unemployment)
    and the claim does not say which measure it means."""
    return all(rx_c.search(claim) for rx_t, rx_c in _QUALIFIED if rx_t.search(title))


def same_subject(claim: str, title: str) -> bool:
    """Gate for structured official cards: a card about another period, currency or legal act is IRRELEVANT
    to the claim (not contradicting it)."""
    if _ACT.search(title):
        nums = re.findall(r"\b(\d{4}/\d{1,5})\b", claim)
        if nums:
            return any(n in title for n in nums)
        m = re.search(r"\b(?:o|w sprawie)\s+(.+)$", title)
        subject = set(tokens(m.group(1), stem=5)) if m else set(tokens(title, stem=5))
        return len(subject & set(tokens(claim, stem=5))) / max(1, len(subject)) >= 0.4
    head = re.split(r"[:—–]\s*\d", title)[0]  # e.g. "Ceny — transport — wrzesień 2026" / "Inflacja CPI w Polsce — marzec 2026"
    subj = _anchors(re.sub(r"\b(19|20)\d\d(-\d\d)?(-\d\d)?\b", " ", head)) - {t for t in tokens(" ".join(_PL_MONTHS))}
    subj = {t for t in subj if not any(t.startswith(m[:4]) for m in _MONTHS_STEMS)}
    if subj and not (subj & set(tokens(claim))) and not re.search(r"\b[A-Z]{3}/PLN\b", title):
        return False  # the card is about another indicator (e.g. transport prices vs. headline inflation)
    cur = re.search(r"\b([A-Z]{3})/PLN\b", title)
    if cur:
        code = cur.group(1)
        if not (re.search(rf"\b{code}\b", claim, re.I) or (_CURR_NAMES.get(code) and _CURR_NAMES[code] in claim.lower())):
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
    if re.search(r"wesz\w* w życie|wchodzi w życie|wejdzie w życie|obowiązuje od|^\s*od\s+\d{1,2}\s+\w+\s+\d{4}", claim, re.I):
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


def numeric_stance(claim: str, source: str) -> str | None:
    """Deterministic check of a numeric claim against an official fact card. Applies only when the claim's year and
    month (if given) also appear in the source — otherwise we would compare different periods."""
    cn = _numbers(claim)
    if not cn:
        return None
    cy, cm = _date_keys(claim)
    sy, sm = _date_keys(source)
    if not cy or not cy <= sy or (cm and not cm <= sm):
        return None
    sn = _numbers(source)
    op = ">" if re.search(r"przekrocz\w*|ponad|powyżej|więcej niż|wyższ\w* niż", claim, re.I) else \
         "<" if re.search(r"poniżej|mniej niż|niższ\w* niż|nie przekrocz\w*", claim, re.I) else "="
    for v, u in cn:
        same_unit = [x for x, su in sn if su == u]
        if not same_unit:
            continue
        if op == "=":
            return "zgodne" if any(abs(x - v) <= max(0.051, abs(v) * 0.005) for x in same_unit) else "niezgodne"
        x = same_unit[0]  # the card's headline value comes first in the anchor sentence
        return "zgodne" if (x > v if op == ">" else x < v) else "niezgodne"
    return None


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
            cands[doc_idx] = _Cand(doc_idx, "", cos, cos, is_claim_match=True, claim_cos=cos)
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
    timings["fragments_ms"] = timings.get("fragments_ms", 0) + (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    pairs, owners = [], []
    for c in ranked:
        d = INDEX.docs[c.doc_idx]
        if c.is_claim_match and d.claim and c.claim_cos >= 0.78:
            pairs.append((claim.query, d.claim)); owners.append((c, "claim"))
            if c.claim_cos >= 0.85:  # reverse direction only needed for the negation test
                pairs.append((d.claim, claim.query)); owners.append((c, "claim_rev"))
        if d.source_type == "official" and not same_subject(claim.query, d.title):
            c.extra_irrelevant = True  # another period/currency/act — not evidence either way
            continue
        if d.source_type in ("official", "media") and _relevance(q_tokens, f"{d.title} {c.fragment}") >= 0.4:
            pairs.append((c.fragment, claim.query)); owners.append((c, "frag"))
    for (c, kind), s_ in zip(owners, NLI_MODEL.score(pairs)):
        setattr(c, {"claim": "nli_claim", "claim_rev": "nli_claim_rev", "frag": "nli"}[kind], s_)
    # deterministic checks override NLI for structured official cards (NLI is weak at numbers and dates)
    for c in ranked:
        d = INDEX.docs[c.doc_idx]
        if d.source_type != "official" or max(c.frag_cos, c.cos) < 0.65 or c.extra_irrelevant:
            continue
        num = None
        if _compatible(claim.query, d.title):
            num = numeric_stance(claim.query, f"{d.title}. {_anchor_text(claim.query, d)}")
            if num == "niezgodne" and not measure_named(claim.query, d.title) and _competing_measure(claim.query, d.title):
                num, c.definitional = None, True  # e.g. CPI vs HICP: different measure, not a contradiction
        num = num or legal_date_stance(claim.query, d.title, d.text)
        if num:
            c.numeric = num
            c.nli = NLIScore(0.95, 0.03, 0.02) if num == "zgodne" else NLIScore(0.02, 0.03, 0.95)
    timings["nli_ms"] = timings.get("nli_ms", 0) + (time.perf_counter() - t0) * 1000

    # ---- evidence validity gates + stance classification
    support, refute, misleading, unverif, evidence, definitional = [], [], [], [], [], []
    quote_failures = 0
    for c in ranked:
        d = INDEX.docs[c.doc_idx]
        if c.extra_irrelevant:
            continue
        if not _quote_ok(c.fragment, d.text or ""):
            quote_failures += 1  # V2 failed: never show a quote we cannot find verbatim in the source
            continue
        if d.source_type in ("factcheck", "incident"):
            nc, same = c.nli_claim, None
            if c.is_claim_match and nc is not None:
                rev = c.nli_claim_rev or nc
                lex = _relevance(set(tokens(d.claim or "")), claim.query)  # share of the checked claim's words used
                incident = d.source_type == "incident"
                if c.claim_cos >= 0.85 and min(nc.contra, rev.contra) >= 0.80:
                    same = False  # the user states the opposite of the checked claim (contradiction both ways)
                elif max(nc.contra, rev.contra) < 0.5 and (
                        (c.claim_cos >= 0.88 and not incident)  # near-paraphrase, no contradiction
                        or (c.claim_cos >= 0.86 and nc.entail >= (0.8 if incident else 0.5))  # user asserts it
                        or (not incident and c.claim_cos >= 0.80 and nc.entail >= 0.8 and lex >= 0.4)):
                    same = True
            mapped = FC_TO_VERDICT.get(d.verdict or "") if same is not None else None
            if mapped and same is False:
                mapped = {"falszywe": "potwierdzone", "potwierdzone": "falszywe"}.get(mapped)
            if mapped == "falszywe":
                refute.append(c); evidence.append(_evidence(c, "przeczy", c.claim_cos, same)); continue
            if mapped == "potwierdzone":
                support.append(c); evidence.append(_evidence(c, "popiera", c.claim_cos, same)); continue
            if mapped == "wprowadzajace_w_blad":
                misleading.append(c); evidence.append(_evidence(c, "kontekst", c.claim_cos, same)); continue
            if mapped == "brak_dowodow":
                unverif.append(c)
            if max(c.claim_cos, c.frag_cos) >= 0.70:
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
    res = _decide(claim, support, refute, misleading, unverif, evidence, high_risk)
    if definitional:
        d0 = INDEX.docs[definitional[0].doc_idx]
        note = (f"Wartość zależy od przyjętej miary: {d0.publisher} („{short(d0.title, 80)}”) podaje inną liczbę dla innej "
                "definicji wskaźnika. Twierdzenie nie mówi, o którą miarę chodzi.")
        res.premises.append(Premise(label="Różne definicje wskaźnika", value=note, effect="-"))
        if res.verdict == "potwierdzone":
            res.missing_context = note
        elif res.verdict == "brak_dowodow":
            res.reason_codes.append("ROZNE_DEFINICJE")
            res.what_unknown = note
    if quote_failures:
        res.limitations.append(f"Pominięto {quote_failures} materiał(y), których cytatu nie dało się dosłownie "
                               "odnaleźć w źródle (bramka V2).")
    return res


def _groups(cands: list[_Cand]) -> set[str]:
    """Independence groups: one per publisher (several articles of one publisher count once)."""
    return {INDEX.docs[c.doc_idx].publisher for c in cands}


def _tiers(cands: list[_Cand]) -> set[int]:
    return {TIER[INDEX.docs[c.doc_idx].source_type] for c in cands}


def _score(c: _Cand) -> float:
    if c.nli is not None:
        return max(c.nli.entail, c.nli.contra)
    return c.claim_cos


def _decide(claim: Claim, support, refute, misleading, unverif, evidence: list[Evidence], high_risk: bool) -> ClaimResult:
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
        main = max(decisive, key=lambda c: (TIER[INDEX.docs[c.doc_idx].source_type] == 1, _score(c)))
        d = INDEX.docs[main.doc_idx]
        age = INDEX.doc_age(d)
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
        if main.numeric:
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
    evidence.sort(key=lambda e: (order[e.stance], e.tier, -e.similarity))
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
    if main.nli is None and d.verdict_raw:
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
