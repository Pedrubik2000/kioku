"""Card audio through AVFoundation, replacing Anki's mpv/mplayer players
(iOS cannot start processes)."""

from __future__ import annotations

import logging
import os
from typing import Any

from rubicon.objc import ObjCClass, at
from rubicon.objc.runtime import load_library

from .webview import prop

from anki.sound import AVTag, SoundOrVideoTag
from aqt import gui_hooks
from aqt.qt import QTimer
from aqt.sound import OnDoneCallback, SoundOrVideoPlayer

load_library("AVFoundation")

logger = logging.getLogger("kioku.audio")

AVAudioPlayer = ObjCClass("AVAudioPlayer")
AVAudioSession = ObjCClass("AVAudioSession")
NSURL = ObjCClass("NSURL")


def _activate_session() -> None:
    try:
        session = prop(AVAudioSession, "sharedInstance")
        # play even with the ring/silent switch on, like other study apps
        session.setCategory_error_(at("AVAudioSessionCategoryPlayback"), None)
        session.setActive_error_(True, None)
    except Exception:
        logger.exception("audio session")


class AVFoundationPlayer(SoundOrVideoPlayer):
    default_rank = 1

    def __init__(self, taskman: Any, media_folder: str) -> None:
        self._media_folder = media_folder
        self._player: Any = None
        self._on_done: OnDoneCallback | None = None
        self._timer = QTimer()
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._poll)
        _activate_session()

    def rank_for_tag(self, tag: AVTag) -> int | None:
        if isinstance(tag, SoundOrVideoTag):
            return self.default_rank
        return None

    def play(self, tag: AVTag, on_done: OnDoneCallback) -> None:
        assert isinstance(tag, SoundOrVideoTag)
        if self._player is not None:
            self._player.stop()
            self._player = None
        path = os.path.join(self._media_folder, tag.filename)
        url = NSURL.fileURLWithPath_(at(path))
        player = AVAudioPlayer.alloc().initWithContentsOfURL_error_(url, None)
        if player is None:
            logger.warning("cannot play %s", tag.filename)
            on_done()
            return
        self._player = player
        self._on_done = on_done
        player.play()
        gui_hooks.av_player_did_begin_playing(self, tag)
        self._timer.start()

    def _poll(self) -> None:
        if self._player is not None and not prop(self._player, "isPlaying"):
            if self._paused:
                return
            self._finish()

    _paused = False

    def _finish(self) -> None:
        self._timer.stop()
        self._player = None
        on_done, self._on_done = self._on_done, None
        if on_done is not None:
            on_done()

    def stop(self) -> None:
        # Anki's queue (aqt.sound.AVPlayer) only plays the next file once the
        # current player reports it is done, also after being stopped; the
        # desktop players (mpv, mplayer) report that asynchronously too.
        self._timer.stop()
        if self._player is not None:
            self._player.stop()
        self._player = None
        self._paused = False
        on_done, self._on_done = self._on_done, None
        if on_done is not None:
            QTimer.singleShot(0, on_done)

    def toggle_pause(self) -> None:
        if self._player is None:
            return
        if self._paused:
            self._player.play()
        else:
            self._player.pause()
        self._paused = not self._paused

    def seek_relative(self, secs: int) -> None:
        if self._player is not None:
            t = max(0.0, float(prop(self._player, "currentTime")) + secs)
            self._player.setCurrentTime_(t)
