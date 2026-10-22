#!/bin/bash
# Take the README screenshots in the running app (launched by the variant's
# run_device.sh, dev mode): deck list, each deck's review question and answer,
# Browse, Statistics and Add. Nothing is answered or changed.
# Usage: readme_shots.sh <ios|android> <slug>=<deck name> ...
#   e.g. readme_shots.sh android hanzi="Anki xiehanzi::HSK 1::Recognition"
# Env: KIOKU_SHOT_WAIT  multiplies the waits (the iPhone's channel is slower)
#      KIOKU_SHOT_DIR   output folder (default docs/images)
set -uo pipefail
SHARED=$(cd "$(dirname "$0")/.." && pwd)
VARIANT=$1
shift
OUT=${KIOKU_SHOT_DIR:-$SHARED/../docs/images}
DEVCMD=$SHARED/../$VARIANT/tools/devcmd.sh
SCREEN=$SHARED/../$VARIANT/build/device-logs/screen.png
mkdir -p "$OUT"

CLOSE='
from PyQt6.QtWidgets import QApplication
for w in QApplication.topLevelWidgets():
    if w is not mw and w.isVisible() and w.isWindow():
        w.close()
'
shot() {  # shot <name> <seconds to wait> <python>
    "$DEVCMD" "$CLOSE
$3" > /dev/null
    sleep $(( $2 * ${KIOKU_SHOT_WAIT:-1} ))
    "$DEVCMD" --shot 'pass' > /dev/null
    cp "$SCREEN" "$OUT/$VARIANT-$1.png" && echo "$OUT/$VARIANT-$1.png"
}

shot decks 4 'mw.moveToState("deckBrowser")'
for deck in "$@"; do
    slug=${deck%%=*}
    name=${deck#*=}
    shot "review-$slug-question" 5 "mw.col.decks.select(mw.col.decks.id_for_name('$name')); mw.moveToState('review')"
    shot "review-$slug-answer" 5 'mw.reviewer._showAnswer()'
done
shot browse 6 'mw.moveToState("deckBrowser"); import aqt; aqt.dialogs.open("Browser", mw)'
shot stats 7 'mw.onStats()'
shot add 5 'mw.onAddCard()'
"$DEVCMD" "$CLOSE
mw.moveToState('deckBrowser')" > /dev/null
