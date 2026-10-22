"""The README's screenshot strips: four screenshots of a variant side by side.

Writes docs/images/strip-<variant>.png from the screenshots taken by the
variants' readme_shots scripts. Rounded corners and a thin outline on a
transparent background, so the strip reads on light and dark pages.

Usage: python3 shared/tools/make_readme_strips.py   (from anywhere)
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
HEIGHT = 650  # of each screenshot in the strip
GAP = 24
RADIUS = 28
OUTLINE = (208, 215, 222, 255)

STRIPS = {
    "termux": ["termux/docs/screenshots/desktop.png",
               "termux/docs/screenshots/anki-decks.png",
               "termux/docs/screenshots/anki-review.png",
               "termux/docs/screenshots/software.png"],
    "android": ["docs/images/android-decks.png",
                "docs/images/android-review-hanzi-answer.png",
                "docs/images/android-browse.png",
                "docs/images/android-stats.png"],
    "ios": ["docs/images/ios-decks.png",
            "docs/images/ios-review-hanzi-answer.png",
            "docs/images/ios-review-neetcode-question.png",
            "docs/images/ios-browse.png"],
}


def rounded(path):
    shot = Image.open(ROOT / path).convert("RGBA")
    shot = shot.resize((round(shot.width * HEIGHT / shot.height), HEIGHT), Image.LANCZOS)
    # draw the mask and outline 4x larger, then shrink, for smooth corners
    big = (shot.width * 4, shot.height * 4)
    mask = Image.new("L", big, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, big[0] - 1, big[1] - 1), RADIUS * 4, fill=255)
    shot.putalpha(mask.resize(shot.size, Image.LANCZOS))
    line = Image.new("RGBA", big, (0, 0, 0, 0))
    ImageDraw.Draw(line).rounded_rectangle((0, 0, big[0] - 1, big[1] - 1), RADIUS * 4,
                                           outline=OUTLINE, width=8)
    return Image.alpha_composite(shot, line.resize(shot.size, Image.LANCZOS))


if __name__ == "__main__":
    for name, paths in STRIPS.items():
        shots = [rounded(p) for p in paths]
        strip = Image.new("RGBA", (sum(s.width for s in shots) + GAP * (len(shots) - 1), HEIGHT))
        x = 0
        for shot in shots:
            strip.paste(shot, (x, 0))
            x += shot.width + GAP
        out = ROOT / f"docs/images/strip-{name}.png"
        strip.save(out, optimize=True)
        print(out, f"{strip.width}x{strip.height}")
