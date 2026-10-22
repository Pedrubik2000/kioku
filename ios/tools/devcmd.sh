#!/bin/bash
# Run Python inside the running app (launched by run_device.sh) and print the
# output. With --shot, also fetch a screenshot to build/device-logs/screen.png.
# Usage: devcmd.sh [--shot] 'python code'   (or code on stdin)
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEV=${KIOKU_DEVICE:-$(xcrun devicectl list devices 2>/dev/null | grep physical \
    | grep -oE '[0-9A-F]{8}-[0-9A-F]{16}' | head -1)}
LOGDIR=$ROOT/build/device-logs
mkdir -p "$LOGDIR"
SHOT=0
if [ "${1:-}" = "--shot" ]; then SHOT=1; shift; fi
if [ $# -gt 0 ]; then CODE=$1; else CODE=$(cat); fi
if [ $SHOT = 1 ]; then CODE="$CODE
print('shot:', shot())"; fi
printf '%s\n' "$CODE" > "$LOGDIR/cmd.py"
copy() {
    xcrun devicectl device copy "$1" --device "$DEV" --domain-type appDataContainer \
        --domain-identifier io.ankidesk.kioku --source "$2" --destination "$3" > /dev/null 2>&1
}
rm -f "$LOGDIR/cmd.out"
copy from Documents/.kioku-cmd.out "$LOGDIR/old.out"   # clear stale output marker
# devicectl reads the file back after copying it and reports a failure when
# the app has already picked it up (and deleted it), so a failure here is
# not final: wait for the output either way
copy to "$LOGDIR/cmd.py" Documents/.kioku-cmd.py || echo "(copy reported a failure; waiting for output anyway)" >&2
for _ in $(seq 1 20); do
    sleep 1
    copy from Documents/.kioku-cmd.out "$LOGDIR/cmd.out"
    if [ -f "$LOGDIR/cmd.out" ] && ! cmp -s "$LOGDIR/cmd.out" "$LOGDIR/old.out" 2>/dev/null; then
        break
    fi
    rm -f "$LOGDIR/cmd.out"
done
cat "$LOGDIR/cmd.out" 2>/dev/null || echo "(no output)"
if [ $SHOT = 1 ]; then
    copy from Documents/screenshot.png "$LOGDIR/screen.png" && echo "screenshot: $LOGDIR/screen.png"
fi
