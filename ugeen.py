#!/usr/bin/env python3
"""
UGEEN.LIVE — Auto Login + reCAPTCHA Audio Solver (SeleniumBase Version)

Features
--------
✔ Undetected Chrome (SeleniumBase UC)
✔ Google reCAPTCHA audio solver
✔ ffmpeg audio conversion
✔ SpeechRecognition transcription
✔ Automatic screenshots
✔ Stable iframe switching
✔ Real login verification
"""

import os
import sys
import time
import json
import random
import shutil
import logging
import tempfile
import subprocess
import requests

from seleniumbase import SB

# ───────────────── CONFIG ───────────────── #

EMAIL = "anaschafik200@gmail.com"
PASSWORD = "jesuisen600"

LOGIN_URL = "http://ugeen.live/signin.html"

TOKEN_FILE = "token.txt"
SESSION_FILE = "session.json"

MAX_RETRIES = 3
TIMEOUT = 20

AUDIO_DIR = tempfile.mkdtemp(prefix="ugeen_captcha_")

SCREENSHOT_DIR = "screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# ────────────── LOGGING ────────────── #

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger("ugeen")

# ────────────── RECAPTCHA SELECTORS ────────────── #

RECAPTCHA_ANCHOR_FRAME = 'iframe[src*="recaptcha"][src*="anchor"]'
RECAPTCHA_BFRAME = 'iframe[src*="recaptcha"][src*="bframe"]'

SEL_AUDIO_BTN = "#recaptcha-audio-button"
SEL_AUDIO_SRC = "#audio-source"
SEL_AUDIO_INPUT = "#audio-response"
SEL_VERIFY_BTN = "#recaptcha-verify-button"
SEL_RELOAD_BTN = "#recaptcha-reload-button"

# ───────────────── UTILS ───────────────── #

def shot(sb, name):
    ts = time.strftime("%H%M%S")
    path = f"{SCREENSHOT_DIR}/{ts}_{name}.png"
    sb.save_screenshot(path)
    log.info(f"[📸] {path}")


def human_type(sb, selector, text):
    sb.click(selector)
    for c in text:
        sb.send_keys(selector, c)
        time.sleep(random.uniform(0.04, 0.09))


def switch_frame(sb, selector):
    try:
        sb.switch_to_default_content()
        sb.wait_for_element(selector, timeout=10)
        sb.switch_to_frame(selector)
        return True
    except Exception:
        return False


# ───────────────── AUDIO ───────────────── #

def download_audio(url, dest):
    headers = {
        "User-Agent":
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    }

    r = requests.get(url, headers=headers, timeout=20)

    with open(dest, "wb") as f:
        f.write(r.content)

    return os.path.exists(dest)


def convert_audio(mp3, wav):

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        mp3,
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        wav,
    ]

    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return os.path.exists(wav)


def transcribe(wav):

    import speech_recognition as sr

    r = sr.Recognizer()

    with sr.AudioFile(wav) as source:
        audio = r.record(source)

    try:
        text = r.recognize_google(audio)
        log.info(f"STT: {text}")
        return text.lower()
    except Exception:
        return None


def solve_audio(audio_url, attempt):

    mp3 = os.path.join(AUDIO_DIR, f"{attempt}.mp3")
    wav = os.path.join(AUDIO_DIR, f"{attempt}.wav")

    if not download_audio(audio_url, mp3):
        return None

    if not convert_audio(mp3, wav):
        return None

    text = transcribe(wav)

    return text


# ───────────────── CAPTCHA ───────────────── #

def handle_recaptcha(sb):

    log.info("reCAPTCHA challenge detected")

    if not switch_frame(sb, RECAPTCHA_BFRAME):
        return False

    time.sleep(1)

    if sb.is_element_visible(SEL_AUDIO_BTN):
        sb.js_click(SEL_AUDIO_BTN)
        time.sleep(2)

    for attempt in range(1, MAX_RETRIES + 1):

        log.info(f"Audio attempt {attempt}")

        if not switch_frame(sb, RECAPTCHA_BFRAME):
            return False

        audio_url = sb.get_attribute(SEL_AUDIO_SRC, "src")

        if not audio_url:
            return False

        sb.switch_to_default_content()

        text = solve_audio(audio_url, attempt)

        if not text:
            continue

        log.info(f"CAPTCHA text: {text}")

        if not switch_frame(sb, RECAPTCHA_BFRAME):
            return False

        sb.type(SEL_AUDIO_INPUT, text)

        shot(sb, "captcha_answer")

        sb.js_click(SEL_VERIFY_BTN)

        time.sleep(4)

        if switch_frame(sb, RECAPTCHA_ANCHOR_FRAME):

            checked = sb.get_attribute("#recaptcha-anchor", "aria-checked")

            if checked == "true":
                log.info("CAPTCHA solved")
                sb.switch_to_default_content()
                return True

    return False


# ───────────────── LOGIN ───────────────── #

def verify_login(sb):

    token = sb.execute_script("return localStorage.getItem('jsonwebToken');")

    url = sb.get_current_url()

    if token and ("dashboard" in url or "index" in url):
        return token

    return None


def login():

    log.info("UGEEN LOGIN START")

    with SB(uc=True, headless=False, locale_code="en") as sb:

        # OPEN PAGE

        sb.uc_open_with_reconnect(LOGIN_URL)

        shot(sb, "login_page")

        sb.execute_script("localStorage.clear();sessionStorage.clear();")

        sb.wait_for_element("#email", timeout=15)

        # FILL FORM

        human_type(sb, "#email", EMAIL)
        human_type(sb, "#password", PASSWORD)

        shot(sb, "credentials_filled")

        sb.js_click("#submit")

        shot(sb, "login_clicked")

        # WAIT FOR CAPTCHA OR REDIRECT

        captcha_handled = False

        for _ in range(40):

            time.sleep(0.5)

            if verify_login(sb):
                break

            frames = sb.find_elements('iframe[src*="recaptcha"]')

            for f in frames:

                src = f.get_attribute("src") or ""

                if "bframe" in src:

                    if not captcha_handled:

                        captcha_handled = True

                        shot(sb, "captcha_detected")

                        solved = handle_recaptcha(sb)

                        if solved:
                            time.sleep(4)

            if verify_login(sb):
                break

        token = verify_login(sb)

        if not token:
            log.error("Login failed")
            return None

        shot(sb, "dashboard")

        username = sb.execute_script(
            "return localStorage.getItem('username');")

        expire = sb.execute_script(
            "return localStorage.getItem('authExpire');")

        session = {
            "token": token,
            "username": username,
            "expire": expire,
        }

        with open(TOKEN_FILE, "w") as f:
            f.write(token)

        with open(SESSION_FILE, "w") as f:
            json.dump(session, f, indent=2)

        log.info("LOGIN SUCCESS")

        return token


# ───────────────── TOKEN TEST ───────────────── #

def test_token(token):

    r = requests.get(
        "http://176.123.9.60:3000/v1/users/overview",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    if r.status_code == 200:
        log.info("Token valid")
        log.info(json.dumps(r.json(), indent=2))
    else:
        log.error("Token invalid")


# ───────────────── MAIN ───────────────── #

if __name__ == "__main__":

    if not shutil.which("ffmpeg"):
        print("Install ffmpeg first")
        sys.exit()

    token = login()

    if token:

        print("\nTOKEN:\n")
        print(token)

        test_token(token)

    else:
        print("Login failed")

    shutil.rmtree(AUDIO_DIR, ignore_errors=True)
