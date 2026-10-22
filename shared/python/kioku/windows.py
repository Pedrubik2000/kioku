"""Phone-friendly top-level windows.

iOS has no window manager: a QDialog or the browser's QMainWindow appears
at its desktop size with no title bar, so it can be wider than the screen
and has no way to close it. Every top-level window except the main window
and popups is therefore made to fill the screen and given a title bar with a
Close button. Message boxes keep their own buttons and are just fitted to
the screen and centred.
"""

from __future__ import annotations

from typing import Any

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QMargins, QObject, QRect, Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QWidget,
)

BAR_HEIGHT = 44
BAR_PROPERTY = "kiokuTitleBar"
WINDOW_TYPES = (Qt.WindowType.Window, Qt.WindowType.Dialog, Qt.WindowType.Sheet)


class TitleBar(QWidget):
    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self.setObjectName(BAR_PROPERTY)
        self.setAutoFillBackground(True)
        self._window = window

        close = QPushButton("‹ " + _back_label(), self)
        close.setFlat(True)
        close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(window.close)
        font = close.font()
        font.setBold(True)
        close.setFont(font)

        self._title = QLabel(self)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        font = self._title.font()
        font.setBold(True)
        self._title.setFont(font)

        # right side: optional action button, else a spacer that keeps the
        # title centred
        self._right = QWidget(self)
        self._right.setFixedWidth(close.sizeHint().width())
        QHBoxLayout(self._right).setContentsMargins(0, 0, 0, 0)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.addWidget(close)
        layout.addWidget(self._title, 1)
        layout.addWidget(self._right)
        self.update_title()

    def add_action(self, text: str, callback: Any) -> QPushButton:
        button = QPushButton(text, self._right)
        button.setFlat(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(callback)
        self._right.layout().addWidget(button)
        self._right.setFixedWidth(max(self._right.width(), button.sizeHint().width()))
        return button

    def update_title(self) -> None:
        self._title.setText(self._window.windowTitle())

    def place(self, safe_top: int) -> None:
        self.setGeometry(0, safe_top, self._window.width(), BAR_HEIGHT)
        self.raise_()

    def paintEvent(self, evt: Any) -> None:
        super().paintEvent(evt)
        from PyQt6.QtGui import QPainter

        p = QPainter(self)
        p.setPen(self.palette().mid().color())
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


def _back_label() -> str:
    try:
        from aqt.utils import tr

        return tr.actions_back()
    except Exception:
        return "Back"


def _safe_area(w: QWidget) -> QMargins:
    handle = w.windowHandle()
    if handle is not None and hasattr(handle, "safeAreaMargins"):
        return handle.safeAreaMargins()
    import aqt

    # the main window fills the screen and has no margins of its own
    rect, inner = aqt.mw.rect(), aqt.mw.contentsRect()
    return QMargins(
        inner.left(),
        inner.top(),
        rect.right() - inner.right(),
        rect.bottom() - inner.bottom(),
    )


def _fit_children(w: QWidget, avail: QRect) -> None:
    """Desktop dialogs are laid out for a wide screen: children pinned to a
    minimum size, combo boxes as wide as their longest entry, long one-line
    labels. Relax those so the window fits the phone."""
    narrow = avail.width()
    for child in [w] + w.findChildren(QWidget):
        if child.minimumWidth() > narrow:
            child.setMinimumWidth(0)
        if child.minimumHeight() > avail.height():
            child.setMinimumHeight(0)
        if isinstance(child, QComboBox):
            child.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            child.setMinimumContentsLength(8)
        elif (
            isinstance(child, QLabel)
            and not child.wordWrap()
            and child.pixmap().isNull()
            and child.sizeHint().width() > narrow * 0.6
        ):
            child.setWordWrap(True)
    layout = w.layout()
    if layout is not None and layout.totalMinimumSize().width() > narrow:
        # still too wide: let the window be narrower than its layout wants
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)


def _available() -> QRect:
    screen = QGuiApplication.primaryScreen()
    return screen.availableGeometry() if screen is not None else QRect(0, 0, 400, 800)


class WindowManager(QObject):
    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        app.installEventFilter(self)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            screen.availableGeometryChanged.connect(self._refit_all)

    def eventFilter(self, obj: QObject | None, evt: QEvent | None) -> bool:
        if evt is None or not isinstance(obj, QWidget):
            return False
        kind = evt.type()
        if kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            if evt.key() == Qt.Key.Key_Back:  # type: ignore[attr-defined]
                # Android's Back: unhandled, it finishes the activity and
                # quits Anki
                if kind == QEvent.Type.KeyRelease:
                    _go_back()
                return True
            return False
        if kind == QEvent.Type.Show and obj.isWindow():
            if self._manageable(obj):
                # after the window's own show logic (e.g. restoring geometry)
                QTimer.singleShot(0, lambda w=obj: self._adopt(w))
        elif kind == QEvent.Type.Resize and obj.isWindow():
            if self._bar(obj) is not None:
                self._layout(obj)
        elif kind == QEvent.Type.WindowTitleChange:
            bar = self._bar(obj)
            if bar is not None:
                bar.update_title()
        return False

    def _manageable(self, w: QWidget) -> bool:
        import aqt

        if w is aqt.mw or isinstance(w, QMenu):
            return False
        return w.windowType() in WINDOW_TYPES

    @staticmethod
    def _bar(w: QWidget) -> TitleBar | None:
        bar = w.findChild(TitleBar, BAR_PROPERTY, Qt.FindChildOption.FindDirectChildrenOnly)
        return bar

    def _adopt(self, w: QWidget) -> None:
        if sip.isdeleted(w) or not w.isVisible():
            return
        avail = _available()
        _fit_children(w, avail)
        if isinstance(w, QMessageBox):
            self._fit_centered(w)
            return
        if self._bar(w) is None:
            # we add the safe area ourselves (Qt would merge it with our
            # margins by taking the larger, hiding the title bar)
            w.setAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea, False)
            # remember the window's own margins; ours are added on top
            m = w.contentsMargins()
            w.setProperty("kiokuMargins", (m.left(), m.top(), m.right(), m.bottom()))
            bar = TitleBar(w)
            bar.show()
            adapt = ADAPTERS.get(type(w).__name__)
            if adapt is not None:
                adapt(w, bar)
        w.setMinimumSize(0, 0)
        w.setGeometry(avail)
        self._layout(w)

    def _layout(self, w: QWidget) -> None:
        """Margins = safe area + the window's own + the title bar. Qt merges
        user margins with the safe area by taking the larger of the two, so
        the safe area has to be included explicitly."""
        bar = self._bar(w)
        if bar is None:
            return
        own = w.property("kiokuMargins") or (0, 0, 0, 0)
        safe = _safe_area(w)
        margins = (
            safe.left() + own[0],
            safe.top() + own[1] + BAR_HEIGHT,
            safe.right() + own[2],
            safe.bottom() + own[3],
        )
        current = w.contentsMargins()
        if (current.left(), current.top(), current.right(), current.bottom()) != margins:
            w.setContentsMargins(*margins)
        bar.place(safe.top())

    @staticmethod
    def _fit_centered(w: QWidget) -> None:
        avail = _available()
        width = min(w.width(), avail.width() - 16)
        height = min(w.height(), avail.height() - 16)
        w.setMinimumSize(0, 0)
        w.resize(width, height)
        w.move(
            avail.x() + (avail.width() - width) // 2,
            avail.y() + (avail.height() - height) // 2,
        )

    def _refit_all(self) -> None:
        for w in QApplication.topLevelWidgets():
            if w.isVisible() and self._manageable(w):
                self._adopt(w)


def _phone_width() -> bool:
    return _available().width() < 600


def adapt_browser(browser: Any, bar: TitleBar) -> None:
    """The sidebar takes half a phone screen: start hidden in portrait and
    give it a title bar button; when shown, let it cover most of the width."""
    from aqt.utils import tr

    dock = browser.sidebarDockWidget

    def toggle() -> None:
        show = not dock.isVisible()
        browser.showSidebar(show)
        if show and _phone_width():
            browser.resizeDocks(
                [dock], [int(_available().width() * 0.8)], Qt.Orientation.Horizontal
            )

    bar.add_action(tr.browsing_sidebar(), toggle)
    if _phone_width():
        browser.showSidebar(False)


ADAPTERS = {"Browser": adapt_browser}

_manager: WindowManager | None = None


def _go_back() -> None:
    """Close the topmost popup or window; on the main window, leave the app
    running in the background like other Android apps."""
    import aqt

    w = (
        QApplication.activePopupWidget()
        or QApplication.activeModalWidget()
        or QApplication.activeWindow()
    )
    if w is None or w is aqt.mw:
        import kioku_platform

        move_to_back = getattr(kioku_platform, "move_to_back", None)
        if move_to_back is not None:
            move_to_back()
        return
    w.close()


def install(app: QApplication) -> None:
    global _manager
    _manager = WindowManager(app)
