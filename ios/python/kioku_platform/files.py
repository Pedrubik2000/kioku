"""Choosing files on iOS.

A path returned by Qt's file dialog points into another app's container (or
iCloud), and iOS only lets the app read it through the security-scoped URL
the picker returned, which Python's open() never sees. The document picker
in copy mode avoids that: iOS copies the chosen files into this app's tmp
folder and hands back paths Python can open normally.
"""

from __future__ import annotations

import os
from typing import Any

from PyQt6.QtCore import QEventLoop
from rubicon.objc import NSObject, ObjCClass, at, objc_method
from rubicon.objc.runtime import load_library

from .webview import prop

load_library("UniformTypeIdentifiers")

UIDocumentPickerViewController = ObjCClass("UIDocumentPickerViewController")
UTType = ObjCClass("UTType")
NSMutableArray = ObjCClass("NSMutableArray")

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "tif", "tiff", "heic", "avif"}


class _PickerDelegate(NSObject):
    @objc_method
    def documentPicker_didPickDocumentsAtURLs_(self, picker, urls) -> None:
        _state["paths"] = [str(prop(url, "path")) for url in urls]
        _state["loop"].quit()

    @objc_method
    def documentPickerWasCancelled_(self, picker) -> None:
        _state["paths"] = []
        _state["loop"].quit()


_state: dict[str, Any] = {}
_delegate = _PickerDelegate.alloc().init()


def _content_types(name_filter: str) -> Any:
    """Qt name filter ("Images (*.png *.jpg)") -> UTTypes for the picker."""
    exts = {
        part.lstrip("*.").lower()
        for part in name_filter.replace("(", " ").replace(")", " ").replace(";", " ").split()
        if part.startswith("*.")
    }
    types = NSMutableArray.alloc().init()
    if exts and exts <= IMAGE_EXTENSIONS:
        types.addObject_(UTType.typeWithIdentifier_(at("public.image")))
    else:
        # Anki's own formats have no registered type; allow any file
        types.addObject_(UTType.typeWithIdentifier_(at("public.item")))
    return types


def _top_view_controller() -> Any:
    app = prop(ObjCClass("UIApplication"), "sharedApplication")
    window = None
    for scene in prop(prop(app, "connectedScenes"), "allObjects"):
        for w in prop(scene, "windows"):
            if window is None or prop(w, "isKeyWindow"):
                window = w
    controller = prop(window, "rootViewController")
    while prop(controller, "presentedViewController") is not None:
        controller = prop(controller, "presentedViewController")
    return controller


def pick_files(name_filter: str = "*", multi: bool = False) -> list[str]:
    picker = UIDocumentPickerViewController.alloc().initForOpeningContentTypes_asCopy_(
        _content_types(name_filter), True
    )
    picker.setAllowsMultipleSelection_(multi)
    picker.setDelegate_(_delegate)
    loop = QEventLoop()
    _state.update(loop=loop, paths=[])
    _top_view_controller().presentViewController_animated_completion_(picker, True, None)
    loop.exec()
    return list(_state.get("paths", []))


def save_path(file_name: str) -> str:
    """Exports go to Documents/Exports, which the Files app shows."""
    folder = os.path.join(os.path.expanduser("~"), "Documents", "Exports")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, file_name)
