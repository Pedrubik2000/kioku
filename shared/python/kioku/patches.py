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

    _patch_app()
    _patch_audio()


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


def _patch_audio() -> None:
    import aqt.sound

    def setup_audio(taskman, base_folder: str, media_folder: str) -> None:
        aqt.sound.av_player.players.append(platform.audio_player(taskman, media_folder))

    aqt.sound.setup_audio = setup_audio
