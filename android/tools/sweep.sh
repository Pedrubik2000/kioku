#!/bin/bash
# Open each Anki window in the running app (run_device.sh), screenshot it and
# report widgets that do not fit on the screen.
# Usage: sweep.sh [name ...]   names: see opener() below
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=$ROOT/build/device-logs/sweep
mkdir -p "$OUT"
opener() {
  case $1 in
    about) echo "mw.onAbout()" ;;
    browse) echo "mw.onBrowse()" ;;
    add) echo "mw.onAddCard()" ;;
    stats) echo "mw.onStats()" ;;
    prefs) echo "mw.onPrefs()" ;;
    notetypes) echo "mw.onNoteTypes()" ;;
    filtered) echo "mw.onCram()" ;;
    studydeck) echo "mw.onStudyDeck()" ;;
    emptycards) echo "mw.onEmptyCards()" ;;
    export) echo "mw.onExport()" ;;
    addons) echo "mw.addonManager.onAddonsDialog()" ;;
    deckoptions) echo "import aqt.deckoptions; aqt.deckoptions.display_options_for_deck_id(mw.col.decks.get_current_id())" ;;
    checkdb) echo "mw.onCheckDB()" ;;
  esac
}
NAMES=${*:-about browse add stats prefs notetypes filtered studydeck emptycards export addons deckoptions}
CLOSE='
from PyQt6.QtWidgets import QApplication
for w in QApplication.topLevelWidgets():
    if w is not mw and w.isVisible() and w.isWindow():
        w.close()
'
REPORT='
from PyQt6.QtWidgets import QApplication, QWidget
W = QApplication.primaryScreen().availableGeometry().width()
for top in QApplication.topLevelWidgets():
    if top is mw or not top.isVisible():
        continue
    print("window", type(top).__name__, top.geometry().getRect(), repr(top.windowTitle()))
    for w in [top] + top.findChildren(QWidget):
        if not w.isVisible():
            continue
        p = w.mapToGlobal(w.rect().topLeft())
        if p.x() + w.width() > W + 1 or p.x() < -1:
            print("  overflow", type(w).__name__, repr(w.objectName()), p.x(), w.width(), "min", w.minimumWidth(), "hint", w.sizeHint().width())
'
for n in $NAMES; do
  echo "=== $n"
  "$ROOT/tools/devcmd.sh" "$CLOSE
$(opener $n)" | grep -v '^$' | head -5
  sleep 4
  "$ROOT/tools/devcmd.sh" --shot "$REPORT" | grep -v '^screenshot' | head -25
  cp "$ROOT/build/device-logs/screen.png" "$OUT/$n.png" 2>/dev/null
done
"$ROOT/tools/devcmd.sh" "$CLOSE" > /dev/null
