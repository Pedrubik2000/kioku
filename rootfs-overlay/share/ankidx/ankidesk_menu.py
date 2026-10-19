"""Installed desktop apps, read from the freedesktop .desktop files in the prefix.

Apps show up in the app grid once their package is installed and disappear
when it is removed; nothing is listed by hand.
"""

from __future__ import annotations

import configparser
import itertools
import os
import re
import socket
from dataclasses import dataclass

PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
APPLICATIONS = os.path.join(PREFIX, "share/applications")
ICON_DIRS = [
    os.path.join(PREFIX, "share/icons/hicolor", size, "apps")
    for size in ("scalable", "256x256", "128x128", "96x96", "64x64", "48x48", "32x32")
] + [os.path.join(PREFIX, "share/icons/breeze/apps/48"), os.path.join(PREFIX, "share/pixmaps")]
TMPDIR = os.environ.get("TMPDIR", PREFIX + "/tmp")
SHELL_SOCKET = os.path.join(TMPDIR, "ankidesk-shell.sock")
REQUEST_DIR = os.path.join(TMPDIR, "ankidx-open")
_counter = itertools.count()

# Desktop files that are part of the runtime, not apps for the user.
HIDDEN = {"anki.desktop", "jwm.desktop"}


@dataclass
class App:
    id: str
    name: str
    comment: str
    exec: str
    icon: str | None
    terminal: bool


def find_icon(name: str) -> str | None:
    if not name:
        return None
    if os.path.isabs(name):
        return name if os.path.exists(name) else None
    for d in ICON_DIRS:
        for ext in (".svg", ".png", ".xpm"):
            p = os.path.join(d, name + ext)
            if os.path.exists(p):
                return p
    return None


def apps() -> list[App]:
    out: list[App] = []
    if not os.path.isdir(APPLICATIONS):
        return out
    for fname in sorted(os.listdir(APPLICATIONS)):
        if not fname.endswith(".desktop") or fname in HIDDEN:
            continue
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            cp.read(os.path.join(APPLICATIONS, fname), encoding="utf-8")
            e = cp["Desktop Entry"]
        except (configparser.Error, KeyError, UnicodeDecodeError):
            continue
        if e.get("Type", "Application") != "Application" or e.get("NoDisplay", "false").lower() == "true":
            continue
        if e.get("Hidden", "false").lower() == "true" or "Exec" not in e:
            continue
        # Field codes (%f, %U ...) need a file/URL; the grid launches without one.
        cmd = re.sub(r"\s*%[fFuUdDnNickvm]", "", e["Exec"]).strip()
        out.append(App(
            id=fname[:-len(".desktop")],
            name=e.get("Name", fname),
            comment=e.get("Comment", ""),
            exec=cmd,
            icon=find_icon(e.get("Icon", "")),
            terminal=e.get("Terminal", "false").lower() == "true",
        ))
    out.sort(key=lambda a: a.name.lower())
    return out


def notify_shell() -> None:
    """Tell a running app grid to re-read the installed apps."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(SHELL_SOCKET)
        s.sendall(b"reload\n")
    except OSError:
        pass
    finally:
        s.close()


def android_request(uri: str) -> None:
    """Hand a URL or an ankidesk:<command> to the Android app (AnkiService)."""
    os.makedirs(REQUEST_DIR, exist_ok=True)
    name = f"req.{os.getpid()}.{next(_counter)}"
    tmp = os.path.join(REQUEST_DIR, "." + name)
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(uri)
    os.rename(tmp, os.path.join(REQUEST_DIR, name))
