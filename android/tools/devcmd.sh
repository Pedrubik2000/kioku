#!/bin/bash
# Run Python inside the running app (launched by run_device.sh) and print the
# output. With --shot, also save a screenshot to build/device-logs/screen.png.
# Usage: devcmd.sh [--shot] 'python code'   (or code on stdin)
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
ADB=${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/Library/Android/sdk}}/platform-tools/adb
DOCS=/sdcard/Android/data/io.ankidesk.kioku/files
LOGDIR=$ROOT/build/device-logs
mkdir -p "$LOGDIR"
SHOT=0
if [ "${1:-}" = "--shot" ]; then SHOT=1; shift; fi
if [ $# -gt 0 ]; then CODE=$1; else CODE=$(cat); fi
printf '%s\n' "$CODE" > "$LOGDIR/cmd.py"
"$ADB" shell rm -f $DOCS/.kioku-cmd.out
"$ADB" push "$LOGDIR/cmd.py" $DOCS/.kioku-cmd.py > /dev/null || { echo "push failed"; exit 1; }
rm -f "$LOGDIR/cmd.out"
for _ in $(seq 1 40); do
    sleep 0.5
    "$ADB" pull $DOCS/.kioku-cmd.out "$LOGDIR/cmd.out" > /dev/null 2>&1 && break
done
cat "$LOGDIR/cmd.out" 2>/dev/null || echo "(no output)"
if [ $SHOT = 1 ]; then
    sleep 0.5
    "$ADB" exec-out screencap -p > "$LOGDIR/screen.png" && echo "screenshot: $LOGDIR/screen.png"
fi
