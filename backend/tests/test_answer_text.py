"""Answer text (answer.py): whole-sentence quotes, the finding sentence of the fact-check, the year of old material.
Hand-built results, no models; every text is invented."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401

from prawdowid import answer  # noqa: E402
from prawdowid.schemas import CheckResult, ClaimResult, Evidence  # noqa: E402


def ev(**kw) -> Evidence:
    base = dict(doc_id="d1", title="Gmina nie zamknęła wszystkich szkół", publisher="Demagog", domain="demagog.org.pl",
                url="https://example.org/a", source_type="factcheck", tier=2, published_at="2025-05-02",
                factcheck_claim="Gmina Zielonka zamknęła wszystkie szkoły podstawowe.", factcheck_verdict_raw="Fałsz",
                factcheck_verdict="false", fragment="W rzeczywistości zamknięto jedną szkołę z trzech.",
                similarity=0.9, stance="przeczy", stance_score=0.9, same_claim=True)
    base.update(kw)
    return Evidence(**base)


def finalize(verdict: str, evidence: list[Evidence], text="Gmina Zielonka zamknęła wszystkie szkoły", **kw) -> ClaimResult:
    c = ClaimResult(claim=text, verdict=verdict, verdict_label=verdict, strength=0.6, strength_label="umiarkowana",
                    explanation="…", evidence=evidence, **kw)
    res = CheckResult(id="x", created_at="2026-01-01", channel="web", status="ok", input_kind="text", input_excerpt="",
                      claims=[c])
    answer.finalize(res)
    return c


class Quotes(unittest.TestCase):
    def test_long_quote_ends_after_a_whole_sentence(self):
        s = ("Pierwsze zdanie analizy ma dokładnie tyle słów, ile potrzeba, by coś wyjaśnić. " * 3
             + "Ostatnie zdanie jest bardzo długie i nie zmieści się już w limicie, więc zostanie pominięte w całości.")
        q = answer._q(s, answer.QUOTE_MAX)
        self.assertLessEqual(len(q), answer.QUOTE_MAX)
        self.assertTrue(s.startswith(q))
        self.assertTrue(q.endswith("wyjaśnić"))  # whole sentences (the final period is dropped inside the quote marks)

    def test_one_overlong_sentence_is_cut_at_a_word(self):
        s = "Zdanie " + "bardzo " * 80 + "długie."
        q = answer._q(s, answer.QUOTE_MAX)
        self.assertTrue(q.endswith("…"))
        self.assertLessEqual(len(q), answer.QUOTE_MAX)
        self.assertFalse(q[:-1].endswith(" "))

    def test_short_labels_unchanged(self):
        self.assertEqual(answer._q("Krótki tytuł.", 70), "Krótki tytuł")


class Finding(unittest.TestCase):
    def test_fact_check_answer_shows_the_finding(self):
        c = finalize("falszywe", [ev()])
        self.assertTrue(c.short_answer.startswith("Nie. Demagog ocenił twierdzenie „Gmina Zielonka zamknęła"))
        self.assertIn("Demagog pisze: „W rzeczywistości zamknięto jedną szkołę z trzech”.", c.short_answer)

    def test_no_finding_when_the_fragment_repeats_the_claim(self):
        c = finalize("falszywe", [ev(fragment="Gmina Zielonka zamknęła wszystkie szkoły podstawowe.")])
        self.assertNotIn("pisze:", c.short_answer)

    def test_who_checked_answer_also_shows_the_finding(self):
        c = finalize("falszywe", [ev()], text="Czy Demagog to sprawdzał? Gmina Zielonka zamknęła wszystkie szkoły")
        self.assertTrue(c.short_answer.startswith("Tak, Demagog to sprawdził"), c.short_answer)
        self.assertIn("pisze: „W rzeczywistości", c.short_answer)

    def test_official_source_quote_is_not_cut_at_170(self):
        frag = ("Liczba uczniów szkół podstawowych w gminie w roku szkolnym 2024/2025 wyniosła 1 204 osoby, "
                "o 3,1% mniej niż rok wcześniej, a liczba oddziałów spadła z 58 do 55 według danych za ostatni rok.")
        c = finalize("potwierdzone", [ev(source_type="official", tier=1, publisher="Urząd Statystyczny", stance="popiera",
                                         factcheck_claim=None, factcheck_verdict_raw=None, factcheck_verdict=None,
                                         same_claim=None, fragment=frag)])
        self.assertIn(frag.rstrip("."), c.short_answer)


class LegalText(unittest.TestCase):
    def test_clause_does_not_stop_at_article_numbering(self):
        f = "Art. 12. Rada gminy uchwala budżet do końca roku. § 2. Wójt wykonuje budżet zgodnie z uchwałą."
        self.assertEqual(answer._clause(f), "Art. 12. Rada gminy uchwala budżet do końca roku")

    def test_clause_does_not_stop_at_year_abbreviation(self):
        f = "Ustawa weszła w życie 1 stycznia 2024 r. Ministerstwo opublikowało do niej rozporządzenia wykonawcze."
        self.assertIn("Ministerstwo opublikowało", answer._clause(f))

    def test_ingest_marker_is_not_quoted(self):
        f = "[fragment: „Art. 7.”] Organy władzy działają na podstawie i w granicach prawa."
        self.assertEqual(answer._q(f, answer.QUOTE_MAX), "Organy władzy działają na podstawie i w granicach prawa")
        two = "Pierwszy wyimek ustawy jest krótki. [fragment: „Art. 9.”] Drugi wyimek ustawy jest wyraźnie dłuższy od pierwszego."
        q = answer._q(two, answer.QUOTE_MAX)
        self.assertTrue(q.startswith("Drugi wyimek") and two.find(q) > 0)  # still one verbatim slice


class Dates(unittest.TestCase):
    def test_fact_check_answer_carries_the_analysis_date(self):
        self.assertIn("(analiza z 02.05.2025)", finalize("falszywe", [ev()]).short_answer)

    def test_official_answer_carries_the_source_date(self):
        c = finalize("potwierdzone", [ev(source_type="official", tier=1, publisher="Urząd Statystyczny", stance="popiera",
                                         factcheck_claim=None, factcheck_verdict_raw=None, factcheck_verdict=None,
                                         same_claim=None, published_at="2025-07-01",
                                         fragment="Liczba uczniów w gminie wyniosła 1 204 osoby w ostatnim roku szkolnym.")])
        self.assertIn("Urząd Statystyczny (01.07.2025): „Liczba uczniów", c.short_answer)

    def test_no_date_no_brackets(self):
        self.assertNotIn("analiza z", finalize("falszywe", [ev(published_at=None)]).short_answer)


class OldMaterial(unittest.TestCase):
    def test_outdated_evidence_names_the_year(self):
        c = finalize("wprowadzajace_w_blad", [ev(stance="popiera", factcheck_verdict="true", factcheck_verdict_raw="Prawda",
                                                 published_at="2021-09-14")],
                     context_type="NIEAKTUALNE",
                     missing_context="Opisane zdarzenie/dane pochodzą z 14.09.2021, a treść przedstawia je jako bieżące.")
        self.assertTrue(c.short_answer.startswith("Częściowo. Materiał pochodzi z 2021 r."), c.short_answer)


if __name__ == "__main__":
    unittest.main()
