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
# Where Qt and GTK look for icon themes, .desktop files and settings; their
# built-in default (/usr/share, /etc/xdg) does not exist here.
export XDG_DATA_DIRS="$PREFIX/share"
export XDG_CONFIG_DIRS="$PREFIX/etc/xdg"

mkdir -p "$HOME" "$TMPDIR" "$PREFIX/var/cache/fontconfig"

# Qt: X11 backend, no OpenGL. Software rendering keeps mesa/LLVM out of the
# bundle and avoids GPU driver issues inside Termux:X11.
export QT_QPA_PLATFORM=xcb
export QT_XCB_GL_INTEGRATION=none
export QT_QUICK_BACKEND=software
export QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu --disable-gpu-compositing --disable-dev-shm-usage --disable-features=Vulkan --in-process-gpu --no-zygote --renderer-process-limit=1 --process-per-site --touch-events=enabled"
export QTWEBENGINE_DISABLE_SANDBOX=1
# Anki's single-instance socket, so the desktop can hand it files to import.
export ANKI_SINGLE_INSTANCE_KEY=kioku-anki

# A D-Bus session bus. Single-instance apps such as PCManFM-Qt look for their
# running copy on it, and without one they hand over to nobody and exit.
if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
	DBUS_SESSION_BUS_ADDRESS=$(dbus-daemon --session --fork --print-address 2>"$TMPDIR/dbus.log") \
		&& export DBUS_SESSION_BUS_ADDRESS
fi

# Large cursors drawn for the phone (ankidesk_cursors.py; generated once per
# runtime, so an app update brings new ones).
export XCURSOR_PATH="$PREFIX/share/icons"
export XCURSOR_THEME=kioku
export XCURSOR_SIZE=64
if [ ! -f "$XCURSOR_PATH/kioku/index.theme" ]; then
	QT_QPA_PLATFORM=offscreen python "$PREFIX/share/ankidx/ankidesk_cursors.py" "$XCURSOR_PATH/kioku" \
		>"$TMPDIR/cursors.log" 2>&1
fi

# Window manager: every window maximized, a bottom dock to switch between
# windows. The config is generated with the chosen wallpaper.
python "$PREFIX/share/ankidx/ankidesk_theme.py" jwmrc >"$TMPDIR/theme.log" 2>&1 \
	|| cp -f "$PREFIX/share/ankidx/jwmrc" "$HOME/.jwmrc"
jwm >"$TMPDIR/jwm.log" 2>&1 &

# After an app update, reinstall the apps the user had added.
if [ -f "$PREFIX/../apps-to-restore.json" ]; then
	python "$PREFIX/share/ankidx/ankidesk_pkg.py" restore >"$TMPDIR/restore.log" 2>&1 &
fi

# Anki is an app on the desktop: closing it returns to the desktop. The
# session lasts as long as the desktop shell, which exits on "Power off".
python "$PREFIX/share/ankidx/launch_anki.py" "$@" >"$TMPDIR/anki.log" 2>&1 &
exec python "$PREFIX/share/ankidx/ankidesk_shell.py"
