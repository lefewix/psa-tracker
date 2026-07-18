#!/usr/bin/env python3
"""psa-tracker web: multi-account password gate + submissions dashboard.

Stdlib only. Reads each account's psa.db (filled by psa_watch.py, never written
here) and writes that account's owners.db (owner tags + archived subs).

Multi-account: every directory under PSA_ACCOUNTS_DIR holding an account.env is
a tracked PSA account. Each account has its OWN site password; the login form
routes whoever types a password to the matching account - the account chooser is
invisible by design. Site passwords must therefore be unique across accounts.

Global env (systemd EnvironmentFile):
  PSA_SECRET        required - random string for session-cookie signing
  PSA_BIND          default 0.0.0.0
  PSA_PORT          default 8080
  PSA_ACCOUNTS_DIR  default /opt/psa-tracker/accounts
  PSA_IMG_CACHE     default /opt/psa-tracker/imgcache (shared; images are public CDN)
  SITE_TITLE        default "Submissions"   (dashboard heading + page titles)
  SITE_TAGLINE      default "PSA GRADING TRACKER" (login-gate subtitle)
  COOKIE_DAYS       default 30
  PSA_COOKIE_SECURE default 1 - set 0 if hosting over plain HTTP (no TLS proxy)

Per-account account.env (written by add_account.sh, chmod 600):
  LABEL             display name on that account's pages
  SITE_PASSWORD     the password that logs friends into THIS account
  PSA_LOGIN_EMAIL / PSA_LOGIN_PW / PSA_COOKIE - used by psa_login.py/psa_watch.py
  PSA_PRICES        optional per-card fee table, "regular:109,max:89.99,bulk:34.99,value:45.99"
                    (matched most-specific-first in the order given)
"""
import base64, hashlib, hmac, html, json, os, re, shlex, sqlite3, threading, time
import urllib.parse, urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

SECRET = os.environ.get("PSA_SECRET", "").encode()
BIND = os.environ.get("PSA_BIND", "0.0.0.0")
PORT = int(os.environ.get("PSA_PORT", "8080"))
COOKIE_DAYS = int(os.environ.get("COOKIE_DAYS", "30"))
COOKIE_SECURE = os.environ.get("PSA_COOKIE_SECURE", "1") not in ("0", "false", "no")
SITE_TITLE = os.environ.get("SITE_TITLE", "Submissions")
SITE_TAGLINE = os.environ.get("SITE_TAGLINE", "PSA GRADING TRACKER")

def _hexcolor(env, default):
    """Env-supplied brand color, validated so env can't inject CSS."""
    v = os.environ.get(env, "").strip()
    return v if re.fullmatch(r"#[0-9a-fA-F]{6}", v) else default

# Per-store branding: one primary accent + one ambient secondary; every other
# shade is derived in CSS via color-mix, so stores only pick two colors.
ACCENT = _hexcolor("PSA_ACCENT", "#8b5cf6")
ACCENT_2 = _hexcolor("PSA_ACCENT_2", "#6366f1")
THEME = "light" if os.environ.get("PSA_THEME", "dark").strip().lower() == "light" else "dark"

# Optional store logo: drop a file at PSA_LOGO (svg/png/jpg) and it appears
# above the site title on the gate and dashboard, served at /logo.
LOGO_PATH = os.environ.get("PSA_LOGO", "/opt/psa-tracker/logo.svg")
# PSA_LOGO_CHIP=1: render the logo on a white rounded backing in dark mode -
# for marks that are dark-on-light or have a baked-in white box.
LOGO_CHIP = os.environ.get("PSA_LOGO_CHIP", "").strip().lower() in ("1", "true", "yes")
# PSA_LOGO_DARK=silhouette: in dark mode render the logo as a white monochrome
# mark (for dark-on-light logos with real transparency). Beats the chip when
# the mark's shapes read well on their own.
LOGO_SIL = os.environ.get("PSA_LOGO_DARK", "").strip().lower() == "silhouette"

def logo_tag():
    if not os.path.exists(LOGO_PATH):
        return ""
    cls = "logo sil" if LOGO_SIL else ("logo chip" if LOGO_CHIP else "logo")
    v = int(os.path.getmtime(LOGO_PATH))  # cache-buster: logo swaps show immediately
    return f'<img class="{cls}" src="/logo?v={v}" alt="">'

# Accent-derived shades flip direction per theme (lighter on dark, deeper on light)
_AC_MIX_L = {"--ac-hot": "85%,black", "--ac-soft": "80%,black",
             "--ac-pale": "68%,black", "--ac-ice": "45%,black"}
_AC_MIX_D = {"--ac-hot": "82%,white", "--ac-soft": "72%,white",
             "--ac-pale": "45%,white", "--ac-ice": "15%,white"}
# Neutral system: dark values are the original hand-picked palette (byte-identical
# default); light values are the store-facing white theme.
_DARK = {"bg": "#101014", "bgtop": "#13121a", "mix": "#101014", "surface": "#17161c",
 "surface2": "#111116", "surface3": "#17171c", "inp": "#0c0c10", "ph": "#141419",
 "hovrow": "#1a1922", "txt": "#ecebf0", "txtstrong": "#ffffff",
 "m1": "#9b93b3", "m2": "#8d87a0", "m3": "#8d8a9a", "m4": "#8a879d", "m5": "#85829a",
 "m6": "#817e92", "m7": "#7d7a90", "m8": "#a79fc0", "m9": "#9d9aab",
 "m10": "#565360", "m11": "#565364",
 "b1": "#24232c", "b2": "#262530", "b3": "#26252f", "b4": "#2b2a34", "b5": "#3a3849",
 "hair": "rgba(255,255,255,.08)", "hairh": "rgba(255,255,255,.14)",
 "hair2": "rgba(255,255,255,.06)", "track": "rgba(255,255,255,.09)",
 "chipbg": "rgba(255,255,255,.05)", "chipline": "rgba(255,255,255,.12)",
 "logoblend": "normal", "chipfill": "#ffffff", "chippad": "6px 8px", "chipdots": "color-mix(in srgb,var(--ac) 20%,transparent)", "logofx": "brightness(0) invert(1)",
 "dots": "color-mix(in srgb,var(--ac-pale) 6%,transparent)",
 "glow1": "color-mix(in srgb,var(--ac) 9%,transparent)",
 "glow2": "color-mix(in srgb,var(--ac) 6%,transparent)",
 "glow3": "color-mix(in srgb,var(--ac2) 5%,transparent)",
 "dot0": "#423a4f", "shc": "rgba(8,5,20,.45)", "shc2": "rgba(8,5,20,.7)",
 "shc3": "rgba(8,5,20,.6)", "frost": "rgba(19,18,26,.7)",
 "sh1": "#15141a", "sh2": "#1d1c24", "err": "#ff8b8b", "holdtx": "#ffc9c9"}
# light neutrals: surfaces tint from the store accent (brand-aware whites);
# text/borders stay hue-neutral for contrast
_LIGHT = {"bg": "color-mix(in srgb,var(--ac) 4%,white)", "bgtop": "#ffffff",
 "mix": "#ffffff", "surface": "#ffffff",
 "surface2": "color-mix(in srgb,var(--ac) 5%,white)",
 "surface3": "color-mix(in srgb,var(--ac) 7%,white)",
 "inp": "color-mix(in srgb,var(--ac) 3%,white)",
 "ph": "color-mix(in srgb,var(--ac) 5%,white)",
 "hovrow": "color-mix(in srgb,var(--ac) 7%,white)",
 "txt": "#1c1c22", "txtstrong": "#0e0e14",
 "m1": "#4e4c58", "m2": "#5c5a68", "m3": "#5c5a68", "m4": "#63616e", "m5": "#686674",
 "m6": "#71707e", "m7": "#79778a", "m8": "#5b5966", "m9": "#6b6975",
 "m10": "#b6b5c0", "m11": "#b6b5c0",
 "b1": "#e3e3ea", "b2": "#e3e3ea", "b3": "#e3e3ea", "b4": "#d9d9e2", "b5": "#c7c7d2",
 "hair": "rgba(22,22,45,.09)", "hairh": "rgba(22,22,45,.18)",
 "hair2": "rgba(22,22,45,.07)", "track": "rgba(22,22,45,.12)",
 "chipbg": "rgba(22,22,45,.05)", "chipline": "rgba(22,22,45,.16)",
 "logoblend": "multiply", "chipfill": "transparent", "chippad": "0", "chipdots": "transparent", "logofx": "none",
 "dots": "color-mix(in srgb,var(--ac) 27%,transparent)",
 "glow1": "color-mix(in srgb,var(--ac) 23%,transparent)",
 "glow2": "color-mix(in srgb,var(--ac) 15%,transparent)",
 "glow3": "color-mix(in srgb,var(--ac2) 19%,transparent)",
 "dot0": "#d7d7e0", "shc": "color-mix(in srgb,var(--ac) 30%,rgba(20,20,35,.12))",
 "shc2": "color-mix(in srgb,var(--ac) 30%,rgba(20,20,35,.14))",
 "shc3": "color-mix(in srgb,var(--ac) 30%,rgba(20,20,35,.12))",
 "frost": "rgba(255,255,255,.78)",
 "sh1": "color-mix(in srgb,var(--ac) 5%,white)",
 "sh2": "color-mix(in srgb,var(--ac) 9%,white)",
 "err": "#c23d3d", "holdtx": "#a03232"}
def _theme_vars(mode):
    acmix = _AC_MIX_L if mode == "light" else _AC_MIX_D
    neut = _LIGHT if mode == "light" else _DARK
    return ("".join(f"{k}:color-mix(in srgb,var(--ac) {v});" for k, v in acmix.items())
            + "".join(f"--{k}:{v};" for k, v in neut.items()))

# The store's PSA_THEME is the default; both palettes are emitted so the
# client-side day/night toggle can flip instantly (data-theme on <html>).
THEME_VARS = (f":root{{--ac:{ACCENT};--ac2:{ACCENT_2};{_theme_vars(THEME)}}}"
              f':root[data-theme="dark"]{{{_theme_vars("dark")}}}'
              f':root[data-theme="light"]{{{_theme_vars("light")}}}')
ACCOUNTS_DIR = os.environ.get("PSA_ACCOUNTS_DIR", "/opt/psa-tracker/accounts")

# Image proxy: PSA card images live on this public CloudFront host. We fetch +
# cache them locally so friends' browsers never hit PSA and everything stays
# behind the password gate. Cache is shared across accounts (public images,
# unguessable per-image hash URLs).
IMG_HOST = "d1htnxwo4o0jhw.cloudfront.net"
IMG_CACHE = os.environ.get("PSA_IMG_CACHE", "/opt/psa-tracker/imgcache")
MAX_IMG_BYTES = 8 * 1024 * 1024

def img_url(u, size="large"):
    """Rewrite a stored thumbnail URL to another size (small/medium/large)."""
    return u.replace("/thumbnail/", f"/{size}/") if u else ""

STAGES = ["Arrived", "Order Prep", "Research & ID", "Grading", "Assembly", "QA Check", "Shipped"]

def stage_index(status):
    try:
        return STAGES.index(status)
    except ValueError:
        return 0

# Timestamps are stored UTC; render them in the audience's timezone.
try:
    DISPLAY_TZ = ZoneInfo(os.environ.get("PSA_DISPLAY_TZ", "America/Toronto"))
except Exception:
    DISPLAY_TZ = timezone.utc

def fmt_local(iso):
    """UTC ISO timestamp -> 'Jul 18, 1:06 AM ET' (or raw slice if unparseable)."""
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        loc = dt.astimezone(DISPLAY_TZ)
        return f"{loc.strftime('%b %d')}, {loc.strftime('%I:%M %p').lstrip('0')} {loc.strftime('%Z')}"
    except (ValueError, TypeError):
        return iso[:16].replace("T", " ")

def short_date(iso):
    """'2026-09-25' -> 'SEP 25' for compact pill display."""
    try:
        return datetime.fromisoformat(iso[:10]).strftime("%b %d")
    except (ValueError, TypeError):
        return iso

# PSA is inconsistent about card-name casing: some specDescriptions arrive ALL
# CAPS, most arrive mixed. Tame the shouty ones at render time; leave mixed-case
# names (PSA's canonical form) untouched.
_ACRONYMS = {"TCG", "PSA", "CCG", "EN", "JP", "GX", "EX", "VMAX", "VSTAR",
             "SM", "SV", "XY", "BW", "DP", "SWSH"}
_SMALL_WORDS = {"a", "an", "and", "at", "for", "in", "of", "on", "the", "to", "with"}

def _title_seg(p):
    """One hyphen-segment: keep set/card codes (digits) as-is, keep acronyms
    upper, capitalize the rest."""
    if any(ch.isdigit() for ch in p):
        return p
    if p.upper() in _ACRONYMS:
        return p.upper()
    return p[:1].upper() + p[1:].lower()

def smart_title(name):
    letters = [c for c in name if c.isalpha()]
    if not letters or sum(c.isupper() for c in letters) / len(letters) < 0.9:
        return name  # already conventional
    out = []
    for i, w in enumerate(name.split()):
        if w.lower() in _SMALL_WORDS and i > 0:
            out.append(w.lower())
        else:
            out.append("-".join(_title_seg(p) for p in w.split("-")))
    return " ".join(out)

# ---------- accounts ----------

DEFAULT_PRICES = [("regular", 109.0), ("max", 89.99), ("bulk", 34.99), ("value", 45.99)]

def read_env_file(path):
    """Parse a shell-style KEY=VALUE env file (handles quoting via shlex)."""
    vals = {}
    try:
        raw = open(path).read()
    except OSError:
        return vals
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            tokens = shlex.split(line, posix=True)
        except ValueError:
            continue
        for t in tokens:
            if t != "export" and "=" in t:
                k, v = t.split("=", 1)
                vals[k] = v
    return vals

def parse_prices(spec):
    """'regular:109,max:89.99' -> [('regular',109.0),...]; order = match priority."""
    out = []
    for part in (spec or "").split(","):
        if ":" not in part:
            continue
        k, _, v = part.strip().partition(":")
        try:
            out.append((k.strip().lower(), float(v)))
        except ValueError:
            continue
    return out or DEFAULT_PRICES

def load_accounts():
    """Scan ACCOUNTS_DIR -> {id: account dict}. Cheap enough to run per request,
    so password/label changes and new accounts apply without a restart."""
    accts = {}
    if not os.path.isdir(ACCOUNTS_DIR):
        return accts
    for d in sorted(os.listdir(ACCOUNTS_DIR)):
        if not re.fullmatch(r"[a-z0-9-]+", d):  # ids must be token-safe (no dots)
            continue
        base = os.path.join(ACCOUNTS_DIR, d)
        env = read_env_file(os.path.join(base, "account.env"))
        pw = env.get("SITE_PASSWORD", "")
        if not pw:
            continue
        accts[d] = {
            "id": d,
            "label": env.get("LABEL", d.upper()),
            "password": pw,
            "db": os.path.join(base, "psa.db"),
            "own_db": os.path.join(base, "owners.db"),
            "prices": parse_prices(env.get("PSA_PRICES", "")),
        }
    return accts

def service_price(a, service):
    s = (service or "").lower()
    for key, price in a["prices"]:
        if key in s:
            return price
    return None

# ---------- auth ----------

def _b64e(s):
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")

def _b64d(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode()

def make_token(acct_id, exp, email=""):
    """Admin (site-password) token: acct.exp.sig
    Customer token carries the email: acct.exp.email_b64.sig"""
    if email:
        msg = f"{acct_id}.{exp}.customer.{email}".encode()
        sig = hmac.new(SECRET, msg, hashlib.sha256).hexdigest()
        return f"{acct_id}.{exp}.{_b64e(email)}.{sig}"
    msg = f"{acct_id}.{exp}".encode()
    sig = hmac.new(SECRET, msg, hashlib.sha256).hexdigest()
    return f"{acct_id}.{exp}.{sig}"

def valid_token(tok):
    """Return (acct_id, customer_email) the token grants, or None.
    customer_email == "" means a full site-password session."""
    parts = (tok or "").split(".")
    if len(parts) not in (3, 4):
        return None
    acct_id, exp_s, sig = parts[0], parts[1], parts[-1]
    try:
        exp = int(exp_s)
    except ValueError:
        return None
    if exp < time.time():
        return None
    if len(parts) == 4:
        try:
            email = _b64d(parts[2])
        except Exception:
            return None
        good = hmac.new(SECRET, f"{acct_id}.{exp_s}.customer.{email}".encode(),
                        hashlib.sha256).hexdigest()
        return (acct_id, email) if hmac.compare_digest(good, sig) else None
    good = hmac.new(SECRET, f"{acct_id}.{exp_s}".encode(), hashlib.sha256).hexdigest()
    return (acct_id, "") if hmac.compare_digest(good, sig) else None

# Per-IP login throttle (in-memory; resets on restart). The 0.4s sleep blunts
# casual brute force; this stops a determined loop.
_FAILS = {}  # ip -> [count, window_start]
_FAILS_LOCK = threading.Lock()
MAX_FAILS = 8
FAIL_WINDOW = 900  # 15 min

def login_locked(ip):
    with _FAILS_LOCK:
        rec = _FAILS.get(ip)
        if not rec:
            return False
        if time.time() - rec[1] > FAIL_WINDOW:
            del _FAILS[ip]
            return False
        return rec[0] >= MAX_FAILS

def login_fail(ip):
    with _FAILS_LOCK:
        rec = _FAILS.get(ip)
        if rec and time.time() - rec[1] <= FAIL_WINDOW:
            rec[0] += 1
        else:
            _FAILS[ip] = [1, time.time()]

def login_ok(ip):
    with _FAILS_LOCK:
        _FAILS.pop(ip, None)

# Light per-IP cap on /suggest so a valid session can't hammer full-table scans.
_SUG = {}  # ip -> [count, window_start]
_SUG_LOCK = threading.Lock()
SUGGEST_MAX = 40  # per 10s (client debounces to ~9/s; this only stops abuse)

def suggest_allowed(ip):
    with _SUG_LOCK:
        rec = _SUG.get(ip)
        now = time.time()
        if not rec or now - rec[1] > 10:
            _SUG[ip] = [1, now]
            return True
        rec[0] += 1
        return rec[0] <= SUGGEST_MAX

# ---------- data (all account-scoped) ----------

def own_conn(a):
    c = sqlite3.connect(a["own_db"])
    c.execute("CREATE TABLE IF NOT EXISTS owners (cert_id TEXT PRIMARY KEY, owner TEXT, updated_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS archived (sub_number TEXT PRIMARY KEY, archived_at TEXT)")
    return c

def archived_set(a):
    c = own_conn(a)
    s = {r[0] for r in c.execute("SELECT sub_number FROM archived")}
    c.close()
    return s

def set_archived(a, sub_number, on):
    c = own_conn(a)
    if on:
        c.execute("INSERT OR REPLACE INTO archived(sub_number, archived_at) VALUES (?,?)",
                  (sub_number, time.strftime("%Y-%m-%dT%H:%M")))
    else:
        c.execute("DELETE FROM archived WHERE sub_number=?", (sub_number,))
    c.commit(); c.close()

def _ro_conn(a):
    conn = sqlite3.connect(f"file:{a['db']}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def load_subs(a):
    try:
        conn = _ro_conn(a)
        rows = conn.execute("""SELECT * FROM subs
            ORDER BY CAST(sub_number AS INTEGER) DESC""").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:  # fresh account: no psa.db until first scan
        return []

def load_sub(a, sub_number):
    try:
        conn = _ro_conn(a)
        row = conn.execute("SELECT * FROM subs WHERE sub_number=?", (sub_number,)).fetchone()
        conn.close()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        return None

def load_cards(a, sub_number):
    try:
        conn = _ro_conn(a)
        rows = conn.execute("SELECT * FROM cards WHERE sub_number=? ORDER BY line_number, cert_id",
                            (sub_number,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []

def load_all_cards(a):
    try:
        conn = _ro_conn(a)
        rows = conn.execute("SELECT * FROM cards ORDER BY CAST(sub_number AS INTEGER) DESC, line_number").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []

def owners_map(a):
    c = own_conn(a)
    m = {cid: ow for cid, ow in c.execute("SELECT cert_id, owner FROM owners WHERE owner!=''")}
    c.close()
    return m

def set_owner(a, cert_id, owner):
    c = own_conn(a)
    c.execute("INSERT OR REPLACE INTO owners(cert_id, owner, updated_at) VALUES (?,?,?)",
              (cert_id, owner.strip(), time.strftime("%Y-%m-%dT%H:%M")))
    c.commit(); c.close()

def find_customer(email):
    """Match a login email against owner tags across accounts (case-insensitive).
    Returns the account dict or None. Emails ARE the customer passwords in the
    store product - deliberately low-stakes (view-only card lists)."""
    e = email.strip().lower()
    if not e:
        return None
    for a in load_accounts().values():
        for tag in set(owners_map(a).values()):
            if tag.strip().lower() == e:
                return a
    return None

def cust_statline(s):
    """One-line per-card status for customer tiles (replaces the sub link)."""
    if not s:
        return ""
    if s["status"] == "Shipped":
        return f"Shipped {s['shipped']}" if s["shipped"] else "Shipped"
    eta = s["est_end"] or s["est_start"]
    return s["status"] + (f" · back ~{short_date(eta)}" if eta else "")

def suggest(a, q, owner=None, limit_names=8, limit_cards=40):
    """Live search backing the unified search box. People (priority) + cards.
    With owner set (person page), results are ONLY that person's cards - no
    People section; switching person means going back to all submissions."""
    ql = (q or "").strip().lower()
    owners = owners_map(a)
    want = (owner or "").strip().lower()
    if want:
        name_hits = []
    else:
        names = sorted({v for v in owners.values() if v})
        matches = [n for n in names if ql in n.lower()]
        # empty focus = browse mode: list EVERY person, scrollable directory
        name_hits = matches if not ql else matches[:limit_names]
    card_hits = []
    if ql or want:
        pool = load_all_cards(a)
        if want:
            pool = [c for c in pool if owners.get(str(c["cert_id"]), "").lower() == want]
            if not ql:  # empty focus on a person page: browse their cards A-Z
                pool.sort(key=lambda c: smart_title(c.get("name") or "").lower())
        for c in pool:
            if ql:
                hay = " ".join((c.get("name") or "", str(c.get("cert_no") or ""),
                                str(c.get("cert_id") or ""))).lower()
                if ql not in hay:
                    continue
            card_hits.append({
                "name": smart_title(c["name"] or ""),
                "cert": "" if str(c["cert_id"]).startswith("spec:") else (c["cert_no"] or ""),
                "sub": c["sub_number"],
                "owner": owners.get(str(c["cert_id"]), ""),
                "img": ("/img?u=" + urllib.parse.quote(img_url(c["front_thumb"], "small")))
                       if c.get("front_thumb") else "",
            })
            if len(card_hits) >= limit_cards:
                break
    return {"names": name_hits, "cards": card_hits}

# ---------- rendering ----------

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
@view-transition{navigation:auto}
body{background-color:var(--bg);min-height:100vh;position:relative;
 background-image:
  radial-gradient(var(--dots) 1px, transparent 1.4px),
  radial-gradient(1100px 540px at 50% -140px, var(--glow1), transparent 62%),
  radial-gradient(720px 900px at -6% 520px, var(--glow2), transparent 60%),
  radial-gradient(720px 900px at 106% 880px, var(--glow3), transparent 60%),
  radial-gradient(800px 560px at 88% 104%, var(--glow3), transparent 62%),
  linear-gradient(180deg,var(--bgtop) 0%,var(--bg) 460px);
 background-size:26px 26px,auto,auto,auto,auto,auto;
 background-repeat:repeat,no-repeat,no-repeat,no-repeat,no-repeat,no-repeat;
 color:var(--txt);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
 -webkit-font-smoothing:antialiased;padding:44px 20px 80px;font-variant-numeric:tabular-nums}
/* faint grain so large dark surfaces don't read as flat vector fill */
body::after{content:"";position:fixed;inset:0;z-index:1;pointer-events:none;opacity:.04;background:
 url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)'/%3E%3C/svg%3E") repeat}
:focus-visible{outline:2px solid var(--ac);outline-offset:2px}
.mono{font-family:ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,monospace}
@media(prefers-reduced-motion:reduce){.node.now .dot,.grid img,.cover{animation:none}
 ::view-transition-group(*),::view-transition-old(*),::view-transition-new(*){animation:none}}
.wrap{max-width:820px;margin:0 auto}
.logo{display:block;height:52px;width:auto;margin:0 0 10px;mix-blend-mode:var(--logoblend,normal)}
.logo.chip{background:radial-gradient(var(--chipdots) 1px,transparent 1.3px) 0 0/11px 11px,var(--chipfill);padding:var(--chippad);border-radius:10px;box-sizing:content-box;height:44px}
.logo.sil{filter:var(--logofx,none)}
.gbox .logo{height:104px;margin:0 auto 14px}
h1{font-size:30px;font-weight:700;letter-spacing:-.02em}
h1.big{font-size:clamp(40px,9vw,56px);line-height:1.02;letter-spacing:-.03em}
.sub{font-size:12px;font-weight:400;letter-spacing:.01em;color:var(--m4);margin-top:6px}
.hrow{display:flex;justify-content:space-between;align-items:flex-start;gap:14px}
.synced{text-align:right;flex-shrink:0;font-size:11px;font-weight:400;letter-spacing:.01em;
 color:var(--m5);line-height:1.5;padding-top:5px;white-space:nowrap}
.synced b{display:block;font-size:12.5px;font-weight:600;letter-spacing:0;color:var(--ac-pale);margin-top:2px}
.synced .estnote{display:block;font-size:10px;font-weight:400;letter-spacing:.01em;color:var(--m7);margin-top:3px;line-height:1.6}
.synced .lbl2{display:block;margin-top:8px}
.lgout{color:var(--m5);display:inline-flex;padding:6px 0 0 2px;transition:color .15s}
.lgout:hover{color:var(--ac-pale)}
.lgout:active{transform:translateY(1px)}
.hint{display:flex;align-items:center;gap:10px;margin:18px 0 2px;padding:11px 15px;font-size:13px;font-weight:400;
 color:var(--ac-pale);background:color-mix(in srgb,var(--ac) 10%,transparent);
 border:1px solid color-mix(in srgb,var(--ac-soft) 28%,transparent);border-radius:12px}
.hintx{width:auto;margin:0 0 0 auto;padding:0 4px;background:transparent;border:0;color:var(--m2);
 font-size:13px;cursor:pointer;letter-spacing:0}
.hintx:hover{color:var(--ac-ice)}
.toolbar{display:flex;gap:10px;margin:22px -14px 4px;flex-wrap:wrap;align-items:stretch;position:sticky;top:0;z-index:20;padding:12px 14px;border-radius:12px;
 background:var(--frost);
 backdrop-filter:blur(16px) saturate(140%);-webkit-backdrop-filter:blur(16px) saturate(140%);
 box-shadow:0 10px 30px -12px var(--shc3)}
.searchwrap{position:relative;flex:1;min-width:220px}
.searchwrap .sicon{position:absolute;left:13px;top:50%;transform:translateY(-50%);color:var(--m5);pointer-events:none}
.searchbar{width:100%;margin:0;text-align:left;padding:10px 13px 10px 36px;font-size:13px;font-weight:400}
.preview{position:absolute;z-index:30;top:calc(100% + 6px);left:0;right:0;background:var(--surface2);
 border:1px solid var(--b2);border-radius:12px;padding:6px;display:none;max-height:64vh;overflow:auto;overscroll-behavior:contain;
 box-shadow:0 14px 44px var(--shc2)}
.pvsec{font-size:10px;font-weight:600;letter-spacing:.04em;color:var(--m7);padding:9px 10px 4px}
.pvrow{display:flex;align-items:center;gap:9px;padding:8px 10px;border-radius:8px;text-decoration:none;
 color:var(--txt);font-size:12.5px;font-weight:500}
.pvrow:hover{background:var(--hovrow)}
.pvrow small{display:block;color:var(--m4);font-size:10.5px;font-weight:400;margin-top:1px;letter-spacing:.01em}
.pvtag{font-size:9px;font-weight:500;letter-spacing:.02em;color:var(--ac-pale);background:color-mix(in srgb,var(--ac) 19%,var(--mix));border:1px solid color-mix(in srgb,var(--ac) 37%,var(--mix));
 border-radius:6px;padding:3px 7px;flex-shrink:0}
.pvimg{width:26px;height:36px;object-fit:cover;border-radius:4px;border:1px solid var(--b3);flex-shrink:0;background:var(--surface3)}
.pvempty{padding:14px 10px;color:var(--m6);font-size:12px}
.filters{display:flex;gap:7px;flex-wrap:wrap;margin:26px 0 22px}
.f{font-size:11.5px;font-weight:500;letter-spacing:.01em;color:var(--m3);background:var(--surface3);
 border:1px solid var(--b1);padding:6px 13px;border-radius:7px;cursor:pointer;transition:.15s}
.f:hover{border-color:var(--b5);color:#c3c0d0}
.f.on{background:var(--ac);border-color:var(--ac);color:#fff}
.f.farch.on{background:#4d4b59;border-color:#4d4b59;color:#fff}
/* flat cards: solid surface + faint hairline */
.card{background:var(--surface);
 border:1px solid var(--hair);border-radius:18px;
 padding:26px 30px;margin-bottom:20px;
 box-shadow:0 4px 16px var(--shc);
 transition:transform .18s,border-color .18s,opacity .18s,filter .18s}
.card:hover{transform:translateY(-2px);border-color:var(--hairh)}
/* spotlight border: the card edge lights up under the cursor (JS sets --mx/--my) */
.card,.gc{position:relative}
.card::before,.gc::before{content:"";position:absolute;inset:-2px;border-radius:inherit;pointer-events:none;
 background:radial-gradient(340px circle at var(--mx,50%) var(--my,50%),color-mix(in srgb,var(--ac-soft) 75%,transparent),color-mix(in srgb,var(--ac-soft) 20%,transparent) 45%,transparent 80%);
 padding:2px;-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);
 mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);
 -webkit-mask-composite:xor;mask-composite:exclude;opacity:0;transition:opacity .25s}
@media(hover:hover){.card:hover::before,.gc:hover::before{opacity:1}
.card:hover .bloom,.gc:hover .bloom{opacity:1}}
/* bloom: a blurred copy of the lit ring (element injected by FX_JS). blurring
   the real ring makes the glow cursor-local, fade outward, and hug the corner
   radius exactly - the three things the masked band and box-shadow each missed */
.bloom{position:absolute;inset:-3px;border-radius:inherit;pointer-events:none;z-index:-1;
 filter:blur(22px);opacity:0;transition:opacity .25s}
.bloom::before{content:"";position:absolute;inset:0;border-radius:inherit;padding:3px;
 background:radial-gradient(circle 340px at calc(var(--mx,50%) + 3px) calc(var(--my,50%) + 3px),color-mix(in srgb,var(--ac) 70%,transparent),transparent 70%);
 -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);
 mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);
 -webkit-mask-composite:xor;mask-composite:exclude}
/* staggered entry: cards rise in with slight delays instead of mounting all at once */
@media(prefers-reduced-motion:no-preference){
 .card,.gc{animation:rise .38s cubic-bezier(.2,.7,.3,1) both}
 .card:nth-child(2),.gc:nth-child(2){animation-delay:.04s}
 .card:nth-child(3),.gc:nth-child(3){animation-delay:.08s}
 .card:nth-child(4),.gc:nth-child(4){animation-delay:.12s}
 .card:nth-child(5),.gc:nth-child(5){animation-delay:.16s}
 .card:nth-child(6),.gc:nth-child(6){animation-delay:.2s}
 .card:nth-child(7),.gc:nth-child(7){animation-delay:.24s}
 .card:nth-child(8),.gc:nth-child(8){animation-delay:.28s}}
@keyframes rise{from{opacity:0;transform:translateY(8px)}}
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.num{font-size:20px;font-weight:700;letter-spacing:-.02em;
 font-family:ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,monospace}
.meta{font-size:14px;font-weight:400;color:var(--m1);margin-top:3px}
.pill{font-size:12px;font-weight:500;letter-spacing:.01em;padding:7px 13px;border-radius:7px;white-space:nowrap;
 color:var(--ac-pale);background:color-mix(in srgb,var(--ac) 16%,transparent);border:1px solid color-mix(in srgb,var(--ac-soft) 32%,transparent)}
.pill.done{color:var(--m9);background:var(--chipbg);border-color:var(--chipline)}
.pill.hold{color:var(--holdtx);background:rgba(220,60,60,.14);border-color:rgba(220,90,90,.35)}
.pill.arch{color:var(--m9);background:var(--chipbg);border-color:var(--chipline)}
.pill .pic{vertical-align:-1.5px;margin-right:6px}
.pills{display:flex;flex-direction:column;gap:5px;align-items:flex-end}
/* progress timeline */
.tl{position:relative;height:46px;margin:22px 0 12px}
/* pixel-exact vertical geometry: track center y=7 == every dot's center
   (10px dot at y=2..12, 14px active dot at y=0..14, labels all start y=21) */
.track{position:absolute;top:6px;left:5%;right:5%;height:2px;background:var(--track);border-radius:2px}
.fill{position:absolute;top:6px;left:5%;height:2px;border-radius:2px;transition:width .4s;
 background:var(--ac)}
.node{position:absolute;top:0;transform:translateX(-50%);text-align:center}
/* dots are OPAQUE so the line disappears behind them instead of showing through */
.dot{width:10px;height:10px;border-radius:50%;background:var(--dot0);border:0;margin:2px auto 9px}
.node.done .dot{background:var(--ac)}
.node.now .dot{width:14px;height:14px;margin:0 auto 7px;background:var(--ac);
 box-shadow:0 0 0 4px color-mix(in srgb,var(--ac) 18%,transparent);
 animation:nowpulse 2.6s ease-in-out infinite}
@keyframes nowpulse{50%{box-shadow:0 0 0 7px color-mix(in srgb,var(--ac) 8%,transparent)}}
.lbl{font-size:9px;font-weight:500;letter-spacing:.06em;color:var(--m7);display:block;line-height:1.2;text-transform:uppercase}
.node.done .lbl{color:var(--m8)}
.node.now .lbl{color:var(--txtstrong);font-weight:600}
.foot{border-top:1px solid var(--hair2);padding-top:13px;display:flex;justify-content:space-between;
 align-items:center;gap:10px;flex-wrap:wrap}
.footacts{display:flex;gap:13px;align-items:center;flex-wrap:wrap}
.est{font-size:13px;font-weight:400;color:var(--m2)}
.view{font-size:13px;font-weight:500;color:var(--ac-soft);text-decoration:none;transition:color .15s}
.view:hover{color:var(--ac-pale)}
.archbtn{font-size:11.5px;font-weight:500;color:var(--m3);background:transparent;border:0;padding:0;cursor:pointer;
 width:auto;margin:0;font-family:inherit;letter-spacing:.01em;transition:color .15s}
.f:active,.archbtn:active,.hintx:active{transform:translateY(1px)}
.archbtn:hover{color:#c3c0d0}
.empty{color:var(--m6);font-size:13px;padding:40px 0;text-align:center}
.cover{width:44px;height:60px;object-fit:cover;border-radius:5px;border:1px solid var(--b3);background:var(--surface3);flex-shrink:0}
.hd{display:flex;gap:13px;align-items:flex-start;flex:1}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:16px;margin-top:24px}
.grid img{width:100%;border-radius:8px;border:1px solid var(--b3);background:var(--surface3);aspect-ratio:1.72/2.4;object-fit:cover;display:block}
.gc{background:var(--surface);
 border:1px solid var(--hair);border-radius:14px;padding:11px;
 display:flex;flex-direction:column;gap:2px;
 box-shadow:0 4px 16px var(--shc);
 transition:transform .18s,border-color .18s,opacity .18s,filter .18s}
.gc:hover{transform:translateY(-2px);border-color:var(--hairh)}
.gc>a,.gc .ph{position:relative}
.gc .ph{width:100%;aspect-ratio:1.72/2.4;border-radius:8px;border:1px dashed var(--b4);background:var(--ph);display:flex;align-items:center;justify-content:center;color:var(--m11);font-size:11px;font-weight:500;letter-spacing:.01em}
.gradebadge{position:absolute;top:7px;left:7px;z-index:2;font-size:11px;font-weight:800;letter-spacing:.02em;
 color:#0c0a12;background:#f5b73d;padding:3px 8px;border-radius:7px;
 box-shadow:0 2px 8px rgba(10,6,20,.55);border:1px solid rgba(255,255,255,.35)}
.gc .cn{font-size:13.5px;font-weight:600;color:var(--txt);margin-top:9px;letter-spacing:-.01em;line-height:19px;
 font-family:ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,monospace}
.cn.pre{color:var(--m3);font-size:11px;letter-spacing:.02em;font-family:inherit;line-height:19px}
.gc .nm{font-size:10.5px;font-weight:400;color:var(--m4);line-height:1.4;margin-top:3px;height:56px;
 display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:6px}
.own{margin-top:auto;background:var(--inp);border:1px solid var(--b1);border-radius:7px;color:var(--txt);font:inherit;font-size:11.5px;font-weight:400;padding:7px 9px;width:100%;outline:none;transition:border-color .15s}
.own::placeholder{color:var(--m10)}
.own:focus{border-color:var(--ac)}
.own.saved{border-color:#3a7c4f}
.own.errsave{border-color:#b25555}
.sublink{display:block;text-align:center;font-size:10.5px;font-weight:500;letter-spacing:.01em;color:var(--ac-pale);
 background:color-mix(in srgb,var(--ac) 13%,var(--mix));border:1px solid color-mix(in srgb,var(--ac) 32%,var(--mix));border-radius:7px;padding:6px 10px;text-decoration:none;margin-top:8px;
 transition:background .15s,color .15s,transform .12s}
.sublink:hover{background:color-mix(in srgb,var(--ac) 21%,var(--mix));color:var(--ac-ice)}
.sublink:active{transform:translateY(1px)}
.svc{text-align:center;font-size:10px;font-weight:400;letter-spacing:.01em;color:var(--m4);margin-top:6px}
/* lightbox for card scans */
.lb{position:fixed;inset:0;z-index:50;background:rgba(7,7,10,.84);display:none;
 align-items:center;justify-content:center;cursor:zoom-out;
 backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)}
.lb.open{display:flex}
.lb img{max-width:92vw;max-height:92vh;border-radius:10px;box-shadow:0 20px 80px rgba(4,2,12,.8)}
.grid a{cursor:zoom-in}
/* image loading shimmer (JS adds .ld once loaded) */
.grid img,.cover{background:linear-gradient(100deg,var(--sh1) 40%,var(--sh2) 50%,var(--sh1) 60%) 0 0/200% 100%;
 animation:shimmer 1.1s linear infinite}
.grid img.ld,.cover.ld{background:var(--surface3);animation:none}
@keyframes shimmer{to{background-position:-200% 0}}
/* day/night corner toggle */
#themeflip{position:fixed;right:18px;bottom:18px;z-index:40;width:42px;height:42px;
 border-radius:50%;background:var(--frost);border:1px solid var(--hair);color:var(--m2);
 backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);cursor:pointer;
 display:flex;align-items:center;justify-content:center;padding:0;margin:0;
 box-shadow:0 4px 14px var(--shc);transition:color .15s,transform .12s}
#themeflip:hover{color:var(--txt)}
#themeflip:active{transform:translateY(1px)}
/* archived grey-out */
.card.arch,.gc.arch{opacity:.42;filter:grayscale(.72)}
.card.arch:hover,.gc.arch:hover{opacity:.9;filter:grayscale(.15)}
.card.arch .fill{background:#4d4b59;box-shadow:none}
.card.arch .node.now .dot,.card.arch .node.done .dot{background:#5b5968;border-color:#5b5968;box-shadow:none;animation:none}
/* gate */
.gate{min-height:75vh;display:flex;align-items:center;justify-content:center}
.gbox{width:290px;text-align:center}
.gbox h1{font-size:26px}
input{width:100%;margin-top:26px;background:var(--surface2);border:1px solid var(--b1);border-radius:10px;
 color:var(--txt);font-size:14px;font-weight:400;text-align:center;padding:12px;font-family:inherit;outline:none}
input:focus{border-color:var(--ac)}
button{width:100%;margin-top:10px;background:var(--ac);border:0;border-radius:10px;color:#fff;
 font-size:13px;font-weight:600;letter-spacing:.02em;padding:12px;cursor:pointer;font-family:inherit;
 transition:background .15s,transform .12s}
button:hover{background:var(--ac-hot)}
button:active{transform:translateY(1px)}
.err{color:var(--err);font-size:11px;font-weight:600;margin-top:12px;min-height:14px}
/* mobile: hide stage labels entirely; only the CURRENT stage is named */
@media(max-width:640px){.lbl{font-size:0}
.node.now .lbl{font-size:8.5px;white-space:nowrap}
.card{padding:20px 18px}.num{font-size:18px}.meta{font-size:12.5px}
.hrow{flex-wrap:wrap}.synced{white-space:normal;text-align:left;padding-top:2px}}
"""

# favicon: accent-colored card mark, inline SVG so it needs no asset file
_FAV_FILL = ACCENT.replace("#", "%23")
FAVICON = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
           f"<rect width='64' height='64' rx='14' fill='{_FAV_FILL}'/>"
           "<rect x='20' y='14' width='24' height='36' rx='4' fill='none' stroke='white' stroke-width='4'/>"
           "<circle cx='32' cy='32' r='3.5' fill='white'/></svg>")

HEAD_HTML = f"""<link rel="icon" type="image/svg+xml" href="{FAVICON}">
<meta name="description" content="PSA grading submission tracker">
<script>(function(){{try{{var t=localStorage.getItem('psa_theme');
if(t&&t!=="{THEME}")document.documentElement.dataset.theme=t;}}catch(e){{}}}})()</script>"""

_SUN = ('<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4.4"/>'
        '<path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8'
        'M4.6 19.4l1.8-1.8M17.6 6.4l1.8-1.8"/></svg>')
_MOON = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
         'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
         '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>')

THEME_JS = f"""<script>
(function(){{
  var d=document.documentElement, def="{THEME}";
  var cur=d.dataset.theme||def;
  var b=document.createElement('button');b.id='themeflip';b.type='button';
  var SUN={json.dumps(_SUN)}, MOON={json.dumps(_MOON)};
  function render(){{
    b.innerHTML=(cur==='dark')?SUN:MOON;
    b.title=b.ariaLabel=(cur==='dark')?'Switch to light mode':'Switch to dark mode';
  }}
  b.addEventListener('click',function(){{
    cur=(cur==='dark')?'light':'dark';
    try{{
      if(cur===def){{delete d.dataset.theme;localStorage.removeItem('psa_theme');}}
      else{{d.dataset.theme=cur;localStorage.setItem('psa_theme',cur);}}
    }}catch(e){{d.dataset.theme=cur;}}
    render();
  }});
  document.body.appendChild(b);render();
}})();
</script>"""

def _pic(paths):
    """Tiny inline pill icon (stroke = currentColor so it inherits pill color)."""
    return (f'<svg class="pic" width="10" height="10" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="2.6" stroke-linecap="round" '
            f'stroke-linejoin="round">{paths}</svg>')

ICON_CLOCK = _pic('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>')
ICON_OUT = ('<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
            '<path d="m16 17 5-5-5-5"/><path d="M21 12H9"/></svg>')
ICON_CHECK = _pic('<path d="m5 13 4 4 10-10"/>')
ICON_HOLD = _pic('<path d="M9 5v14M15 5v14"/>')

def eta_pill(s):
    """Status pill for a sub: return ETA, shipped, hold, or pending."""
    if s["on_hold"]:
        return f'<span class="pill hold">{ICON_HOLD}On hold</span>'
    if s["status"] == "Shipped":
        return f'<span class="pill done">{ICON_CHECK}Shipped</span>'
    if s["est_end"] or s["est_start"]:
        return f'<span class="pill">{ICON_CLOCK}Back ~{html.escape(short_date(s["est_end"] or s["est_start"]))}</span>'
    return f'<span class="pill done">{ICON_CLOCK}ETA pending</span>'

def gate_page(error=""):
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(SITE_TITLE)}</title>
{HEAD_HTML}
<style>{THEME_VARS}{CSS}</style></head><body><div class="wrap"><div class="gate"><div class="gbox">
{logo_tag()}<h1>{html.escape(SITE_TITLE)}</h1><div class="sub">{html.escape(SITE_TAGLINE)}</div>
<form method="POST" action="/login">
<input type="password" name="password" placeholder="Password or email" autofocus autocomplete="current-password">
<button type="submit">Enter</button></form>
<div class="err">{html.escape(error)}</div>
</div></div></div>{THEME_JS}</body></html>"""

def timeline_html(status):
    """The horizontal stage progress bar (Arrived → … → Shipped). Shared by the
    dashboard cards and the sub detail page."""
    idx = stage_index(status)
    pct = 90.0 * idx / (len(STAGES) - 1)
    nodes = []
    for i, name in enumerate(STAGES):
        cls = "node now" if i == idx else ("node done" if i < idx else "node")
        left = 5 + 90.0 * i / (len(STAGES) - 1)
        nodes.append(f'<div class="{cls}" style="left:{left:.1f}%"><div class="dot"></div>'
                     f'<span class="lbl">{html.escape(name.upper())}</span></div>')
    return (f'<div class="tl"><div class="track"></div>'
            f'<div class="fill" style="width:{pct:.1f}%"></div>{"".join(nodes)}</div>')

def card_html(s, archived=False):
    # The stepper already highlights the current stage, so the pill carries the
    # NEXT most useful fact instead: when the cards come back.
    # the pill carries the ETA (latest expected return date), so the footer no
    # longer repeats an "Expected return" line
    pill = eta_pill(s)

    if s["status"] == "Shipped" and s["shipped"]:
        foot = f'Shipped {html.escape(s["shipped"])}'
        if s["carrier"] and s["tracking"]:
            foot += f' · {html.escape(s["carrier"])} {html.escape(s["tracking"])}'
    elif s["grades_ready"]:
        foot = "Grades ready"
    else:
        foot = ""

    cover = (f'<img class="cover" loading="lazy" src="/img?u={urllib.parse.quote(img_url(s["thumb"], "small"))}" alt="">'
             if s.get("thumb") else '')
    sub = html.escape(s['sub_number'])
    if archived:
        pill += '<span class="pill arch">Archived</span>'
    archattr = ' data-arch="1" style="display:none"' if archived else ''
    return f"""<div class="card{' arch' if archived else ''}" data-status="{html.escape(s['status'])}"{archattr}>
<div class="top"><div class="hd">{cover}<div><div class="num">#{sub}</div>
<div class="meta">{html.escape(s['service'])} · {s['card_count']} cards</div></div></div><div class="pills">{pill}</div></div>
{timeline_html(s['status'])}
<div class="foot"><span class="est">{foot}</span>
<a class="view" href="/sub/{sub}">View cards</a></div></div>"""

def search_box(value="", owner="", ph=None):
    """Unified people+card search input with a live-preview dropdown (needs SEARCH_JS).
    With owner set, card results are scoped to that person (SEARCH_JS reads data-owner)."""
    if ph is None:
        ph = f"Search {owner}'s cards…" if owner else "Search names or cards…"
    icon = ('<svg class="sicon" width="14" height="14" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2.4" stroke-linecap="round">'
            '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.8-3.8"/></svg>')
    return (f'<div class="searchwrap">{icon}<input class="searchbar" id="q" type="search" '
            f'autocomplete="off" spellcheck="false" placeholder="{html.escape(ph)}" '
            f'data-owner="{html.escape(owner)}" '
            f'value="{html.escape(value)}"><div class="preview" id="preview"></div></div>')

SEARCH_JS = """<script>
(function(){
  var q=document.getElementById('q'), pv=document.getElementById('preview'), t;
  if(!q) return;
  var own=q.dataset.owner||'';
  var scope=own?('&owner='+encodeURIComponent(own)):'';
  function esc(s){var d=document.createElement('div');d.textContent=s==null?'':s;return d.innerHTML;}
  function render(data){
    var h='';
    if(data.names&&data.names.length){
      h+='<div class="pvsec">People</div>';
      data.names.forEach(function(n){
        h+='<a class="pvrow" href="/cards?owner='+encodeURIComponent(n)+'"><span class="pvtag">Person</span><span>'+esc(n)+'</span></a>';
      });
    }
    if(data.cards&&data.cards.length){
      h+='<div class="pvsec">Cards</div>';
      data.cards.forEach(function(c){
        var img=c.img?'<img class="pvimg" src="'+c.img+'" alt="">':'';
        var sub=esc(c.cert?('#'+c.cert):('sub #'+c.sub))+(c.owner?(' · '+esc(c.owner)):'');
        h+='<a class="pvrow" href="/sub/'+encodeURIComponent(c.sub)+'">'+img+'<span>'+esc(c.name||'Card')+'<small>'+sub+'</small></span></a>';
      });
    }
    if(!h) h='<div class="pvempty">No matches</div>';
    pv.innerHTML=h; pv.style.display='block';
  }
  function go(){
    clearTimeout(t);
    t=setTimeout(function(){
      if(pv.style.display!=='block'){pv.innerHTML='<div class="pvempty">Searching…</div>';pv.style.display='block';}
      fetch('/suggest?q='+encodeURIComponent(q.value.trim())+scope,{headers:{'X-Requested-With':'fetch'}})
        .then(function(r){return r.json();}).then(render).catch(function(){pv.style.display='none';});
    },110);
  }
  q.addEventListener('input',go);
  q.addEventListener('focus',go);
  q.addEventListener('keydown',function(e){
    if(e.key==='Enter'){e.preventDefault();location.href='/search?q='+encodeURIComponent(q.value.trim())+scope;}
    else if(e.key==='Escape'){pv.style.display='none';}
  });
  document.addEventListener('click',function(e){ if(!pv.contains(e.target)&&e.target!==q) pv.style.display='none'; });
})();
</script>"""

ARCH_JS = """<script>
document.querySelectorAll('.archbtn').forEach(function(b){
  b.addEventListener('click', function(){
    b.disabled = true;
    fetch('/archive', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body:'sub='+encodeURIComponent(b.dataset.sub)+'&on='+b.dataset.on})
     .then(function(r){ if(r.ok){ location.reload(); } else { b.disabled = false; } });
  });
});
</script>"""

LIGHTBOX_JS = """<script>
(function(){
  var links=document.querySelectorAll('.grid a[href^="/img"]');
  if(!links.length) return;
  var lb=document.createElement('div'); lb.className='lb'; lb.innerHTML='<img alt="">';
  document.body.appendChild(lb);
  var im=lb.querySelector('img');
  links.forEach(function(a){
    a.addEventListener('click', function(e){
      e.preventDefault();
      im.src=a.getAttribute('href');
      lb.classList.add('open');
    });
  });
  function close(){ lb.classList.remove('open'); im.src=''; }
  lb.addEventListener('click', close);
  document.addEventListener('keydown', function(e){ if(e.key==='Escape') close(); });
})();
</script>"""

OWNER_JS = """
<script>
document.querySelectorAll('.own').forEach(function(i){
  function fail(){ i.classList.add('errsave'); setTimeout(function(){i.classList.remove('errsave')},1200); }
  i.addEventListener('blur', function(){
    fetch('/owner', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body:'cert_id='+encodeURIComponent(i.dataset.cert)+'&owner='+encodeURIComponent(i.value)})
     .then(function(r){ if(r.ok){ i.classList.add('saved'); setTimeout(function(){i.classList.remove('saved')},900);} else { fail(); } })
     .catch(fail);
  });
  i.addEventListener('keydown', function(e){ if(e.key==='Enter') i.blur(); });
});
</script>"""

# page effects: swap the loading shimmer off images once loaded, and track the
# cursor per card so the spotlight border knows where to glow
FX_JS = """<script>
document.querySelectorAll('.grid img,.cover').forEach(function(m){
  var done=function(){m.classList.add('ld');};
  if(m.complete){done();}
  else{m.addEventListener('load',done);m.addEventListener('error',done);}
});
document.querySelectorAll('.card,.gc').forEach(function(c){
  var b=document.createElement('div');b.className='bloom';c.appendChild(b);
  c.addEventListener('pointermove',function(e){
    var r=c.getBoundingClientRect();
    c.style.setProperty('--mx',(e.clientX-r.left)+'px');
    c.style.setProperty('--my',(e.clientY-r.top)+'px');
  });
});
</script>"""

# person page: fold archived-sub cards behind a toggle below the active grid
ARCHFOLD_JS = """<script>
(function(){
  var af=document.getElementById('archtoggle'),ag=document.getElementById('archgrid');
  if(!af)return;
  af.addEventListener('click',function(){
    var on=af.classList.toggle('on');
    ag.style.display=on?'':'none';
    if(on)ag.scrollIntoView({behavior:'smooth',block:'nearest'});
  });
})();
</script>"""

def card_tile(c, owners, show_sub=False, archived=False, service="", customer=False, statline=""):
    cid = html.escape(str(c["cert_id"]))
    is_prelim = str(c["cert_id"]).startswith("spec:")
    name = html.escape(smart_title(c["name"] or ""))
    owner = html.escape(owners.get(str(c["cert_id"]), ""))
    grade = f'<span class="gradebadge">PSA {html.escape(c["grade"])}</span>' if c.get("grade") else ""
    if is_prelim:
        head = '<div class="cn pre">Prelim</div>'
    else:
        head = f'<div class="cn">{html.escape(c["cert_no"] or c["cert_id"])}</div>'
    if c.get("front_thumb"):
        src = "/img?u=" + urllib.parse.quote(img_url(c["front_thumb"], "small"))
        big = "/img?u=" + urllib.parse.quote(img_url(c["front_thumb"], "large"))
        img = f'<a href="{big}">{grade}<img loading="lazy" src="{src}" alt=""></a>'  # grade overlays scan; opens in lightbox
    else:
        img = f'<div class="ph">{grade}No image yet</div>'
    if customer:
        # customers never link into submissions (those show other people's cards);
        # the chip carries this card's own status instead
        sub_link = f'<div class="sublink" style="cursor:default">{html.escape(statline)}</div>' if statline else ""
    else:
        sub_link = (f'<a class="sublink" href="/sub/{html.escape(str(c["sub_number"]))}">Go to sub #{html.escape(str(c["sub_number"]))}</a>'
                    if show_sub else "")
    svc = f'<div class="svc">{html.escape(service)}</div>' if (show_sub and service) else ""
    own_input = ("" if customer else
                 f'<input class="own" data-cert="{cid}" value="{owner}" placeholder="+ owner name">')
    return (f'<div class="gc{" arch" if archived else ""}">{img}{sub_link}{svc}{head}'
            f'<div class="nm">{name}</div>'
            f'{own_input}'
            f'</div>')

def untagged_count(a, active_subs):
    """Cards in ACTIVE (non-archived) subs that have no owner yet - the operator's
    to-tag worklist. Archived subs are excluded (old stuff, intentionally untagged)."""
    owners = owners_map(a)
    active_nums = {s["sub_number"] for s in active_subs}
    n = 0
    for c in load_all_cards(a):
        if c["sub_number"] in active_nums and not owners.get(str(c["cert_id"]), ""):
            n += 1
    return n

def dash_page(a, subs):
    arch = archived_set(a)
    active = [s for s in subs if s["sub_number"] not in arch]
    gone = [s for s in subs if s["sub_number"] in arch]
    body = ("".join(card_html(s) for s in active) + "".join(card_html(s, archived=True) for s in gone)
            or '<div class="empty">No submissions yet. Cards appear here once PSA receives them.</div>')
    updated = max((s["updated_at"] or "" for s in subs), default="")
    stamp = fmt_local(updated) if updated else "n/a"
    toolbar = f'<div class="toolbar">{search_box()}</div>'
    hint = ('<div class="hint" id="hint">👋 New here? Type your name in the search to find just your cards.'
            '<button class="hintx" id="hintx" aria-label="dismiss">✕</button></div>')
    pills = []
    if gone:
        pills.append(f'<span class="f farch" id="archtoggle">Archived · {len(gone)}</span>')
    untag = untagged_count(a, active)
    if untag:
        pills.append(f'<a class="f" href="/cards?owner=unassigned">{untag} need owners</a>')
    filters = f'<div class="filters">{"".join(pills)}</div>' if pills else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(SITE_TITLE)}</title>
{HEAD_HTML}
<style>{THEME_VARS}{CSS}</style></head><body><div class="wrap">
<div class="hrow"><div>{logo_tag()}<h1 class="big">{html.escape(SITE_TITLE)}</h1></div>
<div style="display:flex;gap:14px;align-items:flex-start"><div class="synced">Last refreshed<b>{html.escape(stamp)}</b></div><a class="lgout" href="/logout" title="Sign out" aria-label="Sign out">{ICON_OUT}</a></div></div>
{hint}
{toolbar}
{filters}
<div id="list">{body}</div>
</div>
<script>
(function(){{var h=document.getElementById('hint');
 if(h&&localStorage.getItem('psa_hint_seen')){{h.style.display='none';}}
 var x=document.getElementById('hintx');
 if(x)x.addEventListener('click',function(){{h.style.display='none';localStorage.setItem('psa_hint_seen','1');}});}})();
var af=document.getElementById('archtoggle');
if(af)af.addEventListener('click',function(){{
  var on=af.classList.toggle('on');
  document.querySelectorAll('#list .card').forEach(function(c){{
    var a=c.dataset.arch==='1';
    c.style.display=(on?a:!a)?'':'none';
  }});
}});
</script>{SEARCH_JS}{FX_JS}{THEME_JS}</body></html>"""

def eta_badge(s):
    """Top-right ETA badge for the sub detail page: expected return window, or
    ship date + tracking once shipped."""
    if s["status"] == "Shipped" and s["shipped"]:
        note = (f'<span class="estnote">{html.escape(s["carrier"])} {html.escape(s["tracking"])}</span>'
                if s["carrier"] and s["tracking"] else "")
        return f'<div class="synced">Shipped<b>{html.escape(s["shipped"])}</b>{note}</div>'
    if s["est_start"]:
        val = html.escape(s["est_start"])
        if s["est_end"]:
            val += f' to {html.escape(s["est_end"])}'
        note = '<span class="estnote">grades ready</span>' if s["grades_ready"] else ""
        return f'<div class="synced">PSA ETA<b>{val}</b>{note}</div>'
    return '<div class="synced">PSA ETA<b>Estimate pending</b></div>'

def detail_page(a, sub):
    num = sub["sub_number"]
    archived = num in archived_set(a)
    cards = load_cards(a, num)
    owners = owners_map(a)
    if cards:
        body = '<div class="grid">' + "".join(card_tile(c, owners, archived=archived) for c in cards) + "</div>"
    elif json.loads(sub["cert_ids"] or "[]"):
        body = '<div class="empty">Card images not synced yet. They appear after the next sync (once cards reach Research &amp; ID).</div>'
    else:
        body = '<div class="empty">No cards assigned yet. PSA lists them during Research &amp; ID.</div>'
    if archived:
        act = f'<button class="archbtn" data-sub="{html.escape(num)}" data-on="0">Unarchive</button>'
        tag = ' · <span style="color:var(--m9)">Archived</span>'
    else:
        act = f'<button class="archbtn" data-sub="{html.escape(num)}" data-on="1">Archive</button>'
        tag = ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>#{html.escape(num)}</title>
{HEAD_HTML}
<style>{THEME_VARS}{CSS}</style></head><body><div class="wrap">
<div class="foot" style="border:0;padding:0"><a class="view" href="/">← All submissions</a><span class="footacts">{act}</span></div>
<div class="hrow" style="margin-top:14px"><div><h1>#{html.escape(num)}</h1>
<div class="sub">{html.escape(sub['service'])} · {sub['card_count']} cards · {html.escape(sub['status'])}{tag}</div></div>
{eta_badge(sub)}</div>
<div class="card" style="margin-top:18px">{timeline_html(sub['status'])}</div>
{body}
</div>{OWNER_JS}{ARCH_JS}{LIGHTBOX_JS}{FX_JS}{THEME_JS}</body></html>"""

def grade_summary(cards):
    """'3× PSA 10 · 2× PSA 9' from a card list, or '' if none graded."""
    import collections
    g = collections.Counter(c["grade"] for c in cards if c.get("grade"))
    if not g:
        return ""
    def sortkey(item):
        try:
            return (-float(item[0].split()[0]),)
        except ValueError:
            return (0,)
    parts = " · ".join(f"{n}× PSA {gr}" for gr, n in sorted(g.items(), key=sortkey))
    return parts

def people_page(a, owner, customer=False):
    owners = owners_map(a)
    arch = archived_set(a)
    unassigned = (not customer) and owner.strip().lower() == "unassigned"
    subs_by = {s["sub_number"]: s for s in load_subs(a)}
    if unassigned:  # operator worklist: untagged cards in active subs
        active_nums = {n for n in subs_by if n not in arch}
        cards = [c for c in load_all_cards(a)
                 if c["sub_number"] in active_nums and not owners.get(str(c["cert_id"]), "")]
        title, sub_line = "Unassigned", f"{len(cards)} cards awaiting an owner"
    else:
        want = owner.strip().lower()
        cards = [c for c in load_all_cards(a) if owners.get(str(c["cert_id"]), "").lower() == want]
        title, sub_line = owner, f"{len(cards)} cards with {a['label']}"
    svc_map = {n: s["service"] for n, s in subs_by.items()}
    # archived subs' cards stay on the person page but are folded behind an
    # ARCHIVED toggle below the active grid instead of greyed out inline
    act_cards = [c for c in cards if c["sub_number"] not in arch]
    arc_cards = [c for c in cards if c["sub_number"] in arch]
    if customer:
        title, sub_line = "Your cards", f"{len(act_cards)} cards · {owner}"
    elif not unassigned:
        sub_line = f"{len(act_cards)} cards with {a['label']}"
    def tiles(cs):
        return "".join(card_tile(c, owners, show_sub=True, archived=(c["sub_number"] in arch),
                                 service=svc_map.get(c["sub_number"], ""), customer=customer,
                                 statline=cust_statline(subs_by.get(c["sub_number"])))
                       for c in cs)
    if act_cards:
        grid = '<div class="grid">' + tiles(act_cards) + "</div>"
    elif unassigned:
        grid = '<div class="empty">🎉 Every active card has an owner tag.</div>'
    elif arc_cards:
        grid = f'<div class="empty">All of {html.escape(owner)}’s cards are in archived submissions.</div>'
    else:
        grid = f'<div class="empty">No cards tagged to “{html.escape(owner)}” yet.</div>'
    archsec = ""
    if arc_cards:
        archsec = (f'<div class="filters" style="margin:30px 0 0">'
                   f'<span class="f farch" id="archtoggle">Archived · {len(arc_cards)}</span></div>'
                   f'<div class="grid" id="archgrid" style="display:none">{tiles(arc_cards)}</div>')
    if unassigned or customer:
        est = ""  # store cost/coverage numbers are operator-only
    else:
        total, unpriced, covered, uncovered = 0.0, 0, 0.0, 0
        for c in act_cards:
            p = service_price(a, svc_map.get(c["sub_number"], ""))
            if p is None:
                unpriced += 1
            else:
                total += p
            dv = c.get("declared_value")
            if dv is None:
                uncovered += 1
            else:
                covered += dv
        gsum = grade_summary(act_cards)
        gline = f'<span class="lbl2">Grades</span><b>{html.escape(gsum)}</b>' if gsum else ""
        ins = (f'<span class="lbl2">Insured coverage</span><b>${covered:,.0f}{"+" if uncovered else ""}</b>'
               if covered or uncovered else "")
        est = (f'<div class="synced">Est. grading cost<b>${total:,.2f}'
               f'{"+" if unpriced else ""}</b>{ins}{gline}'
               f'<span class="estnote">base per-card fees · pending PSA upcharges<br>'
               f'coverage = declared value on file with PSA</span></div>') if act_cards else ""
    back = ('<a class="view" href="/logout">Sign out</a>' if customer
            else '<a class="view" href="/">← All submissions</a>')
    page_title = "Your cards" if customer else f"{title}'s cards"
    owner_js = "" if customer else OWNER_JS
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(page_title)}</title>
{HEAD_HTML}
<style>{THEME_VARS}{CSS}</style></head><body><div class="wrap">
{back}
<div class="hrow" style="margin-top:14px"><div><h1>{html.escape(title)}</h1>
<div class="sub">{html.escape(sub_line)}</div></div>{est}</div>
<div class="toolbar">{search_box(owner="" if unassigned else owner, ph="Search your cards…" if customer else None)}</div>
{grid}
{archsec}
</div>{SEARCH_JS}{owner_js}{LIGHTBOX_JS}{ARCHFOLD_JS}{FX_JS}{THEME_JS}</body></html>"""

def customer_page(a, email):
    """Customer home: THEIR cards grouped by submission, each group carrying the
    sub's service line, ETA pill, and the full stage timeline."""
    owners = owners_map(a)
    arch = archived_set(a)
    subs_by = {s["sub_number"]: s for s in load_subs(a)}
    want = email.strip().lower()
    mine = [c for c in load_all_cards(a) if owners.get(str(c["cert_id"]), "").lower() == want]
    groups = {}
    for c in mine:
        groups.setdefault(c["sub_number"], []).append(c)

    def group_html(n, cs):
        s = subs_by.get(n)
        svc = html.escape(s["service"]) if s else ""
        pill = eta_pill(s) if s else ""
        tl = timeline_html(s["status"]) if s else ""
        cnt = f'{len(cs)} card{"s" if len(cs) != 1 else ""}'
        tiles = "".join(card_tile(c, owners, show_sub=False, archived=(n in arch), customer=True)
                        for c in cs)
        return (f'<div class="card grp{" arch" if n in arch else ""}">'
                f'<div class="top"><div><div class="num">#{html.escape(str(n))}</div>'
                f'<div class="meta">{svc} · {cnt}</div></div><div class="pills">{pill}</div></div>'
                f'{tl}<div class="grid" style="margin-top:14px">{tiles}</div></div>')

    order = sorted(groups, key=lambda n: -int(n) if str(n).isdigit() else 0)
    act = [n for n in order if n not in arch]
    gone = [n for n in order if n in arch]
    body = ("".join(group_html(n, groups[n]) for n in act)
            or '<div class="empty">No cards yet — they appear once the store receives your submission.</div>')
    archsec = ""
    if gone:
        archsec = (f'<div class="filters" style="margin:30px 0 0">'
                   f'<span class="f farch" id="archtoggle">Archived · {len(gone)}</span></div>'
                   f'<div id="archgrid" style="display:none">'
                   + "".join(group_html(n, groups[n]) for n in gone) + '</div>')
    total = sum(len(groups[n]) for n in act)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Your cards</title>
{HEAD_HTML}
<style>{THEME_VARS}{CSS}</style></head><body><div class="wrap">
<a class="view" href="/logout">Sign out</a>
<div class="hrow" style="margin-top:14px"><div><h1>Your cards</h1>
<div class="sub">{total} card{"s" if total != 1 else ""} · {html.escape(email)}</div></div></div>
<div class="toolbar">{search_box(owner=email, ph="Search your cards…")}</div>
<div style="margin-top:28px">{body}</div>
{archsec}
</div>{SEARCH_JS}{LIGHTBOX_JS}{ARCHFOLD_JS}{FX_JS}{THEME_JS}</body></html>"""

def search_page(a, q, owner="", customer=False):
    ql = (q or "").strip().lower()
    owners = owners_map(a)
    want = (owner or "").strip().lower()
    res = []
    if ql:
        for c in load_all_cards(a):
            if want and owners.get(str(c["cert_id"]), "").lower() != want:
                continue
            hay = " ".join((
                c.get("name") or "", str(c.get("cert_no") or ""),
                str(c.get("cert_id") or ""), owners.get(str(c["cert_id"]), ""),
            )).lower()
            if ql in hay:
                res.append(c)
    if res:
        arch = archived_set(a)
        subs_by = {s["sub_number"]: s for s in load_subs(a)}
        grid = '<div class="grid">' + "".join(
            card_tile(c, owners, show_sub=True, archived=(c["sub_number"] in arch),
                      service=(subs_by.get(c["sub_number"]) or {}).get("service", ""),
                      customer=customer,
                      statline=cust_statline(subs_by.get(c["sub_number"]))) for c in res) + "</div>"
    elif ql:
        grid = f'<div class="empty">No cards match “{html.escape(q)}”.</div>'
    else:
        grid = '<div class="empty">Type a card name or number to search.</div>'
    count = f"{len(res)} match" + ("es" if len(res) != 1 else "") if ql else "All cards"
    if customer:
        count += " · your cards only"
        back = '<a class="view" href="/">← Your cards</a>'
    elif owner:
        count += f" · {html.escape(owner)}'s cards only"
        back = (f'<a class="view" href="/cards?owner={urllib.parse.quote(owner)}">'
                f'← {html.escape(owner)}\'s cards</a>')
    else:
        back = '<a class="view" href="/">← All submissions</a>'
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Search</title>
{HEAD_HTML}
<style>{THEME_VARS}{CSS}</style></head><body><div class="wrap">
{back}
<h1 style="margin-top:14px">Search</h1>
<div class="sub">{count}</div>
<div class="toolbar">{search_box(q or '', owner=owner, ph="Search your cards…" if customer else None)}</div>
{grid}
</div>{SEARCH_JS}{"" if customer else OWNER_JS}{LIGHTBOX_JS}{FX_JS}{THEME_JS}</body></html>"""

# ---------- server ----------

class H(BaseHTTPRequestHandler):
    server_version = "psa-tracker"

    def log_message(self, fmt, *a):
        print(f"{self.address_string()} {fmt % a}", flush=True)

    def client_ip(self):
        xff = self.headers.get("X-Forwarded-For", "")
        return xff.split(",")[0].strip() if xff else self.address_string()

    def authed(self):
        """Return (account dict, customer_email) for this session, or None.
        customer_email == "" means a full site-password (admin) session."""
        raw = self.headers.get("Cookie", "")
        for part in raw.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "psa_session":
                got = valid_token(v)
                if got:
                    acct = load_accounts().get(got[0])
                    if acct:
                        return acct, got[1]
        return None

    def send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def serve_img(self, query):
        url = urllib.parse.parse_qs(query).get("u", [""])[0]
        if urllib.parse.urlparse(url).netloc != IMG_HOST:
            return self.send(400, "bad host", "text/plain")
        os.makedirs(IMG_CACHE, exist_ok=True)
        fp = os.path.join(IMG_CACHE, hashlib.sha256(url.encode()).hexdigest() + ".jpg")
        if not os.path.exists(fp):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "psa-tracker"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    ctype = r.headers.get("Content-Type", "")
                    data = r.read(MAX_IMG_BYTES + 1)
                if len(data) > MAX_IMG_BYTES or not ctype.startswith("image/"):
                    return self.send(404, "img rejected", "text/plain")
                # atomic write so a crash mid-download can't leave a corrupt cache file
                tmp = f"{fp}.tmp{os.getpid()}.{threading.get_ident()}"
                with open(tmp, "wb") as f:
                    f.write(data)
                os.replace(tmp, fp)
            except Exception:
                return self.send(404, "img fetch failed", "text/plain")
        data = open(fp, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=604800")
        self.end_headers()
        self.wfile.write(data)

    def do_HEAD(self):
        # uptime checks: cheap 200, headers only
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def serve_logo(self):
        if not os.path.exists(LOGO_PATH):
            return self.send(404, "no logo", "text/plain")
        ext = LOGO_PATH.rsplit(".", 1)[-1].lower()
        ctype = {"svg": "image/svg+xml", "png": "image/png",
                 "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "application/octet-stream")
        data = open(LOGO_PATH, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/logo":
            return self.serve_logo()
        got = self.authed()
        if not got:
            return self.send(200, gate_page())
        acct, cust = got
        if path == "/img":
            return self.serve_img(parsed.query)
        if path == "/logout":
            return self.send(302, "", extra=[("Location", "/"),
                ("Set-Cookie", "psa_session=; Path=/; Max-Age=0")])
        if cust:
            # customer sessions are pinned server-side to their own email:
            # no dashboard, no other owners, no sub pages (they show other
            # customers' cards), no owner directory
            if path == "/":
                return self.send(200, customer_page(acct, cust))
            if path == "/search":
                qs = urllib.parse.parse_qs(parsed.query)
                return self.send(200, search_page(acct, qs.get("q", [""])[0],
                                                  owner=cust, customer=True))
            if path == "/suggest":
                if not suggest_allowed(self.client_ip()):
                    return self.send(429, '{"names":[],"cards":[]}', "application/json; charset=utf-8")
                qs = urllib.parse.parse_qs(parsed.query)
                return self.send(200, json.dumps(suggest(acct, qs.get("q", [""])[0], owner=cust)),
                                 "application/json; charset=utf-8")
            return self.send(302, "", extra=[("Location", "/")])
        if path == "/":
            return self.send(200, dash_page(acct, load_subs(acct)))
        if path == "/cards":
            owner = urllib.parse.parse_qs(parsed.query).get("owner", [""])[0]
            return self.send(200, people_page(acct, owner))
        if path == "/search":
            qs = urllib.parse.parse_qs(parsed.query)
            return self.send(200, search_page(acct, qs.get("q", [""])[0],
                                              owner=qs.get("owner", [""])[0]))
        if path == "/suggest":
            if not suggest_allowed(self.client_ip()):
                return self.send(429, '{"names":[],"cards":[]}', "application/json; charset=utf-8")
            qs = urllib.parse.parse_qs(parsed.query)
            return self.send(200, json.dumps(suggest(acct, qs.get("q", [""])[0],
                                                     owner=qs.get("owner", [""])[0])),
                             "application/json; charset=utf-8")
        if path.startswith("/sub/"):
            num = path.split("/sub/", 1)[1].strip("/")
            sub = load_sub(acct, num)
            if not sub:
                return self.send(404, '<div class="empty">Not found</div>')
            return self.send(200, detail_page(acct, sub))
        self.send(404, "not found", "text/plain")

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/owner":
            got = self.authed()
            if not got or got[1]:  # customers can't tag or archive
                return self.send(403, "auth", "text/plain")
            acct = got[0]
            n = int(self.headers.get("Content-Length", "0") or 0)
            form = urllib.parse.parse_qs(self.rfile.read(min(n, 2048)).decode("utf-8", "replace"))
            cid = (form.get("cert_id") or [""])[0]
            owner = (form.get("owner") or [""])[0]
            if cid:
                set_owner(acct, cid, owner)
            return self.send(204, "", "text/plain")
        if path == "/archive":
            got = self.authed()
            if not got or got[1]:  # customers can't tag or archive
                return self.send(403, "auth", "text/plain")
            acct = got[0]
            n = int(self.headers.get("Content-Length", "0") or 0)
            form = urllib.parse.parse_qs(self.rfile.read(min(n, 2048)).decode("utf-8", "replace"))
            sub = (form.get("sub") or [""])[0]
            on = (form.get("on") or [""])[0] in ("1", "true", "on")
            if sub:
                set_archived(acct, sub, on)
            return self.send(204, "", "text/plain")
        if path != "/login":
            return self.send(404, "not found", "text/plain")
        ip = self.client_ip()
        n = int(self.headers.get("Content-Length", "0") or 0)
        form = urllib.parse.parse_qs(self.rfile.read(min(n, 4096)).decode("utf-8", "replace"))
        given = (form.get("password") or [""])[0]
        time.sleep(0.4)  # blunt the brute force; throttle below does the real work
        if login_locked(ip):
            return self.send(200, gate_page("Too many attempts. Try again in a few minutes."))
        # The password IS the account selector: whichever account's site password
        # matches is the account this session gets. Passwords are unique per account.
        matched = None
        for a in load_accounts().values():
            if hmac.compare_digest(given, a["password"]):
                matched = a
                break
        email = ""
        if not matched and "@" in given:
            # customer login: the email IS the credential (store product;
            # view-only, low-stakes by design). Matches owner tags.
            hit = find_customer(given)
            if hit:
                matched, email = hit, given.strip().lower()
        if not matched:
            login_fail(ip)
            msg = ("No cards found for that email yet." if "@" in given
                   else "Incorrect password.")
            return self.send(200, gate_page(msg))
        login_ok(ip)
        exp = int(time.time()) + COOKIE_DAYS * 86400
        cookie = (f"psa_session={make_token(matched['id'], exp, email)}; Path=/; Max-Age={COOKIE_DAYS*86400}; "
                  "HttpOnly; SameSite=Lax" + ("; Secure" if COOKIE_SECURE else ""))
        self.send(302, "", extra=[("Location", "/"), ("Set-Cookie", cookie)])


def main():
    if not SECRET:
        raise SystemExit("PSA_SECRET must be set")
    accts = load_accounts()
    if not accts:
        raise SystemExit(f"no accounts found in {ACCOUNTS_DIR} - run add_account.sh first")
    dupes = len(accts) - len({a["password"] for a in accts.values()})
    if dupes:
        print(f"WARNING: {dupes} duplicate site password(s) across accounts - "
              "login routes to the first match; make them unique!", flush=True)
    print(f"serving on {BIND}:{PORT} - {len(accts)} account(s): {', '.join(accts)}", flush=True)
    ThreadingHTTPServer((BIND, PORT), H).serve_forever()

if __name__ == "__main__":
    main()
