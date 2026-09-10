#!/usr/bin/env python3
"""Helpers shared by app.py and the three scraper scripts: tagged logging,
Discord pings, env-file edits. Stdlib only, like the rest of the tracker."""
import json, os, shlex, urllib.request


def log(prefix):
    """Return a logger that tags each line, e.g. log(f"psa-values:{ACCT}")."""
    def _log(msg):
        print(f"[{prefix}] {msg}", flush=True)
    return _log


def notify(webhook, text):
    """Post one line to a Discord webhook. Never fatal: a dead webhook must
    not take a scan or a login down with it."""
    if not webhook:
        return
    try:
        req = urllib.request.Request(webhook, data=json.dumps({"content": text}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        print(f"webhook failed: {e}", flush=True)


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
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(out) + "\n")
    os.replace(tmp, path)
