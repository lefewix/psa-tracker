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
import hashlib, hmac, html, json, os, re, shlex, sqlite3, threading, time
import urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SECRET = os.environ.get("PSA_SECRET", "").encode()
BIND = os.environ.get("PSA_BIND", "0.0.0.0")
PORT = int(os.environ.get("PSA_PORT", "8080"))
COOKIE_DAYS = int(os.environ.get("COOKIE_DAYS", "30"))
COOKIE_SECURE = os.environ.get("PSA_COOKIE_SECURE", "1") not in ("0", "false", "no")
SITE_TITLE = os.environ.get("SITE_TITLE", "Submissions")
SITE_TAGLINE = os.environ.get("SITE_TAGLINE", "PSA GRADING TRACKER")
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

def make_token(acct_id, exp):
    msg = f"{acct_id}.{exp}".encode()
    sig = hmac.new(SECRET, msg, hashlib.sha256).hexdigest()
    return f"{acct_id}.{exp}.{sig}"

def valid_token(tok):
    """Return the account id the token grants, or None."""
    parts = (tok or "").split(".")
    if len(parts) != 3:
        return None
    acct_id, exp_s, sig = parts
    try:
        exp = int(exp_s)
    except ValueError:
        return None
    if exp < time.time():
        return None
    good = hmac.new(SECRET, f"{acct_id}.{exp_s}".encode(), hashlib.sha256).hexdigest()
    return acct_id if hmac.compare_digest(good, sig) else None

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

def suggest(a, q, owner=None, limit_names=5, limit_cards=5):
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
        name_hits = [n for n in names if ql in n.lower()][:limit_names]
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
body{background:#07070a;min-height:100vh;position:relative;
 color:#ecebf0;font-family:'Inter',-apple-system,'Segoe UI',system-ui,sans-serif;
 -webkit-font-smoothing:antialiased;padding:44px 20px 80px}
/* live aurora background: two big blurred gradient layers drifting on independent loops */
body::before,body::after{content:"";position:fixed;inset:-30%;z-index:-1;pointer-events:none;will-change:transform,opacity}
body::before{background:
 radial-gradient(42% 42% at 32% 30%, rgba(132,84,255,.60), transparent 62%),
 radial-gradient(36% 36% at 72% 62%, rgba(226,92,196,.44), transparent 62%);
 filter:blur(36px);animation:drift1 26s ease-in-out infinite alternate}
body::after{background:
 radial-gradient(40% 40% at 66% 24%, rgba(132,84,255,.50), transparent 62%),
 radial-gradient(46% 46% at 24% 74%, rgba(52,168,255,.32), transparent 62%);
 filter:blur(46px);animation:drift2 35s ease-in-out infinite alternate}
@keyframes drift1{
 0%{transform:translate3d(-5%,-4%,0) scale(1);opacity:.85}
 50%{opacity:1}
 100%{transform:translate3d(7%,6%,0) scale(1.2);opacity:.8}}
@keyframes drift2{
 0%{transform:translate3d(6%,5%,0) scale(1.14);opacity:.8}
 50%{opacity:1}
 100%{transform:translate3d(-6%,-5%,0) scale(1);opacity:.95}}
@media(prefers-reduced-motion:reduce){body::before,body::after,.node.now .dot{animation:none}}
.wrap{max-width:820px;margin:0 auto}
h1{font-size:30px;font-weight:800;letter-spacing:-.02em}
h1.big{font-size:clamp(40px,9vw,56px);line-height:1.02}
.sub{font-size:10px;font-weight:700;letter-spacing:.18em;color:#5a5866;margin-top:6px}
.hrow{display:flex;justify-content:space-between;align-items:flex-start;gap:14px}
.synced{text-align:right;flex-shrink:0;font-size:8.5px;font-weight:700;letter-spacing:.13em;
 color:#6c6a7d;line-height:1.5;padding-top:5px;white-space:nowrap}
.synced b{display:block;font-size:11px;font-weight:800;letter-spacing:.04em;color:#b9aeff;margin-top:2px}
.synced .estnote{display:block;font-size:7.5px;font-weight:700;letter-spacing:.08em;color:#4d4b59;margin-top:3px;line-height:1.6}
.synced .lbl2{display:block;margin-top:8px}
.toolbar{display:flex;gap:10px;margin:22px 0 4px;flex-wrap:wrap;align-items:stretch}
.searchwrap{position:relative;flex:1;min-width:220px}
.searchwrap .sicon{position:absolute;left:13px;top:50%;transform:translateY(-50%);color:#6c6a7d;pointer-events:none}
.searchbar{width:100%;margin:0;text-align:left;padding:10px 13px 10px 36px;font-size:13px;font-weight:600}
.preview{position:absolute;z-index:30;top:calc(100% + 6px);left:0;right:0;background:#111116;
 border:1px solid #262530;border-radius:12px;padding:6px;display:none;max-height:64vh;overflow:auto;
 box-shadow:0 14px 44px rgba(0,0,0,.55)}
.pvsec{font-size:8.5px;font-weight:800;letter-spacing:.14em;color:#5a5866;padding:9px 10px 4px}
.pvrow{display:flex;align-items:center;gap:9px;padding:8px 10px;border-radius:8px;text-decoration:none;
 color:#ecebf0;font-size:12.5px;font-weight:600}
.pvrow:hover{background:#1a1922}
.pvrow small{display:block;color:#77748a;font-size:10px;font-weight:600;margin-top:1px;letter-spacing:.02em}
.pvtag{font-size:8px;font-weight:800;letter-spacing:.1em;color:#c9beff;background:#221b45;border:1px solid #382c72;
 border-radius:99px;padding:3px 7px;text-transform:uppercase;flex-shrink:0}
.pvimg{width:26px;height:36px;object-fit:cover;border-radius:4px;border:1px solid #26252f;flex-shrink:0;background:#17171c}
.pvempty{padding:14px 10px;color:#5f5d6e;font-size:12px}
.filters{display:flex;gap:7px;flex-wrap:wrap;margin:26px 0 22px}
.f{font-size:10px;font-weight:700;letter-spacing:.09em;color:#8d8a9a;background:#17171c;
 border:1px solid #24232c;padding:6px 13px;border-radius:99px;cursor:pointer;transition:.15s}
.f:hover{border-color:#3a3849;color:#c3c0d0}
.f.on{background:#7c5cff;border-color:#7c5cff;color:#fff}
.f.farch.on{background:#4d4b59;border-color:#4d4b59;color:#fff}
/* glass cards over the aurora: translucent purple gradient + faint hairline */
.card{background:linear-gradient(180deg,rgba(38,24,56,.52),rgba(24,15,34,.55));
 border:1px solid rgba(255,255,255,.08);border-radius:18px;
 padding:26px 30px;margin-bottom:20px;
 backdrop-filter:blur(18px) saturate(150%);-webkit-backdrop-filter:blur(18px) saturate(150%);
 box-shadow:inset 0 1px 0 rgba(255,255,255,.07),0 10px 34px rgba(0,0,0,.28);
 transition:transform .18s,border-color .18s,opacity .18s,filter .18s}
.card:hover{transform:translateY(-2px);border-color:rgba(255,255,255,.14)}
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.num{font-size:21px;font-weight:800;letter-spacing:-.01em}
.meta{font-size:14px;font-weight:600;color:#9b93b3;margin-top:3px}
.pill{font-size:11px;font-weight:800;letter-spacing:.09em;padding:8px 15px;border-radius:99px;white-space:nowrap;
 text-transform:uppercase;color:#c9b8ff;background:rgba(139,92,246,.16);border:1px solid rgba(167,139,250,.32)}
.pill.done{color:#9d9aab;background:rgba(255,255,255,.05);border-color:rgba(255,255,255,.12)}
.pill.hold{color:#ffc9c9;background:rgba(220,60,60,.14);border-color:rgba(220,90,90,.35)}
.pill.arch{color:#9d9aab;background:rgba(255,255,255,.05);border-color:rgba(255,255,255,.12)}
.pills{display:flex;flex-direction:column;gap:5px;align-items:flex-end}
/* gradient progress timeline */
.tl{position:relative;height:46px;margin:22px 0 12px}
/* pixel-exact vertical geometry: track center y=7 == every dot's center
   (10px dot at y=2..12, 14px active dot at y=0..14, labels all start y=21) */
.track{position:absolute;top:6px;left:5%;right:5%;height:2px;background:rgba(255,255,255,.09);border-radius:2px}
.fill{position:absolute;top:6px;left:5%;height:2px;border-radius:2px;transition:width .4s;
 background:linear-gradient(90deg,#7c3aed,#d94ff2);
 box-shadow:0 0 9px rgba(217,79,242,.45)}
.node{position:absolute;top:0;transform:translateX(-50%);text-align:center}
.dot{width:10px;height:10px;border-radius:50%;background:rgba(255,255,255,.16);border:0;margin:2px auto 9px}
.node.done .dot{background:#9d5bf0}
.node.now .dot{width:14px;height:14px;margin:0 auto 7px;background:#d94ff2;
 box-shadow:0 0 0 4px rgba(217,79,242,.18),0 0 12px rgba(217,79,242,.6);
 animation:nowpulse 2.6s ease-in-out infinite}
@keyframes nowpulse{50%{box-shadow:0 0 0 7px rgba(217,79,242,.08),0 0 16px rgba(217,79,242,.85)}}
.lbl{font-size:9px;font-weight:700;letter-spacing:.06em;color:#55516a;display:block;line-height:1.2;text-transform:uppercase}
.node.done .lbl{color:#a79fc0}
.node.now .lbl{color:#fff;font-weight:800}
.foot{border-top:1px solid rgba(255,255,255,.06);padding-top:13px;display:flex;justify-content:space-between;
 align-items:center;gap:10px;flex-wrap:wrap}
.footacts{display:flex;gap:13px;align-items:center;flex-wrap:wrap}
.est{font-size:13px;font-weight:600;color:#8d87a0}
.view{font-size:13px;font-weight:600;color:#a78bfa;text-decoration:none}
.view:hover{color:#c4b0ff}
.archbtn{font-size:10.5px;font-weight:700;color:#8d8a9a;background:transparent;border:0;padding:0;cursor:pointer;
 font-family:inherit;letter-spacing:.02em}
.archbtn:hover{color:#c3c0d0}
.empty{color:#5f5d6e;font-size:13px;padding:40px 0;text-align:center}
.cover{width:44px;height:60px;object-fit:cover;border-radius:5px;border:1px solid #26252f;background:#17171c;flex-shrink:0}
.hd{display:flex;gap:13px;align-items:flex-start;flex:1}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:16px;margin-top:24px}
.grid img{width:100%;border-radius:8px;border:1px solid #26252f;background:#17171c;aspect-ratio:1.72/2.4;object-fit:cover;display:block}
.gc{background:linear-gradient(180deg,rgba(38,24,56,.52),rgba(24,15,34,.55));
 border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:11px;
 display:flex;flex-direction:column;gap:2px;
 backdrop-filter:blur(18px) saturate(150%);-webkit-backdrop-filter:blur(18px) saturate(150%);
 box-shadow:inset 0 1px 0 rgba(255,255,255,.07),0 10px 34px rgba(0,0,0,.28);
 transition:transform .18s,border-color .18s,opacity .18s,filter .18s}
.gc:hover{transform:translateY(-2px);border-color:rgba(255,255,255,.14)}
.gc .ph{width:100%;aspect-ratio:1.72/2.4;border-radius:8px;border:1px dashed #2b2a34;background:#141419;display:flex;align-items:center;justify-content:center;color:#3f3d4a;font-size:10px;font-weight:700;letter-spacing:.1em}
.gc .cn{font-size:14px;font-weight:800;color:#ecebf0;margin-top:9px;letter-spacing:-.01em}
.cn.pre{color:#8d8a9a;font-size:11px;letter-spacing:.14em}
.gc .nm{font-size:10px;font-weight:600;color:#77748a;line-height:1.4;margin-top:3px;height:56px;
 display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:6px}
.gc .gr{font-size:9px;font-weight:800;color:#c9beff;letter-spacing:.08em;margin-top:3px}
.own{margin-top:auto;background:#0c0c10;border:1px solid #24232c;border-radius:7px;color:#ecebf0;font:inherit;font-size:11px;font-weight:600;padding:7px 9px;width:100%;outline:none}
.own::placeholder{color:#46444f}
.own:focus{border-color:#7c5cff}
.own.saved{border-color:#3a7c4f}
.sublink{display:block;text-align:center;font-size:9.5px;font-weight:800;letter-spacing:.05em;color:#c9beff;
 background:#1a1533;border:1px solid #322863;border-radius:99px;padding:6px 10px;text-decoration:none;margin-top:8px}
.sublink:hover{background:#241b45;color:#e6e0ff}
.svc{text-align:center;font-size:9px;font-weight:700;letter-spacing:.09em;color:#77748a;margin-top:6px;text-transform:uppercase}
/* archived grey-out */
.card.arch,.gc.arch{opacity:.42;filter:grayscale(.72)}
.card.arch:hover,.gc.arch:hover{opacity:.9;filter:grayscale(.15)}
.card.arch .fill{background:#4d4b59;box-shadow:none}
.card.arch .node.now .dot,.card.arch .node.done .dot{background:#5b5968;border-color:#5b5968;box-shadow:none;animation:none}
/* gate */
.gate{min-height:75vh;display:flex;align-items:center;justify-content:center}
.gbox{width:290px;text-align:center}
.gbox h1{font-size:26px}
input{width:100%;margin-top:26px;background:#111116;border:1px solid #24232c;border-radius:10px;
 color:#ecebf0;font-size:14px;font-weight:600;text-align:center;padding:12px;font-family:inherit;outline:none}
input:focus{border-color:#7c5cff}
button{width:100%;margin-top:10px;background:#7c5cff;border:0;border-radius:10px;color:#fff;
 font-size:12px;font-weight:800;letter-spacing:.1em;padding:12px;cursor:pointer;font-family:inherit}
button:hover{background:#8f73ff}
.err{color:#ff8b8b;font-size:11px;font-weight:600;margin-top:12px;min-height:14px}
@media(max-width:640px){.lbl{font-size:0}.lbl:first-letter{font-size:9px}
.card{padding:20px 18px}.num{font-size:18px}.meta{font-size:12.5px}}
"""

HEAD_HTML = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@600;700;800&display=swap" rel="stylesheet">"""

def gate_page(error=""):
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(SITE_TITLE)}</title>
{HEAD_HTML}
<style>{CSS}</style></head><body><div class="wrap"><div class="gate"><div class="gbox">
<h1>{html.escape(SITE_TITLE)}</h1><div class="sub">{html.escape(SITE_TAGLINE)}</div>
<form method="POST" action="/login">
<input type="password" name="password" placeholder="Password" autofocus autocomplete="current-password">
<button type="submit">ENTER</button></form>
<div class="err">{html.escape(error)}</div>
</div></div></div></body></html>"""

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
    if s["on_hold"]:
        pill = '<span class="pill hold">ON HOLD</span>'
    elif s["status"] == "Shipped":
        pill = '<span class="pill done">SHIPPED</span>'
    else:
        pill = f'<span class="pill">{html.escape(s["status"].upper())}</span>'

    if s["status"] == "Shipped" and s["shipped"]:
        foot = f'Shipped {html.escape(s["shipped"])}'
        if s["carrier"] and s["tracking"]:
            foot += f' · {html.escape(s["carrier"])} {html.escape(s["tracking"])}'
    elif s["est_start"]:
        foot = f'Expected return: {html.escape(s["est_start"])}'
        if s["est_end"]:
            foot += f' to {html.escape(s["est_end"])}'
    else:
        foot = "Estimate pending"
    if s["grades_ready"]:
        foot += " · grades ready"

    cover = (f'<img class="cover" loading="lazy" src="/img?u={urllib.parse.quote(img_url(s["thumb"], "small"))}" alt="">'
             if s.get("thumb") else '')
    sub = html.escape(s['sub_number'])
    if archived:
        pill += '<span class="pill arch">ARCHIVED</span>'
    archattr = ' data-arch="1" style="display:none"' if archived else ''
    return f"""<div class="card{' arch' if archived else ''}" data-status="{html.escape(s['status'])}"{archattr}>
<div class="top"><div class="hd">{cover}<div><div class="num">#{sub}</div>
<div class="meta">{html.escape(s['service'])} · {s['card_count']} cards</div></div></div><div class="pills">{pill}</div></div>
{timeline_html(s['status'])}
<div class="foot"><span class="est">{foot}</span>
<a class="view" href="/sub/{sub}">View cards →</a></div></div>"""

def search_box(value="", owner=""):
    """Unified people+card search input with a live-preview dropdown (needs SEARCH_JS).
    With owner set, card results are scoped to that person (SEARCH_JS reads data-owner)."""
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
        h+='<a class="pvrow" href="/cards?owner='+encodeURIComponent(n)+'"><span class="pvtag">person</span><span>'+esc(n)+'</span></a>';
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

OWNER_JS = """
<script>
document.querySelectorAll('.own').forEach(function(i){
  i.addEventListener('blur', function(){
    fetch('/owner', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body:'cert_id='+encodeURIComponent(i.dataset.cert)+'&owner='+encodeURIComponent(i.value)})
     .then(function(r){ if(r.ok){ i.classList.add('saved'); setTimeout(function(){i.classList.remove('saved')},900);} });
  });
  i.addEventListener('keydown', function(e){ if(e.key==='Enter') i.blur(); });
});
</script>"""

def card_tile(c, owners, show_sub=False, archived=False, service=""):
    cid = html.escape(str(c["cert_id"]))
    is_prelim = str(c["cert_id"]).startswith("spec:")
    name = html.escape(smart_title(c["name"] or ""))
    owner = html.escape(owners.get(str(c["cert_id"]), ""))
    grade = f'<div class="gr">PSA {html.escape(c["grade"])}</div>' if c.get("grade") else ""
    if is_prelim:
        head = '<div class="cn pre">PRELIM</div>'
    else:
        head = f'<div class="cn">{html.escape(c["cert_no"] or c["cert_id"])}</div>'
    if c.get("front_thumb"):
        src = "/img?u=" + urllib.parse.quote(img_url(c["front_thumb"], "small"))
        big = "/img?u=" + urllib.parse.quote(img_url(c["front_thumb"], "large"))
        img = f'<a href="{big}" target="_blank"><img loading="lazy" src="{src}" alt=""></a>'
    else:
        img = '<div class="ph">NO IMAGE YET</div>'
    sub_link = (f'<a class="sublink" href="/sub/{html.escape(str(c["sub_number"]))}">Go to sub #{html.escape(str(c["sub_number"]))} →</a>'
                if show_sub else "")
    svc = f'<div class="svc">{html.escape(service)}</div>' if (show_sub and service) else ""
    return (f'<div class="gc{" arch" if archived else ""}">{img}{sub_link}{svc}{head}'
            f'<div class="nm">{name}</div>{grade}'
            f'<input class="own" data-cert="{cid}" value="{owner}" placeholder="+ owner name">'
            f'</div>')

def dash_page(a, subs):
    arch = archived_set(a)
    active = [s for s in subs if s["sub_number"] not in arch]
    gone = [s for s in subs if s["sub_number"] in arch]
    body = ("".join(card_html(s) for s in active) + "".join(card_html(s, archived=True) for s in gone)
            or '<div class="empty">No submissions yet.</div>')
    updated = max((s["updated_at"] or "" for s in subs), default="")
    stamp = (updated[:16].replace('T', ' ') + " UTC") if updated else "n/a"
    toolbar = f'<div class="toolbar">{search_box()}</div>'
    filters = (f'<div class="filters"><span class="f farch" id="archtoggle">ARCHIVED · {len(gone)}</span></div>'
               if gone else "")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(SITE_TITLE)}</title>
{HEAD_HTML}
<style>{CSS}</style></head><body><div class="wrap">
<div class="hrow"><div><h1 class="big">{html.escape(SITE_TITLE)}</h1></div>
<div class="synced">LAST REFRESHED<b>{html.escape(stamp)}</b></div></div>
{toolbar}
{filters}
<div id="list">{body}</div>
</div>
<script>
var af=document.getElementById('archtoggle');
if(af)af.addEventListener('click',function(){{
  var on=af.classList.toggle('on');
  document.querySelectorAll('#list .card').forEach(function(c){{
    var a=c.dataset.arch==='1';
    c.style.display=(on?a:!a)?'':'none';
  }});
}});
</script>{SEARCH_JS}</body></html>"""

def eta_badge(s):
    """Top-right ETA badge for the sub detail page: expected return window, or
    ship date + tracking once shipped."""
    if s["status"] == "Shipped" and s["shipped"]:
        note = (f'<span class="estnote">{html.escape(s["carrier"])} {html.escape(s["tracking"])}</span>'
                if s["carrier"] and s["tracking"] else "")
        return f'<div class="synced">SHIPPED<b>{html.escape(s["shipped"])}</b>{note}</div>'
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
        tag = ' · <span style="color:#9d9aab">ARCHIVED</span>'
    else:
        act = f'<button class="archbtn" data-sub="{html.escape(num)}" data-on="1">Archive</button>'
        tag = ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>#{html.escape(num)}</title>
{HEAD_HTML}
<style>{CSS}</style></head><body><div class="wrap">
<div class="foot" style="border:0;padding:0"><a class="view" href="/">← All submissions</a><span class="footacts">{act}</span></div>
<div class="hrow" style="margin-top:14px"><div><h1>#{html.escape(num)}</h1>
<div class="sub">{html.escape(sub['service'].upper())} · {sub['card_count']} CARDS · {html.escape(sub['status'].upper())}{tag}</div></div>
{eta_badge(sub)}</div>
<div class="card" style="margin-top:18px">{timeline_html(sub['status'])}</div>
{body}
</div>{OWNER_JS}{ARCH_JS}</body></html>"""

def people_page(a, owner):
    owners = owners_map(a)
    want = owner.strip().lower()
    cards = [c for c in load_all_cards(a) if owners.get(str(c["cert_id"]), "").lower() == want]
    arch = archived_set(a)
    svc_map = {s["sub_number"]: s["service"] for s in load_subs(a)}
    if cards:
        grid = '<div class="grid">' + "".join(
            card_tile(c, owners, show_sub=True, archived=(c["sub_number"] in arch),
                      service=svc_map.get(c["sub_number"], "")) for c in cards) + "</div>"
    else:
        grid = f'<div class="empty">No cards tagged to “{html.escape(owner)}” yet.</div>'
    total = 0.0
    unpriced = 0
    covered = 0.0
    uncovered = 0
    for c in cards:
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
    ins = (f'<span class="lbl2">INSURED COVERAGE</span><b>${covered:,.0f}{"+" if uncovered else ""}</b>'
           if covered or uncovered else "")
    est = (f'<div class="synced">EST. GRADING COST<b>${total:,.2f}'
           f'{"+" if unpriced else ""}</b>{ins}'
           f'<span class="estnote">base per-card fees · pending PSA upcharges<br>'
           f'coverage = declared value on file with PSA</span></div>') if cards else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(owner)}'s cards</title>
{HEAD_HTML}
<style>{CSS}</style></head><body><div class="wrap">
<a class="view" href="/">← All submissions</a>
<div class="hrow" style="margin-top:14px"><div><h1>{html.escape(owner)}</h1>
<div class="sub">{len(cards)} CARDS WITH {html.escape(a['label'].upper())}</div></div>{est}</div>
<div class="toolbar">{search_box(owner=owner)}</div>
{grid}
</div>{SEARCH_JS}{OWNER_JS}</body></html>"""

def search_page(a, q, owner=""):
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
        svc_map = {s["sub_number"]: s["service"] for s in load_subs(a)}
        grid = '<div class="grid">' + "".join(
            card_tile(c, owners, show_sub=True, archived=(c["sub_number"] in arch),
                      service=svc_map.get(c["sub_number"], "")) for c in res) + "</div>"
    elif ql:
        grid = f'<div class="empty">No cards match “{html.escape(q)}”.</div>'
    else:
        grid = '<div class="empty">Type a card name or number to search.</div>'
    count = f"{len(res)} MATCH" + ("ES" if len(res) != 1 else "") if ql else "ALL CARDS"
    if owner:
        count += f" · {html.escape(owner.upper())}'S CARDS ONLY"
        back = (f'<a class="view" href="/cards?owner={urllib.parse.quote(owner)}">'
                f'← {html.escape(owner)}\'s cards</a>')
    else:
        back = '<a class="view" href="/">← All submissions</a>'
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Search</title>
{HEAD_HTML}
<style>{CSS}</style></head><body><div class="wrap">
{back}
<h1 style="margin-top:14px">Search</h1>
<div class="sub">{count}</div>
<div class="toolbar">{search_box(q or '', owner=owner)}</div>
{grid}
</div>{SEARCH_JS}{OWNER_JS}</body></html>"""

# ---------- server ----------

class H(BaseHTTPRequestHandler):
    server_version = "psa-tracker"

    def log_message(self, fmt, *a):
        print(f"{self.address_string()} {fmt % a}", flush=True)

    def client_ip(self):
        xff = self.headers.get("X-Forwarded-For", "")
        return xff.split(",")[0].strip() if xff else self.address_string()

    def authed(self):
        """Return the account dict this request's session is bound to, or None."""
        raw = self.headers.get("Cookie", "")
        for part in raw.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "psa_session":
                acct_id = valid_token(v)
                if acct_id:
                    return load_accounts().get(acct_id)
        return None

    def send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
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

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        acct = self.authed()
        if not acct:
            return self.send(200, gate_page())
        if path == "/img":
            return self.serve_img(parsed.query)
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
        if path == "/logout":
            return self.send(302, "", extra=[("Location", "/"),
                ("Set-Cookie", "psa_session=; Path=/; Max-Age=0")])
        self.send(404, "not found", "text/plain")

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/owner":
            acct = self.authed()
            if not acct:
                return self.send(403, "auth", "text/plain")
            n = int(self.headers.get("Content-Length", "0") or 0)
            form = urllib.parse.parse_qs(self.rfile.read(min(n, 2048)).decode("utf-8", "replace"))
            cid = (form.get("cert_id") or [""])[0]
            owner = (form.get("owner") or [""])[0]
            if cid:
                set_owner(acct, cid, owner)
            return self.send(204, "", "text/plain")
        if path == "/archive":
            acct = self.authed()
            if not acct:
                return self.send(403, "auth", "text/plain")
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
        if not matched:
            login_fail(ip)
            return self.send(200, gate_page("Incorrect password."))
        login_ok(ip)
        exp = int(time.time()) + COOKIE_DAYS * 86400
        cookie = (f"psa_session={make_token(matched['id'], exp)}; Path=/; Max-Age={COOKIE_DAYS*86400}; "
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
