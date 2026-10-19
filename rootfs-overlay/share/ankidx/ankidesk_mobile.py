"""Phone integration for Anki running inside the Android app.

* Shows Android's soft keyboard when a text field gets focus (Qt widgets and
  fields inside Anki's web views, e.g. the editor) and hides it afterwards.
* android_request() sends commands to the app through the same directory the
  xdg-open shim uses; AnkiService turns them into intents.
"""

import os

from aqt import gui_hooks
from aqt.qt import QApplication, QWebEngineScript, QWidget
from aqt.webview import AnkiWebView

from ankidesk_keyboard import Keyboard
from ankidesk_keyboard import install as install_keyboard

FONT_FACTOR = float(os.environ.get("ANKIDX_FONT_FACTOR", "1.2"))

_keyboard: Keyboard | None = None


def _in_webview(w: QWidget | None) -> bool:
    # Web views report their own focus changes (see _FOCUS_JS).
    while w is not None:
        if isinstance(w, AnkiWebView):
            return True
        w = w.parentWidget()
    return False


# Reports focus changes inside web views. composedPath()[0] reaches into shadow
# DOM, where the editor's fields live.
_FOCUS_JS = """
(function () {
    if (window.__ankideskFocus) return;
    window.__ankideskFocus = true;
    const textTypes = ["text", "search", "email", "url", "tel", "password", "number", ""];
    function editable(el) {
        if (!el) return false;
        if (el.isContentEditable) return true;
        if (el.tagName === "TEXTAREA") return !el.readOnly;
        if (el.tagName === "INPUT") return !el.readOnly && textTypes.includes((el.type || "").toLowerCase());
        return false;
    }
    function send(on) { if (window.pycmd) window.pycmd("ankidesk:kbd:" + (on ? 1 : 0)); }
    document.addEventListener("focusin", e => send(editable(e.composedPath()[0])), true);
    document.addEventListener("focusout", () => send(false), true);
})();
"""


def _install_focus_script(web: AnkiWebView) -> None:
    script = QWebEngineScript()
    script.setName("ankidesk-focus")
    script.setSourceCode(_FOCUS_JS)
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setRunsOnSubFrames(True)
    web.page().scripts().insert(script)


def _on_js_message(handled: tuple[bool, object], message: str, context: object) -> tuple[bool, object]:
    if message.startswith("ankidesk:kbd:"):
        show = message.endswith("1")
        if _keyboard is not None:
            _keyboard.want(show, force=not show)
        return True, None
    return handled


# Anki's deck list is laid out for a desktop window (deck column at least
# 15em, 4em per count, 12px cell padding: ~700px). Let it fit a phone.
_DECK_BROWSER_CSS = """
<style>
body { margin: 1em 0.25em; }
table { padding: 0.5rem; width: 100%; }
.decktd { min-width: 0; max-width: none; white-space: normal; }
.count { min-width: 2.2em; }
tr.deck td, .fancy tr.deck td { padding: 6px 4px; }
.gears { visibility: visible; }
</style>
"""


def _on_will_set_content(web_content, context) -> None:
    from aqt.deckbrowser import DeckBrowser

    if isinstance(context, DeckBrowser):
        web_content.head += _DECK_BROWSER_CSS


def setup() -> None:
    original_init = AnkiWebView.__init__

    def init(self: AnkiWebView, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        _install_focus_script(self)

    AnkiWebView.__init__ = init
    gui_hooks.webview_did_receive_js_message.append(_on_js_message)
    gui_hooks.webview_will_set_content.append(_on_will_set_content)

    def connect_focus() -> None:
        global _keyboard
        app = QApplication.instance()
        # Menus, dialogs and lists use the widget font, which stays small even
        # with Anki's UI scale; web content is sized by the scale alone.
        font = app.font()
        if font.pointSizeF() > 0:
            font.setPointSizeF(font.pointSizeF() * FONT_FACTOR)
        else:
            font.setPixelSize(round(font.pixelSize() * FONT_FACTOR))
        app.setFont(font)
        _keyboard = install_keyboard(app, skip=_in_webview)

    gui_hooks.main_window_did_init.append(connect_focus)
