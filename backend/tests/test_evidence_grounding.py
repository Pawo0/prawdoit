"""Displayed findings, numeric obligations and abstention: invented sources, no models."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testenv  # noqa: E402,F401
from prawdowid import engine, grounding  # noqa: E402
from prawdowid.answer import main_evidence  # noqa: E402
from prawdowid.claims import Claim  # noqa: E402
from prawdowid.nli import NLIScore  # noqa: E402
from prawdowid.schemas import ClaimResult, SourceDoc  # noqa: E402


class TextGuards(unittest.TestCase):
    def test_question_is_not_a_finding(self):
        self.assertFalse(
            grounding.has_finding("Dlaczego po remontach nadal są awarie? Wyjaśniamy.")
        )

    def test_allegation_and_outrage_are_not_findings(self):
        self.assertFalse(grounding.has_finding("Internauci sugerują, że most został zamknięty."))
        self.assertFalse(grounding.has_finding("Post o moście wywołał oburzenie mieszkańców."))
        self.assertTrue(
            grounding.has_finding(
                "Internauci sugerują, że most został zamknięty. W rzeczywistości most jest otwarty."
            )
        )

    def test_each_exact_quantity_is_required_for_confirmation(self):
        claim = "Lista uzyskała 51,37% głosów i 27 mandatów."
        self.assertFalse(grounding.numeric_support_complete(claim, "Lista wygrała wybory."))
        self.assertFalse(grounding.numeric_support_complete(claim, "Lista uzyskała 51,37% głosów."))
        self.assertFalse(
            grounding.numeric_support_complete(claim, "Lista uzyskała 51,38% głosów i 27 mandatów.")
        )
        self.assertTrue(
            grounding.numeric_support_complete(claim, "Lista uzyskała 51.37% głosów i 27 mandatów.")
        )

    def test_other_period_is_not_a_contradiction(self):
        self.assertFalse(
            grounding.comparable_scope(
                "W 2031 roku było 12 wypadków.", "W 2029 roku było 15 wypadków."
            )
        )

    def test_vague_count_is_not_a_numeric_contradiction(self):
        self.assertFalse(
            grounding.has_numeric_comparison("Przybyło 12 mln osób.", "Przybyło wiele osób.")
        )
        self.assertTrue(
            grounding.has_numeric_comparison("Przybyło 12 mln osób.", "Przybyło 8 mln osób.")
        )

    def test_total_counts_do_not_refute_a_per_capita_rate(self):
        self.assertFalse(
            grounding.has_numeric_comparison(
                "Grupa A popełnia 8 razy więcej zdarzeń na 1000 osób niż grupa B.",
                "Łącznie zarejestrowano 800 zdarzeń, w tym 20 w grupie A.",
            )
        )
        self.assertTrue(
            grounding.has_numeric_comparison(
                "Grupa A popełnia 8 razy więcej zdarzeń na 1000 osób niż grupa B.",
                "Wskaźnik zdarzeń na 1000 mieszkańców jest wyższy w grupie B niż A.",
            )
        )

    def test_unresolved_country_cannot_contradict_named_destination(self):
        self.assertFalse(
            grounding.comparable_scope(
                "Do Rurytanii przybyło 12 mln osób.",
                "Do naszego kraju przybyły dwa miliony osób.",
            )
        )


class QuoteGate(unittest.TestCase):
    def gate(self, text, claim, alternatives, scores, group="support"):
        document = SourceDoc(
            id="test:1",
            source_type="factcheck",
            publisher="Redakcja",
            domain="example.invalid",
            url="https://example.invalid/a",
            title="Most jest otwarty",
            text=text,
            claim=claim,
            verdict="true" if group == "support" else "misleading",
            verdict_raw="Ocena",
        )
        candidate = engine._Cand(
            doc_idx=0,
            chunk_text="",
            retrieval=0.9,
            cos=0.9,
            claim_cos=0.9,
            fragment=alternatives[0],
            alternatives=tuple((w, 1.0) for w in alternatives),
            same=True,
        )
        index = SimpleNamespace(docs=[document], doc_age=lambda _: 0)
        with (
            patch.object(engine, "INDEX", index),
            patch.object(engine.NLI_MODEL, "score", return_value=scores) as nli,
        ):
            ev = engine._evidence(
                candidate, "popiera" if group == "support" else "kontekst", 0.9, True
            )
            support, refute, misleading = [], [], []
            groups = {"support": support, "refute": refute, "misleading": misleading}
            groups[group].append(candidate)
            rejected = engine._ground_factchecks(
                Claim(claim, claim, "fakt", 1), support, refute, misleading, [ev]
            )
        return candidate, ev, groups[group], rejected, nli

    def test_rating_cannot_rescue_an_allegation(self):
        c, e, decisive, rejected, nli = self.gate(
            "Internauci sugerują, że most jest otwarty.",
            "Most jest otwarty.",
            ["Internauci sugerują, że most jest otwarty."],
            [],
        )
        self.assertFalse(decisive)
        self.assertEqual(rejected, ["test:1"])
        self.assertEqual(e.stance, "kontekst")
        self.assertIsNone(e.same_claim)
        self.assertEqual(nli.call_args.args[0], [])

    def test_verified_alternative_replaces_uninformative_quote(self):
        question, finding = (
            "Dlaczego most jest otwarty?",
            "Most jest otwarty dla wszystkich pojazdów.",
        )
        c, e, decisive, rejected, _ = self.gate(
            question + " " + finding,
            "Most jest otwarty.",
            [question, finding],
            [NLIScore(0.92, 0.05, 0.03)],
        )
        self.assertEqual(c.fragment, finding)
        self.assertEqual(e.fragment, finding)
        self.assertTrue(decisive)
        self.assertFalse(rejected)

    def test_neutral_best_window_cannot_decide(self):
        _, _, decisive, _, _ = self.gate(
            "Most wybudowano wiele lat temu.",
            "Most jest otwarty.",
            ["Most wybudowano wiele lat temu."],
            [NLIScore(0.2, 0.7, 0.1)],
        )
        self.assertFalse(decisive)

    def test_missing_percentage_is_rejected_before_nli(self):
        _, _, decisive, _, nli = self.gate(
            "Lista wygrała wybory.",
            "Lista wygrała wybory z 51,37% głosów.",
            ["Lista wygrała wybory."],
            [],
        )
        self.assertFalse(decisive)
        self.assertEqual(nli.call_args.args[0], [])

    def test_misleading_quote_is_also_checked_and_rejected(self):
        _, e, decisive, _, _ = self.gate(
            "Most wybudowano wiele lat temu.",
            "Most jest otwarty.",
            ["Most wybudowano wiele lat temu."],
            [NLIScore(0.1, 0.8, 0.1)],
            group="misleading",
        )
        self.assertFalse(decisive)
        result = ClaimResult(
            claim="Most jest otwarty.",
            kind="fakt",
            verdict="wprowadzajace_w_blad",
            verdict_label="Wprowadzające w błąd",
            strength=0,
            strength_label="brak",
            explanation="Ocena testowa",
            evidence=[e],
        )
        self.assertIsNone(main_evidence(result))

    def test_misleading_rate_cannot_be_explained_by_total_counts(self):
        _, _, decisive, _, nli = self.gate(
            "Zarejestrowano 800 zdarzeń, w tym 20 w grupie A.",
            "Grupa A ma 8 razy więcej zdarzeń na 1000 osób niż grupa B.",
            ["Zarejestrowano 800 zdarzeń, w tym 20 w grupie A."],
            [],
            group="misleading",
        )
        self.assertFalse(decisive)
        self.assertEqual(nli.call_args.args[0], [])

    def test_a_fabricated_quote_is_rejected_before_nli(self):
        _, _, decisive, _, nli = self.gate(
            "Most jest zamknięty.",
            "Most jest otwarty.",
            ["Most jest otwarty."],
            [],
        )
        self.assertFalse(decisive)
        self.assertEqual(nli.call_args.args[0], [])

    def test_quote_shortlist_has_a_per_document_budget(self):
        windows = [f"Most jest otwarty po remoncie numer {i}." for i in range(20)]
        _, _, _, _, nli = self.gate(
            " ".join(windows),
            "Most jest otwarty.",
            windows,
            [NLIScore(0.1, 0.8, 0.1)] * 20,
        )
        self.assertLessEqual(len(nli.call_args.args[0]), 6)

    def test_unquoted_full_text_cannot_rescue_a_quote(self):
        _, _, decisive, _, _ = self.gate(
            "Most jest zamknięty. Most jest otwarty.",
            "Most jest otwarty.",
            ["Most jest zamknięty."],
            [NLIScore(0.01, 0.01, 0.98)],
        )
        self.assertFalse(decisive)


if __name__ == "__main__":
    unittest.main()
