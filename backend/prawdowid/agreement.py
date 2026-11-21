"""Do two texts name different things or give different numbers? Deterministic, no model, no dictionary of names.

Used by engine.same_claim. Embedding similarity cannot tell "Tarczyński debated Tusk" from "Tarczyński debated
Trzaskowski" (cosine 0.93), so when the user's text and the fact-checked claim DISAGREE on a name or a number, a match
may no longer rest on similarity alone (research/05 §2.2 item 5, research/08 §4 and §11).

Disagreement is always two-sided:
  * a name or number that only ONE text has is an omission or an addition ("Tusk" for "Donald Tusk", a claim
    shortened to its first half) and says nothing;
  * each text having one that the other lacks is a substitution.

NAMES have aliases ("na Narodowym" for "w Warszawie", "Polacy" for "w Polsce"), so two unmatched names count as a
substitution only when they stand in the same place: the content word right before them and the content word right
after them are the same in both texts ("… się z [X] w debacie …"). What is a name is read from capital letters:
  * sure  — a capitalised word inside a sentence, an acronym (NATO, UE), a run of capitalised words (Donald Tusk);
  * maybe — the first word of a sentence (capitalised whatever it is), and any word of a text that carries no
            capitalisation signal at all (typed in lower case, or in capitals throughout);
  * no    — a lower-case word in a text that does use capitals ("z premierem" for "z Donaldem Tuskiem" is fine).
A substitution needs an unmatched name on both sides, and at least one of the two must be a sure name.

NUMBERS have one value however they are written (250 tys., 250 000, ćwierć miliona), so two unmatched numbers are a
disagreement wherever they stand. A bound ("ponad 90%", "prawie 2 tys.") agrees with the numbers it admits.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .textutil import STOP, split_sentences, strip_pl

ALTERNATIONS = (("sz", "ch"), ("cz", "c"), ("rz", "r"))  # Włochy → Włoszech, Niemcy → Niemczech, Węgry → Węgrzech

_LETTERS = re.compile(r"[^\W\d_]+")
_TOKEN = re.compile(r"[^\W\d_]+|\d+(?:[.,]\d+)?")
_EDITOR_NOTE = re.compile(r"[–—-]?\s*przyp\.\s*[^\W\d_]+\.?", re.I)  # "[w Krakowie – przyp. Demagog]": not part of the claim
_OPENER = re.compile(r"(?:[:„«“\"(\[]|(?:^|\s)[–—-])\s*$")  # a word right after one of these starts a clause or quote
_VOWELS = "aeiouy"
_PL_DIACRITIC = re.compile(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
_WS = re.compile(r"\s*")
_STOP_PLAIN = {strip_pl(w) for w in STOP}  # "sie", "ze", "byl": stop words as typed without diacritics


# ------------------------------------------------------------------------------------------------ word matching
def fold(word: str) -> str:
    """Lower case, no diacritics, stem-consonant alternations undone — the form in which two words are compared."""
    w = strip_pl(word)
    for a, b in ALTERNATIONS:
        w = w.replace(a, b)
    return w


def _osa(a: str, b: str) -> int:
    """Optimal string alignment distance (insert, delete, substitute, swap two neighbours)."""
    prev2, prev = None, list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            if prev2 is not None and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        prev2, prev = prev, cur
    return prev[-1]


def _one_swap(a: str, b: str) -> bool:
    """b is a with two neighbouring letters swapped."""
    if len(a) != len(b):
        return False
    d = [i for i in range(len(a)) if a[i] != b[i]]
    return len(d) == 2 and d[1] == d[0] + 1 and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]]


def same_word(a: str, b: str) -> bool:
    """Are two FOLDED words forms of the same word? Tolerant of inflection and of one typing error.
      1. the same first four letters (Tusk/Tuskiem, Polska/Polsce, Trzaskowski/Trzaskowskim, ukraiński/Ukraina);
      2. short words: equal after dropping one final vowel, or one is the beginning of the other (Duda/Dudy,
         Unia/Unii, PiS/PiS-u) — Iran/Irak stay different;
      3. one typing error in a word of six letters or more (Ukriany/Ukrainy, Gabard/Gabbard); in a shorter word only
         two swapped neighbouring letters (Tuksa/Tuska), because one changed letter is enough to make another short
         name (Iranu/Iraku)."""
    if a == b:
        return True
    if min(len(a), len(b)) >= 4 and a[:4] == b[:4]:
        return True
    sa = a[:-1] if a[-1:] in _VOWELS else a
    sb = b[:-1] if b[-1:] in _VOWELS else b
    if min(len(sa), len(sb)) >= 3 and (sa.startswith(sb) or sb.startswith(sa)):
        return True
    if min(len(a), len(b)) >= 6:
        return abs(len(a) - len(b)) <= 1 and _osa(a, b) <= 1
    return min(len(a), len(b)) >= 4 and _one_swap(a, b)


# ------------------------------------------------------------------------------------------------ names
@dataclass
class _Tok:
    text: str
    folded: str
    number: bool
    content: bool  # a number, or a word that is not a stop word


@dataclass
class _Unit:
    """A name (or a word that may be one) with the content words that stand right before and right after it."""
    words: list[str]
    sure: bool
    left: _Tok | None
    right: _Tok | None

    def label(self) -> str:
        return " ".join(self.words)


@dataclass
class _Side:
    sentences: list[list[_Tok]] = field(default_factory=list)
    folded: list[str] = field(default_factory=list)  # every word of the text, folded
    raw: list[str] = field(default_factory=list)  # every word, lower case (for acronym initials)
    signal: bool = False  # does the text use capital letters selectively?
    groups: list[tuple[int, int, int, bool]] = field(default_factory=list)  # (sentence, first, last, sure)


def _clean(text: str) -> str:
    return _EDITOR_NOTE.sub(" ", text or "")


def _read(text: str) -> _Side:
    side = _Side()
    sentences = split_sentences(_clean(text))
    words = [m.group(0) for s in sentences for m in _LETTERS.finditer(s)]
    side.raw = [w.lower() for w in words]
    side.folded = [fold(w) for w in words]
    # capitalisation is a signal only when it is selective: some words start with a capital, some do not
    side.signal = any(w[0].isupper() for w in words) and any(w[0].islower() for w in words)
    for si, s in enumerate(sentences):
        toks: list[_Tok] = []
        group: list[int] = []
        sure, prev_end = False, -1
        for m in _TOKEN.finditer(s):
            w = m.group(0)
            number = w[0].isdigit()
            toks.append(_Tok(w, w.replace(",", ".") if number else fold(w), number,
                             number or (len(w) >= 3 and strip_pl(w) not in _STOP_PLAIN)))
            is_name = (side.signal and not number and w[0].isupper() and strip_pl(w) not in _STOP_PLAIN
                       and (len(w) >= 3 or (w.isupper() and len(w) >= 2)))
            adjacent = bool(group) and re.fullmatch(r"\s+|-", s[prev_end:m.start()]) is not None
            if group and not (is_name and adjacent):
                side.groups.append((si, group[0], group[-1], sure or len(group) > 1))
                group, sure = [], False
            if is_name:
                first_in_clause = not any(not t.number for t in toks[:-1]) or _OPENER.search(s[:m.start()]) is not None
                sure = sure or not first_in_clause or (w.isupper() and len(w) >= 2)
                group.append(len(toks) - 1)
            prev_end = m.end()
        if group:
            side.groups.append((si, group[0], group[-1], sure or len(group) > 1))
        side.sentences.append(toks)
    return side


def _mentioned(folded: str, other: _Side) -> bool:
    return any(same_word(folded, o) for o in other.folded)


def _initials_present(letters: str, other: _Side) -> bool:
    """UE ↔ Unia Europejska: `letters` are spelled by the initials of consecutive words of the other text."""
    n, raw = len(letters), other.raw
    return n >= 2 and any("".join(w[0] for w in raw[i:i + n]) == letters for i in range(len(raw) - n + 1))


def _group_mentioned(words: list[str], other: _Side) -> bool:
    """A name of several words is mentioned if its last word is (people are referred to by surname alone), or if
    the other text uses its acronym, or — for an acronym — its expansion."""
    if _mentioned(fold(words[-1]), other):
        return True
    if len(words) >= 2 and "".join(w[0] for w in words).lower() in other.raw:
        return True
    return len(words) == 1 and words[0].isupper() and _initials_present(words[0].lower(), other)


def _unit(toks: list[_Tok], first: int, last: int, sure: bool) -> _Unit:
    left = next((toks[k] for k in range(first - 1, -1, -1) if toks[k].content), None)
    right = next((toks[k] for k in range(last + 1, len(toks)) if toks[k].content), None)
    return _Unit([t.text for t in toks[first:last + 1]], sure, left, right)


def _unmatched_units(side: _Side, other: _Side) -> list[_Unit]:
    """Names of `side` that `other` does not mention, each with its neighbouring content words."""
    out = []
    if side.signal:
        for si, first, last, sure in side.groups:
            toks = side.sentences[si]
            if not _group_mentioned([t.text for t in toks[first:last + 1]], other):
                out.append(_unit(toks, first, last, sure))
        return out
    # no capitalisation signal: every run of content words that the other text does not have may be a name
    for toks in side.sentences:
        run: list[int] = []
        for k, t in enumerate(toks + [None]):
            new = t is not None and t.content and not t.number and not _mentioned(t.folded, other)
            if new:
                run.append(k)
            elif run and (t is None or t.content):
                out.append(_unit(toks, run[0], run[-1], False))
                run = []
    return out


def _same_neighbour(a: _Tok | None, b: _Tok | None) -> bool:
    if a is None or b is None:
        return a is None and b is None  # both at the edge of their sentence
    if a.number or b.number:
        return a.number and b.number and a.folded == b.folded
    return same_word(a.folded, b.folded)


def names_disagree(user_text: str, checked_claim: str) -> tuple[str, str] | None:
    """(name in the user's text, name in the checked claim) if the claim's name is replaced by another in the same
    place, else None. See the module docstring for the rule."""
    u, c = _read(user_text), _read(checked_claim)
    cu = _unmatched_units(c, u)
    if not cu:
        return None
    for a in _unmatched_units(u, c):
        for b in cu:
            if (a.sure or b.sure) and _same_neighbour(a.left, b.left) and _same_neighbour(a.right, b.right):
                return a.label(), b.label()
    return None


# ------------------------------------------------------------------------------------------------ numbers
_MAGNITUDE = {"tys": 1e3, "tysiac": 1e3, "tysiaca": 1e3, "tysiace": 1e3, "tysiecy": 1e3, "tysiacom": 1e3, "tysiacami": 1e3,
              "tysiacach": 1e3, "mln": 1e6, "milion": 1e6, "miliona": 1e6, "miliony": 1e6, "milionow": 1e6,
              "milionom": 1e6, "milionami": 1e6, "milionach": 1e6, "mld": 1e9, "miliard": 1e9, "miliarda": 1e9,
              "miliardy": 1e9, "miliardow": 1e9, "miliardom": 1e9, "miliardami": 1e9, "miliardach": 1e9,
              "bln": 1e12, "bilion": 1e12, "biliona": 1e12, "biliony": 1e12, "bilionow": 1e12}
_STANDALONE_MAGNITUDE = {"tysiac": 1e3, "milion": 1e6, "miliard": 1e9, "bilion": 1e12}  # "tysiąc dni"; "tysiące" is vague
_FRACTION = {"pol": 0.5, "cwierc": 0.25, "poltora": 1.5, "poltorej": 1.5}  # only before a magnitude word
_NUMERALS: dict[str, int] = {}
for _value, _forms in {
    2: "dwa dwie dwóch dwu dwoma dwiema dwaj dwoje dwojga", 3: "trzy trzech trzem trzema trzej troje trojga",
    4: "cztery czterech czterem czterema czterej czworo", 5: "pięć pięciu pięcioma", 6: "sześć sześciu sześcioma",
    7: "siedem siedmiu siedmioma", 8: "osiem ośmiu ośmioma", 9: "dziewięć dziewięciu dziewięcioma",
    10: "dziesięć dziesięciu dziesięcioma", 11: "jedenaście jedenastu", 12: "dwanaście dwunastu",
    13: "trzynaście trzynastu", 14: "czternaście czternastu", 15: "piętnaście piętnastu", 16: "szesnaście szesnastu",
    17: "siedemnaście siedemnastu", 18: "osiemnaście osiemnastu", 19: "dziewiętnaście dziewiętnastu",
    20: "dwadzieścia dwudziestu", 30: "trzydzieści trzydziestu", 40: "czterdzieści czterdziestu",
    50: "pięćdziesiąt pięćdziesięciu", 60: "sześćdziesiąt sześćdziesięciu", 70: "siedemdziesiąt siedemdziesięciu",
    80: "osiemdziesiąt osiemdziesięciu", 90: "dziewięćdziesiąt dziewięćdziesięciu", 100: "sto stu",
    200: "dwieście dwustu", 300: "trzysta trzystu", 400: "czterysta czterystu", 500: "pięćset pięciuset",
    600: "sześćset sześciuset", 700: "siedemset siedmiuset", 800: "osiemset ośmiuset", 900: "dziewięćset dziewięciuset",
}.items():
    for _f in _forms.split():
        _NUMERALS[_f] = _value
# "jeden" is left out on purpose: it is mostly a determiner ("jeden z posłów"), not a quantity.
_NUMERALS_PLAIN = {strip_pl(k): v for k, v in _NUMERALS.items()}  # for text typed without diacritics ("osmiu")

_UNITS = (("%", re.compile(r"%|proc\b\.?|procent\w*|pkt\.?\s*proc\b\.?")),
          ("zł", re.compile(r"zł\b|zl\b|złot\w*|zlot\w*|pln\b")),
          ("eur", re.compile(r"euro\b|eur\b|€")), ("usd", re.compile(r"dolar\w*|usd\b|\$")),
          ("gbp", re.compile(r"funt\w*|gbp\b")), ("chf", re.compile(r"frank\w*|chf\b")))
_DATE = re.compile(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.((?:19|20)\d\d)(?!\d)|(?<!\d)((?:19|20)\d\d)-(\d\d)-(\d\d)(?!\d)")
# a number written in digits: "250 000", "250.000", "2,7", "15" — not the digits of a name such as COVID-19, F-16, A4
_DIGITS = re.compile(r"(?<![^\W_])(?<![^\W\d_]-)(\d{1,3}(?:[  .]\d{3})+(?![\d,])|\d+(?:[.,]\d+)?)")
_NEXT_WORD = re.compile(r"\s*([^\W\d_]+)\.?")
# words that turn the number after them into a bound
_BOUND = re.compile(r"(?<![^\W\d_])(?:(ponad|powyżej|powyzej|przeszło|przeszlo|przynajmniej|minimum|więcej niż|wiecej niz|"
                    r"co najmniej|nie mniej niż|nie mniej niz)"
                    r"|(poniżej|ponizej|niespełna|niespelna|prawie|blisko|niemal|maksymalnie|mniej niż|mniej niz|"
                    r"nie więcej niż|nie wiecej niz))\s+$")
_ABBREVIATED = {"tys", "mln", "mld", "bln"}

Quantity = tuple[float, "str | None", str]  # value, unit ("%", currency code, None), bound (">", "<", "")


def _unit_at(low: str, pos: int) -> tuple[str | None, int]:
    start = _WS.match(low, pos).end()
    for kind, rx in _UNITS:
        u = rx.match(low, start)
        if u:
            return kind, u.end()
    return None, pos


def _bound_before(low: str, pos: int) -> str:
    m = _BOUND.search(low[max(0, pos - 24):pos])
    return "" if not m else ">" if m.group(1) else "<"


def quantities(text: str) -> list[Quantity]:
    """Numbers stated in a text as (value, unit, bound): digits with thousands separators and decimal commas, magnitude
    words (tys., mln, mld), Polish numerals written out (osiem, dwudziestu pięciu, pół miliona), dates as day and
    year. Unit is "%", a currency code, or None when the text gives none; bound is ">" after "ponad", "<" after
    "prawie", else ""."""
    low = _clean(text).lower()
    out: list[Quantity] = []

    def _date(m: re.Match) -> str:
        day, year = (m.group(1), m.group(3)) if m.group(1) else (m.group(6), m.group(4))
        out.extend([(float(int(day)), None, ""), (float(year), None, "")])
        return " " * (m.end() - m.start())

    low = _DATE.sub(_date, low)
    taken: list[tuple[int, int]] = []
    for m in _DIGITS.finditer(low):
        raw = m.group(1)
        grouped = re.fullmatch(r"\d{1,3}(?:[  .]\d{3})+", raw) is not None
        value = float(re.sub(r"[  .]", "", raw)) if grouped else float(raw.replace(",", "."))
        end = m.end()
        w = _NEXT_WORD.match(low, end)
        mag = strip_pl(w.group(1)) if w else ""
        # "w 2023 tysiące osób…": a year followed by a magnitude word written out is not "2023 thousand"
        if mag in _MAGNITUDE and (mag in _ABBREVIATED or not (not grouped and raw.isdigit() and 1900 <= value <= 2100)):
            value *= _MAGNITUDE[mag]
            end = w.end()
        unit, end = _unit_at(low, end)
        out.append((value, unit, _bound_before(low, m.start())))
        taken.append((m.start(), end))
    # numerals written out; a text with no diacritics at all is read as typed without them ("piec" = pięć)
    numerals = _NUMERALS if _PL_DIACRITIC.search(low) else _NUMERALS_PLAIN
    words = [(m.group(0), m.start(), m.end()) for m in _LETTERS.finditer(low)
             if not any(a <= m.start() < b for a, b in taken)]
    i = 0
    while i < len(words):
        w, start, end = words[i]
        plain = strip_pl(w)
        if plain in _STANDALONE_MAGNITUDE:
            out.append((_STANDALONE_MAGNITUDE[plain], _unit_at(low, end)[0], _bound_before(low, start)))
            i += 1
            continue
        if w in numerals:
            value = float(numerals[w])
            # "dwadzieścia pięć", "sto dwadzieścia": add a directly following numeral of a lower order
            while i + 1 < len(words) and words[i + 1][0] in numerals and low[end:words[i + 1][1]].isspace():
                cur, nxt = numerals[words[i][0]], numerals[words[i + 1][0]]
                if not (cur % 10 == 0 and cur != 10 and len(str(nxt)) < len(str(cur))):
                    break
                i += 1
                end = words[i][2]
                value += nxt
            fraction = False
        elif plain in _FRACTION:
            value, fraction = _FRACTION[plain], True
        else:
            i += 1
            continue
        nxt_w = words[i + 1] if i + 1 < len(words) else None
        if nxt_w is not None and strip_pl(nxt_w[0]) in _MAGNITUDE and low[end:nxt_w[1]].isspace():
            value *= _MAGNITUDE[strip_pl(nxt_w[0])]
            end = nxt_w[2] + (1 if low[nxt_w[2]:nxt_w[2] + 1] == "." else 0)
            fraction = False
            i += 1
        if not fraction:  # "pół roku" is not a number we compare
            out.append((value, _unit_at(low, end)[0], _bound_before(low, start)))
        i += 1
    return out


def _admits(q: Quantity, other: Quantity) -> bool:
    """Does `q` agree with `other`? Equal values, or `q` is a bound that `other` satisfies. Units must not conflict
    (a missing unit conflicts with nothing: "2,8 mld" = "2,8 mld zł"). A bound reaches one step of its own leading
    digit: "ponad 90%" admits up to 100%, "ponad 250 tys." up to 350 tys., "prawie 2 tys." down to 1 tys."""
    if not (q[1] == other[1] or q[1] is None or other[1] is None):
        return False
    if abs(q[0] - other[0]) <= 1e-9 * max(1.0, abs(q[0])):
        return True
    if not q[2] or q[0] <= 0:
        return False
    step = 10.0 ** math.floor(math.log10(q[0]))
    return q[0] < other[0] <= q[0] + step if q[2] == ">" else q[0] - step <= other[0] < q[0]


def _fmt(q: Quantity) -> str:
    v = f"{q[0]:.10g}".replace(".", ",")
    return f"{v} {q[1]}" if q[1] else v


def numbers_disagree(user_text: str, checked_claim: str) -> tuple[list[str], list[str]] | None:
    """(numbers only in the user's text, numbers only in the checked claim) if EACH text states a number the other
    does not, else None. A number missing on one side only is an omission, not a disagreement."""
    uq, cq = quantities(user_text), quantities(checked_claim)
    u_only = [q for q in uq if not any(_admits(q, x) or _admits(x, q) for x in cq)]
    c_only = [q for q in cq if not any(_admits(q, x) or _admits(x, q) for x in uq)]
    if u_only and c_only:
        return list(dict.fromkeys(_fmt(q) for q in u_only)), list(dict.fromkeys(_fmt(q) for q in c_only))
    return None


def disagreement(user_text: str, checked_claim: str) -> str | None:
    """Plain-Polish note for the audit trail if the two texts name different things or give different numbers."""
    parts = []
    names = names_disagree(user_text, checked_claim)
    if names:
        parts.append(f"nazwy: „{names[0]}” zamiast „{names[1]}”")
    nums = numbers_disagree(user_text, checked_claim)
    if nums:
        parts.append(f"liczby: {', '.join(nums[0][:3])} zamiast {', '.join(nums[1][:3])}")
    return "; ".join(parts) or None


# ------------------------------------------------------------------------------------------------ specificity
# Which of several sources that decide a claim is about THIS claim, not only a similar one? Count the concrete details
# of the user's text (who, where, what kind of event, what kind of material, when) that the source also states. Only
# agreement counts: a source that gives another date is not penalised, because an analysis of old material presented
# as new states exactly that other date.
_MEDIA = [re.compile(rx, re.I) for rx in (
    r"\b(film\w*|nagra[nńl]\w*|wideo|video|klip\w*|transmisj\w*)",
    r"\b(zdjęci\w*|zdjec\w*|fotografi\w*|fotk\w*)",
    r"\b(grafik\w*|infografik\w*|mem(y|ów|ow|a|ie)?\b|plakat\w*)",
    r"\b(zrzut\w* ekranu|screen\w*)",
    r"\b(wpis\w*|post(y|a|u|ów|ow|em|cie)?\b|tweet\w*|twee?t\w*)",
    r"\b(artykuł\w*|artykul\w*|depesz\w*)",
)]
_EVENTS = [re.compile(rx, re.I) for rx in (
    r"\b(protest\w*|manifestac\w*|demonstrac\w*|strajk\w*|marsz(u|em|e|ach|ów|ow)?\b|blokad\w*)",
    r"\b(wybor\w*|wybór|głosowa\w*|glosowa\w*|referend\w*|frekwencj\w*)",
    r"\b(powód\w*|powodz\w*|pożar\w*|pozar\w*|katastrof\w*|trzęsieni\w*|trzesieni\w*|huragan\w*|wichur\w*)",
    r"\b(atak\w*|zamach\w*|ostrzał\w*|ostrzal\w*|bombard\w*|inwazj\w*|dron\w*|rakiet\w*)",
    r"\b(wypadek|wypadk\w*|zderzeni\w*|kolizj\w*)",
    r"\b(epidemi\w*|pandemi\w*|szczepi\w*)",
    r"\b(koncert\w*|festiwal\w*|uroczystoś\w*|uroczystos\w*|obchody|obchodów|rocznic\w*)",
)]
_YEAR_RX = re.compile(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)")


def specificity(user_text: str, source_text: str) -> int:
    """Number of the user's concrete details the source states too: each name (actor or place) it mentions, the
    kind of event and the kind of material when both texts name one of the same kind, each year both give."""
    u, s = _read(user_text), _read(source_text)
    n = sum(1 for si, first, last, sure in u.groups if sure
            and _group_mentioned([t.text for t in u.sentences[si][first:last + 1]], s))
    for kinds in (_MEDIA, _EVENTS):
        n += sum(1 for rx in kinds if rx.search(user_text) and rx.search(source_text))
    n += len(set(_YEAR_RX.findall(user_text)) & set(_YEAR_RX.findall(source_text)))
    return n
