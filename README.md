<p align="center">
  <img src="termux/docs/kioku.svg" width="112" alt="Kioku icon">
</p>

<h1 align="center">Kioku</h1>

<p align="center">
  <b>The real Anki desktop app on your phone.</b><br>
  Add-ons, the card browser and every desktop feature, made for a touch screen.
</p>

---

Kioku runs the unmodified Anki desktop app (`aqt`, Qt 6) on phones. Each folder
is a separate app built a different way:

| Folder | Platform | How it runs Anki |
| --- | --- | --- |
| [`termux/`](termux/) | Android | Termux packages and a small X11 desktop inside the APK; installs other Linux apps on demand. |
| [`ios/`](ios/) | iPhone, iPad | Natively: embedded Python, Qt and PyQt6 compiled into the app, the system web view in place of Qt WebEngine. |

[`shared/`](shared/) holds the Python layer and versions the native variants
have in common; [`docs/`](docs/) has the [fixes log](docs/fixes.md) and
[test results](docs/testing.md).

Downloads for every variant are on the [releases page](https://github.com/krmanik/kioku/releases/latest).
