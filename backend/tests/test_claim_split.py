"""Short multi-claim input (claims.py): one claim per independent factual sentence, one merged claim when a sentence
leans on the previous one. Model-free; every input is invented."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prawdowid.claims import extract_claims  # noqa: E402
from prawdowid.textutil import normalize_ws  # noqa: E402


def texts(s, **kw):
    return [c.text for c in extract_claims(s, **kw)]


class Split(unittest.TestCase):
    def test_two_independent_statements(self):
        s = "Rząd podniósł akcyzę na papierosy o 20 procent. A benzyna kosztuje już 7,80 zł za litr."
        cs = extract_claims(s)
        self.assertEqual([c.text for c in cs], ["Rząd podniósł akcyzę na papierosy o 20 procent.",
                                                "A benzyna kosztuje już 7,80 zł za litr."])
        self.assertEqual(cs[1].query, "benzyna kosztuje już 7,80 zł za litr.")  # the conjunction is not the claim

    def test_question_then_statement(self):
        cs = extract_claims("Czy to prawda, że szczepionka na odrę zawiera rtęć? Inflacja w październiku wyniosła 9%.")
        self.assertEqual(len(cs), 2)
        self.assertEqual(cs[0].query, "szczepionka na odrę zawiera rtęć")
        self.assertEqual(cs[1].text, "Inflacja w październiku wyniosła 9%.")

    def test_second_sentence_names_its_own_entity_after_a_light_conjunction(self):
        self.assertEqual(len(texts("W Gdańsku zamknięto 12 szkół podstawowych? A Kraków dostał 300 mln zł z Unii.")), 2)

    def test_cap(self):
        s = "W Gdańsku zamknięto 12 szkół podstawowych? A Kraków dostał 300 mln zł z Unii."
        self.assertEqual(len(texts(s, max_claims=1)), 1)

    def test_each_claim_is_a_verbatim_span_of_the_input(self):
        for s in ["Rząd podniósł akcyzę na papierosy o 20 procent.   A benzyna kosztuje już 7,80 zł za litr.",
                  "Ewa Kowal · 3 godz.\nMinisterstwo zamknęło 40 szpitali w powiecie.\nRadni przyjęli budżet 9 głosami.\n"
                  "Wojewoda odwołał 3 dyrektorów szkół w Lublinie.\n120 udostępnień"]:
            base = normalize_ws(s)
            for c in extract_claims(s):
                with self.subTest(claim=c.text):
                    self.assertIsNotNone(c.span)
                    self.assertEqual(base[c.span[0]:c.span[1]], c.text)


class Merge(unittest.TestCase):
    def assertOne(self, s):
        cs = extract_claims(s)
        self.assertEqual(len(cs), 1, [c.text for c in cs])
        return cs[0]

    def test_anaphoric_or_connective_opening(self):
        for s in ["Sejm uchwalił ustawę o zakazie handlu w niedziele w 2018 r. To było sprzeczne z konstytucją.",
                  "Ministerstwo zamknęło 40 szpitali w 2024 r. A to dopiero początek redukcji.",
                  "Prezydent zawetował ustawę w maju 2023 r. Wtedy Sejm odrzucił weto 280 głosami.",
                  "Rząd podniósł akcyzę na papierosy o 20 procent. I to już drugi raz w tym roku.",
                  "Szpital w Radomiu zamknął porodówkę w 2024 r. Ale w Kielcach otwarto nową w 2025 r.",
                  "Gmina sprzedała 5 działek pod lasem. Dlatego radni złożyli doniesienie do prokuratury."]:
            with self.subTest(s=s):
                self.assertOne(s)

    def test_pronoun_or_dropped_subject(self):
        for s in ["Minister Nowak zrezygnował w marcu 2024 r. Jego następca obniżył dotacje o 30%.",
                  "Burmistrz Kowalski sprzedał działkę gminy w 2022 r. Zarobił na tym 2 mln zł.",
                  "Rząd podniósł akcyzę na papierosy o 20 procent. Podpisał to premier.",
                  "Rząd podniósł akcyzę na papierosy o 20 procent. Jest o tym artykuł w gazecie."]:
            with self.subTest(s=s):
                self.assertOne(s)

    def test_weak_second_sentence(self):
        self.assertOne("Unia zakazała sprzedaży aut spalinowych od 2035 r. Masakra.")

    def test_question_about_the_check_stays_meta(self):
        c = self.assertOne("Czy ktoś to sprawdzał? Ministerstwo wycofało syropy na kaszel z aptek w 2025 r.")
        self.assertEqual(c.meta, "Czy ktoś to sprawdzał?")
        self.assertEqual(c.query, "Ministerstwo wycofało syropy na kaszel z aptek w 2025 r.")


if __name__ == "__main__":
    unittest.main()
