# Testing the native variants

## How

Both native variants have a development mode (`KIOKU_DEV=1`, set by the run
scripts) with a command channel into the running app
(`shared/python/kioku/devtools.py`):

- `ios/tools/run_device.sh` builds, installs and launches on a connected
  iPhone (`KIOKU_TEAM=<team id>` for signing) and prints the app's log.
- `ios/tools/devcmd.sh [--shot] 'python'` runs Python inside the app (with
  `mw`, `aqt`, `shot()`, `widgets()`) and prints its output; `--shot` also
  fetches a screenshot (web views included).
- `ios/tools/sweep.sh` opens every main window and reports widgets that run
  off the screen.

Code run through `devcmd.sh` runs on the main thread: anything that waits for
the main thread (AnkiConnect requests, for example) has to run in a
`threading.Thread`.

Test collections: real desktop profiles exported with Anki 26.8.1's own
library (`export_collection_package`) from an APFS clone (`cp -c`) of the
profile folder, so the desktop data is never opened, pushed with
`xcrun devicectl device copy to … Documents/Import/` and imported with
`aqt.import_export.importing.ColpkgImporter._import(mw, path)`.

## Results: iOS (iPhone 15 Pro Max, iOS 26, Anki 26.8.1)

Collections: 41, 602, 61,199 and 258,430 cards (27k media files) imported,
card and review counts identical to the desktop.

| Area | Result |
| --- | --- |
| Start-up, profiles, switching profiles | works |
| Deck list (258k cards) | works; fits the screen |
| Reviewing: question, answer, answer buttons, intervals, revlog written | works |
| Card audio (mp3) | works, including interrupting and the next card |
| Card audio (ogg/opus) | not supported yet |
| Statistics (new stats page, charts, calendar) | works |
| Statistics: Save PDF | not implemented |
| Browse | works; sidebar behind a title bar button in portrait |
| Add, editor | works |
| Image occlusion: mask editor with an image | works (masks need touch testing) |
| Image occlusion / import / attachments: choosing a file | fixed (document picker in copy mode); needs a hand test |
| Import .colpkg | works |
| Export | writes to Documents/Exports |
| Preferences, Note Types, Deck Options, Filtered Deck, Study Deck, Add-ons, About | open, fit the screen, close with ‹ Back |
| HTTPS (add-on downloads) | works after the truststore fix |
| AnkiWeb sync | not tested yet |

Popups (shared code, after the Android round): the AnkiWeb login is a card
above the keyboard (iOS reports the keyboard in points, as assumed);
closing it and opening another window with the keyboard up works.

### Add-ons

Installed from AnkiWeb inside the app; all 15 load without errors.

| Add-on | Code | Result |
| --- | --- | --- |
| AnkiConnect | 2055492159 | works: HTTP API on 127.0.0.1:8765 answers (version, deckNames, findCards) |
| Review Heatmap | 1771074083 | works: heatmap on the deck list (slightly wider than a phone screen) |
| Anki Simulator | 817108664 | opens; rendering to check |
| AnKing Note Types Easy Customization | 952691989 | loads, menu works; shows a tutorial at start-up |
| Advanced Browser | 874215009 | loads; to check |
| Fill the blanks | 1933645497 | loads; to check |
| Colorful Tags / Hierarchical Tags | 594329229 | loads; to check |
| Customize Keyboard Shortcuts | 24411424 | loads |
| Edit Field During Review Cloze | 385888438 | loads; to check |
| Speed Focus Mode | 1046608507 | loads |
| True Retention | 613684242 | loads; to check |
| HyperTTS | 111623432 | loads; its configuration window did not appear: to check |
| AnkiWebView Inspector | 31746032 | loads; needs Qt WebEngine dev tools, expected not to work (use Safari's Web Inspector instead: web views are inspectable) |
| Color Confirmation | 1084228676 | works (answer confirmation popup) |
| Japanese Support | 3918629684 | loads; Kanji Stats did not open, and readings use MeCab as a subprocess, which iOS forbids: to check |

AnkiWeb returned 404 for 516643804, 2091361802 and 1572969437 (codes no
longer published).

## Results: Android (emulator, Android 17 arm64, 16 KB pages, Anki 26.8.1)

Android has the same tools: `android/tools/run_device.sh` (build, install,
launch in dev mode, print the log; `KIOKU_NO_BUILD=1` reinstalls the last
build), `devcmd.sh [--shot] 'python'` (screenshots with `adb screencap`) and
`sweep.sh`. Collections are pushed with
`adb push … /sdcard/Android/data/io.ankidesk.kioku/files/Import/`.

Emulator: start it with `emulator -avd Medium_Phone -gpu swiftshader_indirect
-feature GLESDynamicVersion`. With `-gpu host` on a Mac it offers only OpenGL
ES 3.0, and WebView aborts the app on pages with embedded video (see
docs/fixes.md).

Collections: the same 41, 602, 61,199 and 258,430-card profiles imported,
counts identical to the desktop.

| Area | Result |
| --- | --- |
| Start-up, profiles, switching profiles | works |
| Menu bar | works (drawn as a widget) |
| Back key | closes the top window; on the main window moves the app to the background |
| Background and resume | works; no error dialog |
| Deck list (258k cards) | works |
| Reviewing: question, answer, answer buttons, revlog written | works |
| Card audio: mp3, wav, ogg (Vorbis), opus | works, Anki's queue gets "done" for each |
| Statistics (new stats page, charts, calendar) | works |
| Statistics: Save PDF | works (5-page PDF in Exports/) |
| Browse, sidebar, notes with embedded YouTube video | works (emulator: needs the ES 3.1 setting above) |
| Add, editor | works (note added through the Add window) |
| Import .colpkg | works |
| Export (.apkg) | writes to Exports/ in the app's external files folder |
| About, Browse, Add, Statistics, Preferences, Note Types, Deck Options, Filtered Deck, Study Deck, Empty Cards, Export, Add-ons | open full screen, nothing wider than the screen (`sweep.sh`, also after the small-dialog change) |
| HTTPS (add-on downloads) | works after the CA bundle fix |
| Image occlusion / file picking | system picker opens; needs a hand test |
| AnkiWeb sync (User 4) | works: login, full sync (download, 39,754 cards), media sync; still logged in after a force-stop and restart |
| Popups: AnkiWeb login, rename prompt, message boxes | bordered card sized to its content; above the keyboard while typing |
| Top bar height over 5 cold starts | 34 px each time (the retry was needed in 2 of 5) |
| AnkiWeb login: OK tapped with the keyboard up, error box follows | works (5 of 5); crashed before the Qt plugin patch |
| Samsung M30s (Android 11, real device) | start-up, `sweep.sh` (all windows full screen), login card above the keyboard, OK with the keyboard up |

### Add-ons (Android)

All 15 installed from AnkiWeb inside the app and load without errors.

| Add-on | Result |
| --- | --- |
| AnkiConnect | works: version 6, deckNames (252 decks) |
| Review Heatmap | works: heatmap drawn on the deck list (366 day cells) |
| Anki Simulator | opens |
| AnKing Note Types Easy Customization | loads, AnKing menu; shows a tutorial at start-up (add-on loading waits until it is closed, as on the desktop) |
| Advanced Browser | loads (its modules are active in Browse) |
| Fill the blanks | loads |
| Colorful Tags / Hierarchical Tags | loads; sidebar works |
| Customize Keyboard Shortcuts | loads (logs a deprecation warning for `tr(TR.…)`) |
| Edit Field During Review Cloze | works (its EFDRC script is in the card page) |
| Speed Focus Mode | loads |
| True Retention | works: its rows in the legacy statistics window (Shift+Stats) |
| HyperTTS | works: configuration window opens; editor buttons shown |
| AnkiWebView Inspector | loads; needs Qt WebEngine dev tools (use chrome://inspect: web views are debuggable) |
| Color Confirmation | works (popup after answering) |
| Japanese Support | works: Kanji Stats opens with statistics; MeCab readings to check |
