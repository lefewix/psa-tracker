#!/bin/bash
# For each tracked account: scan its submissions, refreshing the PSA cookie via
# a real browser login only when needed. Scheduled HOURLY by psa-scan.timer
# (since 2026-07-22). The full browser login runs at the PSA_LOGIN_HOURS slots
# (default 1am/1pm local), when the cookie is empty, or when a scan comes back
# cookie-dead (psa_watch exit 3) - every other run reuses the existing cookie,
# keeping the bot-detection surface at ~2 logins/day. Card values + fx refresh
# only on login-hour runs (they change slowly; hourly runs stay lean).
#
# Failure alerting (2026-07-22): a run whose scan ends non-zero bumps
# $dir/.scan_fails; at PSA_ALERT_AFTER consecutive failures (default 3) the
# account's Discord webhook gets ONE warning ping, and one recovery ping when
# scans come back. A broken PSA login page no longer fails silently.
#
# Env layering: global /etc/psa-tracker.env first, then the account's
# account.env on top (account wins). PSA_DB/PSA_OWN_DB point the scraper at
# that account's databases; PSA_ENV_FILE tells psa_login.py where to write the
# fresh cookie.
export PLAYWRIGHT_BROWSERS_PATH=/opt/psa-tracker/.pw-browsers
GLOBAL=/etc/psa-tracker.env
ACCTS=/opt/psa-tracker/accounts
LOGIN_HOURS=${PSA_LOGIN_HOURS:-"01 13"}
hour=$(TZ=${PSA_TZ:-America/Toronto} date +%H)
shopt -s nullglob
found=0
for envf in "$ACCTS"/*/account.env; do
  found=1
  dir=$(dirname "$envf"); id=$(basename "$dir")
  echo "[run_scan] $(date -Is) === account: $id (hour $hour) ==="
  (
    set -a; . "$GLOBAL"; . "$envf"; set +a
    export PSA_ENV_FILE="$envf" PSA_ACCT_ID="$id" PSA_DB="$dir/psa.db" PSA_OWN_DB="$dir/owners.db"

    alert() {  # $1 = message; uses the layered DISCORD_WEBHOOK, never fatal
      [ -n "${DISCORD_WEBHOOK:-}" ] || return 0
      python3 - "$DISCORD_WEBHOOK" "$1" <<'PYEOF'
import json, sys, urllib.request
try:
    req = urllib.request.Request(sys.argv[1],
        data=json.dumps({"content": sys.argv[2]}).encode(),
        headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=15).read()
except Exception:
    pass
PYEOF
    }

    full=0
    case " $LOGIN_HOURS " in *" $hour "*) full=1 ;; esac
    [ -z "$PSA_COOKIE" ] && full=1
    if [ "$full" = 1 ]; then
      if xvfb-run -a python3 /opt/psa-tracker/psa_login.py; then
        set -a; . "$envf"; set +a   # reload: pick up the fresh PSA_COOKIE
      else
        echo "[run_scan] $id: login failed - scanning with existing cookie"
      fi
    fi
    python3 /opt/psa-tracker/psa_watch.py --once "$@"
    rc=$?
    if [ "$rc" = 3 ] && [ "$full" = 0 ]; then
      echo "[run_scan] $id: cookie looks dead - browser login + rescan"
      if xvfb-run -a python3 /opt/psa-tracker/psa_login.py; then
        set -a; . "$envf"; set +a
        python3 /opt/psa-tracker/psa_watch.py --once "$@"
        rc=$?
      fi
    fi

    # consecutive-failure counter -> one warning ping, one recovery ping
    FAILF="$dir/.scan_fails"
    if [ "$rc" = 0 ]; then
      if [ -f "$FAILF" ]; then
        n=$(cat "$FAILF" 2>/dev/null || echo 0)
        [ "$n" -ge "${PSA_ALERT_AFTER:-3}" ] 2>/dev/null && \
          alert "✅ psa-tracker [$id]: scans recovered after $n failed runs."
        rm -f "$FAILF"
      fi
    else
      n=$(( $(cat "$FAILF" 2>/dev/null || echo 0) + 1 ))
      echo "$n" > "$FAILF"
      echo "[run_scan] $id: scan failed (rc=$rc), consecutive failures: $n"
      if [ "$n" = "${PSA_ALERT_AFTER:-3}" ]; then
        alert "⚠️ psa-tracker [$id]: $n scans in a row have failed (rc=$rc). Check: journalctl -u psa-scan · screenshots in login_debug/."
      fi
    fi

    # Card market values (PSA_VALUES=1 in the env enables; remove to disable).
    # Public cert pages, so failures never block the scan.
    if [ "$full" = 1 ] && [ "${PSA_VALUES:-0}" = "1" ]; then
      xvfb-run -a python3 /opt/psa-tracker/psa_values.py \
        || echo "[run_scan] $id: values fetch failed (non-fatal)"
    fi
  )
done
[ "$found" = 1 ] || echo "[run_scan] no accounts found in $ACCTS - run add_account.sh"
echo "[run_scan] $(date -Is) all accounts done"
