"""Push Kioku's store texts and screenshots to App Store Connect.

Texts come from ios/appstore/*.txt, screenshots from build/appstore-shots
(tools/appstore_shots.py). Sets the App Store listing (en-US: subtitle,
description, keywords, promotional text, URLs, iPhone screenshots), the
TestFlight test information and the newest build's "What to Test".

Auth: APP_STORE_KEY_ID / APP_STORE_ISSUER_ID from the environment or .env,
the key from APP_STORE_KEY_PATH or AuthKey_<key id>.p8 at the repo root.

Usage: uv run --with 'pyjwt[crypto]' python ios/tools/appstore_metadata.py
"""

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import jwt

IOS = Path(__file__).resolve().parents[1]
REPO = IOS.parent
TEXTS = IOS / "appstore"
SHOTS = IOS / "build/appstore-shots"
BUNDLE_ID = "io.ankidesk.kioku"
LOCALE = "en-US"
GITHUB = "https://github.com/krmanik/kioku"
URLS = {
    "support": f"{GITHUB}/issues",
    "marketing": GITHUB,
    "privacy": f"{GITHUB}/blob/main/docs/privacy.md",
}
SCREENSHOT_TYPE = "APP_IPHONE_67"  # 1290×2796

dotenv = REPO / ".env"
env = dict(re.findall(r"^(\w+)=[\"']?([^\"'\n]*)", dotenv.read_text(), re.M)) if dotenv.exists() else {}
KEY_ID = os.environ.get("APP_STORE_KEY_ID") or env["APP_STORE_KEY_ID"]
ISSUER = os.environ.get("APP_STORE_ISSUER_ID") or env["APP_STORE_ISSUER_ID"]
KEY = Path(os.environ.get("APP_STORE_KEY_PATH", REPO / f"AuthKey_{KEY_ID}.p8")).read_text()
COPYRIGHT = os.environ.get("COPYRIGHT_LINE") or env.get("COPYRIGHT_LINE")


def token():
    now = int(time.time())
    return jwt.encode({"iss": ISSUER, "iat": now, "exp": now + 1200, "aud": "appstoreconnect-v1"},
                      KEY, algorithm="ES256", headers={"kid": KEY_ID, "typ": "JWT"})


def api(method, path, body=None):
    req = urllib.request.Request(
        "https://api.appstoreconnect.apple.com" + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + token(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            data = r.read()
            return json.loads(data) if data else {}
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path}: {e.code} {e.read().decode()[:600]}")


def text(name):
    return (TEXTS / f"{name}.txt").read_text().strip()


def patch(kind, id_, attributes):
    api("PATCH", f"/v1/{kind}/{id_}", {"data": {"type": kind, "id": id_, "attributes": attributes}})


def create(kind, attributes, relationships):
    rel = {k: {"data": {"type": t, "id": i}} for k, (t, i) in relationships.items()}
    return api("POST", f"/v1/{kind}", {"data": {"type": kind, "attributes": attributes,
                                                 "relationships": rel}})["data"]


def localization(items):
    return next(item for item in items if item["attributes"]["locale"] == LOCALE)


def upload_screenshot(set_id, path):
    data = path.read_bytes()
    shot = create("appScreenshots", {"fileName": path.name, "fileSize": len(data)},
                  {"appScreenshotSet": ("appScreenshotSets", set_id)})
    for op in shot["attributes"]["uploadOperations"]:
        chunk = data[op["offset"]:op["offset"] + op["length"]]
        headers = {h["name"]: h["value"] for h in op["requestHeaders"]}
        urllib.request.urlopen(urllib.request.Request(op["url"], data=chunk, method=op["method"],
                                                      headers=headers)).read()
    patch("appScreenshots", shot["id"],
          {"uploaded": True, "sourceFileChecksum": hashlib.md5(data).hexdigest()})


def main():
    app = api("GET", f"/v1/apps?filter[bundleId]={BUNDLE_ID}")["data"][0]
    app_id = app["id"]

    # App Store listing: subtitle and privacy policy (app info)
    info = api("GET", f"/v1/apps/{app_id}/appInfos")["data"][0]
    info_loc = localization(api("GET", f"/v1/appInfos/{info['id']}/appInfoLocalizations")["data"])
    patch("appInfoLocalizations", info_loc["id"],
          {"subtitle": text("subtitle"), "privacyPolicyUrl": URLS["privacy"]})
    print("app info: subtitle, privacy policy URL")

    # App Store listing: the version being prepared
    version = next(v for v in api("GET", f"/v1/apps/{app_id}/appStoreVersions")["data"]
                   if v["attributes"]["appStoreState"] == "PREPARE_FOR_SUBMISSION")
    if COPYRIGHT:
        patch("appStoreVersions", version["id"], {"copyright": COPYRIGHT})
    ver_loc = localization(api("GET", f"/v1/appStoreVersions/{version['id']}"
                                      "/appStoreVersionLocalizations")["data"])
    patch("appStoreVersionLocalizations", ver_loc["id"], {
        "description": text("description"), "keywords": text("keywords"),
        "promotionalText": text("promotional_text"),
        "supportUrl": URLS["support"], "marketingUrl": URLS["marketing"]})
    print("version", version["attributes"]["versionString"], ": description, keywords, URLs")

    # iPhone screenshots: replace the whole set
    sets = api("GET", f"/v1/appStoreVersionLocalizations/{ver_loc['id']}/appScreenshotSets")["data"]
    shot_set = next((s for s in sets if s["attributes"]["screenshotDisplayType"] == SCREENSHOT_TYPE), None)
    if shot_set:
        for old in api("GET", f"/v1/appScreenshotSets/{shot_set['id']}/appScreenshots")["data"]:
            api("DELETE", f"/v1/appScreenshots/{old['id']}")
    else:
        shot_set = create("appScreenshotSets", {"screenshotDisplayType": SCREENSHOT_TYPE},
                          {"appStoreVersionLocalization": ("appStoreVersionLocalizations", ver_loc["id"])})
    for path in sorted(SHOTS.glob("*.png")):
        upload_screenshot(shot_set["id"], path)
        print("screenshot", path.name)

    # TestFlight: test information
    beta = dict(description=text("beta_description"), marketingUrl=URLS["marketing"],
                privacyPolicyUrl=URLS["privacy"])
    beta_locs = api("GET", f"/v1/apps/{app_id}/betaAppLocalizations")["data"]
    if any(b["attributes"]["locale"] == LOCALE for b in beta_locs):
        patch("betaAppLocalizations", localization(beta_locs)["id"], beta)
    else:
        create("betaAppLocalizations", {**beta, "locale": LOCALE}, {"app": ("apps", app_id)})
    print("TestFlight: test information")

    # TestFlight: "What to Test" of the newest build
    build = api("GET", f"/v1/builds?filter[app]={app_id}&sort=-uploadedDate&limit=1")["data"][0]
    locs = api("GET", f"/v1/builds/{build['id']}/betaBuildLocalizations")["data"]
    if any(b["attributes"]["locale"] == LOCALE for b in locs):
        patch("betaBuildLocalizations", localization(locs)["id"], {"whatsNew": text("whats_new")})
    else:
        create("betaBuildLocalizations", {"locale": LOCALE, "whatsNew": text("whats_new")},
               {"build": ("builds", build["id"])})
    print("build", build["attributes"]["version"], ": What to Test")


if __name__ == "__main__":
    main()
