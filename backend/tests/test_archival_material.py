"""Rule R3a: old material presented as current (organisers' scenario B). Pure text, no models.
Run:  backend/.venv/bin/python backend/tests/test_archival_material.py      (or pytest backend/tests)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401

from prawdowid import answer  # noqa: E402
from prawdowid.engine import archival_origin, presented_year  # noqa: E402
from prawdowid.schemas import CheckResult, ClaimResult, Evidence, SourceDoc  # noqa: E402

DOC = SourceDoc(
    id="fc", source_type="factcheck", publisher="Demagog", domain="demagog.org.pl", url="https://demagog.org.pl/x/",
    title="Policja zasłania protestujących parawanem? Poseł udostępnia stare nagranie", published_at="2026-09-17",
    claim="Policja zasłania protestujących pod Trybunałem Konstytucyjnym parawanem. W jakim kraju my żyjemy?!",
    verdict="false", verdict_raw="Fałsz",
    text=("Policja zasłania protestujących pod Trybunałem Konstytucyjnym parawanem. W jakim kraju my żyjemy?!\n"
          "- Nagranie, które Jan Kowalski zamieścił w mediach społecznościowych, przedstawia policjantów z parawanem "
          "przed Trybunałem Konstytucyjnym. Materiał nie dotyczy jednak aktualnych wydarzeń – pochodzi z marca 2021 "
          "roku.\n- Nagranie nie przedstawia działań obecnego rządu."))
Q = "film udostępniony przez Jana Kowalskiego w 2026 r. pokazywał ówczesny protest pod Trybunałem Konstytucyjnym"


class ArchivalMaterial(unittest.TestCase):
    def test_presented_year(self):
        self.assertEqual(presented_year(Q, DOC.published_at), 2026)
        self.assertEqual(presented_year("nagranie pokazuje aktualny protest pod Sejmem", "2025-03-01"), 2025)
        self.assertIsNone(presented_year("policja zasłania protestujących pod Trybunałem parawanem", "2026-09-17"))
        self.assertIsNone(presented_year("film pokazuje protest pod Sejmem", "2026-09-17"))  # no time asserted

    def test_analysis_dating_the_material_earlier(self):
        frag, year = archival_origin(DOC, Q, 2026)
        self.assertEqual(year, 2021)
        self.assertIn("pochodzi z marca 2021", frag)
        self.assertIn(frag, DOC.text)  # verbatim
        self.assertFalse(frag.startswith("-"))

    def test_same_year_or_other_people_is_no_refutation(self):
        self.assertIsNone(archival_origin(DOC, Q, 2021))
        other = "film udostępniony przez Annę Nowak w 2026 r. pokazywał ówczesny protest pod Sejmem RP"
        self.assertIsNone(archival_origin(DOC, other, 2026))

    def test_answer_quotes_the_dating_passage(self):
        frag, year = archival_origin(DOC, Q, 2026)
        e = Evidence(doc_id="fc", title=DOC.title, publisher="Demagog", domain="demagog.org.pl", url=DOC.url,
                     source_type="factcheck", tier=2, fragment=frag, factcheck_claim=DOC.claim, factcheck_verdict="false",
                     factcheck_verdict_raw="Fałsz", stance="przeczy", similarity=0.75)
        c = ClaimResult(claim="Czy " + Q + "?", verdict="falszywe", verdict_label="Fałszywe", strength=0.6,
                        strength_label="umiarkowana", explanation="…", evidence=[e], context_type="FALSZYWY_KONTEKST",
                        missing_context="Materiał pochodzi z 2021 r., a twierdzenie przedstawia go jako z 2026 r. "
                                        "(źródło: Demagog).")
        answer.finalize(CheckResult(id="x", created_at="2026-11-21", channel="web", status="ok", input_kind="text",
                                    input_excerpt="", claims=[c]))
        self.assertTrue(c.short_answer.startswith("Nie. Materiał pochodzi z 2021 r."), c.short_answer)
        self.assertIn("pochodzi z marca 2021 roku", c.short_answer)


if __name__ == "__main__":
    unittest.main()
