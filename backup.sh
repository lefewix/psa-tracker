#!/bin/bash
# Nightly on-box snapshot (psa-backup.timer): the account data + config that
# can't be refetched - accounts/ (DBs, env), the global env, the unit files.
# The DBs are copied with sqlite3's backup API into a staging tree first, so a
# scan committing mid-tar can't tear the archive.
# imgcache is deliberately excluded (public CDN, refetches itself).
# Keeps the newest 14 auto-* snapshots; hand-made pre-change tarballs are
# never touched. Restore: untar over / (paths are absolute-rooted).
set -euo pipefail
ROOT=${PSA_ROOT:-/opt/psa-tracker}
ENV_FILE=${PSA_GLOBAL_ENV:-/etc/psa-tracker.env}
UNIT_DIR=${PSA_UNIT_DIR:-/etc/systemd/system}
OUT=$ROOT/backups
KEEP=14
mkdir -p "$OUT"
ts=$(date +%Y%m%d_%H%M%S)

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
acct=$stage/${ROOT#/}/accounts
mkdir -p "$(dirname "$acct")"
cp -a "$ROOT/accounts" "$acct"
rm -f "$acct"/*/*.db "$acct"/*/*.db-wal "$acct"/*/*.db-shm
python3 - "$ROOT/accounts" "$acct" <<'PY'
import glob, os, sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
for path in glob.glob(os.path.join(src, "*", "*.db")):
    live = sqlite3.connect(path, timeout=30)
    snap = sqlite3.connect(os.path.join(dst, os.path.relpath(path, src)))
    live.backup(snap)
    snap.close()
    live.close()
PY

for f in "$ENV_FILE" \
  "$UNIT_DIR/psa-web.service" \
  "$UNIT_DIR/psa-scan.service" \
  "$UNIT_DIR/psa-scan.timer" \
  "$UNIT_DIR/psa-backup.service" \
  "$UNIT_DIR/psa-backup.timer"; do
  [ -f "$f" ] || continue
  mkdir -p "$stage/$(dirname "${f#/}")"
  cp -a "$f" "$stage/${f#/}"
done

tar -czf "$OUT/auto-$ts.tar.gz" -C "$stage" .
ls -1t "$OUT"/auto-*.tar.gz | tail -n +$((KEEP + 1)) | while read -r old; do rm -f "$old"; done
echo "backup done: auto-$ts.tar.gz ($(du -h "$OUT/auto-$ts.tar.gz" | cut -f1)), $(ls "$OUT"/auto-*.tar.gz | wc -l) kept"
