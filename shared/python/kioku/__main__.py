"""Kioku entry point (iOS and native Android): prepare the environment, patch
the few places where Anki assumes a desktop OS, then run the unmodified Anki
desktop app."""

import io
import logging
import os
import sys
import traceback

import kioku_platform as platform

HOME = os.path.expanduser("~")
DOCUMENTS = platform.documents_dir()
LOG_PATH = os.path.join(DOCUMENTS, "kioku.log")


class _Tee(io.TextIOBase):
    """Send output to both the system log and Documents/kioku.log."""

    def __init__(self, stream, log):
        self._stream = stream
        self._log = log

    def write(self, text):
        try:
            self._stream.write(text)
        except Exception:
            pass
        try:
            self._log.write(text)
            self._log.flush()
        except Exception:
            pass
        return len(text)

    def flush(self):
        try:
            self._stream.flush()
        except Exception:
            pass

    @property
    def encoding(self):
        return "utf-8"

    def isatty(self):
        return False


def _setup_logging() -> None:
    os.makedirs(DOCUMENTS, exist_ok=True)
    log = open(LOG_PATH, "w", encoding="utf-8", buffering=1)
    sys.stdout = _Tee(sys.stdout, log)
    sys.stderr = _Tee(sys.stderr, log)
    # Documents/.kioku-debug: debug-level logging (e.g. the RWKV scheduler's timings)
    debug = os.path.exists(os.path.join(DOCUMENTS, ".kioku-debug"))
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )


def _setup_environment() -> None:
    # Anki keeps its data in $XDG_DATA_HOME/Anki2
    os.environ.setdefault("XDG_DATA_HOME", DOCUMENTS)
    os.environ.setdefault("XDG_CONFIG_HOME", platform.config_dir())
    os.environ.setdefault("XDG_CACHE_HOME", platform.cache_dir())
    os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
    os.environ.setdefault("LANG", "en_US.UTF-8")
    # The small RWKV model (shared/python/kioku/rwkv/), for the bridge built with
    # the small engine (android/patches/anki-rsbridge-rwkv-small.patch)
    small_model = os.path.join(os.path.dirname(__file__), "rwkv", "model-small.bin")
    if os.path.exists(small_model):
        os.environ.setdefault("ANKI_RWKV_MODEL_PATH", small_model)


def main() -> None:
    _setup_logging()
    _setup_environment()
    print(f"Kioku: Python {sys.version} on {sys.platform}")
    try:
        platform.prepare()
        from kioku import patches

        patches.apply()
        import aqt

        aqt.run()
    except SystemExit:
        raise
    except BaseException:
        traceback.print_exc()
        raise


main()
