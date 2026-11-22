"""Remove author/date/share metadata before claim extraction, including OCR debris.

Line-level metadata filter, applied to multi-line input before sentence splitting.

Text copied or OCR-read from a social-media post, a forum or a news page carries lines that are not part of the
message: the author line and its timestamp, handles, the interface around the post (share / comment buttons,
reaction counters) and, from OCR, fragments with hardly any letters. Each of these lines would otherwise become a
"sentence" and could be checked as a claim of its own. A line is dropped only when it matches one of these shapes as
a whole; anything with its own wording (a verb, a lower-case content word, a question) stays. The filter never
removes every line, and a single-line input passes through unchanged.

Reading guide: docs/backend/REQUEST_FLOW.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import re

from .textutil import _FACTUAL_CUE, _PAST

_MONTHS = (
    r"(?:stycze[ńn]|styczni[au]|luty|lutego|lutym|marzec|marca|marcu|kwiecie[ńn]|kwietni[au]|maj|maja|maju|"
    r"czerwiec|czerwc[au]|lipiec|lipc[au]|sierpie[ńn]|sierpni[au]|wrzesie[ńn]|wrze[śs]ni[au]|pa[źz]dziernik[au]?|"
    r"listopad[a]?|listopadzie|grudzie[ńn]|grudni[au]|sty|lut|mar|kwi|cze|lip|sie|wrz|pa[źz]|lis|gru|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b"
)
_WEEKDAYS = (
    r"(?:poniedziałek|wtorek|środa|czwartek|piątek|sobota|niedziela|pon|wt|śr|czw|pt|sob|niedz)\b"
)
_UNITS = r"(?:s|sek|sekund\w*|min|minut\w*|h|godz|godzin\w*|g|d|dni|dzień|tydz|tyg|tygodni\w*|mies|miesi\w*|r|rok|lat|lata)\b"
# one date / time expression; the line is tested against a sequence of these with separators only in between
_DATE = re.compile(
    rf"(?:\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{2,4}}|\d{{4}}-\d{{2}}-\d{{2}}(?:[T ]\d{{2}}:\d{{2}}(?::\d{{2}})?)?|"
    rf"\d{{1,2}}\s+(?:{_MONTHS})\.?(?:\s+\d{{4}})?|(?:{_MONTHS})\.?\s+\d{{1,2}},?(?:\s+\d{{4}})?|"
    rf"(?:{_MONTHS})\.?\s+\d{{4}}|"
    rf"(?:o\s+|godz\.?\s*|g\.\s*)?\d{{1,2}}[:.]\d{{2}}(?:\s*(?:am|pm))?|"
    rf"\d+\s*(?:{_UNITS})\.?(?:\s+temu)?|"
    rf"(?:{_WEEKDAYS})\.?|wczoraj|przedwczoraj|dzisiaj|dziś|teraz|przed chwilą|właśnie teraz|temu|"
    rf"(?:19|20)\d{{2}}\b(?:\s*r\.|\s+roku)?|r\.|roku|dnia|w dniu|"
    rf"edytowan\w*|zaktualizowan\w*|aktualizacja|opublikowan\w*|dodan\w*|data publikacji|publikacja)",
    re.I,
)
_SEP = r"[\s,;:·•|/\-–—()\[\].]*"
_DATE_ONLY = re.compile(rf"^{_SEP}(?:(?:{_DATE.pattern}){_SEP})+$", re.I)
_DATE_EDGE = re.compile(
    rf"(?:^{_SEP}(?:(?:{_DATE.pattern}){_SEP})+|{_SEP}(?:(?:{_DATE.pattern}){_SEP})+$)", re.I
)

_HANDLE = re.compile(r"(?<!\w)(?:@[\w.]{2,}|u/[\w-]{2,}|r/[\w-]{2,})")
_USERNAME = re.compile(
    r"^(?=[\w.]*[_\d])(?=[\w.]*[^\W\d_])[\w.]{3,30}$"
)  # one token mixing letters with digits/underscore

# who posted it: a role or account word opening an author line ("<role> <date>", "<role> · <date>")
_ROLE = re.compile(
    r"^(?:użytkowni\w*|autor\w*|redakcj\w*|redaktor\w*|administrator\w*|admin\w*|moderator\w*|reporter\w*|"
    r"dziennikar\w*|korespondent\w*|wpis\w*|post\w*|komentarz\w*|odpowied\w*|profil\w*|konto|kont[ao]|"
    r"stron[aey]|grup[aey]|kanał\w*|fanpage\w*|źródło|fot\.?|foto|zdjęcie|materiał\w* (?:prasow|partnersk|sponsorowan)\w*)$",
    re.I,
)
_BYLINE_VERB = re.compile(
    r"^(?:opublikował\w*|napisał\w*|dodał\w*|udostępnił\w*|skomentował\w*|odpowiedział\w*|"
    r"zamieścił\w*|wrzucił\w*|posted|shared|wrote)$",
    re.I,
)

# interface text around a post: buttons, counters, labels
_UI_WORD = re.compile(
    r"^(?:udostępni\w*|udostępnie\w*|komentarz\w*|skomentuj|komentuj\w*|polub\w*|lubię|lubi|reakcj\w*|reaguj|"
    r"odpowiedz\w*|odpowiedzi|obserwuj\w*|obserwując\w*|subskrybuj\w*|subskrypc\w*|wyświetle\w*|wyświetl|zapisz|"
    r"zapisan\w*|więcej|pokaż|ukryj|zobacz|tłumaczeni\w*|przetłumacz|przekaż|dalej|napisz|sponsorowan\w*|"
    r"promowan\w*|reklama|oznacz\w*|zgłoś|wiadomoś\w*|wyślij|kopiuj|link|tys|mln|k|m|tak|share\w*|like\w*|"
    r"comment\w*|repl\w*|retweet\w*|repost\w*|quote\w*|view\w*|follow\w*|subscribe\w*|send|save|more|translate|"
    r"to|i|oraz|innych|inne|osób|osoby|osoba|użytkowników|razy)$",
    re.I,
)
_COUNTER = re.compile(r"^\d+(?:[.,]\d+)?[kKmM]?$")

_MAX_META_LEN = 160
_WORD = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*")
_VERB_CUE = re.compile(
    r"\b\w{2,}(?:ł|ła|ło|li|ły|łem|łam|łeś|łaś|liśmy|łyśmy|ują|uje|ają|eją)\b", re.I
)


def _words(s: str) -> list[str]:
    return _WORD.findall(s)


def _is_date_line(line: str) -> bool:
    return bool(_DATE_ONLY.match(line))


def _is_name_like(words: list[str]) -> bool:
    """1-4 words, every one capitalised (a person, a page, an outlet): an author line, not a statement. A word in
    capitals longer than an acronym is shouting, not a name ("RZĄD KŁAMIE")."""
    return 1 <= len(words) <= 4 and all(
        w[:1].isupper() and (len(w) <= 4 or not w.isupper()) for w in words
    )


def _has_verb(s: str) -> bool:
    return bool(_FACTUAL_CUE.search(s) or _PAST.search(s) or _VERB_CUE.search(s))


def _is_byline(line: str) -> bool:
    """ "<role or user> <date>" / "<date> · <user>" / "<role>: <name>" / a bare "<Name Surname>": besides an optional
    timestamp at one edge, only an author (a role word, a handle or a capitalised name), no statement of its own.
    """
    if line.rstrip().endswith(("?", "!")):
        return False
    m = re.match(r"^\s*([^\W\d_]+)\s*:\s*(.+?)[\s.]*$", line)
    if m and _ROLE.match(m.group(1)):  # "Autor: Jan Nowak", "Źródło: Redakcja Serwisu"
        named = _words(_HANDLE.sub(" ", m.group(2)))
        if not re.search(r"\d", _DATE_EDGE.sub(" ", m.group(2))) and (
            not named or _is_name_like(named)
        ):
            return True
    dated = bool(_DATE_EDGE.search(line))
    rest = _HANDLE.sub(" ", _DATE_EDGE.sub(" ", line) if dated else line)
    if re.search(r"\d", rest):
        return False
    words = _words(rest)
    if not 1 <= len(words) <= 6:
        return False
    if dated and (_ROLE.match(words[0]) or any(_BYLINE_VERB.match(w) for w in words)):
        return not any(_has_verb(w) and not _BYLINE_VERB.match(w) for w in words)
    # a capitalised name on its own needs two words ("Jan Nowak"), next to a timestamp one is enough ("Nowak · 2 godz.")
    return _is_name_like(words) and (dated or len(words) >= 2) and not _has_verb(rest)


def _is_handle_line(line: str) -> bool:
    """A handle or a username, optionally next to the display name: "@jan_k", "Anna Nowak @anowak", "kowal_77"."""
    rest = _HANDLE.sub(" ", line)
    words = _words(rest)
    if rest.strip() != line.strip():
        return not words or (_is_name_like(words) and not re.search(r"\d", rest))
    toks = line.strip(" .:·•|").split()
    return len(toks) == 1 and bool(_USERNAME.match(toks[0]))


def _is_ui_line(line: str) -> bool:
    """Only buttons, labels and counters: "Udostępnij", "1,2 tys. reakcji · 87 komentarzy", "Lubię to! Odpowiedz"."""
    toks = [t for t in re.split(r"[\s,;:·•|/!()\[\]]+", line) if t.strip(".-–—")]
    if not toks or len(toks) > 10:
        return False
    has_ui = False
    for t in toks:
        t = t.strip(".-–—")
        if _COUNTER.match(t):
            continue
        if not _UI_WORD.match(t):
            return False
        has_ui = has_ui or len(t) > 3
    return has_ui


def _is_low_quality(line: str) -> bool:
    """OCR debris: mostly non-letters, or no word of three letters or more."""
    chars = [c for c in line if not c.isspace()]
    if not chars:
        return True
    letters = sum(c.isalpha() for c in chars)
    alnum = sum(c.isalnum() for c in chars)
    words = _words(line)
    if not any(len(w) >= 3 for w in words):
        return True
    if alnum / len(chars) < 0.5 or letters / len(chars) < 0.3:
        return True
    singles = sum(1 for w in words if len(w) == 1)
    return len(words) >= 4 and singles / len(words) > 0.5


def line_kind(line: str) -> str | None:
    """Why a line is page metadata ('data', 'autor', 'konto', 'interfejs', 'szum'), or None when it is content."""
    s = line.strip()
    if not s:
        return "szum"
    if (
        len(s) > _MAX_META_LEN
    ):  # metadata lines are short; a long line is content (and is not run through the regexes)
        return None
    if _is_date_line(s):
        return "data"
    if _is_ui_line(s):
        return "interfejs"
    if _is_handle_line(s):
        return "konto"
    if _is_byline(s):
        return "autor"
    if _is_low_quality(s):
        return "szum"
    if len(_words(s)) < 2 and not _has_verb(s):
        return "szum"
    return None


def drop_metadata_lines(text: str) -> str:
    """The input without its metadata lines (see module doc). Single-line input and input that would lose every line
    are returned unchanged."""
    lines = [ln for ln in (text or "").split("\n")]
    if sum(1 for ln in lines if ln.strip()) < 2:
        return text
    kept = [ln for ln in lines if ln.strip() and line_kind(ln) is None]
    if not kept:
        return text
    return "\n".join(kept)
