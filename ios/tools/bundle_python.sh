#!/bin/bash
# Post-link step (run by Xcode): put the Python standard library, Kioku's own
# Python code and Anki with its dependencies into the app bundle. iOS only
# loads native code from signed frameworks, so every extension module (.so) is
# moved into Frameworks/<module>.framework and replaced by a .fwork pointer,
# the layout CPython's iOS import machinery expects.
#
# Usage: bundle_python.sh <Python.xcframework slice> <ios folder>
set -euo pipefail

SLICE=$1
ROOT=$2
APP=$CODESIGNING_FOLDER_PATH
XCFRAMEWORK=$(dirname "$SLICE")
SIGN_ID=${EXPANDED_CODE_SIGN_IDENTITY:-}

mkdir -p "$APP/python/lib" "$APP/Frameworks"
rsync -a --delete \
    --exclude 'libpython*.dylib' --exclude '__pycache__' \
    --exclude 'test/' --exclude 'idlelib/' --exclude 'tkinter/' \
    --exclude 'turtledemo/' --exclude 'ensurepip/' \
    "$XCFRAMEWORK/lib/" "$APP/python/lib/"
rsync -a "$SLICE/lib-arm64/" "$APP/python/lib/" --exclude 'libpython*.dylib'

# app/: the shared kioku package and PyQt6 overlay, plus the iOS platform layer
rsync -a --delete --exclude '__pycache__' "$ROOT/../shared/python/" "$APP/app/"
rsync -a --exclude '__pycache__' "$ROOT/python/" "$APP/app/"
rsync -a --delete --exclude '__pycache__' "$ROOT/build/site/" "$APP/app_packages/"

install_so() {
    local full=$1 base=$2
    local rel=${full#$APP/}
    local modpath=${rel#$base/}
    local modname
    modname=$(echo "${modpath%%.*}" | tr / .)
    local fw="Frameworks/$modname.framework"
    mkdir -p "$APP/$fw"
    cp "$XCFRAMEWORK/build/iOS-dylib-Info-template.plist" "$APP/$fw/Info.plist"
    plutil -replace CFBundleExecutable -string "$modname" "$APP/$fw/Info.plist"
    plutil -replace CFBundleIdentifier -string \
        "io.ankidesk.kioku.$(echo "$modname" | tr _ -)" "$APP/$fw/Info.plist"
    mv "$full" "$APP/$fw/$modname"
    echo "$fw/$modname" > "${full%.so}.fwork"
    echo "${rel%.so}.fwork" > "$APP/$fw/$modname.origin"
    # privacy manifest: one shipped next to the module (as CPython's own
    # helper installs it), else ours for the modules that embed OpenSSL
    local shipped
    shipped="$(dirname "$full")/$(basename "${full%%.*}").xcprivacy"
    if [ -f "$shipped" ]; then
        mv "$shipped" "$APP/$fw/PrivacyInfo.xcprivacy"
    elif [ "$modname" = _ssl ] || [ "$modname" = _hashlib ]; then
        cp "$ROOT/res/openssl.xcprivacy" "$APP/$fw/PrivacyInfo.xcprivacy"
    fi
    if [ -n "$SIGN_ID" ]; then
        /usr/bin/codesign --force --sign "$SIGN_ID" -o runtime --timestamp=none \
            --preserve-metadata=identifier,entitlements,flags \
            --generate-entitlement-der "$APP/$fw" >/dev/null
    fi
}

find "$APP/python/lib/python3.14/lib-dynload" -name '*.so' | while read -r so; do
    install_so "$so" python/lib/python3.14/lib-dynload
done
find "$APP/app_packages" -name '*.so' | while read -r so; do
    install_so "$so" app_packages
done
