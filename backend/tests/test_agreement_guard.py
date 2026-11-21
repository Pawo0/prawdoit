"""Name / number agreement guard on the similarity-only route of engine.same_claim. Pure text, no models.

Run:  backend/.venv/bin/python backend/tests/test_agreement_guard.py      (or pytest backend/tests)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prawdowid import engine  # noqa: E402
from prawdowid.agreement import (disagreement, fold, names_disagree, numbers_disagree, quantities,  # noqa: E402
                                 same_word)
from prawdowid.nli import NLIScore  # noqa: E402

CLAIM = "Minister Jan Kowalski spotkał się z Anną Nowak w Poznaniu."


def values(text: str) -> list[float]:
    return [q[0] for q in quantities(text)]


class SameWord(unittest.TestCase):
    def same(self, a: str, b: str) -> bool:
        return same_word(fold(a), fold(b))

    def test_inflection_of_names(self):
        for a, b in [("Tusk", "Tuskiem"), ("Tusk", "Tuska"), ("Trzaskowski", "Trzaskowskim"), ("Polska", "Polsce"),
                     ("Duda", "Dudy"), ("Unia", "Unii"), ("Kraków", "Krakowie"), ("Włochy", "Włoszech"),
                     ("Niemcy", "Niemczech"), ("PiS", "PiSu"), ("Ukraina", "ukraiński")]:
            self.assertTrue(self.same(a, b), (a, b))

    def test_missing_diacritics_and_case(self):
        self.assertTrue(self.same("Tarczyński", "tarczynski"))
        self.assertTrue(self.same("Świnoujście", "swinoujscie"))

    def test_different_names_stay_different(self):
        for a, b in [("Tusk", "Trzaskowski"), ("Gdańsk", "Szczecin"), ("Gdańsk", "Gdynia"), ("Iran", "Irak"),
                     ("Iranu", "Iraku"), ("Kowalski", "Nowak"), ("PiS", "PO"), ("Polska", "Ukraina")]:
            self.assertFalse(self.same(a, b), (a, b))

    def test_one_typing_error(self):
        self.assertTrue(self.same("Ukriany", "Ukrainy"))  # long word: any single error
        self.assertTrue(self.same("Gabard", "Gabbard"))
        self.assertTrue(self.same("Tuksa", "Tuska"))  # short word: swapped neighbours only
        self.assertFalse(self.same("Rusk", "Tusk"))


class Names(unittest.TestCase):
    def test_another_name_in_the_same_place(self):
        self.assertEqual(names_disagree("Minister Jan Kowalski spotkał się z Ewą Wiśniewską w Poznaniu.", CLAIM),
                         ("Ewą Wiśniewską", "Anną Nowak"))
        self.assertIsNotNone(names_disagree("Minister Jan Kowalski spotkał się z Anną Nowak w Gdańsku.", CLAIM))

    def test_inflected_and_reordered_same_names(self):
        self.assertIsNone(names_disagree("Z Anną Nowak spotkał się w Poznaniu minister Kowalski.", CLAIM))
        self.assertIsNone(names_disagree("Spotkanie ministra Jana Kowalskiego z Anną Nowak odbyło się w Poznaniu.", CLAIM))

    def test_omission_is_not_disagreement(self):
        self.assertIsNone(names_disagree("Minister Kowalski spotkał się z Nowak.", CLAIM))  # first names, place dropped
        self.assertIsNone(names_disagree("Kowalski spotkał się w Poznaniu z ważną osobą.", CLAIM))
        self.assertIsNone(names_disagree("Minister spotkał się z kimś w Poznaniu.", CLAIM))

    def test_addition_is_not_disagreement(self):
        self.assertIsNone(names_disagree("Minister Jan Kowalski z PSL spotkał się w piątek z Anną Nowak w Poznaniu.", CLAIM))

    def test_common_noun_for_a_name_when_the_user_writes_capitals(self):
        # "z dziennikarką" is lower case in a text that uses capitals: known not to be a name
        self.assertIsNone(names_disagree("Minister Jan Kowalski spotkał się z dziennikarką w Poznaniu.", CLAIM))

    def test_alias_elsewhere_in_a_reworded_sentence(self):
        # other names, but not in the place of the claim's names: a paraphrase, not a swap
        self.assertIsNone(names_disagree("W stolicy Wielkopolski doszło do rozmowy Kowalskiego z szefową NBP.", CLAIM))
        self.assertIsNone(names_disagree("Więcej Polaków odbiera sobie życie, niż ginie w wypadkach.",
                                         "W Polsce w wyniku samobójstw ginie więcej osób niż w wypadkach."))

    def test_lower_case_user_text(self):
        # no capital letters: any new word standing where the claim's name stood may be another name
        self.assertIsNotNone(names_disagree("minister jan kowalski spotkal sie z ewa wisniewska w poznaniu", CLAIM))
        self.assertIsNone(names_disagree("minister jan kowalski spotkal sie z anna nowak w poznaniu", CLAIM))
        self.assertIsNone(names_disagree("kowalski spotkal sie z nowak", CLAIM))

    def test_typo_in_a_name_is_the_same_name(self):
        self.assertIsNone(names_disagree("Minister Jan Kowalksi spotkał się z Anną Nowak w Poznaniu.", CLAIM))
        self.assertIsNone(names_disagree("Dzieci były zmuszane do śpiewania hymnu Ukriany.",
                                         "Dzieci były zmuszane do śpiewania hymnu Ukrainy."))

    def test_acronym_and_expansion(self):
        claim = "W 2023 roku był największy spadek ludności w całej Unii Europejskiej."
        self.assertIsNone(names_disagree("W 2023 r. był największy spadek ludności w UE.", claim))
        self.assertIsNone(names_disagree("W 2023 r. był największy spadek ludności w całej UE.", claim))
        self.assertIsNotNone(names_disagree("W 2023 r. był największy spadek ludności w całej NATO.", claim))

    def test_editor_note_is_not_a_name(self):
        claim = "Mamy [w Krakowie – przyp. Demagog] najdroższy bilet godzinny w Polsce."
        self.assertIsNone(names_disagree("W Krakowie mamy najdroższy bilet godzinny w Polsce.", claim))
        self.assertIsNotNone(names_disagree("Mamy w Gdańsku najdroższy bilet godzinny w Polsce.", claim))

    def test_first_word_of_a_sentence_is_only_maybe_a_name(self):
        # two sentence-initial words: capitalised whatever they are, so nothing can be concluded
        self.assertIsNone(names_disagree("Preparaty zawierają grafen.", "Szczepionki zawierają grafen."))
        # ... but against a sure name in the same place it counts
        self.assertIsNotNone(names_disagree("Nowak podpisał w Poznaniu umowę.", "Wczoraj Kowalski podpisał w Poznaniu umowę."))

    def test_role_swap_is_not_detected(self):
        # documented limit: the same two names in swapped roles agree as sets
        self.assertIsNone(names_disagree("Ukraina odda Polsce część terytorium.", "Polska odda Ukrainie część terytorium."))


class Numbers(unittest.TestCase):
    def test_same_number_written_differently(self):
        self.assertEqual(values("250 tys."), [250000.0])
        self.assertEqual(values("250 000"), [250000.0])
        self.assertEqual(values("250.000"), [250000.0])
        self.assertEqual(values("250 tysięcy"), [250000.0])
        self.assertEqual(values("ćwierć miliona"), [250000.0])
        self.assertEqual(values("cwierc miliona"), [250000.0])
        self.assertEqual(values("pół miliona złotych"), [500000.0])
        self.assertEqual(values("2,7 proc."), [2.7])
        self.assertEqual(quantities("2,7 proc.")[0][1], "%")
        self.assertEqual(quantities("osiem złotych")[0][:2], (8.0, "zł"))
        self.assertEqual(quantities("8 zł")[0][:2], (8.0, "zł"))
        self.assertEqual(values("dwadzieścia pięć"), [25.0])
        self.assertEqual(values("sto dwadzieścia pięć osób"), [125.0])
        self.assertEqual(values("dwa, trzy razy"), [2.0, 3.0])
        self.assertEqual(values("2–3 razy w kadencji 2007–2014"), [2.0, 3.0, 2007.0, 2014.0])
        self.assertEqual(values("15 mld zł i 2,8 mld"), [15e9, 2.8e9])
        self.assertEqual(values("24.02.2022"), [24.0, 2022.0])

    def test_not_quantities(self):
        self.assertEqual(values("COVID-19 i myśliwce F-16"), [])  # digits of a name
        self.assertEqual(values("dziesiątki milionów migrantów"), [])  # vague
        self.assertEqual(values("pół roku temu"), [])
        self.assertEqual(values("jeden z posłów"), [])
        self.assertEqual(values("w 2023 tysiące osób wyjechało"), [2023.0])

    def test_different_number(self):
        claim = "Podczas pandemii rząd wydał ponad 250 tys. zł na maseczki w 2020 roku."
        self.assertIsNotNone(numbers_disagree("Podczas pandemii rząd wydał 400 tys. zł na maseczki w 2020 roku.", claim))
        self.assertIsNotNone(numbers_disagree("Podczas pandemii rząd wydał 250 tys. zł na maseczki w 2021 roku.", claim))
        self.assertIsNotNone(numbers_disagree("Rząd wydał w pandemii 250 tys. euro na maseczki.", claim))

    def test_same_number_other_spelling(self):
        claim = "Podczas pandemii rząd wydał ponad 250 tys. zł na maseczki w 2020 roku."
        for user in ("Rząd wydał w 2020 r. 250 000 zł na maseczki.", "Rząd wydał w 2020 ćwierć miliona złotych na maseczki.",
                     "rzad wydal 250 tysiecy zl na maseczki", "Rząd wydał 250 tys. na maseczki."):
            self.assertIsNone(numbers_disagree(user, claim), user)

    def test_omission_and_addition_are_not_disagreement(self):
        claim = "Podczas pandemii rząd wydał ponad 250 tys. zł na maseczki w 2020 roku."
        self.assertIsNone(numbers_disagree("Rząd wydał w pandemii pieniądze na maseczki.", claim))
        self.assertIsNone(numbers_disagree("Rząd wydał 250 tys. zł na 3 miliony maseczek w 2020 roku.", claim))

    def test_each_side_with_its_own_number_is_a_disagreement_wherever_the_numbers_stand(self):
        self.assertIsNotNone(numbers_disagree("Policjant został skazany na osiem lat więzienia.",
                                              "Na zdjęciu jest policjant podejrzany o napaść na 22-letnią kobietę."))

    def test_a_bound_agrees_with_what_it_admits(self):
        self.assertIsNone(numbers_disagree("ponad 90% Ukraińców w wieku poborowym pracuje", "95 proc. Ukraińców w wieku poborowym pracuje"))
        self.assertIsNone(numbers_disagree("Kraków ma 1900 pustostanów.", "Kraków posiada prawie 2 tysiące pustostanów."))
        self.assertIsNotNone(numbers_disagree("ponad 90% Ukraińców pracuje", "70 proc. Ukraińców pracuje"))
        self.assertIsNotNone(numbers_disagree("prawie 90% Ukraińców pracuje", "95 proc. Ukraińców pracuje"))
        self.assertIsNotNone(numbers_disagree("Rząd wydał 400 tys. zł.", "Rząd wydał ponad 250 tys. zł."))  # beyond the bound's reach
        self.assertIsNone(numbers_disagree("Rząd wydał 300 tys. zł.", "Rząd wydał ponad 250 tys. zł."))


def nli(entail: float, contra: float = 0.0) -> NLIScore:
    return NLIScore(entail, 1.0 - entail - contra, contra)


class SameClaimRoutes(unittest.TestCase):
    """The guard withdraws the similarity-only route and nothing else."""
    SWAP = "Minister Jan Kowalski spotkał się z Ewą Wiśniewską w Poznaniu."
    SAME = "Minister Kowalski spotkał się w Poznaniu z Anną Nowak."

    def test_similarity_alone_still_accepts_when_names_and_numbers_agree(self):
        self.assertEqual(engine.claim_match(0.93, nli(0.05), nli(0.05), CLAIM, self.SAME, "factcheck"), (True, None))
        self.assertIs(engine.same_claim(0.93, nli(0.05), nli(0.05), CLAIM, self.SAME, "factcheck"), True)

    def test_similarity_alone_is_not_enough_when_they_disagree(self):
        decision, note = engine.claim_match(0.93, nli(0.05), nli(0.05), CLAIM, self.SWAP, "factcheck")
        self.assertIsNone(decision)
        self.assertIn("Ewą Wiśniewską", note)
        self.assertIn("Anną Nowak", note)
        self.assertIsNone(engine.same_claim(0.93, nli(0.05), nli(0.05), CLAIM, self.SWAP, "factcheck"))

    def test_entailment_backed_routes_are_untouched(self):
        # cos >= 0.86 and entailment >= 0.5; cos >= 0.80 and entailment >= 0.8 and lexical overlap
        self.assertEqual(engine.claim_match(0.93, nli(0.6), nli(0.6), CLAIM, self.SWAP, "factcheck"), (True, None))
        self.assertEqual(engine.claim_match(0.82, nli(0.9), nli(0.9), CLAIM, self.SWAP, "factcheck"), (True, None))

    def test_negation_and_veto_are_untouched(self):
        self.assertEqual(engine.claim_match(0.93, nli(0.0, 0.9), nli(0.0, 0.9), CLAIM, self.SWAP, "factcheck"), (False, None))
        self.assertEqual(engine.claim_match(0.93, nli(0.0, 0.9), nli(0.0, 0.9), CLAIM, self.SAME, "factcheck"), (False, None))
        self.assertEqual(engine.claim_match(0.93, nli(0.2, 0.6), nli(0.2, 0.1), CLAIM, self.SAME, "factcheck"), (None, None))

    def test_below_the_shortcut_nothing_changes(self):
        self.assertEqual(engine.claim_match(0.87, nli(0.05), nli(0.05), CLAIM, self.SAME, "factcheck"), (None, None))
        self.assertEqual(engine.claim_match(0.87, nli(0.05), nli(0.05), CLAIM, self.SWAP, "factcheck"), (None, None))

    def test_incident_sources_never_used_the_shortcut(self):
        self.assertEqual(engine.claim_match(0.93, nli(0.05), nli(0.05), CLAIM, self.SAME, "incident"), (None, None))

    def test_number_disagreement_withdraws_the_shortcut(self):
        claim = "Rząd wydał w 2020 roku 250 tys. zł na maseczki."
        decision, note = engine.claim_match(0.93, nli(0.05), nli(0.05), claim, "Rząd wydał w 2021 roku 250 tys. zł na maseczki.", "factcheck")
        self.assertIsNone(decision)
        self.assertIn("2021", note)
        self.assertEqual(engine.claim_match(0.93, nli(0.05), nli(0.05), claim, "Rząd wydał w 2020 r. ćwierć miliona złotych na maseczki.",
                                            "factcheck"), (True, None))

    def test_note_is_none_without_disagreement(self):
        self.assertIsNone(disagreement(self.SAME, CLAIM))
        self.assertIsNotNone(disagreement(self.SWAP, CLAIM))


if __name__ == "__main__":
    unittest.main()
