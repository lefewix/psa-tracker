#!/bin/bash
# Add a tracked PSA account. Creates accounts/<id>/account.env (chmod 600).
# The site password you choose here is what that account's friends type on the
# lock screen - the password itself routes them to this account, so it MUST be
# unique across accounts (checked below).
set -e
ACCTS="${PSA_ACCOUNTS_DIR:-/opt/psa-tracker/accounts}"
mkdir -p "$ACCTS"

read -rp "Account id (short, lowercase, e.g. flx): " ID
[[ "$ID" =~ ^[a-z0-9-]+$ ]] || { echo "id must be lowercase letters/digits/dashes"; exit 1; }
[ -e "$ACCTS/$ID" ] && { echo "account '$ID' already exists"; exit 1; }
read -rp "Display label (shown on their pages, e.g. FLXTCG): " LABEL
read -rp "PSA account email: " EMAIL
read -rsp "PSA account password: " PW; echo
read -rsp "Site password (what friends type to see THIS account): " SITE; echo

python3 - "$ACCTS" "$ID" "$LABEL" "$EMAIL" "$PW" "$SITE" <<'EOF'
import glob, os, shlex, sys
accts, id_, label, email, pw, site = sys.argv[1:7]
if not site:
    sys.exit("ERROR: site password cannot be empty")
# site passwords route logins -> must be unique across accounts
for f in glob.glob(os.path.join(accts, "*", "account.env")):
    for line in open(f):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            tokens = shlex.split(line, posix=True)
        except ValueError:
            continue
        for t in tokens:
            if t.startswith("SITE_PASSWORD=") and t.split("=", 1)[1] == site:
                sys.exit(f"ERROR: that site password is already used by {os.path.dirname(f)} - pick a unique one")
d = os.path.join(accts, id_)
os.makedirs(d)
p = os.path.join(d, "account.env")
pairs = [("LABEL", label), ("SITE_PASSWORD", site),
         ("PSA_LOGIN_EMAIL", email), ("PSA_LOGIN_PW", pw)]
with open(p, "w") as f:
    f.write("".join(f"{k}={shlex.quote(v)}\n" for k, v in pairs))
os.chmod(p, 0o600)
print(f"created {p}")
EOF

echo "Done. The account is live for web login immediately; its first PSA scan"
echo "runs at the next 1am/1pm cycle, or now with: systemctl start psa-scan.service"
