#!/bin/bash
# Deploy tracker files to the box: compile-check -> scp -> sha256 verify ->
# restart psa-web when app.py shipped. The HANDOFF ritual, without the typos.
#
#   ./deploy.sh                    # app.py + FLX brand assets to the server
#   ./deploy.sh app.py run_scan.sh # specific files only
#   PSA_HOST=root@192.0.2.10 ./deploy.sh app.py   # a demo box instead
#     (demo boxes: always name files - the no-arg default includes logo.svg
#      and the favicon PNGs, which are the server's FLX branding)
set -euo pipefail
HOST="${PSA_HOST:-root@192.0.2.10}"
DEST=/opt/psa-tracker
if [ $# -gt 0 ]; then
  FILES=("$@")
else
  FILES=(app.py logo.svg favicon.png apple-touch-icon.png)
fi

for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "no such file: $f"; exit 1; }
  case "$f" in
    *.py) python3 -m py_compile "$f" ;;
    *.sh) bash -n "$f" ;;
  esac
done

scp -q "${FILES[@]}" "$HOST:$DEST/"

restart=0
for f in "${FILES[@]}"; do
  L=$(shasum -a 256 "$f" | cut -d' ' -f1)
  R=$(ssh "$HOST" "sha256sum $DEST/$(basename "$f")" | cut -d' ' -f1)
  [ "$L" = "$R" ] || { echo "SHA MISMATCH on $f - NOT restarting"; exit 1; }
  echo "ok  $(basename "$f")  $L"
  [ "$(basename "$f")" = "app.py" ] && restart=1
done

if [ "$restart" = 1 ]; then
  ssh "$HOST" 'systemctl restart psa-web && sleep 1 && systemctl is-active psa-web'
fi
echo "deployed to $HOST (scraper changes apply at the next hourly scan)"
