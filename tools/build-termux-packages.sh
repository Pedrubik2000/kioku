#!/bin/bash
# Build the runtime's Termux packages for this app's own package name.
#
# Termux binaries hardcode /data/data/<package>/files/usr, so for the release
# id (io.krmanik.ankidesk) every package has to be compiled with
# TERMUX_APP__PACKAGE_NAME set; prebuilt packages from the Termux repos cannot
# be used, and build-package.sh builds all dependencies from source.
#
# Needs an x86_64 Linux host with Docker, ~150 GB of disk and several hours
# (qt6-qtwebengine is most of it).
#
#   tools/build-termux-packages.sh ~/termux-packages        # anki branch of krmanik/termux-packages
#   tools/debs_to_prefix.py --package io.krmanik.ankidesk \
#       --debs ~/termux-packages/output --out build/rootfs-native
set -euo pipefail

TERMUX_PACKAGES="${1:?path to a termux-packages checkout (anki branch)}"
APP_ID="${APP_ID:-io.krmanik.ankidesk}"
HERE="$(cd "$(dirname "$0")" && pwd)"

# Roots of the runtime closure; dependencies are pulled in by build-package.sh.
PACKAGES=(anki jwm termux-exec dash xkeyboard-config ca-certificates resolv-conf)

if [ "${#APP_ID}" -gt 33 ]; then
	echo "Package name '$APP_ID' is longer than Termux's 33 character limit." >&2
	exit 1
fi

cd "$TERMUX_PACKAGES"
sed -i.orig "s/^TERMUX_APP__PACKAGE_NAME=.*/TERMUX_APP__PACKAGE_NAME=\"$APP_ID\"/" scripts/properties.sh
grep -q "^TERMUX_APP__PACKAGE_NAME=\"$APP_ID\"" scripts/properties.sh

./scripts/run-docker.sh ./build-package.sh -a aarch64 "${PACKAGES[@]}"

echo
echo "Debs are in $TERMUX_PACKAGES/output. Next:"
echo "  $HERE/debs_to_prefix.py --package $APP_ID --debs $TERMUX_PACKAGES/output --out build/rootfs-native"
