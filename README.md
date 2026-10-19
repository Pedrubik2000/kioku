# Kioku: Anki desktop for Android

Runs the real Anki desktop app (Qt 6 + Qt WebEngine, built for Termux) on Android as a
normal app: tap the Kioku icon and a small Linux desktop starts with Anki open.
No Termux, no Termux:X11, no setup. (Kioku, 記憶, is Japanese for "memory".)

## How it works

It is set up like a small Linux distribution that boots into its desktop
(`init → display manager → session → desktop + apps`, restarted on failure):

```
LauncherActivity      splash: unpack progress, start-up status, errors + recovery
   │
AnkiService           supervisor (foreground service)
   ├─ unpack assets/bootstrap-aarch64.zip → files/usr   (first run, after updates, or if damaged)
   ├─ app_process … com.termux.x11.CmdEntryPoint :0     X server (termux-x11 "lorie")
   ├─ linker64 usr/bin/dash usr/libexec/ankidx/session.sh
   │     ├─ jwm                                         window manager, bottom dock
   │     ├─ python usr/share/ankidx/launch_anki.py      Anki, started with the session
   │     └─ python usr/share/ankidx/ankidesk_shell.py   the desktop; signals when it is up
   ├─ Power off → stop everything;  desktop/X crash → restart (max 2 in 3 min), then show the error
   └─ xdg-open requests → Android ACTION_VIEW
com.termux.x11.MainActivity   the display (touch → mouse, soft keyboard, extra keys)
HomeDocumentsProvider         files/home in Android's Files app (no bundled file manager)
```

If start-up fails, the splash shows the reason and the log tail with **Retry**,
**Safe mode** (Anki without add-ons), **Repair runtime** (unpack again, decks kept) and
**Share log**.

## Desktop and apps

The desktop (`rootfs-overlay/share/ankidx/ankidesk_shell.py`, PyQt6, no extra size) is styled
after Cutefish and Deepin: wallpaper on the home page, solid dark pages for Software and Settings,
one blue accent, gradient "squircle" app icons drawn from SVG (`ankidesk_theme.py`). It sits below
every window; the Kioku button in the dock minimizes the windows to show it. Closing Anki returns
to the desktop, where the Anki icon opens it again; **Settings → Power off** closes Anki (which
saves the collection) and ends the session. In landscape the page bar becomes a rail on the left
and the dock moves to the right edge (window buttons show icons only).

* **Apps**: clock, search, Anki, Terminal (`st`) and every installed app, with icons from their
  `.desktop` files.
* **Software**: recommended native Linux apps (Files 8 MB, Text Editor 4 MB, QTerminal 3 MB, Web
  Browser/Falkon 49 MB, Image Viewer 6 MB, Archives 7 MB, System Monitor 1 MB) and a search over
  every package in the Termux repositories (main and x11). Apps appear in Apps once installed;
  command-line packages open in a terminal. After an app update the runtime is replaced and they
  are reinstalled automatically.
* **Settings**: wallpaper (six built in, or any picture from Android's gallery or the home
  folder), touch screen or mouse pad (the current one is marked), keyboard, import a deck from
  the phone, phone storage, display settings, app info, restart desktop, power off.

Installed apps are started with Anki's scale (`QT_SCALE_FACTOR`, `GDK_SCALE`) and as if in KDE,
so Qt reads `~/.config/kdeglobals` (`ankidesk_theme.py`): a dark palette like the desktop's and
items that open with one tap. PCManFM-Qt gets single-click in its own settings. The session has a
D-Bus session bus (single-instance apps such as PCManFM-Qt exit without one) and
`XDG_DATA_DIRS`/`XDG_CONFIG_DIRS` pointing into the prefix (icon themes, `.desktop` files). The
file-based apps install `adwaita-icon-theme-legacy` (2 MB) with them for file and folder icons.

The installer (`ankidesk_pkg.py`, also `ankidesk-pkg install|remove|list|search` in a terminal)
resolves dependencies against the bundled packages, checks SHA256, unpacks into the prefix and
rewrites the Termux path; it does not run maintainer scripts, so a few command-line packages may
need extra steps.

Window manager: JWM. Main windows maximized, dialogs centered/on top with a close button, bottom
dock (desktop, open windows, keyboard, clock), flat with no gradients and no hover tooltips.
`~/.jwmrc` is generated from `share/ankidx/jwmrc` with the chosen wallpaper and the dock for the
current orientation. Turning the phone restarts JWM with the other dock; JWM forgets which windows
were maximized or minimized on a restart and when the screen size changes, so the desktop samples
the window states and puts them back. Qt is scaled so the short side of the screen is ~480
logical pixels.

Touch (`ankidesk_touch.py`, used by the desktop and Anki): in touch-screen mode a finger drag
arrives as a held mouse button; dragging in a page, list or web view scrolls it with momentum
(web views through a script) instead of selecting, and the tap at its end is dropped. Windows
whose desktop-sized minimum would not fit the phone (e.g. Anki's About) are shrunk to the
screen, file dialogs fill it and open folders with one tap. In mouse-pad mode one finger moves
the pointer and two fingers scroll.

Keyboard: text fields open the Android keyboard and tapping elsewhere closes it; tapping a field
again reopens it after it was closed with Back. Anki and the desktop follow Qt's focus and taps
(`ankidesk_keyboard.py`, plus a script in Anki's web views). For other apps the desktop watches
taps (XInput2 raw events) and opens the keyboard when the pointer then is a text cursor (I-beam),
e.g. in a terminal (`ankidesk_x11.py`).

Cursors: no cursor theme is bundled, so `ankidesk_cursors.py` draws a large "kioku" Xcursor theme
on first start, and the display draws 16 px core cursors (JWM, `st`) three times larger.

## Phone files

* **Import a deck**: Settings → Import a deck from the phone, or Import in Anki (it asks
  "Phone storage" or "Kioku files"), opens Android's file picker. Kioku also offers itself for
  opening or sharing `.apkg`/`.colpkg` files from other apps. The file is copied to `~/Imports`
  (`PickFileActivity`), and the desktop hands it to Anki through Anki's single-instance socket
  (`ANKI_SINGLE_INSTANCE_KEY=kioku-anki`), or starts Anki with it.
* **Phone storage**: like `termux-setup-storage`. Settings → Phone storage (also offered when
  Files opens for the first time) asks for Android's all-files access and links
  `~/storage/{shared,downloads,documents,dcim,pictures,music,movies}`, with bookmarks for
  PCManFM-Qt (`StorageActivity`). Tapping it again turns it off.
* **Nothing is deleted on the phone's storage**: before the runtime is replaced or repaired and
  before packages are removed, phone storage is turned off (only the links in `~/storage` are
  removed). Deleting never follows links, skips anything under `/storage`, `/sdcard` and `/mnt`,
  and the documents provider (`HomeDocumentsProvider`) does not list the links.

## Updates and user data

Everything that belongs to the user lives in `files/home`: Anki's profiles, collections, media,
backups and add-ons (`~/.local/share/Anki2`), settings (`~/.config`), imports. An app update or
**Repair runtime** only replaces `files/usr`: the new runtime is unpacked into `usr-staging` and
swapped in with renames (the old one is moved aside first, so an interruption never leaves
neither), then the old one is deleted. Packages the user installed are listed in
`files/apps-to-restore.json` (merged with an unfinished earlier list) and reinstalled by the next
session; the list is kept until that succeeds.

## Application id and the runtime

Termux binaries hardcode `/data/data/<package>/files/usr`, so the runtime must be built for
the app's id (`ankideskApplicationId` in `gradle.properties`):

| id | runtime | status |
|---|---|---|
| `io.krmanik.ankidesk` | packages rebuilt with `TERMUX_APP__PACKAGE_NAME=io.krmanik.ankidesk` | release target |
| `io.krmanik` | official Termux packages; same length as `com.termux`, so the path is rewritten in place | development |

Termux limits the package name to 33 characters (21 recommended) because of Unix socket
(108) and shebang (127) path limits.

## Size

| | |
|---|---|
| Typical Termux install used to build/run Anki | ~3.4 GB |
| Anki runtime closure (dpkg) | ~1.1 GB |
| Bundled prefix after pruning | ~625 MB |
| `bootstrap-aarch64.zip` in the APK | ~230 MB |

Pruned: headers, static libs, docs, translations other than English for WebEngine, Qt tools,
perl, mesa + LLVM (Qt and Chromium run without OpenGL), gstreamer.

## Build

Requirements: Android SDK, NDK `30.0.14904198` (see `gradle.properties`), JDK 21, Python 3.

```sh
git submodule update --init third_party/termux-x11
git -C third_party/termux-x11 apply ../../patches/termux-x11.patch
git -C third_party/termux-x11 submodule update --init --depth 1
# macOS only, see below
(cd third_party/termux-x11/lorie/src/main/cpp && for p in pixman:pixman xkbcomp:xkbcomp \
    libxkbfile:xkbfile libx11:x11 libxtrans:Xtrans xserver:xserver libepoxy:libepoxy; do
    patch -p1 -N -d "${p%%:*}" -i "$PWD/patches/${p##*:}.patch" </dev/null; done)

# Runtime: Termux packages (+ local-debs/ from krmanik/termux-packages), cross-compiled
# PyQt6.sip, pure-Python deps (tools/python-requirements.txt), pruned and zipped.
tools/build_bootstrap.sh

./gradlew :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

For the release id, build the packages on x86_64 Linux with
`tools/build-termux-packages.sh ~/termux-packages`, copy the resulting .debs to `local-debs/`, set
`ankideskApplicationId=io.krmanik.ankidesk` and run
`SOURCE_PACKAGE=io.krmanik.ankidesk tools/build_bootstrap.sh`.

Logs on the device: `files/usr/tmp/x11.log`, `files/usr/tmp/session.log`, `files/usr/tmp/anki.log`.

## Known gaps in the Termux packages

* `pyqt6` installs `PyQt6-sip` with pip in its postinst (compiling it on the phone);
  `tools/build_pyqt6_sip.sh` cross-compiles it instead. `python-pyqt6-sip` from
  krmanik/termux-packages would replace this once it is in the repositories.
* `pyqt6` is built without the QtQuick bindings and Qt's OpenGL classes. Anki imports both but
  only uses them for GPU selection; `launch_anki.py` provides stand-ins.

## Local changes to third-party code

Kept in `patches/termux-x11.patch`; apply with `git -C third_party/termux-x11 apply ../../patches/termux-x11.patch`.

* `third_party/termux-x11/lorie/version.gradle`: NDK version can be overridden with the
  `termuxX11NdkVersion` Gradle property.
* `third_party/termux-x11/lorie/src/main/cpp/lorie/renderer.cpp`: core cursors (≤ 32 px) are
  drawn three times larger.
* `third_party/termux-x11/lorie/src/main/cpp/recipes/xkbcomp.cmake`: a `case-compat` include
  dir with bionic's `xlocale.h`, which on case-insensitive filesystems (macOS) otherwise
  resolves to libX11's `X11/Xlocale.h`.
* termux-x11 applies its submodule patches at CMake configure time with
  `patch -R --dry-run || patch …`. Apple's `/usr/bin/patch` exits 0 on a failed reverse dry run,
  so on macOS nothing gets patched (`'GL/gl.h' file not found`); apply them by hand as above.

## Distribution

* **Google Play**: possible for Anki itself: everything ships in the app bundle; the runtime goes
  into an install-time asset pack (≤ 1.5 GB per pack). Targets API 36. Executing bundled binaries
  relies on the system linker, as the Play build of Termux does. The Software page downloads
  executable code, which Play's policy forbids outside Play; a Play build would have to ship the
  optional apps as on-demand asset packs or leave that page out.
* **F-Droid**: would have to build all Termux packages, including Qt WebEngine, from source.
  GitHub Releases or a self-hosted F-Droid repo are simpler.

## Licenses

Anki is AGPL-3.0, termux-x11 and the Termux packages are GPL-3.0 and others. Distributing the APK
means offering the corresponding source. "Anki" is a trademark of Ankitects, hence the app's own
name, Kioku.
