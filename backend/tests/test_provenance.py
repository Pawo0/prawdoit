"""'Is the linked item the one a fact-checker analysed?' (provenance.py, organisers' scenario I). Model-free: the index
holds two hand-made records. Run:  backend/.venv/bin/python backend/tests/test_provenance.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401

from prawdowid import answer, provenance  # noqa: E402
from prawdowid.channels.formatting import chat_text  # noqa: E402
from prawdowid.schemas import CheckResult, SourceDoc  # noqa: E402

HEADLINE = "Premier: nie ma powodu do paniki, prognozy nie są przesadnie alarmujące"
FC = SourceDoc(id="fc1", source_type="factcheck", publisher="Demagog", domain="demagog.org.pl",
               url="https://demagog.org.pl/wypowiedzi/depesza/", title="Depesza PAP nie została usunięta",
               published_at="2024-09-16", claim="Piątkowa depesza PAP została usunięta.", verdict_raw="Fałsz",
               verdict="false",
               text=("Piątkowa depesza PAP została usunięta.\n- Polska Agencja Prasowa opublikowała po tej konferencji "
                     f"depeszę zatytułowaną: „{HEADLINE}”. Jest ona nadal dostępna."))
OTHER = SourceDoc(id="fc2", source_type="factcheck", publisher="Demagog", domain="demagog.org.pl",
                  url="https://demagog.org.pl/wypowiedzi/inna/", title="Inna analiza o powodzi",
                  published_at="2024-09-20", claim="Rząd nic nie zrobił.", verdict_raw="Fałsz", verdict="false",
                  text="Rząd nic nie zrobił. Premier zapowiedział stan klęski żywiołowej na terenach zalanych.")
Q = "Czy ten wpis dotyczy tej samej depeszy PAP, którą sprawdzał Demagog?"


class Provenance(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(provenance.INDEX, "docs", [OTHER, FC])
        p.start()
        self.addCleanup(p.stop)

    def run_q(self, title: str, day: str | None):
        c = provenance.check_linked_item(Q, {"title": title, "date": day})
        res = CheckResult(id="x", created_at="2026-11-21", channel="web", status="ok", input_kind="text",
                          input_excerpt="", claims=[c])
        answer.finalize(res)
        return c, chat_text(res)

    def test_same_headline_and_date_is_the_same_item(self):
        c, reply = self.run_q(f"{HEADLINE} | PAP", "2024-09-13")
        self.assertEqual(c.verdict, "potwierdzone")
        self.assertIn("M2:TEN_SAM_MATERIAL", c.rules_fired)
        self.assertTrue(c.short_answer.startswith("Tak, chodzi o ten sam materiał"), c.short_answer)
        self.assertIn("13 września 2024", c.short_answer)
        self.assertIn(HEADLINE, c.evidence[0].fragment)
        self.assertIn(c.evidence[0].fragment, FC.text)  # verbatim
        self.assertIn(FC.url, reply)

    def test_other_headline_same_topic_is_not_a_match(self):
        c, reply = self.run_q("Premier: rząd przygotowuje rozporządzenie o stanie klęski żywiołowej", "2024-09-16")
        self.assertEqual(c.verdict, "brak_dowodow")
        self.assertTrue(c.short_answer.startswith("Nie udało mi się potwierdzić"), c.short_answer)
        self.assertNotIn("ten sam materiał, który", c.short_answer)
        self.assertEqual(c.evidence, [])

    def test_headline_but_page_dated_after_the_analysis(self):
        c, _ = self.run_q(HEADLINE, "2024-10-30")
        self.assertEqual(c.verdict, "brak_dowodow")
        self.assertIn("nie pasuje", c.short_answer)

    def test_headline_without_a_page_date(self):
        c, _ = self.run_q(HEADLINE, None)
        self.assertEqual(c.verdict, "brak_dowodow")
        self.assertIn("nie podaje daty", c.short_answer)

    def test_question_detection(self):
        self.assertTrue(provenance.asks_same_item(Q + " https://example.org/a"))
        self.assertTrue(provenance.asks_same_item("Czy to ten sam materiał, co w analizie Demagoga?"))
        self.assertFalse(provenance.asks_same_item("Czy Wrocław był jedynym miastem? Sprawdź też tę stronę: https://x.pl"))
        self.assertFalse(provenance.asks_same_item("Co z tym artykułem? https://example.org/a"))


if __name__ == "__main__":
    unittest.main()
