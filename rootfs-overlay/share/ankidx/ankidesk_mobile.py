"""Phone integration for Anki running inside the Android app.

* Shows Android's soft keyboard when a text field gets focus or is tapped (Qt
  widgets and fields inside Anki's web views, e.g. the editor) and hides it
  afterwards.
* One-finger scrolling in web views (deck list, reviewer, editor, stats) and
  lists (browser, sidebar), instead of selecting text.
* Windows and dialogs made for a desktop monitor are kept on screen.
* Import offers the phone's storage (Android's file picker) as well as the
  Kioku home folder.
"""

import os

from aqt import gui_hooks
from aqt.qt import (
    QAbstractItemView,
    QAbstractScrollArea,
    QApplication,
    QMessageBox,
    QScrollArea,
    QWebEngineScript,
    QWidget,
)
from aqt.webview import AnkiWebView

import ankidesk_touch as touch
from ankidesk_keyboard import Keyboard
from ankidesk_keyboard import install as install_keyboard
from ankidesk_menu import android_request

FONT_FACTOR = float(os.environ.get("ANKIDX_FONT_FACTOR", "1.2"))

_keyboard: Keyboard | None = None


def _in_webview(w: QWidget | None) -> bool:
    # Web views report their own focus changes (see _FOCUS_JS).
    while w is not None:
        if isinstance(w, AnkiWebView):
            return True
        w = w.parentWidget()
    return False


# Reports focus changes inside web views, and taps on a text field that already
# has focus (the keyboard may have been closed with Back). composedPath()[0]
# reaches into shadow DOM, where the editor's fields live.
#
# Also scrolls with one finger: the display sends a drag as a held mouse
# button, which would select text. A drag that starts outside a text field
# scrolls the nearest scrollable element instead, with momentum, and the click
# at its end is dropped.
_FOCUS_JS = """
(function () {
    if (window.__ankideskFocus) return;
    window.__ankideskFocus = true;
    const textTypes = ["text", "search", "email", "url", "tel", "password", "number", ""];
    function editable(el) {
        if (!el || el.nodeType !== 1) return false;
        if (el.isContentEditable) return true;
        if (el.tagName === "TEXTAREA") return !el.readOnly;
        if (el.tagName === "INPUT") return !el.readOnly && textTypes.includes((el.type || "").toLowerCase());
        return false;
    }
    function send(on) { if (window.pycmd) window.pycmd("ankidesk:kbd:" + (on ? 1 : 0)); }
    document.addEventListener("focusin", e => send(editable(e.composedPath()[0])), true);
    document.addEventListener("focusout", e => { if (!editable(e.relatedTarget)) send(false); }, true);

    function parentOf(n) { return n.parentElement || (n.getRootNode && n.getRootNode().host) || null; }
    function inField(path) {
        // Text fields keep dragging for selection; sliders and lists for themselves.
        return path.some(n => editable(n) || (n.tagName && /^(SELECT|INPUT|TEXTAREA)$/.test(n.tagName)));
    }
    function scroller(n) {
        for (; n && n !== document.body && n !== document.documentElement; n = parentOf(n)) {
            if (n.nodeType !== 1) continue;
            const s = getComputedStyle(n);
            if (/(auto|scroll|overlay)/.test(s.overflowY + s.overflowX)
                && (n.scrollHeight > n.clientHeight + 1 || n.scrollWidth > n.clientWidth + 1)) return n;
        }
        return document.scrollingElement || document.documentElement;
    }
    const SLOP = 10;
    let down = null, dragging = false, el = null, last = null, samples = [], coast = 0;
    addEventListener("mousedown", e => {
        cancelAnimationFrame(coast);
        down = null;
        if (e.button !== 0) return;
        const path = e.composedPath();
        if (editable(path[0])) send(true);
        if (inField(path)) return;
        down = last = {x: e.clientX, y: e.clientY};
        dragging = false;
        el = scroller(path[0]);
        samples = [[e.timeStamp, e.clientX, e.clientY]];
    }, true);
    addEventListener("mousemove", e => {
        if (!down) return;
        if (!(e.buttons & 1)) { down = null; return; }
        if (!dragging && Math.hypot(e.clientX - down.x, e.clientY - down.y) > SLOP) {
            dragging = true;
            document.documentElement.style.userSelect = "none";
            getSelection().removeAllRanges();
        }
        if (!dragging) return;
        el.scrollBy(last.x - e.clientX, last.y - e.clientY);
        last = {x: e.clientX, y: e.clientY};
        samples.push([e.timeStamp, e.clientX, e.clientY]);
        if (samples.length > 5) samples.shift();
        e.preventDefault();
        e.stopPropagation();
    }, true);
    function swallow(ev) { ev.preventDefault(); ev.stopPropagation(); }
    addEventListener("mouseup", e => {
        if (!down) return;
        const was = dragging;
        down = null;
        dragging = false;
        document.documentElement.style.userSelect = "";
        if (!was) return;
        swallow(e);
        addEventListener("click", swallow, {capture: true, once: true});
        setTimeout(() => removeEventListener("click", swallow, true), 100);
        const [t0, x0, y0] = samples[0], [t1, x1, y1] = samples[samples.length - 1];
        if (t1 - t0 <= 0 || e.timeStamp - t1 > 80) return;
        let vx = (x0 - x1) / (t1 - t0), vy = (y0 - y1) / (t1 - t0), prev = performance.now();
        const target = el;
        function step(now) {
            const dt = now - prev;
            prev = now;
            target.scrollBy(vx * dt, vy * dt);
            vx *= Math.pow(0.94, dt / 16);
            vy *= Math.pow(0.94, dt / 16);
            if (Math.abs(vx) > 0.05 || Math.abs(vy) > 0.05) coast = requestAnimationFrame(step);
        }
        coast = requestAnimationFrame(step);
    }, true);
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
        if _keyboard is not None:
            _keyboard.want(message.endswith("1"), force=True)
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


def _drag_scrolls(area: QAbstractScrollArea) -> bool:
    # Lists and plain scroll areas; text edits keep dragging for selection.
    return isinstance(area, QAbstractItemView) or type(area) is QScrollArea


def _prompt_for_file_then_import(mw) -> None:
    """File > Import and the deck list's Import File: pick from the phone with
    Android's picker, or from the Kioku home folder with Anki's own dialog."""
    box = QMessageBox(mw)
    box.setWindowTitle("Import")
    box.setText("Where is the file you want to import?")
    box.setInformativeText("From the phone, Kioku copies it to the Imports folder and opens it here.")
    phone = box.addButton("Phone storage", QMessageBox.ButtonRole.AcceptRole)
    home = box.addButton("Kioku files", QMessageBox.ButtonRole.ActionRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.exec()
    if box.clickedButton() is phone:
        # The desktop passes the copied file back to Anki (AnkiQt.onAppMsg).
        android_request("ankidesk:pick-deck")
    elif box.clickedButton() is home:
        _original_prompt(mw)


_original_prompt = None


def setup() -> None:
    global _original_prompt
    from aqt.import_export import importing

    _original_prompt = importing.prompt_for_file_then_import
    importing.prompt_for_file_then_import = _prompt_for_file_then_import

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
        app._kioku_touch = (touch.DragScroll(_drag_scrolls, slop=10), touch.FitToScreen())
        for f in app._kioku_touch:
            app.installEventFilter(f)

    gui_hooks.main_window_did_init.append(connect_focus)
