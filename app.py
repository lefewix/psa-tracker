#!/usr/bin/env python3
"""psa-tracker web: multi-account password gate + submissions dashboard.

Stdlib only. Reads each account's psa.db (filled by psa_watch.py, never written
here) and writes that account's owners.db (owner tags + archived subs).

Multi-account: every directory under PSA_ACCOUNTS_DIR holding an account.env is
a tracked PSA account. Each account has its OWN site password; the login form
routes whoever types a password to the matching account - the account chooser is
invisible by design. Site passwords must therefore be unique across accounts.

Config: every environment key this file reads, global (systemd EnvironmentFile)
and per-account (account.env), is listed with its default in deploy/example.env.
"""
import base64, csv, gzip, hashlib, hmac, html, io, json, os, re, shlex, sqlite3, subprocess, sys, tempfile, threading, time, traceback
import urllib.parse, urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo
from psa_common import env_set

SECRET = os.environ.get("PSA_SECRET", "").encode()
BIND = os.environ.get("PSA_BIND", "0.0.0.0")
PORT = int(os.environ.get("PSA_PORT", "8080"))
# 8 months, a whole PSA turnaround. Rotating the site password revokes every
# live cookie anyway, see pw_slug.
COOKIE_DAYS = 180
COOKIE_SECURE = os.environ.get("PSA_COOKIE_SECURE", "1") not in ("0", "false", "no")
# sha256 hex of the settings password. Typing that password on the main gate
# (or at the gear icon's prompt) opens /settings. Unset -> settings disabled.
SETTINGS_HASH = os.environ.get("PSA_SETTINGS_PW_HASH", "").lower()
SETTINGS_MINUTES = 60
GLOBAL_ENV = os.environ.get("PSA_GLOBAL_ENV", "/etc/psa-tracker.env")
SITE_TITLE = os.environ.get("SITE_TITLE", "Submissions")
SITE_TAGLINE = os.environ.get("SITE_TAGLINE", "PSA grading tracker")

def _hexcolor(env, default):
    """Env-supplied brand color, validated so env can't inject CSS."""
    v = os.environ.get(env, "").strip()
    return v if re.fullmatch(r"#[0-9a-fA-F]{6}", v) else default

# Per-store branding: one primary accent + one ambient secondary; every other
# shade is derived in CSS via color-mix, so stores only pick two colors.
ACCENT = _hexcolor("PSA_ACCENT", "#3a6fd8")
ACCENT_2 = _hexcolor("PSA_ACCENT_2", "#5b8def")
# Light is the flagship sheet; a store opts into the dark ground with PSA_THEME=dark.
THEME = "dark" if os.environ.get("PSA_THEME", "light").strip().lower() == "dark" else "light"

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

# Accent-derived shades flip direction per theme: --ac-pale is the accent as
# TEXT (deepened on the white sheet, lightened on the dark one), --ac-hot its
# hover. --ac-fill is the only shade that does NOT flip: it exists to carry
# white text (the one filled button), and a store-supplied PSA_ACCENT can be
# far too light for #fff, so fills are always darkened rather than trusted.
# Hover deepens instead of brightening - brightening drops the label below 4.5.
#
# The mix percentages are CLAMPED per accent, not fixed: a syntax-valid env
# color (kelly green, Pokemon yellow) mixed at a fixed share can still land
# under 4.5:1. Each derived shade starts at the share tuned for the default
# steel blue and walks toward its pole (black on light, white on dark) until
# the WCAG target passes - the pole itself always does, so this cannot fail.
def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))

def _lum(rgb):
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (f(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def _contrast(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)

def _mix(ac, pole, share):
    """color-mix(in srgb, ac share%, pole) - linear sRGB interpolation."""
    t = share / 100
    return tuple(round(a * t + p * (1 - t)) for a, p in zip(ac, pole))

def _over(fg, alpha, bg):
    """An rgba(fg, alpha) layer composited over an opaque bg."""
    return tuple(round(f * alpha + b * (1 - alpha)) for f, b in zip(fg, bg))

def _share(ac, pole, against, target, start):
    """Largest accent share (<= start, 1% steps) whose mix with pole clears
    the contrast target against `against`."""
    for s in range(start, -1, -1):
        if _contrast(_mix(ac, pole, s), against) >= target:
            return s
    return 0

_BLACK, _WHITE = (0, 0, 0), (255, 255, 255)
_AC_RGB = _rgb(ACCENT)
# Card era (2026-08-08): content sits on raised cards over a grouped ground, so
# every clamp runs against the HARDER ground for that ink - light text grounds
# are the grey page (darker than the white card), dark text grounds are the
# card surface (lighter than the near-black page).
_BG_DARK = _rgb("#101113")                     # dark page ground
_CARD_DARK = _rgb("#1c1d20")                   # dark card surface
_BG_LIGHT = _rgb("#f2f2f7")                    # light page ground (cards are white)
_S3_LIGHT = _rgb("#f2f2f4")                    # --surface3 light (hover pill ground)
_S3_DARK = _over(_WHITE, 0.08, _CARD_DARK)     # --surface3 dark, composited on the card
_TRACK_LIGHT = _rgb("#ececef")                 # stage-bar track grounds
_TRACK_DARK = _over(_WHITE, 0.14, _CARD_DARK)
_FILL = _share(_AC_RGB, _BLACK, _WHITE, 4.5, 86)
_AC_MIX_FILL = {"--ac-fill": f"{_FILL}%,black",
                "--ac-fill-hot": f"{max(_FILL - 8, 0)}%,black"}
# --bar: the stage bar's fill vs its track (1.4.11 non-text, 3:1) - raw --ac
# fails it in dark even for the default accent. --ring: focus indicators, and
# it is clamped against --inp, NOT the sheet: inputs take the ring at
# outline-offset:0, so it rides the quiet input fill rather than the ground
# behind it. --inp and --surface3 are the same value in both palettes, and it
# is the harder ground in each (lighter in light, lighter in dark), so
# clamping there is correct everywhere the ring is actually painted.
_AC_MIX_L = {"--ac-hot": f"{_share(_AC_RGB, _BLACK, _S3_LIGHT, 4.5, 82)}%,black",
             "--ac-pale": f"{_share(_AC_RGB, _BLACK, _BG_LIGHT, 4.5, 92)}%,black",
             "--bar": f"{_share(_AC_RGB, _BLACK, _TRACK_LIGHT, 3.0, 100)}%,black",
             "--ring": f"{_share(_AC_RGB, _BLACK, _S3_LIGHT, 3.0, 100)}%,black",
             **_AC_MIX_FILL}
_AC_MIX_D = {"--ac-hot": f"{_share(_AC_RGB, _WHITE, _S3_DARK, 4.5, 82)}%,white",
             "--ac-pale": f"{_share(_AC_RGB, _WHITE, _CARD_DARK, 4.5, 45)}%,white",
             "--bar": f"{_share(_AC_RGB, _WHITE, _TRACK_DARK, 3.0, 100)}%,white",
             "--ring": f"{_share(_AC_RGB, _WHITE, _S3_DARK, 3.0, 100)}%,white",
             **_AC_MIX_FILL}
# Neutral system, card era (owner call 2026-08-08, App Store grammar): a quiet
# grouped ground carries raised cards - light is Apple's grouped grey #f2f2f7
# under white cards, dark is near-black #101113 under #1c1d20 cards. Never
# blue-gray, never pure black.
_DARK = {"bg": "#101113", "surface": "#1c1d20",
 "surface3": "rgba(255,255,255,.08)", "inp": "rgba(255,255,255,.08)",
 "ph": "rgba(255,255,255,.06)", "hovrow": "rgba(255,255,255,.07)",
 # search-preview tag chip: dark grounds swallow a low-alpha accent wash, so the
 # same chip needs a heavier mix here than in light to read at all.
 "tagmix": "18%",
 # AMBIENT GROUND (see body::before): two soft radials pooled at the top edge,
 # behind the sticky glass toolbar, so the lens has something to refract. Dark
 # needs more alpha (11/8 vs 6/4) because #17181a eats it - but the ellipses are
 # SHORTER and stop sooner (55%/52%) so the tint stays a halo at the top and the
 # field below stays neutral graphite. Never blue-gray the whole sheet.
 "amb": ("radial-gradient(110% 54% at 84% -20%,color-mix(in srgb,var(--ac2) 11%,transparent),"
         "transparent 55%),"
         "radial-gradient(88% 46% at -14% -6%,color-mix(in srgb,var(--ac) 8%,transparent),"
         "transparent 52%)"),
 "txt": "#f2f2f4", "m1": "#98989f", "tert": "#8a8a92",
 "hair": "rgba(255,255,255,.12)", "hairh": "rgba(255,255,255,.3)",
 "hair2": "rgba(255,255,255,.08)", "track": "rgba(255,255,255,.14)",
 "chipfill": "#ffffff", "chippad": "5px 7px",
 "logofx": "brightness(0) invert(1)",
 # Liquid Glass chrome: translucent ground, one soft cast shadow, and a LENS -
 # --rim is the specular catch along the top edge, --rimb the falloff along the
 # bottom. Both are felt, not seen: the pair is what separates a lens from a
 # frosted card. Dark needs a heavier --rimb because the ground is already dark,
 # so a light-alpha edge would vanish.
 "glass": "rgba(30,31,35,.62)", "glasssolid": "#212226", "rim": "rgba(255,255,255,.16)",
 "rimb": "rgba(0,0,0,.35)",
 "segtrack": "rgba(255,255,255,.05)", "segon": "rgba(255,255,255,.1)",
 "shc": "rgba(0,0,0,.34)", "shc2": "rgba(0,0,0,.5)", "shc3": "rgba(0,0,0,.28)",
 "sh2": "rgba(255,255,255,.11)", "scrim": "rgba(0,0,0,.4)",
 "err": "#ff8a7a", "holdtx": "#ff8a7a", "grade": "#ff7a6e", "fhov": "#ffffff",
 "ok": "#43c383"}
_LIGHT = {"bg": "#f2f2f7", "surface": "#ffffff",
 # ph is white, not the old #f2f2f4: placeholder tiles now sit on the grey
 # ground (detail-page grids), where a grey ph would vanish into it
 "surface3": "#f2f2f4", "inp": "#f2f2f4", "ph": "#ffffff",
 "hovrow": "rgba(0,0,0,.05)", "tagmix": "12%",
 "amb": ("radial-gradient(120% 62% at 84% -22%,color-mix(in srgb,var(--ac2) 6%,transparent),"
         "transparent 60%),"
         "radial-gradient(96% 52% at -14% -6%,color-mix(in srgb,var(--ac) 4%,transparent),"
         "transparent 56%)"),
 "txt": "#1d1d1f", "m1": "#6e6e73", "tert": "#86868b",
 "hair": "rgba(0,0,0,.1)", "hairh": "rgba(0,0,0,.28)",
 "hair2": "rgba(0,0,0,.07)", "track": "#ececef",
 "chipfill": "transparent", "chippad": "0", "logofx": "none",
 "glass": "rgba(255,255,255,.72)", "glasssolid": "#ffffff", "rim": "rgba(255,255,255,.85)",
 "rimb": "rgba(15,20,30,.06)",
 "segtrack": "rgba(0,0,0,.045)", "segon": "#ffffff",
 "shc": "rgba(20,25,35,.1)", "shc2": "rgba(20,25,35,.18)", "shc3": "rgba(20,25,35,.08)",
 "sh2": "#e8e8ec", "scrim": "rgba(0,0,0,.4)",
 "err": "#b03a2e", "holdtx": "#b03a2e", "grade": "#b12b2b", "fhov": "#1d1d1f",
 "ok": "#2f9e68"}
# The accent ramp is clamped above; the NEUTRAL ramp is hand-picked, and the
# build's one shipped contrast failure lived exactly there. This doesn't
# auto-adjust (the values are static and tuned) - it warns at boot so the next
# hand-picked gray can't ship under target unnoticed.
def _check_neutrals():
    for pal, name in ((_LIGHT, "light"), (_DARK, "dark")):
        # harder ground per theme: light ink also sits on the grey page ground
        # (darker than the white card); dark ink's harder ground is the card
        # surface (lighter than the near-black page)
        bg = _rgb(pal["bg"] if name == "light" else pal["surface"])
        for tok, target in (("txt", 4.5), ("m1", 4.5), ("err", 4.5),
                            ("holdtx", 4.5), ("grade", 4.5),
                            ("tert", 3.0), ("ok", 3.0)):  # tert/ok are non-text
            v = pal[tok]
            if not v.startswith("#"):
                continue
            c = _contrast(_rgb(v), bg)
            if c < target:
                print(f"WARNING: --{tok} {v} on {name} bg is {c:.2f}:1 "
                      f"(target {target}:1)", flush=True)

_check_neutrals()

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
# prefers-contrast: hairlines and secondary text step up hard. Emitted in the
# same three-block shape as the palettes so the bare :root case (default theme,
# no data-theme attribute) resolves to the store's default palette.
# --hair2 rides along: it draws every content card's edge in the card era, so
# high-contrast users get real borders, not shadow-only separation
_HC_L = ("--hair:rgba(0,0,0,.32);--hairh:rgba(0,0,0,.5);--hair2:rgba(0,0,0,.28);"
         "--m1:#4a4a4f;--tert:#5c5c61")
_HC_D = ("--hair:rgba(255,255,255,.36);--hairh:rgba(255,255,255,.55);--hair2:rgba(255,255,255,.32);"
         "--m1:#c0c0c8;--tert:#b0b0b8")
THEME_VARS += ("@media(prefers-contrast:more){"
               f":root{{{_HC_L if THEME == 'light' else _HC_D}}}"
               f':root[data-theme="dark"]{{{_HC_D}}}'
               f':root[data-theme="light"]{{{_HC_L}}}}}')
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

STAGES = ["Arrived", "Order Prep", "Research & ID", "Grading", "Assembly", "QA Check", "Completing", "Shipped"]

def stage_index(status):
    """Position in STAGES, or None for a step PSA reports that this map does not
    know. None means "draw no stage": naming one would be a guess."""
    try:
        return STAGES.index(status)
    except ValueError:
        return None

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
    """'2026-09-25' -> 'Sep 25' for compact display. A date in another year
    carries it ('Jan 05, 2027'): PSA windows cross New Year and a bare 'Jan 05'
    reads as ten months ago."""
    try:
        d = datetime.fromisoformat(iso[:10])
    except (ValueError, TypeError):
        return iso
    year = f", {d.year}" if d.year != datetime.now(DISPLAY_TZ).year else ""
    return d.strftime("%b %d") + year

def fmt_mdy(mdy):
    """PSA's '07/21/26' -> 'Jul 21' (their arrived/shipped date format)."""
    try:
        return datetime.strptime(mdy, "%m/%d/%y").strftime("%b %d")
    except (ValueError, TypeError):
        return mdy

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

DEFAULT_PRICES = [("regular", 109.0), ("value max", 89.99), ("bulk", 34.99), ("value", 45.99), ("express", 279.0)]

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
    """'regular:109,value max:89.99' -> [('regular',109.0),...]; order is free."""
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

_ACCTS_LOCK = threading.Lock()
_ACCTS_SIG = None
_ACCTS_VAL = {}

def _accounts_sig():
    """Cheap change detector for the accounts cache: ids + account.env mtimes.
    env_set/write_account_env/unlink all bump these, so edits still hot-load."""
    try:
        names = sorted(os.listdir(ACCOUNTS_DIR))
    except OSError:
        return ()
    sig = []
    for d in names:
        if not re.fullmatch(r"[a-z0-9-]+", d):
            continue
        try:
            sig.append((d, os.stat(os.path.join(ACCOUNTS_DIR, d, "account.env")).st_mtime_ns))
        except OSError:
            continue
    return tuple(sig)

def load_accounts():
    """Scan ACCOUNTS_DIR -> {id: account dict}. Cached on account.env mtimes:
    called several times per request (auth, setup, renderers), so don't re-parse
    env files unless something on disk actually changed."""
    global _ACCTS_SIG, _ACCTS_VAL
    sig = _accounts_sig()
    with _ACCTS_LOCK:
        if sig == _ACCTS_SIG:
            return _ACCTS_VAL
    accts = {}
    if not os.path.isdir(ACCOUNTS_DIR):
        with _ACCTS_LOCK:
            _ACCTS_SIG, _ACCTS_VAL = sig, accts
        return accts
    for d in sorted(os.listdir(ACCOUNTS_DIR)):
        if not re.fullmatch(r"[a-z0-9-]+", d):  # ids must be token-safe (no dots)
            continue
        base = os.path.join(ACCOUNTS_DIR, d)
        env = read_env_file(os.path.join(base, "account.env"))
        pw = env.get("SITE_PASSWORD", "")
        # PSA_MERGE_INTO (global or per account) names the account whose psa.db
        # and owners.db are the site's universal database; every other PSA
        # account feeds it. A feeder has PSA credentials and a Settings chip,
        # and the one site password covers it at the gate
        into = env.get("PSA_MERGE_INTO", os.environ.get("PSA_MERGE_INTO", "")).strip()
        feeder = bool(into) and into != d and os.path.isdir(os.path.join(ACCOUNTS_DIR, into))
        if not pw and not feeder:
            continue
        dbdir = os.path.join(ACCOUNTS_DIR, into) if feeder else base
        accts[d] = {
            "feeder": feeder,
            "id": d,
            # the id, not id.upper(): an ALL-CAPS store name in the masthead
            # subtitle would be the one tracked-caps string in the product
            "label": env.get("LABEL", d),
            "password": "" if feeder else pw,
            "db": os.path.join(dbdir, "psa.db"),
            "own_db": os.path.join(dbdir, "owners.db"),
            "prices": parse_prices(env.get("PSA_PRICES", "")),
            # unlinked = disconnected from PSA but still served: the site keeps
            # showing the last known data with a banner; run_scan skips it
            "unlinked": env.get("UNLINKED", "") == "1",
        }
    with _ACCTS_LOCK:
        _ACCTS_SIG, _ACCTS_VAL = sig, accts
    return accts

def service_price(a, service):
    """The LONGEST key inside the service name wins, so PSA's compound tiers
    ("Value Bulk", "Value Max") take their own fee and not plain "Value"
    whichever order the table happens to list."""
    s = (service or "").lower()
    hit = max((kp for kp in a["prices"] if kp[0] in s),
              key=lambda kp: len(kp[0]), default=None)
    return hit[1] if hit else None

# ---------- auth ----------

def _b64e(s):
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")

def _b64d(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode()

def pw_slug(acct_id):
    """Fingerprint of the account's current site password, mixed into admin
    session signatures: rotate the password and every old cookie stops
    verifying, which is the only way to revoke a session here."""
    a = load_accounts().get(acct_id)
    return hashlib.sha256((a["password"] if a else "").encode()).hexdigest()[:8]

def make_token(acct_id, exp, email=""):
    """Admin (site-password) token: acct.exp.sig
    Customer token carries the email: acct.exp.email_b64.sig"""
    if email:
        msg = f"{acct_id}.{exp}.customer.{email}".encode()
        sig = hmac.new(SECRET, msg, hashlib.sha256).hexdigest()
        return f"{acct_id}.{exp}.{_b64e(email)}.{sig}"
    msg = f"{acct_id}.{exp}.{pw_slug(acct_id)}".encode()
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
        return (acct_id, email) if hmac.compare_digest(good.encode(), sig.encode()) else None
    good = hmac.new(SECRET, f"{acct_id}.{exp_s}.{pw_slug(acct_id)}".encode(),
                    hashlib.sha256).hexdigest()
    return (acct_id, "") if hmac.compare_digest(good.encode(), sig.encode()) else None

# Per-IP login throttle (in-memory; resets on restart). The 0.4s sleep blunts
# casual brute force; this stops a determined loop.
_FAILS = {}  # ip -> [count, window_start]
_FAILS_LOCK = threading.Lock()
MAX_FAILS = 8
FAIL_WINDOW = 900  # 15 min
# Backstop: a guess spread over many IPs never trips the per-IP counter, so the
# same budget also applies site-wide. Any successful login clears it, so real
# people fumbling the password never lock the site.
_ALL_FAILS = [0, 0.0]  # count, window_start

def _evict(d, window):
    """Drop stale entries once a dict of ip -> [count, start] grows large."""
    if len(d) > 4000:
        cut = time.time() - window
        for k in [k for k, v in d.items() if v[1] < cut]:
            del d[k]

def login_locked(ip):
    with _FAILS_LOCK:
        now = time.time()
        if _ALL_FAILS[0] >= MAX_FAILS and now - _ALL_FAILS[1] <= FAIL_WINDOW:
            return True
        rec = _FAILS.get(ip)
        if not rec:
            return False
        if now - rec[1] > FAIL_WINDOW:
            del _FAILS[ip]
            return False
        return rec[0] >= MAX_FAILS

def login_fail(ip):
    with _FAILS_LOCK:
        now = time.time()
        if now - _ALL_FAILS[1] > FAIL_WINDOW:
            _ALL_FAILS[:] = [1, now]
        else:
            _ALL_FAILS[0] += 1
        rec = _FAILS.get(ip)
        if rec and now - rec[1] <= FAIL_WINDOW:
            rec[0] += 1
        else:
            _FAILS[ip] = [1, now]
        _evict(_FAILS, FAIL_WINDOW)

def login_ok(ip):
    with _FAILS_LOCK:
        _FAILS.pop(ip, None)
        _ALL_FAILS[0] = 0

# Light per-IP cap on /suggest so a valid session can't hammer full-table scans.
_SUG = {}  # ip -> [count, window_start]
_SUG_LOCK = threading.Lock()
SUGGEST_MAX = 40  # per 10s (client debounces to ~9/s; this only stops abuse)

def suggest_allowed(ip):
    with _SUG_LOCK:
        rec = _SUG.get(ip)
        now = time.time()
        if not rec or now - rec[1] > 10:
            _evict(_SUG, 10)
            _SUG[ip] = [1, now]
            return True
        rec[0] += 1
        return rec[0] <= SUGGEST_MAX

# ---------- data (all account-scoped) ----------

_OWN_READY = set()
_OWN_LOCK = threading.Lock()

def own_conn(a):
    c = sqlite3.connect(a["own_db"])
    c.execute("PRAGMA busy_timeout=5000")  # wait out a concurrent writer, don't error at once
    # schema is created once per db per process, not on every open - own_conn
    # runs several times per page render
    with _OWN_LOCK:
        if a["own_db"] not in _OWN_READY:
            c.execute("CREATE TABLE IF NOT EXISTS owners (cert_id TEXT PRIMARY KEY, owner TEXT, updated_at TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS archived (sub_number TEXT PRIMARY KEY, archived_at TEXT)")
            # discord_links: owner tag -> Discord user ID for @-mention pings (psa_watch
            # reads it in notify()). IDs are WRITE-ONLY through the site - no endpoint
            # ever returns one; the UI only reflects linked yes/no.
            c.execute("CREATE TABLE IF NOT EXISTS discord_links (owner TEXT COLLATE NOCASE PRIMARY KEY, "
                      "discord_id TEXT, updated_at TEXT)")
            c.commit()
            _OWN_READY.add(a["own_db"])
    return c

DISCORD_ID_RE = re.compile(r"^\d{17,20}$")

def discord_linked(a, owner):
    c = own_conn(a)
    r = c.execute("SELECT 1 FROM discord_links WHERE owner=? AND discord_id != ''",
                  (owner,)).fetchone()
    c.close()
    return bool(r)

def set_discord(a, owner, discord_id):
    """Set (or clear, with '') the Discord ID for an owner tag."""
    c = own_conn(a)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if discord_id:
        c.execute("""INSERT INTO discord_links (owner, discord_id, updated_at) VALUES (?,?,?)
                     ON CONFLICT(owner) DO UPDATE SET discord_id=excluded.discord_id,
                     updated_at=excluded.updated_at""", (owner, discord_id, now))
    else:
        c.execute("DELETE FROM discord_links WHERE owner=?", (owner,))
    c.commit()
    c.close()

def discord_widget(a, owner):
    """Small button under the person's name; opens a popout with the Discord
    linking UI. The saved ID is never rendered - only the on/off state."""
    linked = discord_linked(a, owner)
    btn = ('<button type="button" class="f dbtn" id="dopen">'
           + ("Discord pings: on" if linked else "Link Discord") + "</button>")
    if linked:
        inner = (f'<div class="srow" style="margin-top:16px"><span class="dstate">Discord pings on</span>'
                 f'<button type="button" class="sbtn sdel f" id="dunlink" data-owner="{html.escape(owner)}">Turn off</button></div>'
                 f'<div class="dhint">You’ll be @-mentioned in the site’s Discord channel '
                 f'when a submission with your cards updates.</div>')
    else:
        inner = (f'<div class="srow" style="margin-top:16px">'
                 f'<input type="password" id="did" placeholder="Discord user ID" '
                 f'aria-label="Discord user ID" '
                 f'autocomplete="off" inputmode="numeric" maxlength="20">'
                 f'<button type="button" class="sbtn f" id="dlink" data-owner="{html.escape(owner)}">Enable</button></div>'
                 f'<div class="dhint">Paste your Discord user ID to get @-mentioned when a submission with '
                 f'your cards updates. Discord: Settings &rarr; Advanced &rarr; Developer Mode, then '
                 f'right-click your name &rarr; Copy User ID. Your ID is stored server-side and never shown again.</div>')
    return (btn + f'<div class="smodal" id="dmodal" role="dialog" aria-modal="true" '
                  f'aria-labelledby="dmtitle"><div class="card sblock">'
                  f'<button type="button" class="sclose" id="dclose" aria-label="Close">{ICON_X}</button>'
                  f'<h2 class="stitle" id="dmtitle">Discord pings</h2>{inner}</div></div>')

DISCORD_JS = """<script>
(function(){
  var dm=document.getElementById('dmodal'),db=document.getElementById('dopen');
  if(db&&dm){
    db.addEventListener('click',function(){dm.classList.add('on');
      // focus after the sheet is visible - a hidden field can't take focus
      var f=document.getElementById('did');
      if(f)requestAnimationFrame(function(){f.focus();});});
    document.getElementById('dclose').addEventListener('click',function(){dm.classList.remove('on');});
    dm.addEventListener('click',function(e){if(e.target===dm)dm.classList.remove('on');});
    document.addEventListener('keydown',function(e){if(e.key==='Escape')dm.classList.remove('on');});
  }
  function post(owner,id,done){
    fetch('/discord',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body:'owner='+encodeURIComponent(owner)+'&id='+encodeURIComponent(id)})
      .then(function(r){done(r.ok);});
  }
  function derr(msg){
    var f=document.getElementById('did'),h=document.querySelector('#dmodal .dhint');
    f.classList.add('errsave');
    if(h)h.textContent=msg;  // words, not just a red underline
  }
  var link=document.getElementById('dlink');
  if(link)link.addEventListener('click',function(){
    var v=(document.getElementById('did').value||'').trim();
    if(!/^\\d{17,20}$/.test(v)){derr('That doesn’t look like a Discord user ID. It’s a 17\\u201320 digit number.');return;}
    post(link.dataset.owner,v,function(ok){if(ok)location.reload();
      else derr('Couldn’t save the ID, try again.');});
  });
  var un=document.getElementById('dunlink');
  if(un)un.addEventListener('click',function(){
    post(un.dataset.owner,'',function(ok){if(ok)location.reload();});
  });
})();
</script>"""

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
    conn.execute("PRAGMA busy_timeout=5000")  # wait out a scanner write, don't error at once
    conn.row_factory = sqlite3.Row
    return conn

def _first_run(a, e):
    """True only for the fresh-account case: no psa.db yet, or no tables in it.
    A locked, unreadable or corrupt db is a failure and must reach the 500
    handler, not render as an empty account."""
    m = str(e)
    return "no such table" in m or ("unable to open database file" in m
                                    and not os.path.exists(a["db"]))

def load_subs(a):
    try:
        conn = _ro_conn(a)
        rows = conn.execute("""SELECT * FROM subs
            ORDER BY CAST(sub_number AS INTEGER) DESC""").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError as e:  # fresh account: no psa.db until first scan
        if not _first_run(a, e):
            raise
        return []

def load_sub(a, sub_number):
    try:
        conn = _ro_conn(a)
        row = conn.execute("SELECT * FROM subs WHERE sub_number=?", (sub_number,)).fetchone()
        conn.close()
        return dict(row) if row else None
    except sqlite3.OperationalError as e:
        if not _first_run(a, e):
            raise
        return None

def load_cards(a, sub_number):
    try:
        conn = _ro_conn(a)
        rows = conn.execute("SELECT * FROM cards WHERE sub_number=? ORDER BY line_number, cert_id",
                            (sub_number,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError as e:
        if not _first_run(a, e):
            raise
        return []

def load_all_cards(a):
    try:
        conn = _ro_conn(a)
        rows = conn.execute("SELECT * FROM cards ORDER BY CAST(sub_number AS INTEGER) DESC, line_number").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError as e:
        if not _first_run(a, e):
            raise
        return []

def card_owner_keys(a):
    """(sub_number, cert_id) for every card. The dashboard's untagged count is
    the only thing that needs a row per card, and it needs these two columns
    alone - load_all_cards stays for the pages that render whole cards."""
    try:
        conn = _ro_conn(a)
        rows = conn.execute("SELECT sub_number, cert_id FROM cards").fetchall()
        conn.close()
        return [(r["sub_number"], r["cert_id"]) for r in rows]
    except sqlite3.OperationalError as e:
        if not _first_run(a, e):
            raise
        return []

def sub_fronts(a):
    """sub_number -> [(front_thumb, name), ...] in line_number order, imaged
    cards only. ONE query for the whole dashboard (the filmstrips), grouped
    here in Python - a per-row query would be one open/close per submission.
    The name rides along so every strip tile gets a real alt text."""
    try:
        conn = _ro_conn(a)
        rows = conn.execute("SELECT sub_number, front_thumb, name FROM cards "
                            "WHERE front_thumb IS NOT NULL AND front_thumb != '' "
                            "ORDER BY line_number").fetchall()
        conn.close()
    except sqlite3.OperationalError as e:
        if not _first_run(a, e):
            raise
        return {}
    out = {}
    for r in rows:
        out.setdefault(r["sub_number"], []).append((r["front_thumb"], r["name"] or ""))
    return out

# Card market values (psa_values.py fills card_values from PSA cert pages).
# Feature-flagged: with PSA_VALUES unset - or the table absent - every page
# renders exactly as it did before the feature existed.
VALUES_ON = os.environ.get("PSA_VALUES", "0") == "1"

def load_values(a):
    """cert_no -> display value (PSA's estimate, else latest comp sale) converted
    to CAD via the stored USDCAD rate (psa_values.py keeps it fresh; raw USD only
    if no rate was ever fetched), plus freshest fetch date and currency label."""
    if not VALUES_ON:
        return {}, "", "CAD"
    try:
        conn = _ro_conn(a)
        try:
            rows = conn.execute(
                "SELECT cert_no, estimate, last_sale, fetched_at FROM card_values").fetchall()
            try:
                fx = conn.execute("SELECT rate FROM fx_rates WHERE pair='USDCAD'").fetchone()
            except sqlite3.Error:
                fx = None
        finally:
            conn.close()
    except sqlite3.Error:
        return {}, "", "CAD"
    rate, cur = (fx["rate"], "CAD") if fx and fx["rate"] else (1.0, "USD")
    vals, latest = {}, ""
    for r in rows:
        v = r["estimate"] if r["estimate"] is not None else r["last_sale"]
        if v is not None:
            vals[r["cert_no"]] = v * rate
        if r["fetched_at"] and r["fetched_at"] > latest:
            latest = r["fetched_at"]
    return vals, (short_date(latest) if latest else ""), cur

def sub_value_totals(a):
    """(sub_number -> total display value, currency label). The dashboard shows
    one total per submission and no per card value, so the totals come off ONE
    grouped join instead of loading every card and every value row."""
    if not VALUES_ON:
        return {}, "CAD"
    try:
        conn = _ro_conn(a)
        try:
            rows = conn.execute(
                "SELECT c.sub_number AS sub_number, "
                "SUM(COALESCE(v.estimate, v.last_sale)) AS total "
                "FROM cards c JOIN card_values v ON v.cert_no = c.cert_no "
                "GROUP BY c.sub_number").fetchall()
            try:
                fx = conn.execute("SELECT rate FROM fx_rates WHERE pair='USDCAD'").fetchone()
            except sqlite3.Error:
                fx = None
        finally:
            conn.close()
    except sqlite3.Error:
        return {}, "CAD"
    rate, cur = (fx["rate"], "CAD") if fx and fx["rate"] else (1.0, "USD")
    return {r["sub_number"]: r["total"] * rate for r in rows if r["total"]}, cur

def owners_map(a):
    c = own_conn(a)
    m = {cid: ow for cid, ow in c.execute("SELECT cert_id, owner FROM owners WHERE owner!=''")}
    c.close()
    return m

def card_exists(a, cert_id):
    """True if this account has a card with that cert. Owner tags are keyed by
    cert_id in a separate db, so nothing else stops a tag for a cert that was
    never scanned (the tag JS once posted the literal 'undefined')."""
    try:
        conn = _ro_conn(a)
        row = conn.execute("SELECT 1 FROM cards WHERE cert_id=? LIMIT 1",
                           (cert_id,)).fetchone()
        conn.close()
        return row is not None
    except sqlite3.OperationalError as e:
        if not _first_run(a, e):
            raise
        return False

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

_EMAIL_ON = [None, 0.0]  # cached value + timestamp

def email_login_on():
    """True if any owner tag looks like an email. Controls the gate placeholder:
    a personal instance with plain-name tags shouldn't advertise an email login
    that can never match. Cached for 60s - this runs on every unauthenticated
    response, and a per-request DB probe for a placeholder string is waste."""
    now = time.time()
    if _EMAIL_ON[0] is not None and now - _EMAIL_ON[1] < 60:
        return _EMAIL_ON[0]
    _EMAIL_ON[0], _EMAIL_ON[1] = _email_login_probe(), now
    return _EMAIL_ON[0]

def _email_login_probe():
    for a in load_accounts().values():
        try:
            c = sqlite3.connect(f"file:{a['own_db']}?mode=ro", uri=True)
            hit = c.execute("SELECT 1 FROM owners WHERE owner LIKE '%@%' LIMIT 1").fetchone()
            c.close()
        except sqlite3.Error:
            continue
        if hit:
            return True
    return False

def cust_statline(s):
    """One-line per-card status for customer tiles (replaces the sub link)."""
    if not s:
        return ""
    if s["status"] == "Shipped":
        return f"Shipped {fmt_mdy(s['shipped'])}" if s["shipped"] else "Shipped"
    if not (s["est_end"] or s["est_start"]):
        return s["status"]
    label, val, muted = eta_words(s)
    return f'{s["status"]} · {val if muted else f"{label} {val}"}'

def load_cards_by_certs(a, cert_ids):
    """The owner-scoped pool for /suggest: only that person's rows, by cert_id,
    instead of a full-table scan per keystroke (customer sessions are ALWAYS
    owner-scoped, so this is the path every customer search hits)."""
    if not cert_ids:
        return []
    out = []
    try:
        conn = _ro_conn(a)
        for i in range(0, len(cert_ids), 500):  # stay under SQLite's param cap
            chunk = cert_ids[i:i + 500]
            marks = ",".join("?" * len(chunk))
            out += [dict(r) for r in conn.execute(
                "SELECT sub_number, line_number, cert_id, cert_no, name, front_thumb "
                f"FROM cards WHERE cert_id IN ({marks})", chunk)]
        conn.close()
    except sqlite3.OperationalError as e:
        if not _first_run(a, e):
            raise
        return []
    # restore load_all_cards' global order: newest sub first, then line order
    out.sort(key=lambda c: (-int(c["sub_number"]) if str(c["sub_number"]).isdigit() else 0,
                            c.get("line_number") or 0))
    return out

def search_cards_sql(a, ql, limit):
    """The unscoped /suggest hot path: push the substring match and the LIMIT
    into SQLite instead of scanning every column of every card per keystroke.
    Matches name, cert_no, and cert_id, like the old Python hay string."""
    pat = "%" + ql.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    try:
        conn = _ro_conn(a)
        rows = conn.execute(
            "SELECT sub_number, cert_id, cert_no, name, front_thumb FROM cards "
            "WHERE lower(name) LIKE ? ESCAPE '\\' "
            "   OR lower(cast(cert_no AS TEXT)) LIKE ? ESCAPE '\\' "
            "   OR lower(cast(cert_id AS TEXT)) LIKE ? ESCAPE '\\' "
            "ORDER BY CAST(sub_number AS INTEGER) DESC, line_number LIMIT ?",
            (pat, pat, pat, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError as e:
        if not _first_run(a, e):
            raise
        return []

def suggest(a, q, owner=None, limit_names=8, limit_cards=40, people=True):
    """Live search backing the unified search box. People (priority) + cards.
    With owner set (person page), card results are ONLY that person's cards, but
    the People section still lists everyone, so a name hops person to person.
    people=False drops that section, which is what a customer session gets."""
    ql = (q or "").strip().lower()
    owners = owners_map(a)
    want = (owner or "").strip().lower()
    if not people:
        name_hits = []
    else:
        names = sorted({v for v in owners.values() if v})
        matches = [n for n in names if ql in n.lower()]
        # empty focus = browse mode: list EVERY person, scrollable directory
        name_hits = matches if not ql else matches[:limit_names]
    card_hits = []
    pool = []
    if ql and not want:
        # SQL does the filtering and the limit; the loop below only formats
        pool = search_cards_sql(a, ql, limit_cards)
    elif want:
        # only this person's rows, fetched by cert_id - never a full scan
        pool = load_cards_by_certs(
            a, [cid for cid, ow in owners.items() if ow.lower() == want])
        if not ql:  # empty focus on a person page: browse their cards A-Z
            pool.sort(key=lambda c: smart_title(c.get("name") or "").lower())
    for c in pool:
        if ql:
            # a no-op re-check for SQL rows (same fields), the real filter for
            # the owner-scoped Python pool
            hay = " ".join((c.get("name") or "", str(c.get("cert_no") or ""),
                            str(c.get("cert_id") or ""))).lower()
            if ql not in hay:
                continue
        card_hits.append({
            # subject first, same as the tiles - the set line is boilerplate
            # and the row already carries a small cert/owner line under it
            "name": split_name(smart_title(c["name"] or ""))[0],
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
/* Canon, played straight: grouped ground, raised cards, glass chrome only. DESIGN.md is
   canonical. */
*{box-sizing:border-box;margin:0;padding:0}
/* --bg on <html> so the canvas (and overscroll bounce) is always the ground colour; body is
   transparent. */
/* touch-action on the root inherits: no 300ms double-tap wait, pan and pinch zoom intact, no
   iOS tap flash. */
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%;background:var(--bg);
 touch-action:manipulation;-webkit-tap-highlight-color:transparent}
@view-transition{navigation:auto}
/* ---- ambient ground ------------------------------------------------------ */
/* ambient accent radials for the glass to refract. Fixed pseudo, not background-attachment
   (mobile Safari repaints that every frame); z-index:-1 sits behind content. */
body::before{content:'';position:fixed;inset:0;z-index:-1;pointer-events:none;
 background:var(--amb)}
body{background:transparent;min-height:100vh;color:var(--txt);
 font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
 -webkit-font-smoothing:antialiased;padding:18px 20px 96px;
 font-size:14px;line-height:1.5;font-variant-numeric:tabular-nums}
:focus-visible{outline:2px solid var(--ring);outline-offset:2px}
.mono{font-family:ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,monospace}
.wrap{max-width:820px;margin:0 auto}
/* screen-reader-only live region (announcements: saves, failures, counts) */
.vh{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;
 clip-path:inset(50%);white-space:nowrap}
/* skip link: first tab stop, visible only on focus - a row's filmstrip is up to 8 links. */
.skip{position:fixed;left:-9999px;top:14px;z-index:100;padding:10px 16px;border-radius:999px;
 background:var(--glasssolid);color:var(--ac-pale);font-size:13px;font-weight:500;
 text-decoration:none;border:1px solid var(--hair);box-shadow:0 10px 26px var(--shc)}
.skip:focus{left:14px}
/* ---- type: system stack, sentence case, tracking scaled to size ----------- */
/* Three rungs: 26/700 title, 17/650 data and section titles, 14/400 body; 13 on control labels
   only. Tracking scales with size (26 = -.021em, 24 = -.020, 22 = -.017, 17 = -.012, 14 and
   below 0) and is never positive. */
h1{font-size:26px;font-weight:700;letter-spacing:-.021em;line-height:1.15}
.sub{font-size:12px;font-weight:400;color:var(--m1);margin-top:2px}
.toolbar .sub{font-size:12.5px}
.logo{display:block;height:30px;width:auto}
.logo.chip{background:var(--chipfill);padding:var(--chippad);border-radius:6px;
 box-sizing:content-box;height:26px}
.logo.sil{filter:var(--logofx,none)}
.brand{display:flex;align-items:center;gap:12px}
.gbox .logo{height:72px;margin:0 auto 18px}
.hrow{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
.synced{text-align:right;flex-shrink:0;font-size:12px;color:var(--m1);line-height:1.5}
.synced b{display:block;font-size:13px;font-weight:600;color:var(--txt)}
/* a header figure is a data value: 17/650, the .num rung. 13 stays where .synced is chrome. */
.hrow>.synced:not(.custrow) b{font-size:17px;font-weight:650;letter-spacing:-.012em;line-height:1.3}
.synced .estnote{display:block;font-size:12px;font-weight:400;color:var(--m1);margin-top:3px;line-height:1.5}
.synced b.holdb{color:var(--holdtx)}
.synced .estnote{max-width:34ch;margin-left:auto}
.synced .lbl2{display:block;margin-top:8px}
/* the customer's sign-out is the icon in the freshness block, not the top-left "back" slot. */
.synced.custrow{display:flex;align-items:flex-start;gap:12px;justify-content:flex-end}
.synced.custrow .custout{text-align:right}
/* sync state: one dot and one word, never a stamp. The dot is 6px of non-text, so
   --ok's 3:1 check covers it; the full phrase rides in the .vh span. */
.sync{display:inline-flex;align-items:center;gap:6px;flex-shrink:0;font-size:12.5px;
 font-weight:500;color:var(--m1);line-height:1.5;white-space:nowrap}
.sync i{width:6px;height:6px;border-radius:50%;background:var(--m1);flex-shrink:0}
.sync.live i{background:var(--ok)}
.sync.stale i{background:var(--holdtx)}
.lgout{color:var(--m1);display:inline-flex;padding:15px;margin:-11px;border-radius:999px;
 transition:color .15s,background-color .15s}
/* ---- Liquid Glass: chrome only, never content ----------------------------- */
/* the dual rim reads as a lens: light on the top edge (--rim), falling off at the bottom
   (--rimb). Both sub-threshold; the drop shadow carries elevation. */
/* two classes on purpose: .f below zeroes background and border, and 0,2,0 lets the solo pill
   keep its glass. */
.toolbar,.filters,.sbar,#gearbtn,#themeflip,.f.fsolo{
 background:var(--glass);
 -webkit-backdrop-filter:blur(16px) saturate(170%);backdrop-filter:blur(16px) saturate(170%);
 border:1px solid var(--hair);
 box-shadow:inset 0 1px 1px var(--rim),inset 0 -1px 1px var(--rimb),0 10px 26px var(--shc)}
.toolbar{position:sticky;top:10px;z-index:20;display:flex;flex-direction:column;gap:10px;
 margin:16px 0 4px;padding:12px 14px;border-radius:16px}
/* NO view-transition-name on glass: a named backdrop-filter panel floats through the
   navigation as a blurred rectangle when the far page lacks its twin. */
/* elevation is earned: FX_JS flips .raised off a 1px sentinel. Named apart from the masthead
   bar so a compact bar never morphs into a tall one. */
.toolbar{box-shadow:inset 0 1px 1px var(--rim),inset 0 -1px 1px var(--rimb),0 1px 2px var(--shc3);
 transition:box-shadow .25s ease-out}
.toolbar.raised{box-shadow:inset 0 1px 1px var(--rim),inset 0 -1px 1px var(--rimb),
 0 10px 26px var(--shc)}
.toolbar.tbq{padding:7px 8px;border-radius:14px}
.tbsentinel{height:1px;pointer-events:none}
.tbtop{display:flex;justify-content:space-between;align-items:center;gap:16px}
.tbend{display:flex;gap:12px;align-items:center}
.searchwrap{position:relative;flex:1;min-width:200px}
.searchwrap .sicon{position:absolute;left:14px;top:50%;transform:translateY(-50%);
 color:var(--tert);pointer-events:none}
/* capsule: chrome and controls are pills here. The icon moves out with the left inset to clear
   the curve. */
.searchbar{width:100%;margin:0;padding:10px 16px 10px 36px;font-size:15px;font-weight:400;
 border-radius:999px}
.preview{position:absolute;z-index:30;top:calc(100% + 8px);left:0;right:0;background:var(--surface);
 border:1px solid var(--hair);border-radius:14px;padding:6px;max-height:64vh;overflow:auto;
 overscroll-behavior:contain;box-shadow:0 14px 40px var(--shc2);
 opacity:0;visibility:hidden;transform:scale(.985) translateY(-4px);transform-origin:top center;
 transition:opacity .18s ease-out,transform .18s cubic-bezier(.23,1,.32,1),visibility 0s .18s}
.preview.on{opacity:1;visibility:visible;transform:none;transition-delay:0s}
.pvsec{font-size:12px;font-weight:400;color:var(--m1);padding:9px 10px 5px}
.pvrow{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;
 text-decoration:none;color:var(--txt);font-size:14px;font-weight:500}
.pvrow small{display:block;color:var(--m1);font-size:12px;font-weight:400;margin-top:1px}
/* keyboard travel through the preview reads exactly like the pointer does */
.pvrow.act{background:var(--hovrow)}
/* the tag is a category, not a sentence, so a quiet capsule demotes it. Fill mixes from
   --ac-pale so white-label swaps re-tint it; line-height:1 keeps the row height. */
.pvtag{font-size:11px;font-weight:500;line-height:1;color:var(--ac-pale);flex-shrink:0;
 padding:3px 9px;border-radius:999px;
 background:color-mix(in srgb,var(--ac-pale) var(--tagmix),transparent)}
.pvimg{width:26px;height:36px;object-fit:cover;border-radius:4px;border:1px solid var(--hair);
 flex-shrink:0;background:var(--surface3)}
.pvempty{padding:14px 10px;color:var(--m1);font-size:14px}
/* ---- filter capsule: floating segmented glass; active = solid pill --------- */
.filters,.sbar{display:inline-flex;gap:2px;flex-wrap:wrap;padding:3px;border-radius:999px;
 background-image:linear-gradient(var(--segtrack),var(--segtrack))}
.filters{margin:20px 0 12px}
/* Archived is a mode switch, not a sort: outside the segment so a scrolling capsule can never
   park it off-screen, carrying its own glass (.f.fsolo). "N need owners" is a second solo
   pill; .rowend wraps the pair as one flex item. */
.filterrow{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;margin:20px 0 12px}
.rowend{display:flex;align-items:center;gap:10px}
.filterrow .filters{margin:0}
.sbar{margin-top:12px}
/* user-select:none on controls only - names, lot numbers, tags, values and inputs stay
   selectable. */
/* line-height stated, not inherited: the UA sheet pins normal on <button>, so pills and the
   one <a class="f"> measured differently. 16px makes every pill the same box, so .fsolo
   matches. */
/* 6/8, not 7/7: no descenders in these labels, so -1/+1 rides the x-height to optical centre
   at the same height. */
.f{font-size:13px;font-weight:500;color:var(--m1);background:transparent;border:0;line-height:16px;
 padding:6px 14px 8px;border-radius:999px;cursor:pointer;text-decoration:none;display:inline-block;
 width:auto;margin:0;font-family:inherit;letter-spacing:0;position:relative;
 -webkit-user-select:none;user-select:none;
 transition:background .18s,color .18s,transform .14s ease-out}
/* the pill looks 30px tall; the hit area grows invisibly past the capsule (30 + 14 = 44, the
   HIG floor). Vertical only; z-index:-1 keeps it behind every real box. Below 360px the
   capsule clips it. */
.f::before{content:'';position:absolute;inset:-7px 0;z-index:-1}
.f.on{background:var(--segon);color:var(--ac-pale);font-weight:600;box-shadow:0 1px 2px var(--shc3)}
/* Archived pressed borrows .fillbtn's grammar (--ac-fill + #fff), not the segment's --segon
   wash: it is a view switch, not a fourth sort. */
.f.farch.on{background:var(--ac-fill);color:#fff}
/* the solo Archived pill is its own capsule, one rung quieter (12/500). The 20px vertical pad
   is arithmetic: 16 + (9+11) + 1*2 = 38px, the sort capsule's height at both breakpoints.
   inline-block, NOT inline-flex, or the count prints "Archived· 18". */
.fsolo{font-size:12px;padding:9px 14px 11px;border-radius:999px;flex-shrink:0;white-space:nowrap}
/* pressed it must read as one solid lozenge: the hairline goes transparent, not to 0, so the
   height match is untouched. Rims go, shadow stays. */
.f.farch.fsolo.on{border-color:transparent;box-shadow:0 10px 26px var(--shc)}
.f:active{transform:scale(.97)}
/* ---- content cards: App Store grammar (owner call 2026-08-08) -------------- */
/* each submission is a raised card on the grouped ground: 16px radius, hair2 edge, quiet
   shadow. Depth is glass chrome and card lift only; inside a card everything is flat. */
.card{background:var(--surface);border:1px solid var(--hair2);border-radius:16px;
 padding:18px 16px;margin:0 0 14px;box-shadow:0 2px 10px var(--shc3);
 transition:background .18s,opacity .18s,filter .18s}
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:14px}
.hd{display:flex;gap:12px;align-items:flex-start;flex:1;min-width:0}
/* the data rung: 17/650. Segoe/Roboto snap 650 to 600 or 700, both fine - it only has to
   out-weigh 14/400. */
.num{font-size:17px;font-weight:650;letter-spacing:-.012em;line-height:1.3}
.meta{font-size:14px;font-weight:400;color:var(--m1);margin-top:3px}
.pills{display:flex;flex-direction:column;gap:4px;align-items:flex-end;text-align:right;flex-shrink:0}
.pill{display:inline-flex;align-items:center;gap:5px;font-size:14px;color:var(--m1);white-space:nowrap}
.pill.hold{color:var(--holdtx)}
/* two gray levels: Shipped = ink, in flight = muted. A third, lighter gray cannot clear 4.5:1
   at 14px, so pending keeps --m1 and its clock icon. No red status pill. */
.pill.shipped{color:var(--txt)}
.pill.shipped svg{color:var(--m1)}
.ledval{font-size:17px;font-weight:650;letter-spacing:-.012em;color:var(--txt);white-space:nowrap}
/* the caption drops to the small rung, so it must drop the value's tracking too - tracking
   inherits, size does not. */
.ledval span{display:block;font-size:12px;font-weight:400;letter-spacing:normal;color:var(--m1)}
/* ---- stage: one text line above a 4px capsule bar ------------------------- */
/* 16/10, not 15/8: the 30px View pill hangs about 6px below the line, so 8px read as
   pill-touching-bar. */
.stage{display:flex;justify-content:space-between;align-items:baseline;gap:14px;
 font-size:14px;color:var(--m1);margin:16px 0 10px}
.stage>span{min-width:0}
/* no bar under an unknown status, so the stage line is last and its margin would double the
   card pad. */
.stage.nobar{margin-bottom:0}
/* 650, matching .num: a stage name is a data value swept as a column, not emphasis. */
.stage b{color:var(--ac-pale);font-weight:650}
.bar{height:4px;border-radius:2px;background:var(--track);overflow:hidden}
/* the one considered moment: FX_JS runs each bar out from 0 on load. --bar, not --ac - the
   fill is clamped server-side to 3:1 on the track. */
.bar i{display:block;height:100%;border-radius:2px;background:var(--bar);
 transition:width .55s cubic-bezier(.23,1,.32,1)}
/* a held sub is not advancing and an archived one is done, so neither earns the accent fill. */
.card.arch .bar i,.card.hold .bar i{background:var(--m1)}
/* the card's one link: a quiet capsule at the stage line's end, label --ac-hot (clamped 4.5:1
   on --surface3), baseline-aligned to the line. */
.stage .view{flex-shrink:0;margin:0;padding:7px 14px;border-radius:999px;line-height:16px;
 font-size:13px;font-weight:600;color:var(--ac-hot);background:var(--surface3);position:relative}
/* reads 30px tall, hit area grows invisibly past it (30 + 14 = 44). Vertical only, so it never
   steals the stage text's tap. */
.stage .view::before{content:'';position:absolute;inset:-7px 0}
/* 18px, not 9: .view and .archbtn each hang 12px past their line and at 9px overlapped on the
   stage bar. 10 + 4 + 18 = 32 clears both. */
.foot{padding:0;border:0;margin-top:18px;display:flex;justify-content:space-between;
 align-items:center;gap:12px;flex-wrap:wrap}
.footacts{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.est{font-size:14px;font-weight:400;color:var(--m1)}
/* bare 14px text actions: pad the hit box to about 43px and cancel it with an equal negative
   margin, so the resting layout is byte-identical. */
.view{font-size:14px;font-weight:500;color:var(--ac-pale);text-decoration:none;
 padding:12px 8px;margin:-12px -8px;-webkit-user-select:none;user-select:none;
 transition:color .15s,background-color .15s}
.archbtn{font-size:14px;font-weight:500;color:var(--ac-pale);background:transparent;border:0;
 padding:12px 8px;cursor:pointer;width:auto;margin:-12px -8px;font-family:inherit;
 -webkit-user-select:none;user-select:none;
 transition:color .15s,background-color .15s,transform .14s ease-out}
.archbtn:active{transform:scale(.97)}
.empty{color:var(--m1);font-size:14px;padding:48px 20px;margin-top:14px;text-align:center;line-height:1.7;
 background:var(--surface);border:1px solid var(--hair2);border-radius:16px;
 box-shadow:0 2px 10px var(--shc3)}
/* ---- filmstrip: the row's own contact sheet ------------------------------ */
/* up to 8 tiles, the 8th a "+N" chip when the sub has more imaged cards than fit. */
/* the strip scrolls at every width: 8 tiles measure 742px, so any sheet under ~782px would
   scroll the page sideways. */
.strip{display:flex;gap:10px;margin-top:14px;overflow-x:auto;
 overscroll-behavior-x:contain;scrollbar-width:none}
.strip::-webkit-scrollbar{display:none}
/* the strip clips vertically too, so a tile's focus ring draws inside the tile. */
.strip a:focus-visible{outline-offset:-2px}
/* [href^="/img"] is the lightbox's own selector, so the "+N" chip keeps its display:flex. */
.strip a[href^="/img"]{display:block;flex-shrink:0;line-height:0}
.strip img{width:84px;height:117px;object-fit:cover;border-radius:6px;border:1px solid var(--hair);
 background:var(--surface3);cursor:zoom-in;flex-shrink:0}
/* --surface3, not --ph: inside a white card the ground-tuned --ph vanishes. --ph stays for
   grids on the page ground. */
.morechip{width:84px;height:117px;border-radius:6px;border:1px solid var(--hair);
 background:var(--surface3);display:flex;align-items:center;justify-content:center;font-size:14px;
 font-weight:600;color:var(--m1);text-decoration:none;flex-shrink:0}
/* no bleed past the phone breakpoint, so an overflowing strip is sliced mid tile; the cue is a
   28px mask fade on the edge with tiles past it (FX_JS sets .sl/.sr). */
@media(min-width:641px){
 .strip{--fadel:0px;--fader:0px;
  -webkit-mask-image:linear-gradient(90deg,transparent,#000 var(--fadel),
   #000 calc(100% - var(--fader)),transparent);
  mask-image:linear-gradient(90deg,transparent,#000 var(--fadel),
   #000 calc(100% - var(--fader)),transparent)}
 .strip.sl{--fadel:28px}
 .strip.sr{--fader:28px}}
.hint{display:flex;align-items:center;gap:10px;margin:14px 0 0;padding:12px 16px;font-size:14px;
 color:var(--m1);background:var(--surface);border:1px solid var(--hair2);border-radius:16px;
 box-shadow:0 2px 10px var(--shc3)}
.hintx{width:auto;margin:-12px -12px -12px auto;padding:12px 14px;background:transparent;border:0;
 color:var(--m1);font-size:14px;cursor:pointer;-webkit-user-select:none;user-select:none;
 transition:color .15s,background-color .15s}
/* ---- scans: image, 6px radius, hairline, no shadow ------------------------ */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(152px,1fr));gap:18px;margin-top:24px}
.grid img{width:100%;border-radius:6px;border:1px solid var(--hair);background:var(--surface3);
 aspect-ratio:1.72/2.4;object-fit:cover;display:block}
/* NO content-visibility: its paint containment clips focus rings and .sublink's
   negative-margin bleed. FX_JS handles the off-screen sweep instead. */
.gc{background:transparent;border:0;border-radius:0;padding:0;display:flex;flex-direction:column}
.gc .ph{width:100%;aspect-ratio:1.72/2.4;border-radius:6px;border:1px solid var(--hair);
 background:var(--ph);display:flex;align-items:center;justify-content:center;
 color:var(--m1);font-size:12px}
.card .gc .ph{background:var(--surface3)}
/* the grade line is always emitted, empty on an ungraded card, or neighbours in a grid row
   stagger. 14 x 1.5 = 21. */
.gc .gr{font-size:14px;font-weight:600;color:var(--grade);margin-top:9px;min-height:21px}
.gc .cn{font-size:12px;font-weight:400;color:var(--m1);margin-top:5px;line-height:1.4;
 font-family:ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,monospace}
.cn.pre{font-family:inherit;font-size:12px}
/* the name is the subject only (split_name demotes the set). Two lines reserved so a grid row
   shares a baseline: 2 x 14 x 1.4 = 39.2 -> 40. min-height, not height (WCAG 1.4.4). */
.gc .nm{font-size:14px;font-weight:400;color:var(--txt);line-height:1.4;margin-top:4px;min-height:40px;
 display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.gc .nmset{font-size:12px;color:var(--m1);margin-top:2px;white-space:nowrap;overflow:hidden;
 text-overflow:ellipsis}
.gc .cval{font-size:17px;font-weight:650;letter-spacing:-.012em;color:var(--txt);margin-top:4px}
.gc .cval span{font-size:12px;font-weight:400;letter-spacing:normal;color:var(--m1)}
.svc{font-size:12px;color:var(--m1);margin-top:4px}
/* -4/+10 top nets the original 6px gap; -10/+10 bottom nets 0 (see .view) */
.sublink{display:block;font-size:14px;font-weight:500;color:var(--ac-pale);text-decoration:none;
 padding:10px 6px;margin:-4px -6px -10px;transition:color .15s,background-color .15s}
/* a real class, not "has any inline style": keying on [style] repainted unrelated inline
   styles. */
.sublink.sublink-static{color:var(--m1);font-weight:400;cursor:default}
/* owner tag: plain text until you touch it - hairline on hover, accent on focus */
.ownrow{display:flex;align-items:center;margin-top:auto}
.own{background:transparent;border:0;border-bottom:1px solid transparent;
 border-radius:0;color:var(--txt);font:inherit;font-size:14px;font-weight:400;
 padding:11px 0 10px;flex:1;min-width:0;transition:border-color .15s;touch-action:manipulation}
/* touch: tap navigates, the pencil edits (double-tap-to-edit races navigation). Hidden while
   editing. */
.ownedit{display:none;border:0;background:transparent;color:var(--m1);padding:0;cursor:pointer}
@media(pointer:coarse){
 .ownedit{display:flex;align-items:center;justify-content:center;width:40px;
  margin-right:-6px;align-self:stretch}
 .ownedit:active{color:var(--txt)}
 /* the input's focus hides it, not the row's: :focus-within matched the pencil's own focus and
    the tap did nothing. */
 .own:focus + .ownedit{display:none}}
.own[readonly]{cursor:pointer}
.own::placeholder{color:var(--m1)}
/* pointer focus keeps the underline; keyboard focus gets the ring - 1px is not a visible
   indicator (WCAG 2.4.11). focus-visible after :focus so it wins. */
.own:focus{border-bottom-color:var(--ring);outline:none}
.own:focus-visible{border-bottom-color:var(--ring);outline:2px solid var(--ring);outline-offset:2px}
.own.saved{border-bottom-color:var(--ok)}
.own.errsave{border-bottom-color:var(--err)}
.undo{width:auto;margin:-6px -6px -12px;padding:12px 6px;background:transparent;border:0;
 color:var(--ac-pale);font-size:12px;font-weight:500;font-family:inherit;cursor:pointer;
 transition:color .15s,background-color .15s}
.undo.uerr{color:var(--err)}
/* ---- lightbox ------------------------------------------------------------ */
/* overscroll-behavior:contain stops a scrim drag chaining to the dashboard; LIGHTBOX_JS pins
   body overflow. */
.lb{position:fixed;inset:0;z-index:50;background:var(--scrim);display:flex;
 align-items:center;justify-content:center;cursor:zoom-out;overscroll-behavior:contain;
 opacity:0;visibility:hidden;backdrop-filter:blur(0px);-webkit-backdrop-filter:blur(0px);
 transition:opacity .2s ease-out,backdrop-filter .2s ease-out,
  -webkit-backdrop-filter .2s ease-out,visibility 0s .2s}
.lb.open{opacity:1;visibility:visible;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
 transition-delay:0s}
.lb img{max-width:92vw;max-height:92vh;border-radius:12px;box-shadow:0 24px 70px rgba(0,0,0,.45);
 transform:scale(.97);transition:transform .25s cubic-bezier(.23,1,.32,1);cursor:default}
.lb.open img{transform:none}
/* the scan is inert, the scrim and this orb close. Fixed values, not tokens - it always sits
   on the dimmed scrim. */
.lbx{position:fixed;top:18px;right:18px;width:44px;height:44px;border-radius:50%;
 display:flex;align-items:center;justify-content:center;padding:0;margin:0;
 color:#fff;background:rgba(0,0,0,.35);border:0;cursor:pointer;
 transition:background .15s,transform .14s ease-out}
@media(hover:hover){.lbx:hover{background:rgba(0,0,0,.55)}}
.grid a{cursor:zoom-in;position:relative;display:block}
/* the loading sweep is one transform-moved overlay on the anchor, compositor only.
   [href^="/img"] is the lightbox's selector, so .sublink is untouched; overflow clips the
   band. */
.grid a[href^="/img"]{overflow:hidden;border-radius:6px}
/* the sweep only runs on .ldg, which FX_JS sets when a loading tile nears the viewport, so
   below-the-fold tiles cost nothing. */
.grid a[href^="/img"].ldg::after{content:'';position:absolute;inset:0;border-radius:6px;
 pointer-events:none;
 background:linear-gradient(100deg,transparent 20%,var(--sh2) 50%,transparent 80%);
 animation:sweep 1.15s linear infinite}
/* FX_JS tags the anchor when its img settles: a plain class match, not :has(img.ld), which
   older Safari/Firefox never resolve. */
.grid a.ld::after{display:none}
@keyframes sweep{from{transform:translateX(-100%)}to{transform:translateX(100%)}}
/* ---- corner controls: glass orbs ----------------------------------------- */
/* 44x44 is the HIG floor; the 8px gap is kept by pushing the gear to 20 + 44 + 8 = 72. */
#gearbtn,#themeflip{position:fixed;bottom:20px;z-index:40;width:44px;height:44px;
 border-radius:50%;color:var(--m1);cursor:pointer;
 display:flex;align-items:center;justify-content:center;padding:0;margin:0;
 transition:color .15s,opacity .15s,transform .14s ease-out;text-decoration:none}
#themeflip{right:20px}
#gearbtn{right:72px}
#gearbtn:active,#themeflip:active{transform:scale(.94)}
/* the orbs float over the owner tag and View, so FX_JS marks the document scrolling for 150ms
   after each scroll and they go inert - the tap falls through. Pointer devices keep them live. */
@media(hover:none){
 html.scrolling #gearbtn,html.scrolling #themeflip{pointer-events:none;opacity:.55}}
/* ---- forms --------------------------------------------------------------- */
/* every single-line control is a capsule; 3px extra side padding buys the curve back.
   Content-side radii stay square-ish. */
input{width:100%;margin-top:12px;background:var(--inp);border:0;border-radius:999px;
 color:var(--txt);font-size:15px;font-weight:400;text-align:left;padding:11px 16px;
 font-family:inherit;outline:none}
input:focus,input:focus-visible{outline:2px solid var(--ring);outline-offset:0}
input::placeholder{color:var(--m1)}
/* BUTTONS ARE NOT FILLED BY DEFAULT: the fill is opt-in via .fillbtn, the element rule keeps
   neutral resets only. Typography stays - a reset, not an identity. */
button{background:transparent;border:0;color:inherit;
 font-family:inherit;font-size:15px;font-weight:600;cursor:pointer}
/* filled primary: form submits and modal saves. Carries the width:100% and margin-top:12px the
   element rule used to hand out. */
.fillbtn{width:100%;margin-top:12px;background:var(--ac-fill);border-radius:999px;color:#fff;
 padding:12px;transition:background .18s,transform .14s ease-out}
/* press-scale stays element-level: it sets no colour, so it cannot leak a fill. */
button:active{transform:scale(.97)}
button:disabled{opacity:.5;cursor:default}
.err{color:var(--err);font-size:12px;font-weight:500;margin-top:12px;min-height:14px}
/* ---- settings ------------------------------------------------------------ */
.card.sblock{margin:0 0 14px;padding:22px 20px 24px}
.sblock .sform{max-width:430px}
.sform button{margin-top:14px}
.srow{display:flex;gap:10px;margin-top:14px;max-width:520px;flex-wrap:wrap;align-items:center}
.srow input{flex:1;min-width:150px;margin-top:0}
.sbtn{width:auto;margin-top:0;padding:11px 18px;font-size:13px;flex-shrink:0}
/* a destructive text action is not a primary, so .sdel never takes .fillbtn; the radius is
   restated because the element rule hands none out. .squiet is the same in accent. */
.sbtn.sdel,.sbtn.squiet{background:transparent;padding:11px 0;margin-top:10px;
 border-radius:999px}
.sbtn.sdel{color:var(--err)}
.sbtn.squiet{color:var(--ac-pale)}
.srow .sbtn.sdel,.srow .sbtn.squiet{margin-top:0}
.stitle{font-size:17px;font-weight:650;letter-spacing:-.012em;color:var(--txt)}
.sblock .meta{margin-top:3px}
.sdanger{margin-top:20px;padding-top:16px;border-top:1px solid var(--hair2)}
.snote{display:inline-block;font-size:14px;font-weight:500;color:var(--ac-pale);margin-top:16px}
.snote.serr{color:var(--err)}
.sbar .f{padding:7px 15px 9px}  /* same -1/+1 optical shift as the base pill */
/* attention dot: the account PSA wants verified. Accent, not red - red is grades and the hold
   pill. The label rides in a .vh span. */
.schip.att::after{content:"";display:inline-block;width:6px;height:6px;margin-left:7px;
 border-radius:50%;background:var(--ac);vertical-align:1px}
.spane{margin-top:16px}
/* sheets materialize like the lightbox: scrim fades up with blur(8px), sheet lands from .97,
   exit quicker. */
.smodal{position:fixed;inset:0;z-index:60;background:var(--scrim);display:flex;
 align-items:center;justify-content:center;padding:18px;
 opacity:0;visibility:hidden;backdrop-filter:blur(0px);-webkit-backdrop-filter:blur(0px);
 transition:opacity .14s ease-out,backdrop-filter .14s ease-out,
  -webkit-backdrop-filter .14s ease-out,visibility 0s .14s}
.smodal.on{opacity:1;visibility:visible;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
 transition:opacity .2s ease-out,backdrop-filter .2s ease-out,
  -webkit-backdrop-filter .2s ease-out,visibility 0s}
.smodal .card{width:min(460px,94vw);margin:0;background:var(--surface);border:1px solid var(--hair);
 border-radius:14px;padding:24px 24px 26px;box-shadow:0 24px 60px var(--shc2);
 animation:none;transform:scale(.97);
 transition:background .18s,opacity .18s,filter .18s,transform .16s ease-out}
.smodal.on .card{transform:none;
 transition:background .18s,opacity .18s,filter .18s,transform .25s cubic-bezier(.23,1,.32,1)}
.sclose{float:right;background:transparent;border:0;color:var(--m1);font-size:15px;cursor:pointer;
 width:auto;margin:-10px -12px;padding:12px 18px;transition:color .15s,background-color .15s}
.dbtn{width:auto;margin:-1px -8px -11px;padding:11px 8px;background:transparent;color:var(--ac-pale);
 font-size:14px;font-weight:500}
.dbtn::before{content:none}  /* .dbtn carries .f: it pads its own hit box now */
.dstate{font-size:14px;font-weight:500;color:var(--txt);flex:1}
.dhint{font-size:12px;color:var(--m1);line-height:1.6;margin-top:12px}
/* ---- misc ---------------------------------------------------------------- */
/* no wash on an archived card: the .5 dim put its text at 2.0 to 3.4 on white (1.4.3). "Past"
   is grayscale alone; the ink keeps its 4.5. */
.card.arch{filter:grayscale(.55)}
/* an archived tile dims its scan, not its data - tiles render inline in search results, so .5
   put real content near 1.9:1 (1.4.3). The no-scan placeholder is a label, not a scan. */
.gc.arch a[href^="/img"]{opacity:.5;filter:grayscale(.6);
 transition:opacity .18s,filter .18s}
.card.tlcard{padding:16px;margin:14px 0}
.archdim img{filter:grayscale(.7);opacity:.85;transition:filter .18s,opacity .18s}
.tlink{color:var(--ac-pale);text-decoration:none;padding:12px 6px;margin:-12px -6px;
 transition:color .15s,background-color .15s}
/* a 22px line, so it takes the sort pills' invisible hit pseudo: 22 + 11 each way = 44.
   Vertical only, so it never reaches the pills across the row. */
.numlink{text-decoration:none;color:inherit;display:inline-block;position:relative}
.numlink::before{content:'';position:absolute;inset:-11px 0}
.numlink .num{transition:color .15s}
.setupform{margin-top:18px}
.setupnote{font-size:12px;color:var(--m1);margin-top:16px;line-height:1.6}
.gate{min-height:calc(100vh - 124px);min-height:calc(100dvh - 124px);
 display:flex;align-items:center;justify-content:center}
/* the gate is a card too: on the grouped ground a bare stack floats anchorless and the quiet
   input fill vanished. */
.gbox{width:min(340px,100%);text-align:center;background:var(--surface);
 border:1px solid var(--hair2);border-radius:20px;padding:28px 22px;
 box-shadow:0 2px 10px var(--shc3)}
/* the gate is a narrow card, not a page: a title sized for an 820px sheet wraps a two-word
   name. One step down, and unchanged on phones. */
.gbox h1{font-size:24px;letter-spacing:-.02em}
.gbox input{text-align:center}
.gbox .sub{margin-top:6px}
/* ---- hover: pointer devices only ----------------------------------------- */
@media(hover:hover){
/* the hover tint layers on the card surface - background replaces, so a bare alpha wash would
   show page ground. */
.card:hover{background:color-mix(in srgb,var(--txt) 4%,var(--surface))}
/* group wrappers and the timeline block are .card for the lift but are not targets; only the
   sub-number link is. */
.card.grp:hover,.card.tlcard:hover{background:var(--surface)}
.card.arch:hover{filter:none}
.gc.arch:hover a[href^="/img"]{opacity:.78;filter:grayscale(.3)}
.f:hover{color:var(--fhov)}
.f.on:hover{color:var(--ac-pale)}
/* after .f.on:hover and at 4 classes so the pressed Archived pill keeps its fill text colour. */
.f.farch.on:hover{color:#fff;background:var(--ac-fill-hot)}
.pvrow:hover{background:var(--hovrow)}
.own[readonly]:hover{border-bottom-color:var(--hairh)}
.lgout:hover,.hintx:hover,.sclose:hover{color:var(--txt)}
.view:hover,.archbtn:hover,.sublink:not(.sublink-static):hover,.undo:hover,.tlink:hover,.dbtn:hover,.sbtn.squiet:hover{color:var(--ac-hot)}
/* text actions keep the invisible hit box but hover never paints it - the slab hung over the
   stage bar. Hover is the colour deepen; the View pill is the exception, it is a visible
   capsule. */
.stage .view:hover{color:var(--ac-hot);background:color-mix(in srgb,var(--txt) 6%,var(--surface3))}
/* the glyph actions ARE square-ish targets, so theirs is a circle */
.hintx:hover,.sclose:hover,.lgout:hover{background:var(--surface3);border-radius:999px}
.numlink:hover .num{color:var(--ac-pale)}
.fillbtn:hover{background:var(--ac-fill-hot)}
.sbtn.sdel:hover{background:transparent;color:var(--err)}
#gearbtn:hover,#themeflip:hover{color:var(--txt)}}
/* ---- motion: one settle on the rows, nothing decorative ------------------- */
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
/* registered so the mobile capsule cue can fade rather than pop; unsupported, the vars still
   resolve. */
@property --cuel{syntax:'<color>';inherits:false;initial-value:transparent}
@property --cuer{syntax:'<color>';inherits:false;initial-value:transparent}
/* ---- mobile: only the CURRENT stage is ever named ------------------------- */
@media(max-width:640px){
 /* phone navigations are instant swaps: the crossfade shows a stale snapshot for about a
    quarter second, which reads as lag. */
 :root{view-transition-name:none}
 body{padding:16px 14px 88px}
 .tbtop{flex-wrap:wrap;gap:10px}
 .brand{gap:10px;min-width:0}
 .logo{height:26px}
 /* the large title tracks the sheet, not the type scale: at 26px beside the logo it pushes
    .tbend to a second line at 347px. .gbox h1 is deliberately untouched. */
 h1{font-size:22px;letter-spacing:-.017em}
 .tbend{gap:8px;margin-left:auto}
 /* page-header summaries take the full sheet width instead of clipping right */
 .hrow{flex-wrap:wrap}
 .hrow>.synced{flex:1 0 100%;text-align:left;margin-top:12px;font-size:12px}
 /* the 34ch measure keeps its width but not its right edge: full-width and left-aligned,
    margin-left:auto floated it to the middle. */
 .hrow>.synced .estnote{margin-left:0}
 /* the segment never breaks to a second row, and to 360px is not an overflow box either: three
    pills measure ~247px, and staying un-clipped is what lets the hit pseudo work (28 + 8 each
    way = 44 on the thin 38px capsule). Below 360 it scrolls and clips. */
 .filters{display:flex;flex-wrap:nowrap;max-width:100%;padding:4px 3px;align-items:center}
 .filters .f{flex:0 0 auto}
 .filterrow .filters .f::before{inset:-8px 0}
 /* scroll cue, live only below 360px where the capsule scrolls and the scrollbar is hidden: a
    22px shade on each edge with content past it, FX_JS flips .sl/.sr. Default attachment, not
    the CSS-only local trick, whose opaque cover would patch over the glass. */
 .filters{--cuel:transparent;--cuer:transparent;
  background-image:linear-gradient(90deg,var(--cuel),transparent),
   linear-gradient(270deg,var(--cuer),transparent),
   linear-gradient(var(--segtrack),var(--segtrack));
  background-position:left center,right center,0 0;
  background-size:22px 100%,22px 100%,auto;
  background-repeat:no-repeat,no-repeat,repeat;
  transition:--cuel .18s ease-out,--cuer .18s ease-out}
 .filters.sl{--cuel:var(--shc3)}
 .filters.sr{--cuer:var(--shc3)}
 /* the capsule hugs its pills - no flex:1, or a long empty glass track past the last pill
    reads as broken; the slack belongs between the controls. min-width:0 is what lets it scroll
    at 360px, where the count leaves Archived and pill padding goes 14 -> 11. */
 .filterrow .filters{min-width:0}
 .archn{display:none}
 .filterrow .filters .f{padding:5px 11px 7px}
 .grid{grid-template-columns:repeat(auto-fill,minmax(136px,1fr));gap:14px}
 /* phone filmstrip: 64x89 tiles, bleeding to the card's own padding edge (-14px) so the last
    tile runs off the edge as the "there is more" cue. */
 .strip{gap:8px;margin:12px -14px 0;padding:0 14px}
 .strip img,.morechip{width:64px;height:89px}
 .card{padding:16px 14px;margin:0 0 12px}
 .card.tlcard{margin:14px 0}
 input,.searchbar{font-size:16px}
 /* 16px only while the tag is editable - the only moment iOS zooms on focus; readonly it
    shouted over the 14px name. */
 .own:not([readonly]){font-size:16px}
 .gc .nm{min-height:0}}
/* sub-360: pills plus the solo pill can exceed the sheet, so the capsule scrolls. The one
   width where the overflow box clips the hit pseudo to 36px (past WCAG 2.5.8's 24px floor);
   overflow-y hidden so the -8px pseudo cannot open a phantom scroll. */
@media(max-width:359px){
 .filters{overflow-x:auto;overflow-y:hidden;overscroll-behavior-x:contain;scrollbar-width:none}
 .filters::-webkit-scrollbar{display:none}}
/* iOS focus-zoom fires on any sub-16px input on a coarse pointer, not on a narrow viewport -
   this covers iPad portrait. */
@media(pointer:coarse) and (min-width:641px){
 input,.searchbar{font-size:16px}
 .own:not([readonly]){font-size:16px}}
/* ---- reduced motion: named, not blanket ---------------------------------- */
/* kill the travel, keep the feedback: hover tints, focus rings and overlay fades still land.
   After the mobile block so it out-orders the capsule cue. */
@media(prefers-reduced-motion:reduce){
 html{scroll-behavior:auto}
 /* travel: the row settle, the bar running out, the loading sweep */
 .card,.gc{animation:none}
 .bar i{transition:none}
 .grid a[href^="/img"]::after{display:none}
 .f:active,.archbtn:active,button:active,#gearbtn:active,#themeflip:active{transform:none}
 .toolbar{transition:none}
 .filters{transition:none}
 .preview{transform:none;transition:opacity .12s ease-out,visibility 0s .12s}
 .preview.on{transform:none;transition:opacity .12s ease-out,visibility 0s}
 .lb,.smodal{backdrop-filter:none;-webkit-backdrop-filter:none;
  transition:opacity .12s ease-out,visibility 0s .12s}
 .lb.open{backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
  transition:opacity .12s ease-out,visibility 0s}
 .smodal.on{backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
  transition:opacity .12s ease-out,visibility 0s}
 .lb img,.lb.open img,.smodal .card,.smodal.on .card{transform:none;transition:none}
 ::view-transition-group(*),::view-transition-old(*),::view-transition-new(*){animation:none}}
/* ---- glass fallbacks ----------------------------------------------------- */
/* background-COLOR, never the shorthand, which would wipe the segtrack layer and the scroll
   cue. */
@supports not ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){
 .toolbar,.filters,.sbar,#gearbtn,#themeflip,.f.fsolo{background-color:var(--glasssolid)}
 /* backdrop-filter made the capsule a stacking context; without it the pills' z-index:-1
    pseudo falls behind the opaque background. */
 .filters,.sbar{isolation:isolate}}
/* no color-mix, no ambient: the pseudo goes empty and the flat --bg on <html> shows through. */
@supports not (background:color-mix(in srgb,red 5%,transparent)){
 body::before{background:none}}
@media(prefers-reduced-transparency:reduce){
 .toolbar,.filters,.sbar,#gearbtn,#themeflip,.f.fsolo{backdrop-filter:none;-webkit-backdrop-filter:none;
  background-color:var(--glasssolid)}
 .filters,.sbar{isolation:isolate}
 .lb,.lb.open,.smodal,.smodal.on{backdrop-filter:none;-webkit-backdrop-filter:none;
  background:rgba(0,0,0,.72)}
 body::before{background:none}}
@media(prefers-contrast:more){
 body::before{background:none}}
"""

# favicon: accent-colored card-fan mark (three cards, opacity steps for depth),
# inline SVG so it needs no asset file - matches the logo.svg fan language
_FAV_FILL = ACCENT.replace("#", "%23")
FAVICON = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
           f"<rect width='64' height='64' rx='14' fill='{_FAV_FILL}'/>"
           "<rect x='21' y='12' width='22' height='32' rx='4' fill='white' opacity='0.5' transform='rotate(-18 32 56)'/>"
           "<rect x='21' y='12' width='22' height='32' rx='4' fill='white' opacity='0.75'/>"
           "<rect x='21' y='12' width='22' height='32' rx='4' fill='white' transform='rotate(18 32 56)'/></svg>")

# Safari + iOS ignore SVG favicons entirely and fall back to a domain-letter
# tile ("F" for example.com). When pre-rendered PNGs sit next to the app
# (deployed like logo.svg) they get linked and served so every browser and the
# iOS home screen show the real mark; without the files behavior is unchanged.
FAV_PNG = os.environ.get("PSA_FAVICON", "/opt/psa-tracker/favicon.png")
TOUCH_PNG = os.environ.get("PSA_TOUCH_ICON", "/opt/psa-tracker/apple-touch-icon.png")
_ICONS = f'<link rel="icon" type="image/svg+xml" href="{FAVICON}">'
if os.path.exists(FAV_PNG):
    _ICONS += f'\n<link rel="icon" type="image/png" sizes="64x64" href="/favicon.png?v={int(os.path.getmtime(FAV_PNG))}">'
if os.path.exists(TOUCH_PNG):
    _ICONS += f'\n<link rel="apple-touch-icon" href="/apple-touch-icon.png?v={int(os.path.getmtime(TOUCH_PNG))}">'

# Home-screen install: with no manifest Chrome falls back to the 64px favicon.
# Five keys is everything it needs, and the icon is the 180px touch PNG.
MANIFEST = json.dumps({"name": SITE_TITLE, "short_name": SITE_TITLE, "start_url": "/",
                       "display": "standalone",
                       "icons": [{"src": "/apple-touch-icon.png", "sizes": "180x180",
                                  "type": "image/png"}] if os.path.exists(TOUCH_PNG) else []})

# theme-color paints the browser and installed-app chrome, so it has to follow
# the ground token of the theme actually rendered. With no stored choice the
# head script below renders the SYSTEM scheme, whatever the store default is,
# so the pair is keyed on prefers-color-scheme to match it. A stored choice is
# always the opposite of the system one (the flip deletes the key when they
# agree), so psaTC collapses the pair to the one color really on screen.
HEAD_HTML = f"""{_ICONS}
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" media="(prefers-color-scheme: dark)" content="{_DARK['bg']}">
<meta name="theme-color" content="{_LIGHT['bg']}">
<meta name="description" content="PSA grading submission tracker">
<script>(function(){{var t=null;try{{t=localStorage.getItem('psa_theme');}}catch(e){{}}
var sys=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light',cur=t||sys;
if(cur!=="{THEME}")document.documentElement.dataset.theme=cur;
window.psaTC=function(c){{var m=document.querySelectorAll('meta[name=theme-color]');
for(var i=0;i<m.length-1;i++)m[i].remove();
if(m.length)m[m.length-1].content=(c==='dark')?"{_DARK['bg']}":"{_LIGHT['bg']}";}};
if(t)psaTC(cur);}})()</script>"""

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
  var mq=matchMedia('(prefers-color-scheme: dark)');
  function sys(){{return mq.matches?'dark':'light';}}
  function render(){{
    b.innerHTML=(cur==='dark')?SUN:MOON;
    b.title=(cur==='dark')?'Switch to light mode':'Switch to dark mode';
    b.setAttribute('aria-label',b.title);
    if(window.psaTC)psaTC(cur);
  }}
  b.addEventListener('click',function(){{
    cur=(cur==='dark')?'light':'dark';
    /* choosing the system's current value returns the page to auto-follow */
    try{{
      if(cur===sys())localStorage.removeItem('psa_theme');
      else localStorage.setItem('psa_theme',cur);
    }}catch(e){{}}
    d.dataset.theme=cur;
    render();
  }});
  /* both orbs live in one landmark. GEAR_HTML ships the nav on pages that have
     a gear; where it is suppressed (personal mode, the gate) this makes it. */
  var nav=document.getElementById('sitectl');
  if(!nav){{
    nav=document.createElement('nav');nav.id='sitectl';
    nav.setAttribute('aria-label','Site controls');
    document.body.appendChild(nav);
  }}
  nav.appendChild(b);render();
  mq.addEventListener('change',function(e){{
    var stored=null;try{{stored=localStorage.getItem('psa_theme');}}catch(x){{}}
    if(!stored){{cur=e.matches?'dark':'light';d.dataset.theme=cur;render();}}
  }});
}})();
</script>"""

def _pic(paths):
    """Tiny inline pill icon (stroke = currentColor so it inherits pill color)."""
    return (f'<svg class="pic" width="12" height="12" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round">{paths}</svg>')

ICON_CLOCK = _pic('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>')
ICON_OUT = ('<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
            '<path d="m16 17 5-5-5-5"/><path d="M21 12H9"/></svg>')
# the one close affordance, shared by every dismiss control (hint, modals).
# 14px: the flip/out icons sit at 15-17, a close reads a step quieter.
# Deliberately left INLINE with vertical-align:middle - an inline child keeps
# the button's font strut, so the line box (and therefore the hover circle and
# hit area) stays exactly the height it was under the text glyph.
ICON_X = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
          'stroke-width="2" stroke-linecap="round" style="vertical-align:middle">'
          '<path d="M6 6l12 12M18 6L6 18"/></svg>')
ICON_CHECK = _pic('<path d="m5 13 4 4 10-10"/>')
ICON_HOLD = _pic('<path d="M9 5v14M15 5v14"/>')

# carrier tracking pages: substring-matched against the sub's carrier field so
# tracking numbers become one-click instead of copy-paste
_CARRIER_URLS = {
    "fedex": "https://www.fedex.com/fedextrack/?trknbr=",
    "ups": "https://www.ups.com/track?tracknum=",
    "usps": "https://tools.usps.com/go/TrackConfirmAction?tLabels=",
    "canada post": "https://www.canadapost-postescanada.ca/track-reperage/en#/search?searchFor=",
    "purolator": "https://www.purolator.com/en/shipping/tracking?pin=",
    "dhl": "https://www.dhl.com/ca-en/home/tracking.html?tracking-id=",
}

def tracking_html(carrier, tracking):
    """'FedEx 3822…' as a link to the carrier's tracking page (plain text if
    the carrier isn't recognized)."""
    label = html.escape(f"{carrier} {tracking}")
    base = next((u for k, u in _CARRIER_URLS.items() if k in (carrier or "").lower()), "")
    if not base:
        c = (carrier or "").strip()
        if c and c.lower() == str(tracking or "").strip().lower():
            return html.escape(c)  # "Pickup pickup" is one word
        return label
    return (f'<a class="tlink" href="{base}{urllib.parse.quote(str(tracking))}" '
            f'target="_blank" rel="noopener">{label}</a>')

def eta_words(s):
    """One vocabulary for a sub's expected return, everywhere: (label, value,
    muted). Muted is the two states with nothing to look forward to - no date
    at all, or a date PSA has already blown through."""
    d = s["est_end"] or s["est_start"]
    if not d:
        return "PSA ETA", "ETA pending", True
    if d[:10] < datetime.now(DISPLAY_TZ).strftime("%Y-%m-%d"):
        return "PSA ETA", f"Was due {short_date(d)}", True
    return "Back", short_date(d), False

def eta_pill(s):
    """Status pill(s) for a sub: the hold, then shipped or the return ETA.
    Shipped reads at ink level, everything in flight at muted, so the column
    scans (the old .done class was emitted for two different states and had
    no CSS rule at all - the column read as one gray).
    A hold no longer swallows the date: both pills render, stacked by .pills."""
    hold = f'<span class="pill hold">{ICON_HOLD}On hold</span>' if s["on_hold"] else ""
    if s["status"] == "Shipped":
        return hold + f'<span class="pill shipped">{ICON_CHECK}Shipped</span>'
    label, val, muted = eta_words(s)
    txt = html.escape(val if muted else f"{label} {val}")
    return hold + f'<span class="pill{" pending" if muted else ""}">{ICON_CLOCK}{txt}</span>'

# NO grades-landed pill and NO red announcement of grades arriving: shipped
# briefly on 2026-08-01 (red "N grades landed" pill + a "Grades ready" sort)
# and REMOVED by the owner's call on 2026-08-02. Grades-ready stays a muted footer
# line; red belongs to the grade on the tile, holds, and alerts only.

# The gate is ONE field on purpose (the account chooser is invisible by design),
# but that field was always type=password - so a customer typing a 20-character
# email address on a phone in the evening typed it entirely blind, with the
# password manager offering the wrong entry. The moment the value looks like an
# email it becomes a plain email field; delete the @ and it masks again. The
# caret jumps to the end on a type swap, which is where it already is mid-typing.
GATE_JS = """<script>
(function(){
  var i=document.querySelector('.gbox input[name=password]');
  if(!i)return;
  i.addEventListener('input',function(){
    var mail=i.value.indexOf('@')>-1;
    if(mail===(i.type==='email'))return;
    i.type=mail?'email':'password';
    i.setAttribute('inputmode',mail?'email':'text');
    i.setAttribute('autocomplete',mail?'email':'current-password');
  });
})();
</script>"""

def gate_page(error=""):
    # only advertise email login where it can actually work (email owner tags)
    email_on = email_login_on()
    ph = "Password or email" if email_on else "Password"
    inv = ' aria-invalid="true"' if error else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(SITE_TITLE)}</title>
{HEAD_HTML}
<style>{THEME_VARS}</style>{APP_CSS_TAG}</head><body><main class="wrap"><div class="gate"><div class="gbox">
{logo_tag()}<h1>{html.escape(SITE_TITLE)}</h1><div class="sub">{html.escape(SITE_TAGLINE)}</div>
<form method="POST" action="/login">
<input type="password" name="password" placeholder="{ph}" aria-label="{ph}"
 autofocus autocomplete="current-password" autocapitalize="none" autocorrect="off"
 spellcheck="false" aria-describedby="err"{inv}>
<button type="submit" class="fillbtn">Enter</button></form>
<div class="err" id="err" role="alert">{html.escape(error)}</div>
</div></div></main>{GATE_JS if email_on else ""}{THEME_JS}</body></html>"""

def not_found_page(msg="There’s no page at this address.", title="Not found"):
    """Branded 404 so a bad link doesn't drop out of the design."""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
{HEAD_HTML}
<style>{THEME_VARS}</style>{APP_CSS_TAG}</head><body><main class="wrap"><div class="gate"><div class="gbox">
{logo_tag()}<h1>{html.escape(title)}</h1><div class="sub">{html.escape(msg)}</div>
<a class="view" style="display:inline-block;margin-top:10px" href="/">&larr; Back to the dashboard</a>
</div></div></main>{THEME_JS}</body></html>"""

def error_page():
    """Branded 500. A read that failed is a failure, not an empty account."""
    return not_found_page("The tracker couldn’t read your submissions just now. "
                          "Try again in a minute.", "Something went wrong")

# ---------- settings ----------
# /settings edits per-account PSA credentials (WRITE-ONLY - existing values are
# never displayed), per-account Discord webhooks, and adds accounts. Entry:
# type the settings password on the main gate, or the gear icon (admin pages)
# -> a settings-password prompt. Session = its own short-lived signed cookie.
# Both settings templates append @view-transition{navigation:none}: the
# cross-page transition crossfading the heavy dashboard into this unrelated
# layout reads as lag + a jolt (scroll offsets differ), so navigations to and
# from settings are plain loads. Dashboard<->sub<->person transitions keep it.

def env_ok(v):
    """A value that survives one KEY='value' line. A newline or control
    character truncates the file for every later reader, which silently drops
    the account and used to reopen the public setup form."""
    return v.isprintable()

def settings_token(exp):
    sig = hmac.new(SECRET, f"settings.{exp}".encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"

def settings_cookie_hdr():
    exp = int(time.time()) + SETTINGS_MINUTES * 60
    return (f"psa_settings={settings_token(exp)}; Path=/; Max-Age={SETTINGS_MINUTES*60}; "
            "HttpOnly; SameSite=Lax" + ("; Secure" if COOKIE_SECURE else ""))

def settings_authed(cookie_header):
    if not SETTINGS_HASH:
        return False
    for part in (cookie_header or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == "psa_settings":
            exp_s, _, sig = v.partition(".")
            try:
                exp = int(exp_s)
            except ValueError:
                return False
            want = hmac.new(SECRET, f"settings.{exp}".encode(), hashlib.sha256).hexdigest()
            return exp > time.time() and hmac.compare_digest(sig.encode(), want.encode())
    return False

def is_settings_pw(given):
    return bool(SETTINGS_HASH) and hmac.compare_digest(
        hashlib.sha256(given.encode()).hexdigest(), SETTINGS_HASH)

def otp_state(acct_id):
    """Marker files psa_login.py leaves beside account.env: needed (PSA asked
    for a code while we were unarmed), armed (Send code pressed), waiting (the
    SMS went out; otp.code is being polled)."""
    d = os.path.dirname(account_env_path(acct_id))
    st = {}
    for k in ("needed", "armed", "waiting"):
        try:
            st[k] = open(os.path.join(d, f"otp.{k}")).read().strip() or "yes"
        except OSError:
            st[k] = ""
    return st

def account_env_path(acct_id):
    return os.path.join(ACCOUNTS_DIR, acct_id, "account.env")

def settings_gate(error=""):
    inv = ' aria-invalid="true"' if error else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Settings</title>
{HEAD_HTML}
<style>{THEME_VARS}@view-transition{{navigation:none}}</style>{APP_CSS_TAG}</head><body><main class="wrap"><div class="gate"><div class="gbox">
{logo_tag()}<h1>Settings</h1><div class="sub">Enter the settings password</div>
<form method="POST" action="/settings/auth">
<input type="password" name="password" placeholder="Settings password"
 aria-label="Settings password" autofocus autocomplete="off" aria-describedby="err"{inv}>
<button type="submit" class="fillbtn">Open settings</button></form>
<div class="err" id="err" role="alert">{html.escape(error)}</div>
</div></div></main>{THEME_JS}</body></html>"""

FLASH = {}  # one-shot settings notices: token -> (msg, err). They ride a token
            # and not the query string because the Add reply carries a freshly
            # generated site password, which must not land in history or a Referer.

def flash(msg="", err=""):
    """Stash a settings notice, return the /settings URL that shows it once."""
    if len(FLASH) > 30:
        FLASH.clear()
    tok = base64.urlsafe_b64encode(os.urandom(9)).decode()
    FLASH[tok] = (msg, err)
    return "/settings?m=" + tok

def settings_page(msg="", err="", only=""):
    """Panels styled like the rest of the site. Accounts panel: chips by
    email; clicking one opens a popup (new PSA password / unlink - the email
    never changes), Add opens a popup asking only PSA email + password (label
    and a one-time site password are generated). The verification code, site
    password, settings password and per-account webhook each have their own panel.
    All credentials write-only.
    only=<account id> renders that one account alone (a gear-mode session is
    one account's admin, not the instance's)."""
    accts = load_accounts()
    if only:
        accts = {k: v for k, v in accts.items() if k == only}
    multi = len(accts) > 1
    achips, wchips, wpanes, schips, spanes, ochips, opanes = [], [], [], [], [], [], []
    live = False  # an account is arming -> page auto-refreshes
    codefield = False  # a code input is on the page -> it must never auto-refresh
    # an account PSA is asking about sorts first, so arming the second account
    # opens the page on it and not on the healthy one (audit ux-3). sorted() is
    # stable, so everything else keeps load_accounts' order.
    ordered = sorted(((a, otp_state(a["id"])) for a in accts.values()),
                     key=lambda p: not any(p[1].values()))
    for i, (a, ost) in enumerate(ordered):
        env = read_env_file(account_env_path(a["id"]))
        email = env.get("PSA_LOGIN_EMAIL", "") or a["id"]
        if a.get("unlinked"):
            email += " · unlinked"
        # comment-break the @ so Cloudflare email obfuscation leaves chip text
        # alone (JS reads chip.textContent, which skips the comment)
        email_html = html.escape(email).replace("@", "<!-- -->@")
        on = " on" if i == 0 else ""
        hide = "" if (i == 0 or not multi) else ' style="display:none"'
        aid = html.escape(a["id"])
        achips.append(f'<button type="button" class="f schip" data-acct="{aid}">{email_html}</button>')
        hook_on = bool(env.get("DISCORD_WEBHOOK"))
        if multi:
            wchips.append(f'<button type="button" class="f schip{on}" data-group="w" '
                          f'data-pane="wpane{i}">{email_html}</button>')
            schips.append(f'<button type="button" class="f schip{on}" data-group="s" '
                          f'data-pane="spane{i}">{email_html}</button>')
        if multi:
            att = " att" if any(ost.values()) else ""
            mark = '<span class="vh">needs attention, </span>' if att else ""
            ochips.append(f'<button type="button" class="f schip{on}{att}" data-group="o" '
                          f'data-pane="opane{i}">{mark}{email_html}</button>')
        if ost["waiting"]:
            # the only state with a code input, so the refresh below stays off:
            # a reload wipes the digits mid-typing (audit ux-2)
            codefield = True
            ometa = "Code sent to the phone on this PSA account. Enter it within 10 minutes."
        elif ost["armed"]:
            live = True
            ometa = ("Signing in now. The code is on its way to the account’s phone; "
                     "the field for it appears here as soon as PSA sends it.")
        elif ost["needed"]:
            ometa = f"PSA is asking to verify this sign-in (since {html.escape(ost['needed'])}). Syncs are paused until a code goes through."
        else:
            ometa = "Only needed when PSA asks to verify a new sign-in."
        if ost["waiting"]:
            obody = f"""<form method="POST" action="/settings/account" class="srow">
<input type="hidden" name="acct" value="{aid}"><input type="hidden" name="action" value="otp_code">
<input name="value" type="text" inputmode="numeric" autocomplete="one-time-code" placeholder="Verification code"
 aria-label="PSA verification code" maxlength="8">
<button type="submit" class="fillbtn sbtn">Send</button></form>"""
        else:
            obody = f"""<form method="POST" action="/settings/account" class="srow">
<input type="hidden" name="acct" value="{aid}"><input type="hidden" name="action" value="otp_send">
<button type="submit" class="fillbtn sbtn">Send code</button></form>"""
        opanes.append(f"""<div class="spane sg-o" id="opane{i}"{hide}>
<div class="meta">{ometa}</div>
{obody}
</div>""")
        remove_btn = (f'<form method="POST" action="/settings/account" style="margin:0">'
                      f'<input type="hidden" name="acct" value="{aid}">'
                      f'<input type="hidden" name="action" value="webhook_clear">'
                      f'<button type="submit" class="sbtn sdel">Remove</button></form>' if hook_on else "")
        wpanes.append(f"""<div class="spane sg-w" id="wpane{i}"{hide}>
<div class="meta">{"configured" if hook_on else "not set"}</div>
<form method="POST" action="/settings/account" class="srow">
<input type="hidden" name="acct" value="{aid}"><input type="hidden" name="action" value="webhook">
<input name="value" type="password" placeholder="discord.com/api/webhooks/… URL"
 aria-label="Discord webhook URL" autocomplete="off">
<button type="submit" class="sbtn squiet">Save</button></form>
{remove_btn}
</div>""")
        if a.get("feeder"):
            spanes.append(f"""<div class="spane sg-s" id="spane{i}"{hide}>
<div class="meta">Scans into the shared dashboard. The site password covers it.</div>
</div>""")
            continue
        spanes.append(f"""<div class="spane sg-s" id="spane{i}"{hide}>
<form method="POST" action="/settings/account" class="srow">
<input type="hidden" name="acct" value="{aid}"><input type="hidden" name="action" value="site_pw">
<input name="value" type="password" placeholder="New site password"
 aria-label="New site password" autocomplete="new-password">
<input name="value2" type="password" placeholder="Repeat"
 aria-label="Repeat new site password" autocomplete="new-password">
<button type="submit" class="sbtn squiet">Save</button></form>
</div>""")
    add_btn = '<button type="button" class="f" id="saddbtn">Add account</button>'
    pwpanel = "" if only else """<div class="card sblock">
<h2 class="stitle">Settings password</h2>
<div class="meta">opens this settings page</div>
<form method="POST" action="/settings/password" class="srow">
<input name="new_pw" type="password" placeholder="New settings password"
 aria-label="New settings password" autocomplete="new-password">
<input name="confirm_pw" type="password" placeholder="Repeat"
 aria-label="Repeat new settings password" autocomplete="new-password">
<button type="submit" class="sbtn squiet">Save</button></form>
</div>"""
    note = (f'<div class="snote serr" role="alert">{html.escape(err)}</div>' if err else
            (f'<div class="snote" role="status">{html.escape(msg)}</div>' if msg else ""))
    wbar = f'<div class="sbar">{"".join(wchips)}</div>' if multi else ""
    obar = f'<div class="sbar">{"".join(ochips)}</div>' if multi else ""
    refresh = '<meta http-equiv="refresh" content="20">' if (live and not codefield) else ""
    sbar2 = f'<div class="sbar">{"".join(schips)}</div>' if multi else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Settings</title>{refresh}
{HEAD_HTML}
<style>{THEME_VARS}@view-transition{{navigation:none}}</style>{APP_CSS_TAG}</head><body><main class="wrap">
<a class="view" href="/">← Back to the site</a>
<div class="hrow" style="margin-top:14px"><div><h1>Settings</h1>
<div class="sub">Changes apply from the next hourly sync.</div></div></div>
{note}
<div class="card sblock" style="margin-top:22px">
<h2 class="stitle">PSA accounts</h2>
<div class="sbar">{"".join(achips)}{"" if only else add_btn}</div>
</div>
<div class="card sblock">
<h2 class="stitle">Verification code</h2>
{obar}
{"".join(opanes)}
</div>
<div class="card sblock">
<h2 class="stitle">Discord webhook</h2>
{wbar}
{"".join(wpanes)}
</div>
{pwpanel}
<div class="card sblock">
<h2 class="stitle">Site password</h2>
<div class="meta">what visitors type to enter the site</div>
{sbar2}
{"".join(spanes)}
</div>
<div class="smodal" id="amodal" role="dialog" aria-modal="true" aria-labelledby="amtitle">
<div class="card sblock">
<button type="button" class="sclose" aria-label="Close">{ICON_X}</button>
<h2 class="stitle" id="amtitle"></h2>
<form method="POST" action="/settings/account" class="srow" style="margin-top:16px">
<input type="hidden" name="acct" value="" class="amacct"><input type="hidden" name="action" value="psa_pw">
<input name="value" type="password" placeholder="New PSA password"
 aria-label="New PSA password" autocomplete="new-password">
<button type="submit" class="fillbtn sbtn">Save</button></form>
<div class="sdanger"><form method="POST" action="/settings/account"
 onsubmit="return confirm('Unlink this account? The site keeps showing its last known data; syncs stop until you save a new PSA password.')">
<input type="hidden" name="acct" value="" class="amacct"><input type="hidden" name="action" value="unlink">
<button type="submit" class="sbtn sdel">Unlink account</button></form></div>
</div></div>
<div class="smodal" id="addmodal" role="dialog" aria-modal="true" aria-labelledby="addtitle">
<div class="card sblock">
<button type="button" class="sclose" aria-label="Close">{ICON_X}</button>
<h2 class="stitle" id="addtitle">Add PSA account</h2>
<div class="meta">Every account here shares this site’s name, logo, accent and web address.</div>
<form method="POST" action="/settings/add" class="sform">
<input name="psa_email" type="email" placeholder="PSA email"
 aria-label="PSA email" autocomplete="off">
<input name="psa_pw" type="password" placeholder="PSA password"
 aria-label="PSA password" autocomplete="new-password">
<button type="submit" class="fillbtn">Add</button>
</form></div></div>
<script>
(function(){{
  function close(m){{m.classList.remove('on');}}
  document.querySelectorAll('.smodal').forEach(function(m){{
    m.addEventListener('click',function(e){{if(e.target===m)close(m);}});
    var x=m.querySelector('.sclose');
    if(x)x.addEventListener('click',function(){{close(m);}});
  }});
  document.addEventListener('keydown',function(e){{
    if(e.key==='Escape')document.querySelectorAll('.smodal.on').forEach(close);
  }});
  var am=document.getElementById('amodal');
  document.querySelectorAll('.schip[data-acct]').forEach(function(b){{
    b.addEventListener('click',function(){{
      document.getElementById('amtitle').textContent=b.textContent.trim();
      am.querySelectorAll('.amacct').forEach(function(x){{x.value=b.dataset.acct;}});
      am.classList.add('on');
      // focus after the sheet is visible - a hidden field can't take focus
      var f=am.querySelector('input[name=value]');
      if(f){{f.value='';requestAnimationFrame(function(){{f.focus();}});}}
    }});
  }});
  var addb=document.getElementById('saddbtn');  // absent when the page is scoped
  if(addb)addb.addEventListener('click',function(){{
    var m=document.getElementById('addmodal');
    m.classList.add('on');
    // focus after the sheet is visible - a hidden field can't take focus
    var f=m.querySelector('input[name=psa_email]');
    if(f)requestAnimationFrame(function(){{f.focus();}});
  }});
  document.querySelectorAll('.schip[data-group]').forEach(function(b){{
    b.addEventListener('click',function(){{
      var g=b.dataset.group;
      document.querySelectorAll('.schip[data-group="'+g+'"]').forEach(function(x){{x.classList.toggle('on',x===b);}});
      document.querySelectorAll('.spane.sg-'+g).forEach(function(p){{
        p.style.display=(p.id===b.dataset.pane)?'':'none';}});
    }});
  }});
}})();
</script>
</main>{APP_JS_TAG}</body></html>"""

GEAR_HTML = ('<nav id="sitectl" aria-label="Site controls">'
             '<a id="gearbtn" href="/settings" title="Settings" aria-label="Settings">'
             '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
             'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
             '<circle cx="12" cy="12" r="3.2"/>'
             '<path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06'
             'a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1-1.55 '
             '1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 '
             '1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09a1.7 1.7 0 0 0 1.55-1 1.7 1.7 0 0 0-.34-1.87'
             'l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34 1.7 1.7 0 0 0 1-1.55V3'
             'a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.87-.34l.06-.06'
             'a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87 1.7 1.7 0 0 0 1.55 1H21'
             'a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.55 1z"/></svg></a></nav>')

# Store mode vs personal mode (PSA_SETTINGS_GEAR, default 1 = store):
# STORE - the site-password holder IS the admin, so admin sessions get the
#   gear AND open /settings directly, no second password (customers never do).
# PERSONAL (=0, the server) - password holders are friends: no gear, and /settings
#   always demands the separate settings password (typed there or at the gate).
SETTINGS_GEAR = os.environ.get("PSA_SETTINGS_GEAR", "1") not in ("0", "false", "no")

def gear_html(customer=False):
    """Settings gear beside the theme toggle - store-mode admin sessions only."""
    return "" if (customer or not SETTINGS_GEAR) else GEAR_HTML

# ---------- first-run setup ----------
# A fresh instance (accounts/ empty) serves a one-time setup form instead of the
# gate: site password + PSA login -> accounts/<id>/account.env + first scan kick.
# Once an account.env exists the form is the owner's retry (session required),
# and it is gone for good once the instance has connected (a PSA_COOKIE lands
# or subs exist), latched in accounts/.setup-done.

_SETUP_CLOSED = False
SETUP_MARKER = os.path.join(ACCOUNTS_DIR, ".setup-done")

def _close_setup():
    """Latch setup shut in process and on disk. The marker is what survives a
    restart: an account.env that stops parsing must never look like a fresh
    instance and reopen the public form."""
    global _SETUP_CLOSED
    _SETUP_CLOSED = True
    try:
        open(SETUP_MARKER, "a").close()
    except OSError:
        pass
    return False, None

def setup_state():
    """(setup_allowed, existing_account_or_None). Open to anyone only on a truly
    fresh instance: no marker and no account.env on disk. Once an account.env
    exists the form is retry-only and the routes gate it behind a session.
    Setup closes for good once the instance has connected - remember that in
    process so steady-state requests skip the env/db checks entirely."""
    global _SETUP_CLOSED
    if _SETUP_CLOSED:
        return False, None
    if os.path.exists(SETUP_MARKER):
        _SETUP_CLOSED = True
        return False, None
    try:
        dirs = sorted(os.listdir(ACCOUNTS_DIR))
    except OSError:
        dirs = []
    envs = [os.path.join(ACCOUNTS_DIR, d, "account.env") for d in dirs
            if re.fullmatch(r"[a-z0-9-]+", d)
            and os.path.exists(os.path.join(ACCOUNTS_DIR, d, "account.env"))]
    if not envs:
        return True, None
    if len(envs) > 1:
        return _close_setup()
    accts = load_accounts()
    if len(accts) != 1:  # an account.env that won't parse is not a fresh instance
        return False, None
    a = next(iter(accts.values()))
    env = read_env_file(envs[0])
    if env.get("PSA_COOKIE"):
        return _close_setup()
    try:
        conn = _ro_conn(a)
        n = conn.execute("SELECT COUNT(*) FROM subs").fetchone()[0]
        conn.close()
    except sqlite3.Error:
        n = 0
    if n:
        return _close_setup()
    return True, a

def write_account_env(acct_id, label, site_pw, psa_email, psa_pw):
    base = os.path.join(ACCOUNTS_DIR, acct_id)
    os.makedirs(base, exist_ok=True)
    q = shlex.quote  # real shell quoting - apostrophes in passwords survive intact
    lines = [f"LABEL={q(label)}", f"SITE_PASSWORD={q(site_pw)}",
             f"PSA_LOGIN_EMAIL={q(psa_email)}", f"PSA_LOGIN_PW={q(psa_pw)}", "PSA_COOKIE=''"]
    into = os.environ.get("PSA_MERGE_INTO", "").strip()
    if into and into != acct_id:  # this site pools every PSA account into one dashboard
        lines.append(f"PSA_MERGE_INTO={q(into)}")
    body = "\n".join(lines) + "\n"
    fd = os.open(os.path.join(base, "account.env"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(body)

def start_first_scan():
    """Fire login+scan without blocking; harmless where systemd is absent."""
    try:
        subprocess.Popen(["systemctl", "start", "--no-block", "psa-scan.service"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def scan_active():
    try:
        r = subprocess.run(["systemctl", "is-active", "psa-scan.service"],
                           capture_output=True, text=True, timeout=3)
        return r.stdout.strip() in ("active", "activating")
    except Exception:
        return False

def first_sync_note(a):
    """Status line under the empty dashboard until the first PSA sync lands."""
    env = read_env_file(os.path.join(ACCOUNTS_DIR, a["id"], "account.env"))
    if env.get("PSA_COOKIE"):
        return ""
    if scan_active():
        return "First sync with PSA is running. Reload in a minute or two."
    return ('Waiting for the first PSA sync (runs within the hour, or start it now with '
            '<span class="mono">systemctl start psa-scan</span>). Wrong PSA login? '
            '<a href="/setup">Re-enter it</a>.')

def setup_page(error="", label="", psa_email=""):
    desc = ' aria-describedby="err"' if error else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(SITE_TITLE)} · Setup</title>
{HEAD_HTML}
<style>{THEME_VARS}</style>{APP_CSS_TAG}</head><body><main class="wrap"><div class="gate"><div class="gbox">
{logo_tag()}<h1>{html.escape(SITE_TITLE)}</h1><div class="sub">First-time setup: connect your PSA account</div>
<form method="POST" action="/setup" class="setupform">
<input name="label" placeholder="Store or site name" aria-label="Store or site name"
 maxlength="40" value="{html.escape(label)}">
<input type="password" name="site_pw" placeholder="Choose a site password (for visitors)"
 aria-label="Choose a site password (for visitors)" autocomplete="new-password"{desc}>
<input type="email" name="psa_email" placeholder="PSA account email"
 aria-label="PSA account email" value="{html.escape(psa_email)}"{desc}>
<input type="password" name="psa_pw" placeholder="PSA account password"
 aria-label="PSA account password" autocomplete="new-password"{desc}>
<button type="submit" class="fillbtn">Connect PSA</button></form>
<div class="setupnote">The site password is what visitors type to enter. Your PSA login is stored
only on this server (chmod 600) and used by the scanner to sign in on your behalf. The first
sync runs within the hour.</div>
<div class="err" id="err" role="alert">{html.escape(error)}</div>
</div></div></main>{THEME_JS}</body></html>"""

def stage_dates(a, sub):
    """stage label -> 'Jul 20': when the sub ENTERED each stage, for the detail
    timeline. Arrived/Shipped use PSA's own dates; middle stages use the
    status_history transitions the scanner actually observed. A sub's initial
    import row (seen_at == first_seen) is discovery, not a transition - skipped."""
    d = {}
    try:
        conn = _ro_conn(a)
        rows = conn.execute("""SELECT status, seen_at FROM status_history
                               WHERE sub_number=? ORDER BY seen_at""",
                            (sub["sub_number"],)).fetchall()
        conn.close()
    except sqlite3.Error:
        rows = []
    for r in rows:
        if r["seen_at"] == (sub["first_seen"] or ""):
            continue
        if r["status"] in STAGES and r["status"] not in d:
            d[r["status"]] = short_date(r["seen_at"])
    if sub["arrived"]:
        d["Arrived"] = fmt_mdy(sub["arrived"])
    if sub["shipped"]:
        d["Shipped"] = fmt_mdy(sub["shipped"])
    return d

def timeline_html(status, dates=None, aside="", key=""):
    """Stage state as one text line (current stage, accent) above the 4px
    progress capsule. `dates` (stage -> 'Jul 20', from stage_dates) appends when
    the sub entered its current stage - detail pages only, so a dashboard row
    stays to a single line. `aside` (the row's one link) rides the bar's own
    row as a capsule pill at its right end.
    `key` is the sub number: FX_JS remembers each sub's stage per browser and
    only runs the bar's run-out for one that actually MOVED since the last
    visit, so the motion means "your cards advanced" and not "a page loaded".
    A status STAGES does not know prints "Status unknown" and no bar at all."""
    idx = stage_index(status)
    if idx is None:
        # PSA sent a step this build has never seen. It used to fall through to
        # stage 1 of 8, which read as "Arrived" for a sub that could be anywhere.
        return f'<div class="stage nobar"><span>Status unknown</span>{aside}</div>'
    pct = 100.0 * (idx + 1) / len(STAGES)
    line = f'<b>{html.escape(STAGES[idx])}</b> · stage {idx + 1} of {len(STAGES)}'
    since = (dates or {}).get(STAGES[idx], "")
    if since:
        line += f' · since {html.escape(since)}'
    k = f' data-k="{html.escape(str(key))}" data-st="{idx}"' if key else ""
    # aside rides the far end of the stage line, worn as a quiet capsule pill
    # (owner calls 2026-08-08: a bar-row placement was tried and reverted same
    # day - "i like where it was before, but i also like that its a pill").
    # The bar below stays full width.
    return (f'<div class="stage"><span>{line}</span>{aside}</div>'
            f'<div class="bar"><i style="width:{pct:.1f}%"{k}></i></div>')

STRIP_MAX = 8   # tiles per filmstrip; the 8th becomes "+N" when there are more

def strip_html(s, fronts):
    """The row's contact sheet: the sub's first scans, in line_number order.
    `fronts` is this sub's imaged (front_thumb, name) list (see sub_fronts).
    Past STRIP_MAX the last tile becomes a "+N" chip into the detail page, so
    the strip is always one fixed-width run and never wraps. A sub with no
    imaged cards falls back to its own subs.thumb; with neither, no strip."""
    fronts = fronts or []
    if not fronts and s.get("thumb"):
        fronts = [(s["thumb"], "")]
    if not fronts:
        return ""
    more = len(fronts) - (STRIP_MAX - 1) if len(fronts) > STRIP_MAX else 0
    shown = fronts[:STRIP_MAX - 1] if more else fronts
    tiles = []
    for u, nm in shown:
        # tiles are 64-84 CSS px, so the stored thumbnail asset is the right
        # size; /small/ is the 380x636 scan and belongs on the grid, not here
        src = "/img?u=" + urllib.parse.quote(u)
        big = "/img?u=" + urllib.parse.quote(img_url(u, "large"))
        # every tile is a focusable link, so it needs a NAME: the card's
        # subject (same trim the grid tiles use), or a plain fallback
        alt = html.escape(split_name(smart_title(nm))[0] or "Card scan")
        # anchor href = the large scan, exactly like a .grid tile: LIGHTBOX_JS
        # reads the href, so strip tiles open the same zoom overlay
        tiles.append(f'<a href="{big}"><img loading="lazy" src="{src}" alt="{alt}"></a>')
    if more:
        # "+5" alone is not a name: say what the five are and where they live
        sn = html.escape(s["sub_number"])
        tiles.append(f'<a class="morechip" href="/sub/{sn}" '
                     f'aria-label="{more} more cards in submission #{sn}">'
                     f'+{more}</a>')
    return f'<div class="strip">{"".join(tiles)}</div>'

def card_html(s, archived=False, value=None, vcur="CAD", fronts=None):
    # The stepper already highlights the current stage, so the pill carries the
    # NEXT most useful fact instead: when the cards come back.
    # the pill carries the ETA (latest expected return date), so the footer no
    # longer repeats an "Expected return" line.
    # Archived rows carry NO status pill: every archived sub is finished and the
    # foot already says "Shipped <date> · tracking", while the extra pill under
    # the value made .pills taller than the header and bumped the filmstrip
    # ~20px out of the active rows' rhythm.
    pill = "" if archived else eta_pill(s)

    if s["status"] == "Shipped" and s["shipped"]:
        foot = f'Shipped {html.escape(fmt_mdy(s["shipped"]))}'
        if s["carrier"] and s["tracking"]:
            foot += f' · {tracking_html(s["carrier"], s["tracking"])}'
    else:
        # no foot for holds (the owner, 2026-09-09: the pill is enough) or
        # grades_ready (2026-08-08: "i dont need the grades ready tab")
        foot = ""

    strip = strip_html(s, fronts)
    sub = html.escape(s['sub_number'])
    ncards = s['card_count']
    # archiving is the operator's highest-frequency chore and it used to live
    # only on the detail page: four page loads per finished sub. A finished sub
    # is a SHIPPED one, so the control rides the foot line those rows already
    # print - no new band, no new grammar, and ARCH_JS is already bundled.
    act = ""
    # `or archived`: the detail page will archive a sub at ANY status, so an
    # in-flight sub archived by mistake had no way back from the dashboard
    if s["status"] == "Shipped" or archived:
        act = (f'<span class="footacts"><button class="archbtn" data-sub="{sub}" '
               f'data-on="{0 if archived else 1}">'
               f'{"Unarchive" if archived else "Archive"}</button></span>')
    archattr = ' data-arch="1" style="display:none"' if archived else ''
    # data-sub/svc/eta feed the client-side sort pills (SORT_JS)
    sortattr = (f' data-sub="{sub}" data-svc="{html.escape(s["service"])}"'
                f' data-eta="{html.escape(s["est_end"] or s["est_start"] or "")}"')
    led = (f'<div class="ledval">${value:,.0f}<span>{vcur} · estimated</span></div>') if value else ""
    foot_h = (f'<div class="foot"><span class="est">{foot}</span>{act}</div>'
              if (foot or act) else "")
    # role=listitem + the h2: every card_html row lands in the dashboard's
    # role=list #list, and the sub number is that row's heading. Zero visual
    # delta - the global reset zeroes h2 margins and .num supplies every type
    # value (17/650/-.012em/1.3), same as the person page's group heading.
    return f"""<div class="card{' arch' if archived else ''}{' hold' if s['on_hold'] else ''}" role="listitem" data-status="{html.escape(s['status'])}"{archattr}{sortattr}>
<div class="top"><div class="hd"><div><a class="numlink" href="/sub/{sub}"><h2 class="num">#{sub}</h2></a>
<div class="meta">{html.escape(s['service'])} · {ncards} card{"s" if ncards != 1 else ""}</div></div></div><div class="pills">{led}{pill}</div></div>
{strip}
{timeline_html(s['status'], aside=f'<a class="view" href="/sub/{sub}">View cards</a>', key=sub)}
{foot_h}</div>"""

def search_box(value="", owner="", ph=None):
    """Unified people+card search input with a live-preview dropdown (needs SEARCH_JS).
    With owner set, card results are scoped to that person (SEARCH_JS reads data-owner)."""
    if ph is None:
        ph = "Search names or cards…"
    icon = ('<svg class="sicon" width="14" height="14" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2.4" stroke-linecap="round">'
            '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.8-3.8"/></svg>')
    return (f'<div class="searchwrap">{icon}<input class="searchbar" id="q" type="search" '
            f'autocomplete="off" spellcheck="false" enterkeyhint="search" '
            f'placeholder="{html.escape(ph)}" '
            f'aria-label="{html.escape(ph)}" data-owner="{html.escape(owner)}" '
            f'role="combobox" aria-expanded="false" aria-autocomplete="list" '
            f'aria-controls="preview" '
            f'value="{html.escape(value)}">'
            f'<div class="preview" id="preview" role="listbox" '
            f'aria-label="Search suggestions"></div></div>')

SEARCH_JS = """<script>
(function(){
  var q=document.getElementById('q'), pv=document.getElementById('preview'), t;
  if(!q) return;
  var own=q.dataset.owner||'';
  var scope=own?('&owner='+encodeURIComponent(own)):'';
  // the preview is a combobox listbox: `rows` is the option list the arrow keys
  // walk, `ai` the active index (-1 = nothing active, Enter falls through to
  // the full search page). Every re-render drops the active row.
  var rows=[], ai=-1;
  function esc(s){var d=document.createElement('div');d.textContent=s==null?'':s;return d.innerHTML;}
  function act(n){
    var p=rows[ai];
    if(p){p.classList.remove('act');p.setAttribute('aria-selected','false');}
    ai=n;
    var r=rows[ai];
    if(r){
      r.classList.add('act'); r.setAttribute('aria-selected','true');
      r.scrollIntoView({block:'nearest'});
      q.setAttribute('aria-activedescendant',r.id);
    }else{
      q.removeAttribute('aria-activedescendant');
    }
  }
  function say(msg){ var l=document.getElementById('live');
    if(l){ l.textContent=''; setTimeout(function(){ l.textContent=msg; },30); } }
  function open(on){
    pv.classList.toggle('on',on);
    q.setAttribute('aria-expanded',on?'true':'false');
    if(!on) act(-1);
  }
  function render(data){
    var h='',n=0;
    if(data.names&&data.names.length){
      h+='<div class="pvsec" role="presentation">People</div>';
      data.names.forEach(function(nm){
        h+='<a class="pvrow" role="option" aria-selected="false" id="pvo'+(n++)+'" href="/cards?owner='+encodeURIComponent(nm)+'"><span class="pvtag">Person</span><span>'+esc(nm)+'</span></a>';
      });
    }
    if(data.cards&&data.cards.length){
      h+='<div class="pvsec" role="presentation">Cards</div>';
      data.cards.forEach(function(c){
        var img=c.img?'<img class="pvimg" src="'+c.img+'" alt="">':'';
        var sub=esc(c.cert?('#'+c.cert):('sub #'+c.sub))+(c.owner?(' · '+esc(c.owner)):'');
        h+='<a class="pvrow" role="option" aria-selected="false" id="pvo'+(n++)+'" href="/sub/'+encodeURIComponent(c.sub)+'">'+img+'<span>'+esc(c.name||'Card')+'<small>'+sub+'</small></span></a>';
      });
    }
    if(!h) h='<div class="pvempty">No matches</div>';
    ai=-1; q.removeAttribute('aria-activedescendant');
    pv.innerHTML=h;
    rows=[].slice.call(pv.querySelectorAll('.pvrow'));
    say(rows.length?rows.length+' suggestion'+(rows.length!==1?'s':''):'No matches');
    open(true);
  }
  function go(){
    clearTimeout(t);
    t=setTimeout(function(){
      if(!pv.classList.contains('on')){pv.innerHTML='<div class="pvempty">Searching…</div>';rows=[];ai=-1;open(true);}
      /* non-OK (the 429 rate limit included) closes the preview instead of
         rendering as a false "No matches" */
      fetch('/suggest?q='+encodeURIComponent(q.value.trim())+scope,{headers:{'X-Requested-With':'fetch'}})
        .then(function(r){if(!r.ok)throw 0;return r.json();}).then(render)
        .catch(function(){rows=[];open(false);});
    },110);
  }
  q.addEventListener('input',go);
  q.addEventListener('focus',go);
  q.addEventListener('keydown',function(e){
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){
      if(!pv.classList.contains('on')||!rows.length) return;
      e.preventDefault();
      var d=e.key==='ArrowDown'?1:-1, n=rows.length;
      act(ai<0 ? (d>0?0:n-1) : (ai+d+n)%n);
    }
    else if(e.key==='Enter'){
      e.preventDefault();
      if(rows[ai]){location.href=rows[ai].href;return;}
      location.href='/search?q='+encodeURIComponent(q.value.trim())+scope;
    }
    /* type=search clears itself on Escape, and that clear fires `input`,
       which reopens the preview - so the first press looked ignored */
    else if(e.key==='Escape'){e.preventDefault();clearTimeout(t);open(false);}
  });
  document.addEventListener('click',function(e){ if(!pv.contains(e.target)&&e.target!==q) open(false); });
})();
</script>"""

ARCH_JS = """<script>
(function(){
  function say(m){var l=document.getElementById('live');
    if(l){l.textContent='';setTimeout(function(){l.textContent=m;},30);}}
  function count(d){
    var p=document.getElementById('archtoggle');if(!p)return;
    var m=(p.getAttribute('aria-label')||'').match(/(\\d+)/);
    var v=Math.max(0,(m?parseInt(m[1],10):0)+d);
    p.setAttribute('aria-label','Archived \\u00b7 '+v);
    var n=p.querySelector('.archn'); if(n)n.textContent=' \\u00b7 '+v;
  }
  /* In place, no reload. Archiving is the operator's most frequent action and
     it was the only state change in the product with no undo, no spoken
     confirmation, and a full page reload that dumped him at the top of the
     list - while RENAMING A TAG, which is trivially redone, shipped a 6s undo
     chip. The reversibility budget was allocated backwards. */
  /* place() is deliberately NOT called by flip(): the row has to stay on
     screen while the Undo chip is up, because the chip lives inside it. The
     first build hid the row the instant it flipped, which took the undo with
     it - the offer was unreachable in exactly the case it existed for. So the
     row flips to its dimmed archived state, sits there for the undo window,
     and only then leaves the view it no longer belongs to. */
  function place(row){
    var lst=document.getElementById('list');
    var viewing=!!(lst&&lst.classList.contains('archview'));
    row.style.display=((row.dataset.arch==='1')===viewing)?'':'none';
  }
  function flip(row,b,on){
    row.dataset.arch=on?'1':'0';
    row.classList.toggle('arch',on);
    b.dataset.on=on?'0':'1';
    b.textContent=on?'Unarchive':'Archive';
    count(on?1:-1);
  }
  /* our own b.disabled=true drops keyboard focus to body, so hand it back:
     only when it fell there, and only if the element held it to begin with */
  function back(el,was){if(was&&document.activeElement===document.body)el.focus();}
  function post(sub,on,done){
    fetch('/archive',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body:'sub='+encodeURIComponent(sub)+'&on='+(on?'1':'0')})
     .then(function(r){done(r.ok);}).catch(function(){done(false);});
  }
  /* delegated, not bound per button: the dashboard's archived rows arrive
     after first paint (the Archived pill fetches them), so half these buttons
     do not exist when this runs */
  document.addEventListener('click',function(e){
    var b=e.target.closest?e.target.closest('.archbtn'):null;
    if(b){
      var label=b.textContent, on=b.dataset.on==='1', sub=b.dataset.sub;
      var row=b.closest?b.closest('.card[data-sub]'):null;
      var foc=document.activeElement===b;
      b.disabled=true;                 // button:disabled dims it - in-flight state
      post(sub,on,function(ok){
        b.disabled=false;
        if(!ok){
          b.textContent="Couldn’t "+label.toLowerCase()+" \\u00b7 retry";
          say("Couldn’t "+label.toLowerCase()+" submission "+sub);
          setTimeout(function(){b.textContent=label;},6000);
          back(b,foc);
          return;
        }
        /* the detail page's whole header reflects archived state, and the very
           first archive has no Archived pill to move the row into - both keep
           the reload */
        if(!row||!document.getElementById('archtoggle')){location.reload();return;}
        flip(row,b,on);
        say('Submission '+sub+(on?' archived':' unarchived'));
        var f=b.parentNode, old=f.querySelector('.undo');
        if(old)old.remove();
        var u=document.createElement('button');
        u.type='button'; u.className='undo'; u.textContent='Undo';
        f.insertBefore(u,b);
        /* when the window closes the row leaves the view, taking the button
           with it, so the Archived pill it went behind takes the focus */
        var t=setTimeout(function(){var uf=document.activeElement===u;
          u.remove(); place(row);
          back(row.style.display==='none'?document.getElementById('archtoggle'):b,uf);
        },6000);
        u.addEventListener('click',function(){
          var uf=document.activeElement===u;
          clearTimeout(t); u.remove(); b.disabled=true;
          post(sub,!on,function(ok2){
            b.disabled=false;
            if(ok2){flip(row,b,!on);
              say('Submission '+sub+(on?' restored':' archived again'));}
            else say("Couldn’t undo that");
            /* focus last: a failed undo leaves the row archived, so place()
               hides it and the button with it */
            place(row);
            back(row.style.display==='none'?document.getElementById('archtoggle'):b,uf);
          });
        });
        back(u,foc);   // the offer is keyboard reachable, not stranded
      });
    }
  });
})();
</script>"""

LIGHTBOX_JS = """<script>
(function(){
  var links=document.querySelectorAll('.grid a[href^="/img"],.strip a[href^="/img"]');
  if(!links.length) return;
  /* a real dialog: role/aria-modal, focus moves in on open and back out on
     close, Tab is held on the close orb (the only tabbable inside), and the
     SCAN ITSELF IS INERT - the reveal must survive being touched. The scrim
     and the orb close; Escape closes. */
  var lb=document.createElement('div'); lb.className='lb';
  lb.setAttribute('role','dialog'); lb.setAttribute('aria-modal','true');
  lb.setAttribute('aria-label','Enlarged scan'); lb.tabIndex=-1;
  lb.innerHTML='<img alt="">'
    +'<button type="button" class="lbx" aria-label="Close">__XICON__</button>';
  document.body.appendChild(lb);
  var im=lb.querySelector('img'), x=lb.querySelector('.lbx'), clr=null, opener=null;
  links.forEach(function(a){
    a.addEventListener('click', function(e){
      e.preventDefault();
      var t=a.querySelector('img');
      im.alt=(t&&t.alt)?t.alt:'Card scan';
      clearTimeout(clr);
      im.src=a.getAttribute('href');
      opener=a;
      lb.classList.add('open');
      document.body.style.overflow='hidden';  // the page behind must not scroll
      lb.focus();
    });
  });
  function close(){
    if(!lb.classList.contains('open'))return;
    lb.classList.remove('open');
    document.body.style.overflow='';
    clearTimeout(clr);
    clr=setTimeout(function(){ if(!lb.classList.contains('open')) im.src=''; },220);
    if(opener&&document.contains(opener))opener.focus();
    opener=null;
  }
  lb.addEventListener('click', function(e){ if(e.target!==im) close(); });
  x.addEventListener('click', function(e){ e.stopPropagation(); close(); });
  lb.addEventListener('keydown', function(e){
    if(e.key==='Tab'){ e.preventDefault(); x.focus(); }  // one tabbable: hold it
  });
  document.addEventListener('keydown', function(e){ if(e.key==='Escape') close(); });
})();
</script>""".replace("__XICON__", ICON_X)

OWNER_JS = """
<script>
var coarse=window.matchMedia&&matchMedia('(pointer:coarse)').matches;
function _say(msg){ var l=document.getElementById('live');
  if(l){ l.textContent=''; setTimeout(function(){ l.textContent=msg; },30); } }
document.querySelectorAll('.own').forEach(function(i){
  var prev=i.value, nav=null, row=i.parentNode;
  function chip(cls,label,onclick,ttl){
    var s=row.nextElementSibling;          // one chip at a time
    if(s&&s.classList.contains('undo')) s.remove();
    var u=document.createElement('button');
    u.type='button'; u.className=cls; u.textContent=label;
    row.insertAdjacentElement('afterend', u);
    var t=ttl?setTimeout(function(){u.remove()},ttl):null;
    u.addEventListener('click', function(){ if(t)clearTimeout(t); u.remove(); onclick(); });
    return u;
  }
  function fail(val,old){
    i.classList.add('errsave'); setTimeout(function(){i.classList.remove('errsave')},1200);
    _say("Couldn’t save the owner tag");
    /* a failed save must say so in words and offer the retry - the red border
       flash alone was invisible to a screen reader and easy to miss at speed */
    chip('undo uerr','Couldn’t save \\u00b7 Retry',function(){ save(val,old); });
  }
  function relabel(v){
    // the name lives in the label now, so a rename has to move it there too
    i.title = v?('Owner: '+v+'. Click or press Enter to open their cards, '
                 +'click again or type to rename.'):'';
    i.setAttribute('aria-label', v?i.title:'Add owner name');
  }
  function save(val,old){
    post(val, function(ok){
      if(!ok){ fail(val,old); return; }
      prev=val; relabel(val);
      i.classList.add('saved'); setTimeout(function(){i.classList.remove('saved')},1600);
      _say('Owner saved');
      chip('undo','Saved \\u00b7 Undo',function(){
        post(old, function(ok2){
          if(!ok2){ fail(old,val); return; }
          i.value=old; prev=old; relabel(old);
          i.classList.add('saved'); setTimeout(function(){i.classList.remove('saved')},900);
          _say('Owner restored');
        });
      },6000);
    });
  }
  function post(val,done){
    fetch('/owner', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body:'cert_id='+encodeURIComponent(i.dataset.cert)+'&owner='+encodeURIComponent(val)})
     .then(function(r){ done(r.ok); }).catch(function(){ done(false); });
  }
  function visit(){
    // already on this person's page? a click shouldn't reload it
    if(location.pathname==='/cards'
       && (new URLSearchParams(location.search).get('owner')||'')===i.value) return;
    location.href='/cards?owner='+encodeURIComponent(i.value);
  }
  function edit(){
    if(nav){ clearTimeout(nav); nav=null; }
    i.readOnly=false; i.focus(); i.select();
  }
  // readonly tag = a link to the person: one click visits (after a beat, in
  // case a second click follows), a quick second click switches to editing.
  // Untagged fields have nowhere to go, so a single click edits immediately.
  i.addEventListener('click', function(){
    if(!i.readOnly) return;                        // already editing - caret clicks
    if(nav){ clearTimeout(nav); nav=null; edit(); return; }
    if(!i.value){ edit(); return; }
    if(i.selectionStart!==i.selectionEnd) return;  // copying the name, not navigating
    if(coarse){ visit(); return; }                 // the pencil edits - taps go straight through
    nav=setTimeout(function(){ nav=null; visit(); },280);
  });
  // iOS focuses the input on the synthesized mousedown, and focus on a sub-16px
  // field zooms the page - kill the focus, the click (and visit()) still fires.
  i.addEventListener('mousedown', function(e){ if(coarse&&i.readOnly) e.preventDefault(); });
  var eb=row.querySelector('.ownedit');
  if(eb) eb.addEventListener('click', edit);
  i.addEventListener('focus', function(){ prev=i.value; });
  i.addEventListener('blur', function(){
    i.readOnly=true;
    if(i.value===prev) return;             // nothing changed - no POST
    save(i.value, prev);
  });
  i.addEventListener('keydown', function(e){
    if(i.readOnly){
      /* keyboard route to the person page: Enter on a FILLED readonly tag
         visits, mirroring the click. The "Enter saves, never navigates"
         ruling governs the editing state, which is unchanged below. */
      if(e.key==='Enter'&&i.value){ e.preventDefault(); visit(); return; }
      if(e.key.length===1&&!e.metaKey&&!e.ctrlKey&&!e.altKey){  // typing starts an edit
        if(nav){ clearTimeout(nav); nav=null; }
        i.readOnly=false;
      }
      return;
    }
    if(e.key==='Enter') i.blur();
    else if(e.key==='Escape'){ i.value=prev; i.blur(); }  // revert before saving
  });
});
</script>"""

# top back-link: with same-origin history it steps back one page (person page,
# search, dashboard - wherever you came from); direct entries and new tabs
# fall through to the href. Modified clicks (new-tab etc.) are left alone.
BACK_JS = """
<script>
(function(){
  var b=document.getElementById('backlk'); if(!b) return;
  b.addEventListener('click', function(e){
    if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey) return;
    if(!document.referrer||history.length<2) return;
    try{ if(new URL(document.referrer).origin!==location.origin) return; }catch(_){ return; }
    e.preventDefault(); history.back();
  });
})();
</script>"""

# page effects: swap the loading sweep off images once loaded, and track the
# cursor per card so the spotlight border knows where to glow
FX_JS = """<script>
/* self-refresh so open tabs stay current - at a RANDOM :12-:17 past each hour
   (never the same moment twice, never in the scan's :05-:10 window, and tabs
   don't stampede together); skipped while someone is typing or the lightbox
   is open */
(function(){
  function arm(){
    var n=new Date(),off=(12*60+Math.random()*300)*1000,
        ms=((60-n.getMinutes())*60-n.getSeconds())*1000+off;
    setTimeout(function(){
      var el=document.activeElement;
      var typing=el&&(el.tagName==='INPUT'||el.tagName==='TEXTAREA')&&el.value;
      /* Reload ONLY a tab nobody is looking at. The old guard reloaded a
         VISIBLE page as long as you weren't typing - so it yanked the page out
         from under someone mid-read - and reloading a hidden tab used to burn
         the stage-bar signal too (the run-out now waits for visibility, see
         the stage block below). A visible tab just re-arms for the next hour. */
      if(document.hidden&&!typing){location.reload();}else{arm();}
    },ms);
  }
  arm();
})();
/* .ld on the img keeps the existing mechanism; .ld on its ANCHOR is what kills
   the sweep overlay (see .grid a.ld::after). Cached images report .complete
   here synchronously - this script runs after the grid markup - so a warm tile
   never flashes the sweep. */
document.querySelectorAll('.grid img,.strip img').forEach(function(m){
  var done=function(){
    m.classList.add('ld');
    var p=m.parentNode;
    if(p&&p.tagName==='A'){p.classList.add('ld');p.classList.remove('ldg');}
  };
  /* a scan that never arrives is swapped for the SAME placeholder a card with
     no scan renders, so the tile keeps its 1.72/2.4 box and the grid rhythm
     holds instead of collapsing around a broken image. Replacing the anchor
     takes the lightbox listener with it, so a dead tile cannot open an empty
     reveal. A broken image reports .complete with naturalWidth 0, so the
     synchronous path has to tell the two apart. Only a tile inside .gc is
     swapped: the filmstrip chip is a different box and keeps its own fill. */
  var fail=function(){
    var p=m.parentNode,t=(p&&p.tagName==='A')?p:m;
    if(!t.parentNode||!t.parentNode.classList.contains('gc')){done();return;}
    var d=document.createElement('div');
    d.className='ph'; d.textContent='No image yet';
    t.parentNode.replaceChild(d,t);
  };
  if(m.complete){if(m.naturalWidth)done();else fail();}
  else{m.addEventListener('load',done);m.addEventListener('error',fail);}
});
/* the loading sweep starts only when a still-loading tile approaches the
   viewport (.ldg) - below-the-fold lazy tiles never load, so an always-on
   sweep would tick forever. Without IntersectionObserver, sweep everything
   (the pre-existing behavior). */
(function(){
  var scans=document.querySelectorAll('.grid a[href^="/img"]:not(.ld)');
  if(!scans.length)return;
  if(!window.IntersectionObserver){
    scans.forEach(function(a){a.classList.add('ldg');});
    return;
  }
  var io=new IntersectionObserver(function(es){
    es.forEach(function(e){
      if(!e.isIntersecting)return;
      var img=e.target.querySelector('img');
      if(img&&!img.complete)e.target.classList.add('ldg');
      io.unobserve(e.target);
    });
  },{rootMargin:'200px'});
  scans.forEach(function(a){io.observe(a);});
})();
/* the stage bar runs out: the bar is knocked back to 0, then released to the
   width the server rendered, delayed onto the same .04s row-settle stagger so
   it lands with its row instead of after it.
   It runs ONLY for a sub whose stage actually CHANGED since this browser last
   saw it (psa_stage remembers sub -> stage index). Replaying it on every
   render - including the silent hourly reload - spent the product's one
   earned motion on "a page loaded" instead of "your cards moved", and a
   celebration that fires 40x a week for a thing that happens twice a month is
   ambient, not earned. First sight of a sub never animates: no baseline, no
   claim. Reduced motion returns early, so the served width is never touched
   and there is no 0-width frame; bars that didn't move render the same way. */
(function(){
  var bars=[].slice.call(document.querySelectorAll('.bar i[data-k]'));
  if(!bars.length)return;
  var seen={},store=1;
  try{seen=JSON.parse(localStorage.getItem('psa_stage')||'{}')||{};}catch(e){store=0;}
  var reduce=0;
  try{reduce=matchMedia('(prefers-reduced-motion:reduce)').matches;}catch(e){}
  var stagger=0;
  /* A bar's stage is recorded as SEEN only once it has actually been on screen
     with the tab visible. Committing every bar at render burned the signal
     twice over: an hourly reload of a hidden tab played the run-out to an
     empty room and marked everything current, and a sub thirty rows down could
     advance, never be scrolled to, and never animate again - with nothing else
     on the row to say it moved. The served width is always the truth, so a bar
     that hasn't animated yet has never claimed anything false. */
  function commit(list){
    var run=[];
    list.forEach(function(b){
      if(b.dataset.seen)return;
      b.dataset.seen='1';
      var k=b.dataset.k;
      if(seen[k]!==undefined&&seen[k]!==b.dataset.st&&!reduce&&b.style.width&&!b.dataset.fx){
        b.dataset.fx='1'; run.push([b,b.style.width]);
      }
      seen[k]=b.dataset.st;
    });
    if(run.length){
      run.forEach(function(p){
        p[0].style.transitionDelay=Math.min(stagger++,7)*40+'ms';
        p[0].style.width='0%';
      });
      void document.body.offsetWidth;    // commit the 0 so the width transition fires
      run.forEach(function(p){p[0].style.width=p[1];});
    }
    if(store&&list.length){try{localStorage.setItem('psa_stage',JSON.stringify(seen));}catch(e){}}
  }
  function start(){
    if(!window.IntersectionObserver){commit(bars);return;}
    var io=new IntersectionObserver(function(es){
      var vis=[];
      es.forEach(function(e){
        if(!e.isIntersecting)return;
        io.unobserve(e.target); vis.push(e.target);
      });
      if(vis.length)commit(vis);
    },{threshold:0});
    bars.forEach(function(b){io.observe(b);});
  }
  if(document.visibilityState==='hidden'){
    document.addEventListener('visibilitychange',function h(){
      if(document.visibilityState!=='hidden'){
        document.removeEventListener('visibilitychange',h); start();
      }
    });
  }else{start();}
})();
/* mobile filter capsule and every filmstrip: their scrollbars are hidden, so
   nothing would say there is more past the edge. Flag which side still has
   content (.sl/.sr) and let the CSS shade or fade that edge; a scroller that
   fits gets neither class, and each class drops the moment you reach that end. */
/* rAF-batches a layout-reading handler so scroll/resize never run a forced
   read->write cycle more than once a frame */
function _raf(fn){var p=0;return function(){if(p)return;p=1;requestAnimationFrame(function(){p=0;fn();});};}
(function(){
  document.querySelectorAll('.filters,.strip').forEach(function(f){
    function cue(){
      var max=f.scrollWidth-f.clientWidth;
      f.classList.toggle('sl',max>1&&f.scrollLeft>1);
      f.classList.toggle('sr',max>1&&f.scrollLeft<max-1);
    }
    var cueR=_raf(cue);
    f.addEventListener('scroll',cueR,{passive:true});
    addEventListener('resize',cueR);
    cue();
  });
})();
/* the corner orbs step aside mid scroll: .scrolling on <html> for 150ms after
   every scroll event is what the touch rule hangs off (see #gearbtn's media
   block). One passive listener, no layout read, so it costs nothing. */
(function(){
  var d=document.documentElement,t;
  addEventListener('scroll',function(){
    d.classList.add('scrolling');
    clearTimeout(t);
    t=setTimeout(function(){d.classList.remove('scrolling');},150);
  },{passive:true});
})();
/* scroll-edge elevation. A sticky bar that casts a full shadow while sitting
   at the top of an unscrolled page is claiming a depth it hasn't got. A 1px
   sentinel is dropped in just above the bar; while it is still on screen the
   bar sits nearly flush, and the moment it passes out of view - which is the
   moment content starts sliding underneath - .raised lifts it.
   rootMargin 6px is the bar's own sticky offset (10px) minus the sentinel box
   (1px + the 16px margin that follows it), so the class flips on the exact
   frame the bar goes sticky. Pages with no toolbar simply return. */
(function(){
  var tb=document.querySelector('.toolbar');
  if(!tb||!window.IntersectionObserver)return;
  var s=document.createElement('div');
  s.className='tbsentinel';
  s.setAttribute('aria-hidden','true');
  tb.parentNode.insertBefore(s,tb);
  new IntersectionObserver(function(e){
    tb.classList.toggle('raised',!e[0].isIntersecting);
  },{rootMargin:'6px 0px 0px 0px',threshold:0}).observe(s);
})();
/* the masthead CONDENSES on a phone: the sticky offset goes negative by exactly
   the height of the brand row, so .tbtop scrolls away with the page and the
   search capsule alone stays pinned - the same compact bar every other page
   carries. Done with `top` and not by hiding .tbtop, because changing a sticky
   element's HEIGHT mid-scroll reflows everything under it and the page jumps
   under your thumb. Measured rather than hardcoded: the brand row's height
   depends on the label wrapping. 10 = the bar's resting sticky offset. Only the
   dashboard has a <header class="toolbar">; the .tbq bars are divs and already
   compact, so they're never touched. Short viewports condense too: a landscape
   phone is WIDER than 640px and only ~390px tall, so the width test alone left
   the masthead holding a third of the screen. */
(function(){
  var tb=document.querySelector('header.toolbar'),tt=tb&&tb.querySelector('.tbtop');
  if(!tb||!tt||!window.matchMedia)return;
  var mq=matchMedia('(max-width:640px),(max-height:500px)');
  function settop(){
    if(!mq.matches){tb.style.top='';return;}
    var cs=getComputedStyle(tb),g=parseFloat(cs.rowGap);
    if(!(g>=0))g=parseFloat(cs.gap)||10;   // 'normal' parses to NaN in older engines
    tb.style.top=(10-(tt.offsetHeight+g+parseFloat(cs.paddingTop)))+'px';
  }
  settop();
  addEventListener('resize',_raf(settop));
  if(mq.addEventListener)mq.addEventListener('change',settop);
})();
/* sheets are dialogs: while one is open, Tab must not walk out the back of it,
   and closing must hand focus back to whatever opened it. Each sheet's own
   open/close code just toggles .on, so this watches that class instead of
   wiring into three different handlers. */
(function(){
  var sheets=document.querySelectorAll('.smodal');
  if(!sheets.length)return;
  var SEL='a[href],button:not([disabled]),input:not([type=hidden]):not([disabled]),'+
          'select,textarea,[tabindex]:not([tabindex="-1"])';
  var opener=null;
  function tabbable(m){
    return [].slice.call(m.querySelectorAll(SEL)).filter(function(el){
      return el.offsetWidth||el.offsetHeight||el.getClientRects().length;});
  }
  document.addEventListener('keydown',function(e){
    if(e.key!=='Tab')return;
    var m=document.querySelector('.smodal.on');
    if(!m)return;
    var f=tabbable(m);
    if(!f.length){e.preventDefault();return;}
    var first=f[0],last=f[f.length-1],a=document.activeElement;
    if(!m.contains(a)){e.preventDefault();(e.shiftKey?last:first).focus();}
    else if(e.shiftKey&&a===first){e.preventDefault();last.focus();}
    else if(!e.shiftKey&&a===last){e.preventDefault();first.focus();}
  },true);
  if(!window.MutationObserver)return;
  var mo=new MutationObserver(function(recs){
    recs.forEach(function(r){
      var m=r.target,on=m.classList.contains('on');
      if(on&&!m.dataset.mopen){
        m.dataset.mopen='1';
        // runs as a microtask, before the sheet's own rAF focus call
        opener=document.activeElement;
      }else if(!on&&m.dataset.mopen){
        delete m.dataset.mopen;
        if(opener&&opener.focus&&document.contains(opener))opener.focus();
        opener=null;
      }
    });
  });
  sheets.forEach(function(m){mo.observe(m,{attributes:true,attributeFilter:['class']});});
})();
// (no cursor-spotlight, no glow: this world's motion is the row settle, the
// stage bar running out, and overlays materializing. Hover lives in CSS alone.)
</script>"""


# person page: fold archived-sub cards behind a toggle below the active grid
SORT_JS = """<script>
(function(){
  var list=document.getElementById('list');
  var btns=document.querySelectorAll('.fsort');
  if(!list||!btns.length)return;
  // clicking the active pill again reverses it; only the sub pill flips its word
  // (Newest/Oldest) - the others keep their plain label in both directions
  var BASE={sub:'Newest',svc:'Order type',eta:'Return'};
  var REV={sub:'Oldest'};
  // re-clicking the active pill reverses the list but two of the three pills
  // keep the same label, so the flip is invisible to a screen reader. Say it.
  var SAID={sub:['Sorted newest first','Sorted oldest first'],
            svc:['Sorted by order type, A to Z','Sorted by order type, Z to A'],
            eta:['Sorted by return date, soonest first','Sorted by return date, latest first']};
  function subDesc(a,b){return parseInt(b.dataset.sub||'0',10)-parseInt(a.dataset.sub||'0',10);}
  function cmp(a,b,m,d){
    var r=0;
    if(m==='sub'){r=subDesc(a,b);return d?-r:r;}
    if(m==='svc'){
      var x=(a.dataset.svc||'').toLowerCase(),y=(b.dataset.svc||'').toLowerCase();
      r=x<y?-1:x>y?1:0; if(r)return d?-r:r;
    }else{
      var x=a.dataset.eta||'',y=b.dataset.eta||'';
      if(x&&!y)return -1; if(!x&&y)return 1;   // no return date: always last
      r=x<y?-1:x>y?1:0; if(r)return d?-r:r;
    }
    return subDesc(a,b);  // ties: newest sub first, both directions
  }
  function apply(m,d){
    var cards=[].slice.call(list.children).filter(function(c){return c.classList.contains('card')});
    var act=cards.filter(function(c){return c.dataset.arch!=='1'});
    var arc=cards.filter(function(c){return c.dataset.arch==='1'});
    var by=function(a,b){return cmp(a,b,m,d)};
    act.sort(by); arc.sort(by);
    act.concat(arc).forEach(function(c){list.appendChild(c)});
    btns.forEach(function(b){
      var on=b.dataset.sort===m;
      b.classList.toggle('on',on);
      b.setAttribute('aria-pressed',on?'true':'false');
      b.textContent=(on&&d&&REV[m])||BASE[b.dataset.sort];
    });
    cur=m; rev=d;
    try{localStorage.setItem('psa_sort',m+(d?':r':''))}catch(e){}
  }
  var cur='sub',rev=0;
  btns.forEach(function(b){b.addEventListener('click',function(){
    var m=b.dataset.sort,again=m===cur;
    apply(m, again?!rev:0);
    if(again)_say(SAID[m][rev?1:0]);
  })});
  var saved=null; try{saved=localStorage.getItem('psa_sort')}catch(e){}
  if(saved){
    var m=saved.split(':')[0], d=saved.indexOf(':r')>-1;
    if(BASE[m]&&(m!=='sub'||d))apply(m,d);
  }
  // the dashboard appends its archived rows after first paint, so it re-runs
  // the sort that is already showing over them
  list.psaSort=function(){apply(cur,rev);};
})();
</script>"""

ARCHFOLD_JS = """<script>
(function(){
  var af=document.getElementById('archtoggle'),ag=document.getElementById('archgrid');
  /* BOTH, not just af. Since every script ships in one bundle this also runs on
     the DASHBOARD, which has an #archtoggle (a view switch over #list) but no
     #archgrid - so this used to throw on `ag.style` at every click AND
     double-toggle the pill's .on class against the dashboard's own handler,
     leaving the pill reading unpressed while the archived view was open. */
  if(!af||!ag)return;
  af.addEventListener('click',function(){
    var on=af.classList.toggle('on');
    af.setAttribute('aria-expanded',on?'true':'false');
    ag.style.display=on?'':'none';
    /* an explicit behavior option overrides the CSS scroll-behavior:auto the
       reduced-motion block sets, so the gate has to live here too */
    if(on)ag.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth',block:'nearest'});
  });
})();
</script>"""

# ---------- cacheable chrome ----------
# The stylesheet and every page-independent script are byte-identical wherever
# they appear, but each response used to inline them under Cache-Control:
# no-store - dominating time-to-first-paint on the phones customers actually
# use. They are served at hashed immutable URLs instead (still stdlib, still
# single-file, zero build); only THEME_VARS (env-derived, 3KB) stays inline.
# Every script in the bundle self-guards with an early return / null check, so
# a page that lacks a script's target simply no-ops it. Pages without FX (the
# gate, setup, 404) keep their inline THEME_JS so their behavior is unchanged.
def _script_body(tagged):
    return tagged.replace("<script>", "").replace("</script>", "")

APP_JS = "\n".join(_script_body(s) for s in (
    FX_JS, SORT_JS, SEARCH_JS, OWNER_JS, ARCH_JS, ARCHFOLD_JS,
    BACK_JS, DISCORD_JS, LIGHTBOX_JS, THEME_JS))
_ASSET_V = hashlib.sha256((CSS + APP_JS).encode()).hexdigest()[:12]


def _bundle(text):
    """(raw bytes, gzipped bytes). Both bundles are immutable for the life of
    the process, so they are compressed here once instead of per request."""
    raw = text.encode()
    return raw, gzip.compress(raw, 6)


CSS_BYTES = _bundle(CSS)
APP_JS_BYTES = _bundle(APP_JS)
APP_CSS_TAG = f'<link rel="stylesheet" href="/app.css?v={_ASSET_V}">'
APP_JS_TAG = f'<script src="/app.js?v={_ASSET_V}"></script>'

_YEAR_TOK = re.compile(r"(19|20)\d\d")
_NUM_TOK = re.compile(r"[A-Za-z]{0,3}-?\d{1,4}[A-Za-z]?\*?", re.I)     # 075, 3, SV107, FP-007, 197b
_CARDNO_TOK = re.compile(r"[A-Za-z]{0,3}-?\d{3,4}[A-Za-z]?\*?", re.I)  # the padded form PSA prints

def split_name(name):
    """'2026 One Piece Promos 075 Monkey D. Luffy Tin Pack' ->
    ('Monkey D. Luffy Tin Pack', '2026 One Piece Promos · 075').

    PSA names read YEAR SET NUM SUBJECT/VARIANT, so the split point is the card
    number - the LAST number-ish token that isn't a year, because set names
    carry their own digits ('Championship 2024 ... 102 Gedatsu', '3rd
    Anniversary ... 3 Brothers Pack 053 Portgas D. Ace'). Padded 3-4 digit
    tokens win over bare ones so set copy like 'Cup-Top 64' can't masquerade as
    the number. Anything that doesn't parse renders whole: (name, "")."""
    toks = (name or "").split()
    if len(toks) < 4 or not _YEAR_TOK.fullmatch(toks[0]):
        return (name or "", "")
    # range: >=1 set word before the number, >=1 subject word after it
    cand = [i for i in range(2, len(toks) - 1)
            if _NUM_TOK.fullmatch(toks[i]) and not _YEAR_TOK.fullmatch(toks[i])]
    if not cand:
        return (name or "", "")
    padded = [i for i in cand if _CARDNO_TOK.fullmatch(toks[i])]
    i = (padded or cand)[-1]
    return (" ".join(toks[i + 1:]), f"{' '.join(toks[:i])} · {toks[i]}")

def card_tile(c, owners, show_sub=False, archived=False, service="", customer=False, statline="",
              value=None, vcur="CAD"):
    cid = html.escape(str(c["cert_id"]))
    is_prelim = str(c["cert_id"]).startswith("spec:")
    subject, setline = split_name(smart_title(c["name"] or ""))
    name = html.escape(subject)
    nmset = f'<div class="nmset">{html.escape(setline)}</div>' if setline else ""
    owner = html.escape(owners.get(str(c["cert_id"]), ""))
    # the grade is the news on this tile: plain text, PSA-label red, under the scan
    gtx = f'PSA {html.escape(c["grade"])}' if c.get("grade") else ""
    grade = f'<div class="gr">{gtx}</div>'
    if is_prelim:
        head = ('<div class="cn pre" title="No cert number until PSA grades it">'
                'Prelim</div>')
    else:
        head = f'<div class="cn">{html.escape(c["cert_no"] or c["cert_id"])}</div>'
    if c.get("front_thumb"):
        src = "/img?u=" + urllib.parse.quote(img_url(c["front_thumb"], "small"))
        big = "/img?u=" + urllib.parse.quote(img_url(c["front_thumb"], "large"))
        img = f'<a href="{big}"><img loading="lazy" src="{src}" alt="{name or "Card scan"}"></a>'  # opens in the lightbox
    else:
        img = '<div class="ph">No image yet</div>'
    if customer:
        # customers never link into submissions (those show other people's cards);
        # the chip carries this card's own status instead
        sub_link = f'<div class="sublink sublink-static">{html.escape(statline)}</div>' if statline else ""
    else:
        sub_link = (f'<a class="sublink" href="/sub/{html.escape(str(c["sub_number"]))}">Go to sub #{html.escape(str(c["sub_number"]))}</a>'
                    if show_sub else "")
    svc = f'<div class="svc">{html.escape(service)}</div>' if (show_sub and service) else ""
    # readonly until OWNER_JS unlocks it: one click opens the person's page,
    # a second click (or typing) switches the field into edit mode
    # ONE sentence, tooltip and accessibility tree alike: sighted and screen
    # reader users were being told two different things about the same control
    ownlbl = (f"Owner: {owner}. Click or press Enter to open their cards, "
              "click again or type to rename.") if owner else ""
    own_input = ("" if customer else
                 f'<div class="ownrow"><input class="own" data-cert="{cid}" value="{owner}" readonly'
                 + (f' title="{ownlbl}" aria-label="{ownlbl}"'
                    if owner else ' aria-label="Add owner name"')
                 + ' enterkeyhint="done" placeholder="+ owner name">'
                   '<button type="button" class="ownedit" aria-label="Edit owner tag">'
                   '<svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">'
                   '<path d="M11.1 2.2a1.6 1.6 0 0 1 2.3 0l.4.4a1.6 1.6 0 0 1 0 2.3L6.4 12.3l-3.1.8.8-3.1z" '
                   'fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>'
                   '</button></div>')
    val = (f'<div class="cval">${value:,.0f} <span>{vcur} · estimated</span></div>'
           if value is not None and not customer else "")
    return (f'<div class="gc{" arch" if archived else ""}">{img}{grade}{head}'
            f'<div class="nm">{name}</div>{nmset}'
            f'{val}{svc}{sub_link}'
            f'{own_input}'
            f'</div>')

def scan_stale_hours(a):
    """Hours since this account's last successful scan, or None when unknown.
    run_scan.sh rewrites accounts/<id>/.last_ok after every scan that returned 0,
    hourly, so its mtime is the fact. No marker (a box that has not scanned
    since) says nothing."""
    try:
        seen = os.stat(os.path.join(ACCOUNTS_DIR, a["id"], ".last_ok")).st_mtime
    except OSError:
        return None
    return (time.time() - seen) / 3600

def scan_error(a):
    """The one line whoever failed last wrote to accounts/<id>/.last_error, or "".
    psa_common.set_error writes it (psa_watch on a dead cookie or an unreachable
    PSA, psa_login on a failed sign-in) and run_scan.sh deletes it after a scan
    that returned 0, so it is this account's current cause and never an old one."""
    try:
        with open(os.path.join(ACCOUNTS_DIR, a["id"], ".last_error"),
                  encoding="utf-8", errors="replace") as f:
            return f.readline().strip()[:300]
    except OSError:
        return ""

def sync_dot(stale):
    """One dot and one word for the toolbar, from scan_stale_hours: the last scan
    that worked, not the newest submission change. Stale is the T24 banner's own
    6 hours, so the dot and the banner can never disagree."""
    if stale is None:
        return '<div class="sync"><i aria-hidden="true"></i>No sync yet</div>'
    if stale < .75:                       # scans run every 9 to 22 minutes (T101)
        cls, word = " live", "Live"
    elif stale < 6:
        mins = int(stale * 60)
        cls, word = "", f"{mins} min ago" if mins < 90 else f"{int(stale)} h ago"
    else:
        cls, word = " stale", "Stale"
    when = fmt_local(datetime.fromtimestamp(time.time() - stale * 3600,
                                            timezone.utc).isoformat())
    return (f'<div class="sync{cls}"><i aria-hidden="true"></i>{word}'
            f'<span class="vh">Last sync {html.escape(when)}</span></div>')

def dash_page(a, subs):
    arch = archived_set(a)
    active = [s for s in subs if s["sub_number"] not in arch]
    gone = [s for s in subs if s["sub_number"] in arch]
    # the page needs two numbers off the cards table, not the rows themselves:
    # the value totals are summed in sqlite, and the untagged count reads two
    # columns per card (owners live in the other db, so that one stays in Python)
    owners = owners_map(a)
    tot, vcur = sub_value_totals(a) if subs else ({}, "CAD")
    active_nums = {s["sub_number"] for s in active}
    untag = sum(1 for sub_number, cert_id in (card_owner_keys(a) if subs else [])
                if sub_number in active_nums and not owners.get(str(cert_id), ""))
    if subs:
        # ACTIVE ROWS ONLY. The archived ones used to ride along hidden with
        # display:none and were most of the page's bytes; the Archived pill
        # fetches them from /?arch=1 the first time it is switched on.
        fronts = sub_fronts(a)   # ONE query for every row's filmstrip
        body = "".join(card_html(s, value=tot.get(s["sub_number"]), vcur=vcur,
                                 fronts=fronts.get(s["sub_number"])) for s in active)
    else:
        note = first_sync_note(a)
        body = ('<div class="empty">No submissions yet. Cards appear here once PSA receives them.'
                + (f'<br><span style="font-size:12px">{note}</span>' if note else "")
                + '</div>')
    stale = scan_stale_hours(a)
    # the masthead lives IN the sticky glass toolbar: title, store, freshness,
    # sign-out and search travel together as the page's one piece of chrome
    # <header> because this one really is the page masthead; the .tbq bars on the
    # other pages stay <div> (they carry a search field, not a page header).
    # Every selector and the FX_JS query use the .toolbar class, so it's a swap.
    toolbar = (f'<header class="toolbar"><div class="tbtop">'
               f'<div class="brand">{logo_tag()}<div><h1>{html.escape(SITE_TITLE)}</h1>'
               f'<div class="sub">{html.escape(a["label"])}</div></div></div>'
               f'<div class="tbend">{sync_dot(stale)}'
               f'<a class="lgout" href="/logout" title="Sign out" aria-label="Sign out">{ICON_OUT}</a>'
               f'</div></div>{search_box()}</header>')
    hint = (f'<div class="hint" id="hint">👋 New here? Type your name in the search to find just your cards.'
            f'<button type="button" class="hintx" id="hintx" aria-label="Dismiss hint">{ICON_X}</button></div>')
    # unlinked account: keep serving everything, say why it stopped moving
    if a.get("unlinked"):
        hint = ('<div class="hint" role="status">This account is unlinked, showing its last '
                'known status from PSA. Syncs are off; save a new PSA password in settings '
                'to relink.</div>') + hint
    else:
        # several scans missed in a row means the PSA link is down, and the
        # statuses below are older than they look
        if stale is not None and stale >= 6:
            # "why" is the scripts' own line, not free text, but it carries an
            # exception string, so it is escaped like anything else (T105)
            why = scan_error(a)
            hint = ('<div class="hint" role="status">Not connecting to PSA since '
                    f'{int(stale)} hours ago'
                    + (f': {html.escape(why)}.' if why else '.')
                    + ' These statuses may be behind.</div>') + hint
    pills = []
    if subs:  # sort pills (SORT_JS reorders #list client-side; choice persists per browser)
        pills += ['<button type="button" class="f fsort on" data-sort="sub" aria-pressed="true">Newest</button>',
                  '<button type="button" class="f fsort" data-sort="svc" aria-pressed="false">Order type</button>',
                  '<button type="button" class="f fsort" data-sort="eta" aria-pressed="false">Return</button>']
    # role=group, not navigation: three sort toggles are not a navigation
    # landmark. Styled and queried by CLASS everywhere, so the role carries no
    # layout weight.
    filters = (f'<div class="filters" role="group" aria-label="Sort submissions">'
               f'{"".join(pills)}</div>') if pills else ""
    # the worklist link navigates away, so it is a row control beside Archived
    # and not a fourth seat in a capsule labelled "Sort submissions" whose
    # arithmetic assumes exactly three pills (see .filterrow).
    needlink = (f'<a class="f fsolo" href="/cards?owner=unassigned">'
                f'{untag} need{"s an owner" if untag == 1 else " owners"}</a>') if untag else ""
    # Archived is a BARE pill beside the sort segment, in the row's plain
    # .rowend box and in no capsule - .fsolo makes the button carry the glass
    # (see .filterrow). The id and classes are unchanged, so the toggle script
    # doesn't care (it only flips classes and aria-pressed, never textContent -
    # so .archn is safe). The count lives in its own span so the 640px block can
    # drop it and give the sort pills the room; aria-label keeps the full phrase.
    archpill = (f'<button type="button" class="f farch fsolo" '
               f'id="archtoggle" aria-pressed="false" aria-label="Archived · {len(gone)}">'
               f'Archived<span class="archn"> · {len(gone)}</span></button>') if gone else ""
    rowend = (f'<div class="rowend">{needlink}{archpill}</div>'
              if (needlink or archpill) else "")
    filterrow = (f'<div class="filterrow">{filters}{rowend}</div>'
                 if (filters or rowend) else "")
    # role=list only when the rows are really there: with no subs the one child
    # is the .empty placeholder, and a list of one non-listitem is a lie.
    listrole = ' role="list"' if subs else ''
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(SITE_TITLE)}</title>
{HEAD_HTML}
<style>{THEME_VARS}</style>{APP_CSS_TAG}</head><body><main class="wrap">
<a class="skip" href="#list">Skip to submissions</a>
{toolbar}
{hint}
{filterrow}
<div id="list" tabindex="-1"{listrole}>{body}</div>
<div class="vh" id="live" aria-live="polite"></div>
</main>
<script>
(function(){{var h=document.getElementById('hint'),seen=null;
 try{{seen=localStorage.getItem('psa_hint_seen');}}catch(e){{}}
 if(h&&seen){{h.style.display='none';}}
 var x=document.getElementById('hintx');
 if(x)x.addEventListener('click',function(){{h.style.display='none';
  try{{localStorage.setItem('psa_hint_seen','1');}}catch(e){{}}}});}})();
var af=document.getElementById('archtoggle');
if(af)af.addEventListener('click',function(){{
  var on=af.classList.toggle('on');
  af.setAttribute('aria-pressed',on?'true':'false');
  var lst=document.getElementById('list');
  if(lst)lst.classList.toggle('archview',on);
  // reads the pill, never the `on` above: show() also runs when the fetch
  // lands, and by then the pill may have been switched back off
  function show(){{var v=af.classList.contains('on');
   document.querySelectorAll('#list .card').forEach(function(c){{
    var a=c.dataset.arch==='1';
    c.style.display=(v?a:!a)?'':'none';
  }});}}
  // the archived rows are not in the first paint: fetch them once, here, and
  // put the pill back to off if that fetch fails (an empty list says nothing)
  if(on&&lst&&!af.dataset.got){{
    fetch('/?arch=1').then(function(r){{if(!r.ok)throw 0;return r.text();}})
     .then(function(h){{
       af.dataset.got='1';
       var d=document.createElement('div'); d.innerHTML=h;
       // a row archived in this session is already here, flipped in place
       [].slice.call(d.children).forEach(function(c){{
         if(!lst.querySelector('.card[data-sub="'+c.dataset.sub+'"]'))lst.appendChild(c);
       }});
       if(lst.psaSort)lst.psaSort();
       show();
     }}).catch(function(){{af.click();}});
  }}
  show();
}});
</script>{gear_html()}{APP_JS_TAG}</body></html>"""

def arch_rows(a, subs):
    """The dashboard's archived rows as bare HTML, served from /?arch=1 and
    appended to #list by the Archived pill on its first switch."""
    arch = archived_set(a)
    gone = [s for s in subs if s["sub_number"] in arch]
    if not gone:
        return ""
    tot, vcur = sub_value_totals(a)
    fronts = sub_fronts(a)
    return "".join(card_html(s, archived=True, value=tot.get(s["sub_number"]), vcur=vcur,
                             fronts=fronts.get(s["sub_number"])) for s in gone)

def eta_badge(s, extra=""):
    """Top-right ETA badge for the sub detail page: expected return window, or
    ship date + tracking once shipped. `extra` = additional lbl2/b lines
    (e.g. the sub's estimated value) appended inside the same block."""
    if s["status"] == "Shipped" and s["shipped"]:
        note = (f'<span class="estnote">{tracking_html(s["carrier"], s["tracking"])}</span>'
                if s["carrier"] and s["tracking"] else "")
        return f'<div class="synced">Shipped<b>{html.escape(fmt_mdy(s["shipped"]))}</b>{note}{extra}</div>'
    label, val, muted = eta_words(s)
    if not muted and s["est_end"] and s["est_start"] and s["est_end"] != s["est_start"]:
        d1, d2 = short_date(s["est_start"]), short_date(s["est_end"])
        if "," in d1 and d1[-6:] == d2[-6:]:  # one year for the pair, on the end
            d1 = d1.split(",")[0]
        val = f"{d1} to {d2}"
    if val == "ETA pending":
        val = "Pending"  # the badge already says "PSA ETA" on the label rung
    note = '<span class="estnote">grades ready</span>' if s["grades_ready"] else ""
    eta = f'{label}<b>{html.escape(val)}</b>'
    if s["on_hold"]:
        # the hold leads and the date stays: the one page you click THROUGH for
        # an explanation used to drop the return window entirely
        eta = (f'Status<b class="holdb">On hold</b>'
               f'<span class="lbl2">{label}</span><b>{html.escape(val)}</b>')
    return f'<div class="synced">{eta}{note}{extra}</div>'

def detail_page(a, sub):
    num = sub["sub_number"]
    archived = num in archived_set(a)
    cards = load_cards(a, num)
    owners = owners_map(a)
    vals, vas_of, vcur = load_values(a)
    vtotal = sum(vals.get(c["cert_no"] or "", 0) for c in cards)
    vextra = ""
    if vtotal:
        vmiss = sum(1 for c in cards if c.get("grade") and (c["cert_no"] or "") not in vals)
        vextra = (f'<span class="lbl2">Est. value</span><b>${vtotal:,.0f}{"+" if vmiss else ""} {vcur}</b>'
                  f'<span class="estnote">PSA estimates · as of {html.escape(vas_of)}</span>')
    if cards:
        # archived treatment on the sub's OWN page greys the scans only (.archdim);
        # the header already says Archived, so cert numbers/names/values stay legible
        gcls = "grid archdim" if archived else "grid"
        body = (f'<div class="{gcls}">'
                + "".join(card_tile(c, owners,
                                    value=vals.get(c["cert_no"] or ""), vcur=vcur) for c in cards)
                + "</div>")
    elif json.loads(sub["cert_ids"] or "[]"):
        body = '<div class="empty">Card images not synced yet. They appear after the next sync (once cards reach Research &amp; ID).</div>'
    else:
        body = '<div class="empty">No cards assigned yet. PSA lists them during Research &amp; ID.</div>'
    if archived:
        act = f'<button class="archbtn" data-sub="{html.escape(num)}" data-on="0">Unarchive</button>'
        tag = ' · <span style="color:var(--m1)">Archived</span>'
    else:
        act = f'<button class="archbtn" data-sub="{html.escape(num)}" data-on="1">Archive</button>'
        tag = ""
    nc = sub['card_count']
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>#{html.escape(num)}</title>
{HEAD_HTML}
<style>{THEME_VARS}</style>{APP_CSS_TAG}</head><body><main class="wrap">
<div class="foot" style="border:0;padding:0"><a class="view" id="backlk" href="/">← Back</a><span class="footacts">{act}</span></div>
<div class="hrow" style="margin-top:14px"><div><h1>#{html.escape(num)}</h1>
<div class="sub">{html.escape(sub['service'])} · {nc} card{"s" if nc != 1 else ""} · {html.escape(sub['status'])}{tag}</div></div>
{eta_badge(sub, vextra)}</div>
<div class="card tlcard">{timeline_html(sub['status'], stage_dates(a, sub), key=num)}</div>
{body}
<div class="vh" id="live" aria-live="polite"></div>
</main>{gear_html()}{APP_JS_TAG}</body></html>"""

def people_page(a, owner):
    """Admin person page (and the operator's `unassigned` worklist).
    Admin-only: customer sessions are routed to customer_page, never here."""
    owners = owners_map(a)
    arch = archived_set(a)
    # no owner in the query is the same request as owner=unassigned: the
    # operator worklist
    unassigned = owner.strip().lower() in ("", "unassigned")
    subs_by = {s["sub_number"]: s for s in load_subs(a)}
    if unassigned:  # operator worklist: untagged cards in active subs
        active_nums = {n for n in subs_by if n not in arch}
        cards = [c for c in load_all_cards(a)
                 if c["sub_number"] in active_nums and not owners.get(str(c["cert_id"]), "")]
        title, sub_line = "Unassigned", f'{len(cards)} card{"s" if len(cards) != 1 else ""} awaiting an owner'
    else:
        want = owner.strip().lower()
        cards = [c for c in load_all_cards(a) if owners.get(str(c["cert_id"]), "").lower() == want]
        title, sub_line = owner, f'{len(cards)} card{"s" if len(cards) != 1 else ""} with {a["label"]}'
    svc_map = {n: s["service"] for n, s in subs_by.items()}
    # archived subs' cards stay on the person page but are folded behind an
    # ARCHIVED toggle below the active grid instead of greyed out inline
    act_cards = [c for c in cards if c["sub_number"] not in arch]
    arc_cards = [c for c in cards if c["sub_number"] in arch]
    if not unassigned:
        sub_line = f'{len(act_cards)} card{"s" if len(act_cards) != 1 else ""} with {a["label"]}'
    vals, vas_of, vcur = load_values(a)
    def tiles(cs):
        return "".join(card_tile(c, owners, show_sub=True, archived=(c["sub_number"] in arch),
                                 service=svc_map.get(c["sub_number"], ""),
                                 statline=cust_statline(subs_by.get(c["sub_number"])),
                                 value=vals.get(c["cert_no"] or ""), vcur=vcur)
                       for c in cs)
    def group_html(n, cs):
        # admin person page mirrors the customer home: one dashboard-style card
        # per submission (service line, ETA pill, stage timeline) with this
        # person's tiles inside; the sub number links through to the sub page.
        s = subs_by.get(n)
        svc = html.escape(s["service"]) if s else ""
        pill = eta_pill(s) if s else ""
        link = (f'<a class="view" href="/sub/{html.escape(str(n))}">'
                f'Go to sub #{html.escape(str(n))}</a>')
        tl = timeline_html(s["status"], aside=link, key=n) if s else ""
        cnt = f'{len(cs)} card{"s" if len(cs) != 1 else ""}'
        tiles_h = "".join(card_tile(c, owners, archived=(n in arch),
                                    value=vals.get(c["cert_no"] or ""), vcur=vcur) for c in cs)
        # data-sub/svc/eta feed the sort pills, same attributes card_html writes
        # on a dashboard row: SORT_JS reorders #list's .card children and does
        # not care that these children are submission groups. No data-arch: the
        # archived groups live in #archgrid, which SORT_JS never touches.
        eta = html.escape(s["est_end"] or s["est_start"] or "") if s else ""
        sortattr = f' data-sub="{html.escape(str(n))}" data-svc="{svc}" data-eta="{eta}"'
        return (f'<div class="card grp{" arch" if n in arch else ""}"{sortattr}>'
                f'<div class="top"><div><a class="numlink" href="/sub/{html.escape(str(n))}">'
                # h2, not div: this IS the group's heading. Zero visual delta -
                # the global reset zeroes h2 margins and .num supplies every
                # type value (17/650/-.012em/1.3), so nothing is inherited.
                f'<h2 class="num">#{html.escape(str(n))}</h2></a>'
                f'<div class="meta">{svc} · {cnt}</div></div><div class="pills">{pill}</div></div>'
                f'{tl}<div class="grid" style="margin-top:14px">{tiles_h}</div></div>')
    def grouped(cs):
        gs = {}
        for c in cs:
            gs.setdefault(c["sub_number"], []).append(c)
        order = sorted(gs, key=lambda n: -int(n) if str(n).isdigit() else 0)
        return "".join(group_html(n, gs[n]) for n in order)
    if act_cards:
        # #list is what SORT_JS reorders; the filterrow above it always carries
        # the 20px 0 12px that used to be this wrapper's own top margin
        grid = '<div id="list" style="margin-top:0">' + grouped(act_cards) + "</div>"
    elif unassigned:
        grid = '<div class="empty">🎉 Every active card has an owner tag.</div>'
    elif arc_cards:
        grid = f'<div class="empty">All of {html.escape(owner)}’s cards are in archived submissions.</div>'
    else:
        grid = f'<div class="empty">No cards tagged to “{html.escape(owner)}” yet.</div>'
    archsec = ""
    if arc_cards:
        archsec = f'<div id="archgrid" style="display:none">{grouped(arc_cards)}</div>'
    # the dashboard's three sort pills, verbatim: SORT_JS reorders the
    # submission groups in #list and the choice is the same psa_sort the
    # dashboard stores. Only when there are active groups to reorder.
    pills = ('<button type="button" class="f fsort on" data-sort="sub" aria-pressed="true">Newest</button>'
             '<button type="button" class="f fsort" data-sort="svc" aria-pressed="false">Order type</button>'
             '<button type="button" class="f fsort" data-sort="eta" aria-pressed="false">Return</button>'
             ) if act_cards else ""
    filters = (f'<div class="filters" role="group" aria-label="Sort submissions">'
               f'{pills}</div>') if pills else ""
    # solo pill, same grammar as the dashboard's: a capsule wrapping a single
    # pill prints a ring with nothing else inside (see .fsolo). It rides the
    # sort row's .rowend, not a .filterrow of its own; the fold itself stays
    # below the active groups (ARCHFOLD_JS scrolls to it).
    rowend = (f'<div class="rowend"><button type="button" class="f farch fsolo" '
              f'id="archtoggle" aria-expanded="false" aria-controls="archgrid">'
              f'Archived · {len(arc_cards)}</button></div>') if arc_cards else ""
    filterrow = (f'<div class="filterrow">{filters}{rowend}</div>'
                 if (filters or rowend) else "")
    if unassigned:
        est = ""  # the worklist is about tagging, not money
    else:
        total, unpriced, covered, uncovered = 0.0, set(), 0.0, 0
        for c in act_cards:
            svc = svc_map.get(c["sub_number"], "")
            p = service_price(a, svc)
            if p is None:
                unpriced.add(svc or "unknown service")
            else:
                total += p
            dv = c.get("declared_value")
            if dv is None:
                uncovered += 1
            else:
                covered += dv
        ins = (f'<span class="lbl2">Insured coverage</span><b>${covered:,.0f}{"+" if uncovered else ""} CAD</b>'
               if covered or uncovered else "")
        vtot = sum(vals.get(c["cert_no"] or "", 0) for c in act_cards)
        vline = (f'<span class="lbl2">Est. value · graded</span><b>${vtot:,.0f} {vcur}</b>'
                 if vtot else "")
        vnote = f'<br>values = PSA estimate or last sale · as of {html.escape(vas_of)}' if vline else ""
        # the + says the total is short a tier; the title names which one, so
        # the missing price can be added to PSA_PRICES without guessing
        plus = (f'<span title="no price for '
                f'{html.escape(", ".join(sorted(unpriced)))}">+</span>') if unpriced else ""
        est = (f'<div class="synced">Est. grading cost<b>${total:,.0f}'
               f'{plus} CAD</b>{ins}{vline}'
               f'<span class="estnote">base per-card fees · pending PSA upcharges<br>'
               f'coverage = declared value on file with PSA{vnote}</span></div>') if act_cards else ""
    # back on the left, the export on the right: the sub page's own foot row,
    # with its 18px top margin dropped so the header sits where it always did
    back = ('<div class="foot" style="margin:0">'
            '<span class="footacts"><a class="view" id="backlk" href="/">← Back</a>'
            '<a class="view" href="/">Home</a></span>'
            f'<span class="footacts"><a class="view" href="/cards?owner='
            f'{urllib.parse.quote(owner)}&amp;format=csv">Export CSV</a></span></div>')
    page_title = "Unassigned cards" if unassigned else f"{title}'s cards"
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(page_title)}</title>
{HEAD_HTML}
<style>{THEME_VARS}</style>{APP_CSS_TAG}</head><body><main class="wrap">
{back}
<div class="hrow" style="margin-top:14px"><div><h1>{html.escape(title)}</h1>
<div class="sub">{html.escape(sub_line)}</div>{"" if unassigned else discord_widget(a, owner)}</div>{est}</div>
<div class="toolbar tbq">{search_box(owner="" if unassigned else owner)}</div>
{filterrow}
{grid}
{archsec}
<div class="vh" id="live" aria-live="polite"></div>
</main>{gear_html()}{APP_JS_TAG}</body></html>"""

def people_csv(a, owner):
    """The person page as a spreadsheet: one row per tile that page renders,
    archived groups included, in the same order. Admin-only, same as the page."""
    owners = owners_map(a)
    arch = archived_set(a)
    subs_by = {s["sub_number"]: s for s in load_subs(a)}
    if owner.strip().lower() in ("", "unassigned"):  # the operator worklist
        active = {n for n in subs_by if n not in arch}
        cards = [c for c in load_all_cards(a)
                 if c["sub_number"] in active and not owners.get(str(c["cert_id"]), "")]
    else:
        want = owner.strip().lower()
        cards = [c for c in load_all_cards(a)
                 if owners.get(str(c["cert_id"]), "").lower() == want]
    vals, _, vcur = load_values(a)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["submission", "cert", "card", "grade", "service", "status",
                "archived", f"est_value_{vcur.lower()}"])
    # load_all_cards already reads newest sub first, then line number: a stable
    # sort on the archived flag alone leaves the page's own order intact
    for c in sorted(cards, key=lambda c: c["sub_number"] in arch):
        s = subs_by.get(c["sub_number"])
        v = vals.get(c["cert_no"] or "")
        # a card PSA has not graded has no cert number yet, and the tile says so
        cert = "" if str(c["cert_id"]).startswith("spec:") else (c["cert_no"] or c["cert_id"])
        w.writerow([c["sub_number"], cert, smart_title(c["name"] or ""),
                    c["grade"] or "", s["service"] if s else "", s["status"] if s else "",
                    "yes" if c["sub_number"] in arch else "no",
                    f"{v:.0f}" if v else ""])
    return buf.getvalue()

def csv_filename(owner):
    """A download name the browser will keep: ASCII word characters only."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", owner).strip("-").lower()
    return f"{slug or 'unassigned'}-cards.csv"

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
        # these groups ARE the customer's sub detail view (no /sub access), so
        # they get the entered-on stage dates the admin detail page has
        tl = timeline_html(s["status"], stage_dates(a, s), key=n) if s else ""
        cnt = f'{len(cs)} card{"s" if len(cs) != 1 else ""}'
        tiles = "".join(card_tile(c, owners, show_sub=False, archived=(n in arch), customer=True)
                        for c in cs)
        foot = ""
        if s and s["status"] == "Shipped" and s["shipped"]:
            ft = f'Shipped {html.escape(fmt_mdy(s["shipped"]))}'
            if s["carrier"] and s["tracking"]:  # the click they want most once shipped
                ft += f' · {tracking_html(s["carrier"], s["tracking"])}'
            foot = f'<div class="foot"><span class="est">{ft}</span></div>'
        return (f'<div class="card grp{" arch" if n in arch else ""}">'
                f'<div class="top"><div><h2 class="num">#{html.escape(str(n))}</h2>'
                f'<div class="meta">{svc} · {cnt}</div></div><div class="pills">{pill}</div></div>'
                f'{tl}<div class="grid" style="margin-top:14px">{tiles}</div>{foot}</div>')

    order = sorted(groups, key=lambda n: -int(n) if str(n).isdigit() else 0)
    act = [n for n in order if n not in arch]
    gone = [n for n in order if n in arch]
    body = ("".join(group_html(n, groups[n]) for n in act)
            or '<div class="empty">No cards yet. They appear once the store receives your submission.</div>')
    archpill = archsec = ""
    if gone:  # pill under the search bar (see people_page), fold below the groups
        archpill = (f'<div class="filterrow"><button type="button" class="f farch fsolo" '
                    f'id="archtoggle" aria-expanded="false" aria-controls="archgrid">'
                    f'Archived · {len(gone)}</button></div>')
        archsec = ('<div id="archgrid" style="display:none">'
                   + "".join(group_html(n, groups[n]) for n in gone) + '</div>')
    total = sum(len(groups[n]) for n in act)
    # freshness stamp + store lockup: the customer home is the store's product
    # face - it gets the same trust signals the admin dashboard has
    updated = max((s["updated_at"] or "" for s in subs_by.values()), default="")
    stamp = fmt_local(updated) if updated else "n/a"
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Your cards</title>
{HEAD_HTML}
<style>{THEME_VARS}</style>{APP_CSS_TAG}</head><body><main class="wrap">
<div class="hrow" style="margin-top:14px"><div><div class="brand">{logo_tag()}<h1>Your cards</h1></div>
<div class="sub">{total} card{"s" if total != 1 else ""} · {html.escape(email)}</div>{discord_widget(a, email)}</div>
<div class="synced custrow"><div class="custout">Last synced<b>{html.escape(stamp)}</b></div>
<a class="lgout" href="/logout" title="Sign out" aria-label="Sign out">{ICON_OUT}</a></div></div>
<div class="toolbar tbq">{search_box(owner=email, ph="Search your cards…")}</div>
{archpill}
<div style="margin-top:{0 if gone else 28}px">{body}</div>
{archsec}
<div class="vh" id="live" aria-live="polite"></div>
</main>{APP_JS_TAG}</body></html>"""

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
    total = len(res)
    res = res[:60]  # a broad query matches most of the collection - don't build
    #                 a thousand image tiles in one document (phones choke first)
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
    count = f"{total} match" + ("es" if total != 1 else "") if ql else "All cards"
    if total > len(res):
        count += f" · showing the first {len(res)}, narrow the search"
    if customer:
        count += " · your cards only"
        back = '<a class="view" href="/">← Your cards</a>'
    elif owner:
        count += f" · {html.escape(owner)}'s cards only"
        back = (f'<a class="view" id="backlk" href="/cards?owner={urllib.parse.quote(owner)}">'
                f'← Back</a>')
    else:
        back = '<a class="view" id="backlk" href="/">← Back</a>'
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Search</title>
{HEAD_HTML}
<style>{THEME_VARS}</style>{APP_CSS_TAG}</head><body><main class="wrap">
{back}
<h1 style="margin-top:14px">Search</h1>
<div class="sub">{count}</div>
<div class="toolbar tbq">{search_box(q or '', owner=owner, ph="Search your cards…" if customer else None)}</div>
{grid}
<div class="vh" id="live" aria-live="polite"></div>
</main>{gear_html(customer)}{APP_JS_TAG}</body></html>"""

# ---------- server ----------

class H(BaseHTTPRequestHandler):
    server_version = "psa-tracker"
    # every reply sets its own Content-Length, so keep-alive is safe: one
    # connection now carries the page and the dozens of thumbnails after it
    protocol_version = "HTTP/1.1"
    timeout = 30  # an idle kept-alive connection must not hold a thread forever
    started = False  # set by send_response: a reply has begun

    def log_message(self, fmt, *a):
        msg = fmt % a
        if "/api/hub.json?" in msg:  # older hub sends the key in the query
            msg = re.sub(r"/api/hub\.json\?\S*", "/api/hub.json", msg)
        print(f"{self.address_string()} {msg}", flush=True)

    def log_error(self, fmt, *a):
        if "timed out" in fmt:  # a kept-alive connection going idle is not an error
            return
        self.log_message(fmt, *a)

    def client_ip(self):
        """Throttle key. Cloudflare writes CF-Connecting-IP; in X-Forwarded-For
        only the LAST hop is written by the proxy in front of us, every earlier
        hop is text the client sent, so never key on the first one."""
        cf = self.headers.get("CF-Connecting-IP", "").strip()
        if cf:
            return cf[:64]
        xff = self.headers.get("X-Forwarded-For", "")
        if xff.strip():
            return xff.rsplit(",", 1)[-1].strip()[:64]
        return self.client_address[0]

    def origin_ok(self):
        """CSRF guard for POSTs. A browser sets Origin on every form post, so a
        request carrying someone else's origin is cross-site: the sibling
        example.com sites are same-site for SameSite=Lax, which alone is no
        defence. No Origin at all (curl, older clients) is left alone."""
        origin = self.headers.get("Origin", "").strip()
        if not origin:
            return True
        host = (self.headers.get("X-Forwarded-Host")
                or self.headers.get("Host") or "").split(",")[0].strip()
        proto = (self.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip()
        # behind Caddy the app speaks http while the browser origin is https
        schemes = (proto,) if proto else ("https", "http")
        return bool(host) and any(origin == f"{s}://{host}" for s in schemes)

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

    def settings_ok(self):
        """Settings authorization: the settings cookie always works; in store
        mode any full site-password (admin) session does too - the store's
        admin login IS the settings credential. Customers never qualify."""
        if settings_authed(self.headers.get("Cookie", "")):
            return True
        if SETTINGS_GEAR:
            got = self.authed()
            return bool(got and not got[1])
        return False

    def settings_scope(self):
        """Which accounts this settings session may touch: "" is all of them
        (the settings password holds the instance), an account id is that one
        alone - a gear-mode admin only proved one account's site password."""
        if settings_authed(self.headers.get("Cookie", "")):
            return ""
        got = self.authed()
        return got[0]["id"] if (SETTINGS_GEAR and got and not got[1]) else ""

    def _gz(self, data):
        """gzip a text response when the client accepts it. The dashboard is
        ~106KB raw and 9KB gzipped, and it repeats every navigation under
        no-store - this is the single biggest payload lever left."""
        if len(data) > 500 and "gzip" in self.headers.get("Accept-Encoding", ""):
            gz = gzip.compress(data, 6)
            if len(gz) < len(data):
                self.send_header("Content-Encoding", "gzip")
                data = gz
        self.send_header("Vary", "Accept-Encoding")
        return data

    def see(self, loc):
        """303 after a form POST: the browser re-GETs, so a reload of the reply
        never resubmits it (a second Add used to mint a duplicate account)."""
        return self.send(303, "", extra=[("Location", loc)])

    def send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        data = self._gz(data)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        # no-store forfeits the back forward cache, so only the responses that
        # carry a password field keep it: the gate (served at any path while
        # signed out), /login, /settings and the setup form. A signed-in page is
        # private, no-cache: never a shared cache, always revalidated, but back
        # navigation restores it without a request.
        rpath = urllib.parse.urlparse(self.path).path
        secret = (rpath in ("/login", "/setup") or rpath.startswith("/settings")
                  or not self.authed())
        self.send_header("Cache-Control", "no-store" if secret else "private, no-cache")
        self.send_header("X-Frame-Options", "DENY")
        # everything is same-origin (the /img proxy included); 'unsafe-inline'
        # stays because the chrome CSS and JS are inline Python strings, and
        # data: is the favicon's SVG
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; img-src 'self' data:; "
                         "script-src 'self' 'unsafe-inline'; "
                         "style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
        # same-origin (not no-referrer): still sends NOTHING cross-site, but keeps
        # internal referrers - BACK_JS needs them to tell "came from inside the
        # site" (history back) apart from a direct/external entry (href fallback)
        self.send_header("Referrer-Policy", "same-origin")
        if self.close_connection:  # say so, rather than let the peer find the FIN
            self.send_header("Connection", "close")
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
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_HEAD(self):
        # uptime checks: cheap 200, headers only
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def serve_str(self, pair, ctype):
        """The hashed chrome bundle (/app.css, /app.js): cached forever, a new
        hash in ?v is the cache buster. No secrets live in either string.
        Takes a _bundle pair, so no request compresses anything."""
        raw, gz = pair
        data = raw
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        if len(gz) < len(raw) and "gzip" in self.headers.get("Accept-Encoding", ""):
            self.send_header("Content-Encoding", "gzip")
            data = gz
        self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def serve_asset(self, fpath, ctype):
        """Small pre-auth static file (favicon PNGs); 404s when the instance
        doesn't ship the file."""
        if not os.path.exists(fpath):
            return self.send(404, "not here", "text/plain")
        data = open(fpath, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

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
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def hub_key_ok(self, query):
        """Gate for the hub's LAN endpoints. PSA_HUB_KEY unset = feature off
        (every caller gets a 404): the URL is public via Cloudflare, the key only
        lives in the two boxes' env files. The key rides X-Hub-Key; the query
        form stays for one release so the server can be updated without an outage, and
        it is redacted from the log (see log_message)."""
        key = os.environ.get("PSA_HUB_KEY", "")
        got = (self.headers.get("X-Hub-Key", "").strip()
               or urllib.parse.parse_qs(query).get("key", [""])[0])
        return bool(key) and hmac.compare_digest(got.encode(), key.encode())

    def serve_card_shot(self, sub, query):
        """GET /api/shot/<sub>.png -> the dashboard card of that submission as a
        PNG, the same render psa_watch attaches to its Discord posts. The hub
        (the server) fetches it when a submission changes, so one call per change: the
        subprocess takes 5 to 15 s and blocks this handler thread meanwhile,
        which is fine (the 30 s handler timeout only covers idle socket reads, it
        does not run while we work). psa_shot imports playwright, which app.py
        must never load, so it is a subprocess and never an import."""
        if not self.hub_key_ok(query):
            return self.send(404, "not found", "text/plain")
        acct = next((a for a in load_accounts().values()
                     if not a.get("feeder") and load_sub(a, sub)), None)
        if not acct:
            return self.send(404, "no such submission", "text/plain")
        env = dict(os.environ, PSA_ACCT_ID=acct["id"],
                   PLAYWRIGHT_BROWSERS_PATH="/opt/psa-tracker/.pw-browsers")
        env.setdefault("PSA_WEB_PORT", str(PORT))
        fd, out = tempfile.mkstemp(suffix=".png", prefix="psa-shot-")
        os.close(fd)
        try:
            here = os.path.dirname(os.path.abspath(__file__))
            r = subprocess.run([sys.executable, os.path.join(here, "psa_shot.py"), sub, out],
                               capture_output=True, text=True, timeout=90, env=env)
            data = open(out, "rb").read() if r.returncode == 0 else b""
            if not data:
                print(f"card shot #{sub} failed: rc={r.returncode} "
                      f"{((r.stderr or r.stdout).strip().splitlines() or [''])[-1]}", flush=True)
                return self.send(503, "render failed", "text/plain")
        except Exception as e:  # timeout, missing playwright, unreadable temp file
            print(f"card shot #{sub} failed: {e.__class__.__name__}: {e}", flush=True)
            return self.send(503, "render failed", "text/plain")
        finally:
            try: os.remove(out)
            except OSError: pass
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def serve_hub_summary(self, query):
        # Read-only submissions summary for a personal dashboard, key-gated like the
        # card shot. hub keys each entry on "sub_number".
        if not self.hub_key_ok(query):
            return self.send(404, "not found", "text/plain")
        subs = []
        try:
            for a in load_accounts().values():
                if a.get("feeder"):  # its subs live in the target's db, listed there
                    continue
                arc = archived_set(a)
                for s in load_subs(a):
                    subs.append({k: s[k] for k in ("sub_number", "status", "card_count",
                                 "arrived", "est_end", "grades_ready", "on_hold",
                                 "shipped", "updated_at")}
                                | {"archived": 1 if s["sub_number"] in arc else 0})
        except sqlite3.Error:  # a failed read is not "no submissions" - hub must not cache it
            traceback.print_exc()
            return self.send(503, '{"error":"unavailable"}',
                             "application/json; charset=utf-8")
        # Per-account scan health, the three files run_scan.sh keeps. Feeders
        # are here too: a feeder scans on its own cookie, so it breaks alone and
        # the hub has to be able to say which account went dark (T105).
        accounts = {}
        for a in load_accounts().values():
            d = os.path.join(ACCOUNTS_DIR, a["id"])
            try:
                ok = datetime.fromtimestamp(
                    os.stat(os.path.join(d, ".last_ok")).st_mtime,
                    timezone.utc).isoformat(timespec="seconds")
            except OSError:
                ok = None
            try:
                fails = int(open(os.path.join(d, ".scan_fails")).read().strip() or 0)
            except (OSError, ValueError):
                fails = 0
            accounts[a["id"]] = {"last_ok": ok, "fails": fails, "error": scan_error(a)}
        return self.send(200, json.dumps({"subs": subs, "accounts": accounts}),
                         "application/json; charset=utf-8")

    def send_response(self, *a, **kw):
        self.started = True  # the guard must not append a 500 to a reply already on the wire
        BaseHTTPRequestHandler.send_response(self, *a, **kw)

    def guard(self, route):
        """Any uncaught error is a 500 page, not a dropped connection."""
        self.started = False  # one handler instance serves a whole keep-alive connection
        try:
            route()
        except Exception:
            traceback.print_exc()
            if self.started:
                self.close_connection = True
                return
            try:
                self.send(500, error_page())
            except Exception:
                self.close_connection = True

    def do_GET(self):
        self.guard(self.route_get)

    def do_POST(self):
        # Bodies below are read up to a cap, so anything past it stays in the
        # stream, and leftover body bytes are not a next request. POSTs are one
        # user action at a time; only the GETs need the connection kept.
        self.close_connection = True
        self.guard(self.route_post)

    def route_get(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/logo":
            return self.serve_logo()
        if path == "/app.css":
            return self.serve_str(CSS_BYTES, "text/css; charset=utf-8")
        if path == "/app.js":
            return self.serve_str(APP_JS_BYTES, "text/javascript; charset=utf-8")
        if path in ("/favicon.png", "/favicon.ico"):  # Safari asks for .ico blind
            return self.serve_asset(FAV_PNG, "image/png")
        if path == "/apple-touch-icon.png":
            return self.serve_asset(TOUCH_PNG, "image/png")
        if path == "/manifest.json":
            return self.send(200, MANIFEST, "application/manifest+json")
        if path == "/api/hub.json":  # LAN summary for the hub (the server), key-gated
            return self.serve_hub_summary(parsed.query)
        m = re.fullmatch(r"/api/shot/(\d{1,20})\.png", path)  # card PNG for the hub
        if m:
            return self.serve_card_shot(m.group(1), parsed.query)
        if path == "/img":  # hot path: skip the setup-state machinery entirely
            if not self.authed():
                return self.send(200, gate_page())
            return self.serve_img(parsed.query)
        s_allowed, s_retry = setup_state()
        if path == "/setup":
            # a retry is the owner re-entering their PSA login, not a public form
            if not s_allowed or (s_retry and not self.authed()):
                return self.send(302, "", extra=[("Location", "/")])
            return self.send(200, setup_page())
        if s_allowed and s_retry is None:  # fresh instance: everything is setup
            return self.send(200, setup_page())
        if path == "/settings":
            if self.settings_ok():  # store admins walk straight in
                m, e = FLASH.pop(urllib.parse.parse_qs(parsed.query).get("m", [""])[0],
                                 ("", ""))
                return self.send(200, settings_page(msg=m, err=e,
                                                    only=self.settings_scope()))
            if not SETTINGS_HASH:
                return self.send(404, "not found", "text/plain")
            return self.send(200, settings_gate())
        got = self.authed()
        if not got:
            return self.send(200, gate_page())
        acct, cust = got
        if path == "/logout":
            return self.send(302, "", extra=[("Location", "/"),
                ("Set-Cookie", "psa_session=; Path=/; Max-Age=0"),
                ("Set-Cookie", "psa_settings=; Path=/; Max-Age=0")])
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
                return self.send(200, json.dumps(suggest(acct, qs.get("q", [""])[0],
                                                        owner=cust, people=False)),
                                 "application/json; charset=utf-8")
            return self.send(302, "", extra=[("Location", "/")])
        if path == "/":
            if urllib.parse.parse_qs(parsed.query).get("arch"):
                return self.send(200, arch_rows(acct, load_subs(acct)))
            return self.send(200, dash_page(acct, load_subs(acct)))
        if path == "/cards":
            qs = urllib.parse.parse_qs(parsed.query)
            owner = qs.get("owner", [""])[0]
            if qs.get("format", [""])[0] == "csv":
                return self.send(200, people_csv(acct, owner), "text/csv; charset=utf-8",
                                 extra=[("Content-Disposition",
                                         f'attachment; filename="{csv_filename(owner)}"')])
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
                return self.send(404, not_found_page("That submission isn’t here."))
            return self.send(200, detail_page(acct, sub))
        self.send(404, not_found_page())

    def route_post(self):
        if not self.origin_ok():
            self.close_connection = True  # the unread body is not a next request
            return self.send(403, "bad origin", "text/plain")
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
            if not cid or not card_exists(acct, cid):
                return self.send(400, "unknown cert", "text/plain")
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
        if path == "/discord":
            got = self.authed()
            if not got:
                return self.send(403, "auth", "text/plain")
            acct, cust = got
            n = int(self.headers.get("Content-Length", "0") or 0)
            form = urllib.parse.parse_qs(self.rfile.read(min(n, 1024)).decode("utf-8", "replace"))
            owner = (form.get("owner") or [""])[0].strip()
            did = (form.get("id") or [""])[0].strip()
            if cust and owner.lower() != cust:  # customers manage only their own tag
                return self.send(403, "auth", "text/plain")
            if not owner or len(owner) > 80 or (did and not DISCORD_ID_RE.fullmatch(did)):
                return self.send(400, "bad request", "text/plain")
            set_discord(acct, owner, did)
            return self.send(204, "", "text/plain")
        if path == "/setup":
            allowed, retry = setup_state()
            if not allowed or (retry and not self.authed()):
                return self.send(403, "setup is closed", "text/plain")
            n = int(self.headers.get("Content-Length", "0") or 0)
            form = urllib.parse.parse_qs(self.rfile.read(min(n, 4096)).decode("utf-8", "replace"))
            get = lambda k: (form.get(k) or [""])[0].strip()
            label = get("label") or "My cards"
            site_pw, psa_email, psa_pw = get("site_pw"), get("psa_email"), get("psa_pw")
            time.sleep(0.4)
            if not all(env_ok(v) for v in (label, site_pw, psa_email, psa_pw)):
                return self.send(200, setup_page("Each field has to be a single line of text.",
                                                 label, psa_email))
            if len(site_pw) < 4:
                return self.send(200, setup_page("Site password needs at least 4 characters.",
                                                 label, psa_email))
            if "@" not in psa_email or not psa_pw:
                return self.send(200, setup_page("Enter your PSA account email and password.",
                                                 label, psa_email))
            acct_id = (retry["id"] if retry else
                       (re.sub(r"[^a-z0-9-]+", "-", label.lower()).strip("-")[:24] or "main"))
            write_account_env(acct_id, label, site_pw, psa_email, psa_pw)
            start_first_scan()
            exp = int(time.time()) + COOKIE_DAYS * 86400
            cookie = (f"psa_session={make_token(acct_id, exp)}; Path=/; Max-Age={COOKIE_DAYS*86400}; "
                      "HttpOnly; SameSite=Lax" + ("; Secure" if COOKIE_SECURE else ""))
            return self.send(302, "", extra=[("Location", "/"), ("Set-Cookie", cookie)])
        if path == "/settings/auth":
            ip = self.client_ip()
            n = int(self.headers.get("Content-Length", "0") or 0)
            form = urllib.parse.parse_qs(self.rfile.read(min(n, 2048)).decode("utf-8", "replace"))
            given = (form.get("password") or [""])[0]
            time.sleep(0.4)
            if login_locked(ip):
                return self.send(200, settings_gate("Too many attempts. Try again in a few minutes."))
            if not is_settings_pw(given):
                login_fail(ip)
                return self.send(200, settings_gate("Incorrect password."))
            login_ok(ip)
            return self.send(302, "", extra=[("Location", "/settings"),
                                             ("Set-Cookie", settings_cookie_hdr())])
        if path == "/settings/password":
            # a scoped session must not mint the instance credential and log
            # back in with it, unscoped
            if not self.settings_ok() or self.settings_scope():
                return self.send(403, "settings auth", "text/plain")
            n = int(self.headers.get("Content-Length", "0") or 0)
            form = urllib.parse.parse_qs(self.rfile.read(min(n, 2048)).decode("utf-8", "replace"))
            new_pw = (form.get("new_pw") or [""])[0]
            confirm = (form.get("confirm_pw") or [""])[0]
            if len(new_pw) < 6:
                return self.see(flash(err="Settings password needs at least 6 characters."))
            if not env_ok(new_pw):  # same env file, same truncation
                return self.see(flash(err="The password has to be a single line of text."))
            if new_pw != confirm:
                return self.see(flash(err="The two passwords don’t match."))
            if any(hmac.compare_digest(new_pw.encode(), a["password"].encode()) for a in load_accounts().values()):
                return self.see(flash(err="That password already routes to an account at the gate."))
            global SETTINGS_HASH
            SETTINGS_HASH = hashlib.sha256(new_pw.encode()).hexdigest()
            try:
                env_set(GLOBAL_ENV, {"PSA_SETTINGS_PW_HASH": SETTINGS_HASH})
            except OSError:
                return self.see(flash(
                    err=f"Password active for now, but writing {GLOBAL_ENV} failed. It reverts on restart."))
            return self.see(flash(msg="Settings password changed. It works immediately."))
        if path in ("/settings/account", "/settings/add"):
            if not self.settings_ok():
                return self.send(403, "settings auth", "text/plain")
            n = int(self.headers.get("Content-Length", "0") or 0)
            form = urllib.parse.parse_qs(self.rfile.read(min(n, 4096)).decode("utf-8", "replace"))
            get = lambda k: (form.get(k) or [""])[0].strip()
            # "" holds the instance, an id is that one account: gates both branches
            scope = self.settings_scope()
            if path == "/settings/account":
                acct_id, action, value = get("acct"), get("action"), get("value")
                if scope and acct_id != scope:
                    return self.send(403, "settings auth", "text/plain")
                accts = load_accounts()
                if acct_id not in accts:
                    return self.send(400, "unknown account", "text/plain")
                if not env_ok(value):
                    return self.see(flash(err="That has to be a single line of text."))
                if action == "psa_pw":
                    if not value:
                        return self.see(flash(err="Enter the new PSA password first."))
                    # also clears UNLINKED: saving a fresh PSA password IS the relink
                    env_set(account_env_path(acct_id),
                            {"PSA_LOGIN_PW": value, "PSA_COOKIE": "", "UNLINKED": ""})
                    return self.see(flash(
                        msg="PSA password saved. The next hourly sync signs in fresh with it."))
                if action == "site_pw":
                    if accts[acct_id].get("feeder"):
                        return self.see(flash(err="This account scans into the shared dashboard; the site password covers it."))
                    if len(value) < 4:
                        return self.see(flash(err="Site password needs at least 4 characters."))
                    if value != get("value2"):
                        return self.see(flash(err="The two site passwords don’t match."))
                    if is_settings_pw(value):
                        return self.see(flash(err="That’s the settings password. Pick a different one."))
                    if any(i != acct_id and hmac.compare_digest(value.encode(), a["password"].encode())
                           for i, a in accts.items()):
                        return self.see(flash(err="That site password already routes to another account."))
                    env_set(account_env_path(acct_id), {"SITE_PASSWORD": value})
                    return self.see(flash(msg="Site password changed. It works at the gate right away."))
                if action == "webhook":
                    if not (value.startswith("https://discord.com/api/webhooks/")
                            or value.startswith("https://discordapp.com/api/webhooks/")):
                        return self.see(flash(err="Webhook must be a discord.com/api/webhooks/… URL."))
                    env_set(account_env_path(acct_id), {"DISCORD_WEBHOOK": value})
                    return self.see(flash(msg="Webhook saved. Status changes for this account ping it."))
                if action == "webhook_clear":
                    env_set(account_env_path(acct_id), {"DISCORD_WEBHOOK": ""})
                    return self.see(flash(msg="Webhook removed."))
                if action in ("otp_send", "otp_code"):
                    d = os.path.dirname(account_env_path(acct_id))
                    if action == "otp_send":
                        for k in ("code", "waiting"):
                            try: os.remove(os.path.join(d, f"otp.{k}"))
                            except FileNotFoundError: pass
                        open(os.path.join(d, "otp.armed"), "w").write(time.strftime("%Y-%m-%dT%H:%M"))
                        start_first_scan()
                        return self.see(flash(
                            msg="Sign-in started. PSA texts the code to this account’s phone in a minute or two. "
                                "Come back here and enter it."))
                    code = re.sub(r"\D", "", value)
                    if not 4 <= len(code) <= 8:
                        return self.see(flash(err="Enter the code PSA texted (digits only)."))
                    tmp = os.path.join(d, "otp.code.tmp")
                    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                    with os.fdopen(fd, "w") as f:
                        f.write(code)
                    os.replace(tmp, os.path.join(d, "otp.code"))
                    return self.see(flash(msg="Code sent. Sign-in finishes within a minute."))
                if action == "unlink":
                    # NOT a rename: the site keeps serving the last known data
                    # (dashboard shows an unlinked banner); the scanner skips the
                    # account and its PSA credentials are cleared. Saving a new
                    # PSA password on the account relinks it.
                    env_set(account_env_path(acct_id),
                            {"UNLINKED": "1", "PSA_COOKIE": "", "PSA_LOGIN_PW": ""})
                    return self.see(flash(
                        msg="Account unlinked. The site keeps showing its last known data; "
                            "syncs stop. Save a new PSA password on it to relink."))
                return self.send(400, "unknown action", "text/plain")
            if scope:  # a gear session administers its own account, no others
                return self.send(403, "settings auth", "text/plain")
            # Add: only PSA email + password are asked. The label comes from the
            # email; the required-unique site password is generated and shown
            # ONCE (changeable in the Site password panel).
            psa_email, psa_pw = get("psa_email"), get("psa_pw")
            if "@" not in psa_email or not psa_pw:
                return self.see(flash(err="Enter the PSA email and password."))
            if not (env_ok(psa_email) and env_ok(psa_pw)):
                return self.see(flash(err="The email and password each have to be a single line of text."))
            accts = load_accounts()
            local = psa_email.split("@")[0]
            label = local[:40]
            acct_id = re.sub(r"[^a-z0-9-]+", "-", local.lower()).strip("-")[:24] or "acct"
            if acct_id in accts:
                acct_id = f"{acct_id}-{int(time.time()) % 10000}"
            while True:
                gen_pw = base64.b32encode(os.urandom(5)).decode().lower().rstrip("=")
                if (not is_settings_pw(gen_pw)
                        and not any(hmac.compare_digest(gen_pw.encode(), a["password"].encode()) for a in accts.values())):
                    break
            write_account_env(acct_id, label, gen_pw, psa_email, psa_pw)
            start_first_scan()
            return self.see(flash(
                msg=f"Account added. Its site password is {gen_pw} (shown once; "
                    f"visitors type it to see this account, change it under Site password)."))
        if path != "/login":
            return self.send(404, "not found", "text/plain")
        ip = self.client_ip()
        n = int(self.headers.get("Content-Length", "0") or 0)
        form = urllib.parse.parse_qs(self.rfile.read(min(n, 4096)).decode("utf-8", "replace"))
        given = (form.get("password") or [""])[0]
        time.sleep(0.4)  # blunt the brute force; throttle below does the real work
        if login_locked(ip):
            return self.send(200, gate_page("Too many attempts. Try again in a few minutes."))
        if is_settings_pw(given):  # the settings password routes to /settings
            login_ok(ip)
            return self.send(302, "", extra=[("Location", "/settings"),
                                             ("Set-Cookie", settings_cookie_hdr())])
        # The password IS the account selector: whichever account's site password
        # matches is the account this session gets. Passwords are unique per account.
        matched = None
        for a in load_accounts().values():
            if a.get("feeder"):
                continue
            if hmac.compare_digest(given.encode(), a["password"].encode()):
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
            msg = ("No cards found for that email yet. Check with the store "
                   "which email your cards are tagged under." if "@" in given
                   else "Incorrect password.")
            return self.send(200, gate_page(msg))
        login_ok(ip)
        exp = int(time.time()) + COOKIE_DAYS * 86400
        cookie = (f"psa_session={make_token(matched['id'], exp, email)}; Path=/; Max-Age={COOKIE_DAYS*86400}; "
                  "HttpOnly; SameSite=Lax" + ("; Secure" if COOKIE_SECURE else ""))
        self.send(302, "", extra=[("Location", "/"), ("Set-Cookie", cookie)])


class Server(ThreadingHTTPServer):
    request_queue_size = 128  # socketserver's default of 5 drops a burst of connections


def main():
    if not SECRET:
        raise SystemExit("PSA_SECRET must be set")
    accts = load_accounts()
    if not accts:
        print(f"no accounts in {ACCOUNTS_DIR} - serving FIRST-RUN SETUP at / "
              "(or run add_account.sh)" if setup_state()[0] else
              f"no readable account in {ACCOUNTS_DIR} - setup stays closed, "
              "fix the account.env", flush=True)
    dupes = len(accts) - len({a["password"] for a in accts.values()})
    if dupes:
        print(f"WARNING: {dupes} duplicate site password(s) across accounts - "
              "login routes to the first match; make them unique!", flush=True)
    print(f"serving on {BIND}:{PORT} - {len(accts)} account(s): {', '.join(accts)}", flush=True)
    Server((BIND, PORT), H).serve_forever()

if __name__ == "__main__":
    main()
