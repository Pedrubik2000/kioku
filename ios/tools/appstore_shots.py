"""App Store screenshots: the README's iPhone screenshots under a caption.

Writes build/appstore-shots/<n>-<name>.png at 1290×2796, the 6.9" iPhone
size App Store Connect accepts, from docs/images/ios-*.png.

Usage: python3 ios/tools/appstore_shots.py   (from anywhere)
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

IOS = Path(__file__).resolve().parents[1]
IMAGES = IOS.parent / "docs/images"
OUT = IOS / "build/appstore-shots"
SIZE = (1290, 2796)
TOP, BOTTOM = "#2563EB", "#1E3A8A"  # the icon's blue, darkened downwards
SHOT_WIDTH = 1000
RADIUS = 56
FONT = "/System/Library/Fonts/SFNS.ttf"

SHOTS = [
    ("decks", "Your whole collection,\nin your pocket"),
    ("review-hanzi-answer", "Review with the\ndesktop scheduler"),
    ("browse", "The full desktop\ncard browser"),
    ("stats", "Statistics, charts\nand forecasts"),
    ("review-neetcode-question", "Any card template:\ncode, tables, maths"),
    ("add", "Add and edit notes\nlike on your computer"),
]


def gradient():
    mask = Image.linear_gradient("L").resize(SIZE)
    return Image.composite(Image.new("RGB", SIZE, BOTTOM), Image.new("RGB", SIZE, TOP), mask)


def framed(name):
    shot = Image.open(IMAGES / f"ios-{name}.png").convert("RGB")
    height = round(shot.height * SHOT_WIDTH / shot.width)
    shot = shot.resize((SHOT_WIDTH, height), Image.LANCZOS)
    big = (SHOT_WIDTH * 4, height * 4)
    mask = Image.new("L", big, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, big[0] - 1, big[1] - 1), RADIUS * 4, fill=255)
    return shot, mask.resize(shot.size, Image.LANCZOS)


def page(name, caption):
    img = gradient()
    font = ImageFont.truetype(FONT, 104)
    font.set_variation_by_name("Bold")
    draw = ImageDraw.Draw(img)
    draw.multiline_text((SIZE[0] / 2, 290), caption, font=font, fill="white",
                        anchor="mm", align="center", spacing=24)
    shot, mask = framed(name)
    x, y = (SIZE[0] - shot.width) // 2, 540
    shadow = Image.new("L", SIZE, 0)
    shadow.paste(mask, (x, y + 24))
    shadow = shadow.filter(ImageFilter.GaussianBlur(40)).point(lambda v: v * 0.45)
    img.paste(Image.new("RGB", SIZE, "#0B1A4A"), (0, 0), shadow)
    img.paste(shot, (x, y), mask)
    return img


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for i, (name, caption) in enumerate(SHOTS, 1):
        out = OUT / f"{i}-{name}.png"
        page(name, caption).save(out)
        print(out)
