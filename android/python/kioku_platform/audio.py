"""Card audio through Android's MediaPlayer (plays mp3, ogg, opus, …),
replacing Anki's mpv/mplayer players (Android apps cannot start processes)."""

from __future__ import annotations

import os
from typing import Any

from anki.sound import AVTag, SoundOrVideoTag
from aqt import gui_hooks
from aqt.qt import QTimer
from aqt.sound import OnDoneCallback, SoundOrVideoPlayer

from . import bridge


class MediaPlayerPlayer(SoundOrVideoPlayer):
    default_rank = 1

    def __init__(self, taskman: Any, media_folder: str) -> None:
        self._media_folder = media_folder
        self._on_done: OnDoneCallback | None = None
        bridge.listen("audioDone", lambda event: self._finished())

    def play(self, tag: AVTag, on_done: OnDoneCallback) -> None:
        assert isinstance(tag, SoundOrVideoTag)
        self._on_done = on_done
        bridge.call("audio.play", path=os.path.join(self._media_folder, tag.filename))
        gui_hooks.av_player_did_begin_playing(self, tag)

    def _finished(self) -> None:
        on_done, self._on_done = self._on_done, None
        if on_done is not None:
            on_done()

    def stop(self) -> None:
        # Anki's queue (aqt.sound.AVPlayer) only plays the next file once the
        # current player reports it is done, also after being stopped.
        bridge.call("audio.stop")
        on_done, self._on_done = self._on_done, None
        if on_done is not None:
            QTimer.singleShot(0, on_done)

    def toggle_pause(self) -> None:
        bridge.call("audio.pause")

    def seek_relative(self, secs: int) -> None:
        bridge.call("audio.seek", ms=secs * 1000)
