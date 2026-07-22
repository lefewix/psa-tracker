#!/bin/bash
# Nightly on-box snapshot (psa-backup.timer): the account data + config that
# can't be refetched - accounts/ (DBs, env), the global env, the unit files.
# imgcache is deliberately excluded (public CDN, refetches itself).
# Keeps the newest 3 auto-* snapshots; hand-made pre-change tarballs are
# never touched. Restore: untar over / (paths are absolute-rooted).
set -euo pipefail
OUT=/opt/psa-tracker/backups
mkdir -p "$OUT"
ts=$(date +%Y%m%d_%H%M%S)
tar -czf "$OUT/auto-$ts.tar.gz" -C / \
  opt/psa-tracker/accounts \
  etc/psa-tracker.env \
  etc/systemd/system/psa-web.service \
  etc/systemd/system/psa-scan.service \
  etc/systemd/system/psa-scan.timer
ls -1t "$OUT"/auto-*.tar.gz | tail -n +4 | xargs -r rm -f
echo "backup done: auto-$ts.tar.gz ($(du -h "$OUT/auto-$ts.tar.gz" | cut -f1)), $(ls "$OUT"/auto-*.tar.gz | wc -l) kept"
