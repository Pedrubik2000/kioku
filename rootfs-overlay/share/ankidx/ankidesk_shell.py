"""The Kioku desktop: home screen, app launcher, software center and settings.

Looks like Cutefish/Deepin (see ankidesk_theme.py) and is built on the PyQt6
that Anki already needs, so it adds no size. It is the session's main process
(session.sh): it stays below every window, the dock's desktop button minimizes
the windows to show it, and the session ends when it exits ("Power off").
Anki is one of its apps; closing Anki returns here.

Pages:
  Apps      clock, search, Anki, Terminal and every installed desktop app
  Software  optional native apps: install / open / remove, with progress
  Settings  wallpaper, touch mode, keyboard, display, storage, power
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import (  # noqa: E402
    QFileSystemWatcher, QObject, QRectF, QSize, QSocketNotifier, Qt, QThread, QTimer, pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap  # noqa: E402
from PyQt6.QtNetwork import QLocalServer  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QAbstractButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import ankidesk_keyboard as keyboard  # noqa: E402
import ankidesk_menu as menu  # noqa: E402
import ankidesk_pkg as pkg  # noqa: E402
import ankidesk_theme as theme  # noqa: E402
import ankidesk_x11 as x11  # noqa: E402

# Optional apps. All use Qt or plain terminals, so they share the libraries the
# runtime already has and stay small.
CATALOG = [
    {"package": "pcmanfm-qt", "name": "Files", "desktop": "pcmanfm-qt", "glyph": "folder",
     "summary": "Browse and manage your files", "size": "8 MB"},
    {"package": "featherpad", "name": "Text Editor", "desktop": "featherpad", "glyph": "edit",
     "summary": "Lightweight text editor", "size": "4 MB"},
    {"package": "qterminal", "name": "QTerminal", "desktop": "qterminal", "glyph": "terminal",
     "summary": "Terminal with tabs", "size": "3 MB"},
    {"package": "falkon", "name": "Web Browser", "desktop": "org.kde.falkon", "glyph": "globe",
     "summary": "Falkon, on the same web engine as Anki", "size": "49 MB"},
    {"package": "lximage-qt", "name": "Image Viewer", "desktop": "lximage-qt", "glyph": "image",
     "summary": "View and convert images", "size": "6 MB"},
    {"package": "lxqt-archiver", "name": "Archives", "desktop": "lxqt-archiver", "glyph": "archive",
     "summary": "Open and create zip, tar and 7z files", "size": "7 MB"},
    {"package": "htop", "name": "System Monitor", "desktop": "htop", "glyph": "activity",
     "summary": "Processes and memory (htop)", "size": "1 MB", "exec": "htop", "terminal": True},
]
GLYPH_FOR_DESKTOP = {e["desktop"]: e["glyph"] for e in CATALOG}
TERMINAL = "st -f 'DejaVu Sans Mono:pixelsize=34'"
LAUNCH_ANKI = shlex.quote(sys.executable) + " " + shlex.quote(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "launch_anki.py"))
PICKED_WALLPAPER = os.path.join(theme.CONFIG_DIR, "picked-wallpaper")

SCALE = 3.0  # physical pixels per dp; set from the screen in main()


def dp(n: float) -> int:
    return round(n * SCALE)


def stylesheet() -> str:
    return f"""
* {{ font-family: "DejaVu Sans"; }}
QWidget {{ background: transparent; color: {theme.TEXT}; font-size: {dp(15)}px; }}
QLabel#clock {{ font-size: {dp(64)}px; font-weight: 200; }}
QLabel#date {{ font-size: {dp(16)}px; color: {theme.TEXT_DIM}; }}
QLabel#title {{ font-size: {dp(30)}px; font-weight: bold; }}
QLabel#subtitle {{ font-size: {dp(14)}px; color: {theme.TEXT_DIM}; }}
QLabel#section {{ font-size: {dp(13)}px; font-weight: bold; color: {theme.TEXT_DIM}; padding-left: {dp(6)}px; }}
QLabel#name {{ font-size: {dp(17)}px; font-weight: bold; }}
QLabel#dim {{ font-size: {dp(13)}px; color: {theme.TEXT_DIM}; }}
QLabel#empty {{ font-size: {dp(15)}px; color: {theme.TEXT_DIM}; }}
QFrame#searchbox {{ background: {theme.CARD}; border: 1px solid {theme.BORDER}; border-radius: {dp(16)}px; }}
QLineEdit#search {{
    border: none; padding: {dp(10)}px 0; font-size: {dp(16)}px; selection-background-color: {theme.ACCENT};
}}
QFrame#card {{ background: {theme.CARD}; border: 1px solid {theme.BORDER}; border-radius: {dp(20)}px; }}
QFrame#sheet {{ background: #1A2133; border: 1px solid {theme.BORDER}; border-radius: {dp(26)}px; }}
QFrame#nav {{ background: rgba(14, 19, 34, 0.86); border: 1px solid {theme.BORDER}; border-radius: {dp(30)}px; }}
QFrame#line {{ background: {theme.BORDER}; max-height: 1px; min-height: 1px; border: none; }}
QToolButton#tile {{
    border: none; border-radius: {dp(18)}px; padding: {dp(6)}px {dp(2)}px;
    font-size: {dp(13)}px; color: {theme.TEXT};
}}
QToolButton#tile:pressed {{ background: {theme.CARD_PRESSED}; }}
QToolButton#navbtn {{
    border: none; border-radius: {dp(24)}px; padding: {dp(6)}px {dp(4)}px;
    font-size: {dp(12)}px; color: {theme.TEXT_DIM};
}}
QToolButton#navbtn:checked {{ background: rgba(46, 139, 255, 0.22); color: white; font-weight: bold; }}
QPushButton {{
    background: {theme.CARD_PRESSED}; border: none; border-radius: {dp(18)}px;
    padding: {dp(8)}px {dp(14)}px; font-size: {dp(15)}px; font-weight: bold; min-height: {dp(20)}px;
}}
QPushButton:pressed {{ background: rgba(255, 255, 255, 0.28); }}
QPushButton#primary {{ background: {theme.ACCENT}; color: white; }}
QPushButton#primary:pressed {{ background: {theme.ACCENT_PRESSED}; }}
QPushButton#danger {{ background: {theme.DANGER}; color: white; }}
QPushButton#row {{
    background: transparent; border-radius: {dp(16)}px; padding: 0; min-height: {dp(58)}px; text-align: left;
}}
QPushButton#row:pressed {{ background: {theme.CARD_PRESSED}; }}
QToolButton#thumb {{
    border: {dp(2)}px solid transparent; border-radius: {dp(16)}px; padding: {dp(3)}px;
    font-size: {dp(12)}px; color: {theme.TEXT_DIM};
}}
QToolButton#thumb:checked {{ border: {dp(2)}px solid {theme.ACCENT}; color: white; font-weight: bold; }}
QLabel#brand {{ font-size: {dp(22)}px; font-weight: bold; }}
QPushButton#round {{ border-radius: {dp(18)}px; padding: {dp(8)}px; min-width: {dp(24)}px; }}
QProgressBar {{
    background: rgba(255, 255, 255, 0.10); border: none; border-radius: {dp(4)}px;
    max-height: {dp(8)}px; min-height: {dp(8)}px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {theme.ACCENT}; border-radius: {dp(4)}px; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: {dp(4)}px; margin: 0; }}
QScrollBar::handle:vertical {{ background: rgba(255, 255, 255, 0.25); border-radius: {dp(2)}px; min-height: {dp(30)}px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    background: none; height: 0;
}}
"""


def launch(command: str, terminal: bool = False) -> None:
    if terminal:
        command = f"{TERMINAL} -e {command}"
    subprocess.Popen(["sh", "-c", command], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def label(text: str, name: str = "", wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    lbl.setWordWrap(wrap)
    return lbl


def pixmap_label(pm: QPixmap) -> QLabel:
    lbl = QLabel()
    lbl.setPixmap(pm)
    lbl.setFixedSize(pm.size())
    return lbl


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(dp(8), dp(8), dp(8), dp(8))
    layout.setSpacing(0)
    return frame, layout


def hline() -> QFrame:
    line = QFrame()
    line.setObjectName("line")
    return line


class Worker(QObject):
    progress = pyqtSignal(str, float)
    finished = pyqtSignal(str)  # error message, empty on success

    def __init__(self, action: str, package: str) -> None:
        super().__init__()
        self.action, self.package = action, package

    def run(self) -> None:
        try:
            if self.action == "size":
                dl, size = pkg.download_size([self.package], pkg.index())
                self.finished.emit(f"={dl}:{size}")
                return
            fn = pkg.install if self.action == "install" else pkg.remove
            fn([self.package], lambda text, f: self.progress.emit(text, f))
            self.finished.emit("")
        except Exception as e:  # noqa: BLE001 - shown to the user
            traceback.print_exc()
            self.finished.emit(str(e) or type(e).__name__)


class DragScroll(QObject):
    """One-finger scrolling with momentum for the shell's pages.

    The display sends a finger drag as a held left button, so dragging inside
    a page scrolls it, like a phone. Once a drag starts, the button under the
    finger is released without clicking.
    """

    areas: list[QScrollArea] = []

    def __init__(self) -> None:
        super().__init__()
        self.area: QScrollArea | None = None
        self.dragging = False
        self.y0 = self.v0 = 0
        self.samples: list[tuple[float, float]] = []
        self.velocity = 0.0  # px per ms, positive scrolls down
        self.coasting: QScrollArea | None = None
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._coast)

    def _area_of(self, w: QObject | None) -> QScrollArea | None:
        while w is not None:
            if w in self.areas:
                return w
            w = w.parent()
        return None

    def eventFilter(self, obj: QObject, event) -> bool:  # noqa: N802 - Qt API
        t = event.type()
        if t == event.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self.timer.stop()
            self.area = self._area_of(obj)
            if self.area is not None:
                self.dragging = False
                self.y0 = event.globalPosition().y()
                self.v0 = self.area.verticalScrollBar().value()
                self.samples = [(time.monotonic() * 1000, self.y0)]
        elif t == event.Type.MouseMove and self.area is not None and event.buttons() & Qt.MouseButton.LeftButton:
            y = event.globalPosition().y()
            if not self.dragging and abs(y - self.y0) > dp(8):
                self.dragging = True
                if isinstance(obj, QAbstractButton):
                    obj.setDown(False)
            if self.dragging:
                self.area.verticalScrollBar().setValue(round(self.v0 - (y - self.y0)))
                self.samples = (self.samples + [(time.monotonic() * 1000, y)])[-5:]
                return True
        elif t == event.Type.MouseButtonRelease and self.area is not None:
            dragging, area = self.dragging, self.area
            self.dragging, self.area = False, None
            if dragging:
                (t0, y0), (t1, y1) = self.samples[0], self.samples[-1]
                if t1 - t0 > 0 and time.monotonic() * 1000 - t1 < 80:
                    self.velocity = -(y1 - y0) / (t1 - t0)
                    self.coasting = area
                    self.timer.start()
                return True
        return False

    def _coast(self) -> None:
        bar = self.coasting.verticalScrollBar()
        bar.setValue(round(bar.value() + self.velocity * 16))
        self.velocity *= 0.94
        if abs(self.velocity) < 0.05 or bar.value() in (bar.minimum(), bar.maximum()):
            self.timer.stop()


class Sheet(QWidget):
    """A bottom sheet over the dimmed shell, instead of separate dialog windows."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.on_ok = None
        self.panel = QFrame()
        self.panel.setObjectName("sheet")
        box = QVBoxLayout(self.panel)
        box.setContentsMargins(dp(22), dp(22), dp(22), dp(18))
        box.setSpacing(dp(10))
        head = QHBoxLayout()
        head.setSpacing(dp(14))
        self.icon = QLabel()
        head.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(dp(4))
        self.title = label("", "name", wrap=True)
        self.text = label("", "dim", wrap=True)
        texts.addWidget(self.title)
        texts.addWidget(self.text)
        head.addLayout(texts, 1)
        box.addLayout(head)
        box.addSpacing(dp(8))
        buttons = QHBoxLayout()
        buttons.setSpacing(dp(10))
        self.cancel = QPushButton("Cancel")
        self.cancel.clicked.connect(self.close_sheet)
        self.ok = QPushButton("OK")
        self.ok.clicked.connect(self._accept)
        buttons.addWidget(self.cancel, 1)
        buttons.addWidget(self.ok, 1)
        box.addLayout(buttons)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(dp(12), dp(12), dp(12), dp(96))
        outer.addStretch(1)
        outer.addWidget(self.panel)
        self.hide()

    def ask(self, icon: QPixmap, title: str, text: str, ok: str, on_ok=None, kind: str = "primary") -> None:
        self.icon.setPixmap(icon)
        self.title.setText(title)
        self.text.setText(text)
        self.ok.setText(ok)
        self.ok.setObjectName(kind)
        self.ok.style().unpolish(self.ok)
        self.ok.style().polish(self.ok)
        self.cancel.setVisible(on_ok is not None)
        self.on_ok = on_ok
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()

    def close_sheet(self) -> None:
        self.on_ok = None
        self.hide()

    def _accept(self) -> None:
        cb = self.on_ok
        self.close_sheet()
        if cb:
            cb()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        QPainter(self).fillRect(self.rect(), QColor(0, 0, 0, 150))

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if not self.panel.geometry().contains(event.position().toPoint()):
            self.close_sheet()


class Shell(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Apps")
        # No title bar: the shell is the phone's home screen, above the dock.
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(stylesheet())
        self.thread: QThread | None = None
        self.worker: Worker | None = None
        self.busy: str | None = None  # package being installed or removed
        self._wallpaper: QPixmap | None = None
        self.tiles: list[tuple[str, QToolButton]] = []

        self.pages = QStackedWidget()
        self.home = QWidget()
        self.software = QWidget()
        self.settings = QWidget()
        self._build_settings()
        for page in (self.home, self.software, self.settings):
            self.pages.addWidget(self._scroll(page))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, dp(10))
        layout.setSpacing(dp(8))
        layout.addWidget(self.pages, 1)
        layout.addWidget(self._build_nav(), 0, Qt.AlignmentFlag.AlignHCenter)

        self.sheet = Sheet(self)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._tick)
        self.clock_timer.start(10_000)
        self.reload()
        self.show_page(0)

    # --- frame ----------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._wallpaper is None or self._wallpaper.size() != self.size():
            self._wallpaper = theme.wallpaper(self.width(), self.height(), dim=0.25)
        QPainter(self).drawPixmap(0, 0, self._wallpaper)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self.sheet.isVisible():
            self.sheet.setGeometry(self.rect())
        super().resizeEvent(event)

    @staticmethod
    def _scroll(w: QWidget) -> QScrollArea:
        s = QScrollArea()
        s.setWidgetResizable(True)
        s.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        s.setWidget(w)
        s.viewport().setAutoFillBackground(False)
        w.setAutoFillBackground(False)
        DragScroll.areas.append(s)
        return s

    @staticmethod
    def _clear(w: QWidget) -> QVBoxLayout:
        old = w.layout()
        if old is not None:
            QWidget().setLayout(old)  # reparent to drop the old layout and its widgets
        layout = QVBoxLayout(w)
        layout.setContentsMargins(dp(18), dp(28), dp(18), dp(12))
        layout.setSpacing(dp(10))
        return layout

    def _header(self, layout: QVBoxLayout, title: str, subtitle: str) -> None:
        layout.addWidget(label(title, "title"))
        layout.addWidget(label(subtitle, "subtitle", wrap=True))
        layout.addSpacing(dp(10))

    def _build_nav(self) -> QFrame:
        nav = QFrame()
        nav.setObjectName("nav")
        row = QHBoxLayout(nav)
        row.setContentsMargins(dp(6), dp(6), dp(6), dp(6))
        row.setSpacing(dp(4))
        self.nav_buttons = []
        for i, (text, glyph) in enumerate((("Apps", "apps"), ("Software", "store"), ("Settings", "settings"))):
            b = QToolButton()
            b.setObjectName("navbtn")
            b.setText(text)
            b.setIcon(theme.line_icon(glyph, dp(24)))
            b.setIconSize(QSize(dp(24), dp(24)))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setCheckable(True)
            b.setFixedSize(dp(96), dp(58))
            b.clicked.connect(lambda _=False, i=i: self.show_page(i))
            row.addWidget(b)
            self.nav_buttons.append(b)
        return nav

    def show_page(self, i: int) -> None:
        self.pages.setCurrentIndex(i)
        for j, b in enumerate(self.nav_buttons):
            b.setChecked(i == j)

    def reload(self) -> None:
        self._build_home()
        self._build_software()

    # --- apps -----------------------------------------------------------------

    def _tile(self, pm: QPixmap, text: str, action) -> QToolButton:
        b = QToolButton()
        b.setObjectName("tile")
        b.setIcon(QIcon(pm))
        b.setIconSize(QSize(dp(60), dp(60)))
        b.setText(b.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, dp(76)))
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        b.setFixedSize(QSize(dp(80), dp(96)))
        b.clicked.connect(action)
        return b

    def _app_pixmap(self, app: menu.App) -> QPixmap:
        size = dp(60)
        glyph = GLYPH_FOR_DESKTOP.get(app.id)
        if glyph:
            return theme.app_tile(glyph, size)
        if app.icon:
            pm = theme.image_tile(app.icon, size)
            if pm is not None:
                return pm
        return theme.letter_tile(app.name, size)

    def _build_home(self) -> None:
        layout = self._clear(self.home)
        layout.setContentsMargins(dp(14), dp(36), dp(14), dp(12))
        self.clock = label("", "clock")
        self.date = label("", "date")
        for w in (self.clock, self.date):
            w.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            layout.addWidget(w)
        self._tick()
        layout.addSpacing(dp(18))

        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Search apps")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._layout_tiles)
        self.search.returnPressed.connect(self._launch_first)
        box = QFrame()
        box.setObjectName("searchbox")
        search_row = QHBoxLayout(box)
        search_row.setContentsMargins(dp(14), 0, dp(6), 0)
        search_row.setSpacing(dp(8))
        search_row.addWidget(pixmap_label(theme.render_svg(theme.glyph_svg("search", theme.TEXT_DIM), dp(20))))
        search_row.addWidget(self.search, 1)
        outer = QHBoxLayout()
        outer.setContentsMargins(dp(6), 0, dp(6), 0)
        outer.addWidget(box)
        layout.addLayout(outer)
        layout.addSpacing(dp(14))

        size = dp(60)
        self.tiles = [
            ("Anki", self._tile(theme.app_tile("anki", size), "Anki", self._open_anki)),
            ("Terminal", self._tile(theme.app_tile("terminal", size), "Terminal", lambda: self._run(TERMINAL))),
        ]
        apps = menu.apps()
        for app in apps:
            self.tiles.append((app.name, self._tile(self._app_pixmap(app), app.name,
                                                    lambda _=False, a=app: self._run(a.exec, a.terminal))))
        # Installed catalog apps whose package has no .desktop file.
        have = {a.id for a in apps}
        installed = pkg.installed()
        for e in CATALOG:
            if e["package"] in installed and e["desktop"] not in have:
                self.tiles.append((e["name"], self._tile(theme.app_tile(e["glyph"], size), e["name"],
                                                         lambda _=False, e=e: self._open(e))))
        self.tiles.append(("Get apps", self._tile(theme.app_tile("plus", size), "Get apps",
                                                  lambda: self.show_page(1))))
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(0)
        self.grid.setVerticalSpacing(dp(8))
        self.no_match = label("No apps found", "empty")
        self.no_match.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.grid_host)
        layout.addWidget(self.no_match)
        layout.addStretch(1)
        self._layout_tiles()

    def _matches(self) -> list[tuple[str, QToolButton]]:
        q = self.search.text().strip().lower()
        return [(n, t) for n, t in self.tiles if q in n.lower()]

    def _layout_tiles(self) -> None:
        for _, t in self.tiles:
            self.grid.removeWidget(t)
            t.hide()
        shown = self._matches()
        for i, (_, t) in enumerate(shown):
            self.grid.addWidget(t, i // 4, i % 4, Qt.AlignmentFlag.AlignHCenter)
            t.show()
        self.no_match.setVisible(not shown)

    def _launch_first(self) -> None:
        shown = self._matches()
        if shown:
            shown[0][1].click()

    def _tick(self) -> None:
        if hasattr(self, "clock"):
            self.clock.setText(time.strftime("%H:%M"))
            self.date.setText(time.strftime("%A, %d %B"))

    # --- software -------------------------------------------------------------

    def _build_software(self) -> None:
        layout = self._clear(self.software)
        self._header(layout, "Software", "Native Linux apps, downloaded when you install them.")
        installed = pkg.installed()

        self.progress_card, box = card()
        box.setContentsMargins(dp(16), dp(14), dp(16), dp(16))
        box.setSpacing(dp(10))
        self.progress_label = label("", "dim", wrap=True)
        self.progress_bar = QProgressBar()
        box.addWidget(self.progress_label)
        box.addWidget(self.progress_bar)
        self.progress_card.setVisible(self.busy is not None)
        layout.addWidget(self.progress_card)

        for entry in CATALOG:
            frame, box = card()
            row = QHBoxLayout()
            row.setContentsMargins(dp(8), dp(8), dp(8), dp(8))
            row.setSpacing(dp(14))
            row.addWidget(pixmap_label(theme.app_tile(entry["glyph"], dp(56))))
            texts = QVBoxLayout()
            texts.setSpacing(dp(2))
            texts.addWidget(label(entry["name"], "name", wrap=True))
            texts.addWidget(label(entry["summary"], "dim", wrap=True))
            is_installed = entry["package"] in installed
            texts.addWidget(label("Installed" if is_installed else entry["size"], "dim"))
            row.addLayout(texts, 1)
            if is_installed:
                open_b = QPushButton("Open")
                open_b.setObjectName("primary")
                open_b.clicked.connect(lambda _=False, e=entry: self._open(e))
                remove_b = QPushButton()
                remove_b.setObjectName("round")
                remove_b.setIcon(theme.line_icon("trash", dp(20)))
                remove_b.setIconSize(QSize(dp(20), dp(20)))
                remove_b.clicked.connect(lambda _=False, e=entry: self._confirm("remove", e))
                row.addWidget(open_b)
                row.addWidget(remove_b)
            else:
                get_b = QPushButton("Get")
                get_b.setObjectName("primary")
                get_b.setIcon(theme.line_icon("download", dp(18), "#FFFFFF"))
                get_b.setIconSize(QSize(dp(18), dp(18)))
                get_b.clicked.connect(lambda _=False, e=entry: self._confirm("install", e))
                row.addWidget(get_b)
            box.addLayout(row)
            for b in frame.findChildren(QPushButton):
                b.setEnabled(self.busy is None)
            layout.addWidget(frame)
        layout.addStretch(1)

    # --- settings -------------------------------------------------------------

    def _row(self, glyph: str, gradient: tuple[str, str], text: str, action) -> QPushButton:
        b = QPushButton()
        b.setObjectName("row")
        row = QHBoxLayout(b)
        row.setContentsMargins(dp(10), dp(8), dp(10), dp(8))
        row.setSpacing(dp(14))
        parts = (
            (pixmap_label(theme.app_tile(glyph, dp(38), gradient)), 0),
            (label(text), 1),
            (pixmap_label(theme.render_svg(theme.glyph_svg("chevron", theme.TEXT_DIM), dp(20))), 0),
        )
        for w, stretch in parts:
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            row.addWidget(w, stretch)
        if isinstance(action, str):
            b.clicked.connect(lambda: menu.android_request(action))
        else:
            b.clicked.connect(action)
        return b

    def _build_settings(self) -> None:
        layout = self._clear(self.settings)
        self._header(layout, "Settings", f"Personalize {theme.DISTRO} and set up touch and keyboard.")
        layout.addWidget(label("WALLPAPER", "section"))
        frame, box = card()
        box.setContentsMargins(dp(10), dp(12), dp(10), dp(10))
        self.wallpaper_grid = QGridLayout()
        self.wallpaper_grid.setSpacing(dp(6))
        box.addLayout(self.wallpaper_grid)
        box.addSpacing(dp(8))
        pick = QHBoxLayout()
        pick.setSpacing(dp(8))
        for text, glyph, fn in (("Gallery", "image", lambda: menu.android_request("ankidesk:pick-wallpaper")),
                                ("Files", "folder", self._pick_wallpaper_file)):
            b = QPushButton(text)
            b.setIcon(theme.line_icon(glyph, dp(18)))
            b.setIconSize(QSize(dp(18), dp(18)))
            b.clicked.connect(fn)
            pick.addWidget(b, 1)
        box.addLayout(pick)
        layout.addWidget(frame)
        layout.addSpacing(dp(12))
        self._build_wallpapers()
        groups = [
            ("TOUCH AND KEYBOARD", [
                ("pointer", ("#4FB3FF", "#1C6FE8"), "Tap to click", "ankidesk:input/touch"),
                ("touchpad", ("#A78BFA", "#6D28D9"), "Use screen as mouse pad", "ankidesk:input/trackpad"),
                ("keyboard", ("#2DD4BF", "#0F8F87"), "Show or hide keyboard", "ankidesk:keyboard/toggle"),
            ]),
            ("DEVICE", [
                ("monitor", ("#FDBA74", "#EA580C"), "Display", "ankidesk:display-settings"),
                ("drive", ("#86EFAC", "#16A34A"), "Storage and app info", "ankidesk:app-settings"),
                ("folder", ("#7DD3FC", "#0284C7"), "Open files in Android", "ankidesk:files"),
                ("phone", ("#CBD5E1", "#64748B"), "Switch to Android", "ankidesk:phone-apps"),
            ]),
            ("SYSTEM", [
                ("refresh", ("#93C5FD", "#2563EB"), "Restart desktop", self._restart_desktop),
                ("power", ("#FCA5A5", "#DC2626"), "Power off", self._confirm_power_off),
            ]),
        ]
        for title, rows in groups:
            layout.addWidget(label(title, "section"))
            frame, box = card()
            for i, (glyph, gradient, text, req) in enumerate(rows):
                if i:
                    box.addWidget(hline())
                box.addWidget(self._row(glyph, gradient, text, req))
            layout.addWidget(frame)
            layout.addSpacing(dp(12))

        about, box = card()
        box.setContentsMargins(dp(16), dp(16), dp(16), dp(16))
        row = QHBoxLayout()
        row.setSpacing(dp(14))
        row.addWidget(pixmap_label(theme.render_svg(open(theme.LOGO, encoding="utf-8").read(), dp(56))))
        texts = QVBoxLayout()
        texts.setSpacing(dp(2))
        texts.addWidget(label(f"{theme.DISTRO} {theme.VERSION}", "brand"))
        texts.addWidget(label("Anki desktop on Android. Built on Termux, Qt 6 and JWM.", "dim", wrap=True))
        row.addLayout(texts, 1)
        box.addLayout(row)
        layout.addWidget(about)
        layout.addStretch(1)

    def _build_wallpapers(self) -> None:
        grid = self.wallpaper_grid
        while grid.count():
            grid.takeAt(0).widget().deleteLater()
        current = theme.current_wallpaper()
        papers = theme.builtin_wallpapers()
        if os.path.exists(theme.CUSTOM_WALLPAPER):
            papers.append(("Yours", theme.CUSTOM_WALLPAPER))
        w, h = dp(88), dp(132)
        for i, (name, path) in enumerate(papers):
            b = QToolButton()
            b.setObjectName("thumb")
            b.setCheckable(True)
            b.setChecked(path == current)
            b.setText(name)
            b.setIcon(QIcon(self._thumbnail(path, w, h)))
            b.setIconSize(QSize(w, h))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.clicked.connect(lambda _=False, p=path: self._apply_wallpaper(p))
            grid.addWidget(b, i // 3, i % 3, Qt.AlignmentFlag.AlignHCenter)

    @staticmethod
    def _thumbnail(path: str, w: int, h: int) -> QPixmap:
        src = theme.wallpaper(w, h, path=path)
        out = QPixmap(w, h)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), dp(12), dp(12))
        p.setClipPath(clip)
        p.drawPixmap(0, 0, src)
        p.end()
        return out

    def _apply_wallpaper(self, path: str) -> None:
        theme.set_wallpaper(path)
        self._wallpaper = None
        self._build_wallpapers()
        self.update()

    def _pick_wallpaper_file(self) -> None:
        dialog = QFileDialog(self, "Choose a wallpaper", theme.HOME,
                             "Pictures (*.png *.jpg *.jpeg *.webp *.svg *.bmp *.gif)")
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setStyleSheet(f"* {{ background: #1A2133; color: {theme.TEXT}; font-size: {dp(15)}px; }}"
                             f"QPushButton {{ background: {theme.ACCENT}; border-radius: {dp(10)}px; "
                             f"padding: {dp(8)}px {dp(16)}px; }}")
        if dialog.exec() and dialog.selectedFiles():
            self._import_wallpaper(dialog.selectedFiles()[0])
        self.showMaximized()

    def _import_wallpaper(self, path: str) -> None:
        try:
            if path.endswith(".svg"):
                self._apply_wallpaper(path)
                return
            screen = self.screen().geometry()
            self._apply_wallpaper(theme.import_wallpaper(path, screen.width(), screen.height()))
        except (OSError, ValueError) as e:
            self.sheet.ask(theme.app_tile("image", dp(52)), "Cannot use this picture", str(e), "OK")

    def _on_config_changed(self, _path: str = "") -> None:
        # A picture picked in Android's gallery (PickWallpaperActivity).
        if os.path.exists(PICKED_WALLPAPER):
            try:
                self._import_wallpaper(PICKED_WALLPAPER)
            finally:
                os.remove(PICKED_WALLPAPER)
            self.show_page(2)
            self.activateWindow()

    # --- power ----------------------------------------------------------------

    def _restart_desktop(self) -> None:
        theme.write_jwmrc()
        subprocess.run(["jwm", "-restart"], check=False)

    def _confirm_power_off(self) -> None:
        self.sheet.ask(theme.app_tile("power", dp(52), ("#FCA5A5", "#DC2626")), "Power off?",
                       "Anki and all apps close; your collection is saved. Open the app again to start.",
                       "Power off", self._power_off, kind="danger")

    def _power_off(self) -> None:
        # Ask every window to close (Anki saves and syncs on close), then end
        # the session once Anki is gone or after a grace period.
        for w in x11.find(lambda w: w.wm_class != "ankidesk-shell"):
            x11.close_window(w.id)
        deadline = time.monotonic() + 30

        def check() -> None:
            if x11.find(lambda w: w.wm_class.lower() == "anki") and time.monotonic() < deadline:
                QTimer.singleShot(500, check)
            else:
                QApplication.quit()

        QTimer.singleShot(500, check)

    # --- actions --------------------------------------------------------------

    def _run(self, command: str, terminal: bool = False) -> None:
        launch(command, terminal)

    def _open_anki(self) -> None:
        # Switch to Anki's main window if it is open, otherwise start it.
        wins = x11.find(lambda w: w.wm_class.lower() == "anki")
        main = [w for w in wins if w.title.endswith("- Anki")] or wins
        if not (main and x11.activate(main[0].id)):
            launch(LAUNCH_ANKI)

    def _open(self, entry: dict) -> None:
        for app in menu.apps():
            if app.id == entry["desktop"]:
                self._run(app.exec, app.terminal)
                return
        self._run(entry.get("exec", shlex.quote(entry["package"])), entry.get("terminal", False))

    def _confirm(self, action: str, entry: dict) -> None:
        if self.thread is not None:
            return
        icon = theme.app_tile(entry["glyph"], dp(52))
        if action == "remove":
            self.sheet.ask(icon, f"Remove {entry['name']}?", "You can install it again at any time.",
                           "Remove", lambda: self._start("remove", entry), kind="danger")
            return
        # Size the download in the background; the server can be slow.
        self.sheet.ask(icon, f"Install {entry['name']}?", "Checking download size…", "Install",
                       lambda: self._start("install", entry))
        self.sheet.ok.setEnabled(False)
        self._run_worker("size", entry)

    def _start(self, action: str, entry: dict) -> None:
        if self.thread is not None:
            return
        self.busy = entry["package"]
        self._build_software()
        self.progress_label.setText(("Installing " if action == "install" else "Removing ") + entry["name"])
        self.progress_bar.setValue(0)
        self._run_worker(action, entry)

    def _run_worker(self, action: str, entry: dict) -> None:
        self.thread = QThread()
        self.worker = Worker(action, entry["package"])
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(lambda result: self._on_finished(action, entry, result))
        self.thread.start()

    def _on_progress(self, text: str, fraction: float) -> None:
        self.progress_label.setText(text)
        self.progress_bar.setValue(int(fraction * 100))

    def _on_finished(self, action: str, entry: dict, result: str) -> None:
        self.thread.quit()
        self.thread.wait()
        self.thread = self.worker = None
        if action == "size":
            if not self.sheet.isVisible():
                return
            if result.startswith("="):
                dl, size = map(int, result[1:].split(":"))
                self.sheet.text.setText(f"Downloads {dl / 2**20:.1f} MB and uses {size / 2**20:.0f} MB.")
                self.sheet.ok.setEnabled(True)
            else:
                self.sheet.ask(theme.app_tile(entry["glyph"], dp(52)), "Cannot reach the package server",
                               result, "OK")
            return
        self.busy = None
        if result:
            self.sheet.ask(theme.app_tile(entry["glyph"], dp(52)), "Something went wrong", result, "OK")
        self.reload()
        self.show_page(1)

    # --- visibility -----------------------------------------------------------

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Back):
            if self.sheet.isVisible():
                self.sheet.close_sheet()
            else:
                self.show_home()
            return
        super().keyPressEvent(event)

    def show_home(self) -> None:
        self.sheet.close_sheet()
        if hasattr(self, "search"):
            self.search.clear()
            self.search.clearFocus()
        self._tick()
        self.show_page(0)
        self.showMaximized()
        self.activateWindow()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        # The desktop is not closed with a gesture or Alt+F4; see "Power off".
        event.ignore()


# Windows that show and hide the keyboard themselves (ankidesk_keyboard.py).
OWN_KEYBOARD = {"anki", "ankidesk-shell"}


def watch_taps(kbd: keyboard.Keyboard) -> None:
    """Keyboard for other apps (terminals, installed apps): after a tap on one
    of their windows, open it if the pointer is a text cursor, else close it."""
    try:
        watcher = x11.TapWatcher()
    except OSError as e:
        print("no tap watcher:", e, file=sys.stderr)
        return

    def check() -> None:
        client = watcher.client_under_pointer()
        if client is None or client.wm_class.lower() in OWN_KEYBOARD:
            return
        show = watcher.text_cursor()
        kbd.want(show, force=not show)

    def on_readable() -> None:
        if watcher.taps():
            # Give the app a moment to update the cursor for the new position.
            QTimer.singleShot(120, check)

    notifier = QSocketNotifier(watcher.fileno(), QSocketNotifier.Type.Read)
    notifier.activated.connect(on_readable)
    kbd.tap_watcher = (watcher, notifier)  # kept alive with the keyboard
    on_readable()


def main() -> int:
    global SCALE
    app = QApplication(sys.argv)
    app.setApplicationName("ankidesk-shell")
    screen = app.primaryScreen().geometry()
    SCALE = max(min(screen.width(), screen.height()) / 360, 1.0)
    font = QFont("DejaVu Sans")
    font.setPixelSize(dp(15))
    app.setFont(font)
    shell = Shell()
    kbd = keyboard.install(app)
    watch_taps(kbd)
    scroller = DragScroll()
    app.installEventFilter(scroller)
    os.makedirs(theme.CONFIG_DIR, exist_ok=True)
    watcher = QFileSystemWatcher([theme.CONFIG_DIR])
    watcher.directoryChanged.connect(shell._on_config_changed)

    server = QLocalServer()
    QLocalServer.removeServer(menu.SHELL_SOCKET)
    if not server.listen(menu.SHELL_SOCKET):
        print("cannot listen on", menu.SHELL_SOCKET, file=sys.stderr)
        return 1

    def on_connection() -> None:
        conn = server.nextPendingConnection()

        def on_ready() -> None:
            for line in bytes(conn.readAll()).decode().split():
                if line in ("show", "toggle"):
                    shell.show_home()
                elif line == "reload":
                    shell.reload()

        conn.readyRead.connect(on_ready)

    server.newConnection.connect(on_connection)
    shell.show_home()
    ready = os.environ.get("ANKIDX_READY_FILE")
    if ready:
        # The desktop is up: the Android app swaps its splash for the display.
        QTimer.singleShot(300, lambda: open(ready, "w").close())
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
