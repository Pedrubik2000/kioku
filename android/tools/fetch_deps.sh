#!/bin/bash
# Download everything the native Android build needs into android/deps
# (skipping what is already there) and set up the host Python venv with sip.
#   deps/qt/<ver>/{android_arm64_v8a,<host>}  Qt for Android and its host tools
#   deps/python-android                       python.org's Android package
#   deps/anki                                 Anki source (for rsbridge)
#   deps/sdist/*                              PyQt6, PyQt6-sip, orjson, rpds-py, markupsafe
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
source "$ROOT/../shared/versions.env"
DEPS=$ROOT/deps
mkdir -p "$DEPS/sdist"
cd "$DEPS"

if [ "$(uname)" = Darwin ]; then
    HOST_OS=mac; HOST_ARCH=clang_64; HOST_DIR=macos
else
    HOST_OS=linux; HOST_ARCH=linux_gcc_64; HOST_DIR=gcc_64
fi

if [ ! -x "$ROOT/.venv/bin/sip-build" ]; then
    uv venv -q -p "$PYTHON_VERSION" "$ROOT/.venv"
    uv pip install -q -p "$ROOT/.venv/bin/python" pip \
        "sip==$SIP_VERSION" "pyqt-builder==$PYQT_BUILDER_VERSION"
fi

QT=$DEPS/qt/$QT_VERSION
if [ ! -d "$QT/$HOST_DIR/bin" ]; then
    uvx --from aqtinstall aqt install-qt "$HOST_OS" desktop "$QT_VERSION" "$HOST_ARCH" \
        --archives qtbase qtsvg qttools -O qt -b "$QT_MIRROR"
fi
if [ ! -d "$QT/android_arm64_v8a/lib" ]; then
    uvx --from aqtinstall aqt install-qt all_os android "$QT_VERSION" android_arm64_v8a \
        --archives qtbase qtsvg -O qt -b "$QT_MIRROR"
fi
# aqtinstall writes a host path relative to its working directory
for tool in qmake qmake6; do
    sed -i.bak -E "s|^[^ ]*/bin/qmake6 |$QT/$HOST_DIR/bin/qmake6 |" "$QT/android_arm64_v8a/bin/$tool"
    rm -f "$QT/android_arm64_v8a/bin/$tool.bak"
done

if [ ! -d python-android/prefix ]; then
    version=$(curl -fsSL https://www.python.org/ftp/python/ \
        | grep -o "$PYTHON_VERSION\.[0-9]*/" | tr -d / | sort -uV | tail -1)
    curl -fsSL -o python-android.tar.gz \
        "https://www.python.org/ftp/python/$version/python-$version-aarch64-linux-android.tar.gz"
    mkdir -p python-android && tar xzf python-android.tar.gz -C python-android
    rm python-android.tar.gz
fi

if [ ! -d anki/rslib ]; then
    git clone -q --depth 1 --branch "$ANKI_TAG" https://github.com/ankitects/anki anki
    git -C anki submodule update -q --init --depth 1
fi

sdist() {  # sdist <pypi name> <version> <unpacked dir>
    [ -d "sdist/$3" ] && return
    url=$(curl -fsSL "https://pypi.org/pypi/$1/$2/json" | python3 -c \
        "import json,sys; print(next(u['url'] for u in json.load(sys.stdin)['urls'] if u['packagetype']=='sdist'))")
    curl -fsSL "$url" | tar xz -C sdist
}
sdist pyqt6 "$PYQT6_VERSION" "pyqt6-$PYQT6_VERSION"
sdist pyqt6-sip "$PYQT6_SIP_VERSION" "pyqt6_sip-$PYQT6_SIP_VERSION"
sdist orjson "$ORJSON_VERSION" "orjson-$ORJSON_VERSION"
sdist rpds-py "$RPDS_VERSION" "rpds_py-$RPDS_VERSION"
sdist markupsafe "$MARKUPSAFE_VERSION" "markupsafe-$MARKUPSAFE_VERSION"
