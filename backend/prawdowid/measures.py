"""Recognize statistical measures and distinguish different definitions of similar numbers.

Indicators whose value depends on the definition used — general statistical knowledge, not case text.

A number that differs from an official statistical card is a contradiction only if the claim and the card measure
the same thing. Several common indicators have more than one official definition, and those give different numbers
for the same period:

  inflation      CPI (GUS: wskaźnik cen towarów i usług konsumpcyjnych)  vs  HICP (Eurostat: zharmonizowany)
                 headline vs core ("inflacja bazowa")
  unemployment   registered (GUS, urzędy pracy)  vs  LFS (BAEL / ILO, survey; Eurostat)
  GDP growth     real (constant prices)  vs  nominal (current prices)
  GDP per capita in purchasing power standards (PPS)  vs  at market exchange rates
  wages          gross vs net; enterprise sector vs whole national economy; mean vs median
  pensions       gross vs net; ZUS (non-agricultural) vs KRUS (farmers)
  public debt    EU / EDP (general government)  vs  national (constitutional, art. 216 ust. 5)
  deficit        general government (EDP)  vs  state budget

For each indicator the table lists its dimensions, and for each dimension the variants: how a card states that it
uses the variant (searched in the card's title and FIRST sentence only — card texts often add a note naming the
other definition, "Uwaga: to inna miara niż …") and the words by which a claim names it. A dimension is
`ambiguous` when a claim that does not name a variant could mean any of them (CPI or HICP); otherwise an unqualified
claim means the usual variant (headline inflation, mean wage) and only a claim naming another variant is excluded.

Used by engine.verify_claim: a numeric mismatch with a card counts only if the claim names the card's variant on
every ambiguous dimension, or cards for every alternative definition of the same period are indexed and none of
them gives the claimed number.

Reading guide: docs/backend/ENGINE.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

_I = re.IGNORECASE


@dataclass(frozen=True)
class Variant:
    name: str  # shown in notes, e.g. "CPI (GUS)"
    card: (
        re.Pattern | None
    )  # how a card says it uses this variant; None = the card's default when nothing else matches
    claim: re.Pattern  # words by which a claim names this variant


@dataclass(frozen=True)
class Dimension:
    key: str
    variants: tuple[Variant, ...]
    ambiguous: bool = True  # an unqualified claim could mean any variant


@dataclass(frozen=True)
class Measure:
    key: str
    card: re.Pattern  # the card (title + first sentence) reports this indicator
    dims: tuple[Dimension, ...]


def _rx(p: str) -> re.Pattern:
    return re.compile(p, _I)


_GROSS_NET = Dimension(
    "brutto_netto",
    (
        Variant("brutto", _rx(r"\bbrutto\b"), _rx(r"\bbrutto\b")),
        Variant(
            "netto",
            _rx(r"\bnetto\b|na rękę"),
            _rx(r"\bnetto\b|na rękę|do ręki|na czysto|po odliczeniu (podatk|składek)"),
        ),
    ),
)

MEASURES: tuple[Measure, ...] = (
    Measure(
        "dług publiczny",
        _rx(r"\bdług\w*\b.{0,40}\bpubliczn|\bzadłużeni\w* (państwa|publiczn|sektora)"),
        (
            Dimension(
                "definicja",
                (
                    Variant(
                        "definicja unijna (EDP)",
                        _rx(
                            r"\bEDP\b|definicj\w* (UE|unijn)|instytucji rządowych i samorządowych|Maastricht"
                        ),
                        _rx(
                            r"\bedp\b|instytucji rządowych|definicj\w* (ue|unijn|eurostat)|metodologi\w* (ue|unijn|eurostat)"
                            r"|maastricht|eurostat"
                        ),
                    ),
                    Variant(
                        "definicja krajowa (konstytucyjna)",
                        _rx(r"\bPDP\b|państwow\w* dług|definicj\w* krajow|konstytucyjn"),
                        _rx(
                            r"\bpdp\b|państwow\w* dług|dług\w* państwow|definicj\w* krajow|metodologi\w* krajow|konstytucyjn"
                            r"|ustaw\w* o finansach publicznych|ministerstw\w* finansów|\bmf\b"
                        ),
                    ),
                ),
            ),
        ),
    ),
    Measure(
        "deficyt",
        _rx(r"\bdeficyt"),
        (
            Dimension(
                "zakres",
                (
                    Variant(
                        "sektor finansów publicznych (EDP)",
                        _rx(r"sektor\w* finansów publicznych|instytucji rządowych|\bEDP\b"),
                        _rx(
                            r"sektor\w* finansów publicznych|instytucji rządowych|\bedp\b|eurostat|całego sektora"
                        ),
                    ),
                    Variant(
                        "budżet państwa",
                        _rx(r"budżet\w* państwa"),
                        _rx(r"budżet\w* państwa|budżetow\w*"),
                    ),
                ),
            ),
        ),
    ),
    Measure(
        "PKB per capita",
        _rx(r"\bPKB\b.{0,15}(per capita|na (jednego )?mieszkańca|na osobę)"),
        (
            Dimension(
                "jednostka",
                (
                    Variant(
                        "parytet siły nabywczej (PPS)",
                        _rx(r"\bPPS\b|siły nabywczej"),
                        _rx(r"\bpps\b|siły nabywczej|parytet"),
                    ),
                    Variant(
                        "kurs rynkowy",
                        _rx(r"kurs\w* rynkow|\bEUR\b(?!/kWh)|\bUSD\b|cen\w* bieżąc"),
                        _rx(r"kurs\w* rynkow|nominaln|\beur\b|\beuro\b|dolar|\busd\b"),
                    ),
                ),
            ),
        ),
    ),
    Measure(
        "wzrost PKB",
        _rx(
            r"(wzrost|dynamik\w*|spad\w*)\s+(realn\w+\s+|nominaln\w+\s+)?PKB|\bPKB\b.{0,30}\b(wzrósł|wzrost|spadł)"
        ),
        (
            Dimension(
                "ceny",
                (
                    Variant(
                        "realnie (ceny stałe)",
                        _rx(r"\brealn|cen\w* stał|wolumen"),
                        _rx(r"\brealn|cen\w* stał"),
                    ),
                    Variant(
                        "nominalnie (ceny bieżące)",
                        _rx(r"\bnominaln|cen\w* bieżąc"),
                        _rx(r"\bnominaln|cen\w* bieżąc"),
                    ),
                ),
            ),
        ),
    ),
    Measure(
        "inflacja",
        _rx(
            r"\binflacj|\bHICP\b|\bCPI\b|wskaźnik\w* cen towarów i usług konsumpcyjnych"
            r"|zharmonizowan\w* wskaźnik\w* cen"
        ),
        (
            Dimension(
                "wskaźnik",
                (
                    Variant(
                        "CPI (GUS)",
                        _rx(r"\bCPI\b|towarów i usług konsumpcyjnych"),
                        _rx(
                            r"\bcpi\b|\bgus\w*|główn\w* urzęd\w* statystyczn|towarów i usług konsumpcyjnych"
                        ),
                    ),
                    Variant(
                        "HICP (Eurostat)",
                        _rx(r"\bHICP\b|zharmonizowan"),
                        _rx(r"\bhicp\b|zharmonizowan|eurostat"),
                    ),
                ),
            ),
            Dimension(
                "zakres",
                (
                    Variant("inflacja ogółem", None, _rx(r"\bogółem\b|\bogóln\w*")),
                    Variant("inflacja bazowa", _rx(r"\bbazow"), _rx(r"\bbazow")),
                ),
                ambiguous=False,
            ),
        ),
    ),
    Measure(
        "bezrobocie",
        _rx(r"\bbezroboci"),
        (
            Dimension(
                "metoda",
                (
                    Variant(
                        "bezrobocie rejestrowane (GUS, urzędy pracy)",
                        _rx(r"rejestrowan"),
                        _rx(
                            r"rejestrowan|zarejestrowan|urzęd\w* pracy|urzęd\w* zatrudnieni|\bpup\b|\bgus\w*"
                        ),
                    ),
                    Variant(
                        "bezrobocie wg BAEL/LFS (Eurostat)",
                        _rx(
                            r"\bBAEL\b|\bLFS\b|\bILO\b|\bMOP\b|aktywności ekonomicznej|\(Eurostat\)"
                        ),
                        _rx(r"\bbael\b|\blfs\b|\bilo\b|\bmop\b|aktywności ekonomicznej|eurostat"),
                    ),
                ),
            ),
        ),
    ),
    Measure(
        "emerytura",
        _rx(r"\bemerytur|\brent[aęy]\b"),
        (
            _GROSS_NET,
            Dimension(
                "system",
                (
                    Variant(
                        "ZUS (system pozarolniczy)",
                        _rx(r"\bZUS\b|pozarolnicz"),
                        _rx(r"\bzus\b|pozarolnicz"),
                    ),
                    Variant("KRUS (rolnicy)", _rx(r"\bKRUS\b|rolnik"), _rx(r"\bkrus\b|rolni")),
                ),
            ),
        ),
    ),
    Measure(
        "wynagrodzenie",
        _rx(r"\bwynagrodzeni|\bpensj|\bzarobk"),
        (
            _GROSS_NET,
            Dimension(
                "zakres",
                (
                    Variant(
                        "sektor przedsiębiorstw",
                        _rx(r"sektor\w* przedsiębiorstw"),
                        _rx(r"sektor\w* przedsiębiorstw|w przedsiębiorstwach|w firmach"),
                    ),
                    Variant(
                        "gospodarka narodowa",
                        _rx(r"gospodar\w* narodow|cał\w* gospodar"),
                        _rx(r"gospodar\w* narodow|cał\w* gospodar"),
                    ),
                ),
            ),
            Dimension(
                "statystyka",
                (
                    Variant("średnia", _rx(r"przeciętn|średni"), _rx(r"przeciętn|średni")),
                    Variant(
                        "mediana",
                        _rx(r"\bmedian|dominant"),
                        _rx(r"\bmedian|dominant|połowa .{0,30}zarabia"),
                    ),
                ),
                ambiguous=False,
            ),
        ),
    ),
)

# legal acts state amounts (minimum wage, benefit levels) by law, not a statistical measure with competing definitions
_ACT = re.compile(
    r"^(Ustawa|Rozporządzenie|Dyrektywa|Decyzja|Konstytucja|Uchwała|Obwieszczenie)\b", _I
)
_FIRST_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ])")


def _head(title: str, text: str) -> str:
    """Title + first sentence: where a card states its own definition (later sentences may name the other one)."""
    first = _FIRST_SENT.split((text or "").strip()[:600], maxsplit=1)[0]
    return f"{title}. {first}"


@lru_cache(maxsize=8192)
def profile(
    title: str, text_head: str
) -> tuple[Measure, tuple[tuple[Dimension, Variant], ...]] | None:
    """(indicator, ((dimension, variant the card uses), …)) for a statistical card; None if it reports no indicator
    in the table. A dimension is left out when the card does not say which variant it uses, or says two.
    """
    if _ACT.search(title or ""):
        return None
    head = _head(title, text_head)
    for m in MEASURES:
        if not m.card.search(head):
            continue
        own = []
        for dim in m.dims:
            hit = [v for v in dim.variants if v.card is not None and v.card.search(head)]
            if not hit:
                hit = [v for v in dim.variants if v.card is None]
            if len(hit) == 1:
                own.append((dim, hit[0]))
        return m, tuple(own)
    return None


def card_profile(title: str, text: str):
    return profile(title or "", (text or "")[:600])


def named(claim: str, dim: Dimension) -> set[str]:
    """Names of the variants of `dim` that the claim names."""
    return {v.name for v in dim.variants if v.claim.search(claim)}


def compatible(claim: str, title: str, text: str) -> bool:
    """False if the claim names a different variant than the card on some dimension (claim: HICP, card: CPI;
    claim: net, card: gross) — then the card's number says nothing about the claim's number."""
    p = card_profile(title, text)
    if p is None:
        return True
    for dim, v in p[1]:
        n = named(claim, dim)
        if n and v.name not in n:
            return False
    return True


def unnamed(claim: str, title: str, text: str) -> list[tuple[Dimension, Variant]]:
    """Ambiguous dimensions on which the claim does not say which variant it means (with the card's variant)."""
    p = card_profile(title, text)
    if p is None:
        return []
    return [(dim, v) for dim, v in p[1] if dim.ambiguous and not named(claim, dim)]


def uses(title: str, text: str, measure_key: str, dim_key: str) -> str | None:
    """The variant name the card uses on dimension `dim_key` of indicator `measure_key` (None if another indicator
    or not stated)."""
    p = card_profile(title, text)
    if p is None or p[0].key != measure_key:
        return None
    return next((v.name for dim, v in p[1] if dim.key == dim_key), None)


def measure_of(title: str, text: str) -> Measure | None:
    p = card_profile(title, text)
    return p[0] if p else None
