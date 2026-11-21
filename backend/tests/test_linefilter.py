"""Line-level metadata filter (linefilter.py) and its effect on claim extraction. Model-free; every input is invented."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prawdowid.claims import extract_claims  # noqa: E402
from prawdowid.linefilter import drop_metadata_lines, line_kind  # noqa: E402


class LineKinds(unittest.TestCase):
    def assertKind(self, kind, lines):
        for line in lines:
            with self.subTest(line=line):
                self.assertEqual(line_kind(line), kind)

    def test_dates_and_times(self):
        self.assertKind("data", ["12.04.2025, 08:15", "3 marca 2025 r.", "Wczoraj o 18:40", "2 godz. temu",
                                 "Edytowano", "Opublikowano: 07.01.2026", "środa, 14:05", "2023"])

    def test_author_lines(self):
        self.assertKind("autor", ["Autor wpisu 3 marca 2025.", "Redakcja portalu · 12.04.2025, 08:15",
                                  "Jan Nowak 5 godz. temu", "Administrator grupy 2 lutego 2026.", "Autor: Ewa Kowal",
                                  "Gazeta Codzienna 15.09.2024", "Nowak · 2 godz.", "Ewa Kowal"])

    def test_handles(self):
        self.assertKind("konto", ["@kowal_88", "kowal_77", "Ewa Kowal @ekowal", "u/sasiad_z_gory"])

    def test_interface_text(self):
        self.assertKind("interfejs", ["Udostępnij", "1,5 tys. polubień · 230 komentarzy", "Lubię to! Odpowiedz",
                                      "Pokaż więcej", "12K views", "Komentarze (34)", "Zobacz tłumaczenie"])

    def test_ocr_debris(self):
        self.assertKind("szum", ["|| ~ ® =", "ii | lf ;", "Pilne!", "---"])

    def test_content_lines_stay(self):
        self.assertKind(None, [
            "Czy to prawda?", "Sejm uchwalił ustawę 15 września 2024.", "Powódź we Wrocławiu 15 września 2024.",
            "Post został usunięty 3 marca 2025.", "Autorka książki zmarła 5 maja 2024", "RZĄD KŁAMIE",
            "Szczepionki Zabijają Dzieci", "PKB: +3,1% r/r", "Inflacja w maju wyniosła 4,1%.",
            "Od 15 lat rząd nic nie zrobił", "Rząd podnosi podatki teraz", "W 2024 r. inflacja spadła.",
            "Czy ktoś to sprawdzał?", "@premier kłamie o podatkach", "https://example.com/artykul-o-czyms"])


class Filter(unittest.TestCase):
    def test_single_line_unchanged(self):
        for s in ["Jan Nowak", "2 godz. temu", "Udostępnij"]:
            self.assertEqual(drop_metadata_lines(s), s)

    def test_never_drops_everything(self):
        s = "Jan Nowak\n2 godz. temu\nUdostępnij"
        self.assertEqual(drop_metadata_lines(s), s)

    def test_keeps_order_of_content(self):
        s = "Ewa Kowal · 3 godz.\nPierwsze zdanie o czymś ważnym.\n87 udostępnień\nDrugie zdanie o czymś innym."
        self.assertEqual(drop_metadata_lines(s), "Pierwsze zdanie o czymś ważnym.\nDrugie zdanie o czymś innym.")


class Extraction(unittest.TestCase):
    def test_post_with_author_date_and_counters_is_one_claim(self):
        cs = extract_claims("Autor wpisu 3 marca 2025.\nRząd zlikwidował podatek od psów w całym kraju.\n"
                            "1,5 tys. polubień · 230 komentarzy")
        self.assertEqual([c.text for c in cs], ["Rząd zlikwidował podatek od psów w całym kraju."])

    def test_question_with_screenshot_text(self):
        # the user's question first, then what a screenshot says (service.py joins them with a newline)
        cs = extract_claims("Czy ktoś to sprawdzał?\nAdministrator grupy 2 lutego 2026.\n"
                            "Ministerstwo wycofało z aptek wszystkie syropy na kaszel.\n87 udostępnień.\n@ewa_k")
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0].query, "Ministerstwo wycofało z aptek wszystkie syropy na kaszel.")
        self.assertNotIn("2026", cs[0].text)

    def test_dated_statement_is_still_a_claim(self):
        cs = extract_claims("Jan Nowak 5 godz. temu\nSejm uchwalił ustawę o podatku cyfrowym 15 września 2024.")
        self.assertEqual(len(cs), 1)
        self.assertIn("15 września 2024", cs[0].query)


if __name__ == "__main__":
    unittest.main()
