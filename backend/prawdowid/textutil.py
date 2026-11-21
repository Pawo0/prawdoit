"""Polish text utilities: normalisation, sentence splitting, tokenisation (BM25), claim heuristics."""
from __future__ import annotations

import re
import unicodedata

_ABBREV = {
    "np", "m.in", "tzw", "tj", "itd", "itp", "ok", "godz", "ul", "al", "dr", "prof", "hab", "inż", "mgr", "św",
    "r", "w", "tys", "mln", "mld", "zł", "proc", "pkt", "art", "ust", "poz", "nr", "str", "tel", "wg", "por",
    "jw", "ds", "gen", "płk", "mjr", "kpt", "pt", "ww", "zob", "cd", "sp", "z.o.o", "s.a", "dz.u", "dz",
    "przyp",  # "[we Wrocławiu – przyp. Demagog]", "przyp. red.": an editor's note inside a quoted sentence
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
    for m in _TOKEN_RE.finditer(PII_TAG.sub(" ", text).lower()):
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
    r"genialn\w*|fatalny\w*|fatalna|cudown\w*|super\b|beznadzie\w*|"
    r"jedyn\w* sensown\w*|sensown\w*|fanaberi\w*|bzdur\w*|absurd\w*|"
    r"byłob[yi]|byłaby|byłyby|gdyby|powinno się)\b",
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


# A request to produce or transform text ("napisz wiersz", "przetłumacz to", "write a story") is a task, not information
# to check. Generic: an imperative production verb at the start + a text-genre object (or a translation), and no sign
# of a fact-check request anywhere in the message — "Napisz, czy to prawda, że…" is still checked.
_POLITE = re.compile(r"^\s*(?:(?:proszę|prosze|please|hej|cześć|czesc)[,!]?\s+)?(?:(?:czy\s+)?(?:możesz|mozesz|"
                     r"mógłbyś|mogłabyś|can you|could you)\s+)?(?:mi\s+|me\s+)?", re.I)
_TASK_REQUEST = re.compile(
    r"^(?:"
    r"(?:napisz|napisać|stwórz|stworzyć|wygeneruj|wygenerować|ułóż|ułożyć|wymyśl|wymyślić|zredaguj|przygotuj|"
    r"opowiedz|opowiedzieć|narysuj|zaprojektuj|zaprogramuj|dokończ|write|compose|generate|create|draw|tell)\b"
    r"(?:\s+\S+){0,4}?\s+(?:wiersz\w*|wierszyk\w*|piosenk\w*|tekst\w*\s+piosenk\w*|rymowank\w*|limeryk\w*|haiku|"
    r"fraszk\w*|bajk\w*|baśń|basn\w*|opowiadani\w*|histori\w*|esej\w*|wypracowani\w*|rozprawk\w*|list\w*|mail\w*|"
    r"e-mail\w*|życzeni\w*|zyczeni\w*|przemówieni\w*|toast\w*|dowcip\w*|żart\w*|zart\w*|kawał\w*|przepis\w*|kod\w*|"
    r"program\w*|skrypt\w*|funkcj\w*|slogan\w*|hasł\w*\s+reklam\w*|ogłoszeni\w*|post\w*|tweet\w*|wpis\w*\s+na|"
    r"obraz\w*|rysun\w*|logo|poem|song|story|essay|letter|joke|code|recipe)\b"
    r"|(?:przetłumacz|przetlumacz|przetłumaczyć|translate)\b)", re.I)
_FACTCHECK_INTENT = re.compile(r"\b(?:prawd\w*|fałsz\w*|falsz\w*|sprawd\w*|zweryfik\w*|weryfik\w*|potwierdz\w*|"
                               r"fake\w*|true|false|czy|że|iż|ze\s+niby)\b", re.I)


def is_task_request(s: str) -> bool:
    """'Napisz mi wiersz o jesieni' -> True; 'Napisz, czy to prawda, że VAT spadnie' -> False."""
    body = _POLITE.sub("", re.sub(r"https?://\S+", " ", s or ""), count=1)
    return bool(_TASK_REQUEST.match(body)) and not _FACTCHECK_INTENT.search(body)


_PREAMBLE = re.compile(
    r"^\s*(?:(?:czy\s+)?to\s+prawda,?\s+że|prawda,?\s+że|czy|podobno|ponoć|"
    r"(?:słyszał\w*|czytał\w*|widział\w*|dostał\w*|ktoś\s+(?:mi\s+)?(?:napisał|powiedział|wysłał|przesłał)\w*|"
    r"(?:w|na)\s+(?:telewizji|tv|internecie|necie|radiu|fejsie|facebooku|grupie)\s+(?:mówią|mówili|piszą|pisali|podali|podają)"
    r")[^,.?!]{0,60}?,?\s*że)\s+", re.I)
_TRAILING_META = re.compile(r"\s*(to jak to (w końcu )?jest|czy to prawda|prawda to|serio|o co chodzi|co o tym myślicie|"
                            r"co wy na to|jak to jest)\s*\?*\s*$", re.I)


# "Czy Demagog sprawdzał, czy X?", "Czy ktoś już weryfikował informację, że X?", "Czy fact-checkerzy ocenili, czy X?"
# -> X: a question about whether somebody checked a claim is answered by checking the claim itself (the answer then
# names who checked it). Only stripped when the verb is followed by "czy"/"że", so "Czy NIK zbadała wydatki…" stays.
_CHECKED_BY = re.compile(
    r"^\s*(?:czy\s+)?(?P<who>(?:[\w.-]+\s+){0,3}?)(?:już\s+|kiedyś\s+|ostatnio\s+)?"
    r"(?:sprawdza\w*|sprawdzi\w*|zweryfikowa\w*|weryfikowa\w*|analizowa\w*|przeanalizowa\w*|ocenia\w*|ocenil\w*|"
    r"ocenił\w*|zbada\w*|bada\w*|pisa\w*\s+o\s+tym|opisywa\w*)\s*(?:to|już)?,?\s*"
    r"(?:czy|że|to,?\s+(?:czy|że)|informacj\w*,?\s+(?:że|o\s+tym,?\s+że)|twierdzeni\w*,?\s+że|tez\w*,?\s+że)\s+", re.I)


# Sentences ABOUT a check rather than about the world: "Dlaczego w analizie Demagoga jest 650 mln zł?",
# "Sprawdź też tę stronę: …". They stay in the text shown to the user but are left out of the retrieval query.
_META_SENTENCE = re.compile(
    r"^\s*(?:(?:a|i|to)\s+)?(?:dlaczego|czemu|skąd|jak\s+to\s+możliwe)\b[^.?!]*\b(?:analiz\w*|weryfikac\w*|"
    r"fact-?check\w*|ocen\w*|sprawdz\w*|artyku\w*|tekś\w*|tekst\w*|raport\w*)"
    r"|^\s*(?:proszę\s+|prosze\s+)?(?:sprawdź|sprawdz|zobacz|przeczytaj|oceń|ocen)\b(?:\s+\w+){0,3}?\s+"
    r"(?:stron\w*|link\w*|artyku\w*|wpis\w*|post\w*|materiał\w*|adres\w*)\b[^.?!]*[.?!:]?\s*$", re.I)


_CHECK_VERB = (r"(?:sprawdza\w*|sprawdzi\w*|zweryfikowa\w*|weryfikowa\w*|analizowa\w*|przeanalizowa\w*|ocenia\w*|"
               r"ocenil\w*|ocenił\w*|zbada\w*|bada\w*|opisywa\w*|opisa\w*)")
_OBJ = r"(?:to|tego|tę\s+\w+|ten\s+\w+|tą\s+\w+|o\s+tym|już)"
# A sentence that only asks WHETHER / WHO checked the rest of the message, with no claim of its own:
# "Czy Demagog to sprawdzał?", "Czy ktoś już to zweryfikował?", "Czy fact-checkerzy sprawdzali tę informację?".
_CHECKED_QUESTION = re.compile(
    rf"^\s*czy\s+(?P<who>(?:(?!(?:to|tego|tę|ten|już|kiedyś)\b)[\w.-]+\s+){{0,3}}?)(?:już\s+|kiedyś\s+)?(?:{_OBJ}\s+)?"
    rf"(?:już\s+)?{_CHECK_VERB}(?:\s+{_OBJ})?(?:\s+(?:informacj\w*|wiadomoś\w*|tez\w*|twierdzeni\w*|wpis\w*))?"
    r"\s*[?!.]*\s*$", re.I)


def checked_question(s: str) -> str | None:
    """'Czy Demagog to sprawdzał?' -> 'Demagog'; 'Czy ktoś to sprawdził?' -> 'ktoś'; any other sentence -> None."""
    m = _CHECKED_QUESTION.match(s or "")
    return m.group("who").strip() if m else None


def is_meta_sentence(s: str) -> bool:
    s = re.sub(r"https?://\S+", " ", s or "")
    return bool(_META_SENTENCE.search(s)) or checked_question(s) is not None


def split_meta(s: str) -> tuple[str, str]:
    """(claim part, meta clauses) — also splits after an abbreviation the sentence splitter keeps
    ('…700 mln zł. Dlaczego w analizie…?'). If everything is meta, the whole text stays the claim part."""
    parts = re.split(r"(?<=[.?!:])\s+(?=[„\"(]?[A-ZĄĆĘŁŃÓŚŹŻ])", s or "")
    keep = [x for x in parts if not is_meta_sentence(x)]
    if not keep or len(keep) == len(parts):
        return s, ""
    return " ".join(keep), " ".join(x for x in parts if is_meta_sentence(x))


def asks_who_checked(s: str) -> str | None:
    """'Czy Demagog sprawdzał, czy X?' -> 'Demagog'; 'Czy ktoś to sprawdzał, że…' -> ''; plain claim -> None."""
    s = _TRAILING_META.sub("", s.strip())
    m = _CHECKED_BY.match(s) or _CHECKED_BY.match(_PREAMBLE.sub("", s))
    if m:
        return re.sub(r"\s+(to|już)$", "", m.group("who").strip(), flags=re.I)
    # "Czy Demagog to sprawdzał? <claim>" — the question is a sentence of its own, before or after the claim
    for sent in split_sentences(s):
        who = checked_question(sent)
        if who is not None:
            return who
    return None


def strip_preamble(s: str) -> str:
    """'Słyszałam w telewizji, że X. To jak to w końcu jest?' -> 'X' (the reported claim itself)."""
    s = _TRAILING_META.sub("", s.strip())
    for _ in range(3):  # "Czy to prawda, że Demagog sprawdzał, czy X" → X
        t = _CHECKED_BY.sub("", _PREAMBLE.sub("", s)).strip()
        if t == s or len(t) < 8:
            break
        s = t
    return s.strip()


def question_to_claim(s: str) -> str:
    """'Czy szczepionki zawierają chipy?' -> 'szczepionki zawierają chipy' (for retrieval only)."""
    return strip_preamble(s).rstrip("?").strip()


_META = set("hej cześć siema hejka witam dzień dobry elo sprawdź sprawdz sprawdzisz pls plz proszę prosze dzięki dzieki ok okej "
            "możesz mozesz pomóż pomoz zobacz co tam to mi ten ta tego info coś cos tak nie test".split())


def content_words(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-ząćęłńóśźż0-9]+", PII_TAG.sub(" ", s).lower())
            if w not in STOP and w not in _META and len(w) > 2]


_LEADIN = re.compile(r"^\s*(?:\S+\s+){0,3}?(?:skandal\w*|szok\w*|pilne|uwaga|hańba|tragedia|dramat)\b[^.!?]{0,40}[!.]+\s*", re.I)


_PAST = re.compile(r"\b\w{3,}(?:ł|ła|ło|li|ły)\b")
_COMPOUND_FUTURE = re.compile(r"\bbęd\w*\s+\w+")
_BEDZIE = re.compile(r"będzie")
_PL_DIACRITIC = re.compile(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
_KIND_RX = (_LEADIN, _OPINION, _PREDICTION, _FACTUAL_CUE, _PAST, _COMPOUND_FUTURE, _BEDZIE)
# the same patterns with their own diacritics stripped ("będzie" -> "bedzie", "…ł" -> "…l"), for text typed without them
_KIND_RX_PLAIN = tuple(re.compile(rx.pattern.translate(_STRIP), rx.flags) for rx in _KIND_RX)


def claim_kind(s: str) -> str:
    """fakt | opinia | pytanie | prognoza, from wording cues.

    A text that contains no Polish diacritic at all is taken as typed without them ("zostanie zwolniony i wroci",
    "dopuscil sie") and is matched with diacritic-stripped patterns. A text that does contain diacritics keeps the exact
    patterns: stripping there would only add ambiguity ("czuję" I feel / "czuje" he feels, "mają" / "3 maja")."""
    leadin, opinion, prediction, factual, past_rx, compound_future, bedzie = (
        _KIND_RX if _PL_DIACRITIC.search(s) else _KIND_RX_PLAIN)
    s = leadin.sub("", s) or s  # "Skandal we Wrocławiu! <fact>" — the exclamation is not the claim
    if opinion.search(s) and not _NUMBER.search(s):
        return "opinia"
    if is_question(s):
        return "pytanie"
    # past-tense verbs signal a factual report, except in compound future tense ("będą rosły", "będzie rodził")
    past = past_rx.search(compound_future.sub(" ", s))
    if prediction.search(s) and not factual.search(bedzie.sub("", s)) and not past:
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


# an amount with its unit: "700 mln zł", "3,3 proc.", "207,9 mln" (engine.numeric_stance uses the same pattern)
AMOUNT_RX = re.compile(r"(\d+(?:[.,]\d+)?)\s*(%|proc\w*|zł\b|złotych|zl\b|mln|mld|tys)", re.I)


def amount_unit(u: str) -> str:
    u = u.lower()
    return "%" if u.startswith(("%", "proc")) else "zł" if u.startswith(("zł", "zl")) else u


def amounts(s: str) -> list[tuple[float, str, str]]:
    """(value, unit, the amount as written incl. a following 'zł') for every amount in the text."""
    out = []
    for m in AMOUNT_RX.finditer(s or ""):
        lit = m.group(0) + (re.match(r"\s*(zł|złotych)\b", s[m.end():]) or [""])[0] if amount_unit(m.group(2)) != "zł" else m.group(0)
        out.append((float(m.group(1).replace(",", ".")), amount_unit(m.group(2)), lit.strip()))
    return out


def same_amount(a: tuple, b: tuple) -> bool:
    return a[1] == b[1] and abs(a[0] - b[0]) <= max(0.051, abs(a[0]) * 0.005)


def is_time_sensitive(s: str) -> bool:
    return bool(_TEMPORAL_NOW.search(s))


def years_in(s: str) -> list[int]:
    return [int(y) for y in _YEAR.findall(s)]


# ------------------------------------------------------------------ PII masking (RODO: data minimisation)
# Policy (organisers' clarification; docs/COMPLIANCE.md): mask the direct identifiers of private persons — PESEL,
# ID card and passport numbers, phone numbers, bank account numbers, personal e-mail addresses — and nothing the check
# needs. Names (public figures above all), institutions, places, dates, amounts, statistics and legal references are
# never masked. Every pattern is validated (checksums, strict formats, phone context), so factual numbers survive.
PII_TAG = re.compile(r"\[(?:PESEL|DOWOD|PASZPORT|TELEFON|NR_KONTA|EMAIL)\]")
_URL_SPAN = re.compile(r"(?:https?://|www\.)\S+", re.I)
_EMAIL = re.compile(r"(?<![\w.+-])([\w.+-]+)@[\w-]+(?:\.[\w-]+)+")
# role mailboxes of institutions are contact points, not personal data
_ROLE_MAILBOX = re.compile(r"(?:info|kontakt|contact|biuro|office|sekretariat|kancelaria|press|prasa|media|rzecznik\w*|"
                           r"redakcja|newsroom|iod|abuse|support|pomoc|help|cert|incydent\w*|zgloszeni\w*|hello|"
                           r"no-?reply)", re.I)
_IBAN = re.compile(r"(?<![\w])[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,3})?(?![\w])")
_NRB = re.compile(r"(?<![\w.,])\d{2}(?:[ ]?\d{4}){6}(?![\w]|[.,]\d| \d)")  # Polish account number = IBAN without "PL"
_PESEL = re.compile(r"(?<![\w.,+])\d{11}(?![\w]|[.,]\d)")
# "PL…" + digits are site / register codes (Natura 2000 PLH220032, PLB…), not identity documents
_ID_CARD = re.compile(r"(?<![\w])(?!PL)[A-Z]{3}[ ]?\d{6}(?![\w])")
_PASSPORT = re.compile(r"(?<![\w])[A-Z]{2}[ ]?\d{7}(?![\w])")
_PHONE_INTL = re.compile(r"(?<![\w+])(?:\+|00(?=[1-9]))\d{1,3}[ -]?\(?\d{1,4}\)?(?:[ -]?\d{2,4}){2,4}(?![\w]|[.,]\d)")
_PHONE_PL = re.compile(r"(?<![\w+.,/-])(?<!\d )(?:\(?\d{2}\)?[ -]?\d{3}[ -]?\d{2}[ -]?\d{2}|\d{3}[ -]?\d{3}[ -]?\d{3})"
                       r"(?![\w]|[.,]\d| \d)")
# a number followed by a unit or a currency is an amount or a statistic, never a phone number
_UNIT_AFTER = re.compile(r"\s*(?:zł|zl\b|pln|eur|euro|usd|dolar|\$|€|£|%|proc|mln|mld|tys|os[óo]b|ludzi|mieszka|głos|"
                         r"glos|km|kg|ton|ha\b|m2|m²|szt|egz|daw|wyświetl|razy)", re.I)
# a domestic number counts as a phone only when the text says so ("tel.", "zadzwoń", "mój numer"…) or it is written
# with dashes; "numer partii 716371209", "nr KRS …" and bare digit groups stay
_PHONE_CONTEXT = re.compile(r"(?:\b(?:tel|kom|fax|faks)\.?|\b(?:telefon|komórk|komork|zadzwo|dzwo|sms|esemes|whatsapp|"
                            r"signal|telegram|kontakt|infolini)\w*|\b(?:pod|na|z|ze|ten|tego|tym|m[óo]j|tw[óo]j|jego|jej|ich|nasz|wasz|nieznan)\w*"
                            r"\s+(?:numer\w*|nr\.?)(?:\s+tel\w*\.?)?)[^.!?\n]{0,25}$", re.I)


def _label(s: str, start: int, words: str) -> bool:
    """The identifier is named right before the number ("PESEL: …", "nr dowodu …")."""
    return bool(re.search(rf"\b(?:{words})\w*[^.!?\n\d]{{0,15}}$", s[max(0, start - 40): start], re.I))


def _pesel_ok(d: str) -> bool:
    check = (10 - sum(int(x) * w for x, w in zip(d, (1, 3, 7, 9, 1, 3, 7, 9, 1, 3))) % 10) % 10
    return check == int(d[10]) and 1 <= int(d[2:4]) % 20 <= 12 and 1 <= int(d[4:6]) <= 31


def _weighted_ok(code: str, weights: tuple[int, ...]) -> bool:
    """ID card (AAA + 6 digits) and passport (AA + 7 digits): letters A=10…Z=35, weighted sum ≡ 0 (mod 10)."""
    return sum(int(ch, 36) * w for ch, w in zip(code.replace(" ", ""), weights)) % 10 == 0


def _iban_ok(raw: str) -> bool:
    s = raw.replace(" ", "").upper()
    s = "PL" + s if s[:2].isdigit() else s
    return 15 <= len(s) <= 34 and int("".join(str(int(ch, 36)) for ch in s[4:] + s[:4])) % 97 == 1


def pii_spans(s: str) -> list[tuple[str, int, int]]:
    """(kind, start, end) of every direct identifier in `s`; URLs are left as typed (links must still open)."""
    taken = [(m.start(), m.end()) for m in _URL_SPAN.finditer(s)]
    spans: list[tuple[str, int, int]] = []

    def add(kind: str, a: int, b: int) -> None:
        if not any(a < e and b > st for st, e in taken):
            spans.append((kind, a, b))
            taken.append((a, b))

    for m in _EMAIL.finditer(s):
        if not _ROLE_MAILBOX.fullmatch(m.group(1)):
            add("EMAIL", m.start(), m.end())
    for rx in (_IBAN, _NRB):
        for m in rx.finditer(s):
            if _iban_ok(m.group(0)) or _label(s, m.start(), "kont|rachun|iban|nrb|przelew"):
                add("NR_KONTA", m.start(), m.end())
    for m in _PESEL.finditer(s):
        if _pesel_ok(m.group(0)) or _label(s, m.start(), "pesel"):
            add("PESEL", m.start(), m.end())
    for m in _ID_CARD.finditer(s):
        if _weighted_ok(m.group(0), (7, 3, 1, 9, 7, 3, 1, 7, 3)) or _label(s, m.start(), "dowod|dowód"):
            add("DOWOD", m.start(), m.end())
    for m in _PASSPORT.finditer(s):
        if _weighted_ok(m.group(0), (7, 3, 9, 1, 7, 3, 1, 7, 3)) or _label(s, m.start(), "paszport"):
            add("PASZPORT", m.start(), m.end())
    for m in _PHONE_INTL.finditer(s):
        if 9 <= sum(ch.isdigit() for ch in m.group(0)) <= 15 and not _UNIT_AFTER.match(s, m.end()):
            add("TELEFON", m.start(), m.end())
    for m in _PHONE_PL.finditer(s):
        g = m.group(0)
        if _UNIT_AFTER.match(s, m.end()):
            continue
        if _PHONE_CONTEXT.search(s[max(0, m.start() - 40): m.start()]) or "-" in g:
            add("TELEFON", m.start(), m.end())
    return sorted(spans, key=lambda x: x[1])


def mask_pii(s: str) -> str:
    """Replace direct identifiers with [PESEL] / [DOWOD] / [PASZPORT] / [TELEFON] / [NR_KONTA] / [EMAIL]. Idempotent."""
    out, last = [], 0
    for kind, a, b in pii_spans(s or ""):
        out += [s[last:a], f"[{kind}]"]
        last = b
    return "".join(out) + (s or "")[last:]


def drop_pii_tags(s: str) -> str:
    """The placeholders stay in what the user sees, never in a retrieval or live-search query."""
    return normalize_ws(PII_TAG.sub(" ", s))


def short(s: str, n: int = 280) -> str:
    s = normalize_ws(s)
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"
