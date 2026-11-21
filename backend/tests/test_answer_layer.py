"""Short-answer layer (answer.py) and the chat rendering (channels/formatting.py) on hand-built results. No models.
Run:  backend/.venv/bin/python backend/tests/test_answer_layer.py      (or pytest backend/tests)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401  (isolated runtime directory before prawdowid is imported)

from prawdowid import answer  # noqa: E402
from prawdowid.channels.formatting import chat_text  # noqa: E402
from prawdowid.schemas import CheckResult, ClaimResult, Evidence  # noqa: E402


def ev(**kw) -> Evidence:
    base = dict(doc_id="d1", title="Tytuł", publisher="Demagog", domain="demagog.org.pl", url="https://example.org/a",
                source_type="factcheck", tier=2, published_at="2024-03-12", fragment="Fragment źródła o mieście.",
                similarity=0.8, stance="kontekst")
    base.update(kw)
    return Evidence(**base)


def claim(verdict: str, evidence: list[Evidence], text: str = "Czy Wrocław był jedynym miastem z darmowymi przejazdami?",
          **kw) -> ClaimResult:
    kw.setdefault("strength_label", "niewystarczająca")
    return ClaimResult(claim=text, verdict=verdict, verdict_label=verdict, strength=0.0, explanation="…",
                       evidence=evidence, **kw)


def result(*claims: ClaimResult) -> CheckResult:
    res = CheckResult(id="abc", created_at="2026-11-21", channel="web", status="ok", input_kind="text", input_excerpt="",
                      claims=list(claims))
    answer.finalize(res)
    return res


class RelatedMaterial(unittest.TestCase):
    def test_unmatched_factcheck_is_named_without_its_rating(self):
        other = ev(title="Wydatki na komunikację publiczną. Wrocław daleko w tyle",
                   factcheck_claim="Warszawa 2 razy więcej wydaje na komunikację publiczną per capita.",
                   factcheck_verdict_raw="Fałsz", factcheck_verdict="false",
                   fragment="Warszawa 2 razy więcej wydaje na komunikację publiczną per capita niż Wrocław, jedyne "
                            "miasto, które wydaje mniej.")
        c = claim("brak_dowodow", [other], reason_codes=["TYLKO_MATERIALY_POKREWNE"])
        res = result(c)
        self.assertTrue(c.short_answer.startswith("Nie udało mi się"))
        self.assertNotIn("Fałsz", c.short_answer)  # the rating of ANOTHER claim is not attached to an abstention
        self.assertNotIn("ocenił", c.short_answer)
        self.assertIn("Wrocław daleko w tyle", c.short_answer)
        self.assertEqual(c.related_evidence, 0)
        reply = chat_text(res)
        self.assertIn("Materiał pokrewny (nie rozstrzyga): Demagog", reply)
        self.assertIn(other.url, reply)
        self.assertNotIn("Źródło:", reply)

    def test_official_related_item_is_quoted_and_linked(self):
        notice = ev(source_type="official", tier=1, publisher="Ministerstwo Spraw Zagranicznych",
                    domain="odyseusz.gov.pl", url="https://odyseusz.gov.pl/IT", title="Włochy: komunikat MSZ",
                    fragment="W dniu 20 listopada we Włoszech zapowiedziano strajk generalny.", similarity=0.8)
        c = claim("brak_dowodow", [notice], text="Czy we Włoszech odbywał się strajk generalny?")
        reply = chat_text(result(c))
        self.assertIn("zapowiedziano strajk generalny", c.short_answer)
        self.assertIn("https://odyseusz.gov.pl/IT", reply)

    def test_no_related_item_no_source_line(self):
        c = claim("brak_dowodow", [], text="Czy od wczoraj w Pcimiu bilety autobusowe można kupić tylko przez aplikację?")
        reply = chat_text(result(c))
        self.assertIsNone(c.related_evidence)
        self.assertNotIn("Materiał pokrewny", reply)

    def test_verdict_keeps_the_decisive_source_line(self):
        e = ev(stance="przeczy", factcheck_claim="Wrocław jest jedynym miastem z takimi ulgami.",
               factcheck_verdict_raw="Fałsz", factcheck_verdict="false", same_claim=True, similarity=0.9)
        c = claim("falszywe", [e], strength_label="umiarkowana")
        reply = chat_text(result(c))
        self.assertIsNone(c.related_evidence)
        self.assertIn("Źródło: Demagog", reply)


if __name__ == "__main__":
    unittest.main()
