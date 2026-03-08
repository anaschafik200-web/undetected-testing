import os
import re
import json
import time
import requests

from seleniumbase import SB

# ===============================
# CONFIG
# ===============================

EMAIL = "anaschafik200@gmail.com"
PASSWORD = "jesuisen600"

BASE_API = "http://176.123.9.60:3000"
SITE = "http://ugeen.live"

LOGIN_URL = f"{SITE}/signin.html"

TOKEN_FILE = "token.txt"
PLAYLIST_FILE = "playlist.m3u"


# ===============================
# INSTALL CHECK
# ===============================

def system_setup():

    print("Installing Chrome...")

    os.system("apt update")
    os.system("apt install -y wget gnupg unzip")

    os.system(
        "wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
    )

    os.system(
        "apt install -y ./google-chrome-stable_current_amd64.deb"
    )

    print("Installing Python deps...")

    os.system("pip install seleniumbase requests")

    print("Installing chromedriver...")
    os.system("sbase install chromedriver")


# ===============================
# LOGIN + CAPTCHA BYPASS
# ===============================

def browser_login():

    print("Starting stealth browser...")

    with SB(
        uc=True,
        headless=True,
        locale_code="ar",
        chromium_arg="--no-sandbox"
    ) as sb:

        sb.uc_open_with_reconnect(LOGIN_URL, reconnect_time=3)

        sb.sleep(3)

        print("Solving captcha if present")

        try:
            sb.uc_gui_click_captcha()
        except:
            pass

        sb.type("#email", EMAIL)
        sb.type("#password", PASSWORD)

        sb.click("#submit")

        sb.sleep(8)

        token = sb.execute_script(
            "return localStorage.getItem('jsonwebToken')"
        )

        if not token:
            raise Exception("Token not found")

        with open(TOKEN_FILE, "w") as f:
            f.write(token)

        print("TOKEN:", token[:40])

        return token


# ===============================
# API CLIENT
# ===============================

class Ugeen:

    def __init__(self, token):

        self.s = requests.Session()

        self.s.headers.update({
            "Authorization": f"Bearer {token}"
        })

    def user(self):

        r = self.s.get(f"{BASE_API}/v1/users/overview")

        return r.json()

    def subscriptions(self):

        r = self.s.get(f"{BASE_API}/v1/subscriptions")

        return r.json()

    def bouquets(self):

        r = self.s.get(f"{BASE_API}/v1/bouquets")

        return r.json()

    def codes(self):

        r = self.s.get(f"{BASE_API}/v1/codes")

        return r.json()

    def activate(self, bouquet, code, token):

        r = self.s.post(
            f"{BASE_API}/v1/subscriptions",
            data={
                "bouquetId": bouquet,
                "code": code,
                "token": token
            }
        )

        return r.json()


# ===============================
# AUTO SUBSCRIBE
# ===============================

def activate_subscription(api):

    print("Getting code...")

    c = api.codes()

    url = c["uri"]
    token = c["token"]

    file = requests.get(url).text

    code = re.search(r"\d{25}", file).group()

    print("CODE:", code)

    b = api.bouquets()["bouquets"]

    bouquet = b[0]["id"]

    print("BOUQUET:", bouquet)

    result = api.activate(bouquet, code, token)

    print(result)


# ===============================
# DOWNLOAD PLAYLIST
# ===============================

def download_playlist(api):

    sub = api.subscriptions()

    iptv = sub["iptv"]

    user = iptv["user"]
    passwd = iptv["pass"]

    url = f"http://ugeen.live:8080/get.php?username={user}&password={passwd}&type=m3u"

    print("Downloading playlist")

    r = requests.get(url)

    open(PLAYLIST_FILE, "wb").write(r.content)

    print("Saved:", PLAYLIST_FILE)


# ===============================
# MAIN
# ===============================

def main():

    if not os.path.exists(TOKEN_FILE):

        token = browser_login()

    else:

        token = open(TOKEN_FILE).read().strip()

    api = Ugeen(token)

    print("User:", api.user())

    activate_subscription(api)

    download_playlist(api)


if __name__ == "__main__":
    main()
