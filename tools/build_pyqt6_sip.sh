#!/bin/sh
# Cross-compile PyQt6.sip for Termux's Python with the Android NDK.
#
# Termux's pyqt6 package pip-installs PyQt6-sip from source in its postinst,
# which needs a compiler on the phone. Build it here instead and ship it as an
# overlay for tools/build_rootfs.py (--extra).
#
#   tools/build_pyqt6_sip.sh build/rootfs-repo/usr 3.14 build/pyqt6-sip-overlay
set -eu

PREFIX_TREE="${1:?prefix tree containing include/pythonX.Y and lib/libpythonX.Y.so}"
PYVER="${2:?python version, e.g. 3.14}"
OUT="${3:?output overlay dir}"
SIP_VERSION="${SIP_VERSION:-13.12.0}"
API="${ANDROID_API:-24}"
NDK="${ANDROID_NDK:-$HOME/Library/Android/sdk/ndk/30.0.14904198}"

CC="$(ls -d "$NDK"/toolchains/llvm/prebuilt/*/bin | head -1)/clang"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 -m pip download --quiet --no-deps --no-binary :all: "PyQt6-sip==$SIP_VERSION" -d "$WORK"
tar xzf "$WORK"/pyqt6_sip-"$SIP_VERSION".tar.gz -C "$WORK"
SRC="$WORK/pyqt6_sip-$SIP_VERSION"

SITE="$OUT/lib/python$PYVER/site-packages"
mkdir -p "$SITE/PyQt6"
TAG="cpython-$(echo "$PYVER" | tr -d .)"
# Termux Python only loads extensions with its full platform suffix.
SUFFIX="$TAG-aarch64-linux-android"
# Android's linker, unlike glibc's, needs extensions to link libpython.
"$CC" --target="aarch64-linux-android$API" -shared -fPIC -O2 \
	-I"$PREFIX_TREE/include/python$PYVER" -I"$SRC" \
	"$SRC"/*.c -L"$PREFIX_TREE/lib" -lpython"$PYVER" \
	-o "$SITE/PyQt6/sip.$SUFFIX.so"
"$(dirname "$CC")/llvm-strip" "$SITE/PyQt6/sip.$SUFFIX.so"

DIST="$SITE/pyqt6_sip-$SIP_VERSION.dist-info"
mkdir -p "$DIST"
printf 'Metadata-Version: 2.1\nName: PyQt6-sip\nVersion: %s\n' "$SIP_VERSION" > "$DIST/METADATA"
printf 'Wheel-Version: 1.0\nGenerator: kioku\nRoot-Is-Purelib: false\nTag: %s-%s-android_%s_arm64_v8a\n' \
	"$(echo "$TAG" | sed 's/cpython-/cp/')" "$(echo "$TAG" | sed 's/cpython-/cp/')" "$API" > "$DIST/WHEEL"
printf 'pip\n' > "$DIST/INSTALLER"
echo "built $SITE/PyQt6/sip.$SUFFIX.so"
