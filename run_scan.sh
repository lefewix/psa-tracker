#!/bin/bash
# For each tracked account: scan its submissions, refreshing the PSA cookie via
# a real browser login only when needed. Scheduled HOURLY by psa-scan.timer
# (since 2026-07-22). The full browser login runs at the PSA_LOGIN_HOURS slots
# (default 1am/1pm local), when the cookie is empty, or when a scan comes back
# cookie-dead (psa_watch exit 3) - every other run reuses the existing cookie,
# keeping the bot-detection surface at ~2 logins/day. Card values + fx refresh
# only on successful login-hour runs (they change slowly; hourly runs stay lean).
#
# Login backoff (2026-09-10): an account whose scans keep failing used to burn a
# browser login every single hour. Past PSA_LOGIN_BACKOFF_AFTER consecutive
# failures (default 3) only the PSA_LOGIN_HOURS slots and an armed OTP still log
# in, and an account sitting at otp.needed without otp.armed never does - PSA is
# waiting on an SMS code no login can supply.
#
# Failure alerting (2026-07-22): a run whose scan ends non-zero bumps
# $dir/.scan_fails; at PSA_ALERT_AFTER consecutive failures (default 3) the
# account's Discord webhook gets a warning ping, repeated every 24 runs while it
# stays broken, and one recovery ping when scans come back. A broken PSA login
# page no longer fails silently.
#
# Time budget (2026-09-10): every browser/scan call runs under `timeout`, so one
# hung account cannot eat the whole run. Login 600s (900s while otp.armed - the
# code screen itself waits up to 10 min), scan 420s, values 420s. Worst case per
# account is ~29 min; psa-scan.service's TimeoutStartSec covers the fleet.
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
    if [ "${UNLINKED:-}" = "1" ]; then
      # unlinked via settings: site keeps serving the last known data, we stop
      # touching PSA for it (and never trip the failure alert)
      echo "[run_scan] $id: unlinked - skipping"
      exit 0
    fi
    # PSA_MERGE_INTO=<account id> (global or per account): this account's subs,
    # cards, owners and values land in THAT account's databases, so one site
    # password shows every PSA account. The target itself resolves to its own dir.
    ddir="$dir"
    if [ -n "${PSA_MERGE_INTO:-}" ] && [ "$PSA_MERGE_INTO" != "$id" ] && [ -d "$ACCTS/$PSA_MERGE_INTO" ]; then
      ddir="$ACCTS/$PSA_MERGE_INTO"
    fi
    export PSA_ENV_FILE="$envf" PSA_ACCT_ID="$id" PSA_DB="$ddir/psa.db" PSA_OWN_DB="$ddir/owners.db"

    alert() {  # $1 = message; uses the layered DISCORD_WEBHOOK, never fatal
      if [ -z "${DISCORD_WEBHOOK:-}" ]; then
        echo "[run_scan] $id: no DISCORD_WEBHOOK set, alert not delivered: $1"
        return 0
      fi
      python3 - "$DISCORD_WEBHOOK" "$1" <<'PYEOF'
import json, sys, urllib.request
try:
    req = urllib.request.Request(sys.argv[1],
        data=json.dumps({"content": sys.argv[2]}).encode(),
        headers={"Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"})
    urllib.request.urlopen(req, timeout=15).read()
except Exception as e:
    print("[run_scan] alert delivery failed: %r" % (e,), file=sys.stderr)
PYEOF
    }

    slot=0
    case " $LOGIN_HOURS " in *" $hour "*) slot=1 ;; esac
    fails=$(cat "$dir/.scan_fails" 2>/dev/null || echo 0)
    case "$fails" in ''|*[!0-9]*) fails=0 ;; esac
    may_login=1
    if [ "$slot" = 0 ] && [ "$fails" -ge "${PSA_LOGIN_BACKOFF_AFTER:-3}" ] && [ ! -f "$dir/otp.armed" ]; then
      may_login=0; why="$fails failed scans in a row, next login at hour(s) $LOGIN_HOURS"
    fi
    if [ -f "$dir/otp.needed" ] && [ ! -f "$dir/otp.armed" ]; then
      may_login=0; why="PSA wants an SMS code - arm one in Settings"
    fi

    # a login that is going to sit on the code screen needs the 10 min OTP wait
    login_budget=600
    [ -f "$dir/otp.armed" ] && login_budget=900

    full=$slot
    [ -z "$PSA_COOKIE" ] && full=1
    [ -f "$dir/otp.armed" ] && full=1   # "Send code" pressed in Settings
    if [ "$full" = 1 ] && [ "$may_login" = 0 ]; then
      echo "[run_scan] $id: skipping login ($why)"
      full=0
    fi
    if [ "$full" = 1 ]; then
      if timeout "$login_budget" xvfb-run -a python3 /opt/psa-tracker/psa_login.py; then
        set -a; . "$envf"; set +a   # reload: pick up the fresh PSA_COOKIE
      else
        echo "[run_scan] $id: login failed - scanning with existing cookie"
      fi
    fi
    timeout 420 python3 /opt/psa-tracker/psa_watch.py --once "$@"
    rc=$?
    if [ "$rc" = 3 ] && [ "$full" = 0 ]; then
      if [ "$may_login" = 1 ]; then
        echo "[run_scan] $id: cookie looks dead - browser login + rescan"
        if timeout "$login_budget" xvfb-run -a python3 /opt/psa-tracker/psa_login.py; then
          set -a; . "$envf"; set +a
          timeout 420 python3 /opt/psa-tracker/psa_watch.py --once "$@"
          rc=$?
        fi
      else
        echo "[run_scan] $id: cookie looks dead, skipping login ($why)"
      fi
    fi

    # consecutive-failure counter -> warning ping, then daily, one recovery ping
    FAILF="$dir/.scan_fails"
    if [ "$rc" = 0 ]; then
      date -Is > "$dir/.last_ok"   # the dashboard warns when this goes stale
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
      after=${PSA_ALERT_AFTER:-3}
      # at the threshold, then once a day after it: a stuck account keeps pinging
      if [ "$n" -ge "$after" ] 2>/dev/null && [ $(( (n - after) % 24 )) -eq 0 ]; then
        alert "⚠️ psa-tracker [$id]: $n scans in a row have failed (rc=$rc). Check: journalctl -u psa-scan · screenshots in login_debug/."
      fi
    fi

    # Card market values (PSA_VALUES=1 in the env enables; remove to disable).
    # Public cert pages, so failures never block the scan.
    if [ "$full" = 1 ] && [ "$rc" = 0 ] && [ "${PSA_VALUES:-0}" = "1" ]; then
      timeout 420 xvfb-run -a python3 /opt/psa-tracker/psa_values.py \
        || echo "[run_scan] $id: values fetch failed (non-fatal)"
    fi
  )
done
[ "$found" = 1 ] || echo "[run_scan] no accounts found in $ACCTS - run add_account.sh"
echo "[run_scan] $(date -Is) all accounts done"
