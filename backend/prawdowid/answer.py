"""Short answers in the style of the organizers' examples — deterministic, no LLM.

Pattern (rules/Czy we Włoszech…docx): the first words give the answer ("Nie." / "Tak." / "Częściowo…" /
"Nie udało mi się tego potwierdzić."), then 1–2 sentences on WHO checked WHAT, then one link (the decisive source,
`ClaimResult.main_evidence`). For "no evidence" we say what would settle it and that a missing result is not proof.

Every sentence is assembled from fields that already exist in the result (verdict, the decisive evidence item, its
`factcheck_verdict_raw` / `factcheck_claim` / verbatim `fragment`, `missing_context`, the abstain reason). Nothing is
added that is not in the evidence; the web page, the chat channels and the extension all show this same text.
"""
from __future__ import annotations

import re

from .schemas import CheckResult, ClaimResult, Evidence
from .textutil import asks_who_checked, short, tokens

FC_LABEL = {"false": "fałsz", "true": "prawda", "misleading": "wprowadzające w błąd", "mixed": "częściowa prawda",
            "unverifiable": "nieweryfikowalne"}
REASON = {"BRAK_MATERIALOW": "brak materiałów na ten temat w katalogu źródeł",
          "TYLKO_MATERIALY_POKREWNE": "są tylko materiały na pokrewny temat",
          "ZRODLA_SPRZECZNE": "źródła są ze sobą sprzeczne",
          "FACTCHECK_NIEWERYFIKOWALNE": "fact-checkerzy uznali to za nieweryfikowalne",
          "NIEAKTUALNE_DOWODY": "dowody są nieaktualne",
          "ROZNE_DEFINICJE": "wynik zależy od przyjętej miary wskaźnika"}

# Per-topic "what would settle it" hints, more specific than the engine's generic one. Keyed to a TOPIC (any claim
# about transport tickets, clean-transport zones, weather, scams, travel, municipal decisions), never to a test case.
SETTLE = [
    (re.compile(r"\b(diesl\w*|stref\w* czyst\w*|zakaz\w* wjazd\w*|wjazd\w* do centrum|sct\b)", re.I),
     "oficjalna uchwała gminy określająca granice strefy i datę wejścia przepisów w życie"),
    (re.compile(r"\b(bilet\w*|autobus\w*|tramwaj\w*|komunikacj\w*|mpk|ztm|metr[oa]\b|przejazd\w*|jeźdz\w*|jeździ\w*)", re.I),
     "komunikat lokalnego organizatora transportu albo aktualny regulamin sprzedaży biletów"),
    (re.compile(r"\b(pogod\w*|burz\w*|upał\w*|ulew\w*|powód\w*|powodz\w*|wichur\w*|ostrzeżeni\w* meteo\w*)", re.I),
     "aktualne ostrzeżenie IMGW lub komunikat Rządowego Centrum Bezpieczeństwa"),
    (re.compile(r"\b(sms\w*|oszust\w*|wyłudz\w*|phishing\w*|hak\w*|cyber\w*|wyciek\w*)", re.I),
     "komunikat CERT Polska, banku lub instytucji, pod którą ktoś się podszywa"),
    (re.compile(r"\b(podróż\w*|wyjazd\w*|wiz[aąy]\b|paszport\w*|ambasad\w*|konsulat\w*|strajk\w*)", re.I),
     "komunikat MSZ dla podróżujących (Odyseusz) lub oficjalne źródło danego kraju"),
    (re.compile(r"\b(gmin\w*|burmistrz\w*|wójt\w*|starost\w*|ratusz\w*|rad\w* miasta|urząd miasta|urzęd\w* gminy)", re.I),
     "komunikat lub uchwała właściwego urzędu gminy albo miasta"),
]


# ------------------------------------------------------------------ Polish agreement without a dictionary
def _gender(publisher: str) -> str:
    """Grammatical gender of a publisher name from its first word (Demagog → m, Stowarzyszenie Pravda → n,
    Państwowa Komisja Wyborcza → f). Good enough for institution names; used only to agree a past-tense verb."""
    w = re.sub(r"[^\wąćęłńóśźż]", "", (publisher.split() or [""])[0].lower())
    if w.endswith("a"):
        return "f"
    if w.endswith(("o", "e", "um")):
        return "n"
    return "m"


def _past(publisher: str, verb_m: str) -> str:
    return verb_m + {"m": "", "f": "a", "n": "o"}[_gender(publisher)]


def _q(s: str | None, n: int = 150) -> str:
    """Quote-safe shortening: no trailing period or quotes inside the Polish quotation marks."""
    s = short(re.sub(r"\s+", " ", s or "").strip(), n)
    return s.strip(" „”\"'").rstrip(".;:,")


def _clause(fragment: str) -> str:
    """Verbatim leading clause of a quoted fragment (up to the first '; ' or sentence end) — keeps the quote exact."""
    return re.split(r";\s|\.\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ])", fragment or "", maxsplit=1)[0]


def _plural(n: int, one: str, few: str, many: str) -> str:
    if n == 1:
        return one
    return few if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else many


def _fc_label(e: Evidence) -> str:
    raw = (e.factcheck_verdict_raw or "").strip()
    if raw and len(raw) <= 32:
        return raw
    return FC_LABEL.get(e.factcheck_verdict or "", raw[:32] or "oceniono")


# ------------------------------------------------------------------ which evidence item is "the" source
def _decisive(c: ClaimResult) -> list[int]:
    ev = c.evidence
    if c.verdict == "falszywe":
        return [i for i, e in enumerate(ev) if e.stance == "przeczy"]
    if c.verdict == "potwierdzone":
        return [i for i, e in enumerate(ev) if e.stance == "popiera"]
    if c.verdict == "wprowadzajace_w_blad":
        fc = [i for i, e in enumerate(ev) if e.factcheck_verdict in ("misleading", "mixed") and e.same_claim is True]
        return fc or [i for i, e in enumerate(ev) if e.stance == "popiera"]  # archival-context case (R4 NIEAKTUALNE)
    return []


def main_evidence(c: ClaimResult) -> int | None:
    """The decisive source the engine based the verdict on: primary/official first, then the strongest match
    (mirrors engine._decide: max(decisive, key=(tier == 1, score)))."""
    idx = _decisive(c)
    if not idx:
        return None
    return max(idx, key=lambda i: (c.evidence[i].tier == 1, c.evidence[i].stance_score))


# ------------------------------------------------------------------ per-claim short answer
def _who_checked(e: Evidence) -> str:
    """'Demagog ocenił twierdzenie „…” jako „Fałsz”.' — only from fields of the evidence item."""
    pub = e.publisher
    checked = _q(e.factcheck_claim or e.title, 150)
    opposite = "odwrotne " if e.same_claim is False else ""
    if e.source_type == "incident":
        return f"{pub} {_past(pub, 'opisał')} {'odwrotny ' if e.same_claim is False else ''}przekaz „{checked}” jako dezinformację."
    return f"{pub} {_past(pub, 'ocenił')} {opposite}twierdzenie „{checked}” jako „{_fc_label(e)}”."


def _checked_answer(c: ClaimResult, e: Evidence) -> str | None:
    """'Czy Demagog sprawdzał, czy X?' asks WHETHER it was checked: the answer is 'Tak, Demagog to sprawdził i ocenił…',
    not 'Nie.' (which would read as 'no, it did not check'). When the user named another checker than the one that
    rated the claim, we say who did check it instead of claiming the named one did."""
    who = asks_who_checked(c.claim)
    if who is None or e.source_type not in ("factcheck", "incident") or not e.factcheck_verdict_raw:
        return None
    pub = e.publisher
    rated = _who_checked(e).split(" ", len(pub.split()))[-1]  # "ocenił twierdzenie „…” jako „…”."
    named = {t for t in tokens(who) if len(t) >= 4}
    if not named or named & set(tokens(pub)) or re.search(r"\b(ktoś|ktos|fact|weryfik|sprawdz)", who, re.I):
        return f"Tak, {pub} to {_past(pub, 'sprawdził')} i {rated}"
    return f"Sprawdził{'a' if _gender(pub) == 'f' else 'o' if _gender(pub) == 'n' else ''} to {pub}: {rated}"


_ALTERNATIONS = (("sz", "ch"), ("cz", "c"), ("rz", "r"))  # Włochy / we Włoszech (same idea as engine._alt_stems)


def _topic_stems(s: str, drop: set[str], min_len: int = 4) -> set[str]:
    out = set()
    for t in tokens(s, stem=12):
        if t[0].isdigit() or len(t) < min_len:
            continue
        for a, b in _ALTERNATIONS:
            t = t.replace(a, b)
        if t[:5] not in drop:
            out.add(t[:5])
    return out


_NAME = re.compile(r"(?<=[\s(„\"])[A-ZĄĆĘŁŃÓŚŹŻ][\wąćęłńóśźż-]{2,}")  # capitalised, not sentence-initial


def _related(c: ClaimResult) -> Evidence | None:
    """Closest context item for an abstention, shown as 'related material' only when it is about the same subject:
    it must contain a proper name of the claim (place, person, institution; publisher names excluded) — or, for a
    claim without names, share at least three topic words. A similar-sounding article on another subject is never
    quoted (then the 'what would settle it' hint is shown instead)."""
    best = None
    for e in c.evidence:
        if e.stance != "kontekst" or e.similarity < 0.72 or not e.fragment:
            continue
        drop = _topic_stems(e.publisher, set(), 3)
        names = _topic_stems(" ".join(_NAME.findall(f" {c.claim}")), drop, 3)
        text = f"{e.title} {e.factcheck_claim or ''} {e.fragment}"
        shared = _topic_stems(c.claim, drop) & _topic_stems(text, drop)
        if names:
            if not names & _topic_stems(text, drop, 3) or len(shared | (names & _topic_stems(text, drop, 3))) < 2:
                continue
        elif len(shared) < 3:
            continue
        key = (len(shared), e.tier == 1, e.similarity)
        if best is None or key > best[0]:
            best = (key, e)
    return best[1] if best else None


def _related_sentence(e: Evidence) -> str:
    if e.source_type in ("factcheck", "incident") and e.factcheck_verdict_raw:
        return f"Najbliższy materiał: {_who_checked(e).rstrip('.')} — sprawdź w pełnej analizie, czy dotyczy tego samego."
    d = (e.published_at or "")[:10]
    when = f" ({d[8:10]}.{d[5:7]}.{d[:4]})" if re.fullmatch(r"\d{4}-\d\d-\d\d", d) else ""
    return (f"Znalazłem tylko materiał pokrewny — {e.publisher}{when}: „{_q(_clause(e.fragment), 170)}”. "
            "Nie rozstrzyga on samego twierdzenia.")


def _live(res: CheckResult | None) -> str:
    """Status of the live web-search stage (websearch.py): '' (did not run) | ok | brak_wynikow | blad."""
    ls = getattr(res, "live_search", None) if res is not None else None
    return str(getattr(ls, "status", "") or "") if ls is not None else ""


def short_answer(c: ClaimResult, live: str = "") -> str:
    v = c.verdict
    if v == "nie_podlega_weryfikacji":
        what = ("To przewidywanie dotyczące przyszłości — nie da się go dziś potwierdzić ani obalić."
                if c.kind == "prognoza" else "To opinia, a nie twierdzenie o faktach — nie da się jej potwierdzić ani obalić.")
        return what + " Mogę sprawdzić konkretne fakty, na których się opiera (liczby, daty, decyzje) — wpisz je osobno."

    if v == "brak_dowodow":
        if c.conflicting:
            pubs = list(dict.fromkeys(e.publisher for e in c.evidence if e.stance in ("popiera", "przeczy")))[:2]
            who = f" ({' i '.join(pubs)})" if pubs else ""
            return (f"Nie udało mi się tego rozstrzygnąć. Wiarygodne źródła{who} podają w tej sprawie różne informacje — "
                    "porównaj ich daty i zakres.")
        unv = next((e for e in c.evidence if e.factcheck_verdict == "unverifiable"), None)
        if unv is not None and "FACTCHECK_NIEWERYFIKOWALNE" in c.reason_codes:
            return (f"Nie udało mi się tego potwierdzić. {unv.publisher} {_past(unv.publisher, 'uznał')} podobne "
                    f"twierdzenie „{_q(unv.factcheck_claim or unv.title, 140)}” za niemożliwe do zweryfikowania.")
        if "ROZNE_DEFINICJE" in c.reason_codes:
            return ("Nie udało mi się tego jednoznacznie potwierdzić. Wynik zależy od przyjętej miary wskaźnika, "
                    "a twierdzenie nie mówi, o którą chodzi.")
        txt = "Nie udało mi się tego potwierdzić."
        if live == "blad":  # scenario J: a failed search is reported as such, never as "there is no such article"
            txt = ("Nie udało mi się tego potwierdzić w lokalnej bazie, a zaufanych stron w internecie nie mogę teraz "
                   "przeszukać z powodu błędu dostępu.")
        rel = _related(c)
        if rel is not None:  # say what the closest material does say, without turning it into a verdict
            txt += " " + _related_sentence(rel)
        elif c.would_settle:
            txt += f" Potrzebne byłoby źródło, np. {c.would_settle.rstrip('.')}."
        return txt + " Brak wyniku w bazie nie oznacza, że to nieprawda."

    i = c.main_evidence if c.main_evidence is not None else main_evidence(c)
    e = c.evidence[i] if i is not None and i < len(c.evidence) else None
    if e is None:  # defensive: verdict without a decisive item should not happen — fall back to the explanation
        return short(c.explanation, 300)

    checked = _checked_answer(c, e)
    if checked:
        return checked
    if v == "wprowadzajace_w_blad":
        if c.context_type == "NIEAKTUALNE" and c.missing_context:
            return f"Częściowo. {c.missing_context.rstrip('.')} (źródło: {e.publisher})."
        opener = "Częściowo." if e.factcheck_verdict == "mixed" else "Częściowo, ale całość wprowadza w błąd."
        return f"{opener} {_who_checked(e)}"

    opener = "Nie." if v == "falszywe" else "Tak."
    if e.factcheck_verdict_raw and e.source_type in ("factcheck", "incident"):
        txt = f"{opener} {_who_checked(e)}"
        if e.same_claim is False:
            txt += " Twoje zdanie mówi coś przeciwnego."
    else:  # primary / official source: quote the verbatim fragment that decided it
        rel = "Przeczy temu" if v == "falszywe" else "Potwierdza to"
        txt = f"{opener} {rel} {e.publisher}: „{_q(_clause(e.fragment), 170)}”."
        if v == "falszywe" and any(p.label.startswith("Porównanie liczb") for p in c.premises):
            txt += " Liczba w twierdzeniu nie zgadza się z danymi źródła za ten sam okres."
    if v == "potwierdzone" and c.missing_context:
        txt += " Wynik zależy jednak od przyjętej miary wskaźnika."
    return txt


# ------------------------------------------------------------------ one-line strength + limitation
def basis_line(c: ClaimResult) -> str:
    if c.verdict == "nie_podlega_weryfikacji":
        return "Podstawa: nie dotyczy — to nie jest twierdzenie o faktach."
    if c.verdict == "brak_dowodow":
        why = "; ".join(REASON.get(r, r) for r in c.reason_codes) or REASON["BRAK_MATERIALOW"]
        return f"Podstawa: niewystarczająca — {why}."
    dec = [c.evidence[i] for i in _decisive(c)]
    pubs = list(dict.fromkeys(re.sub(r"\s*\([^)]*\)", "", e.publisher) for e in dec))
    n = len(pubs) or 1
    kinds = {e.source_type for e in dec}
    names = ", ".join(short(p, 40) for p in pubs[:2]) + (" i in." if len(pubs) > 2 else "")
    count = f"{n} {'niezależne ' if n > 1 else ''}{_plural(n, 'źródło', 'źródła', 'źródeł')}"
    if n > 1 and "official" in kinds:
        count += ", w tym urzędowe"
    kind = {"official": "urzędowe", "factcheck": "fact-checking", "incident": "baza incydentów"}.get(
        next(iter(kinds)), "") if len(kinds) == 1 else ""
    return f"Podstawa: {c.strength_label} — {count} ({kind + ': ' if kind and n == 1 else ''}{names})."


def limitation_line(c: ClaimResult, live: str = "") -> str:
    if c.verdict == "nie_podlega_weryfikacji":
        return "Ograniczenie: rozpoznanie opinii opiera się na sygnałach językowych i może się mylić."
    if c.verdict == "brak_dowodow":
        if c.conflicting:
            return "Ograniczenie: źródła mogą dotyczyć różnych okresów lub definicji — porównaj je w pełnej analizie."
        if live == "blad":
            return "Ograniczenie: wyszukiwanie na zaufanych stronach było niedostępne (błąd techniczny) — sprawdzono tylko lokalną bazę."
        if live in ("brak_wynikow", "ok"):
            return "Ograniczenie: przeszukano katalog źródeł i wybrane zaufane strony w internecie — mogło w nich zabraknąć tej sprawy."
        return "Ograniczenie: przeszukano tylko katalog zaufanych źródeł — mogło w nim zabraknąć tej sprawy."
    if "HR:JEDNO_ZRODLO_ESKALACJA" in c.rules_fired:
        return "Ograniczenie: temat wysokiego ryzyka, a ocena opiera się na jednym źródle — sprawa trafia do analityka."
    i = c.main_evidence
    e = c.evidence[i] if i is not None and i < len(c.evidence) else None
    pubs = {c.evidence[j].publisher for j in _decisive(c)}
    if e is not None and e.factcheck_claim and e.similarity < 0.9:
        return "Ograniczenie: źródło sprawdzało bardzo podobne, a nie identyczne twierdzenie."
    if c.context_type == "NIEAKTUALNE":
        return "Ograniczenie: dowód pochodzi sprzed ponad roku — sytuacja mogła się od tego czasu zmienić."
    if c.missing_context:  # definitional note (CPI vs HICP …) — the answer already says it depends on the measure
        return "Ograniczenie: twierdzenie nie mówi, o którą miarę wskaźnika chodzi — szczegóły w pełnej analizie."
    if len(pubs) <= 1:
        return "Ograniczenie: ocena opiera się na jednym źródle."
    if e is not None and e.age_days is not None and e.age_days > 365:
        return "Ograniczenie: najnowszy dowód ma ponad rok."
    return "Ograniczenie: wynik odzwierciedla stan źródeł z dnia sprawdzenia."


# ------------------------------------------------------------------ whole result
def _gist(s: str) -> str:
    """First sentence; plus the next one when the first is just 'Tak.' / 'Nie.' / 'Częściowo.'."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ])", s)
    return " ".join(parts[:2]) if len(parts) > 1 and len(parts[0]) < 15 else parts[0]


def result_short_answer(res: CheckResult) -> str:
    if res.status != "ok":
        if res.status == "blad_techniczny":
            return res.status_message or "Nie mogę teraz tego sprawdzić z powodu błędu technicznego. To nie jest ocena treści."
        return res.status_message or ""
    if not res.claims:
        return ""
    if len(res.claims) == 1:
        return res.claims[0].short_answer
    n = len(res.claims)
    parts = [f"„{_q(c.claim, 70)}” — {_gist(c.short_answer)}" for c in res.claims]
    return f"Sprawdziłem {n} {_plural(n, 'twierdzenie', 'twierdzenia', 'twierdzeń')}: " + " ".join(
        f"{k}) {p}" for k, p in enumerate(parts, 1))


def finalize(res: CheckResult) -> None:
    """Fill short_answer / basis_line / limitation_line / main_evidence on every claim and on the result."""
    live = _live(res)
    for c in res.claims:
        if c.verdict == "brak_dowodow":
            for rx, hint in SETTLE:
                if rx.search(c.claim):
                    c.would_settle = hint
                    break
        c.main_evidence = main_evidence(c)
        c.short_answer = short_answer(c, live)
        c.basis_line = basis_line(c)
        c.limitation_line = limitation_line(c, live)
    res.short_answer = result_short_answer(res)
