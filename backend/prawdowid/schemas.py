"""Data contracts shared by the API, channels, extension and website."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# Verdicts required by the challenge. Technical failure / clarification / out-of-scope are NOT verdicts
# and are reported in CheckResult.status instead.
Verdict = Literal[
    "potwierdzone",
    "falszywe",
    "wprowadzajace_w_blad",
    "brak_dowodow",
    "nie_podlega_weryfikacji",
]

VERDICT_LABEL_PL: dict[str, str] = {
    "potwierdzone": "Potwierdzone",
    "falszywe": "Fałszywe",
    "wprowadzajace_w_blad": "Wprowadzające w błąd",
    "brak_dowodow": "Brak wystarczających dowodów",
    "nie_podlega_weryfikacji": "Nie podlega weryfikacji",
}

Status = Literal["ok", "blad_techniczny", "doprecyzuj", "poza_zakresem"]
SourceType = Literal["official", "factcheck", "incident", "media"]
Stance = Literal["popiera", "przeczy", "kontekst", "neutralne"]


class SourceDoc(BaseModel):
    id: str
    source_type: SourceType
    publisher: str
    domain: str
    url: str
    title: str
    published_at: Optional[str] = None
    retrieved_at: Optional[str] = None
    language: str = "pl"
    license: str = ""
    text: str = ""
    claim: Optional[str] = None
    claim_author: Optional[str] = None
    verdict_raw: Optional[str] = None
    verdict: Optional[str] = None  # true|false|misleading|mixed|unverifiable
    tags: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    doc_id: str
    title: str
    publisher: str
    domain: str
    url: str
    source_type: SourceType
    tier: int  # 1 = źródło pierwotne/urzędowe, 2 = fact-checking (IFCN/EFCSN), 3 = baza incydentów, 4 = media
    published_at: Optional[str] = None
    retrieved_at: Optional[str] = None
    age_days: Optional[int] = None
    fragment: str  # the exact passage used (verbatim from the source)
    factcheck_claim: Optional[str] = None
    factcheck_verdict_raw: Optional[str] = None
    factcheck_verdict: Optional[str] = None
    retrieval_score: float = 0.0
    similarity: float = 0.0  # cosine(user claim, fact-checked claim or passage)
    stance: Stance = "neutralne"
    stance_score: float = 0.0
    same_claim: Optional[bool] = None  # True: same claim as fact-check; False: negated/opposite claim
    license: str = ""


class Premise(BaseModel):
    """One explicit, human-readable reason contributing to the strength of the answer."""
    label: str
    value: str
    effect: Literal["+", "-", "0"] = "0"


class ClaimResult(BaseModel):
    claim: str
    kind: Literal["fakt", "opinia", "pytanie", "prognoza"] = "fakt"
    verdict: Verdict
    verdict_label: str
    strength: float  # 0..1, derived ONLY from the premises below
    strength_label: str  # "mocna" | "umiarkowana" | "niewystarczająca" — shown as text, never as a percentage
    premises: list[Premise] = Field(default_factory=list)
    rules_fired: list[str] = Field(default_factory=list)  # e.g. ["R3:FALSZYWE", "HR:ESKALACJA"]
    reason_codes: list[str] = Field(default_factory=list)  # e.g. BRAK_MATERIALOW, ZRODLA_SPRZECZNE, NIEAKTUALNE_DOWODY
    context_type: Optional[str] = None  # NIEAKTUALNE | FALSZYWY_KONTEKST | MIESZANE ...
    would_settle: Optional[str] = None  # "co mogłoby to rozstrzygnąć"
    high_risk: bool = False
    explanation: str
    missing_context: Optional[str] = None
    conflicting: bool = False
    what_unknown: Optional[str] = None
    evidence: list[Evidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    # short answer layer (answer.py, deterministic) — the same text on the web, in chats and in the extension
    short_answer: str = ""  # "Nie. Demagog ocenił twierdzenie „…” jako „Fałsz”."
    basis_line: str = ""  # "Podstawa: mocna — 2 niezależne źródła, w tym urzędowe (…)."
    limitation_line: str = ""  # "Ograniczenie: …"
    main_evidence: Optional[int] = None  # index into `evidence` of the decisive source (the one link we show)
    # abstentions only: index into `evidence` of the item the short answer names as related material (never decisive;
    # shown with its link so the reader can open it, labelled as not settling the claim)
    related_evidence: Optional[int] = None
    # a sentence of the message about the check itself, kept out of the query ("Dlaczego w analizie Demagoga jest
    # 650 mln zł?"); when it names a number, the engine quotes the passage of the analysis that gives it
    meta_question: Optional[str] = None


RULES_VERSION = "1.0"


class SecurityEvent(BaseModel):
    kind: str
    where: str
    detail: str


class CheckRequest(BaseModel):
    text: Optional[str] = Field(default=None, max_length=20000)
    url: Optional[str] = Field(default=None, max_length=2048)
    channel: str = "web"
    session: Optional[str] = None  # opaque, client-generated; lets the user delete their demo session
    # "auto" = background check started by the extension router for a `candidate` item (service.run_check): local
    # corpus only (no live search, no page fetch, no LLM), no moderator case, and the text is not written to the audit log.
    mode: Literal["manual", "auto"] = "manual"
    live_search: Optional[bool] = None  # False skips the live stage for this request; always off in auto mode


class LiveSearchInfo(BaseModel):
    """Live stage (websearch.py): Google Fact Check and/or trusted-domain search. A failure is never a verdict."""
    provider: str  # google_factcheck | sitesearch | searxng | brave (joined with "+")
    query: str = ""
    n_results: int = 0  # documents added as candidate evidence
    status: Literal["ok", "brak_wynikow", "blad"] = "brak_wynikow"
    notice: str = ""  # plain-Polish notice for the user
    steps: list[dict] = Field(default_factory=list)  # per provider: provider, query, n_results, status, notice


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    channel: str = Field(default="chat", max_length=20)
    session: Optional[str] = Field(default=None, max_length=32)


class CheckResult(BaseModel):
    id: str
    created_at: str
    channel: str
    status: Status
    status_message: Optional[str] = None
    input_kind: Literal["text", "url", "image"]
    input_excerpt: str
    url_meta: Optional[dict] = None
    claims: list[ClaimResult] = Field(default_factory=list)
    summary: str = ""
    short_answer: str = ""  # whole-result short answer (answer.py)
    resources: list[dict] = Field(default_factory=list)  # ≤3 trusted pages for the topic: {title, url, why, topic}
    claims_overview: str = ""
    signals: list[dict] = Field(default_factory=list)  # SPRAWDŹ (NASK) educational signals — never affect verdicts
    warnings: list[str] = Field(default_factory=list)
    security_events: list[SecurityEvent] = Field(default_factory=list)
    timings_ms: dict[str, float] = Field(default_factory=dict)
    engine: dict = Field(default_factory=dict)
    case_id: Optional[str] = None
    case_status: Optional[str] = None  # "rekomendowane" vs "przekazane" — never claim forwarding that did not happen
    live_search: Optional[LiveSearchInfo] = None  # None = live stage did not run (no key / not needed / disabled)
    mode: Literal["manual", "auto"] = "manual"  # echo of CheckRequest.mode (auto: see service.run_check)


class QuickItem(BaseModel):
    id: str
    text: str = Field(max_length=4000)


class QuickRequest(BaseModel):
    items: list[QuickItem] = Field(max_length=40)
    page_url: Optional[str] = None


class QuickMatch(BaseModel):
    claim: str
    verdict: Optional[str]
    verdict_raw: Optional[str]
    publisher: str
    url: str
    title: str
    published_at: Optional[str]
    similarity: float
    sentence: str


class QuickConflict(BaseModel):
    """A claim rated TRUE by a fact-checker that is about as close to the text as the debunked one."""
    claim: str
    verdict_raw: Optional[str]
    publisher: str
    url: str
    published_at: Optional[str]
    similarity: float


RouterState = Literal["none", "candidate", "match"]


class QuickResult(BaseModel):
    """Tier 1 = router. `state` is the contract; `risk`/`level` are kept for older extension builds.

    none      – nothing to show, nothing to check.
    candidate – NOT shown to the user; only tells the client which items tier 2 may check in the background
                (ordered by `priority`). `match`, when present, is merely the nearest rated claim.
    match     – the text repeats a claim rated by a named fact-checker: `match` carries publisher, rating, date and
                link. level != "brak" exactly when state == "match"."""
    id: str
    risk: float  # 0..1 — internal score of "repeats a claim already rated false/misleading"; never shown to users
    level: Literal["wysokie", "srednie", "brak"]
    match: Optional[QuickMatch] = None
    reason: str = ""
    analysis_url: Optional[str] = None
    state: RouterState = "none"
    priority: float = 0.0  # candidates only, 0..1: order for automatic tier-2 checks
    reasons: list[str] = Field(default_factory=list)  # RATED_CLAIM_MATCH | NEAR_MISS | CONFLICTING_RATINGS |
    #                                                   HIGH_RISK_TOPIC | FACTUAL_SENTENCE
    conflict: Optional[QuickConflict] = None  # set when a true-rated claim is equally close (the tag is suppressed)
