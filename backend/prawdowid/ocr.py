"""Local screenshot-to-text conversion with image limits and explicit OCR failures.

Text from a screenshot (scenario F): local Tesseract OCR, no cloud service.

The image is decoded with Pillow (format allow-list, pixel cap, EXIF and other metadata dropped), converted to
grayscale and upscaled when small, then piped to the `tesseract` binary on stdin. Nothing is written to disk and
the image is never stored: only the recognised text continues through the normal text pipeline (PII masking,
prompt-injection scan, claim extraction). In the container the binary and the Polish data come from the Debian
packages `tesseract-ocr` and `tesseract-ocr-pol` (Dockerfile). Without the binary the service answers with a
technical notice, never with a verdict.

Reading guide: docs/backend/REQUEST_FLOW.md. Module map: docs/backend/MODULES.md.
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import os
import re
import shutil
import subprocess
from functools import lru_cache

log = logging.getLogger(__name__)

MAX_IMAGE_BYTES = int(os.environ.get("PRAWDOWID_MAX_IMAGE_BYTES", str(6_000_000)))
MAX_PIXELS = 40_000_000  # decompression-bomb guard (Pillow's own limit is a warning below 2x this)
FORMATS = {"PNG", "JPEG", "WEBP", "BMP", "TIFF", "GIF"}
TIMEOUT_S = float(os.environ.get("PRAWDOWID_OCR_TIMEOUT_S", "30"))
CMD = os.environ.get("PRAWDOWID_TESSERACT_CMD", "tesseract")


class OcrUnavailable(RuntimeError):
    """No tesseract binary (or no usable language data) on this server."""


class OcrError(ValueError):
    """The input is not an image we accept, or it could not be read."""


def _exe() -> str | None:
    return shutil.which(CMD)


@lru_cache(maxsize=1)
def _languages() -> str:
    exe = _exe()
    if not exe:
        raise OcrUnavailable("brak programu tesseract")
    out = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=10).stdout
    have = {line.strip() for line in out.splitlines()[1:]}
    langs = [x for x in ("pol", "eng") if x in have]
    if not langs:
        raise OcrUnavailable("brak danych języka polskiego dla tesseract")
    return "+".join(langs)


def available() -> bool:
    try:
        return bool(_languages())
    except (OcrUnavailable, OSError, subprocess.SubprocessError):
        return False


def decode_b64(value: str) -> bytes:
    """Base64, optionally as a data URL ("data:image/png;base64,...")."""
    value = value.strip()
    if value.startswith("data:"):
        value = value.partition(",")[2]
    try:
        data = base64.b64decode(re.sub(r"\s+", "", value), validate=True)
    except (binascii.Error, ValueError) as e:
        raise OcrError("obraz nie jest poprawnie zakodowany (base64)") from e
    if not data:
        raise OcrError("pusty obraz")
    if len(data) > MAX_IMAGE_BYTES:
        raise OcrError(f"obraz jest za duży (limit {MAX_IMAGE_BYTES // 1_000_000} MB)")
    return data


def prepare(data: bytes) -> bytes:
    """Validated, metadata-free grayscale PNG for tesseract."""
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in FORMATS:
                raise OcrError(
                    f"nieobsługiwany format obrazu ({im.format}); obsługiwane: PNG, JPEG, WebP"
                )
            w, h = im.size
            if w * h > MAX_PIXELS:
                raise OcrError("obraz ma zbyt wiele pikseli")
            im.seek(0)  # first frame of an animated GIF / WebP
            g = im.convert("L")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise OcrError("nie udało się odczytać obrazu") from e
    if g.width < 1000:  # small screenshots: tesseract reads ~2x upscaled text much better
        g = g.resize((g.width * 2, g.height * 2), Image.LANCZOS)
    out = io.BytesIO()
    g.save(out, format="PNG")
    return out.getvalue()


def read_text(data: bytes) -> str:
    """Recognised text, whitespace kept per line (dates and headlines stay on their own lines)."""
    langs = _languages()
    png = prepare(data)
    try:
        proc = subprocess.run(
            [_exe() or CMD, "stdin", "stdout", "-l", langs],
            input=png,
            capture_output=True,
            timeout=TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as e:
        raise OcrError("odczyt obrazu trwał zbyt długo") from e
    except OSError as e:
        raise OcrUnavailable(str(e)) from e
    if proc.returncode != 0:
        log.warning("tesseract exit %s: %s", proc.returncode, proc.stderr[-300:])
        raise OcrError("nie udało się odczytać tekstu z obrazu")
    return blocks_to_sentences(proc.stdout.decode("utf-8", "replace"))


def blocks_to_sentences(text: str) -> str:
    """Tesseract separates text blocks by blank lines and wraps lines inside a block. A block becomes one line;
    a block without final punctuation ends with a period, so a byline, a date and a headline do not merge into
    one 'sentence' for claim extraction."""
    out = []
    for block in re.split(r"\n\s*\n", text):
        line = re.sub(r"\s+", " ", block).strip()
        if not line:
            continue
        out.append(line if line[-1] in ".!?…:;" else line + ".")
    return "\n".join(out)
