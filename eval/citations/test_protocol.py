"""Regression tests for per-assertion denominators and independent citation judgments."""

import unittest

from protocol import packet, score


class CitationMetrics(unittest.TestCase):
    def setUp(self):
        self.source = {
            "id": "source:1",
            "text": "Wartość wynosi 3. Stawka jest niezmienna.",
            "title": "Raport",
            "publisher": "Urząd",
            "url": "https://example.org",
            "published_at": "2030-01-01",
        }
        evidence = {
            "doc_id": "source:1",
            "title": "Raport",
            "publisher": "Urząd",
            "url": "https://example.org",
            "fragment": self.source["text"],
        }
        self.packet = packet(
            {
                "result": {
                    "input_excerpt": "Pytanie",
                    "claims": [
                        {
                            "claim": "Wartość wynosi 3",
                            "verdict": "potwierdzone",
                            "explanation": "Stawka jest niezmienna. Wszyscy dostaną dopłatę.",
                            "evidence": [evidence],
                        }
                    ],
                }
            },
            {"source:1": self.source},
            "P001",
        )
        self.review = {
            "packet_id": "P001",
            "packet_sha256": self.packet["sha256"],
            "reviewer_type": "ai_single_reviewer",
            "inventory_complete": True,
            "surfaces": {
                "C1.verdict": {"category": "factual", "reason": "Wynik o świecie"},
                "C1.explanation": {"category": "mixed", "reason": "Dwie tezy"},
            },
            "assertions": [
                self.assertion(
                    "A1",
                    "C1.verdict",
                    "Wartość wynosi 3",
                    "supported",
                    "Wartość wynosi 3",
                ),
                self.assertion(
                    "A2",
                    "C1.explanation",
                    "Stawka jest niezmienna",
                    "supported",
                    "Stawka jest niezmienna",
                ),
                self.assertion(
                    "A3", "C1.explanation", "Wszyscy dostaną dopłatę", "unsupported", ""
                ),
            ],
        }

    def assertion(self, id_, surface, text, judgment, support):
        return {
            "id": id_,
            "proposition": text,
            "anchor": text,
            "surface_ids": [surface],
            "citations": [
                {
                    "id": "C1E1",
                    "judgment": judgment,
                    "support_span": support,
                    "reason": "Indywidualna ocena fragmentu",
                }
            ],
        }

    def test_each_atomic_assertion_counts_including_extra_explanation_fact(self):
        report = score([self.packet], [self.review])
        self.assertEqual(report["counts"]["assertions"], 3)
        self.assertEqual(report["evidence_coverage"], 2 / 3)
        self.assertEqual(report["citation_presence"], 1)
        self.assertEqual(report["citation_correctness"], 2 / 3)
        self.assertFalse(report["human_validation_complete"])

    def test_unlinked_assertion_stays_in_coverage_denominator(self):
        self.review["assertions"][-1]["citations"] = []
        report = score([self.packet], [self.review])
        self.assertEqual(report["evidence_coverage"], 2 / 3)
        self.assertEqual(report["citation_correctness"], 1)
        self.assertEqual(report["citation_presence"], 2 / 3)

    def test_contextual_or_partial_citation_does_not_count_as_support(self):
        for a in self.review["assertions"]:
            a["citations"][0]["judgment"] = "partial"
        self.assertEqual(score([self.packet], [self.review])["evidence_coverage"], 0)

    def test_missing_review_of_a_surface_is_rejected(self):
        del self.review["surfaces"]["C1.explanation"]
        with self.assertRaises(ValueError):
            score([self.packet], [self.review])

    def test_omitted_factual_assertions_are_rejected(self):
        self.review["assertions"] = self.review["assertions"][:1]
        with self.assertRaises(ValueError):
            score([self.packet], [self.review])

    def test_full_article_cannot_repair_an_unrelated_displayed_excerpt(self):
        self.review["assertions"][0]["citations"][0][
            "support_span"
        ] = "Nieobecne w cytacie"
        with self.assertRaises(ValueError):
            score([self.packet], [self.review])

    def test_fabricated_quote_is_not_counted_even_when_reviewer_accepts_it(self):
        record = {
            "result": {
                "claims": [
                    {
                        "claim": "Wartość wynosi 9",
                        "verdict": "potwierdzone",
                        "evidence": [
                            {
                                "doc_id": "source:1",
                                "title": "Raport",
                                "publisher": "Urząd",
                                "url": "https://example.org",
                                "fragment": "Wartość wynosi 9",
                            }
                        ],
                    }
                ]
            }
        }
        p = packet(record, {"source:1": self.source}, "P001")
        review = {
            **self.review,
            "packet_sha256": p["sha256"],
            "surfaces": {"C1.verdict": self.review["surfaces"]["C1.verdict"]},
            "assertions": [
                self.assertion(
                    "A1",
                    "C1.verdict",
                    "Wartość wynosi 9",
                    "supported",
                    "Wartość wynosi 9",
                )
            ],
        }
        self.assertEqual(score([p], [review])["evidence_coverage"], 0)

    def test_tampered_packet_is_rejected(self):
        self.packet["input"] = "zmiana po ocenie"
        with self.assertRaises(ValueError):
            score([self.packet], [self.review])

    def test_partial_sample_does_not_confirm_thresholds(self):
        second = packet({"result": {}}, {}, "P002")
        report = score([self.packet, second], [self.review])
        self.assertFalse(report["complete_sample_review"])
        self.assertIsNone(report["coverage_target_met_on_sample"])
        self.assertIsNone(report["correctness_target_met_on_sample"])

    def test_no_factual_assertions_is_not_a_perfect_score(self):
        p = packet(
            {"result": {"status_message": "Podaj więcej szczegółów"}}, {}, "P001"
        )
        r = {
            "packet_id": "P001",
            "packet_sha256": p["sha256"],
            "reviewer_type": "ai_single_reviewer",
            "inventory_complete": True,
            "surfaces": {
                "result.status_message": {
                    "category": "non_factual",
                    "reason": "Prośba o dane",
                }
            },
            "assertions": [],
        }
        report = score([p], [r])
        self.assertIsNone(report["evidence_coverage"])
        self.assertIsNone(report["citation_correctness"])


if __name__ == "__main__":
    unittest.main()
