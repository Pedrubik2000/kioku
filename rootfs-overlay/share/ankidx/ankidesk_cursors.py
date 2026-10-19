"""Write the "kioku" Xcursor theme: large, crisp pointers for a phone screen.

No cursor theme is bundled, so X would fall back to its 16 px core cursors.
These are drawn from SVG with Qt (already in the runtime) and written in the
Xcursor file format, which Qt (libxcb-cursor) loads by name.

Usage: ankidesk_cursors.py <theme dir>   (run with QT_QPA_PLATFORM=offscreen)
"""

from __future__ import annotations

import os
import struct
import sys

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QGuiApplication, QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer

SIZES = (32, 48, 64, 96)
FILL, LINE, ACCENT = "#FFFFFF", "#141A2A", "#2E8BFF"

# 32x32 drawings with their hotspot. White with a dark outline reads on any
# background.
_ARROW = (f'<path d="M5 3 L5 24 L10.5 19 L14.2 27.5 L18 25.8 L14.4 17.6 L21.5 17.6 Z" fill="{FILL}" '
          f'stroke="{LINE}" stroke-width="1.6" stroke-linejoin="round"/>')
_RING = (f'<circle cx="23" cy="23" r="6.5" fill="none" stroke="{LINE}" stroke-width="4"/>'
         f'<path d="M23 16.5 A6.5 6.5 0 0 1 29.5 23" fill="none" stroke="{ACCENT}" stroke-width="2.6" '
         f'stroke-linecap="round"/>'
         f'<path d="M29.5 23 A6.5 6.5 0 1 1 23 16.5" fill="none" stroke="{FILL}" stroke-width="2.6" '
         f'stroke-linecap="round"/>')


def _double_arrow(angle: int) -> str:
    shape = (f'<path d="M3 16 L9 10 L9 14 L23 14 L23 10 L29 16 L23 22 L23 18 L9 18 L9 22 Z" fill="{FILL}" '
             f'stroke="{LINE}" stroke-width="1.5" stroke-linejoin="round"/>')
    return f'<g transform="rotate({angle} 16 16)">{shape}</g>'


CURSORS = {
    # name: (svg body, hot x, hot y), on the 32x32 grid
    "left_ptr": (_ARROW, 5, 3),
    "left_ptr_watch": (_ARROW + _RING, 5, 3),
    "watch": (f'<circle cx="16" cy="16" r="10" fill="none" stroke="{LINE}" stroke-width="6"/>'
              f'<circle cx="16" cy="16" r="10" fill="none" stroke="{FILL}" stroke-width="3.5"/>'
              f'<path d="M16 6 A10 10 0 0 1 26 16" fill="none" stroke="{ACCENT}" stroke-width="3.5" '
              f'stroke-linecap="round"/>', 16, 16),
    "xterm": (f'<path d="M11 5 Q16 5 16 8 Q16 5 21 5 M16 8 L16 24 M11 27 Q16 27 16 24 Q16 27 21 27 M12.5 16 L19.5 16" '
              f'fill="none" stroke="{LINE}" stroke-width="5" stroke-linecap="round"/>'
              f'<path d="M11 5 Q16 5 16 8 Q16 5 21 5 M16 8 L16 24 M11 27 Q16 27 16 24 Q16 27 21 27 M12.5 16 L19.5 16" '
              f'fill="none" stroke="{FILL}" stroke-width="2.2" stroke-linecap="round"/>', 16, 16),
    "hand2": (f'<path d="M12 4.5 a2.2 2.2 0 0 1 4.4 0 V14 l1-.2 a2 2 0 0 1 3.4 .6 l.4 .2 a2 2 0 0 1 3.2 1 '
              f'a2 2 0 0 1 3.2 1.4 V22 q0 6-6 7.5 h-4.6 q-3 0-4.8-2.6 L6 20.6 a2.1 2.1 0 0 1 3.2-2.7 L12 20 Z" '
              f'fill="{FILL}" stroke="{LINE}" stroke-width="1.5" stroke-linejoin="round"/>', 14, 3),
    "sb_h_double_arrow": (_double_arrow(0), 16, 16),
    "sb_v_double_arrow": (_double_arrow(90), 16, 16),
    "fd_double_arrow": (_double_arrow(45), 16, 16),
    "bd_double_arrow": (_double_arrow(-45), 16, 16),
    "fleur": (_double_arrow(0) + _double_arrow(90), 16, 16),
    "crosshair": (f'<path d="M16 3 V13 M16 19 V29 M3 16 H13 M19 16 H29" stroke="{LINE}" stroke-width="5" '
                  f'stroke-linecap="round"/><path d="M16 3 V13 M16 19 V29 M3 16 H13 M19 16 H29" stroke="{FILL}" '
                  f'stroke-width="2.2" stroke-linecap="round"/>', 16, 16),
    "circle": (f'<circle cx="16" cy="16" r="10" fill="none" stroke="{LINE}" stroke-width="6"/>'
               f'<circle cx="16" cy="16" r="10" fill="none" stroke="#FF5A5F" stroke-width="3.5"/>'
               f'<path d="M9 9 L23 23" stroke="#FF5A5F" stroke-width="3.5"/>', 16, 16),
}

# Names applications ask for (X core, CSS, Qt) mapped to the drawings above.
ALIASES = {
    "left_ptr": ["default", "arrow", "top_left_arrow", "X_cursor", "right_ptr", "whats_this", "help",
                 "question_arrow", "context-menu", "copy", "alias", "dnd-move", "dnd-copy", "dnd-link",
                 "dnd-none", "draft_large", "draft_small"],
    "left_ptr_watch": ["progress", "half-busy", "08e8e1c95fe2fc01f976f1e063a24ccd",
                       "3ecb610c1bf2410f44200f48c40d3599"],
    "watch": ["wait", "clock"],
    "xterm": ["text", "ibeam", "vertical-text"],
    "hand2": ["hand", "hand1", "pointer", "pointing_hand", "openhand", "closedhand", "grab", "grabbing",
              "e29285e634086352946a0e7090d73106", "9d800788f1b08800ae810202380a0822"],
    "sb_h_double_arrow": ["size_hor", "ew-resize", "e-resize", "w-resize", "h_double_arrow", "col-resize",
                          "split_h", "left_side", "right_side", "028006030e0e7ebffc7f7070c0600140",
                          "14fef782d02440884392942c11205230"],
    "sb_v_double_arrow": ["size_ver", "ns-resize", "n-resize", "s-resize", "v_double_arrow", "row-resize",
                          "split_v", "top_side", "bottom_side", "00008160000006810000408080010102",
                          "2870a09082c103050810ffdffffe0204"],
    "fd_double_arrow": ["size_fdiag", "nwse-resize", "nw-resize", "se-resize", "top_left_corner",
                        "bottom_right_corner", "c7088f0f3e6c8088236ef8e1e3e70000"],
    "bd_double_arrow": ["size_bdiag", "nesw-resize", "ne-resize", "sw-resize", "top_right_corner",
                        "bottom_left_corner", "fcf1c3c7cd4491d801f1e1c78f100000"],
    "fleur": ["size_all", "move", "all-scroll"],
    "crosshair": ["cross", "tcross", "cell", "plus"],
    "circle": ["forbidden", "not-allowed", "no-drop", "crossed_circle", "03b6e0fcb3499374a867c041f52298f0"],
}


def _image(body: str, size: int) -> bytes:
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">{body}</svg>'
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode())).render(p, QRectF(0, 0, size, size))
    p.end()
    # Xcursor wants premultiplied ARGB as little-endian 32-bit words, which is
    # exactly QImage's ARGB32_Premultiplied layout on a little-endian CPU.
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    stride = img.bytesPerLine()
    return b"".join(bytes(ptr[y * stride:y * stride + size * 4]) for y in range(size))


def xcursor(body: str, hx: int, hy: int) -> bytes:
    images = []
    for size in SIZES:
        scale = size / 32
        header = struct.pack("<9I", 36, 0xFFFD0002, size, 1, size, size,
                             min(round(hx * scale), size - 1), min(round(hy * scale), size - 1), 0)
        images.append(header + _image(body, size))
    toc_size = 12 * len(images)
    out = struct.pack("<4sIII", b"Xcur", 16, 0x10000, len(images))
    pos = 16 + toc_size
    for size, chunk in zip(SIZES, images):
        out += struct.pack("<III", 0xFFFD0002, size, pos)
        pos += len(chunk)
    return out + b"".join(images)


def main(theme_dir: str) -> None:
    QGuiApplication(sys.argv)
    cursors = os.path.join(theme_dir, "cursors")
    os.makedirs(cursors, exist_ok=True)
    for name, (body, hx, hy) in CURSORS.items():
        with open(os.path.join(cursors, name), "wb") as fh:
            fh.write(xcursor(body, hx, hy))
        for alias in ALIASES.get(name, []):
            link = os.path.join(cursors, alias)
            if os.path.lexists(link):
                os.remove(link)
            os.symlink(name, link)
    # Written last: session.sh treats its presence as "theme complete".
    with open(os.path.join(theme_dir, "index.theme"), "w", encoding="utf-8") as fh:
        fh.write("[Icon Theme]\nName=Kioku\nComment=Large cursors for phones\n")


if __name__ == "__main__":
    main(sys.argv[1])
