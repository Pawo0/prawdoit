"""Polish text utilities: normalisation, sentence splitting, tokenisation (BM25), claim heuristics."""
from __future__ import annotations

import re
import unicodedata

_ABBREV = {
    "np", "m.in", "tzw", "tj", "itd", "itp", "ok", "godz", "ul", "al", "dr", "prof", "hab", "inż", "mgr", "św",
    "r", "w", "tys", "mln", "mld", "zł", "proc", "pkt", "art", "ust", "poz", "nr", "str", "tel", "wg", "por",
    "jw", "ds", "gen", "płk", "mjr", "kpt", "pt", "ww", "zob", "cd", "sp", "z.o.o", "s.a", "dz.u", "dz",
}

_SENT_RE = re.compile(r"(?<=[.!?…])[\"'”»)]*\s+(?=[\"'„«(]*[A-ZĄĆĘŁŃÓŚŹŻ0-9])")


def normalize_ws(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "")
    s = s.replace(" ", " ").replace("​", "")
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n{3,}", "\n\n", s)).strip()


def split_sentences(text: str) -> list[str]:
    text = normalize_ws(text)
    out: list[str] = []
    for para in re.split(r"\n+", text):
        para = para.strip()
        if not para:
            continue
        parts = _SENT_RE.split(para)
        buf = ""
        for p in parts:
            buf = f"{buf} {p}".strip() if buf else p
            last = buf.rstrip(".!?…\"'”») ").split(" ")[-1].lower() if buf else ""
            # don't split after abbreviations / initials / ordinal numbers
            if buf.endswith(".") and (last in _ABBREV or re.fullmatch(r"[a-ząćęłńóśźż]|\d{1,2}", last)):
                continue
            out.append(buf)
            buf = ""
        if buf:
            out.append(buf)
    return [s for s in out if s]


_STRIP = str.maketrans("ąćęłńóśźż", "acelnoszz")
_TOKEN_RE = re.compile(r"[0-9]+(?:[.,][0-9]+)?%?|[a-ząćęłńóśźż]+", re.IGNORECASE)
STOP = set(
    """a aby ach acz aczkolwiek aj albo ale ależ ani aż bardziej bardzo bez bo bowiem by byli bym bynajmniej być był była
    było były będzie będą cali cała cały chce ci ciebie cię co cokolwiek coraz coś czasami czasem czemu czy czyli często
    dla dlaczego dlatego do dobrze dokąd dość dużo dwa dwaj dwie dwoje dziś dzisiaj gdy gdyby gdyż gdzie gdziekolwiek
    gdzieś go i ich ile im inna inne inny innych iż ja ją jak jakaś jakby jaki jakichś jakie jakiś jakiż jakkolwiek jako
    jakoś je jeden jedna jedno jednak jednakże jego jej jemu jest jestem jeszcze jeśli jeżeli już ją każdy kiedy kilka
    kimś kto ktokolwiek ktoś która które którego której który których którym którzy ku lat lecz lub ma mają mało mam mi
    mimo między mną mnie mogą moi moim moja moje może możliwe można mój mu musi my na nad nam nami nas nasi nasz nasza
    nasze naszego naszych natomiast natychmiast nawet nic nich nie niech niego niej niemu nigdy nim nimi niż no o obok
    od około on ona one oni ono oraz oto owszem pan pana pani po pod podczas pomimo ponad ponieważ powinien powinna
    powinni powinno poza prawie przecież przed przede przedtem przez przy roku również sam sama są się skąd sobie sobą
    sposób swoje ta tak taka taki takie także tam te tego tej temu ten teraz też to tobą tobie toteż trzeba tu tutaj
    twoi twoim twoja twoje twym twój ty tych tylko tym u w wam wami was wasz wasza wasze we według wiele wielu więc
    więcej wszyscy wszystkich wszystkie wszystkim wszystko wtedy wy właśnie z za zapewne zawsze ze zł znowu znów
    został żaden żadna żadne żadnych że żeby the of and to in is""".split()
)


def strip_pl(s: str) -> str:
    return s.lower().translate(_STRIP)


def tokens(text: str, stem: int = 6) -> list[str]:
    """Lowercase, drop stopwords, strip diacritics and truncate to a prefix — a crude but robust stemmer for
    a highly inflected language (szczepionki/szczepionek/szczepionkach -> szczep)."""
    out = []
    for m in _TOKEN_RE.finditer(text.lower()):
        t = m.group(0)
        if t in STOP or len(t) < 2:
            continue
        if t[0].isdigit():
            out.append(t.replace(",", "."))
            continue
        out.append(strip_pl(t)[:stem])
    return out


# ------------------------------------------------------------------ claim heuristics
_OPINION = re.compile(
    r"\b(uważam|sądzę|myślę|moim zdaniem|według mnie|wydaje mi się|mam wrażenie|czuję|wierzę|lubię|nie lubię|"
    r"nienawidzę|kocham|powin(?:ien|na|no|ni|ny)|należy|trzeba by|najlepsz\w*|najgorsz\w*|beznadziejn\w*|"
    r"wspaniał\w*|okropn\w*|skandal\w*|hańb\w*|żenujące|głupi\w*|piękn\w*|brzydk\w*|zdrajc\w*|obrzydliw\w*|"
    r"naj(?:piękn|wspanialsz|fajn|cudown|gorsz|lepsz|głupsz|mądrzejsz|brzydsz|okropniejsz)\w*|nie umywa|"
    r"genialn\w*|fatalny\w*|fatalna|cudown\w*|super\b|beznadzie\w*)\b",
    re.IGNORECASE,
)
_PREDICTION = re.compile(r"\b(będzie|będą|zostanie|zostaną|wkrótce|za rok|za miesiąc|w przyszłym|prognoz\w*)\b", re.I)
_FACTUAL_CUE = re.compile(
    r"\b(jest|są|był\w*|wynosi|wyniósł|wyniosła|wzrósł|wzrosła|spadł\w*|ogłosił\w*|wprowadz\w*|zakaz\w*|nakaz\w*|"
    r"przyj[ęe]ł\w*|uchwali\w*|podpisał\w*|zmarł\w*|zgin[ęe]ł\w*|kosztuje|kosztował\w*|zawiera\w*|powoduj\w*|"
    r"spowodował\w*|zatrzyman\w*|aresztowan\w*|wysła\w*|przekaza\w*|otrzyma\w*|zarabia\w*|płaci\w*|likwid\w*|"
    r"zlikwid\w*|obowiązuj\w*|zabrania\w*|pozwala\w*|dostał\w*|zniesi\w*|wydał\w*|wyda\w*|potwierdzi\w*|"
    r"zatwierdzi\w*|zdecydował\w*|ma\b|mają\b|mieli\b|miał\w*|nie ma)\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d")
_TEMPORAL_NOW = re.compile(
    r"\b(dziś|dzisiaj|teraz|właśnie|wczoraj|w tym tygodniu|przed chwilą|obecnie|aktualnie|od jutra|pilne|"
    r"breaking|najnowsze|trwa|w tej chwili)\b",
    re.IGNORECASE,
)
_YEAR = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")


def is_question(s: str) -> bool:
    s = s.strip()
    return s.endswith("?") or bool(re.match(r"^(czy|kiedy|dlaczego|ile|jak|kto|co|gdzie|po co)\b", s, re.I))


_PREAMBLE = re.compile(
    r"^\s*(?:(?:czy\s+)?to\s+prawda,?\s+że|prawda,?\s+że|czy|podobno|ponoć|"
    r"(?:słyszał\w*|czytał\w*|widział\w*|dostał\w*|ktoś\s+(?:mi\s+)?(?:napisał|powiedział|wysłał|przesłał)\w*|"
    r"(?:w|na)\s+(?:telewizji|tv|internecie|necie|radiu|fejsie|facebooku|grupie)\s+(?:mówią|mówili|piszą|pisali|podali|podają)"
    r")[^,.?!]{0,60}?,?\s*że)\s+", re.I)
_TRAILING_META = re.compile(r"\s*(to jak to (w końcu )?jest|czy to prawda|prawda to|serio|o co chodzi|co o tym myślicie|"
                            r"co wy na to|jak to jest)\s*\?*\s*$", re.I)


def strip_preamble(s: str) -> str:
    """'Słyszałam w telewizji, że X. To jak to w końcu jest?' -> 'X' (the reported claim itself)."""
    s = _TRAILING_META.sub("", s.strip())
    return _PREAMBLE.sub("", s).strip()


def question_to_claim(s: str) -> str:
    """'Czy szczepionki zawierają chipy?' -> 'szczepionki zawierają chipy' (for retrieval only)."""
    return strip_preamble(s).rstrip("?").strip()


_META = set("hej cześć siema hejka witam dzień dobry elo sprawdź sprawdz sprawdzisz pls plz proszę prosze dzięki dzieki ok okej "
            "możesz mozesz pomóż pomoz zobacz co tam to mi ten ta tego info coś cos tak nie test".split())


def content_words(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-ząćęłńóśźż0-9]+", s.lower()) if w not in STOP and w not in _META and len(w) > 2]


def claim_kind(s: str) -> str:
    if _OPINION.search(s) and not _NUMBER.search(s):
        return "opinia"
    if is_question(s):
        return "pytanie"
    # past-tense verbs signal a factual report, except in compound future tense ("będą rosły", "będzie rodził")
    past = re.search(r"\b\w{3,}(?:ł|ła|ło|li|ły)\b", re.sub(r"\bbęd\w*\s+\w+", " ", s))
    if _PREDICTION.search(s) and not _FACTUAL_CUE.search(s.replace("będzie", "")) and not past:
        return "prognoza"
    return "fakt"


def checkworthiness(s: str) -> float:
    """0..1 heuristic score: numbers, named entities, factual verbs, length."""
    words = s.split()
    n = len(words)
    if n < 4:
        return 0.1
    score = 0.2
    if _NUMBER.search(s):
        score += 0.25
    caps = sum(1 for w in words[1:] if w[:1].isupper())
    score += min(0.25, caps * 0.08)
    if _FACTUAL_CUE.search(s):
        score += 0.2
    if _OPINION.search(s):
        score -= 0.25
    if n > 60:
        score -= 0.15
    return max(0.0, min(1.0, score))


def is_time_sensitive(s: str) -> bool:
    return bool(_TEMPORAL_NOW.search(s))


def years_in(s: str) -> list[int]:
    return [int(y) for y in _YEAR.findall(s)]


# ------------------------------------------------------------------ PII masking (RODO: data minimisation)
_PII = [
    (re.compile(r"\b\d{11}\b"), "[PESEL]"),
    (re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?\d{4}){6}\b|\b\d{2}(?:[ ]?\d{4}){6}\b"), "[NR_KONTA]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"(?<!\d)(?:\+?48[ -]?)?(?:\d{3}[ -]?\d{3}[ -]?\d{3})(?!\d)"), "[TELEFON]"),
    (re.compile(r"\b[A-Z]{3}\s?\d{6}\b"), "[DOWOD]"),
]


def mask_pii(s: str) -> str:
    for rx, rep in _PII:
        s = rx.sub(rep, s)
    return s


def short(s: str, n: int = 280) -> str:
    s = normalize_ws(s)
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"
