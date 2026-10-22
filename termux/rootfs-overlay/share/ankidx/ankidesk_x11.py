"""Minimal X client on the bundled libX11/libXi/libXfixes (ctypes, no extra packages).

* Lists the open windows the window manager manages and asks it to activate or
  close one, so the desktop can switch to Anki instead of starting it twice.
* The dock's desktop button (`python ankidesk_x11.py desktop`): minimizes every
  window to show the desktop, and on the next tap brings them back with the
  window that was active on top.
* TapWatcher: notices every tap on the screen (XInput2 raw events) and tells
  whether the pointer then shows a text cursor (I-beam), which is how the
  desktop knows to open the keyboard for apps that are not ours (terminals,
  installed apps).
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
from dataclasses import dataclass

PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
TMPDIR = os.environ.get("TMPDIR", os.path.join(PREFIX, "tmp"))
SHOWN_DESKTOP = os.path.join(TMPDIR, "ankidesk-shown-desktop.json")
SHELL_CLASS = "ankidesk-shell"

_c_ulong_p = ctypes.POINTER(ctypes.c_ulong)

# Xlib's default error handler ends the process. Windows can close between
# listing them and reading their properties (BadWindow); such reads come back
# empty instead.
_ERROR_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)(lambda dpy, err: 0)


class _ClientMessage(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("message_type", ctypes.c_ulong),
        ("format", ctypes.c_int),
        ("data", ctypes.c_long * 5),
    ]


class _Event(ctypes.Union):
    _fields_ = [("xclient", _ClientMessage), ("pad", ctypes.c_long * 24)]


_CLIENT_MESSAGE = 33
_SUBSTRUCTURE_MASK = (1 << 19) | (1 << 20)  # SubstructureNotify | SubstructureRedirect


@dataclass
class Window:
    id: int
    wm_class: str
    title: str


class Display:
    def __init__(self) -> None:
        x = ctypes.CDLL(os.path.join(PREFIX, "lib/libX11.so"))
        x.XOpenDisplay.restype = ctypes.c_void_p
        x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x.XDefaultRootWindow.restype = ctypes.c_ulong
        x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x.XInternAtom.restype = ctypes.c_ulong
        x.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x.XGetWindowProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long, ctypes.c_long, ctypes.c_int,
            ctypes.c_ulong, _c_ulong_p, ctypes.POINTER(ctypes.c_int), _c_ulong_p, _c_ulong_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        x.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long,
                                 ctypes.POINTER(_Event)]
        x.XFlush.argtypes = [ctypes.c_void_p]
        x.XFree.argtypes = [ctypes.c_void_p]
        x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x.XSetErrorHandler.argtypes = [ctypes.c_void_p]
        x.XSetErrorHandler(ctypes.cast(_ERROR_HANDLER, ctypes.c_void_p))
        self.x = x
        self.dpy = x.XOpenDisplay(None)
        if not self.dpy:
            raise OSError("cannot open display")
        self.root = x.XDefaultRootWindow(self.dpy)

    def close(self) -> None:
        self.x.XCloseDisplay(self.dpy)

    def __enter__(self) -> "Display":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def atom(self, name: str) -> int:
        return self.x.XInternAtom(self.dpy, name.encode(), 0)

    def _prop(self, win: int, name: str) -> tuple[int, bytes]:
        actual_type, actual_format = ctypes.c_ulong(), ctypes.c_int()
        nitems, after, data = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_void_p()
        status = self.x.XGetWindowProperty(self.dpy, win, self.atom(name), 0, 1 << 16, 0, 0,
                                           ctypes.byref(actual_type), ctypes.byref(actual_format),
                                           ctypes.byref(nitems), ctypes.byref(after), ctypes.byref(data))
        if status != 0 or not data.value:
            return 0, b""
        # Format-32 items are C longs in Xlib's client-side representation.
        size = {8: 1, 16: ctypes.sizeof(ctypes.c_short), 32: ctypes.sizeof(ctypes.c_long)}.get(actual_format.value, 1)
        raw = ctypes.string_at(data.value, nitems.value * size)
        self.x.XFree(data)
        return actual_format.value, raw

    def windows(self) -> list[Window]:
        fmt, raw = self._prop(self.root, "_NET_CLIENT_LIST")
        if fmt != 32:
            return []
        ids = (ctypes.c_ulong * (len(raw) // ctypes.sizeof(ctypes.c_ulong))).from_buffer_copy(raw)
        out = []
        for wid in ids:
            _, title = self._prop(wid, "_NET_WM_NAME")
            if not title:
                _, title = self._prop(wid, "WM_NAME")
            out.append(Window(wid, self.wm_class(wid), title.decode(errors="replace")))
        return out

    def wm_class(self, win: int) -> str:
        """The class part of WM_CLASS ("" if the window has none)."""
        _, cls = self._prop(win, "WM_CLASS")
        parts = cls.split(b"\0")
        return (parts[1] if len(parts) > 1 else parts[0]).decode(errors="replace")

    def stacking(self) -> list[int]:
        """Ids of the managed windows, bottom first."""
        ids = self.atoms(self.root, "_NET_CLIENT_LIST_STACKING")
        return ids or [w.id for w in self.windows()]

    def active(self) -> int:
        ids = self.atoms(self.root, "_NET_ACTIVE_WINDOW")
        return ids[0] if ids else 0

    def _message(self, win: int, name: str, *data: int) -> None:
        ev = _Event()
        ev.xclient.type = _CLIENT_MESSAGE
        ev.xclient.send_event = 1
        ev.xclient.window = win
        ev.xclient.message_type = self.atom(name)
        ev.xclient.format = 32
        for i, d in enumerate(data):
            ev.xclient.data[i] = d
        self.x.XSendEvent(self.dpy, self.root, 0, _SUBSTRUCTURE_MASK, ctypes.byref(ev))
        self.x.XFlush(self.dpy)

    def atoms(self, win: int, name: str) -> list[int]:
        fmt, raw = self._prop(win, name)
        if fmt != 32:
            return []
        return list((ctypes.c_ulong * (len(raw) // ctypes.sizeof(ctypes.c_ulong))).from_buffer_copy(raw))

    def is_maximized(self, win: int) -> bool:
        state = self.atoms(win, "_NET_WM_STATE")
        return self.atom("_NET_WM_STATE_MAXIMIZED_VERT") in state and self.atom("_NET_WM_STATE_MAXIMIZED_HORZ") in state

    def is_hidden(self, win: int) -> bool:
        return self.atom("_NET_WM_STATE_HIDDEN") in self.atoms(win, "_NET_WM_STATE")

    def minimize(self, win: int) -> None:
        self._message(win, "WM_CHANGE_STATE", 3)  # IconicState

    def maximize(self, win: int, add: bool = True) -> None:
        self._message(win, "_NET_WM_STATE", 1 if add else 0, self.atom("_NET_WM_STATE_MAXIMIZED_VERT"),
                      self.atom("_NET_WM_STATE_MAXIMIZED_HORZ"), 2)

    def activate(self, win: int) -> None:
        self._message(win, "_NET_ACTIVE_WINDOW", 2, 0, 0)  # 2: request from a pager/taskbar

    def close_window(self, win: int) -> None:
        self._message(win, "_NET_CLOSE_WINDOW", 0, 2)


class _EventMask(ctypes.Structure):
    _fields_ = [("deviceid", ctypes.c_int), ("mask_len", ctypes.c_int), ("mask", ctypes.POINTER(ctypes.c_ubyte))]


class _Cookie(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("extension", ctypes.c_int),
        ("evtype", ctypes.c_int),
        ("cookie", ctypes.c_uint),
        ("data", ctypes.c_void_p),
    ]


class _RawEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("extension", ctypes.c_int),
        ("evtype", ctypes.c_int),
        ("time", ctypes.c_ulong),
        ("deviceid", ctypes.c_int),
        ("sourceid", ctypes.c_int),
        ("detail", ctypes.c_int),
    ]


class _AnyEvent(ctypes.Union):
    _fields_ = [("type", ctypes.c_int), ("xcookie", _Cookie), ("pad", ctypes.c_long * 24)]


class _CursorImage(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_short),
        ("y", ctypes.c_short),
        ("width", ctypes.c_ushort),
        ("height", ctypes.c_ushort),
        ("xhot", ctypes.c_ushort),
        ("yhot", ctypes.c_ushort),
        ("cursor_serial", ctypes.c_ulong),
        ("pixels", ctypes.POINTER(ctypes.c_ulong)),
    ]


_GENERIC_EVENT = 35
_XI_RAW_BUTTON_PRESS = 15
_XI_RAW_TOUCH_END = 24
_XI_ALL_MASTER_DEVICES = 1


class TapWatcher(Display):
    """Own X connection; poll fileno() and call taps() when it is readable."""

    def __init__(self) -> None:
        super().__init__()
        x = self.x
        xi = ctypes.CDLL(os.path.join(PREFIX, "lib/libXi.so"))
        xfixes = ctypes.CDLL(os.path.join(PREFIX, "lib/libXfixes.so"))
        x.XQueryExtension.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int),
                                      ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
        x.XConnectionNumber.argtypes = [ctypes.c_void_p]
        x.XPending.argtypes = [ctypes.c_void_p]
        x.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.POINTER(_AnyEvent)]
        x.XGetEventData.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Cookie)]
        x.XFreeEventData.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Cookie)]
        x.XQueryPointer.argtypes = [ctypes.c_void_p, ctypes.c_ulong, _c_ulong_p, _c_ulong_p] + \
            [ctypes.POINTER(ctypes.c_int)] * 4 + [ctypes.POINTER(ctypes.c_uint)]
        xi.XIQueryVersion.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
        xi.XISelectEvents.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(_EventMask), ctypes.c_int]
        xfixes.XFixesGetCursorImage.restype = ctypes.POINTER(_CursorImage)
        xfixes.XFixesGetCursorImage.argtypes = [ctypes.c_void_p]
        self.xfixes = xfixes

        opcode, ev, err = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        if not x.XQueryExtension(self.dpy, b"XInputExtension", ctypes.byref(opcode), ctypes.byref(ev),
                                 ctypes.byref(err)):
            raise OSError("no XInput extension")
        major, minor = ctypes.c_int(2), ctypes.c_int(2)
        if xi.XIQueryVersion(self.dpy, ctypes.byref(major), ctypes.byref(minor)) != 0:
            raise OSError("XInput 2 not supported")
        self.opcode = opcode.value
        bits = (ctypes.c_ubyte * 4)()
        # Touches arrive as touch events, not buttons, in the display's direct touch mode.
        for evtype in (_XI_RAW_BUTTON_PRESS, _XI_RAW_TOUCH_END):
            bits[evtype >> 3] |= 1 << (evtype & 7)
        mask = _EventMask(_XI_ALL_MASTER_DEVICES, len(bits), bits)
        xi.XISelectEvents(self.dpy, self.root, ctypes.byref(mask), 1)
        x.XFlush(self.dpy)

    def fileno(self) -> int:
        return self.x.XConnectionNumber(self.dpy)

    def taps(self) -> int:
        """Drain pending events; return how many left-button presses and
        lifted fingers there were."""
        n = 0
        ev = _AnyEvent()
        while self.x.XPending(self.dpy):
            self.x.XNextEvent(self.dpy, ctypes.byref(ev))
            cookie = ev.xcookie
            if ev.type != _GENERIC_EVENT or cookie.extension != self.opcode:
                continue
            if self.x.XGetEventData(self.dpy, ctypes.byref(cookie)):
                if cookie.evtype == _XI_RAW_TOUCH_END or (
                        cookie.evtype == _XI_RAW_BUTTON_PRESS and
                        ctypes.cast(cookie.data, ctypes.POINTER(_RawEvent)).contents.detail == 1):
                    n += 1
                self.x.XFreeEventData(self.dpy, ctypes.byref(cookie))
        return n

    def client_under_pointer(self) -> Window | None:
        """The application window under the pointer; None over the dock,
        the desktop background, a title bar or a popup (menu, tooltip), which
        the window manager does not manage."""
        win = self.root
        for _ in range(8):
            root_ret, child = ctypes.c_ulong(), ctypes.c_ulong()
            i, mask = ctypes.c_int(), ctypes.c_uint()
            self.x.XQueryPointer(self.dpy, win, ctypes.byref(root_ret), ctypes.byref(child), ctypes.byref(i),
                                 ctypes.byref(i), ctypes.byref(i), ctypes.byref(i), ctypes.byref(mask))
            if not child.value:
                return None
            win = child.value
            _, cls = self._prop(win, "WM_CLASS")
            if cls:
                if win not in self.atoms(self.root, "_NET_CLIENT_LIST"):
                    return None
                parts = cls.split(b"\0")
                return Window(win, (parts[1] if len(parts) > 1 else parts[0]).decode(errors="replace"), "")
        return None

    def text_cursor(self) -> bool:
        """Whether the pointer currently is an I-beam: hotspot in the middle
        and the drawing tall and narrow (core "xterm" glyph or a themed one)."""
        img = self.xfixes.XFixesGetCursorImage(self.dpy)
        if not img:
            return False
        c = img.contents
        w, h = c.width, c.height
        left, right, top, bottom = w, -1, h, -1
        for y in range(h):
            row = y * w
            for xx in range(w):
                if c.pixels[row + xx] >> 24 > 0x40:
                    left, right = min(left, xx), max(right, xx)
                    top, bottom = min(top, y), max(bottom, y)
        self.x.XFree(img)
        if right < 0:
            return False
        bw, bh = right - left + 1, bottom - top + 1
        centered = abs(c.xhot - (left + right) / 2) <= bw / 2 and top < c.yhot < bottom
        return centered and bh >= 1.6 * bw and bh >= h * 0.5


def screen_size() -> tuple[int, int]:
    """Width and height of the X screen in pixels."""
    with Display() as d:
        d.x.XDisplayWidth.argtypes = d.x.XDisplayHeight.argtypes = [ctypes.c_void_p, ctypes.c_int]
        return d.x.XDisplayWidth(d.dpy, 0), d.x.XDisplayHeight(d.dpy, 0)


def window_states() -> tuple[list[int], list[int]]:
    """Ids of the maximized and of the minimized windows."""
    try:
        with Display() as d:
            ids = [w.id for w in d.windows()]
            return [i for i in ids if d.is_maximized(i)], [i for i in ids if d.is_hidden(i)]
    except OSError:
        return [], []


def restore_states(maximized: list[int], minimized: list[int], minimize: bool = True) -> None:
    """Put windows back as window_states() found them (JWM forgets on restart).
    After a restart JWM may believe a window is maximized at the old screen
    size, so maximizing is undone and redone."""
    try:
        with Display() as d:
            current = {w.id for w in d.windows()}
            for wid in maximized:
                if wid in current:
                    d.maximize(wid, add=False)
                    d.maximize(wid)
            if minimize:
                for wid in minimized:
                    if wid in current:
                        d.minimize(wid)
    except OSError:
        pass


def ensure_maximized(win: int) -> None:
    """Maximize `win` if JWM has dropped it (screen resize, restart). Qt keeps
    believing the window is maximized then, so showMaximized() does nothing."""
    try:
        with Display() as d:
            if not d.is_maximized(win):
                d.maximize(win)
    except OSError:
        pass


def toggle_desktop() -> None:
    """Minimize every window (the desktop shows), or when none is open, bring
    back the ones minimized that way, the one that was active on top. JWM's
    own showdesktop also minimizes the desktop itself and loses track once a
    window is opened from the desktop."""
    with Display() as d:
        apps = {w.id for w in d.windows() if w.wm_class != SHELL_CLASS}
        order = [i for i in d.stacking() if i in apps]
        shown = [i for i in order if not d.is_hidden(i)]
        if shown:
            active = d.active()
            state = {"windows": shown, "active": active if active in shown else shown[-1]}
            try:
                with open(SHOWN_DESKTOP, "w", encoding="utf-8") as fh:
                    json.dump(state, fh)
            except OSError:
                pass
            for wid in reversed(shown):
                d.minimize(wid)
            return
        try:
            with open(SHOWN_DESKTOP, encoding="utf-8") as fh:
                state = json.load(fh)
        except (OSError, ValueError):
            state = {}
        back = [i for i in state.get("windows", []) if i in apps]
        if not back and order:
            back = [order[-1]]  # minimized some other way: the topmost one
        active = state.get("active")
        if active not in back:
            active = back[-1] if back else 0
        # Activating restores a minimized window; the active one goes last, on top.
        for wid in back:
            if wid != active:
                d.activate(wid)
        if active:
            d.activate(active)


def find(predicate) -> list[Window]:
    try:
        with Display() as d:
            return [w for w in d.windows() if predicate(w)]
    except OSError:
        return []


def activate(win: int) -> bool:
    try:
        with Display() as d:
            d.activate(win)
        return True
    except OSError:
        return False


def close_window(win: int) -> None:
    try:
        with Display() as d:
            d.close_window(win)
    except OSError:
        pass


if __name__ == "__main__":
    if sys.argv[1:] == ["desktop"]:
        toggle_desktop()
    else:
        sys.exit("usage: ankidesk_x11.py desktop")
