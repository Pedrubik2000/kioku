#!/bin/sh
# Download the pure-Python dependencies pinned in tools/python-requirements.txt
# and unpack them into an overlay for tools/build_rootfs.py (--extra).
#
#   tools/fetch_python_deps.sh 3.13 build/python-deps
set -eu

PYVER="${1:?python version, e.g. 3.13}"
OUT="${2:?output dir}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WHEELS="$OUT.wheels"

rm -rf "$OUT" "$WHEELS"
mkdir -p "$WHEELS" "$OUT/lib/python$PYVER/site-packages"

# Pure wheels only: these run unchanged on Android. Anything compiled must come
# from a Termux package instead.
python3 -m pip download --quiet --no-deps --only-binary=:all: \
	--platform any --implementation py --python-version "$PYVER" \
	-r "$HERE/python-requirements.txt" -d "$WHEELS"

for whl in "$WHEELS"/*.whl; do
	python3 -I -m zipfile -e "$whl" "$OUT/lib/python$PYVER/site-packages"
done
echo "$(ls "$WHEELS" | wc -l | tr -d ' ') wheels -> $OUT/lib/python$PYVER/site-packages"
