#!/usr/bin/env python3
"""psa-login: automated cookie refresh via a real browser.

PSA/Collectors auth is a confidential OAuth2 client (secret lives server-side), so the
scraper can't mint tokens itself. Instead we log in the way a human does - drive a real
Chromium (headful, under xvfb, to pass Cloudflare) through the collectors.com sign-in,
then harvest the fresh psacard.com cookie and write it into /etc/psa-tracker.env.

Runs before each scheduled scan so PSA_COOKIE never goes stale.

Env (from /etc/psa-tracker.env):
  PSA_LOGIN_EMAIL, PSA_LOGIN_PW   required - the PSA/Collectors account login.
      NOTE: deliberately NOT PSA_PASSWORD - that name is the site's friends-gate password
      (read by app.py). Keep these separate or you'll clobber the site login.
  PSA_ENV_FILE              default /etc/psa-tracker.env  (where PSA_COOKIE is written)
  PLAYWRIGHT_BROWSERS_PATH  set by the wrapper to /opt/psa-tracker/.pw-browsers
"""
import os, shlex, sys, time
from playwright.sync_api import sync_playwright

EMAIL = os.environ.get("PSA_LOGIN_EMAIL", "")
PASSWORD = os.environ.get("PSA_LOGIN_PW", "")
ENV_FILE = os.environ.get("PSA_ENV_FILE", "/etc/psa-tracker.env")
ACCT = os.environ.get("PSA_ACCT_ID", "account")  # used in logs + debug filenames
WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
# Persistent Chromium profile per account: PSA (Descope) trusts a device after one
# verification code, so keeping the profile means the code is asked once, not
# every run. Lives outside accounts/ so backup.sh doesn't tar ~100MB of cache.
PROFILE_DIR = os.path.join("/opt/psa-tracker/.profiles", ACCT)
# OTP hand-off markers, beside account.env (app.py's Settings page reads/writes
# them): otp.needed = login hit the code screen while unarmed; otp.armed = the owner
# pressed "Send code"; otp.waiting = the SMS went out, waiting for otp.code.
STATE_DIR = os.path.dirname(os.path.abspath(ENV_FILE))
def marker(name):
    return os.path.join(STATE_DIR, f"otp.{name}")
START_URL = "https://www.psacard.com/en-CA/myaccount/myorders"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
DEBUG_DIR = "/opt/psa-tracker/login_debug"


def log(m):
    print(f"[psa-login:{ACCT}] {m}", flush=True)


def write_cookie(cookie):
    """Replace (or add) the PSA_COOKIE line in the env file, preserving everything else."""
    quoted = shlex.quote(cookie)  # real shell quoting - no characters silently dropped
    try:
        lines = open(ENV_FILE).read().splitlines()
    except FileNotFoundError:
        lines = []
    out, found = [], False
    for ln in lines:
        if ln.startswith("PSA_COOKIE="):
            out.append("PSA_COOKIE=" + quoted); found = True
        else:
            out.append(ln)
    if not found:
        out.append("PSA_COOKIE=" + quoted)
    tmp = ENV_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(out) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, ENV_FILE)


def notify(text):
    if not WEBHOOK:
        return
    try:
        import json, urllib.request
        req = urllib.request.Request(WEBHOOK, data=json.dumps({"content": text}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        log(f"webhook failed: {e}")


def has_tokens(ctx):
    names = {c["name"] for c in ctx.cookies()}
    return "accessToken" in names and "refreshToken" in names


def mfa_flow(page, ctx):
    """PSA's 'Let's make sure it's you' screen (SMS code). Returns True once
    signed in, False to give up this run. Only sends the SMS when armed from
    Settings - an unarmed hourly run must not text the account's phone."""
    if not os.path.exists(marker("armed")):
        if not os.path.exists(marker("needed")):
            open(marker("needed"), "w").write(time.strftime("%Y-%m-%dT%H:%M"))
            notify(f"🔐 psa-tracker [{ACCT}]: PSA wants a verification code for this account. "
                   "Settings → Verification code → Send code, then enter the code it texts.")
        log("MFA screen and not armed - skipping (arm it from Settings)")
        return False
    for name in ("code", "waiting"):
        try: os.remove(marker(name))
        except FileNotFoundError: pass
    try:
        page.get_by_role("button", name="Continue").first.click()
    except Exception as e:
        log(f"MFA: no Continue button on the code screen ({e}) - staying armed, no code sent")
        return False
    page.wait_for_timeout(4000)
    page.screenshot(path=os.path.join(DEBUG_DIR, f"mfa_code_{ACCT}.png"))
    # the send is spent from here on, so drop the arm: a later failure this run
    # must not text the phone again on the next hourly login
    try: os.remove(marker("armed"))
    except FileNotFoundError: pass
    open(marker("waiting"), "w").write(time.strftime("%Y-%m-%dT%H:%M"))
    log("code requested - waiting up to 10 min for otp.code from Settings")
    notify(f"📲 psa-tracker [{ACCT}]: code sent to the account's phone - enter it in Settings within 10 min.")
    code = ""
    deadline = time.time() + 600
    while time.time() < deadline:
        if os.path.exists(marker("code")):
            code = open(marker("code")).read().strip()
            if code:  # empty means Settings is mid-write, not a spent code
                os.remove(marker("code"))
                break
        page.wait_for_timeout(3000)
    try: os.remove(marker("waiting"))
    except FileNotFoundError: pass
    if not code:
        log("no code arrived - giving up this run")
        return False
    # Descope passcode: one field or a row of digit boxes; typing into the first
    # covers both (the boxes auto-advance), and it usually auto-submits
    box = page.locator("input[autocomplete='one-time-code'], input[inputmode='numeric'], "
                       "input[type='tel'], input[type='text']").first
    box.wait_for(timeout=15000)
    box.click()
    page.keyboard.type(code, delay=80)
    page.wait_for_timeout(2500)
    if not has_tokens(ctx):
        for label in ("Continue", "Verify", "Submit"):
            try:
                page.get_by_role("button", name=label).first.click(timeout=2000); break
            except Exception:
                pass
    deadline = time.time() + 45
    while time.time() < deadline and not has_tokens(ctx):
        page.wait_for_timeout(1500)
    if not has_tokens(ctx):
        page.screenshot(path=os.path.join(DEBUG_DIR, f"mfa_fail_{ACCT}.png"))
        log("code entered but no session - wrong/expired code? (see login_debug/mfa_fail)")
        return False
    return True


def do_login():
    if not EMAIL or not PASSWORD:
        log("PSA_LOGIN_EMAIL / PSA_LOGIN_PW not set - aborting")
        return 2
    os.makedirs(DEBUG_DIR, exist_ok=True)
    os.makedirs(PROFILE_DIR, exist_ok=True)
    with sync_playwright() as p:
        def launch():
            return p.chromium.launch_persistent_context(
                PROFILE_DIR,
                headless=False,  # real headful browser under xvfb - beats Cloudflare bot mgmt
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                      "--disable-blink-features=AutomationControlled"],
                user_agent=UA, locale="en-CA", viewport={"width": 1366, "height": 900},
            )
        try:
            ctx = launch()
        except Exception as e:
            aside = f"{PROFILE_DIR}.broken.{int(time.time())}"
            log(f"profile will not open ({e}) - moving it to {aside} and retrying once")
            try: os.rename(PROFILE_DIR, aside)
            except OSError: pass
            os.makedirs(PROFILE_DIR, exist_ok=True)
            try:
                ctx = launch()
            except Exception as e2:
                log(f"ERROR: Chromium will not start even on a fresh profile: {e2}")
                return 1
        # mask the webdriver flag some bot checks look at
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            log("opening PSA (redirects to sign-in)…")
            page.goto(START_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)  # let SPA + any CF check settle
            got = has_tokens(ctx)  # persistent profile may still hold a live session
            if got:
                log("session still valid in the saved profile - no sign-in needed")
        except Exception as e:
            log(f"ERROR: {e}"); ctx.close(); return 1
        try:
            if not got:
                # --- email ---
                email_sel = ("input[type='email'], input[name='email'], input[name='username'], "
                             "input[autocomplete='username']")
                page.wait_for_selector(email_sel, timeout=45000)
                page.fill(email_sel, EMAIL)
                log("email entered")

                # some flows require advancing before the password field appears
                pw_sel = ("input[type='password'], input[name='password'], "
                          "input[autocomplete='current-password']")
                if page.query_selector(pw_sel) is None:
                    for label in ("Continue", "Next", "Sign in", "Log in"):
                        b = page.query_selector(f"button:has-text('{label}')")
                        if b:
                            b.click(); break
                    page.wait_for_timeout(1500)

                # --- password ---
                page.wait_for_selector(pw_sel, timeout=30000)
                page.fill(pw_sel, PASSWORD)
                log("password entered")
                # The password page's submit is a textless icon button, so submit via Enter,
                # with a type=submit / labeled-button fallback if we're still on the sign-in page.
                page.press(pw_sel, "Enter")
                page.wait_for_timeout(2500)
                try:  # the page may be mid-navigation here - a torn context is not a failure
                    if "signin" in page.url:
                        for sel in ("button[type='submit']", "button:has-text('Sign in')",
                                    "button:has-text('Continue')", "button:has-text('Log in')"):
                            el = page.query_selector(sel)
                            if el and el.is_enabled():
                                el.click()
                                break
                except Exception:
                    pass

                # --- SMS verification? (Descope renders in shadow DOM; get_by_text pierces it)
                page.wait_for_timeout(3000)
                try:
                    mfa = page.get_by_text("make sure it's you").first.is_visible()
                except Exception as e:
                    log(f"MFA check failed ({e}) - assuming no code screen")
                    mfa = False
                if mfa:
                    if not mfa_flow(page, ctx):
                        return 4
                    got = True

                # --- wait for authenticated session (accessToken cookie appears) ---
                deadline = time.time() + 75
                while not got and time.time() < deadline:
                    got = has_tokens(ctx)
                    page.wait_for_timeout(1500)
                if not got:
                    # nudge: navigate to the orders page once more
                    try:
                        page.goto(START_URL, wait_until="domcontentloaded", timeout=45000)
                        page.wait_for_timeout(3000)
                    except Exception:
                        pass
                    names = {c["name"] for c in ctx.cookies()}
                    got = "accessToken" in names and "refreshToken" in names

                if not got:
                    page.screenshot(path=os.path.join(DEBUG_DIR, f"login_fail_{ACCT}.png"))
                    log(f"FAILED: no accessToken/refreshToken after login (see login_debug/login_fail_{ACCT}.png)")
                    return 1

            # harvest the psacard.com cookie header
            cookies = [c for c in ctx.cookies() if "psacard.com" in c["domain"]]
            header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
            have = {c["name"] for c in cookies}
            if "accessToken" not in have:  # cookies may sit on the collectors domain
                cookies = ctx.cookies()
                header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
            write_cookie(header)
            log(f"SUCCESS: refreshed cookie ({len(cookies)} cookies) -> {ENV_FILE}")
            for name in ("armed", "needed"):
                try: os.remove(marker(name))
                except FileNotFoundError: pass
            return 0
        except Exception as e:
            try:
                page.screenshot(path=os.path.join(DEBUG_DIR, f"login_error_{ACCT}.png"))
            except Exception:
                pass
            log(f"ERROR: {e}")
            return 1
        finally:
            ctx.close()


if __name__ == "__main__":
    sys.exit(do_login())
