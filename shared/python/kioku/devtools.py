"""Development helpers, active only when the app is launched with KIOKU_DEV=1
(see the run scripts in each variant's tools/):

- Qt messages go to the log file instead of the detached stderr;
- Documents/.kioku-cmd.py is executed on the main thread when it appears,
  its output written to Documents/.kioku-cmd.out;
- shot(path) saves a screenshot of the whole UI, web views included.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import traceback
from typing import Any

from PyQt6.QtCore import QTimer, qInstallMessageHandler

import kioku_platform as platform

DOCUMENTS = platform.documents_dir()
CMD = os.path.join(DOCUMENTS, ".kioku-cmd.py")
OUT = os.path.join(DOCUMENTS, ".kioku-cmd.out")

_timer: QTimer | None = None
_namespace: dict[str, Any] = {}


def _qt_message(mode: Any, context: Any, message: str) -> None:
    print(f"Qt: {message}", file=sys.stderr)


def install() -> None:
    qInstallMessageHandler(_qt_message)
    if not os.environ.get("KIOKU_DEV"):
        return
    global _timer
    _timer = QTimer()
    _timer.setInterval(500)
    _timer.timeout.connect(_poll)
    _timer.start()
    # a locked phone suspends the app; stay awake while testing
    platform.keep_awake()
    print("Kioku: dev command channel active")


def _poll() -> None:
    if not os.path.exists(CMD):
        return
    try:
        with open(CMD, encoding="utf8") as f:
            code = f.read()
    finally:
        os.remove(CMD)
    import aqt

    _namespace.update(aqt=aqt, mw=aqt.mw, shot=shot, widgets=widgets)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            exec(compile(code, "kioku-cmd", "exec"), _namespace)
        except BaseException:
            traceback.print_exc()
    with open(OUT + ".tmp", "w", encoding="utf8") as f:
        f.write(buf.getvalue())
    os.replace(OUT + ".tmp", OUT)


def widgets() -> str:
    """Describe the visible top-level windows and their children."""
    from PyQt6.QtWidgets import QApplication, QWidget

    lines = []

    def walk(w: QWidget, depth: int) -> None:
        if not w.isVisible():
            return
        g = w.geometry()
        text = ""
        for attr in ("text", "windowTitle", "title"):
            fn = getattr(type(w), attr, None)
            if callable(fn):
                try:
                    value = fn(w)
                except Exception:
                    continue
                if isinstance(value, str) and value:
                    text = value[:40]
                    break
        lines.append(
            f"{'  ' * depth}{type(w).__name__} {w.objectName()!r} "
            f"{g.x()},{g.y()} {g.width()}x{g.height()} {text!r}"
        )
        for child in w.children():
            if isinstance(child, QWidget):
                walk(child, depth + 1)

    for top in QApplication.topLevelWidgets():
        walk(top, 0)
    return "\n".join(lines)


def shot(path: str | None = None) -> str:
    """Save a screenshot of the whole UI, web views included."""
    return platform.screenshot(path or os.path.join(DOCUMENTS, "screenshot.png"))
