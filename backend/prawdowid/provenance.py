"""Answer whether a linked item is the same material described by a fact-check.

Is the linked item the one a fact-checker analysed? ("Czy ten artykuł to ten sam tekst, który oceniał <checker>?
<link>" — the question type of the organisers' scenario I)

The question is about the identity of a material, not about the truth of a claim, so it is answered by comparing the
linked page with the fact-check records instead of by claim matching. Deterministic, no model:

  * headline — the page's headline occurs word for word (case, punctuation and quotation marks aside) in the text of a
    fact-check record: the analysis names the material it examined;
  * date — the page's own publication date is not later than the analysis and at most MAX_LAG_DAYS before it;
  * topic — implied by the headline: a similar topic, the same site or the same person are not enough.

All three agree -> "Tak, chodzi o ten sam materiał", with the verbatim passage of the analysis that names the headline
and both dates (rule M2). Otherwise no match is stated and the answer says what did not agree.

Reading guide: docs/backend/ENGINE.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import re
from datetime import date

from .index import INDEX, TIER
from .schemas import VERDICT_LABEL_PL, ClaimResult, Evidence, Premise
from .textutil import short, tokens

MAX_LAG_DAYS = (
    60  # a fact-check follows the material it examines; a page dated long before it is another item
)
MIN_HEADLINE_WORDS = 4  # "Strona główna", "Aktualności": too generic to identify a material

# "Czy ten wpis / artykuł / ta depesza … dotyczy tej samej / tego samego …": a question about the linked item itself
_ITEM = (
    r"(?:wpis\w*|artykuł\w*|artykul\w*|tekst\w*|post\w*|materiał\w*|material\w*|link\w*|stron\w*|depesz\w*|"
    r"nagrani\w*|film\w*|zdjęci\w*|wiadomoś\w*|news\w*|publikacj\w*|notk\w*)"
)
_SAME_ITEM = re.compile(
    rf"\b(?:ten|ta|to|tym|tej|tego|tę|tą)\s+{_ITEM}\b.*?\b(?:t(?:ej|ego|ą|ę|en|o|a)\s+sam\w*|to\s+samo|ten\s+sam\w*)\b"
    rf"|\b(?:t(?:ej|ego|ą|ę|en|o|a)\s+sam\w*)\s+{_ITEM}\b.*?\b(?:co|któr\w*)\b",
    re.I | re.S,
)

_MONTHS = [
    "stycznia",
    "lutego",
    "marca",
    "kwietnia",
    "maja",
    "czerwca",
    "lipca",
    "sierpnia",
    "września",
    "października",
    "listopada",
    "grudnia",
]


def asks_same_item(message: str) -> bool:
    return bool(_SAME_ITEM.search(re.sub(r"https?://\S+", " ", message or "")))


def _norm(s: str) -> str:
    return re.sub(r"[\W_]+", " ", (s or "").lower()).strip()


def _headlines(title: str) -> list[str]:
    """The page title and its longest segment ("Premier: … | PAP" -> "Premier: …"), longest first."""
    parts = [title] + [p for p in re.split(r"\s+[|–—-]\s+", title or "") if p != title]
    good = [p.strip() for p in parts if len(tokens(p)) >= MIN_HEADLINE_WORDS]
    return sorted(dict.fromkeys(good), key=len, reverse=True)


def _date(s: str | None) -> date | None:
    try:
        return date.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def _pl_date(d: date) -> str:
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year} r."


def _dmy(d: date) -> str:
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def _passage(text: str, headline: str) -> str | None:
    """Shortest verbatim window of the record text that contains the headline."""
    from .engine import _fragment_windows

    want = _norm(headline)
    hits = [
        w.lstrip("-–•* ") for w in _fragment_windows(text, text) if want in _norm(w)
    ]  # a bullet is not quoted
    return min(hits, key=len) if hits else None


def _evidence(d, fragment: str, stance: str) -> Evidence:
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
        fragment=fragment,
        factcheck_claim=d.claim,
        factcheck_verdict_raw=d.verdict_raw,
        factcheck_verdict=d.verdict,
        similarity=1.0,
        stance=stance,
        stance_score=1.0,
        same_claim=None,
        license=d.license,
    )


def find(meta: dict) -> list[tuple[object, str, str]]:
    """Fact-check records whose text contains the page headline: (doc, headline, verbatim passage)."""
    out = []
    for h in _headlines(meta.get("title") or ""):
        want = _norm(h)
        for d in INDEX.docs:
            if d.source_type not in ("factcheck", "incident") or want not in _norm(
                f"{d.title} {d.text}"
            ):
                continue
            passage = _passage(d.text or "", h)
            if passage and all(x[0] is not d for x in out):
                out.append((d, h, passage))
        if out:
            break
    return out


def check_linked_item(question: str, meta: dict) -> ClaimResult:
    title = (meta.get("title") or "").strip()
    page_day = _date(meta.get("date"))
    hits = find(meta)
    limitations = [
        "Dopasowanie porównuje nagłówek i datę strony z tekstem analiz w katalogu źródeł; nie porównuje "
        "całej treści ani nie ocenia samego wpisu."
    ]

    def abstain(
        why: str, premises: list[Premise], evidence: list[Evidence] | None = None
    ) -> ClaimResult:
        txt = (
            f"Nie udało mi się potwierdzić, że to ten materiał, który sprawdzali fact-checkerzy: {why} Podobny "
            "temat, ta sama osoba albo ta sama domena nie wystarczą do dopasowania."
        )
        return ClaimResult(
            claim=question,
            verdict="brak_dowodow",
            verdict_label=VERDICT_LABEL_PL["brak_dowodow"],
            strength=0.0,
            strength_label="niewystarczająca",
            premises=premises,
            rules_fired=["M2:BRAK_DOPASOWANIA_MATERIALU", "R6:BRAK_DOWODOW"],
            reason_codes=["BRAK_DOPASOWANIA_MATERIALU"],
            explanation=txt,
            evidence=evidence or [],
            limitations=limitations,
        )

    if not _headlines(title):
        return abstain(
            "strona nie ma nagłówka, po którym dałoby się ją rozpoznać.",
            [Premise(label="Nagłówek strony", value=title or "brak", effect="-")],
        )
    if not hits:
        return abstain(
            f"nagłówka ze strony („{short(title, 140)}”) nie ma w żadnej analizie w katalogu źródeł.",
            [Premise(label="Nagłówek strony w tekście analiz", value="nie występuje", effect="-")],
        )
    matched, mismatched = [], []
    for d, h, passage in hits:
        doc_day = _date(d.published_at)
        lag = (doc_day - page_day).days if doc_day and page_day else None
        (matched if lag is not None and 0 <= lag <= MAX_LAG_DAYS else mismatched).append(
            (d, h, passage, doc_day, lag)
        )
    if not matched:
        d, h, passage, doc_day, lag = mismatched[0]
        when = (
            f"strona nie podaje daty publikacji, więc nie da się jej porównać z analizą {d.publisher} "
            f"z {_dmy(doc_day)}."
            if page_day is None or doc_day is None
            else f"data strony ({_pl_date(page_day)}) nie pasuje do analizy {d.publisher} z {_dmy(doc_day)}."
        )
        return abstain(
            f"nagłówek występuje w analizie, ale {when}",
            [
                Premise(
                    label="Nagłówek strony w tekście analizy",
                    value="występuje dosłownie",
                    effect="+",
                ),
                Premise(
                    label="Data strony a data analizy", value="niezgodna lub nieznana", effect="-"
                ),
            ],
            [_evidence(d, passage, "kontekst")],
        )
    d, h, passage, doc_day, lag = matched[0]
    pub = d.publisher
    txt = (
        f"Tak, chodzi o ten sam materiał, który opisał {pub} w analizie z {_dmy(doc_day)}: nagłówek ze strony "
        f"(„{short(h, 160)}”) występuje w niej dosłownie, a data na stronie ({_pl_date(page_day)}) poprzedza "
        f"analizę o {lag} {'dzień' if lag == 1 else 'dni'}. {pub} pisze: „{short(passage, 300).rstrip(' .”')}”."
    )
    if d.verdict_raw and d.claim:
        txt += f" W tej analizie {pub} ocenił twierdzenie „{short(d.claim, 150)}” jako „{d.verdict_raw}”."
    premises = [
        Premise(
            label="Nagłówek strony w tekście analizy (reguła deterministyczna)",
            value="występuje dosłownie",
            effect="+",
        ),
        Premise(
            label="Data strony a data analizy",
            value=f"strona {_dmy(page_day)}, analiza {_dmy(doc_day)} ({lag} dni później)",
            effect="+",
        ),
        Premise(label="Źródło pierwotne / urzędowe", value="nie", effect="0"),
    ]
    return ClaimResult(
        claim=question,
        verdict="potwierdzone",
        verdict_label=VERDICT_LABEL_PL["potwierdzone"],
        strength=0.6,
        strength_label="umiarkowana",
        premises=premises,
        rules_fired=["M2:TEN_SAM_MATERIAL", "R5:POTWIERDZONE"],
        explanation=txt,
        evidence=[_evidence(d, passage, "popiera")],
        limitations=limitations,
    )
