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
| [`android/`](android/) | Android 9+ (arm64) | Natively, the same way as `ios/`, with Android's WebView. |

[`shared/`](shared/) holds the Python layer and versions the native variants
have in common; [`docs/`](docs/) has the [fixes log](docs/fixes.md) and
[test results](docs/testing.md).

## Screenshots

Deck list, reviewing (question and answer), Browse, Statistics and Add.

Android:

<p>
  <img src="docs/images/android-decks.png" width="200" alt="Deck list on Android">
  <img src="docs/images/android-review-hanzi-question.png" width="200" alt="Reviewing a Chinese card: question">
  <img src="docs/images/android-review-hanzi-answer.png" width="200" alt="Reviewing a Chinese card: answer">
  <img src="docs/images/android-review-neetcode-question.png" width="200" alt="Reviewing a NeetCode card">
  <img src="docs/images/android-browse.png" width="200" alt="Browse on Android">
  <img src="docs/images/android-stats.png" width="200" alt="Statistics on Android">
  <img src="docs/images/android-add.png" width="200" alt="Add on Android">
</p>

iPhone:

<p>
  <img src="docs/images/ios-decks.png" width="200" alt="Deck list on iPhone">
  <img src="docs/images/ios-review-hanzi-question.png" width="200" alt="Reviewing a Chinese card on iPhone: question">
  <img src="docs/images/ios-review-hanzi-answer.png" width="200" alt="Reviewing a Chinese card on iPhone: answer">
  <img src="docs/images/ios-review-neetcode-question.png" width="200" alt="Reviewing a NeetCode card on iPhone">
  <img src="docs/images/ios-browse.png" width="200" alt="Browse on iPhone">
  <img src="docs/images/ios-stats.png" width="200" alt="Statistics on iPhone">
  <img src="docs/images/ios-add.png" width="200" alt="Add on iPhone">
</p>

Downloads for every variant are on the [releases page](https://github.com/krmanik/kioku/releases/latest).
