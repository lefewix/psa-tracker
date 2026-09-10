#!/usr/bin/env python3
"""Helpers shared by app.py and the three scraper scripts: tagged logging,
Discord pings, env-file edits. Stdlib only, like the rest of the tracker."""
import json, os, shlex, urllib.error, urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def log(prefix):
    """Return a logger that tags each line, e.g. log(f"psa-values:{ACCT}")."""
    def _log(msg):
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


def notify(webhook, text, log=print):
    """Post to a Discord webhook. Never fatal: a dead webhook must not take a
    scan or a login down with it. Cloudflare 403s a missing User-Agent and
    Discord 404s a deleted webhook, so a non 2xx reply is logged with its body."""
    if not webhook:
        return
    for part in split_message(text):
        try:
            req = urllib.request.Request(webhook, data=json.dumps({"content": part}).encode(),
                                         headers={"Content-Type": "application/json",
                                                  "User-Agent": UA})
            urllib.request.urlopen(req, timeout=15).read()
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
