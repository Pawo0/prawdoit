"""Screenshot input (ocr.py, service._read_image): no tesseract binary or model needed.

Image preparation is tested on images drawn here; the text rebuilt from tesseract's TSV output is tested on TSV rows
written by hand, with the layouts tesseract returned for real screenshots (eval: phone post, chat bubble, news page)."""
import base64
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw  # noqa: E402

from prawdowid import ocr  # noqa: E402


def png(w=40, h=20) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(out, format="PNG")
    return out.getvalue()


class Decode(unittest.TestCase):
    def test_data_url_and_plain_base64(self):
        raw = png()
        b64 = base64.b64encode(raw).decode()
        self.assertEqual(ocr.decode_b64(b64), raw)
        self.assertEqual(ocr.decode_b64("data:image/png;base64," + b64), raw)

    def test_rejects_garbage_and_oversize(self):
        with self.assertRaises(ocr.OcrError):
            ocr.decode_b64("not base64 !!!")
        with mock.patch.object(ocr, "MAX_IMAGE_BYTES", 10), self.assertRaises(ocr.OcrError):
            ocr.decode_b64(base64.b64encode(png()).decode())


class Prepare(unittest.TestCase):
    def test_small_image_upscaled_grayscale_png(self):
        out = Image.open(io.BytesIO(ocr.prepare(png(400, 100))))
        self.assertEqual((out.format, out.mode, out.size), ("PNG", "L", (800, 200)))

    def test_not_an_image(self):
        with self.assertRaises(ocr.OcrError):
            ocr.prepare(b"%PDF-1.4 not an image")

    def test_pixel_cap(self):
        with mock.patch.object(ocr, "MAX_PIXELS", 100), self.assertRaises(ocr.OcrError):
            ocr.prepare(png(40, 20))

    def test_exif_orientation_is_applied(self):
        # a phone photo: pixels stored sideways (300 wide, 100 high) + Orientation=6 ("turn 90° clockwise to view")
        im = Image.new("RGB", (300, 100), "white")
        ImageDraw.Draw(im).rectangle((0, 0, 29, 99), fill="black")  # dark band on the stored left edge
        exif = Image.Exif()
        exif[0x0112] = 6
        out = io.BytesIO()
        im.save(out, format="JPEG", exif=exif.tobytes(), quality=95)
        upright = ocr.load(out.getvalue())
        self.assertEqual(upright.size, (100, 300))
        self.assertLess(upright.getpixel((50, 10))[0], 60)  # the band is now at the top, as a viewer shows it
        self.assertGreater(upright.getpixel((50, 290))[0], 200)
        self.assertNotIn(0x0112, upright.getexif())  # not applied twice downstream

    def test_transparent_background(self):
        # text pixels opaque, background transparent with RGB 0,0,0 (what most tools write)
        def sticker(ink):
            im = Image.new("RGBA", (60, 20), (0, 0, 0, 0))
            ImageDraw.Draw(im).rectangle((10, 5, 30, 15), fill=ink)
            out = io.BytesIO()
            im.save(out, format="PNG")
            return ocr.load(out.getvalue()).convert("L")

        dark = sticker((0, 0, 0, 255))
        self.assertEqual((dark.getpixel((20, 10)), dark.getpixel((50, 2))), (0, 255))  # dark ink on white
        light = sticker((255, 255, 255, 255))
        self.assertEqual((light.getpixel((20, 10)), light.getpixel((50, 2))), (255, 0))  # light ink on black

    def test_bright_ink_mask(self):
        im = Image.new("RGB", (40, 10), (120, 80, 60))  # brownish photo
        ImageDraw.Draw(im).rectangle((5, 2, 15, 8), fill=(250, 250, 250))  # white meme letter
        ImageDraw.Draw(im).rectangle((25, 2, 35, 8), fill=(250, 220, 40))  # bright but coloured: not text
        mask = ocr._bright_ink(im)
        self.assertEqual((mask.getpixel((10, 5)), mask.getpixel((30, 5)), mask.getpixel((1, 1))), (0, 255, 255))


# ------------------------------------------------------------------ TSV -> text
def tsv(*lines) -> str:
    """lines: (block, par, line, left, top, height, [(word, conf), ...]); words laid out left to right."""
    rows = ["level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"]
    for block, par, line, left, top, height, words in lines:
        x = left
        for i, (word, conf) in enumerate(words, 1):
            width = int(len(word) * height * 0.5)
            rows.append(f"5\t1\t{block}\t{par}\t{line}\t{i}\t{x}\t{top}\t{width}\t{height}\t{conf}\t{word}")
            x += width + height // 3
    return "\n".join(rows)


def words(text, conf=95):
    return [(w, conf) for w in text.split()]


def rebuild(tsv_text, size=(1200, 900)):
    return ocr.lines_to_text(ocr.Reading(ocr.parse_tsv(tsv_text), size))


class Lines(unittest.TestCase):
    def test_post_metadata_stays_on_its_own_lines(self):
        # desktop post: name and date (one paragraph, with the globe icon read as "@"), the message, counters with
        # the reaction icons read as "4 O©", buttons
        text = rebuild(tsv(
            (1, 1, 1, 168, 80, 20, words("Jan Kowalski")),
            (1, 1, 2, 169, 112, 18, words("3 marca 2025 -") + [("@", 84)]),
            (2, 1, 1, 74, 176, 22, words("Ukraina w ogóle nie płaci Orlenowi za dostarczane paliwo. My płacimy za")),
            (2, 1, 2, 74, 216, 22, words("wszystko, a oni nic.")),
            (3, 1, 1, 82, 294, 28, [("4", 82), ("O©", 77)] + words("2,4 tys. 318 komentarzy - 1,2 tys. udostępnień")),
        ))
        self.assertEqual(text.split("\n"), [
            "Jan Kowalski.", "3 marca 2025.",
            "Ukraina w ogóle nie płaci Orlenowi za dostarczane paliwo. My płacimy za wszystko, a oni nic.",
            "4 2,4 tys. 318 komentarzy - 1,2 tys. udostępnień."])

    def test_wrapped_sentence_joined_across_blocks(self):
        # chat bubble: tesseract starts a new block in the middle of the sentence; the next line starts with a name
        text = rebuild(tsv(
            (5, 1, 1, 76, 480, 32, words("Mama")),
            (5, 1, 2, 76, 542, 30, words("Przekazane dalej wiele razy")),
            (5, 1, 3, 76, 590, 54, words("Piątkowa depesza PAP ze słowami Donalda")),
            (6, 1, 1, 73, 666, 54, words("Tuska, który bagatelizował zagrożenie")),
            (6, 1, 2, 76, 742, 54, words("powodzią, została usunięta!")),
        ), size=(1560, 2800))
        self.assertEqual(text.split("\n"), [
            "Mama.", "Przekazane dalej wiele razy.",
            "Piątkowa depesza PAP ze słowami Donalda Tuska, który bagatelizował zagrożenie powodzią, została usunięta!"])

    def test_lower_case_continuation_of_centred_text(self):
        text = rebuild(tsv(
            (1, 1, 1, 121, 382, 40, words("We Włoszech, w Toskanii, wilk rzucił")),
            (2, 1, 1, 300, 454, 52, words("się na dwulatka.")),
        ))
        self.assertEqual(text, "We Włoszech, w Toskanii, wilk rzucił się na dwulatka.")

    def test_name_and_date_not_joined_even_when_wide(self):
        text = rebuild(tsv(
            (3, 1, 1, 189, 360, 34, words("Patriota Polski 1966")),
            (3, 1, 2, 189, 400, 32, words("15 września 2024")),
        ))
        self.assertEqual(text.split("\n"), ["Patriota Polski 1966.", "15 września 2024."])

    def test_side_by_side_columns_split(self):
        # a date line and a sidebar entry far to the right, read as one line
        text = rebuild(tsv(
            (5, 1, 1, 41, 149, 10, words("3 marca 2025, 08:41 - Redakcja")),
            (5, 1, 1, 947, 149, 10, words("2. Ekstraklasa: remis w hicie kolejki")),
        ))
        self.assertEqual(text.split("\n"), ["3 marca 2025, 08:41 - Redakcja.", "2. Ekstraklasa: remis w hicie kolejki."])

    def test_status_bar_avatar_and_unreadable_words_dropped(self):
        text = rebuild(tsv(
            (1, 1, 1, 87, 50, 35, words("17:02 wall 5G 64%")),  # phone status bar
            (2, 1, 1, 35, 300, 78, [("O", 78)]),  # avatar circle as a letter, taller than the name next to it
            (2, 1, 1, 136, 320, 30, words("Patriota Polski") + [("patriota", 0), ("1966", 0)] + words("- 15 wrz 2024")),
        ), size=(1170, 2532))
        self.assertEqual(text.split("\n"), ["Patriota Polski.", "15 wrz 2024."])

    def test_blocks_become_sentences(self):
        raw = ("© Użytkownik serwisu\n15 września 2024\n\nPiątkowa depesza PAP ze słowami Donalda Tuska,\n"
               "została usunięta!\n\n1,2 tys. udostępnień\n")
        self.assertEqual(ocr.blocks_to_sentences(raw),
                         "© Użytkownik serwisu 15 września 2024.\n"
                         "Piątkowa depesza PAP ze słowami Donalda Tuska, została usunięta!\n1,2 tys. udostępnień.")


class Passes(unittest.TestCase):
    """read_text without a binary: _tesseract is replaced by canned readings."""

    def reading(self, text, conf, height=30, label=""):
        ws = [ocr.Word(w, conf, 10 + 60 * i, 10, 50, height, (1, 1, 1)) for i, w in enumerate(text.split())]
        return ocr.Reading(ws, (600, 400), label)

    def run_with(self, readings, osd=0):
        calls = []

        def fake(im, langs, deadline, label):
            calls.append(label)
            return readings[label]

        with mock.patch.object(ocr, "_tesseract", side_effect=fake), \
                mock.patch.object(ocr, "_languages", return_value="pol+eng"), \
                mock.patch.object(ocr, "_rotation", return_value=osd):
            out = ocr.read_text(png(300, 200))
        return out, calls

    def test_confident_first_read_is_kept(self):
        good = self.reading("Ukraina w ogóle nie płaci Orlenowi za dostarczane paliwo ani za gaz", 95)
        out, calls = self.run_with({"szarość": good})
        self.assertEqual(calls, ["szarość"])
        self.assertIn("Orlenowi", out)

    def test_weak_read_retried_and_best_wins(self):
        readings = {
            "szarość": self.reading("WERERG R ASRS W", 55),
            "jasny tekst": self.reading("WEDŁUG GUS INFLACJA W MARCU 2026 SIĘGNĘŁA AŻ 8%", 95),
            "obrót": self.reading("nic", 30),
        }
        out, calls = self.run_with(readings, osd=90)
        self.assertEqual(calls, ["szarość", "jasny tekst", "obrót"])
        self.assertEqual(out, "WEDŁUG GUS INFLACJA W MARCU 2026 SIĘGNĘŁA AŻ 8%.")

    def test_small_text_read_again_larger(self):
        readings = {"szarość": self.reading("Ukraina nie płaci Orlenowi za paliwo dostarczane przez spółkę", 92, 12),
                    "powiększenie": self.reading("Ukraina nie płaci Orlenowi za paliwo dostarczane przez spółkę od lat",
                                                 93, 30)}
        out, calls = self.run_with(readings)
        self.assertEqual(calls, ["szarość", "powiększenie"])
        self.assertTrue(out.endswith("od lat."))


class ServiceNoBinary(unittest.TestCase):
    def test_missing_tesseract_is_a_technical_notice_not_a_verdict(self):
        from prawdowid import service
        from prawdowid.schemas import CheckRequest, CheckResult
        res = CheckResult(id="t", created_at="2026-01-01T00:00:00+00:00", channel="web", status="ok",
                          input_kind="text", input_excerpt="", engine={})
        req = CheckRequest(text="Czy Demagog to sprawdzał?", image_b64=base64.b64encode(png()).decode())
        with mock.patch.object(ocr, "_exe", return_value=None), mock.patch.object(service.store, "log_error"):
            ocr._installed.cache_clear()
            text = service._read_image(req, res, "t", {})
        ocr._installed.cache_clear()
        self.assertEqual((text, res.status, res.input_kind), ("", "blad_techniczny", "image"))
        self.assertIn("nie ocena treści", res.status_message)


if __name__ == "__main__":
    unittest.main()
