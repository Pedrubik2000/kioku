"""Look of the Kioku desktop: colours, line icons, app icons and wallpapers.

Modelled on Cutefish and Deepin: a mountain wallpaper, frosted dark cards,
one blue accent, rounded "squircle" app icons with a gradient and a white
glyph. Everything is SVG drawn by Qt's svg plugin, which the runtime already
has; no icon theme is bundled.
"""

from __future__ import annotations

import os
import re
import sys

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
HOME = os.environ.get("HOME", os.path.join(os.path.dirname(PREFIX), "home"))
THEME_DIR = os.path.join(PREFIX, "share/ankidx/theme")
WALLPAPER_DIR = os.path.join(THEME_DIR, "wallpapers")
DEFAULT_WALLPAPER = os.path.join(WALLPAPER_DIR, "alpine.svg")
CONFIG_DIR = os.path.join(HOME, ".config/kioku")
WALLPAPER_SETTING = os.path.join(CONFIG_DIR, "wallpaper")
CUSTOM_WALLPAPER = os.path.join(CONFIG_DIR, "custom-wallpaper.png")
JWMRC_TEMPLATE = os.path.join(PREFIX, "share/ankidx/jwmrc")
LOGO = os.path.join(THEME_DIR, "kioku.svg")

DISTRO = "Kioku"
VERSION = "1.0"

ACCENT = "#2E8BFF"
ACCENT_PRESSED = "#1A6FE0"
TEXT = "#F4F6FB"
TEXT_DIM = "#A8B3C7"
# Frosted glass, only on the home page over the wallpaper.
CARD = "rgba(16, 22, 38, 0.78)"
CARD_PRESSED = "rgba(255, 255, 255, 0.18)"
BORDER = "rgba(255, 255, 255, 0.10)"
# Solid surfaces for Software and Settings, where text must stay readable.
BACKGROUND = "#0E1322"
SURFACE = "#182034"
SURFACE_RAISED = "#222B42"
SURFACE_PRESSED = "#2C3756"
SURFACE_BORDER = "#252E46"
DANGER = "#FF5A5F"
SUCCESS = "#34C77B"

# Line icons on a 24x24 grid, stroked with the current colour
# (Feather-style: 2px stroke, round joins).
GLYPHS = {
    "apps": '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/>'
            '<rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
    "store": '<path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/>'
             '<path d="M16 10a4 4 0 0 1-8 0"/>',
    "settings": '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/>'
                '<line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/>'
                '<line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>'
                '<line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/>'
                '<line x1="17" y1="16" x2="23" y2="16"/>',
    "terminal": '<polyline points="5 16 10 11 5 6"/><line x1="12" y1="18" x2="19" y2="18"/>',
    "folder": '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>'
             '<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "image": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/>'
             '<polyline points="21 15 16 10 5 21"/>',
    "archive": '<polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5" rx="1"/>'
               '<line x1="10" y1="12" x2="14" y2="12"/>',
    "activity": '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    "plus": '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    "search": '<circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.2" y2="16.2"/>',
    "chevron": '<polyline points="9 18 15 12 9 6"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/>'
                '<line x1="12" y1="15" x2="12" y2="3"/>',
    "trash": '<polyline points="3 6 5 6 21 6"/>'
             '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "keyboard": '<rect x="2" y="5" width="20" height="14" rx="2"/><line x1="6" y1="9" x2="6" y2="9"/>'
                '<line x1="10" y1="9" x2="10" y2="9"/><line x1="14" y1="9" x2="14" y2="9"/>'
                '<line x1="18" y1="9" x2="18" y2="9"/><line x1="6" y1="12.5" x2="6" y2="12.5"/>'
                '<line x1="18" y1="12.5" x2="18" y2="12.5"/><line x1="8" y1="16" x2="16" y2="16"/>',
    "pointer": '<path d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51z"/><path d="M13 13l6 6"/>',
    "touchpad": '<rect x="3" y="3" width="18" height="18" rx="3"/><line x1="3" y1="15" x2="21" y2="15"/>'
                '<line x1="12" y1="15" x2="12" y2="21"/>',
    "monitor": '<rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/>'
               '<line x1="12" y1="17" x2="12" y2="21"/>',
    "drive": '<line x1="22" y1="12" x2="2" y2="12"/>'
             '<path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24'
             'a2 2 0 0 0-1.79 1.11z"/><line x1="6" y1="16" x2="6.01" y2="16"/><line x1="10" y1="16" x2="10.01" y2="16"/>',
    "phone": '<rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18"/>',
    "refresh": '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>'
               '<path d="M3.5 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.5 15"/>',
    "power": '<path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/>',
    "check": '<polyline points="20 6 9 17 4 12"/>',
    "close": '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "package": '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4'
               'a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.3 7 12 12 20.7 7"/>'
               '<line x1="12" y1="22" x2="12" y2="12"/>',
    "anki": '<rect x="5.5" y="3" width="13" height="18" rx="2.5" transform="rotate(-12 12 12)" stroke-opacity=".55"/>'
            '<polygon points="12 6.5 13.8 10.2 17.8 10.7 14.9 13.5 15.6 17.5 12 15.6 8.4 17.5 9.1 13.5 6.2 10.7 10.2 10.2"'
            ' fill="#fff" stroke-width="1.2"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/>'
              '<line x1="12" y1="3" x2="12" y2="15"/>',
    "smartphone": '<rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18"/>',
    "lock": '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>'
            '<path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
}

# Gradient (top-left, bottom-right) per app icon.
GRADIENTS = {
    "anki": ("#6FC3FF", "#2457E6"),
    "terminal": ("#3A4256", "#151922"),
    "folder": ("#4FB3FF", "#1C6FE8"),
    "edit": ("#FFB547", "#F2732B"),
    "globe": ("#38D1C6", "#1679D8"),
    "image": ("#FF7EB3", "#C2389B"),
    "archive": ("#C69C6D", "#8A5A2E"),
    "activity": ("#5BE38D", "#13985A"),
    "store": ("#6E8BFF", "#5B3DE0"),
    "settings": ("#9AA6BA", "#566179"),
    "plus": ("#6E8BFF", "#5B3DE0"),
    "package": ("#8C7BFF", "#5236C8"),
}
_FALLBACK_GRADIENTS = [("#FF8A65", "#E5484D"), ("#7C83FD", "#3E4BD8"), ("#4DD0E1", "#0D8ABC"),
                       ("#AED581", "#4C9A2A"), ("#F48FB1", "#B83280"), ("#FFD54F", "#F59E0B")]


def glyph_svg(name: str, color: str = TEXT, stroke: float = 2.0) -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">'
            f'{GLYPHS[name]}</svg>')


def render_svg(svg: str, size: int) -> QPixmap:
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode())).render(p, QRectF(0, 0, size, size))
    p.end()
    return QPixmap.fromImage(img)


def line_icon(name: str, size: int, color: str = TEXT) -> QIcon:
    return QIcon(render_svg(glyph_svg(name, color), size))


def _tile_svg(inner: str, top: str, bottom: str) -> str:
    """A squircle with a diagonal gradient, a soft top sheen and `inner` on top."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96">
<defs>
 <linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{top}"/>
  <stop offset="1" stop-color="{bottom}"/></linearGradient>
 <linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".28"/>
  <stop offset=".5" stop-color="#fff" stop-opacity="0"/></linearGradient>
 <linearGradient id="sh" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity=".35"/>
  <stop offset="1" stop-color="#000" stop-opacity="0"/></linearGradient>
</defs>
<rect x="6" y="9" width="84" height="84" rx="24" fill="url(#sh)"/>
<rect x="6" y="4" width="84" height="84" rx="24" fill="url(#g)"/>
<rect x="6" y="4" width="84" height="84" rx="24" fill="url(#s)"/>
<rect x="6.5" y="4.5" width="83" height="83" rx="23.5" fill="none" stroke="#fff" stroke-opacity=".18"/>
{inner}
</svg>"""


def app_tile(glyph: str, size: int, gradient: tuple[str, str] | None = None) -> QPixmap:
    top, bottom = gradient or GRADIENTS.get(glyph, GRADIENTS["package"])
    inner = (f'<g transform="translate(24 22) scale(2)" fill="none" stroke="#fff" stroke-width="2" '
             f'stroke-linecap="round" stroke-linejoin="round">{GLYPHS[glyph]}</g>')
    return render_svg(_tile_svg(inner, top, bottom), size)


def letter_tile(text: str, size: int) -> QPixmap:
    top, bottom = _FALLBACK_GRADIENTS[sum(map(ord, text)) % len(_FALLBACK_GRADIENTS)]
    letter = (text[:1] or "?").upper().replace("&", "&amp;").replace("<", "&lt;")
    inner = (f'<text x="48" y="61" text-anchor="middle" font-family="DejaVu Sans" font-weight="bold" '
             f'font-size="40" fill="#fff">{letter}</text>')
    return render_svg(_tile_svg(inner, top, bottom), size)


def image_tile(path: str, size: int) -> QPixmap | None:
    """An app's own icon file, centred on a frosted squircle so all tiles line up."""
    inner = int(size * 0.62)
    if path.endswith(".svg"):
        pm = render_svg(open(path, encoding="utf-8").read(), inner)
    else:
        pm = QPixmap(path)
        if pm.isNull():
            return None
        pm = pm.scaled(inner, inner, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    base = render_svg(_tile_svg("", "#FFFFFF", "#DCE3EE"), size)
    p = QPainter(base)
    p.drawPixmap((size - pm.width()) // 2, (size - pm.height()) // 2 - int(size * 0.02), pm)
    p.end()
    return base


def builtin_wallpapers() -> list[tuple[str, str]]:
    """(name, path) of the bundled wallpapers, the default first."""
    names = sorted(f[:-4] for f in os.listdir(WALLPAPER_DIR) if f.endswith(".svg"))
    names.sort(key=lambda n: n + ".svg" != os.path.basename(DEFAULT_WALLPAPER))
    return [(n.capitalize(), os.path.join(WALLPAPER_DIR, n + ".svg")) for n in names]


def current_wallpaper() -> str:
    try:
        with open(WALLPAPER_SETTING, encoding="utf-8") as fh:
            path = fh.read().strip()
        if os.path.isfile(path):
            return path
    except OSError:
        pass
    return DEFAULT_WALLPAPER


def _render_cover(p: QPainter, path: str, width: int, height: int) -> bool:
    """Draw `path` scaled to fill width x height, cropping the overflow."""
    if path.endswith(".svg"):
        renderer = QSvgRenderer(path)
        if not renderer.isValid():
            return False
        vb = renderer.viewBoxF()
        scale = max(width / vb.width(), height / vb.height())
        w, h = vb.width() * scale, vb.height() * scale
        renderer.render(p, QRectF((width - w) / 2, (height - h) / 2, w, h))
        return True
    img = QImage(path)
    if img.isNull():
        return False
    img = img.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                     Qt.TransformationMode.SmoothTransformation)
    p.drawImage((width - img.width()) // 2, (height - img.height()) // 2, img)
    return True


def wallpaper(width: int, height: int, dim: float = 0.0, path: str | None = None) -> QPixmap:
    pm = QPixmap(width, height)
    pm.fill(QColor("#0B1020"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    if not _render_cover(p, path or current_wallpaper(), width, height):
        _render_cover(p, DEFAULT_WALLPAPER, width, height)
    if dim:
        p.fillRect(pm.rect(), QColor(5, 8, 18, int(255 * dim)))
    p.end()
    return pm


def is_landscape() -> bool:
    try:
        import ankidesk_x11

        width, height = ankidesk_x11.screen_size()
        return width > height
    except OSError:
        return False


def jwmrc_landscape() -> bool:
    """Whether ~/.jwmrc has the landscape (side) dock."""
    try:
        with open(os.path.join(HOME, ".jwmrc"), encoding="utf-8") as fh:
            return 'layout="vertical"' in fh.read()
    except OSError:
        return False


def _side_dock(rc: str) -> str:
    """The template's bottom dock turned into one on the right edge: in
    landscape the height is the scarce axis. Window buttons show icons only."""
    tray = re.search(r"<Tray .*?</Tray>", rc, re.S).group(0)
    side = (tray.replace('x="0" y="-1" height="132"', 'x="-1" y="0" width="132" layout="vertical"')
            .replace('<Spacer width=', '<Spacer height=')
            .replace('<TaskList maxwidth="380" height="104"/>', '<TaskList height="112" labeled="false"/>'))
    return rc.replace(tray, side)


def write_jwmrc(landscape: bool | None = None) -> None:
    """~/.jwmrc from the template, with the chosen wallpaper as background and
    the dock at the bottom (portrait) or on the right (landscape)."""
    with open(JWMRC_TEMPLATE, encoding="utf-8") as fh:
        rc = fh.read()
    rc = re.sub(r"(<Background type=\"scale\">)[^<]*(</Background>)",
                lambda m: m.group(1) + current_wallpaper() + m.group(2), rc)
    if landscape is None:
        landscape = is_landscape()
    if landscape:
        rc = _side_dock(rc)
    tmp = os.path.join(HOME, ".jwmrc.new")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(rc)
    os.replace(tmp, os.path.join(HOME, ".jwmrc"))


def set_wallpaper(path: str) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(WALLPAPER_SETTING, "w", encoding="utf-8") as fh:
        fh.write(path)
    # JWM's own background is hidden behind the desktop shell; it takes the new
    # picture at its next restart. Restarting it now would disturb open windows.
    write_jwmrc(jwmrc_landscape())


def import_wallpaper(src: str, width: int, height: int) -> str:
    """Crop a picture to the screen and keep a copy, so the original may go."""
    img = QImage(src)
    if img.isNull():
        raise ValueError("This file is not a picture Qt can read.")
    img = img.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                     Qt.TransformationMode.SmoothTransformation)
    img = img.copy((img.width() - width) // 2, (img.height() - height) // 2, width, height)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not img.save(CUSTOM_WALLPAPER, "PNG"):
        raise OSError("Could not save the wallpaper.")
    return CUSTOM_WALLPAPER


# Settings for the optional apps (Qt and GTK), which unlike Anki and the desktop
# know nothing about the phone. Qt reads ~/.config/kdeglobals when it believes
# it runs in KDE (app_environment()): a dark palette matching the desktop and
# items opened with one tap instead of a double click.
KDEGLOBALS = os.path.join(HOME, ".config/kdeglobals")
_KDEGLOBALS = """# Written by Kioku (ankidesk_theme.py); delete this line to keep your own changes.
[KDE]
SingleClick=true
widgetStyle=Fusion

[General]
ColorScheme=Kioku
font=DejaVu Sans,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1
fixed=DejaVu Sans Mono,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1
menuFont=DejaVu Sans,11,-1,5,400,0,0,0,0,0,0,0,0,0,0,1
toolBarFont=DejaVu Sans,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1

[Toolbar style]
ToolButtonStyle=TextBesideIcon

[MainToolbarIcons]
Size=24

[ToolbarIcons]
Size=24

[Icons]
Theme=AdwaitaLegacy

[Colors:Window]
BackgroundNormal=24,32,52
BackgroundAlternate=30,39,62
ForegroundNormal=244,246,251
ForegroundInactive=168,179,199
ForegroundLink=46,139,255

[Colors:View]
BackgroundNormal=14,19,34
BackgroundAlternate=20,26,44
ForegroundNormal=244,246,251
ForegroundInactive=168,179,199
ForegroundLink=46,139,255

[Colors:Button]
BackgroundNormal=34,43,66
BackgroundAlternate=44,55,86
ForegroundNormal=244,246,251
ForegroundInactive=168,179,199

[Colors:Selection]
BackgroundNormal=46,139,255
BackgroundAlternate=26,111,224
ForegroundNormal=255,255,255
ForegroundInactive=230,236,245

[Colors:Tooltip]
BackgroundNormal=26,33,51
ForegroundNormal=244,246,251

[Colors:Header]
BackgroundNormal=24,32,52
ForegroundNormal=244,246,251

[Colors:Complementary]
BackgroundNormal=14,19,34
ForegroundNormal=244,246,251
"""


# PCManFM-Qt has its own click setting; written only if the user has none.
PCMANFM_SETTINGS = os.path.join(HOME, ".config/pcmanfm-qt/default/settings.conf")
# Installed with the file-based apps (ankidesk_pkg.ICON_THEME_PACKAGE).
ICON_THEME = "AdwaitaLegacy"
_PCMANFM_SETTINGS = f"""[System]
FallbackIconThemeName={ICON_THEME}

[Behavior]
SingleClick=true

[FolderView]
Mode=icon
BigIconSize=48
SmallIconSize=24
SidePaneIconSize=24
ThumbnailIconSize=128
"""


def write_app_settings() -> None:
    try:
        with open(PCMANFM_SETTINGS, encoding="utf-8") as fh:
            ours = "FallbackIconThemeName" not in fh.read()  # an older one of ours
    except FileNotFoundError:
        ours = True
    if ours:
        os.makedirs(os.path.dirname(PCMANFM_SETTINGS), exist_ok=True)
        with open(PCMANFM_SETTINGS, "w", encoding="utf-8") as fh:
            fh.write(_PCMANFM_SETTINGS)
    try:
        with open(KDEGLOBALS, encoding="utf-8") as fh:
            if not fh.readline().startswith("# Written by Kioku"):
                return  # the user's own
    except FileNotFoundError:
        pass
    os.makedirs(os.path.dirname(KDEGLOBALS), exist_ok=True)
    with open(KDEGLOBALS, "w", encoding="utf-8") as fh:
        fh.write(_KDEGLOBALS)


def app_environment() -> dict[str, str]:
    """Environment for apps started from the desktop (not Anki, which scales
    itself): sized like Anki, with the settings above."""
    env = dict(os.environ)
    scale = float(env.get("ANKIDX_SCALE", "2"))
    env.update({
        "QT_SCALE_FACTOR": f"{scale:g}",
        "QT_ENABLE_HIGHDPI_SCALING": "1",
        "XDG_CURRENT_DESKTOP": "KDE",
        "KDE_FULL_SESSION": "true",
        "KDE_SESSION_VERSION": "6",
        "GDK_SCALE": str(max(1, round(scale))),
        # Touch events (the display's direct touch mode for these apps) reach
        # Firefox only with XInput 2; Qt and GTK use it already.
        "MOZ_USE_XINPUT2": "1",
    })
    for key in ("QT_QPA_PLATFORMTHEME", "QT_STYLE_OVERRIDE"):
        env.pop(key, None)
    return env


if __name__ == "__main__" and sys.argv[1:] == ["jwmrc"]:
    # Session start: the X screen does not have the display's size yet, so
    # start with the portrait dock; the desktop switches it if needed.
    write_jwmrc(landscape=False)
    write_app_settings()
