#!/bin/bash
# Deploy tracker files to the box: compile-check -> smoke test -> scp to a
# staging dir -> sha256 verify -> move into place -> restart psa-web when
# app.py shipped -> curl the box. The HANDOFF ritual, without the typos.
# A build that fails any of those never replaces the live app.py.
#
#   ./deploy.sh                    # app.py + psa_common.py + FLX brand assets to the server
#   ./deploy.sh app.py run_scan.sh # specific files only
#   PSA_HOST=root@192.0.2.10 ./deploy.sh app.py   # a demo box instead
#     (demo boxes: always name files - the no-arg default includes logo.svg
#      and the favicon PNGs, which are the server's FLX branding)
set -euo pipefail
HOST="${PSA_HOST:-root@192.0.2.10}"
DEST=/opt/psa-tracker
WEB_PORT="${PSA_WEB_PORT:-8080}"
if [ $# -gt 0 ]; then
  FILES=("$@")
else
  FILES=(app.py psa_common.py logo.svg favicon.png apple-touch-icon.png)
fi

# app.py and the three scrapers all import psa_common.py: never ship one without it.
case " ${FILES[*]} " in
  *" psa_common.py "*) ;;
  *.py*) FILES+=(psa_common.py) ;;
esac

restart=0
for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "no such file: $f"; exit 1; }
  case "$f" in
    *.py) python3 -m py_compile "$f" ;;
    *.sh) bash -n "$f" ;;
  esac
  if [ "$(basename "$f")" = "app.py" ]; then restart=1; fi
done

# app.py ships only if it boots and serves: smoke.py runs the whole route table
# against a throwaway fixture and exits non-zero on the first bad answer.
if [ "$restart" = 1 ]; then
  python3 "$(dirname "$0")/scripts/smoke.py"
fi

# Stage, verify the sha on the box, then move into place: a truncated or
# half-written upload never becomes the live file.
STAGE=$(ssh "$HOST" 'mktemp -d')
trap 'ssh "$HOST" "rm -rf $STAGE" >/dev/null 2>&1 || true' EXIT
scp -q "${FILES[@]}" "$HOST:$STAGE/"
for f in "${FILES[@]}"; do
  L=$(shasum -a 256 "$f" | cut -d' ' -f1)
  R=$(ssh "$HOST" "sha256sum $STAGE/$(basename "$f")" | cut -d' ' -f1)
  [ "$L" = "$R" ] || { echo "SHA MISMATCH on $f - nothing moved into $DEST"; exit 1; }
  echo "ok  $(basename "$f")  $L"
done
ssh "$HOST" "mv $STAGE/* $DEST/"

if [ "$restart" = 1 ]; then
  ssh "$HOST" 'systemctl restart psa-web && sleep 1 && systemctl is-active psa-web'
  for p in / /settings; do
    url="http://127.0.0.1:$WEB_PORT$p"
    # Demo boxes may lack curl; fall back to python3's urllib for the status code.
    remote_cmd="command -v curl >/dev/null && curl -s -o /dev/null -w '%{http_code}' $url || python3 -c 'import sys,urllib.request,urllib.error
try: print(urllib.request.urlopen(sys.argv[1],timeout=10).status)
except urllib.error.HTTPError as e: print(e.code)
except Exception: print(0)' $url"
    code=$(ssh "$HOST" "$remote_cmd" || echo 000)
    case "$code" in
      2*|3*|4*) echo "live $p -> $code" ;;
      *) echo "POST-DEPLOY FAIL: $p -> $code (check journalctl -u psa-web)"; exit 1 ;;
    esac
  done
fi
echo "deployed to $HOST (scraper changes apply at the next hourly scan)"
