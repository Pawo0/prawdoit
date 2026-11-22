"""Local screenshot-to-text conversion with image limits and explicit OCR failures.

Text from a screenshot (scenario F): local Tesseract OCR, no cloud service.

The image is decoded with Pillow (format allow-list, pixel cap, metadata dropped), turned upright (EXIF orientation),
flattened onto a solid background when it has transparency, converted to grayscale and upscaled when small, then
piped to the `tesseract` binary on stdin. Nothing is written to disk and the image is never stored: only the
recognised text continues through the normal text pipeline (PII masking, prompt-injection scan, claim extraction).
In the container the binary and the Polish data come from the Debian packages `tesseract-ocr` and
`tesseract-ocr-pol` (Dockerfile). Without the binary the service answers with a technical notice, never with a verdict.

Tesseract returns words with their confidence and position (TSV). That is used twice:
- a first read with small letters is repeated larger; a weak one (few confident words) is retried with light text
  on a busy background (memes) as dark ink and with the page turned by the orientation Tesseract detects; the read
  with the most confident words wins, all passes together within PRAWDOWID_OCR_TIMEOUT_S;
- the text is rebuilt line by line. A screenshot of a post is mostly interface: author and date, counters, buttons,
  a phone's status bar. Each of those stays a line of its own, so the metadata filter (linefilter.py) can drop it
  before claim extraction; only a sentence wrapped over several lines is joined back. Icons read as stray symbols
  ("©", "@", "$") are removed, so that "3 marca 2025 · 🌐" is still recognised as a date line.

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
import statistics
import subprocess
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image

log = logging.getLogger(__name__)

MAX_IMAGE_BYTES = int(os.environ.get("PRAWDOWID_MAX_IMAGE_BYTES", str(6_000_000)))
MAX_PIXELS = 40_000_000  # decompression-bomb guard (Pillow's own limit is a warning below 2x this)
FORMATS = {"PNG", "JPEG", "WEBP", "BMP", "TIFF", "GIF"}
TIMEOUT_S = float(
    os.environ.get("PRAWDOWID_OCR_TIMEOUT_S", "30")
)  # whole read, all passes together
CMD = os.environ.get("PRAWDOWID_TESSERACT_CMD", "tesseract")

# Tesseract reads best when letters are roughly 20-40 px high. Below SMALL_TEXT_PX (median word box height) the image is
# read again, scaled so that words are about TARGET_TEXT_PX high, within MAX_OCR_PIXELS (time grows with pixels).
SMALL_TEXT_PX = 18
TARGET_TEXT_PX = 32
MAX_OCR_PIXELS = 16_000_000
# a first read is "weak" (worth another preparation) with fewer confident words than this or a low mean confidence
WEAK_WORDS = 8
WEAK_CONF = 75.0


class OcrUnavailable(RuntimeError):
    """No tesseract binary (or no usable language data) on this server."""


class OcrError(ValueError):
    """The input is not an image we accept, or it could not be read."""


def _exe() -> str | None:
    return shutil.which(CMD)


@lru_cache(maxsize=1)
def _installed() -> frozenset[str]:
    exe = _exe()
    if not exe:
        raise OcrUnavailable("brak programu tesseract")
    out = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=10).stdout
    return frozenset(line.strip() for line in out.splitlines()[1:])


def _languages() -> str:
    langs = [x for x in ("pol", "eng") if x in _installed()]
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


# ------------------------------------------------------------------ image preparation
def load(data: bytes) -> Image:
    """Validated RGB image: first frame, upright, no transparency, no metadata."""
    from PIL import Image, ImageOps, UnidentifiedImageError

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
            # A phone stores a photo as the sensor saw it plus an EXIF Orientation tag; viewers turn it, Tesseract
            # does not (a sideways photo reads as mirrored gibberish). The tag goes with the rest of the metadata.
            upright = ImageOps.exif_transpose(im)
            return _flatten(upright)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise OcrError("nie udało się odczytać obrazu") from e


def _flatten(im: Image) -> Image:
    """RGB without transparency. Transparent pixels usually hold RGB 0,0,0, so a plain conversion turns a transparent
    background black and dark text on it disappears: dark ink goes onto white, light ink onto black.
    """
    from PIL import Image, ImageStat

    if im.mode not in ("RGBA", "LA", "PA") and "transparency" not in im.info:
        return im.convert("RGB")
    rgba = im.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] == 255:
        return rgba.convert("RGB")
    visible = alpha.point(lambda a: 255 if a > 127 else 0)
    stat = ImageStat.Stat(rgba.convert("L"), visible)
    ink = stat.mean[0] if stat.count[0] else 0.0
    background = (255, 255, 255, 255) if ink < 128 else (0, 0, 0, 255)
    return Image.alpha_composite(Image.new("RGBA", rgba.size, background), rgba).convert("RGB")


def _scaled(gray: Image, factor: float) -> Image:
    from PIL import Image

    if abs(factor - 1) < 0.05:
        return gray
    return gray.resize((round(gray.width * factor), round(gray.height * factor)), Image.LANCZOS)


def _base_factor(gray: Image) -> float:
    return (
        2.0 if gray.width < 1000 else 1.0
    )  # small screenshots: tesseract reads ~2x upscaled text much better


def prepare(data: bytes) -> bytes:
    """Validated, metadata-free grayscale PNG for tesseract (the first pass of read_text)."""
    gray = load(data).convert("L")
    return _png(_scaled(gray, _base_factor(gray)))


def _png(im: Image) -> bytes:
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def _bright_ink(rgb: Image) -> Image:
    """Meme text: white letters with a dark outline over a photo. Thresholding the grayscale image mixes the letters
    with the background; bright, colourless pixels as black ink on white keep only the letters."""
    import numpy as np
    from PIL import Image

    a = np.asarray(rgb, dtype=np.int16)
    lo, hi = a.min(axis=2), a.max(axis=2)
    ink = (lo > 200) & (hi - lo < 40)
    return Image.fromarray(np.where(ink, 0, 255).astype(np.uint8))


# ------------------------------------------------------------------ tesseract
@dataclass
class Word:
    text: str
    conf: float
    left: int
    top: int
    width: int
    height: int
    line: tuple[int, int, int]  # block, paragraph, line as numbered by tesseract

    @property
    def right(self) -> int:
        return self.left + self.width


@dataclass
class Reading:
    """One tesseract pass: its words and the image they were read from (size after scaling)."""

    words: list[Word]
    size: tuple[int, int]
    label: str = ""

    @property
    def confident(self) -> list[Word]:
        return [w for w in self.words if w.conf >= 60 and sum(c.isalpha() for c in w.text) >= 3]

    @property
    def score(self) -> float:
        return sum(w.conf / 100 for w in self.confident)

    @property
    def text_height(self) -> float:
        return statistics.median(w.height for w in self.confident) if self.confident else 0.0

    @property
    def weak(self) -> bool:
        wordy = [w.conf for w in self.words if sum(c.isalpha() for c in w.text) >= 3]
        return len(self.confident) < WEAK_WORDS or not wordy or statistics.mean(wordy) < WEAK_CONF


def _run(args: list[str], png: bytes, deadline: float) -> subprocess.CompletedProcess:
    left = deadline - time.monotonic()
    if left <= 0:
        raise OcrError("odczyt obrazu trwał zbyt długo")
    try:
        return subprocess.run(
            [_exe() or CMD, "stdin", "stdout", *args], input=png, capture_output=True, timeout=left
        )
    except subprocess.TimeoutExpired as e:
        raise OcrError("odczyt obrazu trwał zbyt długo") from e
    except OSError as e:
        raise OcrUnavailable(str(e)) from e


def _tesseract(im: Image, langs: str, deadline: float, label: str) -> Reading:
    proc = _run(["-l", langs, "tsv"], _png(im), deadline)
    if proc.returncode != 0:
        log.warning("tesseract exit %s: %s", proc.returncode, proc.stderr[-300:])
        raise OcrError("nie udało się odczytać tekstu z obrazu")
    return Reading(parse_tsv(proc.stdout.decode("utf-8", "replace")), im.size, label)


def parse_tsv(tsv: str) -> list[Word]:
    """Word rows (level 5) of tesseract's TSV output, in reading order."""
    words = []
    for row in tsv.splitlines()[1:]:
        f = row.split("\t")
        if len(f) != 12 or f[0] != "5" or not f[11].strip():
            continue
        try:
            words.append(
                Word(
                    f[11].strip(),
                    float(f[10]),
                    int(f[6]),
                    int(f[7]),
                    int(f[8]),
                    int(f[9]),
                    (int(f[2]), int(f[3]), int(f[4])),
                )
            )
        except ValueError:
            continue
    return words


def _rotation(im: Image, deadline: float) -> int:
    """Clockwise angle that makes the page upright according to tesseract's orientation detection; 0 when unsure."""
    if "osd" not in _installed():
        return 0
    proc = _run(["--psm", "0", "-l", "osd"], _png(im), deadline)
    out = proc.stdout.decode("utf-8", "replace")
    angle = re.search(r"Rotate:\s*(\d+)", out)
    conf = re.search(r"Orientation confidence:\s*([\d.]+)", out)
    if proc.returncode or not angle or not conf or float(conf.group(1)) < 2.0:
        return 0
    return int(angle.group(1)) % 360


def _best_reading(rgb: Image, langs: str, deadline: float) -> Reading:
    """First pass as before; a weak or tiny-text read is retried with other preparations, the most confident wins."""
    gray = rgb.convert("L")
    base = _base_factor(gray)
    best = _tesseract(_scaled(gray, base), langs, deadline, "szarość")
    retries = []
    if 0 < best.text_height < SMALL_TEXT_PX:  # e.g. a desktop page captured at 1x: body text ~13 px
        factor = min(
            base * TARGET_TEXT_PX / best.text_height,
            4.0,
            (MAX_OCR_PIXELS / (gray.width * gray.height)) ** 0.5,
        )
        if factor > base * 1.2:
            retries.append(("powiększenie", lambda: _scaled(gray, factor)))
    if best.weak:
        retries.append(("jasny tekst", lambda: _scaled(_bright_ink(rgb), base)))

        def turned():
            first = _scaled(gray, base)
            angle = _rotation(first, deadline)
            return first.rotate(-angle, expand=True) if angle else None

        retries.append(("obrót", turned))
    for label, make in retries:
        if time.monotonic() > deadline - 2:
            break
        im = make()
        if im is None:
            continue
        reading = _tesseract(im, langs, deadline, label)
        if reading.score > best.score:
            best = reading
    return best


def read_text(data: bytes) -> str:
    """Recognised text, one line per text line of the image (a sentence wrapped over several lines is one line)."""
    langs = _languages()
    rgb = load(data)
    deadline = time.monotonic() + TIMEOUT_S
    reading = _best_reading(rgb, langs, deadline)
    log.info("ocr: %s, %d words, score %.1f", reading.label, len(reading.words), reading.score)
    return lines_to_text(reading)


# ------------------------------------------------------------------ words -> lines
_TERMINAL = ".!?…:;"
_SEPARATORS = {"-", "–", "—", "|", "·", "•"}
_PUNCT = set(".,:;!?%()[]'\"„”«»-–—/")


def _keep(word: Word, line_height: float) -> bool:
    """Drop what icons and avatars turn into: stray symbols ("©", "@", "$", "#"), a single character glued to a
    symbol ("O©"), a letter much taller than the line around it (an avatar circle read as "O"), and words tesseract
    itself could not read (confidence below 20)."""
    t = word.text
    alnum = sum(c.isalnum() for c in t)
    if word.conf < 20:
        return False
    if alnum == 0:
        return t in _SEPARATORS
    if alnum == 1 and any(not c.isalnum() and c not in _PUNCT for c in t):
        return False
    if alnum <= 2 and line_height and word.height > 1.7 * line_height:
        return False
    return True


@dataclass
class _Line:
    words: list[Word]
    key: tuple[int, int, int]
    full: bool = (
        False  # as wide as the widest line around it (75%): the text wrapped here because the line was full
    )

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def left(self) -> int:
        return min(w.left for w in self.words)

    @property
    def right(self) -> int:
        return max(w.right for w in self.words)

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def top(self) -> int:
        return min(w.top for w in self.words)

    @property
    def bottom(self) -> int:
        return max(w.top + w.height for w in self.words)

    @property
    def height(self) -> float:
        """Font size: the tallest real word (one with both an ascender and a descender spans the full height; a median
        would depend on which letters the line happens to contain)."""
        wordy = [w.height for w in self.words if sum(c.isalnum() for c in w.text) >= 2]
        return max(wordy or [w.height for w in self.words])


def _split_gaps(line: _Line) -> list[_Line]:
    """Tesseract sometimes reads two columns side by side as one line (a date and a sidebar entry, a counter on the
    left and one on the right): a gap wider than a few letter heights starts a new line."""
    words, height = line.words, line.height
    out = [[words[0]]]
    for prev, w in zip(words, words[1:]):
        if w.left - prev.right > 2.5 * height:
            out.append([])
        out[-1].append(w)
    pieces = [_Line(ws, line.key) for ws in out]
    for piece in pieces:  # "· 15 wrz 2024" after the split: the separator belonged to the gap
        while piece.words and piece.words[0].text in _SEPARATORS:
            piece.words.pop(0)
    return [p for p in pieces if p.words]


def _status_bar(line: _Line, size: tuple[int, int]) -> bool:
    """A phone screenshot's top row: clock, signal, battery."""
    w, h = size
    return (
        h > 1.5 * w
        and line.bottom < 0.05 * h
        and bool(re.search(r"\b\d{1,2}[:.]\d{2}\b", line.text))
    )


def _continues(a: _Line, b: _Line) -> bool:
    """b is the rest of a sentence wrapped from a. Tesseract often puts the continuation into a new block (a chat
    bubble, centred text), so this is decided from the layout: b directly below a in the same column, letters of a
    similar size, no final punctuation in a; then b starts in lower case or a ends with a comma or hyphen, or a is as
    wide as the text around it (it wrapped because the line was full). A line that is metadata on its own (a name, a
    date, counters) is never joined to its neighbour this way, so a byline does not swallow the message.
    """
    from .linefilter import line_kind

    if a.text[-1] in _TERMINAL or b.top <= a.top:
        return False
    tall = max(a.height, b.height)
    if b.top - a.bottom > tall:
        return False
    if min(a.right, b.right) - max(a.left, b.left) < 0.3 * min(a.width, b.width):
        return False  # side by side or in another column
    sizes = tall / max(min(a.height, b.height), 1)
    first = b.text[0]
    if (first.islower() or a.text[-1] in ",-–") and sizes < 1.5:
        return True
    return (
        sizes < 1.25
        and a.full
        and (first.isupper() or first.isdigit())
        and line_kind(a.text) is None
        and line_kind(b.text) is None
    )


def lines_to_text(reading: Reading) -> str:
    """One line per text line, wrapped sentences joined; a line without final punctuation ends with a period, so a
    byline, a date and a headline do not merge into one 'sentence' for claim extraction."""
    rows: dict[tuple[int, int, int], list[Word]] = {}
    for w in reading.words:
        rows.setdefault(w.line, []).append(w)
    lines: list[_Line] = []
    for key, words in rows.items():
        wordy = [w.height for w in words if sum(c.isalnum() for c in w.text) >= 2]
        kept = [w for w in words if _keep(w, statistics.median(wordy) if wordy else 0)]
        while kept and kept[0].text in _SEPARATORS:
            kept.pop(0)
        if kept and not _status_bar(row := _Line(kept, key), reading.size):
            lines += _split_gaps(row)
    widest: dict[int, int] = {}
    for ln in lines:
        widest[ln.key[0]] = max(widest.get(ln.key[0], 0), ln.width)
    out: list[str] = []
    prev: _Line | None = None
    for ln in lines:
        if prev is not None:
            prev.full = prev.width >= 0.75 * max(widest[prev.key[0]], widest[ln.key[0]])
        if prev is not None and _continues(prev, ln):
            out[-1] = f"{out[-1]} {ln.text}"
        else:
            out.append(ln.text)
        prev = ln
    return "\n".join(_end(s) for s in out if s.strip(" -–—|·•"))


def _end(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip().rstrip(",-–—|·• ")
    return line if line and line[-1] in _TERMINAL else line + "."


def blocks_to_sentences(text: str) -> str:
    """Plain-text tesseract output (blocks separated by blank lines) to one line per block. Kept for text that does
    not come with positions; read_text uses lines_to_text."""
    out = []
    for block in re.split(r"\n\s*\n", text):
        line = re.sub(r"\s+", " ", block).strip()
        if not line:
            continue
        out.append(line if line[-1] in _TERMINAL else line + ".")
    return "\n".join(out)
