<div align="center">

<img src="logo.svg" width="88" alt="psa-tracker logo">

# psa-tracker

**A self-hosted dashboard that lets your friends or customers watch their cards move through PSA grading.**

![Linux](https://img.shields.io/badge/Linux-Debian_12-A81D33?style=flat-square&logo=debian&logoColor=white)
![Python](https://img.shields.io/badge/Python-stdlib-3776AB?style=flat-square&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)

</div>

If you submit cards to PSA for other people, they keep asking "where are my cards?". psa-tracker signs into
your PSA account, follows every submission through PSA's stages (Arrived → Order Prep → Research & ID →
Grading → Assembly → QA Check → Completing → Shipped) and shows it on a simple password-protected website.

## Features

- **No user accounts**: give each group one password; the password decides which dashboard they see
- **Multi-account**: one install can track any number of PSA accounts
- **Fully automatic**: hourly scans, with a real browser re-login twice a day when the session expires
- **Card galleries**: images even before cert numbers exist, owner tags, per-person pages and live search
- **Card values** (optional): recent sales at each card's grade, shown in CAD
- **Discord alerts**: per-account webhooks and @-mentions when someone's cards move
- **Your branding**: one accent colour, light/dark theme, your own logo and favicon
- **No frameworks**: Python standard library web server + SQLite

## Install

Needs a small Debian 12 box (~1 GB RAM including swap).

```bash
# 1. code
mkdir -p /opt/psa-tracker && cp app.py psa_common.py psa_watch.py psa_login.py psa_values.py \
  run_scan.sh add_account.sh backup.sh /opt/psa-tracker/
chmod +x /opt/psa-tracker/{run_scan,add_account,backup}.sh

# 2. dependencies
pip install --break-system-packages curl_cffi playwright
export PLAYWRIGHT_BROWSERS_PATH=/opt/psa-tracker/.pw-browsers
playwright install-deps chromium && playwright install chromium
apt-get install -y xvfb xauth

# 3. config: copy, then edit (at least PSA_SECRET)
cp deploy/example.env /etc/psa-tracker.env && chmod 600 /etc/psa-tracker.env

# 4. services
cp deploy/psa-*.service deploy/psa-*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now psa-web.service psa-scan.timer psa-backup.timer
```

Put a TLS reverse proxy (Caddy, nginx, Cloudflare Tunnel…) in front of port `8080`.

## Usage

1. Open the site. With no accounts yet, it shows a one-time setup page: pick a site password and enter your
   PSA login. The first scan starts right away.
2. Share the site password with the people you grade for
3. Add more PSA accounts any time with `/opt/psa-tracker/add_account.sh`. Each one gets its own password.

## How it works

```
psa-scan.timer (hourly)
  └─ run_scan.sh                 for each accounts/<id>/:
       ├─ psa_login.py           real Chromium (xvfb) signs into PSA → fresh cookie
       ├─ psa_watch.py --once    orders + card images → accounts/<id>/psa.db
       └─ psa_values.py          optional: recent sales values → psa.db

psa-backup.timer (nightly)
  └─ backup.sh                   accounts + config + units → backups/auto-*.tar.gz

psa-web.service
  └─ app.py                      reads psa.db, writes owners.db (tags, archive)
                                 password-routed sessions, image proxy + cache
```

Each account lives in `accounts/<id>/`: `account.env` (label, site password, PSA login and cookie, chmod
600), `psa.db` (written by the scanner) and `owners.db` (written by the web app).

<details>
<summary><b>Configuration and branding</b></summary>

Every setting the code reads is listed with its default in [`deploy/example.env`](deploy/example.env).
Global settings go in `/etc/psa-tracker.env`; per-account ones in `accounts/<id>/account.env`.

- **Settings page**: set `PSA_SETTINGS_PW_HASH` (sha256 of a password) to enable `/settings`, for updating
  PSA credentials, Discord webhooks and adding accounts from the browser.
- **Colours**: `PSA_ACCENT` (one hex colour drives the whole palette) and `PSA_THEME=light|dark`.
- **Logo**: drop `logo.svg` (or `.png`/`.jpg`) next to the app. `PSA_LOGO_CHIP=1` puts it on a white backing
  in dark mode; `PSA_LOGO_DARK=silhouette` turns it white.
- **Favicon**: an accent-coloured SVG is built in. For Safari and iOS, add `favicon.png` (64 px) and
  `apple-touch-icon.png` (180 px) next to the app and restart `psa-web`.
- **Plain HTTP** (not recommended): `PSA_COOKIE_SECURE=0`.

The included `logo.svg` and favicons are example branding; replace them with your own.

</details>

<details>
<summary><b>Operations</b></summary>

```bash
journalctl -u psa-scan -f            # login + scan logs
journalctl -u psa-web -f             # site logs
systemctl start psa-scan.service     # scan all accounts now
python3 psa_watch.py --once --full   # force a full refresh (with the account env loaded)
PSA_HOST=root@your-server ./deploy.sh app.py   # checked, staged deploy from your machine
```

- Shipped and fully imaged submissions are skipped on later scans (`--full` overrides).
- If PSA's login page changes, screenshots land in `login_debug/` and the scan keeps using the previous
  cookie. You can paste a fresh browser cookie into `account.env` (`PSA_COOKIE=`) as a stopgap.
- If PSA asks for an SMS code, the login waits and Discord pings you: open **Settings → Verification code**,
  press **Send code** and type in the code.
- Backups run nightly and keep the newest 3 (the image cache is skipped; it refetches itself).

</details>

<details>
<summary><b>Security</b></summary>

- PSA credentials and cookies live only in chmod-600 files on the server.
- Session cookies are HMAC-signed (`PSA_SECRET`), HttpOnly, SameSite=Lax and Secure. Login is throttled per
  IP (8 failures per 15 minutes).
- The image proxy only fetches from PSA's image host, is size-capped and caches atomically.
- PSA's completed-submissions data includes payment and address details; the scanner keeps only the card
  lines and never stores the rest.

</details>

<details>
<summary><b>Notes on PSA's API</b></summary>

PSA's site is cookie-authenticated and sits behind Cloudflare, which checks the TLS fingerprint, so requests
use `curl_cffi` with Chrome impersonation. Tokens can't be refreshed directly, so a real browser signs in
through the normal login page when the cookie expires. `psa_watch.py` has the full field maps. This only
reads your own account's data.

</details>

## Development

```bash
python3 scripts/smoke.py    # boots app.py on a throwaway fixture and checks every route; no network
```

[`DESIGN.md`](DESIGN.md) is the design record: layout, colour and typography decisions and why they were made.

## License

[MIT](LICENSE) © Felix Wang
