# How Kioku works

Kioku is set up like a small Linux distribution that boots into its desktop
(`init → display manager → session → desktop + apps`, restarted on failure):

```
LauncherActivity      splash: unpack progress, start-up status, errors + recovery
   │
AnkiService           supervisor (foreground service)
   ├─ unpack assets/bootstrap-aarch64.zip → file/usr    (first run, after updates, or if damaged)
   ├─ app_process … com.termux.x11.CmdEntryPoint :0     X server (termux-x11 "lorie")
   ├─ linker64 usr/bin/dash usr/libexec/ankidx/session.sh
   │     ├─ jwm                                         window manager, bottom dock
   │     ├─ python usr/share/ankidx/launch_anki.py      Anki, started with the session
   │     └─ python usr/share/ankidx/ankidesk_shell.py   the desktop; signals when it is up
   ├─ Power off → stop everything;  desktop/X crash → restart (max 2 in 3 min), then show the error
   └─ xdg-open requests → Android ACTION_VIEW
com.termux.x11.MainActivity   the display (touch → mouse or touch events, soft keyboard, extra keys)
HomeDocumentsProvider         file/home in Android's Files app (no bundled file manager)
```

If start-up fails, the splash shows the reason and the log tail with **Retry**,
**Safe mode** (Anki without add-ons), **Repair runtime** (unpack again, decks kept) and
**Share log**.

Logs on the device (`adb shell run-as io.ankidesk cat …` on a debug build):
`file/usr/tmp/x11.log`, `file/usr/tmp/session.log`, `file/usr/tmp/anki.log`.

## Where things live

The app's data directory is `/data/data/io.ankidesk`. Termux keeps its rootfs in `files/`;
Kioku keeps it in **`file/`** (see [Application id and the runtime](building.md#application-id-and-the-runtime)):

| Path | What |
|---|---|
| `file/usr` | the runtime (Termux prefix): Python, Qt, Anki, JWM, installed apps |
| `file/home` | everything that belongs to the user |
| `file/home/.local/share/Anki2` | Anki profiles, collections, media, backups, add-ons |
| `file/home/.config` | settings (`kioku/` for the desktop's own) |
| `file/home/Imports` | decks picked from the phone |
| `file/apps-to-restore.json` | apps to reinstall after a runtime update |

## Updates and user data

An app update or **Repair runtime** only replaces `file/usr`: the new runtime is unpacked into
`usr-staging` and swapped in with renames (the old one is moved aside first, so an interruption
never leaves neither), then the old one is deleted. `file/home` is never touched. Packages the
user installed are listed in `file/apps-to-restore.json` (merged with an unfinished earlier list)
and reinstalled by the next session; the list is kept until that succeeds.

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
