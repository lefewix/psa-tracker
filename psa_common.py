#!/usr/bin/env python3
"""Helpers shared by app.py and the three scraper scripts: tagged logging,
Discord pings, env-file edits. Stdlib only, like the rest of the tracker."""
import json, os, shlex, urllib.error, urllib.request, uuid

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


# The last line any logger printed. psa_login reports it as the failure cause
# when it has nothing more specific to say (T105).
LAST_LINE = ""


def log(prefix):
    """Return a logger that tags each line, e.g. log(f"psa-values:{ACCT}")."""
    def _log(msg):
        global LAST_LINE
        LAST_LINE = str(msg)
        print(f"[{prefix}] {msg}", flush=True)
    return _log


def split_message(text, limit=1900):
    """Discord 400s anything over 2000 characters - break on line boundaries."""
    parts, cur = [], ""
    for line in text.split("\n"):
        line = line[:limit]
        if cur and len(cur) + 1 + len(line) > limit:
            parts.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        parts.append(cur)
    return parts


def _multipart(payload, files):
    """Discord webhook upload: payload_json + files[n], one boundary."""
    b = uuid.uuid4().hex
    out = (f"--{b}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\n"
           f"Content-Type: application/json\r\n\r\n{json.dumps(payload)}\r\n").encode()
    for i, (name, data) in enumerate(files):
        out += (f"--{b}\r\nContent-Disposition: form-data; name=\"files[{i}]\"; "
                f"filename=\"{name}\"\r\nContent-Type: image/png\r\n\r\n").encode() + data + b"\r\n"
    out += f"--{b}--\r\n".encode()
    return out, f"multipart/form-data; boundary={b}"


def notify(webhook, text, log=print, files=()):
    """Post to a Discord webhook, optionally with PNG attachments on the first
    part (Discord takes up to 10 files per message). Never fatal: a dead webhook
    must not take a scan or a login down with it. Cloudflare 403s a missing
    User-Agent and Discord 404s a deleted webhook, so a non 2xx reply is logged
    with its body."""
    if not webhook:
        return
    files = list(files)[:10]
    for part in split_message(text):
        try:
            if files:
                data, ctype = _multipart({"content": part}, files)
                files = []  # attachments ride the first part only
            else:
                data, ctype = json.dumps({"content": part}).encode(), "application/json"
            req = urllib.request.Request(webhook, data=data,
                                         headers={"Content-Type": ctype, "User-Agent": UA})
            urllib.request.urlopen(req, timeout=30).read()
        except urllib.error.HTTPError as e:
            log(f"webhook returned {e.code}: {e.read(400).decode('utf-8', 'replace').strip()}")
        except Exception as e:
            log(f"webhook failed: {e}")


def env_set(path, updates):
    """Update KEY='value' lines in an env file, preserving all other lines.
    Empty value removes the key. Atomic write, chmod 600."""
    try:
        lines = open(path).read().splitlines()
    except FileNotFoundError:
        lines = []
    out, seen = [], set()
    for ln in lines:
        k = ln.split("=", 1)[0] if ("=" in ln and not ln.lstrip().startswith("#")) else None
        if k in updates:
            seen.add(k)
            if updates[k] != "":
                out.append(f"{k}={shlex.quote(updates[k])}")
        else:
            out.append(ln)
    for k, v in updates.items():
        if k not in seen and v != "":
            out.append(f"{k}={shlex.quote(v)}")
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)  # a leftover tmp from a crashed run keeps its old mode
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(out) + "\n")
    os.replace(tmp, path)


def set_error(text):
    """One line saying why this account's scan or login just failed, into
    `<account dir>/.last_error` (the account dir is PSA_ENV_FILE's parent, which
    run_scan.sh exports). run_scan.sh puts that line in its Discord alert and
    deletes the file after a scan that returns 0; app.py serves it in hub.json
    and on the dashboard banner. Never fatal, and a no-op outside run_scan."""
    env = os.environ.get("PSA_ENV_FILE", "")
    if not env:
        return
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(env)), ".last_error")
        with open(path, "w", encoding="utf-8") as f:
            f.write(" ".join(str(text).split())[:300] + "\n")
    except OSError as e:
        print(f"[psa] could not write .last_error: {e}", flush=True)
