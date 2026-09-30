# psa-tracker

A tiny self-hosted website that tracks PSA card-grading submissions so the
friends you grade for can watch their cards move through PSA's pipeline -
Arrived → Order Prep → Research & ID → Grading → Assembly → QA Check →
Completing → Shipped.

- **Password gate, zero user accounts.** You hand each group of friends one
  password. Whichever password someone types routes them to the matching PSA
  account's dashboard - the account chooser is invisible by design.
- **Multi-account.** One instance can track any number of PSA accounts
  (`accounts/<id>/`), each with its own data, its own friends password, its own
  owner tags.
- **Fully automatic.** Scans run hourly reusing the stored session; twice a
  day (and whenever the cookie dies) a real Chromium (headful under `xvfb`)
  re-logs into PSA for a fresh one. No manual cookie copying, ever.
- **Card galleries with images** - including *before* PSA assigns cert numbers
  (pulled from the submission's spec images), duplicate-aware (a line with
  qty 34 renders 34 tiles), with owner tagging, per-person pages, estimated
  grading cost, live search, and per-submission archiving.
- **Card values** (optional, `PSA_VALUES=1`) - `psa_values.py` reads each graded
  card's recent sales at its grade from PSA's own sales data (the psacard.com
  spec page API, on the scanner's session) and shows the latest in CAD.
- **No frameworks.** Python stdlib web server + SQLite + one scraper. The only
  deps are `curl_cffi` (TLS fingerprint impersonation) and `playwright`
  (the twice-daily login).

## Architecture

```
psa-scan.timer (systemd, hourly)
  └─ run_scan.sh                 for each accounts/<id>/:
       ├─ psa_login.py           real Chromium (xvfb) logs into PSA → fresh cookie → account.env
       ├─ psa_watch.py --once    scrape orders + card images → accounts/<id>/psa.db
       └─ psa_values.py          PSA_VALUES=1: sales values (new certs every scan, refresh + USDCAD on login hours) → psa.db

psa-backup.timer (systemd, nightly 04:15)
  └─ backup.sh                   accounts/ + global env + units → backups/auto-*.tar.gz

psa-web.service
  └─ app.py                      reads psa.db, writes owners.db (tags/archive)
                                 password-routed sessions, image proxy+cache
```

Per-account files (`/opt/psa-tracker/accounts/<id>/`):

| file | what |
|---|---|
| `account.env` | LABEL, SITE_PASSWORD, PSA login creds, current cookie (chmod 600) |
| `psa.db` | scraper-owned: subs, cards, status history |
| `owners.db` | app-owned: owner tags, archived subs |

## Install (Debian 12, ~1 GB RAM incl. swap)

```bash
# 1. code
mkdir -p /opt/psa-tracker && cp app.py psa_common.py psa_watch.py psa_login.py psa_values.py \
  run_scan.sh add_account.sh backup.sh /opt/psa-tracker/
chmod +x /opt/psa-tracker/run_scan.sh /opt/psa-tracker/add_account.sh /opt/psa-tracker/backup.sh

# 2. deps
pip install --break-system-packages curl_cffi playwright
export PLAYWRIGHT_BROWSERS_PATH=/opt/psa-tracker/.pw-browsers
playwright install-deps chromium && playwright install chromium
apt-get install -y xvfb xauth

# 3. global config
cp deploy/example.env /etc/psa-tracker.env   # then EDIT it (PSA_SECRET etc.)
chmod 600 /etc/psa-tracker.env

# 4. first account - EITHER of:
#    a) skip this step: with no accounts yet, the site serves a one-time
#       setup page at / (site password + PSA login) and kicks the first
#       scan itself once you submit it. The page disappears for good after
#       the first successful PSA sign-in.
#    b) the CLI way:
/opt/psa-tracker/add_account.sh

# 5. services
cp deploy/psa-web.service deploy/psa-scan.service deploy/psa-scan.timer \
   deploy/psa-backup.service deploy/psa-backup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now psa-web.service psa-scan.timer psa-backup.timer
systemctl start psa-scan.service   # first scan now instead of waiting for the timer
# The timer fires hourly; a real browser login only happens at 1am/1pm
# (PSA_LOGIN_HOURS) or when the stored cookie dies - other runs reuse it.
# Optional: PSA_SETTINGS_PW_HASH (sha256 of a settings password) in the global
# env enables /settings - web UI for updating PSA credentials (write-only),
# per-account Discord webhooks and adding accounts. Anyone's person page can
# link a Discord user ID to get @-mentioned on updates to their subs.
```

Put a TLS reverse proxy (Caddy, nginx, Cloudflare tunnel…) in front of
`:8080`. If you really must serve plain HTTP, set `PSA_COOKIE_SECURE=0`.

## Adding another PSA account

```bash
/opt/psa-tracker/add_account.sh
```

Pick a unique site password - that password *is* the account selector. The
account works for web login immediately; its first scan runs at the next timer
tick (or `systemctl start psa-scan.service`).

## Configuration

Every key the code reads, global and per-account, is listed with its default and
a one-line note in [`deploy/example.env`](deploy/example.env). Copy it to
`/etc/psa-tracker.env` and edit; per-account keys go in
`accounts/<id>/account.env`, which `add_account.sh` writes.

Each person's page also shows **INSURED COVERAGE** - the sum of the real
per-card declared values PSA has on file (captured automatically from the
submission data; no configuration needed).

## Branding

Two accent colors drive the whole palette: `PSA_ACCENT` + `PSA_ACCENT_2`
(validated hex, global env) plus `PSA_THEME=light|dark` for the default theme
(visitors can flip it per-browser with the corner toggle).

**Logo**: drop a file at `/opt/psa-tracker/logo.svg` (or `.png`/`.jpg`; path
override `PSA_LOGO`) and it appears on the gate and beside the dashboard title,
served at `/logo` - no restart needed. For marks that assume a light
background: `PSA_LOGO_CHIP=1` renders it on a white rounded backing in dark
mode, or `PSA_LOGO_DARK=silhouette` recolors it as a white mark.

**Favicon**: an accent-colored SVG favicon is built in and needs no files -
but Safari and iOS ignore SVG favicons and show a domain-letter tile instead.
Fix: pre-render two PNGs of your mark and drop them next to the app -
`favicon.png` (~64px, shown in tabs) and `apple-touch-icon.png` (180px,
square corners; iOS rounds them itself). When present they're linked and
served automatically at `/favicon.png`, `/favicon.ico` and
`/apple-touch-icon.png` (path overrides `PSA_FAVICON` / `PSA_TOUCH_ICON`);
restart `psa-web` after adding them. Any SVG-to-PNG renderer works
(macOS: `qlmanage -t -s 64 -o . icon.svg`).

## Operations

```bash
journalctl -u psa-scan -f        # login + scan logs
journalctl -u psa-web -f         # site logs
systemctl start psa-scan.service # scan all accounts now
python3 psa_watch.py --once --full  # force full refresh (with account env loaded)
```

- Scans skip detail-fetching submissions that were already Shipped and fully
  imaged (they can't change). `--full` overrides.
- If the PSA login page changes and auto-login breaks, screenshots land in
  `login_debug/` and the scan falls back to the previous cookie. You can always
  paste a fresh browser cookie into the account's `account.env` (`PSA_COOKIE=`)
  as a stopgap.
- If PSA asks for an SMS verification code the login parks and Discord pings:
  open **Settings → Verification code**, press **Send code**, then type the code
  it texts into the same panel. The waiting login finishes the sign-in.
- Backups: `deploy/psa-backup.timer` + `backup.sh` snapshot accounts/ (DBs +
  env), the global env and the unit files nightly at 04:15, keeping the newest
  3 under `backups/auto-*` (imgcache is excluded - it refetches itself). For
  bigger one-off snapshots, tar `/opt/psa-tracker` (minus `.pw-browsers`) +
  `/etc/psa-tracker.env` + the systemd units by hand.

## Security notes

- PSA credentials + cookies live only in chmod-600 files on the box.
- Session cookies are HMAC-signed (`PSA_SECRET`), HttpOnly, SameSite=Lax,
  Secure (unless disabled). Login has a per-IP throttle (8 fails / 15 min).
- The image proxy is locked to PSA's CloudFront host, size-capped, and caches
  atomically. PSA accounts with SMS 2FA work: auto-login hands the code screen
  off to the **Verification code** panel in /settings (see Operations).
- The `submissions.completed` PSA endpoint returns payment/address PII - the
  scraper extracts only the card lines and never stores the rest.

## Notes on PSA scraping

Auth is cookie-only (Bearer silently returns nothing) and Cloudflare gates on
TLS fingerprint, hence `curl_cffi ... impersonate="chrome"`. The OAuth client
is confidential (secret is server-side), so tokens can't be minted from the
refresh token - that's why cookie refresh drives a real browser through the
sign-in page instead. See `psa_watch.py` for the full API field maps.
