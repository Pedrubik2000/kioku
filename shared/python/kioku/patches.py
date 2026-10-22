"""The places where Anki desktop assumes a desktop OS, adjusted for phones.

On iOS sys.platform is "ios" and on Android "android", so Anki takes its
Linux code paths. Most of them work unchanged; the ones below would load
libraries or start processes that do not exist here. What differs between
the platforms comes from kioku_platform.
"""

from __future__ import annotations

import logging

import kioku_platform as platform

logger = logging.getLogger("kioku.patches")


def apply() -> None:
    import aqt
    import aqt.theme
    import aqt.utils

    # setupGL() loads libGL.so.1 and configures Qt WebEngine's renderer;
    # neither exists here.
    aqt.setupGL = lambda pm: None

    # Linux dark mode detection runs dbus-send/gsettings
    aqt.theme.get_linux_dark_mode = _dark_mode

    # Other modules import these by name, so replace the code in place.
    aqt.utils.openFolder.__code__ = _open_folder.__code__
    aqt.utils.show_in_folder.__code__ = _show_in_folder.__code__
    # Desktop file dialogs return paths the app may not read (iOS) or
    # content:// URIs (Android); the platform pickers copy into the app.
    aqt.utils.getFile.__code__ = _get_file.__code__
    aqt.utils.getSaveFile.__code__ = _get_save_file.__code__
    # Taps go to the native web views, so Qt often has no focus widget (or
    # one in a window that has closed); Anki then takes changes made on the
    # main screen (e.g. collapsing a deck) for changes from another window,
    # dims the main screen and waits for a focus change to undo it.
    aqt.utils.current_window.__code__ = _current_window.__code__

    _patch_app()
    _patch_audio()
    _patch_profile_saving()


def _dark_mode() -> bool:
    try:
        return platform.dark_mode()
    except Exception:
        logger.exception("dark mode detection")
        return False


def _open_folder(path: str) -> None:
    import kioku_platform

    kioku_platform.open_folder(path)


def _show_in_folder(path: str) -> None:
    import os

    import kioku_platform

    kioku_platform.open_folder(path if os.path.isdir(path) else os.path.dirname(path))


def _current_window():  # type: ignore[no-untyped-def]
    import aqt
    from aqt.qt import QApplication

    widget = QApplication.focusWidget()
    window = widget.window() if widget is not None else None
    if window is None or not window.isVisible():
        window = QApplication.activeModalWidget() or QApplication.activeWindow()
    if window is None or not window.isVisible():
        window = aqt.mw
    return window


def _get_file(parent, title, cb, filter="*", dir=None, key=None, multi=False):  # type: ignore[no-untyped-def]
    import kioku_platform

    paths = kioku_platform.pick_files(filter, multi)
    if not paths:
        return None
    result = paths if multi else paths[0]
    if cb:
        cb(result)
    return result


def _get_save_file(parent, title, dir_description, key, ext, fname=""):  # type: ignore[no-untyped-def]
    import os

    import kioku_platform
    from aqt.utils import askUser, tr

    name = fname or f"export{ext}"
    if not name.lower().endswith(ext):
        name += ext
    path = kioku_platform.save_path(name)
    if os.path.exists(path) and not askUser(
        tr.qt_misc_this_file_exists_are_you_sure(), parent
    ):
        return None
    return path


def _patch_app() -> None:
    import aqt

    from kioku import devtools, mediaserver, windows

    original_init = aqt.AnkiApp.__init__

    def init(self, argv):  # type: ignore[no-untyped-def]
        original_init(self, argv)
        windows.install(self)
        mediaserver.install()
        devtools.install()

    aqt.AnkiApp.__init__ = init


def _patch_profile_saving() -> None:
    """Anki writes the profile (AnkiWeb login, preferences) to prefs21.db
    only when the profile is closed or Anki quits. Phone apps are usually
    killed in the background instead, which lost the AnkiWeb login after
    every restart. Save it when the login changes and whenever the app
    leaves the foreground."""
    import aqt
    from aqt.profiles import ProfileManager
    from aqt.qt import Qt

    def saving(setter):  # type: ignore[no-untyped-def]
        def set_and_save(self, val):  # type: ignore[no-untyped-def]
            setter(self, val)
            _save_profile(self)

        return set_and_save

    for name in ("set_sync_key", "set_sync_username", "set_host_number", "set_current_sync_url"):
        setattr(ProfileManager, name, saving(getattr(ProfileManager, name)))

    original_init = aqt.AnkiApp.__init__

    def init(self, argv):  # type: ignore[no-untyped-def]
        original_init(self, argv)

        def on_state(state: Qt.ApplicationState) -> None:
            if state != Qt.ApplicationState.ApplicationActive and aqt.mw is not None:
                _save_profile(aqt.mw.pm)

        self.applicationStateChanged.connect(on_state)

    aqt.AnkiApp.__init__ = init


def _save_profile(pm) -> None:  # type: ignore[no-untyped-def]
    if getattr(pm, "profile", None) is None or getattr(pm, "name", None) is None:
        return
    try:
        pm.save()
    except Exception:
        logger.exception("saving the profile")


def _patch_audio() -> None:
    import aqt.sound

    def setup_audio(taskman, base_folder: str, media_folder: str) -> None:
        aqt.sound.av_player.players.append(platform.audio_player(taskman, media_folder))

    aqt.sound.setup_audio = setup_audio
