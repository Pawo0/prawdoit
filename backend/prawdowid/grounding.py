"""Conservative checks on the displayed evidence, separate from claim matching.

A rating for a similar claim is not proof that the selected quote supports the
answer. These guards run before verdict rules; independent evaluation remains
in eval/citations and never consumes these model scores as ground truth.
"""

from __future__ import annotations

import math
import re

from .agreement import names_disagree
from .textutil import amounts, split_sentences, years_in

_REPORT = re.compile(
    r"\b(?:internau\w*|rzekom\w*|sugeruj\w*|twierdz\w*|przekonuj\w*|"
    r"(?:wpis|post|film|zdjęcie)\w*[^.!?]{0,80}(?:oburzeni\w*|krąży\w*|udostępni\w*)|"
    r"w (?:sieci|mediach społecznościowych)|(?:poinformowa|stwierdzi|zaznaczy)\w*|tweeterowicz\w*)\b",
    re.I,
)
_CORRECTION = re.compile(
    r"\b(?:w rzeczywistości|wbrew|nieprawd\w*|fałsz\w*|nie (?:ma|jest|są|był\w*|został\w*|dotycz\w*|powiedział\w*|mówił\w*|przewiduje|oznacza)|"
    r"zaprzecz\w*|zdementowa\w*|dementuj\w*|pochodzi\w*|archiwaln\w*)\b",
    re.I,
)


def has_finding(fragment: str) -> bool:
    """A question or a report of a viral allegation cannot establish that allegation.

    A neighbouring correction can supply the finding. This is only a negative
    filter; passing it still requires semantic verification against the claim.
    """
    return any(
        not sentence.rstrip(' ”"').endswith("?")
        and not re.fullmatch(r"(?:wyjaśniamy|sprawdzamy)[.!]?", sentence.strip(), re.I)
        and (not _REPORT.search(sentence) or _CORRECTION.search(sentence))
        for sentence in split_sentences(fragment)
    )


def _quantities(text: str) -> list[tuple]:
    # amounts() intentionally parses only quantities with recognised units.
    # Plain counts, years and percentages with no space need witnesses too.
    numbers = re.findall(r"(?<![\w])(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:[.,]\d+)?", text)
    return amounts(text) + [
        (float(re.sub(r"\s+", "", n).replace(",", ".")), "", n) for n in numbers
    ]


def numeric_support_complete(claim: str, fragment: str) -> bool:
    """Every explicit quantity of a confirmed claim must occur in its evidence.

    Unlike approximate retrieval matching, quotation grounding does not silently
    round a percentage. Units remain distinct (53 seats is not 53 percent).
    This checks necessary numeric witnesses, not their semantic relationship.
    """
    found = _quantities(fragment)
    return all(
        any(a[1] == b[1] and math.isclose(a[0], b[0], rel_tol=1e-9, abs_tol=1e-9) for b in found)
        for a in _quantities(claim)
    )


def comparable_scope(claim: str, fragment: str) -> bool:
    """Do not turn another named subject or disjoint period into a contradiction."""
    # An unresolved "our country" is not evidence about the named destination
    # of the user's claim. The publisher's address cannot supply that scope.
    if re.search(r"\b(?:do naszego kraju|w naszym kraju|u nas|w tym kraju)\b", fragment, re.I):
        return False
    left, right = set(years_in(claim)), set(years_in(fragment))
    if left and right and not left.intersection(right):
        return False
    return names_disagree(claim, fragment) is None


def has_numeric_comparison(claim: str, fragment: str) -> bool:
    """'Many people' does not contradict a stated count, even when NLI says so.

    A numeric contradiction needs a comparable quantity or an explicit denial.
    Exact same values can still be contradicted by negation or other facts.
    """
    rate_claim = re.search(r"\bna\s+\d+|\bw przeliczeniu|\brazy\b", claim, re.I)
    if rate_claim and not re.search(
        r"\bna\s+\d+|\bwskaźnik\w*|\bodset\w*|\bw przeliczeniu|\brazy\b", fragment, re.I
    ):
        return False
    asked = amounts(claim) or [a for a in _quantities(claim) if not (1900 <= a[0] <= 2099)]
    return (
        not asked
        or any(a[1] == b[1] for a in asked for b in _quantities(fragment))
        or bool(_CORRECTION.search(fragment))
    )
