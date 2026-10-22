"""Calls to and events from the Java side (KiokuBridge.java), through the
_kioku_android module (src/kioku_android.cpp)."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

import _kioku_android

logger = logging.getLogger("kioku.bridge")

_listeners: dict[str, list[Callable[[dict], None]]] = {}


def call(method: str, **args: Any) -> Any:
    result = json.loads(_kioku_android.call(method, json.dumps(args)))
    if isinstance(result, dict) and "error" in result:
        raise RuntimeError(f"{method}: {result['error']}")
    return result


def listen(event_type: str, callback: Callable[[dict], None]) -> None:
    _listeners.setdefault(event_type, []).append(callback)


def _dispatch(text: str) -> None:
    event = json.loads(text)
    for callback in _listeners.get(event.get("type", ""), []):
        try:
            callback(event)
        except Exception:
            logger.exception("handling %s", event.get("type"))


_kioku_android.set_handler(_dispatch)
