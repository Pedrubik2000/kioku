#!/bin/bash
# Build Anki's rsbridge and the orjson / rpds-py extension modules as static
# libraries for aarch64-linux-android with the NDK's clang. pyo3 is told not
# to link libpython; the app links it itself.
# Env: ANDROID_NDK_ROOT (or ANDROID_NDK)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
source "$ROOT/../shared/versions.env"
TARGET=aarch64-linux-android
API=28
NDK=${ANDROID_NDK_ROOT:-${ANDROID_NDK:?set ANDROID_NDK_ROOT}}
HOST_TAG=$( [ "$(uname)" = Darwin ] && echo darwin-x86_64 || echo linux-x86_64 )
LLVM=$NDK/toolchains/llvm/prebuilt/$HOST_TAG/bin

export CC_aarch64_linux_android=$LLVM/$TARGET$API-clang
export CXX_aarch64_linux_android=$LLVM/$TARGET$API-clang++
export AR_aarch64_linux_android=$LLVM/llvm-ar
export CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER=$CC_aarch64_linux_android
export PROTOC=${PROTOC:-$(command -v protoc)}

# Anki pins its toolchain (rust-toolchain.toml); orjson needs a newer rustc
# than that, so it uses nightly.
ANKI_TOOLCHAIN=$(sed -n 's/^channel *= *"\(.*\)"/\1/p' "$ROOT/deps/anki/rust-toolchain.toml")
for toolchain in "$ANKI_TOOLCHAIN" nightly stable; do
    rustup toolchain install --profile minimal "$toolchain" >/dev/null
    rustup target add --toolchain "$toolchain" "$TARGET" >/dev/null
done

# rsbridge refuses to load unless its build hash matches the Python package's
mkdir -p "$ROOT/deps/anki/out"
HASH=$(git -C "$ROOT/deps/anki" rev-parse --short=8 HEAD)
[ "$(cat "$ROOT/deps/anki/out/buildhash" 2>/dev/null)" = "$HASH" ] \
    || echo "$HASH" > "$ROOT/deps/anki/out/buildhash"

# rsbridge over the small RWKV engine (patches/anki-rsbridge-rwkv-small.patch):
# Kioku ships JSchoreels' small model (shared/python/kioku/rwkv/); KIOKU_RWKV_BIG=1
# builds the plain bridge for the big model embedded in aqt instead.
PATCH=$ROOT/patches/anki-rsbridge-rwkv-small.patch
git -C "$ROOT/deps/anki" apply --check --reverse "$PATCH" 2>/dev/null \
    || git -C "$ROOT/deps/anki" apply "$PATCH"
RSBRIDGE_FEATURES=$( [ "${KIOKU_RWKV_BIG:-}" = 1 ] && echo "" || echo ",rwkv-small" )

cd "$ROOT/deps/anki"
PYO3_CONFIG_FILE=$ROOT/../shared/tools/pyo3/abi3.cfg cargo rustc -p rsbridge --lib --release \
    --target "$TARGET" --features "rustls$RSBRIDGE_FEATURES" --crate-type staticlib

export PYO3_CONFIG_FILE=$ROOT/../shared/tools/pyo3/cp314.cfg
cd "$ROOT/deps/sdist/orjson-$ORJSON_VERSION"
cargo +nightly rustc --lib --release --target "$TARGET" --crate-type staticlib
cd "$ROOT/deps/sdist/rpds_py-$RPDS_VERSION"
cargo +stable rustc --lib --release --target "$TARGET" --crate-type staticlib
