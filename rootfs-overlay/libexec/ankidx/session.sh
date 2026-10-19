#!/data/data/com.termux/files/usr/bin/sh
# Desktop session started by the Android app once the X server is listening.
# Paths below are written for the Termux prefix; tools/build_rootfs.py rewrites
# them to the app's own data directory.

PREFIX=/data/data/com.termux/files/usr
export PREFIX
export HOME="${HOME:-/data/data/com.termux/files/home}"
export TMPDIR="${TMPDIR:-$PREFIX/tmp}"
export PATH="$PREFIX/bin:/system/bin"
export DISPLAY="${DISPLAY:-:0}"
export LANG="${LANG:-en_US.UTF-8}"
export SHELL="$PREFIX/bin/dash"

mkdir -p "$HOME" "$TMPDIR" "$PREFIX/var/cache/fontconfig"

# Qt: X11 backend, no OpenGL. Software rendering keeps mesa/LLVM out of the
# bundle and avoids GPU driver issues inside Termux:X11.
export QT_QPA_PLATFORM=xcb
export QT_XCB_GL_INTEGRATION=none
export QT_QUICK_BACKEND=software
export QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu --disable-gpu-compositing --disable-dev-shm-usage --disable-features=Vulkan --in-process-gpu --no-zygote --renderer-process-limit=1 --process-per-site --touch-events=enabled"
export QTWEBENGINE_DISABLE_SANDBOX=1

# Window manager: every window maximized, a bottom task bar to switch between
# Anki's windows (main, Browse, Add ...).
cp -f "$PREFIX/share/ankidx/jwmrc" "$HOME/.jwmrc"
jwm >"$TMPDIR/jwm.log" 2>&1 &

# After an app update, reinstall the apps the user had added.
if [ -f "$PREFIX/../apps-to-restore.json" ]; then
	python "$PREFIX/share/ankidx/ankidesk_pkg.py" restore >"$TMPDIR/restore.log" 2>&1 &
fi

exec python "$PREFIX/share/ankidx/launch_anki.py" "$@"
