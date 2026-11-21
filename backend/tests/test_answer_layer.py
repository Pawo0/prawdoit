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


class LiveOutage(unittest.TestCase):
    """Scenario J: a failed live stage is visible in the reply whatever the verdict."""

    def _res(self, verdict: str, evidence: list[Evidence], status: str = "blad") -> CheckResult:
        from prawdowid.schemas import LiveSearchInfo

        res = CheckResult(id="abc", created_at="2026-11-21", channel="web", status="ok", input_kind="text",
                          input_excerpt="", claims=[claim(verdict, evidence, strength_label="umiarkowana")],
                          live_search=LiveSearchInfo(provider="google_factcheck", status=status,
                                                     notice="Indeks Google Fact Check jest teraz niedostępny (błąd techniczny)."))
        res.warnings.append(res.live_search.notice)
        answer.finalize(res)
        return res

    def test_verdict_from_local_corpus_reports_the_outage(self):
        e = ev(stance="przeczy", factcheck_claim="Wrocław jest jedynym miastem z takimi ulgami.",
               factcheck_verdict_raw="Fałsz", factcheck_verdict="false", same_claim=True, similarity=0.85)
        res = self._res("falszywe", [e])
        line = res.claims[0].limitation_line
        self.assertIn("niedostępne (błąd techniczny)", line)
        self.assertIn("bardzo podobne", line)  # the verdict's own limitation is kept
        self.assertIn("niedostępne (błąd techniczny)", chat_text(res))

    def test_no_outage_no_notice(self):
        e = ev(stance="przeczy", factcheck_claim="Wrocław jest jedynym miastem z takimi ulgami.",
               factcheck_verdict_raw="Fałsz", factcheck_verdict="false", same_claim=True, similarity=0.95)
        line = self._res("falszywe", [e], status="ok").claims[0].limitation_line
        self.assertEqual(line, "Ograniczenie: ocena opiera się na jednym źródle.")


class WhoCheckedQuestion(unittest.TestCase):
    """'Czy Demagog to sprawdzał? <claim>' asks WHETHER it was checked (organisers' scenario F)."""

    def test_question_sentence_is_kept_out_of_the_query(self):
        from prawdowid.claims import extract_claims

        for text in ("Czy Demagog to sprawdzał? Depesza PAP ze słowami premiera została usunięta! 15 września 2024",
                     "Czy Demagog to sprawdzał? Depesza PAP ze słowami premiera została usunięta!",
                     "Depesza PAP ze słowami premiera została usunięta! Czy ktoś już to zweryfikował?"):
            cs = extract_claims(text)
            self.assertEqual(len(cs), 1, text)
            self.assertEqual(cs[0].query.rstrip("!"), "Depesza PAP ze słowami premiera została usunięta", text)
            self.assertIn("Czy", cs[0].text)

    def test_not_a_who_checked_question(self):
        from prawdowid.textutil import checked_question

        self.assertEqual(checked_question("Czy Demagog to sprawdzał?"), "Demagog")
        self.assertEqual(checked_question("Czy ktoś już to zweryfikował?"), "ktoś")
        for s in ("Czy NIK zbadała wydatki?", "Czy szczepionki zawierają chipy?", "Czy to prawda?",
                  "Czy Demagog sprawdzał, czy Wrocław był jedynym miastem?"):
            self.assertIsNone(checked_question(s), s)

    def test_answer_opens_with_yes_it_was_checked(self):
        e = ev(stance="przeczy", factcheck_claim="Depesza PAP została usunięta.", factcheck_verdict_raw="Fałsz",
               factcheck_verdict="false", same_claim=True, similarity=0.9)
        c = claim("falszywe", [e], text="Czy Demagog to sprawdzał? Depesza PAP została usunięta!",
                  strength_label="umiarkowana")
        result(c)
        self.assertTrue(c.short_answer.startswith("Tak, Demagog to sprawdził i ocenił"), c.short_answer)


class AskedNumber(unittest.TestCase):
    """'Czy X wydaje około 700 mln zł? Dlaczego w analizie Demagoga jest 650 mln zł?' (organisers' scenario C)."""

    CLAIM = ("To rezygnacja z przychodów z tytułu biletów, a to jest w 7 mld budżecie naprawdę skromna kwota – 200 mln "
             "zł około. Natomiast MPK [we Wrocławiu – przyp. Demagog] i tak nas kosztuje bodajże ok. 700 mln zł.")
    TEXT = (CLAIM + "\n- W 2023 roku do budżetu Wrocławia wpłynęło 207,9 mln zł z tytułu sprzedaży biletów na transport "
            "miejski, co stanowiło 3,3 proc. dochodów budżetowych (6,38 mld zł).\n- Z miejskiej kasy na transport "
            "zbiorowy przeznaczono 650 mln zł. Wpływy z biletów pozwalały więc kompensować ok. ⅓ wydatków.")

    def test_engine_quotes_the_passage_with_the_asked_number_and_its_year(self):
        from prawdowid.engine import asked_number_fragment
        from prawdowid.textutil import amounts

        frag = asked_number_fragment(self.TEXT, self.CLAIM, amounts("Dlaczego jest 650 mln zł?"))
        self.assertIn("650 mln zł", frag)
        self.assertIn("2023", frag)  # the neighbouring sentence that states the period
        self.assertIsNone(asked_number_fragment(self.TEXT, self.CLAIM, amounts("Dlaczego jest 900 mln zł?")))

    def test_answer_explains_both_figures_from_the_evidence(self):
        frag = "W 2023 roku do budżetu wpłynęło 207,9 mln zł. - Z miejskiej kasy na transport zbiorowy przeznaczono 650 mln zł."
        e = ev(factcheck_claim=self.CLAIM, factcheck_verdict_raw="Częściowa prawda", factcheck_verdict="mixed",
               fragment=frag)
        meta = "Dlaczego w analizie Demagoga jest 650 mln zł?"
        c = claim("brak_dowodow", [e], text=f"Czy Wrocław wydaje na komunikację około 700 mln zł. {meta}",
                  meta_question=meta)
        reply = chat_text(result(c))
        a = c.short_answer
        self.assertTrue(a.startswith("700 mln zł to przybliżona kwota z ocenianej wypowiedzi"), a)
        self.assertIn("650 mln zł", a)
        self.assertIn("2023", a)
        self.assertIn("Te liczby sobie nie przeczą — mierzą co innego", a)
        self.assertIn("„Częściowa prawda”", a)
        self.assertEqual(c.related_evidence, 0)
        self.assertIn(e.url, reply)

    def test_no_meta_question_no_explanation(self):
        e = ev(factcheck_claim=self.CLAIM, factcheck_verdict_raw="Częściowa prawda", factcheck_verdict="mixed",
               fragment="Z miejskiej kasy na transport zbiorowy przeznaczono 650 mln zł.")
        c = claim("brak_dowodow", [e], text="Czy Wrocław wydaje na komunikację około 700 mln zł?")
        result(c)
        self.assertNotIn("sprzeczne pomiary", c.short_answer)


if __name__ == "__main__":
    unittest.main()
