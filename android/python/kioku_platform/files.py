"""Choosing files on Android: the system picker returns content:// URIs,
which Python cannot open, so KiokuBridge copies the chosen files into the
app's cache and reports their paths."""

from __future__ import annotations

import os

from PyQt6.QtCore import QEventLoop

from . import bridge

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "tif", "tiff", "heic", "avif"}

_state: dict = {}


def _on_picked(event: dict) -> None:
    _state["paths"] = event.get("paths", [])
    loop = _state.get("loop")
    if loop is not None:
        loop.quit()


bridge.listen("picked", _on_picked)


def pick_files(name_filter: str = "*", multi: bool = False) -> list[str]:
    exts = {
        part.lstrip("*.").lower()
        for part in name_filter.replace("(", " ").replace(")", " ").replace(";", " ").split()
        if part.startswith("*.")
    }
    mime = "image/*" if exts and exts <= IMAGE_EXTENSIONS else "*/*"
    loop = QEventLoop()
    _state.update(loop=loop, paths=[])
    bridge.call("pickFiles", multi=multi, mime=mime)
    loop.exec()
    _state["loop"] = None
    return list(_state.get("paths", []))


def save_path(file_name: str) -> str:
    """Exports go to Exports/ in the app's external files folder."""
    from . import documents_dir

    folder = os.path.join(documents_dir(), "Exports")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, file_name)
