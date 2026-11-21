"""Screenshot input (ocr.py, service._read_image): no tesseract binary or model needed."""
import base64
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402

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


class Blocks(unittest.TestCase):
    def test_blocks_become_sentences(self):
        raw = ("© Użytkownik serwisu\n15 września 2024\n\nPiątkowa depesza PAP ze słowami Donalda Tuska,\n"
               "została usunięta!\n\n1,2 tys. udostępnień\n")
        self.assertEqual(ocr.blocks_to_sentences(raw),
                         "© Użytkownik serwisu 15 września 2024.\n"
                         "Piątkowa depesza PAP ze słowami Donalda Tuska, została usunięta!\n1,2 tys. udostępnień.")


class ServiceNoBinary(unittest.TestCase):
    def test_missing_tesseract_is_a_technical_notice_not_a_verdict(self):
        from prawdowid import service
        from prawdowid.schemas import CheckRequest, CheckResult
        res = CheckResult(id="t", created_at="2026-01-01T00:00:00+00:00", channel="web", status="ok",
                          input_kind="text", input_excerpt="", engine={})
        req = CheckRequest(text="Czy Demagog to sprawdzał?", image_b64=base64.b64encode(png()).decode())
        with mock.patch.object(ocr, "_exe", return_value=None), mock.patch.object(service.store, "log_error"):
            ocr._languages.cache_clear()
            text = service._read_image(req, res, "t", {})
        ocr._languages.cache_clear()
        self.assertEqual((text, res.status, res.input_kind), ("", "blad_techniczny", "image"))
        self.assertIn("nie ocena treści", res.status_message)


if __name__ == "__main__":
    unittest.main()
