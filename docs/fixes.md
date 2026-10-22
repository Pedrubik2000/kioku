# Fixes log: running Anki desktop natively on iOS and Android

Every problem found while bringing the unmodified Anki desktop app (`aqt`) to
iOS (`ios/`) and native Android (`android/`), what caused it, and where the
fix lives. Newest at the bottom of each section. Add to this file whenever
something new is fixed.

Background: on these platforms `sys.platform` is `"ios"` / `"android"`, so
Anki takes its **Linux** code paths (`anki.utils.is_lin` is true). Most work;
the ones below assume a desktop OS (spawning processes, X11/D-Bus, system
libraries, a file manager, an unrestricted file system).

## Building

| Problem | Cause | Fix |
| --- | --- | --- |
| Qt download hangs forever | aqtinstall's default mirror (ftp.jaist.ac.jp) stalls | `QT_MIRROR` in `shared/versions.env` (Berkeley mirror) |
| iOS `qmake` fails with exit 127 | Qt's iOS `qmake` is a wrapper pointing at the build machine's path (`/Users/qt/work/install`) | `ios/tools/fetch_deps.sh` rewrites the wrappers and `target_qt.conf` to the downloaded macOS host Qt, on every run (the path breaks again if `deps/` moves) |
| No iOS Simulator builds on Apple silicon | Qt's prebuilt iOS libraries have only `arm64` (device) and `x86_64` (simulator) slices | Test on a device; `tools/run_device.sh` |
| PyQt6 fails to compile: DTLS, Vulkan, `QProcess` | Qt for iOS lacks them; PyQt's config tests can't run when cross-compiling | `--disabled-feature PyQt_DTLS/Process/Vulkan/XCB/Wayland` in `ios/tools/gen_pyqt.sh` |
| sip: `'QProcessEnvironment' is undefined` | PyQt 6.11 declares its comparison operators outside the `PyQt_Process` guard | `ios/patches/pyqt6-qprocess-guard.patch` |
| `no member named 'EnterEditFocus'` | dropped the `QT_KEYPAD_NAVIGATION` define from the generated `.pro` | keep every define from the `.pro` (`tools/gen_pyqt_cmake.py`) |
| pyo3: `attempted to link to Python shared library but config does not contain lib_name` | pyo3 wants to link libpython for iOS | config files in `ios/tools/pyo3/` with `suppress_build_script_link_lines=true`; the app links Python itself |
| orjson needs rustc 1.95 | newer than Anki's pinned toolchain | orjson builds with `+nightly` (`tools/build_rust.sh`) |
| `dyld: Library not loaded: @rpath/Python.framework` | no `LC_RPATH` | `LD_RUNPATH_SEARCH_PATHS=@executable_path/Frameworks` (CMakeLists) |
| `rsbridge and anki build hashes do not match` | rslib reads its build hash from `out/buildhash`, absent outside Anki's own build | `build_rust.sh` writes the release's commit hash (only when it changes, or the whole core rebuilds) |
| `sip module implements ABI v13.0 to v13.11 but … requires v13.13` | Anki pins PyQt6-sip 13.11; sip 6.17 generates ABI 13.13 | use PyQt6-sip 13.13 (`shared/versions.env`) |
| Several Rust static libraries in one binary | – | links fine (no duplicate-symbol clash) |
| Changing anything regenerated all PyQt sources (full rebuild) | – | `gen_pyqt.sh` skips when its inputs are unchanged |

## Runtime: Qt WebEngine replacement

Qt WebEngine (Chromium) cannot run on iOS and is not offered for Qt on
Android. `shared/python/PyQt6/QtWebEngine*.py` and `QtWebChannel.py` are
pure-Python stand-ins (`shared/python/kioku/webengine.py`) over the system web
view (`kioku_platform.WebView`: WKWebView on iOS, android.webkit.WebView on
Android).

| Problem | Cause | Fix |
| --- | --- | --- |
| `pycmd()` / web channel | no `qt.webChannelTransport` | `webscripts.PRELUDE` defines a `QWebChannel` whose calls go to Python through each backend's `__kiokuNative` bridge |
| Pages laid out at 980 px and shrunk | Anki pages have no viewport meta | injected viewport meta (`webscripts.VIEWPORT`) |
| API calls rejected by Anki's media server | Qt's request interceptor adds an `Authorization` header; WebKit has none | headers from the page's interceptor are added to fetch/XHR to 127.0.0.1 by an injected script, and to the main request |
| `setFixedHeight(float)` TypeError (toolbar) | WebKit returns every JS number as a double, Qt WebEngine whole numbers as ints | `runJavaScript` results go through `_qt_value()` |
| rubicon: `No type encoding known for ctype ObjCBlock` | block parameters of `objc_method` need the raw type | declare them `c_void_p`, wrap with `ObjCBlock(objc_id(ptr), None, *types)` (WebKit's blocks carry no signature) |
| rubicon: `'ObjCBoundMethod' has no attribute 'ptr'`; setters silently ignored | rubicon only treats a name as a property if the runtime declares it; many UIKit getters come back as methods | `prop(obj, name)` for reads, explicit `setFoo_()` calls for writes |
| `desktop dialogs: QWebEngineView.focusProxy()` asserted non-None | WebEngine's view has a focus-proxy child | `focusProxy()` returns the view |

## Runtime: platform

| Problem | Cause | Fix |
| --- | --- | --- |
| Crash at start: `libGL.so.1` | `aqt.setupGL()` loads it on Linux | `kioku/patches.py`: no-op |
| "Error during startup" in `theme_manager.apply_style()` | Linux dark-mode detection runs `dbus-send`/`gsettings` | `kioku_platform.dark_mode()` (UIKit trait collection on iOS) |
| Opening a folder ran a Linux file manager | `aqt.utils.openFolder` | `kioku_platform.open_folder()` (Files app via `shareddocuments://` on iOS) |
| Card audio used mpv/mplayer subprocesses | iOS/Android cannot start processes | `kioku_platform.audio_player()` (AVFoundation on iOS) |
| Windows (About, Browse, …) could not be closed and were wider than the screen | no window manager or title bars on a phone | `kioku/windows.py`: every top-level window fills the screen, gets a title bar with **‹ Back**, oversized minimum widths/combo boxes/labels are relaxed; message boxes are fitted and centred |
| Title bar hidden under the status bar | Qt merges user margins with the safe area by taking the larger | turn off `WA_ContentsMarginsRespectsSafeArea` on managed windows and add the safe area ourselves |
| Browse: sidebar took half the screen | desktop layout | hidden in portrait, **Sidebar** button in the title bar |
| Deck list cut off its Due column | `.decktd { min-width: 15em }` etc. | phone-width CSS in `webscripts.VIEWPORT` |
| Blank pages after returning from another app (e.g. importing a deck from Files) | iOS reclaims a backgrounded app's listening sockets; Anki's media server keeps running but refuses connections | `kioku/mediaserver.py`: checks the server when the app becomes active and when a local page fails, and serves again (same port, or a new one if it is still held); failed loads are retried once |
| Restarting the media server: `select(): Bad file descriptor` | closing the old server's sockets from the main thread raced with its loop thread (descriptors reused) | leave the old server alone and start a new one |
| `[Errno 1] Operation not permitted` reading a picked file (import, image occlusion, attachments) | a Files-app path is only readable through the security-scoped URL the picker returned | `aqt.utils.getFile` → `kioku_platform.pick_files()`: on iOS the document picker in copy mode, so files land in the app's tmp folder |
| Export dialogs | no usable save dialog | `aqt.utils.getSaveFile` → `Documents/Exports/<name>` (visible in Files) |
| HTTPS fails everywhere (add-on downloads, update check): `CERTIFICATE_VERIFY_FAILED` | Python's OpenSSL has no CA store on iOS; truststore (injected by Anki) picks its OpenSSL backend because `platform.system()` is `"iOS"` | `kioku_platform.prepare()` imports truststore while `platform` reports Darwin, so it uses Security.framework (same API on iOS) |
| Phone locks during testing and the app stops answering | a locked phone suspends the app | dev mode disables the idle timer |
| After one card's audio, no more audio plays | aqt's queue (`AVPlayer`) only starts the next file after the current player calls `on_done`, also after `stop()` (mpv/mplayer report it asynchronously); the iOS player dropped the callback when a card was flipped or answered mid-playback | `stop()` reports completion on the next event-loop turn (`ios/python/kioku_platform/audio.py`) |
| Some card audio is silent on iOS | AVAudioPlayer cannot decode Ogg/Opus | open: needs a decoder (e.g. via AVAudioEngine + libopus) |

## Add-ons

Results on iOS with Anki 26.8.1 (October 2026): see [testing.md](testing.md).

| Problem | Cause | Fix |
| --- | --- | --- |
| Some add-ons seemed not to load | one add-on (AnKing Note Types) opens a modal tutorial during start-up; the rest load when it is closed | nothing to fix |
| AnkiConnect requests time out when made from the main thread | AnkiConnect answers on the main thread | call it from another thread (as real clients do) |
