# psa-tracker

A tiny self-hosted website that tracks PSA card-grading submissions so the
friends you grade for can watch their cards move through PSA's pipeline -
Arrived → Order Prep → Research & ID → Grading → Assembly → QA Check → Shipped.

- **Password gate, zero user accounts.** You hand each group of friends one
  password. Whichever password someone types routes them to the matching PSA
  account's dashboard - the account chooser is invisible by design.
- **Multi-account.** One instance can track any number of PSA accounts
  (`accounts/<id>/`), each with its own data, its own friends password, its own
  owner tags.
- **Fully automatic.** Twice a day a real headless browser logs into PSA,
  refreshes the session cookie, and scans. No manual cookie copying, ever.
- **Card galleries with images** - including *before* PSA assigns cert numbers
  (pulled from the submission's spec images), duplicate-aware (a line with
  qty 34 renders 34 tiles), with owner tagging, per-person pages, estimated
  grading cost, live search, and per-submission archiving.
- **No frameworks.** Python stdlib web server + SQLite + one scraper. The only
  deps are `curl_cffi` (TLS fingerprint impersonation) and `playwright`
  (the twice-daily login).

## Architecture

```
psa-scan.timer (systemd, 2×/day)
  └─ run_scan.sh                 for each accounts/<id>/:
       ├─ psa_login.py           real Chromium (xvfb) logs into PSA → fresh cookie → account.env
       └─ psa_watch.py --once    scrape orders + card images → accounts/<id>/psa.db

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
mkdir -p /opt/psa-tracker && cp app.py psa_watch.py psa_login.py run_scan.sh add_account.sh /opt/psa-tracker/
chmod +x /opt/psa-tracker/run_scan.sh /opt/psa-tracker/add_account.sh

# 2. deps
pip install --break-system-packages curl_cffi playwright
export PLAYWRIGHT_BROWSERS_PATH=/opt/psa-tracker/.pw-browsers
playwright install-deps chromium && playwright install chromium
apt-get install -y xvfb xauth

# 3. global config
cp deploy/example.env /etc/psa-tracker.env   # then EDIT it (PSA_SECRET etc.)
chmod 600 /etc/psa-tracker.env

# 4. first account
/opt/psa-tracker/add_account.sh

# 5. services
cp deploy/psa-web.service deploy/psa-scan.service deploy/psa-scan.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now psa-web.service psa-scan.timer
systemctl start psa-scan.service   # first scan now instead of waiting for the timer
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

Global (`/etc/psa-tracker.env`): `PSA_SECRET` (required), `PSA_BIND`,
`PSA_PORT`, `SITE_TITLE`, `SITE_TAGLINE`, `PSA_COOKIE_SECURE`, `PSA_DISPLAY_TZ` (IANA name for displayed times, default America/Toronto), `PSA_LOCALE` /
`PSA_LOCATION` (US accounts: `en-US` / `US`), `DISCORD_WEBHOOK` (optional
status-change pings).

Per-account (`account.env`): `LABEL`, `SITE_PASSWORD`, `PSA_LOGIN_EMAIL`,
`PSA_LOGIN_PW`, optional `PSA_PRICES` fee table
(`"regular:109,max:89.99,bulk:34.99,value:45.99"`, matched most-specific-first)
used for the per-person estimated-cost badge.

Each person's page also shows **INSURED COVERAGE** - the sum of the real
per-card declared values PSA has on file (captured automatically from the
submission data; no configuration needed).

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
- Back up by tarring `/opt/psa-tracker` (minus `.pw-browsers`) +
  `/etc/psa-tracker.env` + the systemd units.

## Security notes

- PSA credentials + cookies live only in chmod-600 files on the box.
- Session cookies are HMAC-signed (`PSA_SECRET`), HttpOnly, SameSite=Lax,
  Secure (unless disabled). Login has a per-IP throttle (8 fails / 15 min).
- The image proxy is locked to PSA's CloudFront host, size-capped, and caches
  atomically. The 2FA-less PSA account is assumed; enable at your own risk of
  breaking auto-login.
- The `submissions.completed` PSA endpoint returns payment/address PII - the
  scraper extracts only the card lines and never stores the rest.

## Notes on PSA scraping

Auth is cookie-only (Bearer silently returns nothing) and Cloudflare gates on
TLS fingerprint, hence `curl_cffi ... impersonate="chrome"`. The OAuth client
is confidential (secret is server-side), so tokens can't be minted from the
refresh token - that's why cookie refresh drives a real browser through the
sign-in page instead. See `HANDOFF.md` for the full API field maps.
