"""Phone-style shell for the desktop: app grid, software center and settings.

Inspired by postmarketOS's phone shells, but built on the PyQt6 that Anki
already needs, so it adds no size. One resident process; the dock's "Apps"
button (bin/ankidesk-apps) toggles it through a local socket.

Pages:
  Apps      Anki, Terminal and every installed desktop app, with icons
  Software  optional native apps: install / open / remove, with progress
  Settings  touch mode, keyboard, display, storage
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QObject, QSize, Qt, QThread, pyqtSignal  # noqa: E402
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap  # noqa: E402
from PyQt6.QtNetwork import QLocalServer  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import ankidesk_menu as menu  # noqa: E402
import ankidesk_pkg as pkg  # noqa: E402

# Optional apps. All use Qt or plain terminals, so they share the libraries the
# runtime already has and stay small.
CATALOG = [
    {"package": "pcmanfm-qt", "name": "Files", "desktop": "pcmanfm-qt", "summary": "File manager"},
    {"package": "featherpad", "name": "Text Editor", "desktop": "featherpad", "summary": "Lightweight text editor"},
    {"package": "qterminal", "name": "QTerminal", "desktop": "qterminal", "summary": "Terminal with tabs"},
    {"package": "falkon", "name": "Web Browser", "desktop": "org.kde.falkon", "summary": "Falkon, using the same web engine as Anki"},
    {"package": "lximage-qt", "name": "Image Viewer", "desktop": "lximage-qt", "summary": "View and convert images"},
    {"package": "lxqt-archiver", "name": "Archives", "desktop": "lxqt-archiver", "summary": "Open and create zip, tar and 7z files"},
    {"package": "htop", "name": "System Monitor", "desktop": "htop", "summary": "Processes and memory (htop)",
     "exec": "htop", "terminal": True},
]

ACCENT = "#E95420"
STYLE = f"""
QWidget {{ background: #2C001E; color: white; font-size: 34px; }}
QLabel#title {{ font-size: 64px; font-weight: bold; padding: 24px 16px; }}
QToolButton {{ border: none; padding: 8px; font-size: 32px; }}
QToolButton:pressed {{ background: #5E2750; border-radius: 32px; }}
QPushButton {{ background: #5E2750; border: none; border-radius: 24px; padding: 26px 34px; font-size: 34px; }}
QPushButton:pressed {{ background: {ACCENT}; }}
QPushButton#primary {{ background: {ACCENT}; }}
QPushButton#nav {{ background: transparent; border-radius: 0; font-size: 36px; padding: 32px; }}
QPushButton#nav:checked {{ border-top: 6px solid {ACCENT}; font-weight: bold; }}
QProgressBar {{ background: #3D2A38; border: none; border-radius: 10px; height: 24px; text-align: center; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 10px; }}
QScrollArea {{ border: none; }}
QMessageBox QLabel {{ font-size: 34px; }}
"""


def letter_icon(name: str, size: int = 128) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(ACCENT))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, size * 0.22, size * 0.22)
    p.setPen(QColor("white"))
    f = QFont()
    f.setPixelSize(int(size * 0.5))
    f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, name[:1].upper())
    p.end()
    return QIcon(pm)


def app_icon(path: str | None, name: str) -> QIcon:
    if path:
        icon = QIcon(path)
        if not icon.isNull():
            return icon
    return letter_icon(name)


def launch(command: str, terminal: bool = False) -> None:
    if terminal:
        command = f"st -f 'DejaVu Sans Mono:pixelsize=34' -e {command}"
    subprocess.Popen(["sh", "-c", command], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Worker(QObject):
    progress = pyqtSignal(str, float)
    finished = pyqtSignal(str)  # error message, empty on success

    def __init__(self, action: str, package: str) -> None:
        super().__init__()
        self.action, self.package = action, package

    def run(self) -> None:
        try:
            fn = pkg.install if self.action == "install" else pkg.remove
            fn([self.package], lambda label, f: self.progress.emit(label, f))
            self.finished.emit("")
        except Exception as e:  # noqa: BLE001 - shown to the user
            traceback.print_exc()
            self.finished.emit(str(e))


class Shell(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Apps")
        self.setStyleSheet(STYLE)
        self.thread: QThread | None = None
        self.worker: Worker | None = None

        self.pages = QStackedWidget()
        self.home = QWidget()
        self.software = QWidget()
        self.settings = self._build_settings()
        for page in (self.home, self.software, self.settings):
            self.pages.addWidget(self._scroll(page))

        nav = QHBoxLayout()
        nav.setSpacing(0)
        self.nav_buttons = []
        for i, label in enumerate(("Apps", "Software", "Settings")):
            b = QPushButton(label)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, i=i: self.show_page(i))
            nav.addWidget(b)
            self.nav_buttons.append(b)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.pages, 1)
        layout.addLayout(nav)
        self.reload()
        self.show_page(0)

    # --- pages ---------------------------------------------------------------

    @staticmethod
    def _scroll(w: QWidget) -> QScrollArea:
        s = QScrollArea()
        s.setWidgetResizable(True)
        s.setWidget(w)
        return s

    @staticmethod
    def _clear(w: QWidget) -> QVBoxLayout:
        old = w.layout()
        if old is not None:
            QWidget().setLayout(old)  # reparent to drop the old layout and its widgets
        layout = QVBoxLayout(w)
        return layout

    def show_page(self, i: int) -> None:
        self.pages.setCurrentIndex(i)
        for j, b in enumerate(self.nav_buttons):
            b.setChecked(i == j)

    def reload(self) -> None:
        self._build_home()
        self._build_software()

    def _tile(self, icon: QIcon, label: str, action) -> QToolButton:
        b = QToolButton()
        b.setIcon(icon)
        b.setIconSize(QSize(170, 170))
        b.setText(label)
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        b.setFixedSize(QSize(320, 290))
        b.clicked.connect(action)
        return b

    def _build_home(self) -> None:
        layout = self._clear(self.home)
        title = QLabel("Apps")
        title.setObjectName("title")
        layout.addWidget(title)
        grid = QGridLayout()
        tiles = [
            self._tile(letter_icon("A"), "Anki", self.hide),
            self._tile(letter_icon(">_"), "Terminal", lambda: self._run("st -f 'DejaVu Sans Mono:pixelsize=34'")),
        ]
        apps = menu.apps()
        for app in apps:
            tiles.append(self._tile(app_icon(app.icon, app.name), app.name,
                                    lambda _=False, a=app: self._run(a.exec, a.terminal)))
        # Installed catalog apps whose package has no .desktop file.
        have = {a.id for a in apps}
        installed = pkg.installed()
        for e in CATALOG:
            if e["package"] in installed and e["desktop"] not in have:
                tiles.append(self._tile(letter_icon(e["name"]), e["name"], lambda _=False, e=e: self._open(e)))
        tiles.append(self._tile(letter_icon("+"), "Get apps", lambda: self.show_page(1)))
        for i, t in enumerate(tiles):
            grid.addWidget(t, i // 3, i % 3)
        layout.addLayout(grid)
        layout.addStretch(1)

    def _build_software(self) -> None:
        layout = self._clear(self.software)
        title = QLabel("Software")
        title.setObjectName("title")
        layout.addWidget(title)
        installed = pkg.installed()
        self.progress_label = QLabel("")
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)
        for entry in CATALOG:
            row = QHBoxLayout()
            text = QLabel(f"<b style='font-size:40px'>{entry['name']}</b><br>"
                          f"<span style='color:#C9B8C4; font-size:30px'>{entry['summary']}</span>")
            text.setWordWrap(True)
            row.addWidget(text, 1)
            if entry["package"] in installed:
                open_b = QPushButton("Open")
                open_b.setObjectName("primary")
                open_b.clicked.connect(lambda _=False, e=entry: self._open(e))
                remove_b = QPushButton("Remove")
                remove_b.clicked.connect(lambda _=False, e=entry: self._start("remove", e))
                row.addWidget(open_b)
                row.addWidget(remove_b)
            else:
                b = QPushButton("Install")
                b.setObjectName("primary")
                b.clicked.connect(lambda _=False, e=entry: self._start("install", e))
                row.addWidget(b)
            layout.addLayout(row)
        layout.addStretch(1)

    def _build_settings(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        title = QLabel("Settings")
        title.setObjectName("title")
        layout.addWidget(title)
        items = [
            ("Touch: tap to click", "ankidesk:input/touch"),
            ("Touch: mouse pad", "ankidesk:input/trackpad"),
            ("Show / hide keyboard", "ankidesk:keyboard/toggle"),
            ("Display settings", "ankidesk:display-settings"),
            ("Storage and app info", "ankidesk:app-settings"),
            ("Open files in Android", "ankidesk:files"),
        ]
        for label, req in items:
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, r=req: menu.android_request(r))
            layout.addWidget(b)
        layout.addStretch(1)
        return w

    # --- actions --------------------------------------------------------------

    def _run(self, command: str, terminal: bool = False) -> None:
        launch(command, terminal)
        self.hide()

    def _open(self, entry: dict) -> None:
        for app in menu.apps():
            if app.id == entry["desktop"]:
                self._run(app.exec, app.terminal)
                return
        self._run(entry.get("exec", shlex.quote(entry["package"])), entry.get("terminal", False))

    def _start(self, action: str, entry: dict) -> None:
        if self.thread is not None:
            return
        if action == "install":
            try:
                dl, size = pkg.download_size([entry["package"]], pkg.index())
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "Software", f"Cannot reach the package server:\n{e}")
                return
            msg = f"Install {entry['name']}?\n\nDownload {dl / 2**20:.1f} MB, uses {size / 2**20:.0f} MB."
        else:
            msg = f"Remove {entry['name']}?"
        if QMessageBox.question(self, "Software", msg) != QMessageBox.StandardButton.Yes:
            return
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.thread = QThread()
        self.worker = Worker(action, entry["package"])
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.thread.start()

    def _on_progress(self, label: str, fraction: float) -> None:
        self.progress_label.setText(label)
        self.progress_bar.setValue(int(fraction * 100))

    def _on_finished(self, error: str) -> None:
        self.thread.quit()
        self.thread.wait()
        self.thread = self.worker = None
        if error:
            QMessageBox.warning(self, "Software", error)
        self.reload()
        self.show_page(1)

    # --- visibility -----------------------------------------------------------

    def toggle(self) -> None:
        if self.isVisible() and self.isActiveWindow():
            self.hide()
        else:
            self.show_page(0)
            self.showMaximized()
            self.raise_()
            self.activateWindow()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ankidesk-shell")
    font = app.font()
    font.setPixelSize(30)
    app.setFont(font)
    shell = Shell()

    server = QLocalServer()
    QLocalServer.removeServer(menu.SHELL_SOCKET)
    if not server.listen(menu.SHELL_SOCKET):
        print("cannot listen on", menu.SHELL_SOCKET, file=sys.stderr)
        return 1

    def on_connection() -> None:
        conn = server.nextPendingConnection()

        def on_ready() -> None:
            for line in bytes(conn.readAll()).decode().split():
                if line == "toggle":
                    shell.toggle()
                elif line == "show" and not shell.isVisible():
                    shell.toggle()
                elif line == "reload":
                    shell.reload()

        conn.readyRead.connect(on_ready)

    server.newConnection.connect(on_connection)
    if "--show" in sys.argv:
        shell.toggle()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
