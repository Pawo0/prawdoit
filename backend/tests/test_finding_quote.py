"""Quote of a fact-check that carries the finding (engine._finding_score and finding windows). No models: NLI and the
index are replaced by stubs. Every text is invented."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _testenv  # noqa: E402,F401

from prawdowid import engine  # noqa: E402
from prawdowid.textutil import tokens  # noqa: E402

CLAIM = "Gmina Zielonka zamknęła w 2025 r. wszystkie trzy szkoły podstawowe"
FC_CLAIM = "W gminie Zielonka zamknięto wszystkie szkoły podstawowe"


def fs(w, claim=CLAIM):
    return engine._finding_score(w, set(tokens(claim)), set(tokens(FC_CLAIM)), claim)


class FindingScore(unittest.TestCase):
    def test_finding_beats_retelling(self):
        retell = "W mediach społecznościowych krąży wpis, według którego gmina rzekomo zamknęła szkoły podstawowe."
        finding = "W rzeczywistości zamknięto jedną szkołę, a dwie pozostałe połączono w zespół szkół."
        self.assertGreater(fs(finding), fs(retell))
        self.assertLess(fs(retell), 0)

    def test_near_restatement_is_penalised(self):
        self.assertLess(fs("Gmina Zielonka zamknęła wszystkie szkoły podstawowe."), 0)

    def test_earlier_year_and_different_amount(self):
        plain = "Decyzję podjęła rada gminy po konsultacjach z rodzicami uczniów."
        older = "Decyzję podjęła rada gminy w 2019 r. po konsultacjach z rodzicami uczniów."
        self.assertGreater(fs(older), fs(plain))
        money = "Gmina wydaje na oświatę 12 mln zł rocznie"
        self.assertGreater(fs("Budżet szkół wynosi 9 mln zł, czyli mniej niż podano.", money),
                           fs("Budżet szkół jest uchwalany co roku przez radę gminy.", money))


class OppositeClaim(unittest.TestCase):
    """The analysis rated the opposite of the user's claim (claim match with same=False): its verdict words are about
    the claim the user denies, so they earn no finding bonus when the quote is chosen."""
    VERDICT_ONLY = "Sprawdziliśmy, dlaczego to nieprawda."
    NEUTRAL = "W rzeczywistości zamknięto jedną szkołę z trzech."

    def test_verdict_words_count_only_for_the_same_claim(self):
        q, fc = set(tokens(CLAIM)), set(tokens(FC_CLAIM))
        same = engine._finding_score(self.VERDICT_ONLY, q, fc, CLAIM)
        opposite = engine._finding_score(self.VERDICT_ONLY, q, fc, CLAIM, opposite=True)
        self.assertAlmostEqual(same - opposite, 0.3)

    def test_other_finding_cues_still_count(self):
        q, fc = set(tokens(CLAIM)), set(tokens(FC_CLAIM))
        self.assertEqual(engine._finding_score(self.NEUTRAL, q, fc, CLAIM),
                         engine._finding_score(self.NEUTRAL, q, fc, CLAIM, opposite=True))

    def test_best_fragment_drops_the_verdict_sentence(self):
        text = ("W gminie Zielonka zamknięto wszystkie szkoły podstawowe. Wyjaśniamy, dlaczego to fałsz. "
                "Rada gminy zamknęła jedną szkołę podstawową w 2025 r. i połączyła dwie pozostałe.")
        doc = SimpleNamespace(text=text, title="Szkoły w gminie Zielonka działają", claim=FC_CLAIM, source_type="factcheck")
        chunk = SimpleNamespace(text=text)
        index = SimpleNamespace(doc_chunks=[[0]], synthetic=set(), chunk_emb=np.ones((1, 2), dtype=np.float32),
                                chunks=[chunk], docs=[doc])
        q_emb = np.ones(2, dtype=np.float32)
        q = set(tokens(CLAIM))
        with mock.patch.object(engine, "INDEX", index):
            same, _, _ = engine._best_fragment(0, q_emb, q, CLAIM)
            opposite, _, _ = engine._best_fragment(0, q_emb, q, CLAIM, opposite=True)
        self.assertIn("to fałsz", same)
        self.assertNotIn("to fałsz", opposite)
        self.assertIn(engine._squash(opposite), engine._squash(text))  # still verbatim


class MidSentence(unittest.TestCase):
    def test_cut_starts(self):
        src = engine._squash("Rada gminy podała, że w szkole uczy się\nponad dwustu uczniów. Budżet (ok. 4 mln zł) "
                             "uchwalono w maju. Dyrektorka szkoły, Anna Nowak, potwierdziła plan.")
        self.assertTrue(engine._starts_mid_sentence("ponad dwustu uczniów.", src))  # line break inside a sentence
        self.assertTrue(engine._starts_mid_sentence("4 mln zł) uchwalono w maju.", src))  # bracket never opened
        self.assertTrue(engine._starts_mid_sentence("Anna Nowak, potwierdziła plan.", src))  # after a comma
        self.assertTrue(engine._starts_mid_sentence("szkoły, Anna Nowak, potwierdziła plan.", src))
        self.assertTrue(engine._starts_mid_sentence("ajca szkoły, Anna Nowak", "Dyrektorka szkoły, Anna Nowak"))  # mid-word

    def test_whole_sentences(self):
        src = engine._squash("Rada gminy podała dane. Budżet (ok. 4 mln zł) uchwalono w maju.\n- Szkoła działa dalej.")
        for w in ("Rada gminy podała dane.", "Budżet (ok. 4 mln zł) uchwalono w maju.", "- Szkoła działa dalej.",
                  "„Szkoła działa dalej”"):
            self.assertFalse(engine._starts_mid_sentence(w, src), w)

    def test_best_fragment_prefers_a_whole_sentence(self):
        # the finding's sentence runs over a line break, so the splitter also yields its second half on its own
        head = ("Rada gminy na sesji w ratuszu omawiała przez kilka godzin sprawozdanie burmistrza, plan remontów dróg "
                "gminnych, oświetlenie ulic, dotacje dla klubów sportowych, program opieki nad zabytkami, budowę ścieżki "
                "rowerowej wzdłuż rzeki, harmonogram odbioru odpadów, wysokość opłat za wodę, stypendia dla uczniów, "
                "zakup nowego wozu dla straży, przebudowę targowiska, a także sprawy oświaty, i po długiej dyskusji "
                "radni przyjęli informację, że")
        text = (f"W gminie Zielonka zamknięto wszystkie szkoły podstawowe. {head}\nzamknięto jedną szkołę podstawową "
                "w gminie Zielonka w 2025 roku. Dwie pozostałe szkoły w gminie działają.")
        doc = SimpleNamespace(text=text, title="W gminie Zielonka zamknięto jedną szkołę", claim=FC_CLAIM,
                              source_type="factcheck")
        index = SimpleNamespace(doc_chunks=[[0]], synthetic=set(), chunk_emb=np.ones((1, 2), dtype=np.float32),
                                chunks=[SimpleNamespace(text=text)], docs=[doc])

        def best():
            with mock.patch.object(engine, "INDEX", index):
                return engine._best_fragment(0, np.ones(2, dtype=np.float32), set(tokens(CLAIM)), CLAIM)[0]
        self.assertTrue(best().startswith("Rada gminy"), best())
        with mock.patch.object(engine, "MID_SENTENCE_PENALTY", 0.0):
            self.assertTrue(best().startswith("zamknięto"))  # without the penalty the cut half wins


if __name__ == "__main__":
    unittest.main()
