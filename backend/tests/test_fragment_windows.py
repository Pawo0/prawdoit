"""Quoted fragments must be verbatim (validity gate V2), whatever the sentence splitter does. Pure text, no models.

Run:  backend/.venv/bin/python backend/tests/test_fragment_windows.py      (or pytest backend/tests)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prawdowid.engine import _fragment_windows, _quote_ok, _squash  # noqa: E402
from prawdowid.textutil import split_sentences  # noqa: E402

# A Demagog-style quote with an editor's note. "– dop. Demagog]." is split after the abbreviation "dop.", which the
# splitter does not know, and leaves the 9-character sentence "Demagog]." between two real sentences. ("przyp." used
# to be split the same way; it is a known abbreviation now, see test_editor_note_przyp_is_not_split.)
NOTE = ("Przed wojną przecież była połączona funkcja [Prokuratora Generalnego i Ministra Sprawiedliwości – dop. "
        "Demagog]. Po wojnie przez lata była połączona. A potem wy ją rozdzieliliście.")
# A closing quotation mark after the full stop is consumed by the splitter.
QUOTE = "Minister powiedział: „Budżet został przyjęty bez poprawek.” Posłowie opozycji wyszli wtedy z sali obrad."


def old_windows(text: str) -> list[str]:
    """The construction used before the fix: drop short sentences, then join neighbours of what is left."""
    sents = [x for x in split_sentences(text) if len(x) > 15] or [text]
    return [w for w in sents + [f"{a} {b}" for a, b in zip(sents, sents[1:])] if len(w) <= 520] or [sents[0][:520]]


class FragmentWindows(unittest.TestCase):
    def assert_all_verbatim(self, passage: str, source: str) -> list[str]:
        windows = _fragment_windows(passage, source)
        self.assertTrue(windows)
        for w in windows:
            self.assertIn(w, _squash(source))
            self.assertTrue(_quote_ok(w, source))
        return windows

    def test_the_splitter_really_produces_the_short_sentence(self):
        self.assertIn("Demagog].", split_sentences(NOTE))

    def test_old_construction_joined_non_adjacent_sentences(self):
        glued = "Ministra Sprawiedliwości – dop. Po wojnie przez lata była połączona."
        self.assertTrue(any(glued in w for w in old_windows(NOTE)))  # the bug this guards against
        self.assertFalse(_quote_ok(next(w for w in old_windows(NOTE) if glued in w), NOTE))

    def test_no_window_skips_a_short_sentence(self):
        windows = self.assert_all_verbatim(NOTE, NOTE)
        self.assertFalse(any("dop. Po wojnie" in w for w in windows))
        self.assertIn("Przed wojną przecież była połączona funkcja [Prokuratora Generalnego i Ministra Sprawiedliwości "
                      "– dop. Demagog].", windows)  # the short sentence is quoted together with its neighbour
        self.assertIn("Po wojnie przez lata była połączona. A potem wy ją rozdzieliliście.", windows)

    def test_editor_note_przyp_is_not_split(self):
        s = "Natomiast MPK [we Wrocławiu – przyp. Demagog] i tak nas sporo kosztuje. Drugie zdanie."
        self.assertEqual(split_sentences(s), ["Natomiast MPK [we Wrocławiu – przyp. Demagog] i tak nas sporo kosztuje.",
                                              "Drugie zdanie."])

    def test_restated_claim_is_recognised(self):
        from prawdowid.engine import _restates

        claim = "Piątkowa depesza PAP - jak twierdzi poseł - została usunięta. Tusk wszedł w buty Cimoszewicza z 1997 r."
        self.assertTrue(_restates("Piątkowa depesza PAP – jak twierdzi poseł – została usunięta.", claim))  # en dash
        self.assertTrue(_restates("Tusk wszedł w buty Cimoszewicza z 1997 r. - W piątek premier mówił o powodzi.", claim))
        self.assertFalse(_restates("Jak wyjaśnia redaktor naczelny PAP depesza nie została usunięta.", claim))

    def test_short_sentence_is_not_quoted_alone(self):
        self.assertNotIn("Demagog].", _fragment_windows(NOTE, NOTE))

    def test_pair_keeps_the_closing_quotation_mark(self):
        windows = self.assert_all_verbatim(QUOTE, QUOTE)
        self.assertIn(QUOTE, windows)  # both sentences, with the ” that a plain join would lose
        self.assertFalse(_quote_ok(" ".join(split_sentences(QUOTE)), QUOTE))

    def test_whitespace_of_the_source_does_not_matter(self):
        source = "Wstęp do artykułu o cenach.\n\nCeny biletów wzrosły w maju   o osiem procent.\nRada miasta przyjęła uchwałę."
        passage = "Ceny biletów wzrosły w maju o osiem procent. Rada miasta przyjęła uchwałę."
        windows = self.assert_all_verbatim(passage, source)
        self.assertIn(passage, windows)

    def test_passage_built_from_joined_sentences_of_the_source(self):
        # index chunks are sentences joined with one space; the lost ” must come back from the source
        passage = " ".join(split_sentences(QUOTE))
        self.assertNotIn("”", passage)
        self.assertIn(QUOTE, self.assert_all_verbatim(passage, "Nagłówek strony.\n" + QUOTE + "\nStopka strony z datą."))

    def test_sentence_missing_from_the_source_is_left_out(self):
        source = "Pierwsze zdanie jest w źródle. Trzecie zdanie też jest w źródle."
        passage = "Pierwsze zdanie jest w źródle. Tego zdania w źródle nie ma wcale. Trzecie zdanie też jest w źródle."
        windows = self.assert_all_verbatim(passage, source)
        self.assertEqual(sorted(windows), ["Pierwsze zdanie jest w źródle.", "Trzecie zdanie też jest w źródle."])

    def test_nothing_in_common_gives_no_window(self):
        self.assertEqual(_fragment_windows("Tytuł dokumentu bez treści w bazie.", ""), [])

    def test_length_limits(self):
        long_sentence = "Bardzo długie zdanie " + "o tym samym " * 60 + "kończy się tutaj."
        windows = self.assert_all_verbatim(long_sentence, long_sentence)
        self.assertEqual(len(windows), 1)
        self.assertEqual(len(windows[0]), 520)
        for w in self.assert_all_verbatim(NOTE + " " + QUOTE, NOTE + " " + QUOTE):
            self.assertTrue(16 <= len(w) <= 520)


if __name__ == "__main__":
    unittest.main()
