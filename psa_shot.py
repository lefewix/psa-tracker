#!/usr/bin/env python3
"""psa-shot: render one submission's dashboard card to a PNG, for Discord posts.

    psa_shot.py SUB_NUMBER OUT.png

Uses the site's own renderer on 127.0.0.1 (no Cloudflare, no xvfb): mints a
session cookie for the universal dashboard the same way /login does, opens /,
and screenshots `.card[data-sub=SUB]`. Env, as run_scan.sh exports it:
PSA_SECRET, PSA_ACCT_ID, PSA_MERGE_INTO (the account dir holding the universal
db; falls back to PSA_ACCT_ID), PSA_ACCOUNTS_DIR, PSA_WEB_PORT.
"""
import hashlib, hmac, os, sys, time
from playwright.sync_api import sync_playwright

ACCTS = os.environ.get("PSA_ACCOUNTS_DIR", "/opt/psa-tracker/accounts")
PORT = os.environ.get("PSA_WEB_PORT", "8080")
SECRET = os.environ.get("PSA_SECRET", "").encode()


def site_password(acct_id):
    for ln in open(os.path.join(ACCTS, acct_id, "account.env")):
        if ln.startswith("SITE_PASSWORD="):
            v = ln.split("=", 1)[1].strip()
            return v[1:-1] if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"" else v
    return ""


def session_cookie(acct_id):
    # mirrors app.py make_token(): acct.exp.sig over acct.exp.<sha256(site pw)[:8]>
    exp = int(time.time()) + 300
    slug = hashlib.sha256(site_password(acct_id).encode()).hexdigest()[:8]
    sig = hmac.new(SECRET, f"{acct_id}.{exp}.{slug}".encode(), hashlib.sha256).hexdigest()
    return f"{acct_id}.{exp}.{sig}"


def shoot(sub, out):
    acct = os.environ.get("PSA_MERGE_INTO") or os.environ.get("PSA_ACCT_ID", "")
    if not acct or not SECRET:
        raise SystemExit("PSA_ACCT_ID/PSA_MERGE_INTO and PSA_SECRET are required")
    with sync_playwright() as p:
        # channel="chromium": new headless mode of the full build psa_login uses (the
        # separate headless shell is not installed on the box)
        b = p.chromium.launch(headless=True, channel="chromium",
                              args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = b.new_context(viewport={"width": 900, "height": 900}, device_scale_factor=2)
        ctx.add_cookies([{"name": "psa_session", "value": session_cookie(acct),
                          "domain": "127.0.0.1", "path": "/"}])
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle", timeout=45000)
        card = page.locator(f'.card[data-sub="{sub}"]').first
        card.wait_for(timeout=15000)
        card.scroll_into_view_if_needed()
        page.wait_for_timeout(600)  # let the lazy scans in the strip paint
        card.screenshot(path=out)
        ctx.close(); b.close()


if __name__ == "__main__":
    shoot(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else f"/tmp/psa-{sys.argv[1]}.png")
