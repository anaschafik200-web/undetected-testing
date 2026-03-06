"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           UGEEN.LIVE — Full API Client + SeleniumBase CDP Auto-Login        ║
║  Base API:  http://176.123.9.60:3000                                        ║
║  WS Server: ws://176.123.9.60:3011                                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

ENDPOINTS DISCOVERED (all prefixed with http://176.123.9.60:3000):
──────────────────────────────────────────────────────────────────
AUTH  (no token needed)
  POST  /auth/login                → Login, returns JWT token
  POST  /auth/register             → Register new user
  POST  /auth/activation           → Activate email (token from URL _t param)
  POST  /auth/forgot-password      → Request password reset email
  POST  /auth/reset-password       → Reset password with token

USER (token required)
  GET   /v1/users/overview         → Get current user info (username, email, status)

SUBSCRIPTIONS (token required)
  GET   /v1/subscriptions          → Get subscription info + history + IPTV creds
  POST  /v1/subscriptions          → Activate subscription (bouquetId + code + token)

BOUQUETS (token required)
  GET   /v1/bouquets               → List public bouquets (for renew page)
  GET   /v1/bouquets/advanced      → Admin: list all bouquets with stats
  POST  /v1/bouquets               → Admin: create new bouquet

CODES (token required)
  GET   /v1/codes                  → Request a download code link
  GET   /v1/codes/manage           → Admin: list all codes + stats
  POST  /v1/codes/create           → Admin: create a new code

FEEDBACKS (token required)
  POST  /v1/feedbacks              → Submit feedback/contact message

IPTV DOWNLOAD
  GET   http://ugeen.live:8080/get.php?username=X&password=X&type=m3u
        → Download M3U/Xtream playlist file

WEBSOCKET
  ws://176.123.9.60:3011           → Real-time status updates (auth via token query param)
──────────────────────────────────────────────────────────────────
"""

# ─────────────────────────────────────────────
# PART 1: SeleniumBase CDP Auto-Login (bypass reCAPTCHA)
# ─────────────────────────────────────────────
# pip install seleniumbase requests
#
# Run:  python ugeen_auto.py --mode browser
#       (extracts JWT token and saves to token.txt)
#
# Then: python ugeen_auto.py --mode api
#       (uses saved token.txt for all API operations - no browser needed)
# ─────────────────────────────────────────────

import requests
import json
import time
import argparse
import os
import sys

# ══════════════════════════════════════════════
#   CONFIGURATION
# ══════════════════════════════════════════════
EMAIL    = "anaschafik200@gmail.com"
PASSWORD = "jesuisen600"

BASE_API  = "http://176.123.9.60:3000"
API_V1    = f"{BASE_API}/v1"
SITE_URL  = "http://ugeen.live"
LOGIN_URL = f"{SITE_URL}/signin.html"
TOKEN_FILE = "token.txt"

HEADERS_BASE = {
    "Accept":          "application/json",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Content-Type":    "application/x-www-form-urlencoded",
}

# ══════════════════════════════════════════════════════════════════
#  PART 1 — SeleniumBase CDP Browser Auto-Login
#  Uses Chrome CDP mode to bypass Google reCAPTCHA v2 (invisible)
# ══════════════════════════════════════════════════════════════════

def seleniumbase_login():
    """
    Uses SeleniumBase CDP mode (undetected Chrome) to:
    1. Open ugeen.live/signin.html
    2. Fill email + password
    3. Trigger reCAPTCHA solve via CDP (uc_cdp_events / undetected-chromedriver)
    4. Wait for redirect to dashboard.html
    5. Extract JWT token from localStorage
    6. Save token to token.txt for API use
    """
    try:
        from seleniumbase import SB
    except ImportError:
        print("[!] SeleniumBase not installed. Run: pip install seleniumbase")
        sys.exit(1)

    print("=" * 60)
    print("  UGEEN.LIVE — CDP Auto-Login (bypasses reCAPTCHA)")
    print("=" * 60)
    print(f"  Target : {LOGIN_URL}")
    print(f"  Email  : {EMAIL}")
    print("=" * 60)

    # CDP mode = undetected stealth Chrome, bypasses Cloudflare & reCAPTCHA
    with SB(uc=True, headless=False, locale_code="ar") as sb:
        
        print("\n[1/6] Opening login page ...")
        sb.uc_open_with_reconnect(LOGIN_URL, reconnect_time=3)
        sb.sleep(2)

        # Handle any Cloudflare / CAPTCHA challenge first
        print("[2/6] Checking for Cloudflare challenge ...")
        try:
            sb.uc_gui_click_captcha()  # Handles CF turnstile if present
            sb.sleep(2)
        except Exception:
            pass  # No Cloudflare challenge, continue

        print("[3/6] Filling in credentials ...")
        # Wait for email field
        sb.wait_for_element_visible("#email", timeout=15)
        sb.clear("#email")
        sb.type("#email", EMAIL)
        sb.sleep(0.5)
        
        sb.wait_for_element_visible("#password", timeout=10)
        sb.clear("#password")
        sb.type("#password", PASSWORD)
        sb.sleep(0.5)

        print("[4/6] Triggering reCAPTCHA & submitting form ...")
        # Click submit — this triggers grecaptcha.execute() invisibly
        # CDP mode makes the browser appear completely human to Google
        sb.click("#submit")
        sb.sleep(1)

        # Wait for reCAPTCHA to fire the callback then form submits
        # The invisible reCAPTCHA calls onSubmit(token) -> $('#signin').submit()
        # We wait up to 20s for the page to change to dashboard
        print("[5/6] Waiting for login & redirect to dashboard ...")
        try:
            sb.wait_for_url_to_contain("dashboard", timeout=25)
            print("[✓] Login successful! Redirected to dashboard.")
        except Exception:
            # Check if we're still on signin page with error
            try:
                error_el = sb.find_element(".error-message")
                error_text = error_el.text
                if error_text:
                    print(f"[✗] Login error from server: {error_text}")
                    sys.exit(1)
            except Exception:
                pass
            print("[~] Timeout waiting for redirect — checking localStorage anyway...")

        sb.sleep(2)

        print("[6/6] Extracting JWT token from localStorage ...")
        token   = sb.execute_script("return localStorage.getItem('jsonwebToken')")
        expire  = sb.execute_script("return localStorage.getItem('authExpire')")
        uname   = sb.execute_script("return localStorage.getItem('username')")
        email   = sb.execute_script("return localStorage.getItem('email')")
        status  = sb.execute_script("return localStorage.getItem('status')")

        if not token:
            # Also try cookie.php which may store the token
            print("[~] localStorage empty — trying to get cookie token via JS...")
            token = sb.execute_script(
                "return document.cookie.split(';').find(c => c.includes('token'))"
            )

        if token:
            # Save to file
            with open(TOKEN_FILE, "w") as f:
                f.write(token)
            print(f"\n{'='*60}")
            print(f"  ✅ TOKEN CAPTURED AND SAVED TO: {TOKEN_FILE}")
            print(f"{'='*60}")
            print(f"  Token   : {token[:40]}...{token[-10:]}")
            print(f"  Expires : {expire}")
            print(f"  User    : {uname} ({email})")
            print(f"  Status  : {status}")
            print(f"{'='*60}\n")
            return token
        else:
            print("[✗] Could not extract token. Login may have failed.")
            sys.exit(1)


# ══════════════════════════════════════════════════════════════════
#  PART 2 — Full API Client (no browser required after token saved)
# ══════════════════════════════════════════════════════════════════

class UgeenAPI:
    """
    Full API client for ugeen.live backend.
    Discovered API base: http://176.123.9.60:3000
    All authenticated endpoints use Bearer JWT token.
    """

    def __init__(self, token: str):
        self.token   = token
        self.session = requests.Session()
        self.session.headers.update({
            **HEADERS_BASE,
            "Authorization": f"Bearer {token}",
            "Host": BASE_API,
        })
        print(f"\n[UgeenAPI] Initialized with token: {token[:30]}...")

    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{BASE_API}{path}"
        print(f"\n  → GET  {url}")
        r = self.session.get(url, params=params, timeout=15)
        print(f"  ← {r.status_code}")
        try:
            return r.json()
        except Exception:
            return {"raw": r.text, "status_code": r.status_code}

    def _post(self, path: str, data: dict = None) -> dict:
        url = f"{BASE_API}{path}"
        print(f"\n  → POST {url}")
        if data:
            print(f"     data: {json.dumps({k:v for k,v in data.items() if k!='password'}, ensure_ascii=False)}")
        r = self.session.post(url, data=data, timeout=15)
        print(f"  ← {r.status_code}")
        try:
            return r.json()
        except Exception:
            return {"raw": r.text, "status_code": r.status_code}

    # ── AUTH ENDPOINTS ─────────────────────────────────────────────

    @staticmethod
    def login(email: str, password: str, recaptcha_token: str = "bypass") -> dict:
        """
        POST /auth/login
        Body: email, password, recaptcha
        Returns: { access: { token, expire }, user: { email, username, status } }
        Note: recaptcha is validated server-side. Use SeleniumBase login to get
              a real solved token, then the browser already handles this flow.
        """
        url = f"{BASE_API}/auth/login"
        print(f"\n[AUTH] POST {url}")
        r = requests.post(url, data={
            "email":     email,
            "password":  password,
            "recaptcha": recaptcha_token,
        }, headers=HEADERS_BASE, timeout=15)
        print(f"  ← {r.status_code}")
        try:
            return r.json()
        except Exception:
            return {"raw": r.text}

    @staticmethod
    def register(username: str, email: str, password: str, recaptcha_token: str = "") -> dict:
        """
        POST /auth/register
        Body: username, email, password, recaptcha
        Returns: success or error message
        """
        url = f"{BASE_API}/auth/register"
        print(f"\n[AUTH] POST {url}")
        r = requests.post(url, data={
            "username":  username,
            "email":     email,
            "password":  password,
            "recaptcha": recaptcha_token,
        }, headers=HEADERS_BASE, timeout=15)
        print(f"  ← {r.status_code}")
        try:
            return r.json()
        except Exception:
            return {"raw": r.text}

    @staticmethod
    def activate_email(activation_token: str) -> dict:
        """
        POST /auth/activation
        Body: token  (JWT from email link ?_t=<token>)
        Returns: success confirmation
        """
        url = f"{BASE_API}/auth/activation"
        print(f"\n[AUTH] POST {url}")
        r = requests.post(url, data={"token": activation_token},
                          headers=HEADERS_BASE, timeout=15)
        print(f"  ← {r.status_code}")
        try:
            return r.json()
        except Exception:
            return {"raw": r.text}

    @staticmethod
    def forgot_password(email: str, recaptcha_token: str = "") -> dict:
        """
        POST /auth/forgot-password
        Body: email, recaptcha
        Returns: success (email sent) or error
        """
        url = f"{BASE_API}/auth/forgot-password"
        print(f"\n[AUTH] POST {url}")
        r = requests.post(url, data={
            "email":     email,
            "recaptcha": recaptcha_token,
        }, headers=HEADERS_BASE, timeout=15)
        print(f"  ← {r.status_code}")
        try:
            return r.json()
        except Exception:
            return {"raw": r.text}

    @staticmethod
    def reset_password(reset_token: str, new_password: str) -> dict:
        """
        POST /auth/reset-password
        Body: token (from email link), password
        Returns: success or error
        """
        url = f"{BASE_API}/auth/reset-password"
        print(f"\n[AUTH] POST {url}")
        r = requests.post(url, data={
            "token":    reset_token,
            "password": new_password,
        }, headers=HEADERS_BASE, timeout=15)
        print(f"  ← {r.status_code}")
        try:
            return r.json()
        except Exception:
            return {"raw": r.text}

    # ── USER ENDPOINTS ──────────────────────────────────────────────

    def get_user_overview(self) -> dict:
        """
        GET /v1/users/overview
        Headers: Authorization: Bearer <token>
        Returns: { username, email, status }
        Status codes: 0=exceptional, 1=active, 5=disabled, 9=banned
        """
        return self._get("/v1/users/overview")

    # ── SUBSCRIPTION ENDPOINTS ──────────────────────────────────────

    def get_subscriptions(self) -> dict:
        """
        GET /v1/subscriptions
        Headers: Authorization: Bearer <token>
        Returns: {
          user: <id>,
          iptv: { host, port, user, pass },   ← XTREAM CODES credentials!
          active: { id, created_at, expired_at, bouquet: {...} },
          history: [ { id, created_at, expired_at, bouquet } ],
          live: { date, stream, ip, country }  ← current watching session
        }
        """
        return self._get("/v1/subscriptions")

    def activate_subscription(self, bouquet_id: int, code: str, download_token: str) -> dict:
        """
        POST /v1/subscriptions
        Headers: Authorization: Bearer <token>
        Body: bouquetId, code (25-digit), token (from /v1/codes response)
        Returns: success message or error
        Flow: GET /v1/codes → download file → extract code → POST here
        """
        return self._post("/v1/subscriptions", data={
            "bouquetId": bouquet_id,
            "code":      code,
            "token":     download_token,
        })

    # ── BOUQUET ENDPOINTS ───────────────────────────────────────────

    def get_bouquets(self) -> dict:
        """
        GET /v1/bouquets
        Headers: Authorization: Bearer <token>
        Returns: { bouquets: [
          { id, title, description, image, available, users_groupe, packages }
        ] }
        users_groupe: 0=guests only, 1=members only, 2=members+guests
        """
        return self._get("/v1/bouquets")

    def get_bouquets_advanced(self) -> dict:
        """
        GET /v1/bouquets/advanced   [ADMIN]
        Headers: Authorization: Bearer <token>
        Returns: { bouquets: [ { id, title, ..., selected, created_at } ] }
        Includes stats (how many users selected each bouquet today)
        """
        return self._get("/v1/bouquets/advanced")

    def create_bouquet(self, title: str, packages: str, image: str,
                       description: str, users_groupe: int, status: bool) -> dict:
        """
        POST /v1/bouquets   [ADMIN]
        Headers: Authorization: Bearer <token>
        Body: title, packages (XTREAM IDs), image (filename), description,
              users_groupe (0/1/2), status (true/false)
        Returns: { id: <new_bouquet_id> }
        """
        return self._post("/v1/bouquets", data={
            "title":        title,
            "packages":     packages,
            "image":        image,
            "description":  description,
            "users_groupe": users_groupe,
            "status":       str(status).lower(),
        })

    # ── CODES ENDPOINTS ─────────────────────────────────────────────

    def get_activation_code(self) -> dict:
        """
        GET /v1/codes
        Headers: Authorization: Bearer <token>
        Returns: {
          uri:        <download URL for code file>,
          token:      <token to use in POST /v1/subscriptions>,
          expiration: "DD-MM-YYYY HH:mm:ss",
          creation:   "DD-MM-YYYY HH:mm:ss"
        }
        The downloaded file contains a 25-digit activation code.
        Code is valid for ~10 minutes (600s).
        """
        return self._get("/v1/codes")

    def get_codes_manage(self) -> dict:
        """
        GET /v1/codes/manage   [ADMIN]
        Headers: Authorization: Bearer <token>
        Returns: {
          codes: [ { id, code, download_link, status, downloads, created_at } ],
          stats: [ { day, month, year, downloads } ],
          sum:   { downloads: <total> }
        }
        """
        return self._get("/v1/codes/manage")

    def create_code(self, code: str, link: str, status: int = 1) -> dict:
        """
        POST /v1/codes/create   [ADMIN]
        Headers: Authorization: Bearer <token>
        Body: code (25-digit), link (download URL), status (1=active, 0=disabled)
        Returns: { id: <new_code_id> }
        """
        return self._post("/v1/codes/create", data={
            "code":   code,
            "link":   link,
            "status": status,
        })

    # ── FEEDBACK ENDPOINTS ──────────────────────────────────────────

    def send_feedback(self, category: str, message: str) -> dict:
        """
        POST /v1/feedbacks
        Headers: Authorization: Bearer <token>
        Body: category (bug/idea/support/feedback/other), message (Arabic)
        Returns: success or error
        """
        valid_categories = ["bug", "idea", "support", "feedback", "other"]
        if category not in valid_categories:
            raise ValueError(f"category must be one of: {valid_categories}")
        return self._post("/v1/feedbacks", data={
            "category": category,
            "message":  message,
        })

    # ── IPTV PLAYLIST DOWNLOAD ──────────────────────────────────────

    def download_iptv_playlist(self, iptv_user: str, iptv_pass: str,
                               fmt: str = "m3u") -> bytes:
        """
        GET http://ugeen.live:8080/get.php
        Params: username, password, type (m3u / m3u_plus / ts / rtmp)
        Returns: raw M3U playlist bytes
        First call GET /v1/subscriptions to get iptv.user and iptv.pass
        """
        url = "http://ugeen.live:8080/get.php"
        print(f"\n  → GET  {url}  [type={fmt}]")
        r = requests.get(url, params={
            "username": iptv_user,
            "password": iptv_pass,
            "type":     fmt,
        }, timeout=30)
        print(f"  ← {r.status_code} ({len(r.content)} bytes)")
        return r.content

    # ── FULL WORKFLOW HELPERS ───────────────────────────────────────

    def full_subscription_flow(self) -> bool:
        """
        Complete flow to renew/activate a free 24h subscription:
        1. GET /v1/codes         → get download link + token
        2. Download the file     → extract 25-digit code
        3. GET /v1/bouquets      → pick first available bouquet
        4. POST /v1/subscriptions → activate with bouquetId + code + token
        """
        print("\n" + "="*60)
        print("  FULL SUBSCRIPTION ACTIVATION FLOW")
        print("="*60)

        # Step 1: Get code download link
        print("\n[Step 1] Requesting activation code download link...")
        codes_resp = self.get_activation_code()
        print(f"  Response: {json.dumps(codes_resp, ensure_ascii=False, indent=2)}")

        if "uri" not in codes_resp:
            print("[✗] Failed to get code URI")
            return False

        download_uri   = codes_resp["uri"]
        download_token = codes_resp["token"]
        expiration     = codes_resp.get("expiration", "?")
        print(f"  Download URI   : {download_uri}")
        print(f"  Download Token : {download_token[:20]}...")
        print(f"  Expires        : {expiration}")

        # Step 2: Download the code file
        print(f"\n[Step 2] Downloading code file from: {download_uri}")
        try:
            r = requests.get(download_uri, timeout=30)
            file_content = r.text
            print(f"  File content: {file_content[:200]}")

            # Extract 25-digit code from file
            import re
            code_match = re.search(r'\b(\d{25})\b', file_content)
            if not code_match:
                # Try any long digit sequence
                code_match = re.search(r'(\d{20,})', file_content)
            
            if code_match:
                activation_code = code_match.group(1)
                print(f"  [✓] Extracted code: {activation_code}")
            else:
                print(f"  [✗] Could not extract 25-digit code from file")
                print(f"  Raw file: {file_content}")
                return False
        except Exception as e:
            print(f"  [✗] Download failed: {e}")
            return False

        # Step 3: Get available bouquets
        print("\n[Step 3] Fetching available bouquets...")
        bouquets_resp = self.get_bouquets()
        print(f"  Response: {json.dumps(bouquets_resp, ensure_ascii=False, indent=2)}")

        bouquets = bouquets_resp.get("bouquets", [])
        available = [b for b in bouquets if b.get("available") == True]
        
        if not available:
            print("[✗] No available bouquets found")
            return False

        selected_bouquet = available[0]
        bouquet_id = selected_bouquet["id"]
        print(f"  [✓] Selected bouquet: [{bouquet_id}] {selected_bouquet.get('title', '?')}")

        # Step 4: Activate subscription
        print(f"\n[Step 4] Activating subscription...")
        print(f"  bouquetId : {bouquet_id}")
        print(f"  code      : {activation_code}")
        print(f"  token     : {download_token[:20]}...")

        activate_resp = self.activate_subscription(
            bouquet_id=bouquet_id,
            code=activation_code,
            download_token=download_token
        )
        print(f"  Response: {json.dumps(activate_resp, ensure_ascii=False, indent=2)}")
        print("\n[✓] Subscription activation flow completed!")
        return True


# ══════════════════════════════════════════════════════════════════
#  MAIN — CLI Entry Point
# ══════════════════════════════════════════════════════════════════

def load_token() -> str:
    """Load JWT token from file or prompt user."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()
        if token:
            print(f"[✓] Loaded token from {TOKEN_FILE}: {token[:30]}...")
            return token
    print(f"[!] No token found in {TOKEN_FILE}. Run with --mode browser first.")
    sys.exit(1)


def demo_api(token: str):
    """Run a full demo of all API endpoints."""
    api = UgeenAPI(token)

    print("\n" + "╔" + "═"*58 + "╗")
    print("║  UGEEN.LIVE API — FULL ENDPOINT DEMO                    ║")
    print("╚" + "═"*58 + "╝")

    # ── 1. User Overview ────────────────────────────────────────
    print("\n" + "─"*60)
    print("  [1] GET /v1/users/overview")
    print("─"*60)
    resp = api.get_user_overview()
    print(f"  Result: {json.dumps(resp, ensure_ascii=False, indent=4)}")

    # ── 2. Subscriptions ────────────────────────────────────────
    print("\n" + "─"*60)
    print("  [2] GET /v1/subscriptions  (includes IPTV credentials)")
    print("─"*60)
    resp = api.get_subscriptions()
    print(f"  Result: {json.dumps(resp, ensure_ascii=False, indent=4)}")

    # Extract IPTV creds if available
    iptv = resp.get("iptv", {})
    if iptv:
        print(f"\n  ┌─ IPTV CREDENTIALS ────────────────────────")
        print(f"  │  Host     : {iptv.get('host', '?')}")
        print(f"  │  Port     : {iptv.get('port', '?')}")
        print(f"  │  Username : {iptv.get('user', '?')}")
        print(f"  │  Password : {iptv.get('pass', '?')}")
        print(f"  └───────────────────────────────────────────")

        # Generate M3U URL
        h = iptv.get('host','')
        p = iptv.get('port','')
        u = iptv.get('user','')
        pw = iptv.get('pass','')
        print(f"\n  M3U URL: http://{h}:{p}/get.php?username={u}&password={pw}&type=m3u")
        print(f"  M3U+URL: http://{h}:{p}/get.php?username={u}&password={pw}&type=m3u_plus")
        print(f"  XC URL : http://{h}:{p}/player_api.php?username={u}&password={pw}")

    # ── 3. Bouquets ─────────────────────────────────────────────
    print("\n" + "─"*60)
    print("  [3] GET /v1/bouquets")
    print("─"*60)
    resp = api.get_bouquets()
    print(f"  Result: {json.dumps(resp, ensure_ascii=False, indent=4)}")

    # ── 4. Get Activation Code ───────────────────────────────────
    print("\n" + "─"*60)
    print("  [4] GET /v1/codes  (request activation code link)")
    print("─"*60)
    resp = api.get_activation_code()
    print(f"  Result: {json.dumps(resp, ensure_ascii=False, indent=4)}")

    # ── 5. Send Feedback ─────────────────────────────────────────
    print("\n" + "─"*60)
    print("  [5] POST /v1/feedbacks")
    print("─"*60)
    # Uncomment to actually send:
    # resp = api.send_feedback("support", "استفسار تجريبي من السكريبت")
    # print(f"  Result: {json.dumps(resp, ensure_ascii=False, indent=4)}")
    print("  (skipped to avoid sending test message)")

    print("\n" + "═"*60)
    print("  DEMO COMPLETED")
    print("═"*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Ugeen.live API Client + CDP Auto-Login",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--mode",
        choices=["browser", "api", "subscribe", "demo"],
        default="demo",
        help=(
            "browser   : Launch Chrome CDP, auto-login, save token\n"
            "api       : Run full API demo with saved token\n"
            "subscribe : Run full subscription activation flow\n"
            "demo      : Run full API demo (default)\n"
        )
    )
    args = parser.parse_args()

    if args.mode == "browser":
        print("\n[MODE] Browser CDP Login")
        token = seleniumbase_login()
        print(f"\n[✓] Token saved. Now run:  python ugeen_auto.py --mode api\n")

    elif args.mode in ("api", "demo"):
        print("\n[MODE] API Demo")
        token = load_token()
        demo_api(token)

    elif args.mode == "subscribe":
        print("\n[MODE] Full Subscription Flow")
        token = load_token()
        api = UgeenAPI(token)
        api.full_subscription_flow()


if __name__ == "__main__":
    main()
