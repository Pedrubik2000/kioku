"""Keep Anki's local web server (aqt.mediasrv) reachable.

Every Anki page is served from 127.0.0.1. iOS reclaims the listening sockets
of an app that goes to the background (opening the Files app to fetch a deck
is enough), after which the server thread keeps running but refuses every
connection and new pages come up blank. When the app becomes active again,
or a local page fails to load, check the server and, if needed, serve again
on the same port, so URLs that pages already use stay valid (or on a new one
if the old port is still held).
"""

from __future__ import annotations

import logging
import socket
import threading

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication

logger = logging.getLogger("kioku.mediaserver")


def _answers(port: int) -> bool:
    try:
        socket.create_connection(("127.0.0.1", port), timeout=1).close()
        return True
    except OSError:
        return False


def current_port() -> int | None:
    import aqt

    srv = getattr(aqt.mw, "mediaServer", None) if aqt.mw else None
    return srv.getPort() if srv is not None and srv._ready.is_set() else None


def ensure_running() -> bool:
    """Returns True if the server had to be restarted."""
    import aqt

    srv = getattr(aqt.mw, "mediaServer", None) if aqt.mw else None
    if srv is None or not srv._ready.is_set():
        return False
    port = srv.getPort()
    if _answers(port):
        return False

    logger.warning("media server stopped answering; serving again on port %d", port)
    from waitress import create_server

    from aqt.mediasrv import app as flask_app

    # Leave the old server alone: closing its sockets from this thread races
    # with its loop thread, and the descriptors get reused by the new server.
    # Its listener is dead anyway. MediaServer.run() only swallows errors from
    # that loop while is_shutdown is set.
    srv.is_shutdown = True
    try:
        server = create_server(
            flask_app, host="127.0.0.1", port=port, clear_untrusted_proxy_headers=True
        )
    except OSError:
        # the port is still held: use a new one (mw.serverURL() follows it)
        server = create_server(
            flask_app, host="127.0.0.1", port=0, clear_untrusted_proxy_headers=True
        )
        logger.warning("now serving on port %s", server.effective_port)
    srv.server = server
    threading.Thread(target=server.run, name="mediasrv", daemon=True).start()
    return True


def install() -> None:
    app = QGuiApplication.instance()
    if app is None:
        return

    def on_state(state: Qt.ApplicationState) -> None:
        if state == Qt.ApplicationState.ApplicationActive:
            QTimer.singleShot(0, ensure_running)

    app.applicationStateChanged.connect(on_state)
