#!/bin/bash
# For each tracked account: refresh its PSA cookie via a real browser login,
# then scan its submissions. Scheduled twice daily by psa-scan.timer.
#
# Env layering: global /etc/psa-tracker.env first, then the account's
# account.env on top (account wins). PSA_DB/PSA_OWN_DB point the scraper at
# that account's databases; PSA_ENV_FILE tells psa_login.py where to write the
# fresh cookie.
export PLAYWRIGHT_BROWSERS_PATH=/opt/psa-tracker/.pw-browsers
GLOBAL=/etc/psa-tracker.env
ACCTS=/opt/psa-tracker/accounts
shopt -s nullglob
found=0
for envf in "$ACCTS"/*/account.env; do
  found=1
  dir=$(dirname "$envf"); id=$(basename "$dir")
  echo "[run_scan] $(date -Is) === account: $id ==="
  (
    set -a; . "$GLOBAL"; . "$envf"; set +a
    export PSA_ENV_FILE="$envf" PSA_ACCT_ID="$id" PSA_DB="$dir/psa.db" PSA_OWN_DB="$dir/owners.db"
    if xvfb-run -a python3 /opt/psa-tracker/psa_login.py; then
      set -a; . "$envf"; set +a   # reload: pick up the fresh PSA_COOKIE
    else
      echo "[run_scan] $id: login failed — scanning with existing cookie"
    fi
    python3 /opt/psa-tracker/psa_watch.py --once "$@"
  )
done
[ "$found" = 1 ] || echo "[run_scan] no accounts found in $ACCTS — run add_account.sh"
echo "[run_scan] $(date -Is) all accounts done"
