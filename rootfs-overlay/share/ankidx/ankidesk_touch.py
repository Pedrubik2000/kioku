"""Touch helpers for Qt apps on a phone, used by the desktop shell and Anki.

* DragScroll: one-finger scrolling with momentum. The display sends a finger
  drag as a held left button; dragging inside a scrollable area scrolls it,
  like a phone, instead of selecting or doing nothing.
* SingleClickStyle: lists and file dialogs open an item with one tap instead
  of a double click.
* FitToScreen: dialogs are kept within the screen; Qt layouts made for a
  desktop monitor would otherwise be cut off on a 480-pixel-wide phone.
"""

from __future__ import annotations

import os
import time
from typing import Callable

from PyQt6.QtCore import QEvent, QObject, QPointF, Qt, QTimer, QUrl
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractScrollArea,
    QAbstractSlider,
    QApplication,
    QDialog,
    QFileDialog,
    QProxyStyle,
    QStyle,
    QWidget,
)

# Height of JWM's title bar plus borders, in X pixels (see jwmrc).
TITLE_BAR_PX = 92 + 2 * 3


class DragScroll(QObject):
    """Install on the QApplication. `accept(area)` picks the scroll areas that
    scroll by dragging. Once a drag starts, the press is cancelled, so the
    button or item under the finger is not clicked."""

    def __init__(self, accept: Callable[[QAbstractScrollArea], bool], slop: float = 24,
                 horizontal: bool = True) -> None:
        super().__init__()
        self.accept, self.slop, self.horizontal = accept, slop, horizontal
        self.area: QAbstractScrollArea | None = None
        self.target: QObject | None = None
        self.dragging = False
        self.cancelling = False
        self.press: tuple[int, float, float] | None = None  # the press being delivered
        self.x0 = self.y0 = 0.0
        self.h0 = self.v0 = 0
        self.samples: list[tuple[float, float, float]] = []
        self.velocity = (0.0, 0.0)  # px per ms, positive scrolls right/down
        self.coasting: QAbstractScrollArea | None = None
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._coast)

    def _area_of(self, w: QObject | None) -> QAbstractScrollArea | None:
        # The innermost area that can scroll; scroll bars and sliders keep their own drag.
        while w is not None:
            if isinstance(w, QAbstractSlider):
                return None
            if isinstance(w, QAbstractScrollArea) and self.accept(w):
                if w.verticalScrollBar().maximum() > 0 or (self.horizontal and w.horizontalScrollBar().maximum() > 0):
                    return w
            w = w.parent()
        return None

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt API
        t = event.type()
        if t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if not isinstance(obj, QWidget):
                return False  # the QWindow sees it first; wait for the widget
            # A press no widget accepts (a label, a card) goes on to the parents;
            # only the first widget picks the area, or a parent outside every
            # scroll area would drop it.
            p = event.globalPosition()
            key = (event.timestamp(), p.x(), p.y())
            if key == self.press:
                return False
            self.press = key
            self.timer.stop()
            self.area = self._area_of(obj)
            if self.area is not None:
                self.target = obj
                self.dragging = False
                self.x0, self.y0 = p.x(), p.y()
                self.h0 = self.area.horizontalScrollBar().value()
                self.v0 = self.area.verticalScrollBar().value()
                self.samples = [(time.monotonic() * 1000, self.x0, self.y0)]
        elif t == QEvent.Type.MouseMove and self.area is not None and event.buttons() & Qt.MouseButton.LeftButton:
            p = event.globalPosition()
            dx, dy = p.x() - self.x0, p.y() - self.y0
            if not self.dragging and max(abs(dx), abs(dy)) > self.slop:
                self.dragging = True
                self._cancel_press()
            if self.dragging:
                if self.horizontal:
                    self.area.horizontalScrollBar().setValue(round(self.h0 - dx))
                self.area.verticalScrollBar().setValue(round(self.v0 - dy))
                self.samples = (self.samples + [(time.monotonic() * 1000, p.x(), p.y())])[-5:]
                return True
        elif t == QEvent.Type.MouseButtonRelease and self.area is not None and not self.cancelling:
            dragging, area = self.dragging, self.area
            self.dragging, self.area, self.target = False, None, None
            if dragging:
                (t0, x0, y0), (t1, x1, y1) = self.samples[0], self.samples[-1]
                if t1 - t0 > 0 and time.monotonic() * 1000 - t1 < 80:
                    self.velocity = (-(x1 - x0) / (t1 - t0) if self.horizontal else 0.0, -(y1 - y0) / (t1 - t0))
                    self.coasting = area
                    self.timer.start()
                return True
        return False

    def _cancel_press(self) -> None:
        """Release the pressed widget without a click: buttons are no longer
        down, and lists end their selection drag with the pointer far away."""
        w = self.target
        if isinstance(w, QAbstractButton):
            w.setDown(False)
        if isinstance(w, QWidget):
            far = QPointF(-100000, -100000)
            self.cancelling = True
            try:
                QApplication.sendEvent(w, QMouseEvent(QEvent.Type.MouseButtonRelease, far, far, far,
                                                      Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
                                                      Qt.KeyboardModifier.NoModifier))
            finally:
                self.cancelling = False

    def _coast(self) -> None:
        area = self.coasting
        try:
            bars = (area.horizontalScrollBar(), area.verticalScrollBar())
        except RuntimeError:  # the area was deleted
            self.timer.stop()
            return
        moving = False
        for bar, v in zip(bars, self.velocity):
            if abs(v) >= 0.05 and bar.minimum() < bar.value() + v * 16 < bar.maximum():
                moving = True
            bar.setValue(round(bar.value() + v * 16))
        self.velocity = (self.velocity[0] * 0.94, self.velocity[1] * 0.94)
        if not moving:
            self.timer.stop()


class SingleClickStyle(QProxyStyle):
    """Activate list items with one tap. Set on item views (see FitToScreen)."""

    def styleHint(self, hint, option=None, widget=None, returnData=None):  # noqa: N802 - Qt API
        if hint == QStyle.StyleHint.SH_ItemView_ActivateItemOnSingleClick:
            return 1
        return super().styleHint(hint, option, widget, returnData)


class FitToScreen(QObject):
    """Install on the QApplication. Keeps shown dialogs within the screen's
    free area (without the dock), shrinking minimum sizes set for desktop
    monitors; file dialogs fill the screen and open folders with one tap."""

    def __init__(self, skip: Callable[[QWidget], bool] = lambda w: False) -> None:
        super().__init__()
        self.skip = skip
        self.single_click = SingleClickStyle()
        self.single_click.setParent(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt API
        # Dialogs only: main windows are maximized by the window manager, and
        # resizing one (e.g. when it is shown again after being minimized)
        # would undo that.
        if event.type() == QEvent.Type.Show and isinstance(obj, QDialog) and obj.isWindow():
            if not obj.isMaximized() and not obj.isFullScreen() and not self.skip(obj):
                if isinstance(obj, QFileDialog):
                    self._file_dialog(obj)
                self.fit(obj)
                # Geometry restored after show (e.g. Anki's saved sizes).
                QTimer.singleShot(0, lambda w=obj: self.fit(w))
        return False

    def _file_dialog(self, dialog: QFileDialog) -> None:
        for view in dialog.findChildren(QAbstractItemView):
            view.setStyle(self.single_click)
        # Shortcuts to the imports and, with phone storage on, the phone's folders.
        home = os.path.expanduser("~")
        places = [home] + [os.path.join(home, p) for p in
                           ("Imports", "storage/downloads", "storage/documents", "storage/shared")]
        urls = [QUrl.fromLocalFile(p) for p in places if os.path.isdir(p)]
        if urls and not dialog.property("kioku_places"):
            dialog.setProperty("kioku_places", True)
            dialog.setSidebarUrls(urls + [u for u in dialog.sidebarUrls() if u not in urls])

    @staticmethod
    def fit(w: QWidget) -> None:
        try:
            screen = w.screen()
        except RuntimeError:  # deleted meanwhile
            return
        if screen is None or not w.isVisible():
            return
        avail = screen.availableGeometry()
        max_w = avail.width() - round(6 / w.devicePixelRatioF())
        max_h = avail.height() - round(TITLE_BAR_PX / w.devicePixelRatioF())
        if isinstance(w, QFileDialog):
            w.resize(max_w, max_h)
            return
        if w.width() <= max_w and w.height() <= max_h:
            return
        for c in [w] + w.findChildren(QWidget):
            if c.minimumWidth() > max_w:
                c.setMinimumWidth(max_w if c is w else 0)
            if c.minimumHeight() > max_h:
                c.setMinimumHeight(max_h if c is w else 0)
        w.resize(min(w.width(), max_w), min(w.height(), max_h))
