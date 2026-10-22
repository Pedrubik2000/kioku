# Kioku on kuma3-anki-core (RWKV on the phone)

This fork builds the native Android variant on top of
[kuma3-anki-core](https://github.com/Pedrubik2000/kuma3-anki-core) instead of
upstream Anki. That repo is the whole Anki tree (the JSchoreels FSRS-7 fork plus
kuma3's changes), and its desktop `aqt` already schedules with RWKV through the
Rust core (`_rsbridge.RwkvInference`, no PyTorch needed; the model ships inside
the `aqt` wheel). So Kioku + that core = desktop Anki with RWKV, on a phone,
with no Kioku code changes beyond the build.

What changed here:

- `shared/versions.env`: `ANKI_REPO` (new), `ANKI_TAG=kuma3-21`,
  `ANKI_PY_VERSION=26.9.3+fsrs7`.
- `android/tools/fetch_deps.sh` clones `$ANKI_REPO` at `$ANKI_TAG`.
- `shared/tools/prepare_site.sh`: `ANKI_WHEELS=<dir>` points pip at locally built
  `anki`/`aqt` wheels (the fork is not on PyPI). Build them in a checkout of the
  core at the same commit with `./ninja wheels`; the build hash in the `anki`
  wheel must match `deps/anki`'s HEAD or `rsbridge` refuses to load.
- `android/patches/qtforandroid-disable-accessibility.patch` + `android/src/main.cpp`:
  `QT_ANDROID_DISABLE_ACCESSIBILITY=1` keeps Qt's Android accessibility bridge
  inert. With an accessibility service enabled (a screen reader, a screen
  mirroring tool) that bridge blocks Android's UI thread on Qt's thread, which
  deadlocked against Kioku's Java bridge (`webview.title` on every page load)
  and then aborted in Qt's deadlock protector while creating a GL surface. The
  web views keep Android's own accessibility.
- `KiokuBridge.java`: `webview.url` / `webview.title` answer from values cached
  by the web clients instead of waiting for the UI thread.
- `shared/python/kioku/devtools.py`: `Documents/.kioku-stack` dumps every
  thread's Python stack to `.kioku-stack.out` (dev builds), for hangs like the
  one above.
- `shared/python/kioku/__main__.py`: `Documents/.kioku-debug` turns on debug
  logging (the RWKV scheduler's timings).

Build (Linux or WSL): the usual `android/tools/build.sh` with `ANKI_WHEELS`,
`PROTOC`, `ANDROID_NDK_ROOT` set; NDK 29 works too.
