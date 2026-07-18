#!/usr/bin/env python3
"""psa-login: automated cookie refresh via a real browser.

PSA/Collectors auth is a confidential OAuth2 client (secret lives server-side), so the
scraper can't mint tokens itself. Instead we log in the way a human does — drive a real
Chromium (headful, under xvfb, to pass Cloudflare) through the collectors.com sign-in,
then harvest the fresh psacard.com cookie and write it into /etc/psa-tracker.env.

Runs before each scheduled scan so PSA_COOKIE never goes stale.

Env (from /etc/psa-tracker.env):
  PSA_LOGIN_EMAIL, PSA_LOGIN_PW   required — the PSA/Collectors account login.
      NOTE: deliberately NOT PSA_PASSWORD — that name is the site's friends-gate password
      (read by app.py). Keep these separate or you'll clobber the site login.
  PSA_ENV_FILE              default /etc/psa-tracker.env  (where PSA_COOKIE is written)
  PLAYWRIGHT_BROWSERS_PATH  set by the wrapper to /opt/psa-tracker/.pw-browsers
"""
import os, sys, time
from playwright.sync_api import sync_playwright

EMAIL = os.environ.get("PSA_LOGIN_EMAIL", "")
PASSWORD = os.environ.get("PSA_LOGIN_PW", "")
ENV_FILE = os.environ.get("PSA_ENV_FILE", "/etc/psa-tracker.env")
ACCT = os.environ.get("PSA_ACCT_ID", "account")  # used in logs + debug filenames
START_URL = "https://www.psacard.com/en-CA/myaccount/myorders"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
DEBUG_DIR = "/opt/psa-tracker/login_debug"


def log(m):
    print(f"[psa-login:{ACCT}] {m}", flush=True)


def write_cookie(cookie):
    """Replace (or add) the PSA_COOKIE line in the env file, preserving everything else."""
    cookie = cookie.replace("'", "")  # keep the single-quoted env value shell-safe
    try:
        lines = open(ENV_FILE).read().splitlines()
    except FileNotFoundError:
        lines = []
    out, found = [], False
    for ln in lines:
        if ln.startswith("PSA_COOKIE="):
            out.append("PSA_COOKIE='" + cookie + "'"); found = True
        else:
            out.append(ln)
    if not found:
        out.append("PSA_COOKIE='" + cookie + "'")
    tmp = ENV_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(out) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, ENV_FILE)


def do_login():
    if not EMAIL or not PASSWORD:
        log("PSA_LOGIN_EMAIL / PSA_LOGIN_PW not set — aborting")
        return 2
    os.makedirs(DEBUG_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # real headful browser under xvfb — beats Cloudflare bot mgmt
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                  "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(user_agent=UA, locale="en-CA",
                                  viewport={"width": 1366, "height": 900})
        # mask the webdriver flag some bot checks look at
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()
        try:
            log("opening PSA (redirects to sign-in)…")
            page.goto(START_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)  # let SPA + any CF check settle

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
            if "signin" in page.url:
                for sel in ("button[type='submit']", "button:has-text('Sign in')",
                            "button:has-text('Continue')", "button:has-text('Log in')"):
                    el = page.query_selector(sel)
                    if el and el.is_enabled():
                        try:
                            el.click()
                        except Exception:
                            pass
                        break

            # --- wait for authenticated session (accessToken cookie appears) ---
            deadline = time.time() + 75
            got = False
            while time.time() < deadline:
                names = {c["name"] for c in ctx.cookies()}
                if "accessToken" in names and "refreshToken" in names:
                    got = True; break
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
            return 0
        except Exception as e:
            try:
                page.screenshot(path=os.path.join(DEBUG_DIR, f"login_error_{ACCT}.png"))
            except Exception:
                pass
            log(f"ERROR: {e}")
            return 1
        finally:
            ctx.close(); browser.close()


if __name__ == "__main__":
    sys.exit(do_login())
