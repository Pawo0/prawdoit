"""Draw the screenshot used by scenario F (fixtures/f_screenshot.png): an anonymous social-media post with the claim
that PAP deleted the dispatch, and a visible date. Needs Pillow and a font with Polish letters; the PNG is committed,
so this only has to be run when the fixture should change.

    backend/.venv/bin/python eval/organizers/make_fixtures.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONTS = ["/usr/share/fonts/noto/NotoSans-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"]
LINES = ["Piątkowa depesza PAP ze słowami Donalda Tuska,", "który bagatelizował zagrożenie powodzią,",
         "została usunięta!"]
DATE = "15 września 2024"


def font(size: int):
    for f in FONTS:
        if Path(f).is_file():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def main() -> None:
    img = Image.new("RGB", (1000, 420), "#f5f6f7")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((30, 30, 970, 390), radius=18, fill="white", outline="#d0d5dd", width=2)
    d.ellipse((60, 60, 120, 120), fill="#98a2b3")
    d.text((140, 62), "Użytkownik serwisu społecznościowego", font=font(26), fill="#101828")
    d.text((140, 96), DATE, font=font(22), fill="#667085")
    y = 160
    for line in LINES:
        d.text((60, y), line, font=font(34), fill="#101828")
        y += 52
    d.text((60, 340), "1,2 tys. udostępnień", font=font(20), fill="#667085")
    out = HERE / "fixtures" / "f_screenshot.png"
    out.parent.mkdir(exist_ok=True)
    img.save(out, optimize=True)
    print("wrote", out, out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
