"""Android soft keyboard for Qt apps: shown while a text field has focus (its
text cursor is showing), hidden again when focus leaves or a tap lands
outside any text field, as on Android. Tapping a text field always shows it,
also after the user closed the keyboard with Back while the field kept focus.

Used by Anki (ankidesk_mobile.py, which adds its web views) and the shell.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QEvent, QObject, QTimer
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QFileDialog,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)

from ankidesk_menu import android_request


class Keyboard:
    """Debounced show/hide, so moving focus between two fields does not flicker."""

    def __init__(self) -> None:
        self.visible = False
        self.wanted = False
        self.force = False
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._apply)

    def want(self, show: bool, force: bool = False) -> None:
        self.wanted = show
        self.force = force
        self.timer.start(40 if show else 250)

    def _apply(self) -> None:
        # Taps are forced: the user may have opened or closed the keyboard
        # without us (Back, the dock's keyboard button), so `visible` is a guess.
        if self.wanted != self.visible or self.force:
            self.visible = self.wanted
            android_request("ankidesk:keyboard/" + ("show" if self.visible else "hide"))


def is_text_input(w: QWidget | None) -> bool:
    if isinstance(w, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)):
        return not w.isReadOnly()
    if isinstance(w, QComboBox):
        return w.isEditable()
    return False


class _TapOutside(QObject):
    def __init__(self, keyboard: Keyboard, skip: Callable[[QWidget], bool]) -> None:
        super().__init__()
        self.keyboard, self.skip = keyboard, skip

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress and isinstance(obj, QWidget) and not self.skip(obj):
            # A text edit's events go to its viewport, a spin box's to its line edit.
            text = is_text_input(obj) or is_text_input(obj.parentWidget())
            self.keyboard.want(text, force=True)
        return False


KEYBOARD: Keyboard | None = None  # the one install() made


def install(app: QApplication, skip: Callable[[QWidget | None], bool] = lambda w: False) -> Keyboard:
    """Follow focus in `app`. `skip(widget)` marks widgets that report text
    focus themselves (web views) and must be left alone."""
    global KEYBOARD
    keyboard = KEYBOARD = Keyboard()

    def on_focus_changed(old: QWidget | None, new: QWidget | None) -> None:
        if not skip(new):
            text = is_text_input(new)
            # A file dialog focuses its file name field on opening; there the
            # keyboard would only hide the files. A tap on the field opens it.
            if text and isinstance(new.window(), QFileDialog):
                return
            keyboard.want(text, force=text)

    app.focusChanged.connect(on_focus_changed)
    keyboard.tap_outside = _TapOutside(keyboard, skip)  # kept alive with the keyboard
    app.installEventFilter(keyboard.tap_outside)
    return keyboard
