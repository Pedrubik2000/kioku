# The Kioku desktop

The desktop (`rootfs-overlay/share/ankidx/ankidesk_shell.py`, PyQt6, no extra size) is styled
after Cutefish and Deepin: wallpaper on the home page (Alpine by default), solid dark pages for
Software and Settings, one blue accent, gradient "squircle" app icons drawn from SVG
(`ankidesk_theme.py`). It sits below every window. Closing Anki returns to the desktop, where the
Anki icon opens it again; **Settings → Power off** closes Anki (which saves the collection) and
ends the session. In landscape the page bar becomes a rail on the left and the dock moves to the
right edge (window buttons show icons only).

* **Apps**: clock, search, Anki, Terminal (`st`) and every installed app, with icons from their
  `.desktop` files.
* **Software**: recommended native Linux apps (Files 8 MB, Text Editor 4 MB, QTerminal 3 MB, Web
  Browser/Falkon 49 MB, Image Viewer 6 MB, Archives 7 MB, System Monitor 1 MB) and a search over
  every package in the Termux repositories (main and x11). Apps appear in Apps once installed;
  command-line packages open in a terminal. After an app update the runtime is replaced and they
  are reinstalled automatically.
* **Settings**: wallpaper (six built in, or any picture from Android's gallery or the home
  folder), touch screen or mouse pad (the current one is marked), keyboard, import a deck from
  the phone, phone storage, display settings, app info, restart desktop, power off.

Installed apps are started with Anki's scale (`QT_SCALE_FACTOR`, `GDK_SCALE`) and as if in KDE,
so Qt reads `~/.config/kdeglobals` (`ankidesk_theme.py`): a dark palette like the desktop's and
items that open with one tap. PCManFM-Qt gets single-click in its own settings. The session has a
D-Bus session bus (single-instance apps such as PCManFM-Qt exit without one) and
`XDG_DATA_DIRS`/`XDG_CONFIG_DIRS` pointing into the prefix (icon themes, `.desktop` files). The
file-based apps install `adwaita-icon-theme-legacy` (2 MB) with them for file and folder icons.

The installer (`ankidesk_pkg.py`, also `ankidesk-pkg install|remove|list|search` in a terminal)
resolves dependencies against the bundled packages, checks SHA256, unpacks into the prefix and
rewrites the Termux path; it does not run maintainer scripts, so a few command-line packages may
need extra steps.

## Window manager and dock

JWM. Main windows maximized, dialogs centered/on top with a close button, bottom dock (desktop
button, open windows, keyboard, clock), flat with no gradients and no hover tooltips.
`~/.jwmrc` is generated from `share/ankidx/jwmrc` with the chosen wallpaper and the dock for the
current orientation.

The **Kioku button** at the start of the dock minimizes every window to show the desktop; tapping
it again brings them back with the window that was active on top (`ankidesk_x11.py desktop`).
JWM's own `showdesktop` is not used: it loses track as soon as a window is opened from the
desktop.

Turning the phone restarts JWM with the other dock; JWM forgets which windows were maximized or
minimized on a restart and when the screen size changes, so the desktop samples the window
states and puts them back. Qt is scaled so the short side of the screen is ~480 logical pixels.

## Touch

Settings offers **Touch screen** (tap to click, drag to scroll) and **Mouse pad** (one finger
moves a pointer, two fingers scroll).

In touch-screen mode the display runs in one of two termux-x11 modes, chosen by the desktop for
the active window:

* **Anki and the desktop**: termux-x11's simulated touchscreen, where a finger drag arrives as a
  held mouse button. `ankidesk_touch.py` turns a drag in a page, list or web view into scrolling
  with momentum (web views through a script) instead of selecting, and drops the tap at its
  end. Windows whose desktop-sized minimum would not fit the phone (e.g. Anki's About) are
  shrunk to the screen, file dialogs fill it and open folders with one tap.
* **Every other app** (web browser, file manager, …): termux-x11's direct touch, so the app
  gets real touch events. Browsers and GTK/Qt apps then scroll with a drag and select text with
  a long press, as on a phone, instead of a drag selecting text. Firefox gets
  `MOZ_USE_XINPUT2=1` for this.

## Keyboard

Text fields open the Android keyboard and tapping elsewhere closes it; tapping a field again
reopens it after it was closed with Back. Anki and the desktop follow Qt's focus and taps
(`ankidesk_keyboard.py`, plus a script in Anki's web views). For other apps the desktop watches
taps (XInput2 raw events) and opens the keyboard when the pointer then is a text cursor (I-beam),
e.g. in a terminal (`ankidesk_x11.py`). The keyboard button in the dock shows or hides it.

## Cursors

No cursor theme is bundled, so `ankidesk_cursors.py` draws a large "kioku" Xcursor theme on
first start, and the display draws 16 px core cursors (JWM, `st`) three times larger.
