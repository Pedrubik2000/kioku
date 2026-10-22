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

## Results: Android

Not run yet.
