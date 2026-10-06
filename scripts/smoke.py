#!/usr/bin/env python3
"""Boot app.py against a throwaway fixture and GET every route.

Stdlib only, no network, no box. Builds a temp accounts dir (two account.env
files, a psa.db carrying psa_watch/psa_values' own schema plus a handful of synthetic
rows; owners.db is left for the app to create), starts app.py on a free port,
then asserts each route answers the expected status with a non-empty body, for
no session and for a logged-in session. Exits 1 on the first failure, naming
the route.

  python3 scripts/smoke.py
"""
import csv, datetime, gzip, hashlib, json, os, re, shutil, signal, socket, sqlite3
import subprocess, sys, tempfile, time, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_PW = "smoke-site-pw"
SET_PW = "smoke-settings-pw"
SET_HASH = hashlib.sha256(SET_PW.encode()).hexdigest()
HUB_KEY = "smoke-hub-key"
CADENCE = "Changes apply at the next sync, within about 20 minutes."
MAX_FAILS = 8  # app.py's login budget: a hard per-IP pause, site-wide a delay
NOW = "2026-01-01T00:00:00+00:00"
# ETA dates are relative to the run: one still to come, one next year (the year
# has to print), one PSA has blown through (T65)
TODAY = datetime.date.today()
ETA_SOON = TODAY + datetime.timedelta(days=45)
ETA_NEXT_YEAR = datetime.date(TODAY.year + 1, 6, 15)
ETA_PAST = TODAY - datetime.timedelta(days=45)


def eta_text(d):
    """What short_date must print for a date: 'Sep 25', 'Jun 15, 2027'."""
    return f"{d:%b} {d.day}" + (f", {d.year}" if d.year != TODAY.year else "")
# a pre-seeded proxy cache entry, so /img answers from disk and the run stays offline
IMG_URL = "https://d1htnxwo4o0jhw.cloudfront.net/thumbnail/99000001.jpg"


def schema(mod):
    src = open(os.path.join(ROOT, mod), encoding="utf-8").read()
    return re.search(r'SCHEMA = """(.*?)"""', src, re.S).group(1)


def build_fixture(base):
    """Two accounts: demo carries the rows (a graded sub and an in-flight one),
    second is empty and exists so the settings scoping can be checked."""
    acct = os.path.join(base, "accounts", "demo")
    os.makedirs(acct)
    os.makedirs(os.path.join(base, "imgcache"))
    other = os.path.join(base, "accounts", "second")
    os.makedirs(other)
    with open(os.path.join(other, "account.env"), "w", encoding="utf-8") as f:
        f.write(f"LABEL='Second Store'\nSITE_PASSWORD='{SITE_PW}-2'\n"
                "PSA_LOGIN_EMAIL='second@example.com'\nPSA_LOGIN_PW='x'\n"
                "PSA_COOKIE='fake'\n")
    c2 = sqlite3.connect(os.path.join(other, "psa.db"))
    c2.executescript(schema("psa_watch.py"))
    c2.executescript(schema("psa_values.py"))
    c2.commit()
    c2.close()
    with open(os.path.join(acct, "account.env"), "w", encoding="utf-8") as f:
        # the fee table is listed least-specific first on purpose: matching is
        # by longest key, so the order must not change a single price (T73)
        f.write(f"LABEL='Smoke Store'\nSITE_PASSWORD='{SITE_PW}'\n"
                "PSA_LOGIN_EMAIL='smoke@example.com'\nPSA_LOGIN_PW='x'\n"
                "PSA_PRICES='value:45.99,bulk:34.99,value max:89.99,regular:109'\n"
                "PSA_COOKIE='fake'\n")
    open(os.path.join(base, "global.env"), "w").close()
    c = sqlite3.connect(os.path.join(acct, "psa.db"))
    c.executescript(schema("psa_watch.py"))
    c.executescript(schema("psa_values.py"))
    subs = [("14900001", "Completing", 2, "2026-09-10", "", 1, 0,
             ETA_NEXT_YEAR - datetime.timedelta(days=7), ETA_NEXT_YEAR),
            ("14900002", "Arrived", 1, "", "", 0, 1, ETA_SOON, ETA_SOON),
            # a step the stage map does not know (T19), and an ETA PSA has
            # already blown through (T65)
            ("14900003", "ReceivedHold", 1, "", "", 0, 0, ETA_PAST, ETA_PAST),
            # shipped with an ISO date, not PSA's mm/dd/yy (T183)
            ("14900004", "Shipped", 1, "2026-09-06", "", 1, 0, ETA_PAST, ETA_PAST)]
    for num, status, cnt, shipped, tracking, ready, hold, est1, est2 in subs:
        c.execute("INSERT INTO subs (sub_number, order_number, service, status, "
                  "card_count, destination, arrived, est_start, est_end, shipped, "
                  "tracking, carrier, grades_ready, on_hold, thumb, cert_ids, "
                  "first_seen, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (num, "O-" + num, "Regular", status, cnt, "Ship back", "2026-08-01",
                   est1.isoformat(), est2.isoformat(), shipped, tracking, "UPS", ready, hold,
                   "", json.dumps([]), NOW, NOW))
        c.execute("INSERT INTO status_history (sub_number, status, seen_at) VALUES (?,?,?)",
                  (num, status, NOW))
    # front_thumb is PSA's own thumbnail asset: what the scanner stores and what
    # the filmstrip must serve unrewritten (T20)
    thumb = "https://d1htnxwo4o0jhw.cloudfront.net/thumbnail/%s.jpg"
    cards = [("99000001", "14900001", "99000001", "Charizard 4/102 Base Set Holo", 1, "10"),
             ("99000002", "14900001", "99000002", "Pikachu VMAX 044/185", 2, "9"),
             ("spec:14900002:1", "14900002", "", "Umbreon VMAX 215/203", 1, "")]
    # nine imaged cards on one sub, so its filmstrip overflows STRIP_MAX and
    # renders the "+N" chip the overflow-naming check needs (T56)
    cards += [("9700000%d" % i, "14900003", "9700000%d" % i,
               "Snorlax %d/165" % i, i, "") for i in range(1, 10)]
    for cid, num, cert_no, name, line, grade in cards:
        c.execute("INSERT INTO cards (cert_id, sub_number, cert_no, name, line_number, "
                  "front_thumb, back_thumb, grade, declared_value, updated_at) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (cid, num, cert_no, name, line, thumb % cid.replace(":", "-"),
                   "", grade, 120.0, NOW))
    # three value rows for the dashboard total (T27): an estimate, a sale-only
    # row (the fallback), and one whose cert never landed in this account
    values = [("99000001", 310.0, 290.0), ("99000002", None, 150.0),
              ("99009999", 999.0, 999.0)]
    for cert_no, est, sale in values:
        c.execute("INSERT INTO card_values (cert_no, estimate, last_sale, last_sale_date, "
                  "n_sales, sales_json, fetched_at, error) VALUES (?,?,?,?,?,?,?,?)",
                  (cert_no, est, sale, "2026-08-15", 3,
                   json.dumps([{"price": sale, "date": "2026-08-15"}]), NOW, ""))
    c.execute("INSERT INTO fx_rates (pair, rate, fetched_at) VALUES ('USDCAD',1.36,?)", (NOW,))
    c.commit()
    c.close()
    with open(os.path.join(base, "imgcache",
                           hashlib.sha256(IMG_URL.encode()).hexdigest() + ".jpg"), "wb") as f:
        f.write(b"\xff\xd8\xff\xdb" + b"\x00" * 64)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


STYLE_ATTR = re.compile(rb'style=\\?"([^"\\]*)')
STYLE_OK = {b"display:none", b"vertical-align:middle"}
STYLE_DYN = re.compile(rb"width:\d+(\.\d)?%|--i:\d+")


def boot(base, port, log, gear="1"):
    env = dict(os.environ, PSA_SETTINGS_GEAR=gear or "",
               PSA_PORT=str(port), PSA_BIND="127.0.0.1", PSA_COOKIE_SECURE="0",
               PSA_SECRET="smoke-secret-not-real", PSA_SETTINGS_PW_HASH=SET_HASH,
               PSA_ACCOUNTS_DIR=os.path.join(base, "accounts"),
               PSA_GLOBAL_ENV=os.path.join(base, "global.env"),
               PSA_IMG_CACHE=os.path.join(base, "imgcache"),
               PSA_LOGO=os.path.join(ROOT, "logo.svg"),
               PSA_FAVICON=os.path.join(ROOT, "favicon.png"),
               PSA_TOUCH_ICON=os.path.join(ROOT, "apple-touch-icon.png"),
               PSA_HUB_KEY=HUB_KEY, PSA_VALUES="1", PSA_THEME="light")
    if gear is None:
        del env["PSA_SETTINGS_GEAR"]
    p = subprocess.Popen([sys.executable, os.path.join(ROOT, "app.py")], env=env,
                         cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(100):
        if p.poll() is not None:
            return p
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            return p
        except OSError:
            time.sleep(0.1)
    return p


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def call(base_url, path, cookie=None, form=None, headers=None):
    """-> (status, body bytes, headers). Raises on a dropped connection."""
    data = urllib.parse.urlencode(form).encode() if form else None
    r = urllib.request.Request(base_url + path, data=data)
    if cookie:
        r.add_header("Cookie", cookie)
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    try:
        with OPENER.open(r, timeout=30) as resp:
            return resp.status, resp.read(), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


def keepalive_checks(port, fails):
    """One socket, two pipelined GETs: HTTP/1.1 must answer both without closing
    in between. A POST is the exception, it says Connection: close, because its
    body is read up to a cap and the rest would look like a next request (T22)."""
    s = socket.create_connection(("127.0.0.1", port), 10)
    s.settimeout(10)
    try:
        s.sendall(b"GET /api/hub.json HTTP/1.1\r\nHost: smoke\r\n\r\n"
                  b"GET /api/hub.json HTTP/1.1\r\nHost: smoke\r\nConnection: close\r\n\r\n")
        buf = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    finally:
        s.close()
    if buf.count(b"HTTP/1.1 404") != 2:
        fails.append("pipelined GETs: one connection did not carry two replies")

    s = socket.create_connection(("127.0.0.1", port), 10)
    s.settimeout(10)
    try:
        body = b"x=1"  # a path that 404s without reading the body: the worst case
        s.sendall(b"POST /nope HTTP/1.1\r\nHost: smoke\r\nContent-Type: "
                  b"application/x-www-form-urlencoded\r\nContent-Length: "
                  + str(len(body)).encode() + b"\r\n\r\n" + body)
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = s.recv(4096)
            if not chunk:
                break
            head += chunk
    finally:
        s.close()
    if b"Connection: close" not in head.split(b"\r\n\r\n", 1)[0]:
        fails.append("POST /nope: the reply does not close the connection")


def copy_checks(fails):
    """One typographic vocabulary in the shipped copy: no em dash anywhere, the
    curly ’ is the only apostrophe encoding (T66), one name for the settings
    password and one word for the PSA fetch (T67)."""
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    for dash in ("—", "\\u2014"):
        if dash in src:
            fails.append("app.py: an em dash is back in the copy")
    for ent in ("&#39;", "&#x27;", "&apos;", "&rsquo;", "&#8217;", "\\u2019"):
        if ent in src:
            fails.append(f"app.py: {ent} is a second apostrophe encoding")
    for phrase in ("Admin password", "admin password"):
        if phrase in src:
            fails.append(f"app.py: {phrase!r} is back, the panel is the settings password")
    for phrase in ("Last refreshed", "hourly scan", "Scans are", "scans stop"):
        if phrase in src:
            fails.append(f"app.py: {phrase!r} calls the sync something else")
    for phrase in ("1am", "1pm"):
        if phrase in src:
            fails.append(f"app.py: {phrase!r} is back, the scan timer is not a clock (T68)")
    if "hourly" in src.lower():
        fails.append("app.py: 'hourly' is back, scans run every 9 to 22 minutes (T163)")
    if src.count(CADENCE) < 3:
        fails.append("app.py: settings, setup and the first sync note must all say "
                     f"{CADENCE!r} (T163)")


def env_checks(fails):
    """Knobs nothing sets are constants, not os.environ lookups (T83), and the
    retired logo blend and settings label class stay deleted (T84)."""
    for mod, names in (("app.py", ("COOKIE_DAYS", "PSA_SETTINGS_MINUTES")),
                       ("psa_watch.py", ("PSA_ORDERS_URL", "PSA_SPEC_DEPT_ID"))):
        src = open(os.path.join(ROOT, mod), encoding="utf-8").read()
        for name in names:
            if f'"{name}"' in src:
                fails.append(f"{mod}: {name} is read from the env again, "
                             "it is a dead knob (T83)")
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    for name in ("logoblend", "mix-blend-mode", ".slbl"):
        if name in src:
            fails.append(f"app.py: {name} is back, it is retired styling (T84)")


def accent_checks(fails):
    """A store that sets only PSA_ACCENT gets --ac2 in the same hue, both set
    keep both, neither keeps the steel blue pair, and no WARNING prints (T182)."""
    for env, want in (({}, "#5b8def"), ({"PSA_ACCENT": "#2e8b57"}, "#2e8b57"),
                      ({"PSA_ACCENT": "#2e8b57", "PSA_ACCENT_2": "#ffcc00"}, "#ffcc00")):
        e = {k: v for k, v in os.environ.items() if not k.startswith("PSA_ACCENT")}
        e.update(env)
        out = subprocess.run([sys.executable, "-c", "import app;print(app.THEME_VARS)"],
                             cwd=ROOT, env=e, capture_output=True, text=True).stdout
        if f"--ac2:{want};" not in out or "WARNING" in out:
            fails.append(f"--ac2 with {env or 'no accent env'}: want {want} (T182)")


def barmuted_checks(fails):
    """The held/archived bar has its own token in both palettes, quieter than
    the accent --bar on the track (lighter in light, darker in dark), 2.5-3:1 (T148)."""
    code = ("import app\n"
            "for name, pal, pole, track in (('light', app._LIGHT, app._BLACK, app._TRACK_LIGHT),"
            " ('dark', app._DARK, app._WHITE, app._TRACK_DARK)):\n"
            " acmix = app._AC_MIX_L if name == 'light' else app._AC_MIX_D\n"
            " bar = app._mix(app._AC_RGB, pole, int(acmix['--bar'].split('%')[0]))\n"
            " m = app._rgb(pal['barmuted'])\n"
            " c = app._contrast(m, track)\n"
            " lighter = app._lum(m) > app._lum(bar)\n"
            " ok = 2.5 <= c < 3.0 and lighter == (name == 'light') and app.THEME_VARS.count('--barmuted:') == 3\n"
            " print(name, 'ok' if ok else f'bad {c:.2f}')\n")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True).stdout
    if out.split() != ["light", "ok", "dark", "ok"] or "WARNING" in out:
        fails.append(f"--barmuted: {out.strip() or 'no output'} (T148)")


def day_checks(fails):
    """A UTC seen_at late in the Toronto evening counts as that local day (T130)."""
    code = ("import os\nos.environ['PSA_DISPLAY_TZ']='America/Toronto'\nimport app\n"
            "print(app._day('2026-09-12T03:00:00+00:00'), app._day('07/21/26'), app._day(''))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True).stdout
    if out.split()[-3:] != ["2026-09-11", "2026-07-21", "None"]:
        fails.append(f"_day: {out.strip() or 'no output'} (T130)")


def well_checks(fails):
    """The scan well is one opaque colour per palette and the PSA 10 chip clears
    4.5:1 on its tint over that well in both (T119)."""
    sys.path.insert(0, ROOT)
    import app
    for name, pal in (("light", app._LIGHT), ("dark", app._DARK)):
        if not pal["surface3"].startswith("#"):
            fails.append(f"app.py: {name} --surface3 is translucent again (T119)")
            continue
        g = app._rgb(pal["grade"])
        c = app._contrast(g, app._over(g, 0.14, app._rgb(pal["surface3"])))
        if c < 4.5:
            fails.append(f"app.py: {name} PSA 10 chip is {c:.2f}:1 on the well (T119)")


def scrim_checks(fails):
    """One --scrim token, two palette values: light .4, dark .62 (T139)."""
    sys.path.insert(0, ROOT)
    import app
    for name, pal, want in (("light", app._LIGHT, "rgba(0,0,0,.4)"),
                            ("dark", app._DARK, "rgba(0,0,0,.62)")):
        if pal["scrim"] != want:
            fails.append(f"app.py: {name} --scrim is {pal['scrim']}, want {want} (T139)")


def common_checks(fails):
    """log, notify and env_set live in psa_common.py only, every caller imports
    them, and deploy.sh ships the file beside app.py (T86)."""
    for mod in ("app.py", "psa_watch.py", "psa_login.py", "psa_values.py"):
        src = open(os.path.join(ROOT, mod), encoding="utf-8").read()
        if "psa_common" not in src:
            fails.append(f"{mod}: does not use psa_common (T86)")
        for name in ("notify", "env_set", "log"):
            if f"def {name}(" in src:
                fails.append(f"{mod}: defines {name} again, psa_common owns it (T86)")
    if "psa_common.py" not in open(os.path.join(ROOT, "deploy.sh"), encoding="utf-8").read():
        fails.append("deploy.sh: does not ship psa_common.py (T86)")
    sys.path.insert(0, ROOT)
    import psa_common
    envf = os.path.join(tempfile.mkdtemp(prefix="psa-smoke-env-"), "account.env")
    open(envf, "w", encoding="utf-8").write("# keep\nLABEL='Demo'\nPSA_COOKIE='old'\n")
    psa_common.env_set(envf, {"PSA_COOKIE": "a b'c"})
    psa_common.env_set(envf, {"LABEL": ""})
    got = open(envf, encoding="utf-8").read()
    want = "# keep\nPSA_COOKIE='a b'\"'\"'c'\n"
    if got != want:
        fails.append(f"psa_common.env_set: wrote {got!r}, want {want!r}")
    if oct(os.stat(envf).st_mode & 0o777) != "0o600":
        fails.append("psa_common.env_set: env file is not chmod 600")


def tracking_checks(fails):
    """An unrecognized carrier whose tracking field only repeats it says the
    word once, a real carrier plus number still says both (T69)."""
    sys.path.insert(0, ROOT)
    import app
    for carrier, tracking, want in (("Pickup", "pickup", "Pickup"),
                                    ("LM", "LM-88213", "LM LM-88213"),
                                    ("Loomis", "LM-88213", "Loomis LM-88213"),
                                    ("UPS", "1Z999AA10123456784",
                                     "UPS 1Z999AA10123456784")):
        got = app.tracking_html(carrier, tracking)
        if re.sub(r"<[^>]+>", "", got) != want:
            fails.append(f"tracking_html({carrier!r}, {tracking!r}): said {got!r}, "
                         f"want {want!r}")


def leading_checks(fails):
    """No rule leaves leading to the UA's normal, and every 14px rule that states a
    leading states the body rung's 1.5 (T179)."""
    src = open(os.path.join(ROOT, "app.py")).read()
    if "line-height:normal" in src:
        fails.append("app.py: line-height:normal is back (T179)")
    for rule in re.findall(r"[^{}]*\{[^{}]*font-size:14px[^{}]*\}", src):
        lh = re.search(r"line-height:([^;}]+)", rule)
        if lh and lh.group(1).strip() != "1.5":
            fails.append(f"app.py: a 14px rule leads at {lh.group(1)}, not 1.5 (T179): "
                         f"{rule.strip()[:60]!r}")
    for sel in ("input{", "button{"):
        rule = src[src.index("\n" + sel):].split("}", 1)[0]
        if "line-height:1.5" not in rule:
            fails.append(f"app.py: {sel[:-1]} leaves leading to the UA's normal (T179)")


def hit_checks(fails):
    """The narrowest controls reach 44x44 through a hit pseudo or padding that
    leaves the painted layout alone (T187). Measured at 390x844 in Playwright
    (/tmp/psa-fix/T187/measure.py); this pins the CSS that does it."""
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    for want, what in ((".ownedit::before{content:'';position:absolute;inset:0 -2px}", ".ownedit"),
                       (".undo::before{content:'';position:absolute;inset:-2px 0}", ".undo"),
                       (".sbtn.squiet::before{content:'';position:absolute;inset:-2px 0}", ".squiet"),
                       ("min-width:44px;text-align:left", "the settings Save"),
                       ("padding:22px 0 0;margin-top:1px", ".own"),
                       ("padding-block:8px}", "the sub-360 sort capsule")):
        if want not in src:
            fails.append(f"app.py: {what} lost its 44px hit area (T187)")


def desk_checks(fails):
    """Above 1024px the sheet stays 820 and the strip and detail grid grow
    inside it (T188)."""
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    if ".wrap{max-width:820px;" not in src:
        fails.append("app.py: the sheet is no longer 820px (T188)")
    blk = src.split("@media(min-width:1025px){", 1)[-1].split("}}", 1)[0]
    if "width:110px;height:153px" not in blk or "minmax(240px,1fr)" not in blk:
        fails.append("app.py: the desktop strip or detail grid did not grow (T188)")


def comment_checks(fails):
    """Comments name what sits beside them: the reading rung is 14px, the gate
    card and the settings panel count are not pinned to a stale number, and
    psa_login points at the account env file, not the global one (T96)."""
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    for phrase in ("Four panels", "five panels", "300px", "13/400",
                   "13px text actions"):
        if phrase in src:
            fails.append(f"app.py: {phrase!r} is a stale comment (T96)")
    doc = open(os.path.join(ROOT, "psa_login.py"), encoding="utf-8").read().split('"""')[1]
    if "account.env" not in doc:
        fails.append("psa_login.py: the docstring does not name account.env (T96)")
    if "Env (from /etc/psa-tracker.env)" in doc:
        fails.append("psa_login.py: the docstring still sends account secrets to "
                     "the global env (T96)")


def shot_checks(fails):
    """A Discord card shot is never blank (T194): the context kills the rise
    animation, the lazy strip scans are forced eager and waited for, and a card
    that is still unpainted or too short exits non-zero instead of writing a
    file. Playwright is not installed here, so this reads the source."""
    src = open(os.path.join(ROOT, "psa_shot.py"), encoding="utf-8").read()
    for want, why in ((' reduced_motion="reduce"', "does not disable the rise animation"),
                      ("i.loading = 'eager'", "does not force the lazy scans eager"),
                      ("i.complete && i.naturalWidth > 0", "does not wait for the scans"),
                      ("page.wait_for_function", "does not wait for the scans"),
                      ('box["height"] < 100', "does not reject a collapsed card")):
        if want not in src:
            fails.append(f"psa_shot.py: {why} ({want!r} missing) (T194)")
    if "wait_for_timeout" in src:
        fails.append("psa_shot.py: still shoots on a fixed timer (T194)")
    if src.index("card.screenshot") < src.index("page.wait_for_function"):
        fails.append("psa_shot.py: screenshots before waiting for the scans (T194)")


def gear_mode_checks(fails):
    """Personal mode ships by default: unset means no gear and /settings asks
    for the settings password; =1 brings the store gear back (T124)."""
    base = tempfile.mkdtemp(prefix="psa-smoke-gear-")
    log = open(os.path.join(base, "app.log"), "w")
    build_fixture(base)
    proc = None
    try:
        for gear in (None, "1"):
            label = "PSA_SETTINGS_GEAR " + ("unset" if gear is None else "=" + gear)
            port = free_port()
            url = f"http://127.0.0.1:{port}"
            proc = boot(base, port, log, gear)
            if proc.poll() is not None:
                fails.append(f"{label}: app.py did not start")
                return
            _, _, hdrs = call(url, "/login", form={"password": SITE_PW})
            cookie = (hdrs.get("Set-Cookie") or "").split(";")[0]
            _, body, _ = call(url, "/", cookie)
            _, sbody, _ = call(url, "/settings", cookie)
            orb, gate = b'id="gearbtn"' in body, b"Enter the settings password" in sbody
            if gear is None and (orb or not gate):
                fails.append(f"{label}: gear orb {orb}, settings gate {gate}; want no orb, gate")
            if gear and (not orb or gate or b"PSA accounts" not in sbody):
                fails.append(f"{label}: gear orb {orb}, settings gate {gate}; want orb, open")
            proc.send_signal(signal.SIGTERM)
            proc.wait(5)
            proc = None
    finally:
        if proc and proc.poll() is None:
            proc.kill()
        log.close()
        shutil.rmtree(base, ignore_errors=True)


def setup_instance_checks(fails):
    """An instance whose single account has never connected: the setup form is
    the owner's retry, not a public takeover, and an account.env that stops
    parsing must not reopen it after a restart (T18)."""
    base = tempfile.mkdtemp(prefix="psa-smoke-setup-")
    log = open(os.path.join(base, "app.log"), "w")
    acct = os.path.join(base, "accounts", "solo")
    os.makedirs(acct)
    os.makedirs(os.path.join(base, "imgcache"))
    envf = os.path.join(acct, "account.env")
    with open(envf, "w", encoding="utf-8") as f:
        f.write(f"LABEL='Solo'\nSITE_PASSWORD='{SITE_PW}'\n"
                "PSA_LOGIN_EMAIL='solo@example.com'\nPSA_LOGIN_PW='x'\nPSA_COOKIE=''\n")
    c = sqlite3.connect(os.path.join(acct, "psa.db"))
    c.executescript(schema("psa_watch.py"))
    c.executescript(schema("psa_values.py"))
    c.commit()
    c.close()
    open(os.path.join(base, "global.env"), "w").close()
    takeover = {"label": "Mallory", "site_pw": "mallory-pw",
                "psa_email": "mallory@example.com", "psa_pw": "x"}
    proc = None
    try:
        for label, want_form in (("never connected", True), ("broken account.env", False)):
            port = free_port()
            url = f"http://127.0.0.1:{port}"
            proc = boot(base, port, log)
            if proc.poll() is not None:
                fails.append(f"setup instance ({label}): app.py did not start")
                return
            was = open(envf, "rb").read()
            code, _, _ = call(url, "/setup")
            if code != 302:
                fails.append(f"GET /setup ({label}, no session): got {code}, want 302")
            code, _, _ = call(url, "/setup", form=takeover)
            if code != 403:
                fails.append(f"POST /setup ({label}, no session): got {code}, want 403")
            if open(envf, "rb").read() != was:
                fails.append(f"POST /setup ({label}, no session): account.env was rewritten")
            if want_form:  # the owner can still re-enter their PSA login
                _, _, hdrs = call(url, "/login", form={"password": SITE_PW})
                cookie = (hdrs.get("Set-Cookie") or "").split(";")[0]
                code, body, _ = call(url, "/setup", cookie)
                if code != 200 or b'action="/setup"' not in body:
                    fails.append(f"GET /setup (owner session): got {code}, the retry form is gone")
                if CADENCE.encode() not in body:
                    fails.append("GET /setup: the setup note lost the sync cadence (T163)")
                code, body, _ = call(url, "/", cookie)
                if code != 200 or CADENCE.encode() not in body:
                    fails.append(f"GET / (never synced): got {code}, the first sync note "
                                 "lost the sync cadence (T163)")
                if b">No sync yet<" not in body:
                    fails.append("GET / (never synced): an empty account lost No sync yet (T162)")
                # while psa-scan runs, the empty page pulses and reloads itself every
                # 30 s instead of asking for a reload (T202); a fake systemctl says active
                fake = os.path.join(base, "bin")
                os.makedirs(fake, exist_ok=True)
                with open(os.path.join(fake, "systemctl"), "w") as f:
                    f.write("#!/bin/sh\necho active\n")
                os.chmod(os.path.join(fake, "systemctl"), 0o755)
                proc.send_signal(signal.SIGTERM)
                proc.wait(5)
                path, port = os.environ["PATH"], free_port()
                url = f"http://127.0.0.1:{port}"
                os.environ["PATH"] = fake + os.pathsep + path
                try:
                    proc = boot(base, port, log)
                finally:
                    os.environ["PATH"] = path
                _, _, hdrs = call(url, "/login", form={"password": SITE_PW})
                body = call(url, "/", (hdrs.get("Set-Cookie") or "").split(";")[0])[1] or b""
                if (b'<meta http-equiv="refresh" content="30">' not in body
                        or b'<span class="waitdot" aria-hidden="true"></span>First sync' not in body
                        or b"Reload in a minute" in body):
                    fails.append("GET / (first sync running): no wait dot or self refresh (T202)")
            proc.send_signal(signal.SIGTERM)
            proc.wait(5)
            proc = None
            with open(envf, "w", encoding="utf-8") as f:  # what a newline used to leave
                f.write("LABEL='Solo'\nSITE_PASSWORD='bad\n")
    finally:
        if proc and proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
        log.close()
        shutil.rmtree(base, ignore_errors=True)


def main():
    base = tempfile.mkdtemp(prefix="psa-smoke-")
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    fails = []
    logpath = os.path.join(base, "app.log")
    log = open(logpath, "w")
    proc = None
    try:
        build_fixture(base)
        proc = boot(base, port, log)
        if proc.poll() is not None:
            log.close()
            print("FAIL  app.py did not start:\n" + open(logpath).read().strip())
            return 1

        def check(label, path, want, cookie=None, form=None, must_have=None,
                  headers=None):
            try:
                code, body, _ = call(url, path, cookie, form, headers)
            except Exception as e:  # dropped connection = a crashed handler
                fails.append(f"{label}: no reply ({e.__class__.__name__}: {e})")
                return b""
            if code not in want:
                fails.append(f"{label}: got {code}, want {'/'.join(map(str, want))}")
            elif code == 200 and not body:
                fails.append(f"{label}: 200 with an empty body")
            elif must_have and must_have.encode() not in body:
                fails.append(f"{label}: 200 but missing {must_have!r}")
            return body

        # --- no session: every page is the gate, assets are public
        check("GET / (no session)", "/", (200,), must_have='action="/login"')
        # the gate says who has the password, always, not only after an error (T115)
        check("GET / (gate hint)", "/", (200,), must_have="Ask the store for the password.")
        # the gate field rests without the focus ring; only a retry after an
        # error lands focused. The error line reserves its full 18px line box so
        # the card never grows, and the bottom pad gives that line back (T169)
        if b"autofocus" in check("GET / (gate rests unfocused)", "/", (200,)):
            fails.append("GET /: the gate autofocuses, so its field never shows a rest state (T169)")
        check("GET /sub/14900001 (no session)", "/sub/14900001", (200,))
        check("GET / (bad token)", "/", (200,), cookie="psa_session=nope.nope.nope",
              must_have='action="/login"')
        css = check("GET /app.css", "/app.css", (200,))
        js = check("GET /app.js", "/app.js", (200,))
        # the sheet every browser downloads is CSS, not an essay. Source comments
        # are stripped when the served copy is built, so this caps the RULES, not
        # the prose - app.py may explain itself at length (T82, T112)
        if css and (b"min-height:18px}" not in css.split(b".err{", 1)[-1][:120]
                    or b".gbox:has(>.err){padding-bottom:14px}" not in css):
            fails.append("GET /app.css: the gate card is not balanced around its error line (T169)")
        if css and len(css) >= 40000:
            fails.append(f"GET /app.css: {len(css)} bytes, want under 40000")
        # a scan that 404s is swapped for the no-scan placeholder, anchor and
        # all, so the grid keeps its rhythm and the dead tile cannot open the
        # lightbox. A broken image reports .complete, hence the naturalWidth
        # test on the synchronous path (T62)
        if js:
            if b"m.naturalWidth" not in js:
                fails.append("GET /app.js: a broken scan is treated as loaded again")
            if b"replaceChild(d,t)" not in js or b"'No image yet'" not in js:
                fails.append("GET /app.js: a failed scan no longer shows the placeholder")
            # a dead strip thumb keeps the strip's height as an empty chip, and
            # a loading scan fades in rather than popping (T197)
            if b"'morechip dead'" not in js or b"classList.add('pend')" not in js:
                fails.append("GET /app.js: dead strip thumbs collapse or scans pop in")
            # an owner save marks itself in the underline after 300 ms and its chip
            # takes the pencil's place inside the row, so no tile grows (T201)
            if (b"i.classList.add('saving'); },300)" not in js
                    or b"row.appendChild(u);" not in js
                    or (css and (b".own.saving{border-bottom-color:var(--m1)}" not in css
                                 or b".ownrow:has(.undo) .ownedit{display:none}" not in css))):
                fails.append("GET /app.js: an owner save can move the grid (T201)")
            # on the unassigned worklist Enter hands focus straight to the next
            # untagged field, never via body, so nine tags are one pass (T190)
            if (b"if(_pg===''&&i.value.trim()&&!coarse){" not in js
                    or b"if(nx){ nx.readOnly=false; nx.focus(); } else { i.blur(); refocus(); }"
                    not in js):
                fails.append("GET /app.js: Enter on the worklist does not open the next untagged tag (T190)")
        if css:
            if (b".morechip.dead{background:var(--sk)}" not in css
                    or b'.strip a[href^="/img"].ldg::after' not in css
                    or b".gc:nth-child" in css):
                fails.append("GET /app.css: the calm loading ground or sweep is gone (T197)")
            # the compact bar bleeds its 8px padding + 1px border, so the field sits
            # on the h1's edge; the dashboard header keeps its own inset (T143)
            if (b".toolbar.tbq{padding:7px 8px;border-radius:14px;margin-inline:-9px}" not in css
                    or b"margin:16px 0 4px;padding:12px 14px;" not in css):
                fails.append("GET /app.css: the search field is off the page margin (T143)")
            # a ground band under the stuck bar hides the row in the gap and corners;
            # only once raised, so the resting page keeps its top links (T176)
            if (b"html:has(.toolbar.raised)::before{content:'';position:fixed;top:0;left:0;right:0;"
                    b"height:26px;z-index:19;" not in css
                    or b"html:has(header.toolbar.raised)::before{height:10px}" not in css):
                fails.append("GET /app.css: the gap above the stuck toolbar is unmasked (T176)")
            # dark lifts the toolbar mark so its card planes stay apart; light is a no-op (T177)
            _, gate, _ = call(url, "/")
            if (b".toolbar .logo:not(.sil,.chip){filter:var(--logotb)}" not in css
                    or b'--logotb:none;' not in gate
                    or b'--logotb:contrast(1.3) brightness(1.15) saturate(.8);' not in gate):
                fails.append("GET /app.css: the dark toolbar logo loses a card plane (T177)")
            # motion runs on three durations and two easings, every transition names
            # both; the row stagger is --i, and the bar runs out on scaleX (T178)
            trans = re.findall(rb"transition:([^;}]*)", css)
            loose = [t for t in trans if t != b"none" and any(
                not p.strip().startswith(b"visibility") and not (b"var(--t" in p and b"var(--e" in p)
                for p in re.split(rb",(?![^(]*\))", t))]
            if (re.search(rb"\bease\b(?!-)|ease-out|cubic-bezier", css) or loose
                    or re.search(rb"\.card:nth-child\(\d", css)
                    or b"animation-delay:calc(var(--i,0)*.04s)" not in css
                    or b"transform-origin:left;\n transition:transform var(--t3) var(--e2)" not in css
                    and b"transform-origin:left; transition:transform var(--t3) var(--e2)" not in css
                    or b"--t1:.15s;--t2:.25s;--t3:.55s;--e1:ease-out;" not in gate):
                fails.append(f"GET /app.css: motion is off its tokens or the bar lays out (T178) {loose[:2]}")
            if js and (b"style.transform='scaleX(0)'" not in js or b"style.width='0%'" in js):
                fails.append("GET /app.js: the stage bar run-out animates width again (T178)")
            # a grid on the page ground takes the card plane, light's well is the ground (T119)
            if b".wrap>.grid .gc{background:var(--surface)}" not in css:
                fails.append("GET /app.css: tiles on the page ground melt into it (T119)")
            # the tile's bottom space is the well's 10px, matching the scan's top, and the
            # chip's label sits on the name's edge, its rim in the gutter (T174)
            if (b"margin:8px 0 0 -8px;min-height:21px}" not in css
                    or b"padding:22px 0 0;margin-top:1px;flex:1;" not in css
                    or b" .gc>.gr{margin:0}" not in css):
                fails.append("GET /app.css: scan tile unbalanced or chip off the text column (T174)")
            # under 360 a tile is a list row, scan floated left of its text (T173)
            if b" .gc{display:flow-root;padding-left:78px}\n .gc>:first-child{float:left;width:56px;" not in css.split(b"@media(max-width:359px){", 1)[-1]:
                fails.append("GET /app.css: the sub-360 card grid is not a list (T173)")
        # taps and submits show they are working: a guarded nav bar, one POST per
        # form, a busy submitter, all cleared on back/forward restore (T198)
        gate = check("GET / (gate nav bar)", "/", (200,), must_have="window.psaNav=function")
        if js and gate:
            for want in (b"if(window.psaNav)return;", b"if(f.dataset.sent){e.preventDefault();return;}",
                         b"s.classList.add('busy')", b"addEventListener('pageshow'",
                         b"if(window.psaNav)psaNav();", b".catch(function(){done(false);})"):
                if want not in js:
                    fails.append(f"GET /app.js: {want.decode()!r} missing (T198)")
        if css and (b"html.navw body::after" not in css or b".busy{" not in css
                    or b".view:active,.numlink:active{opacity:.6}" not in css):
            fails.append("GET /app.css: the nav bar or busy pulse is gone (T198)")
        # Service sorts priciest tier first and heads each tier (T151)
        if js and (b"r=(parseFloat(q)||0)-(parseFloat(p)||0)" not in js
                   or b"h.className='tierhd'" not in js):
            fails.append("GET /app.js: Service no longer sorts by fee with tier headers (T151)")
        if css and b".tierhd{" not in css:
            fails.append("GET /app.css: the tier header style is gone (T151)")
        # each suggestion line says what its number is (T154)
        if js and b"'Cert '+c.cert" not in js:
            fails.append("GET /app.js: suggestion lines are unlabelled (T154)")
        # search drops stale answers and shows skeleton rows while waiting (T199)
        if js and (b"if(my===seq){clearTimeout(sk);render(d);}" not in js
                   or b"pvrow skrow" not in js):
            fails.append("GET /app.js: search renders stale answers or looks empty (T199)")
        if css and b".sk{display:block;background:var(--sk);border-radius:6px;animation:pulse" not in css:
            fails.append("GET /app.css: the skeleton pulse is gone (T199)")
        # the lightbox opens blurred on the small scan and sharpens; a dead large
        # scan keeps the small one, a dead cold open closes (T200)
        if js and (b"im.src=t.currentSrc||t.src;" not in js
                   or b"p.onload=function(){ if(want===big){ im.src=big; lb.classList.remove('wait'); } };" not in js
                   or b"im.onerror=function(){ if(want===big) close(); };" not in js):
            fails.append("GET /app.js: the lightbox opens on an empty scrim again (T200)")
        if css and (b".lb.wait img{filter:blur(6px)}" not in css
                    or b".lb img{height:min(calc(92vh - 44px),900px,calc(92vw*635/380));width:auto;aspect-ratio:380/635;" not in css):
            fails.append("GET /app.css: the lightbox lost its blur or slab box (T200, T157)")
        # the lightbox captions itself, pages within one grid, and makes main inert (T157)
        if js and (b"function page(d){" not in js
                   or b"if(e.key==='ArrowRight'){ e.preventDefault(); page(1); }" not in js
                   or b"if(Math.abs(dx)>50&&Math.abs(dx)>Math.abs(dy)) page(dx<0?1:-1);" not in js
                   or b"a.closest('.grid,.strip')" not in js
                   or b"'https://www.psacard.com/cert/'+encodeURIComponent(cert)" not in js
                   or b"main.inert=true" not in js or b"main.inert=false" not in js
                   or b"if(had) (cap.querySelector('a')||x).focus();" not in js):
            fails.append("GET /app.js: the lightbox lost its caption, paging, focus or inert main (T157)")
        # High Contrast keeps the stage bar's track and fill (T185)
        if css and (b"@media(forced-colors:active){" not in css
                    or b".bar i{background:Highlight;forced-color-adjust:none}" not in css):
            fails.append("GET /app.css: the stage bar vanishes under forced colors (T185)")

        # --- the pencil hides on the INPUT's focus, not the row's: :focus-within
        # also matched the pencil's own focus, so a tap removed the button
        # before its click and a filled tag could not be edited on a phone (T16)
        if css:
            if b":focus-within .ownedit{display:none}" in css:
                fails.append("GET /app.css: the pencil still hides on the row's focus")
            if b".own:focus + .ownedit{display:none}" not in css:
                fails.append("GET /app.css: the pencil no longer hides while the tag is edited")
            # on a mouse the pencil shows on tile hover or focus, faint at rest
            # on a filled tag, so a click is not the only way in (T134)
            if (b"@media not all and (pointer:coarse){\n .gc:hover .ownedit,.gc:focus-within .ownedit{display:flex}" not in css
                    or b".own:not(:placeholder-shown) + .ownedit{display:flex;opacity:.5}" not in css
                    or b".own:not([readonly]) + .ownedit{display:none}" not in css):
                fails.append("GET /app.css: desktop has no visible way to edit an owner tag (T134)")
            if b"@media(pointer:coarse){\n .ownedit{display:flex}" not in css:
                fails.append("GET /app.css: touch lost the pencil beside every owner tag (T134)")
            # person page groups sit in two equal columns on desktop, a 3+ card
            # group spans both (T120)
            for rule in (b"#list:has(>.grp),#archgrid:has(>.grp){display:grid;grid-template-columns:repeat(2,minmax(0,1fr))",
                         b".grp:has(>.grid>:nth-child(3)){grid-column:1/-1}"):
                if rule not in css:
                    fails.append(f"GET /app.css: person page groups lost {rule.decode()} (T120)")
            # archived cards carry grayscale only, in every view: an opacity wash
            # fades the card's own surface and takes the text under 4.5:1 (T51)
            if b".card.arch{filter:grayscale(" not in css:
                fails.append("GET /app.css: archived cards no longer read as past")
            if b".card.arch{opacity" in css or b"archview .card.arch" in css:
                fails.append("GET /app.css: an archived card is washed with opacity again")
            # a narrow row foot breaks between fields, never between the carrier
            # and its number, and Archive stays on the ship date's line (T175)
            if (b"white-space:nowrap" not in css.split(b".tlink{")[1].split(b"}")[0]
                    or b".est{font-size:14px;font-weight:400;color:var(--m1);flex:1 1 0}" not in css
                    or b"align-items:baseline" not in css.split(b".foot{")[1].split(b"}")[0]):
                fails.append("GET /app.css: the row foot wraps mid tracking number again (T175)")
            # a held sub's bar drops to the muted grey, so it stops painting
            # full accent under the red hold pill (T75)
            if b".card.arch .bar i,.card.hold .bar i,.dstage.hold .bar i{background:var(--barmuted)}" not in css:
                fails.append("GET /app.css: a held card still paints an accent stage bar")
            if b".gc.arch .ph" in css:
                fails.append("GET /app.css: the archived no-scan placeholder is dimmed again")
            # an archived tile greys whole, chip and value with the scan, and
            # lifts to colour on hover (T141)
            if (b".gc.arch{filter:grayscale(.55)" not in css or b".gc.arch:hover{filter:none}" not in css
                    or b"filter" in css.split(b'.gc.arch a[href^="/img"]{')[1].split(b"}")[0]):
                fails.append("GET /app.css: an archived tile greys its scan only (T141)")
            # an ungraded tile reserves the grade line box, so graded and
            # ungraded neighbours in one grid row keep the same baseline (T77)
            if b"min-height:21px" not in css.split(b".gc .gr{")[-1].split(b"}")[0]:
                fails.append("GET /app.css: the grade line no longer reserves its box")
            # an empty state sits on a card like every other block, not bare
            # on the grouped ground (T78)
            emp = css.split(b".empty{")[-1].split(b"}")[0]
            if b"background:var(--surface)" not in emp or b"border-radius:16px" not in emp:
                fails.append("GET /app.css: the empty state sits bare on the ground again")
            # a page-header figure is a data value: 17/650, the same rung as the
            # card values under it. The toolbar freshness stamp stays 13 (T76)
            if b".hrow>.synced:not(.custrow) b{font-size:17px;font-weight:650" not in css:
                fails.append("GET /app.css: the header figure is off the 17/650 data rung")
            if b".synced b{display:block;font-size:13px" not in css:
                fails.append("GET /app.css: the toolbar freshness stamp left 13px")
            # phones swap to the short sync phrase, under 360 the dot alone (T162)
            if (b".sync .ss{display:none}" not in css
                    or b" .sync .sl{display:none}\n .sync .ss{display:inline}" not in css
                    or b" .sync .ss{position:absolute;width:1px" not in css):
                fails.append("GET /app.css: the phone toolbar lost the short sync phrase (T162)")
            # under 640 the header note goes full width and left aligned, so its
            # right-align margin must be cleared or it floats mid column (T79)
            if b".hrow>.synced .estnote{margin-left:0}" not in css:
                fails.append("GET /app.css: the header note keeps its right-align "
                             "margin on phones")
            # on a phone Discord pings rides the person page's name line (T211)
            if b".hrow:has(>.tots) .dbtn{grid-column:2;grid-row:1}" not in css:
                fails.append("GET /app.css: Discord pings left the name line on phones (T211)")
            # an overflowing filmstrip fades the edge that still has tiles beyond
            # it, at every width: the rules sit unindented, outside any @media
            # block. The fade is driven by .sl/.sr, so a strip that fits gets none
            # of it (T80, T149). The strip snaps a tile to its left edge (T149)
            if b"\n.strip.sl{--fadel:28px}" not in css or b"\n.strip.sr{--fader:28px}" not in css:
                fails.append("GET /app.css: an overflowing filmstrip has no edge cue "
                             "at every width")
            if b"scroll-snap-type:x proximity;" not in css \
                    or b"\n.strip>*{scroll-snap-align:start}" not in css:
                fails.append("GET /app.css: the filmstrip does not snap (T149)")
            if js and b"querySelectorAll('.filters,.strip')" not in js:
                fails.append("GET /app.js: the scroll cue no longer runs on filmstrips")
            # no corner orbs: nothing fixed floats over the rows; gear and theme sit
            # in the dashboard toolbar, theme also on settings (T208)
            if re.search(rb"#gearbtn|#themeflip|position:fixed;bottom", css):
                fails.append("GET /app.css: the corner orbs are back (T208)")
            if js and (b"createElement('nav')" in js or b"'scrolldn'" in js):
                fails.append("GET /app.js: the theme script still builds a floating orb (T208)")
        check("GET /logo", "/logo", (200,))

        # --- /img and /logo are cached at the Cloudflare edge on origin TTL, so
        # both must carry a public max-age, and the gate served under an /img URL
        # must stay no-store or the edge could cache it in an image's place (T21)
        imgq = "/img?u=" + urllib.parse.quote(IMG_URL, safe="")
        _, _, ghdrs = call(url, "/logo")
        if "public, max-age=" not in (ghdrs.get("Cache-Control") or ""):
            fails.append("GET /logo: no public max-age for the edge to respect")
        _, _, ihdrs = call(url, imgq)
        if "no-store" not in (ihdrs.get("Cache-Control") or ""):
            fails.append("GET /img (no session): the gate page is edge cacheable")
        # --- pages carry a CSP, and every hand-rolled response carries nosniff (T25)
        _, _, phdrs = call(url, "/")
        if "frame-ancestors 'none'" not in (phdrs.get("Content-Security-Policy") or ""):
            fails.append("GET /: no Content-Security-Policy")
        # --- the gate holds a password field: it stays no-store wherever it is
        # served, while the bundles are compressed once at import, so repeated
        # fetches are byte-identical (T26)
        if "no-store" not in (phdrs.get("Cache-Control") or ""):
            fails.append("GET / (no session): the gate is not no-store")
        shots = {call(url, "/app.css", headers={"Accept-Encoding": "gzip"})[1]
                 for _ in range(10)}
        if len(shots) != 1:
            fails.append("GET /app.css: ten fetches did not return identical bytes")
        elif css:
            try:
                ok = gzip.decompress(shots.pop()) == css
            except OSError:
                ok = False  # not gzip at all
            if not ok:
                fails.append("GET /app.css: the gzip bundle is not the stylesheet")
        for label, hdrs in (("/logo", ghdrs),
                            ("/app.css", call(url, "/app.css")[2]),
                            ("/favicon.png", call(url, "/favicon.png")[2])):
            if hdrs.get("X-Content-Type-Options") != "nosniff":
                fails.append(f"GET {label}: no nosniff")
        check("GET /favicon.png", "/favicon.png", (200,))
        check("GET /apple-touch-icon.png", "/apple-touch-icon.png", (200,))
        # --- an installable app: the manifest is public, typed, and points the
        # home-screen icon at the 180px touch PNG, not the 64px favicon (T61)
        mcode, mbody, mhdrs = call(url, "/manifest.json")
        if mcode != 200:
            fails.append(f"GET /manifest.json: got {mcode}, want 200")
        elif "application/manifest+json" not in (mhdrs.get("Content-Type") or ""):
            fails.append("GET /manifest.json: not served as application/manifest+json")
        else:
            man = json.loads(mbody)
            if man.get("display") != "standalone" or man.get("start_url") != "/":
                fails.append("GET /manifest.json: not an installable standalone app")
            if [i["src"] for i in man.get("icons", [])] != ["/apple-touch-icon.png", "/icon.svg"]:
                fails.append("GET /manifest.json: the install icons are not the 180px PNG + svg")
            # T184: a maskable icon that serves, and the light ground on the splash
            if not any("maskable" in i.get("purpose", "") for i in man.get("icons", [])):
                fails.append("GET /manifest.json: no maskable icon")
            if man.get("background_color") != "#f2f2f7":
                fails.append("GET /manifest.json: background_color is not the light bg")
            check("GET /icon.svg", "/icon.svg", (200,), must_have="<svg")
        check("GET / (manifest link)", "/", (200,), must_have='rel="manifest"')
        check("GET / (theme-color)", "/", (200,), must_have='name="theme-color"')
        check("GET /api/hub.json (no key)", "/api/hub.json", (404,))
        check("GET /setup (setup closed)", "/setup", (302,))
        keepalive_checks(port, fails)
        setup_instance_checks(fails)
        gear_mode_checks(fails)
        copy_checks(fails)
        env_checks(fails)
        accent_checks(fails)
        barmuted_checks(fails)
        day_checks(fails)
        well_checks(fails)
        scrim_checks(fails)
        common_checks(fails)
        tracking_checks(fails)
        leading_checks(fails)
        hit_checks(fails)
        desk_checks(fails)
        comment_checks(fails)
        shot_checks(fails)

        # --- non-ASCII credentials compare, they don't crash the handler (T5)
        check("GET /api/hub.json (non-ASCII key)", "/api/hub.json?key=caf%C3%A9", (404,))
        check("GET / (non-ASCII token)", "/", (200,),
              cookie="psa_session=demo.9999999999.caf\u00e9",
              must_have='action="/login"')
        check("POST /login (non-ASCII password)", "/login", (200,),
              form={"password": "caf\u00e9"}, must_have="Incorrect password")
        check("POST /login (retry lands focused)", "/login", (200,),
              form={"password": "nope"}, must_have=" autofocus autocomplete")

        # --- the settings gate: rendered for no session, and after a wrong password
        check("GET /settings (no settings session)", "/settings", (200,),
              must_have="Enter the settings password")
        check("POST /settings/auth (wrong password)", "/settings/auth", (200,),
              form={"password": "wrong-" + SET_PW}, must_have="Incorrect password")
        code, _, hdrs = call(url, "/settings/auth", form={"password": SET_PW})
        scookie = (hdrs.get("Set-Cookie") or "").split(";")[0]
        if code != 302 or not scookie:
            fails.append(f"POST /settings/auth: got {code}, no settings cookie")
        else:
            body = check("GET /settings (settings session)", "/settings", (200,),
                         scookie, must_have="PSA accounts")
            if body and b'class="skip" href="#content"' not in body:
                fails.append("GET /settings: no skip link (T160)")
            if body and CADENCE.encode() not in body:
                fails.append("GET /settings: the subtitle lost the sync cadence (T163)")
            if body and b'data-acct="second"' not in body:
                fails.append("GET /settings (settings session): the other account "
                             "is missing, the settings password holds them all")
            # --- the Add account panel says the branding is shared (T72)
            if body:
                note = body.find("shares this site’s name, logo, accent".encode())
                addb = body.find(b'class="fillbtn">Add<')
                if note < 0 or addb < 0 or note > addb:
                    fails.append("GET /settings: the Add account panel does not say "
                                 "the site name, logo and accent are shared")

            # --- one filled accent capsule on the panel screen: the verification
            # code submit, the one an operator sends again and again. Every other
            # save is the bare text grammar (T81). Per-account panes repeat in the
            # markup but only the chosen one is on screen; modals are own screens.
            if body:
                panels = body.split(b'<div class="smodal"')[0]
                stray = (panels.count(b'class="fillbtn')
                         - panels.count(b'name="action" value="otp_'))
                if stray or b'fillbtn sbtn">Save<' in panels:
                    fails.append("GET /settings: the panel screen carries a filled "
                                 "capsule that is not the verification code submit")

            # --- the verification panel opens on the account PSA is asking
            # about, and never reloads the page: the armed pane polls ?only= (T11, T121)
            odir = os.path.join(base, "accounts", "second")

            def otp(*marks):
                for k in ("needed", "armed", "waiting"):
                    p = os.path.join(odir, "otp." + k)
                    if k in marks:
                        open(p, "w").write("yes")
                    elif os.path.exists(p):
                        os.remove(p)
                return check(f"GET /settings (otp {'+'.join(marks) or 'clear'})",
                             "/settings", (200,), scookie) or b""

            b_armed = otp("armed")
            if b_armed.find(b'data-acct="second"') > b_armed.find(b'data-acct="demo"'):
                fails.append("GET /settings (otp armed): the flagged account did not sort first")
            if b'class="f schip on att" data-group="o" data-pane="opane0"' not in b_armed:
                fails.append("GET /settings (otp armed): the flagged chip is not marked or not selected")
            if b'value="otp_code"' in b_armed:
                fails.append("GET /settings (otp armed): a code field renders before PSA sent one")
            if b'http-equiv="refresh"' in b_armed:
                fails.append("GET /settings (otp armed): the page still meta-refreshes (T121)")
            if b'class="spoll"' not in b_armed or b'id="live"' not in b_armed:
                fails.append("GET /settings (otp armed): no polled pane or no live region (T121)")
            b_one = check("GET /settings?only=second", "/settings?only=second", (200,),
                          scookie) or b""
            if (b_one.count(b'class="spane sg-o"') != 1 or b'data-acct="second"' not in b_one
                    or b'class="spoll"' not in b_one or b'data-acct="demo"' in b_one):
                fails.append("GET /settings?only=second: not that account's pane alone (T121)")
            b_wait = otp("armed", "waiting")
            if b'value="otp_code"' not in b_wait:
                fails.append("GET /settings (otp waiting): no code field")
            if b'http-equiv="refresh"' in b_wait:
                fails.append("GET /settings (otp waiting): auto-refresh would wipe the code being typed")
            b_clear = otp()
            if b'att" data-group="o"' in b_clear or b'http-equiv="refresh"' in b_clear:
                fails.append("GET /settings (otp clear): a marker or a refresh survived")

            # --- Unlink asks inside the sheet, never window.confirm, and the
            # unlinked banner links to settings (T125)
            if b"confirm(" in b_clear or b'<form method="POST" action="/settings/account" id="unform" hidden>' not in b_clear:
                fails.append("GET /settings: Unlink is a native confirm(), not the sheet (T125)")
            check("POST /settings/account (unlink second)", "/settings/account", (302, 303),
                  scookie, {"acct": "second", "action": "unlink"})
            _, _, h2 = call(url, "/login", form={"password": SITE_PW + "-2"})
            c2 = (h2.get("Set-Cookie") or "").split(";")[0]
            b_un = check("GET / (unlinked)", "/", (200,), c2 or None) if c2 else b""
            # an account with nothing to look at renders no attention card (T150)
            if b_un and b'id="attn"' in b_un:
                fails.append("GET / (empty account): an all-zero attention card renders (T150)")
            if (b"This account is unlinked" not in b_un
                    or b'password in <a class="tlink" href="/settings">settings</a> to relink' not in b_un):
                fails.append("GET / (unlinked): the banner's settings is not a link (T125)")

        # --- admin session
        code, _, hdrs = call(url, "/login", form={"password": SITE_PW})
        cookie = (hdrs.get("Set-Cookie") or "").split(";")[0]
        if code != 302 or not cookie:
            fails.append(f"POST /login: got {code}, no session cookie")
            cookie = None
        # a session has to outlive an 8 month PSA turnaround (T61); rotating the
        # site password is what still revokes it
        if "Max-Age=15552000" not in (hdrs.get("Set-Cookie") or ""):
            fails.append("POST /login: the session cookie is not 180 days")
        if cookie:
            body = check("GET /", "/", (200,), cookie, must_have="14900001")
            # no .last_ok yet over a full dashboard is unknown, not never (T162)
            if (b"No sync yet" in (body or b"") or b">Last update unknown<" not in (body or b"")
                    or b">Sync unknown<" not in (body or b"")):
                fails.append("GET /: a full dashboard with no .last_ok says No sync yet (T162)")
            if ((body or b"").count(b'class="f fsort') != 3
                    or b'data-sort="svc" aria-pressed="false">Service<' not in (body or b"")
                    or b'data-svc="Regular" data-price="109.0"' not in (body or b"")):
                fails.append("GET /: not three sort pills, or Service rows lack the tier price (T151)")
            # the sort rides the URL and the server renders it; shipped sorts
            # with the dateless rows, last under Return either way (T152)
            def order(b):
                return re.findall(rb'<h2 class="num">#(\d+)</h2>', b.split(b'id="list"', 1)[-1])
            if order(body or b"") != [b"14900004", b"14900003", b"14900002", b"14900001"]:
                fails.append(f"GET /: default order {order(body or b'')} (T152)")
            asc = check("GET /?sort=eta", "/?sort=eta", (200,), cookie)
            desc = check("GET /?sort=eta&dir=desc", "/?sort=eta&dir=desc", (200,), cookie)
            bad = check("GET /?sort=x&dir=y", "/?sort=%3Cx%3E&dir=up", (200,), cookie)
            # 14900004 shipped (stale ETA in the past) after past-due 14900003
            if order(asc or b"") != [b"14900003", b"14900002", b"14900001", b"14900004"]:
                fails.append(f"GET /?sort=eta: order {order(asc or b'')} (T152)")
            if (order(desc or b"") != [b"14900001", b"14900002", b"14900003", b"14900004"]
                    or b'class="f fsort on rev" data-sort="eta" aria-pressed="true">Return<'
                    not in (desc or b"")):
                fails.append(f"GET /?sort=eta&dir=desc: order {order(desc or b'')} (T152)")
            if (order(bad or b"") != order(body or b"")
                    or b'class="f fsort on" data-sort="sub" aria-pressed="true">Newest<' not in (bad or b"")
                    or b"&lt;x" in (bad or b"")):
                fails.append("GET /?sort=<x>&dir=up: bad params not ignored (T152)")
            sub_rev = check("GET /?sort=sub&dir=asc", "/?sort=sub&dir=asc", (200,), cookie)
            if (order(sub_rev or b"") != [b"14900001", b"14900002", b"14900003", b"14900004"]
                    or b'aria-pressed="true">Oldest<' not in (sub_rev or b"")):
                fails.append("GET /?sort=sub&dir=asc: not oldest first (T152)")
            # one quiet attention line above the list, each count a link (T150)
            want = ('<div class="hint attn" id="attn">'
                    '<a class="tlink" href="/?show=hold">1 on hold</a> · '
                    '<a class="tlink" href="/?show=late">1 past due</a> · '
                    '<a class="tlink" href="/?show=graded">1 graded</a> · '
                    '<a class="tlink" href="/cards?owner=unassigned">12 untagged</a></div>')
            if want.encode() not in (body or b""):
                fails.append("GET /: the attention card is missing or wrong (T150)")
            elif (body or b"").index(b'id="attn"') > (body or b"").index(b'id="list"'):
                fails.append("GET /: the attention card is not above the list (T150)")
            # every count links a filtered dashboard: two held subs show exactly
            # those two and a way back; an unknown show= is ignored (T218)
            hdb = sqlite3.connect(os.path.join(base, "accounts", "demo", "psa.db"))
            hdb.execute("UPDATE subs SET on_hold = 1 WHERE sub_number = '14900003'")
            hdb.commit()
            two = check("GET /?show=hold", "/?show=hold", (200,), cookie) or b""
            if (order(two) != [b"14900003", b"14900002"]
                    or 'Showing 2 on hold · <a class="tlink" href="/">Show all</a>'.encode() not in two
                    or b'<a class="tlink" href="/?show=hold">2 on hold</a>' not in two):
                fails.append(f"GET /?show=hold: rows {order(two)}, want the two held subs and Show all (T218)")
            junk = check("GET /?show=junk", "/?show=junk", (200,), cookie) or b""
            if len(order(junk)) != 4 or b"showln" in junk:
                fails.append("GET /?show=junk: an unknown show= was not ignored (T218)")
            if order(check("GET /?show=late", "/?show=late", (200,), cookie) or b"") != [b"14900003"]:
                fails.append("GET /?show=late: not just the past-due sub (T218)")
            hdb.execute("UPDATE subs SET on_hold = 0 WHERE sub_number = '14900003'")
            hdb.commit()
            hdb.close()
            # strip scans decode off the main thread as well as load lazily (T181)
            imgs = re.findall(rb'<img [^>]*src="/img[^>]*>', body or b"")
            if not imgs or any(b'loading="lazy"' not in i or b'decoding="async"' not in i
                               for i in imgs):
                fails.append("GET /: a strip scan lacks lazy loading or async decoding")

            # --- the untagged count lives in the attention line, not a pill (T150)
            if body:
                cap = re.search(rb'<div class="filters".*?</div>', body, re.S)
                if not cap:
                    fails.append("GET /: no sort capsule")
                if b'class="f fsolo" href="/cards?owner=unassigned"' in body:
                    fails.append("GET /: the need-owners pill is back beside the attention line")

                # --- the per sub total is summed in sqlite over the cards this
                # account holds: estimate wins, last_sale is the fallback, and a
                # value row with no card of ours adds nothing (T27)
                if b'ledval">$626<span>CAD' not in body:
                    fails.append("GET /: the submission total is not (310+150)*1.36")

                # --- an unmapped PSA step reads as unknown, not as stage 1 of 8,
                # and draws no bar: one bar per sub the stage map knows (T19)
                if b"Status unknown" not in body:
                    fails.append("GET /: the unmapped status does not read as unknown")
                if body.count(b'<div class="bar">') != 2:
                    fails.append("GET /: the unmapped status still draws a stage bar")

                # --- grades landing is the stage word itself on the dashboard
                # row, in place of "Completing", and nothing else: no pill, no
                # badge, no colour, no sort control (T114)
                if "<b>Grades ready</b> · <span>back ".encode() not in body:
                    fails.append("GET /: the grades-ready sub still reads as Completing")
                if b"<b>Completing</b>" in body:
                    fails.append("GET /: a grades-ready row still prints the Completing "
                                 "stage word")

                # --- filmstrip tiles are 64-84 CSS px: they serve the stored
                # thumbnail, never the /small/ 380x636 scan (T20)
                strips = re.findall(rb'<div class="strip">.*?</div>', body, re.S)
                if not strips:
                    fails.append("GET /: no filmstrip rendered")
                for st in strips:
                    for src in re.findall(rb'<img [^>]*src="([^"]+)"', st):
                        if b"/thumbnail/" not in src:
                            fails.append("GET /: a filmstrip tile is not the "
                                         f"thumbnail asset ({src!r})")

                # --- the overflow chip is NAMED: "+2" alone tells a screen
                # reader neither what the two are nor where they live (T56)
                chip = re.search(rb'<a class="morechip"[^>]*>', body)
                if not chip:
                    fails.append("GET /: no filmstrip overflow chip")
                elif (b'aria-label="2 more cards in submission #14900003"'
                      not in chip.group(0)):
                    fails.append("GET /: the overflow chip is named only by its count")

                # --- the filmstrip is a preview: its tiles and chip are out of
                # the tab order, so "View cards" is a few Tabs in (T158)
                for st in strips:
                    for a in re.findall(rb'<a [^>]*>', st):
                        if b'tabindex="-1"' not in a:
                            fails.append("GET /: a filmstrip link is a tab stop again")
                            break
                head = body.split(b'id="list"')[-1].split(b'class="view"')[0]
                stops = [t for t in re.findall(
                    rb'<(?:a [^>]*href|button|input(?![^>]*type="hidden")|select|textarea)[^>]*>',
                    head) if b'tabindex="-1"' not in t]
                if len(stops) > 3:
                    fails.append(f"GET /: first View cards is {len(stops) + 2} Tabs in "
                                 "via the skip link, want 5 or fewer")

                # --- row controls carry the sub number in their name, so no
                # two links or buttons announce the same thing (T159)
                names = []
                for tag, txt in re.findall(
                        rb'<((?:a [^>]*href|button)[^>]*)>(.*?)</(?:a|button)>', body, re.S):
                    if b'tabindex="-1"' in tag:
                        continue
                    lab = re.search(rb'aria-label="([^"]*)"', tag)
                    names.append(lab.group(1) if lab else
                                 re.sub(rb'<[^>]*>|\s+', b' ', txt).strip())
                dup = sorted({n for n in names if names.count(n) > 1})
                if dup:
                    fails.append(f"GET /: links or buttons share a name: {dup} (T159)")
                if ("b.setAttribute('aria-label',b.textContent" not in
                        open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()):
                    fails.append("GET /: archive flip leaves the old aria-label (T159)")

                # --- gear and theme are toolbar icons beside sign-out, not
                # floating orbs; no page carries the old controls nav (T208)
                tb = body.split(b'<div class="tbend">', 1)[-1].split(b"</header>", 1)[0]
                if (b'id="gearbtn"' not in tb or b'id="themeflip"' not in tb
                        or tb.index(b'id="themeflip"') > tb.index(b'href="/logout"')
                        or b'id="sitectl"' in body):
                    fails.append("GET /: gear and theme are not toolbar icons beside sign-out (T208)")
                _, sb, _ = call(url, "/settings", cookie)
                if b'id="themeflip"' not in sb or b'id="sitectl"' in sb:
                    fails.append("GET /settings: no theme toggle on the settings page (T208)")

                # --- a touch keyboard gets Search on the search box (T56)
                if b'enterkeyhint="search"' not in body:
                    fails.append("GET /: the search box carries no enter-key hint")
            # --- a dead PSA link is said out loud: run_scan writes .last_ok
            # after every successful scan, the dashboard reads its stamp (T24)
            okf = os.path.join(base, "accounts", "demo", ".last_ok")

            def last_ok(ago):
                open(okf, "w").close()
                os.utime(okf, (time.time() - ago,) * 2)

            last_ok(2 * 86400)
            body = check("GET / (scans two days stale)", "/", (200,), cookie)
            if b"Not connecting to PSA" not in body:
                fails.append("GET /: two days without a scan and the dashboard says nothing")
            # the cause is one plain sentence and a settings link, never the raw line (T128)
            errf = os.path.join(base, "accounts", "demo", ".last_error")
            raw = "login failed: Descope flow error E062108 at sign-in"
            with open(errf, "w", encoding="utf-8") as f:
                f.write(raw + "\n")
            body = check("GET / (stale with a Descope error)", "/", (200,), cookie)
            os.remove(errf)
            if (b"Descope" in body or b"E062108" in body
                    or b'<div class="hint warn" role="status">' not in body
                    or b"Signing in to PSA failed" not in body
                    or b'<a class="tlink" href="/settings">settings</a>' not in body):
                fails.append("GET /: the PSA outage banner leaks its raw cause or links no fix (T128)")
            # the toolbar says the same thing in one dot and one word (T104)
            # one grammar, the clock time in the title (T162)
            # phones read the short form so the toolbar stays one row. The clock
            # time is in plain sight, not a .vh span: the live phrase ends on it
            # and the live phone form is the clock alone (T169)
            dot = re.compile(rb'<div class="sync( \w+)?" title="(Last sync [A-Z][a-z]{2} \d{1,2}, '
                             rb'\d{1,2}:\d\d [AP]M [^"]*)"><i aria-hidden="true"></i>'
                             rb'<span class="sl">([^<]*)</span><span class="ss">([^<]*)</span></div>')
            clk = rb"\d{1,2}:\d\d [AP]M"
            for ago, cls, want, short in (
                    (2 * 86400, b" stale", rb"Not updating since [A-Z][a-z]{2} \d{1,2}", rb"Not updating"),
                    (90 * 60, b" stale", rb"Not updating since " + clk, rb"Not updating"),
                    (48 * 60, b" live", rb"Updated 48 min ago \xc2\xb7 " + clk, clk),
                    (0, b" live", rb"Updated just now \xc2\xb7 " + clk, clk)):
                last_ok(ago)
                body = check(f"GET / (last scan {ago}s ago)", "/", (200,), cookie)
                m = dot.search(body)
                if (not m or m.group(1) != cls or not re.fullmatch(want, m.group(3))
                        or not re.fullmatch(short, m.group(4)) or b'class="vh">Last sync' in body
                        or (cls == b" live" and not m.group(3).endswith(m.group(4)))):
                    fails.append(f"GET /: a scan {ago}s old reads "
                                 f"{m and m.group(0)!r}, want {want!r} (T162)")
                if (b"Not connecting to PSA" in body) != (ago >= 6 * 3600):
                    fails.append(f"GET /: the PSA link banner is wrong {ago}s after a scan")
            if b"Last synced" in body:
                fails.append("GET /: the toolbar still prints a last synced stamp")

            # --- a signed-in page is private, no-cache, not no-store: back
            # navigation from a sub restores it from the back forward cache (T26)
            for label, path in (("/", "/"), ("/sub/14900001", "/sub/14900001")):
                got = call(url, path, cookie)[2].get("Cache-Control") or ""
                if got != "private, no-cache":
                    fails.append(f"GET {label} (session): Cache-Control {got!r} "
                                 "forfeits the back forward cache")
            if "no-store" not in (call(url, "/settings", cookie)[2].get("Cache-Control") or ""):
                fails.append("GET /settings (session): not no-store")

            icode, _, ihdrs = call(url, imgq, cookie)
            if icode != 200:
                fails.append(f"GET /img: got {icode}, want 200")
            elif "public, max-age=" not in (ihdrs.get("Cache-Control") or ""):
                fails.append("GET /img: no public max-age for the edge to respect")
            if ihdrs.get("Set-Cookie"):
                fails.append("GET /img: a Set-Cookie keeps it out of the edge cache")
            if ihdrs.get("X-Content-Type-Options") != "nosniff":
                fails.append("GET /img: no nosniff on the served image (T25)")
            # no owner in the query is the unassigned worklist (T63)
            body = check("GET /cards", "/cards", (200,), cookie,
                         must_have="<title>Unassigned cards</title>")
            if b"<h1>Unassigned</h1>" not in body:
                fails.append("GET /cards: no owner is missing the worklist heading")
            check("GET /cards?owner=", "/cards?owner=Nobody", (200,), cookie)

            # --- counts pluralize. One card reads "1 card" on the dashboard
            # row, the sub header, the person header and the group heading, and
            # the attention line says 1 untagged for a single card (T64, T150)
            def arch(num, on):
                return call(url, "/archive", cookie, {"sub": num, "on": on})[0]

            arch("14900001", "1")
            arch("14900003", "1")
            check("GET / (one card untagged)", "/", (200,), cookie,
                  must_have='href="/cards?owner=unassigned">1 untagged</a>')
            # the Archived count survives every width: the phone pays in
            # characters ("Arch."), never by hiding the number (T146)
            check("GET / (Archived count)", "/", (200,), cookie,
                  must_have='<span class="archs">Arch.</span><span class="archn"> · 2</span>')
            if css and re.search(rb"\.archn\{display:none", css):
                fails.append("GET /app.css: a rule hides the Archived count again")
            # the archived view says so in ink and in #live, and the sub page
            # gives Archived its own line (T145)
            dbody = check("GET / (Archived line)", "/", (200,), cookie,
                          must_have='id="archhd" hidden>Archived · 2 submissions</div>') or b""
            for want in (b"hd.hidden=!on", b"' archived submission'", b"say('Showing '",
                         b"t load archived submissions", b"clearTimeout(l.st)"):
                if want not in dbody:
                    fails.append(f"GET /: Archived toggle lacks {want.decode()!r} (T145)")
            if js and b"getElementById('archhd')" not in js:
                fails.append("GET /app.js: archiving leaves the Archived line's count (T145)")
            sbody = check("GET /sub/14900003 (Archived line)", "/sub/14900003", (200,), cookie,
                          must_have='</div><div class="sub" id="archtag">Archived</div>') or b""
            if b'<span style="color:var(--m1)">Archived' in sbody:
                fails.append("GET /sub/14900003: Archived still trails the subtitle (T145)")
            # the sub's own page wears the same whole-tile grey as search (T141)
            if b'<div class="gc arch">' not in sbody or b"archdim" in sbody:
                fails.append("GET /sub/14900003: archived tiles grey the scan only (T141)")
            check("GET /cards (one card untagged)", "/cards", (200,), cookie,
                  must_have="1 card awaiting an owner")
            arch("14900001", "0")
            arch("14900003", "0")
            if call(url, "/owner", cookie,
                    {"cert_id": "99000002", "owner": "Solo"})[0] != 204:
                fails.append("POST /owner: tagging one card was refused")
            sbody = check("GET /cards?owner=Solo", "/cards?owner=Solo", (200,), cookie,
                          must_have="1 card with")
            # the person page keeps its owner field: retagging off it is T168/T217 (T207 ruling)
            if b'class="own" data-cert="99000002" value="Solo"' not in sbody:
                fails.append("GET /cards?owner=Solo: tiles lost the owner field, no retag here (T207)")
            # one money format in the person page value block: every figure
            # carries the currency, the fee total prints no cents (T71)
            for want in (b"Est. grading cost<b>$109 CAD</b>", b"<b>$120 CAD</b>",
                         b"<b>$204 CAD</b>"):
                if want not in sbody:
                    fails.append("GET /cards?owner=Solo: the value block is missing "
                                 + want.decode())
            # the cards lead: one row of figures, value first, and the footnote
            # folded behind a details, so a phone sees a card above 300px (T211)
            if (not re.search(rb'<div class="trow"><span>Est\. value[^<]*<b>[^/]*</b></span>'
                              rb'<span>Insured coverage<b>[^/]*</b></span>'
                              rb'<span>Est\. grading cost<b>', sbody)
                    or b'<details class="estnote"><summary>How these are counted</summary>'
                    not in sbody or b'class="lbl2"' in sbody):
                fails.append("GET /cards?owner=Solo: the totals are not one row "
                             "with the footnote folded (T211)")
            # each tile carries its share of the three figures, so a retag can
            # re-sum them in place to what a reload prints (T217)
            sh = [tuple(round(float(x or 0)) for x in m) for m in re.findall(
                rb'class="gc" data-v="([^"]*)" data-g="[^"]*" data-dv="([^"]*)" data-p="([^"]*)"',
                sbody)]
            if (sh != [(204, 120, 109)] or not js or b"function _retot(" not in js
                    or b"if(l)_retot(l);" not in js):
                fails.append(f"GET /cards?owner=Solo: tiles do not carry the totals {sh} (T217)")
            # the CSV is a file, so the nav bar never starts on it (T198)
            if b'&amp;format=csv" download>' not in sbody:
                fails.append("GET /cards?owner=Solo: Export CSV lacks download (T198)")
            # --- format=csv hands the person page's rows out as a spreadsheet:
            # one data row per tile the HTML renders, archived tiles included,
            # under a text/csv type and a download name (T74)
            for who, name in (("Solo", "solo-cards.csv"),
                              ("", "unassigned-cards.csv"),
                              ("unassigned", "unassigned-cards.csv")):
                q = "/cards?owner=" + urllib.parse.quote(who)
                code, cbody, chdrs = call(url, q + "&format=csv", cookie)
                if code != 200:
                    fails.append(f"GET {q}&format=csv: got {code}, want 200")
                    continue
                if "text/csv" not in (chdrs.get("Content-Type") or ""):
                    fails.append(f"GET {q}&format=csv: not text/csv")
                if name not in (chdrs.get("Content-Disposition") or ""):
                    fails.append(f"GET {q}&format=csv: no {name} to download as")
                rows = len(list(csv.reader(cbody.decode().splitlines()))) - 1
                tiles = check(f"GET {q} (csv parity)", q, (200,), cookie).count(b'class="gc')
                if rows != tiles:
                    fails.append(f"GET {q}&format=csv: {rows} rows for {tiles} tiles")
                if not tiles:
                    fails.append(f"GET {q}: no tiles to compare the export against")

            # the longest key in the service name sets the fee, so a compound
            # tier does not fall back to the plain "Value" one, and a tier
            # nobody priced keeps the + and names itself in its title (T73)
            def priced_as(svc):
                db = sqlite3.connect(os.path.join(base, "accounts", "demo", "psa.db"))
                db.execute("UPDATE subs SET service = ? WHERE sub_number = '14900001'",
                           (svc,))
                db.commit()
                db.close()
                return call(url, "/cards?owner=Solo", cookie)[1] or b""

            for svc, want in (("Value Bulk 1980-present", b"cost<b>$46 CAD</b>"),
                              ("Value Max", b"cost<b>$90 CAD</b>"),
                              ("Regular Toronto Nat 2025", b"cost<b>$109 CAD</b>")):
                if want not in priced_as(svc):
                    fails.append(f"GET /cards?owner=Solo: {svc} is not priced "
                                 + want.decode())
            if b'$0+<span class="vh"> no price for Wibble Tier</span> CAD' \
                    not in priced_as("Wibble Tier"):
                fails.append("GET /cards?owner=Solo: an unpriced service has no "
                             "+ naming itself in the title")
            priced_as("Regular")
            # one + rule on every money total: + iff a card that should count
            # has no figure yet, and the person footnote defines it (T165)
            pl = b'+<span class="vh"> some cards have no figure yet</span>'
            def totals():
                return (call(url, "/", cookie)[1] or b"",
                        call(url, "/sub/14900001", cookie)[1] or b"",
                        call(url, "/cards?owner=Solo", cookie)[1] or b"")
            d, sp, pp = totals()
            if (b'ledval">$626<span>' not in d or b"<b>$626 CAD</b>" not in sp
                    or b"<b>$204 CAD</b>" not in pp or pl in d + sp + pp
                    or b"+ = some cards" in pp):
                fails.append("GET /, /sub, /cards: a complete total carries + (T165)")
            call(url, "/owner", cookie, {"cert_id": "99000001", "owner": "Solo"})
            db = sqlite3.connect(os.path.join(base, "accounts", "demo", "psa.db"))
            db.execute("UPDATE card_values SET estimate = NULL, last_sale = NULL "
                       "WHERE cert_no = '99000001'")
            db.commit()
            d, sp, pp = totals()
            if (b'ledval">$204' + pl + b"<span>" not in d
                    or b"<b>$204" + pl + b" CAD</b>" not in sp
                    or b"<b>$204" + pl + b" CAD</b>" not in pp
                    or b"<br>+ = some cards have no figure yet</details>" not in pp):
                fails.append("GET /, /sub, /cards: an unpriced graded card leaves "
                             "its total without + or the footnote (T165)")
            db.execute("UPDATE card_values SET estimate = 310, last_sale = 290 "
                       "WHERE cert_no = '99000001'")
            db.commit()
            db.close()
            call(url, "/owner", cookie, {"cert_id": "99000001", "owner": ""})
            check("GET /sub/14900002 (one card)", "/sub/14900002", (200,), cookie,
                  must_have="1 card \u00b7")
            for label in ("/", "/sub/14900002", "/cards", "/cards?owner=Solo"):
                if re.search(rb"(?<!\d)1 cards", call(url, label, cookie)[1] or b""):
                    fails.append(f'GET {label}: a single card still reads "1 cards"')
            # one word per thing: no operator vocabulary on a served page, every
            # link into a sub reads View cards, Discord pings has one name (T164)
            for label in ("/", "/sub/14900002", "/cards", "/cards?owner=Solo",
                          "/search?q=Umbreon", "/search?q=Charizard"):
                b = call(url, label, cookie)[1] or b""
                for bad in (b"Prelim", b"Go to sub", b"Link Discord", b">Enable<"):
                    if bad in b:
                        fails.append(f"GET {label}: still says {bad.decode()} (T164)")
            b = call(url, "/search?q=Umbreon", cookie)[1] or b""
            # a search tile is the detail tile plus one link, "Open sub #N" (T207)
            if (b'<a class="sublink" href="/sub/14900002">Open sub #14900002</a>' not in b
                    or b'class="svc"' in b or b'class="cn' in b):
                fails.append("GET /search?q=Umbreon: tile is not the detail tile plus Open sub #N (T207)")
            if (b'aria-label="View cards in #14900001">View cards</a>' not in sbody
                    or b'id="dopen">Discord pings</button>' not in sbody
                    or b'id="dlink" data-owner="Solo">Save</button>' not in sbody):
                fails.append("GET /cards?owner=Solo: group link or Discord pings naming drifted (T164)")
            # --- the person page searches names as well as cards, and carries a
            # Home link Back cannot replace once you have hopped person to person
            # (T103). The Cards half stays pinned to that person either way.
            call(url, "/owner", cookie, {"cert_id": "99000001", "owner": "Duo"})
            hop = json.loads(check("GET /suggest (person page, a name)",
                                   "/suggest?q=duo&owner=Solo", (200,), cookie)
                             or b'{"names":[]}')
            if "Duo" not in hop.get("names", []):
                fails.append("GET /suggest?owner=Solo: a name query finds nobody (T103)")
            browse = json.loads(check("GET /suggest (person page, browse)",
                                      "/suggest?q=&owner=Solo", (200,), cookie)
                                or b'{"names":[],"cards":[]}')
            if "Duo" not in browse.get("names", []):
                fails.append("GET /suggest?owner=Solo: browse mode lists no people (T103)")
            if not browse.get("cards") or any(c.get("owner") != "Solo"
                                              for c in browse["cards"]):
                fails.append("GET /suggest?owner=Solo: the Cards half left that "
                             "person's cards (T103)")
            # every inner page wears one header: back link (history aware) with the
            # page's one action across, title, one meta line, at most one figure (T206)
            head = re.compile(rb'<div class="foot footbare"><a class="view"(?: id="backlk")? href="[^"]*">'
                              + "\u2190".encode()
                              + rb' [^<]*</a>(<span class="footacts">.*?</span>)?</div>'
                              rb'<div class="hrow" id="content" tabindex="-1"><div><h1>[^<]+</h1>'
                              rb'<div class="sub">', re.S)
            for p in ("/sub/14900001", "/cards?owner=Solo", "/search?q=Charizard", "/settings"):
                b = call(url, p, cookie)[1] or b""
                # settings saves 303 back to /settings, so its Back is a plain link home
                if len(head.findall(b)) != 1 or b.count(b'id="backlk"') != (p != "/settings"):
                    fails.append(f"GET {p}: not the one shared page header (T206)")
            b = call(url, "/sub/14900001", cookie)[1] or b""
            if b"tlcard" in b or b.count(b'class="synced"') != 1 or b"PSA estimates" in b:
                fails.append("GET /sub/14900001: the header right column is not one figure (T206)")
            # the sticky bar's sentinel ships in the markup, so a late app.js
            # cannot shift the page by inserting it (T202)
            b = call(url, "/", cookie)[1] or b""
            if (b'<div class="tbsentinel" aria-hidden="true"></div><header class="toolbar">' not in b
                    or (js and b"className='tbsentinel'" in js)):
                fails.append("GET /: the toolbar sentinel is inserted by script again (T202)")
            # Send code pressed: a pulsing dot on "Signing in now" and no second Send code (T202)
            armf = os.path.join(base, "accounts", "demo", "otp.armed")
            open(armf, "w").close()
            b = call(url, "/settings", cookie)[1] or b""
            os.remove(armf)
            pane = b.split(b'class="spane sg-o"', 1)[-1].split(b'</div>\n</div>', 1)[0]
            if (b'<span class="waitdot" aria-hidden="true"></span>Signing in now' not in pane
                    or b">Send code<" in pane):
                fails.append("GET /settings (armed): no wait dot, or Send code still offered (T202)")
            # one back link, no Home beside it (T206, was T103)
            if b'<a class="view" href="/">Home</a>' in \
                    (call(url, "/cards?owner=Solo", cookie)[1] or b""):
                fails.append("GET /cards?owner=Solo: Home is back beside Back (T206)")
            # every owner field offers the names in use from one datalist (T135)
            for p in ("/sub/14900003", "/cards?owner=Solo", "/search?q=Charizard"):
                b = call(url, p, cookie)[1] or b""
                if (b.count(b"<datalist") != 1 or b'<option value="Duo">' not in b
                        or b'<option value="Solo">' not in b
                        or b'class="own"' not in b
                        or b.count(b'class="own"') != b.count(b'list="owners"')):
                    fails.append(f"GET {p}: owner fields lack the one names datalist (T135)")
            if css and b".own::-webkit-list-button{display:none" not in css:
                fails.append("GET /app.css: Safari's datalist arrow shows on the tag (T135)")
            # a no-result search names the next move and links every owner (T154)
            body = check("GET /search (no result)", "/search?q=zzzznothinghere",
                         (200,), cookie) or b""
            if (b"Try a card name, a cert number, or an owner's name." not in body
                    or b'href="/cards?owner=Duo"' not in body
                    or b'href="/cards?owner=Solo"' not in body):
                fails.append("GET /search?q=zzzznothinghere: no next action or owner links (T154)")
            call(url, "/owner", cookie, {"cert_id": "99000001", "owner": ""})
            call(url, "/owner", cookie, {"cert_id": "99000002", "owner": ""})
            body = check("GET /search", "/search?q=Charizard", (200,), cookie) or b""
            if not re.search(rb"<title>Search: Charizard - \d+ match(es)?</title>", body):
                fails.append("GET /search?q=Charizard: title does not name the query (T156)")
            body = check("GET /search (empty q)", "/search?q=", (200,), cookie) or b""
            if b"<title>Search</title>" not in body:
                fails.append("GET /search?q=: title is not plain Search (T156)")
            # a grade token filters on the grade; a bare 10 stays a text match (T155)
            for q in ("PSA+10", "gem+mint", "10"):
                body = check(f"GET /search?q={q}", "/search?q=" + q, (200,), cookie) or b""
                if b"Charizard" not in body or b"Pikachu" in body or b"1 match<" not in body:
                    fails.append(f"GET /search?q={q}: not just the one PSA 10 card (T155)")
            for q in ("%", "_", "\\"):
                body = check(f"GET /suggest?q={q!r}", "/suggest?q=" +
                             urllib.parse.quote(q), (200,), cookie)
                if body:
                    try:
                        json.loads(body)
                    except ValueError:
                        fails.append(f"GET /suggest?q={q!r}: not JSON")
            # the Prelim slot names itself: the tile where a cert number will
            # go carries the reason it is empty, and a graded tile still prints
            # its number plain (T70)
            body = check("GET /sub/14900001", "/sub/14900001", (200,), cookie,
                         must_have="Charizard")
            # the cert number lives in the lightbox caption, not on the tile (T207)
            if b'class="cn' in body or b'data-cert="99000001"' not in body:
                fails.append("GET /sub/14900001: the cert is on the tile, or off the caption (T207)")
            # one neutral chip, any 10 the accent: a qualifier grade parses its last number (T204)
            gdb = sqlite3.connect(os.path.join(base, "accounts", "demo", "psa.db"))
            qual = (("97000001", "GEM MT 10"), ("97000002", "MINT 9"), ("97000003", "8"))
            gdb.executemany("UPDATE cards SET grade=? WHERE cert_id=?", [(g, c) for c, g in qual])
            gdb.commit()
            chips = re.findall(rb'<div class="gr([^"]*)">PSA ([^<]*)</div>',
                               call(url, "/sub/14900003", cookie)[1] or b"")
            chips += re.findall(rb'<div class="gr([^"]*)">PSA ([^<]*)</div>', body)
            if sorted(chips) != sorted([(b" g10", b"GEM MT 10"), (b"", b"MINT 9"), (b"", b"8"),
                                        (b" g10", b"10"), (b"", b"9")]):
                fails.append(f"GET /sub/14900003: grade chips {chips}, want any 10 g10 and the rest one neutral class")
            gdb.execute("UPDATE cards SET grade='' WHERE sub_number='14900003'")
            gdb.commit()
            gdb.close()
            # detail grid tiles stay keyboard reachable (T158)
            grid = re.findall(rb'<a [^>]*href="/img[^>]*>', body)
            if not grid or any(b'tabindex="-1"' in a for a in grid):
                fails.append("GET /sub/14900001: grid tiles are not tab stops")
            # the tile carries the lightbox caption: grade, cert, value (T157)
            if not any(b'data-gr="PSA 10" data-cert="99000001" data-val="$' in a for a in grid):
                fails.append("GET /sub/14900001: tiles lack the lightbox caption data (T157)")
            imgs = re.findall(rb'<img [^>]*src="/img[^>]*>', body)
            if not imgs or any(b'loading="lazy"' not in i or b'decoding="async"' not in i
                               for i in imgs):
                fails.append("GET /sub/14900001: a tile scan lacks lazy loading or async decoding")
            # --- the detail page says the same word on the same rung, and the
            # old lowercase note under the ETA badge is gone (T114)
            if b"<b>Grades ready</b>" not in body or b" of 8" in body:
                fails.append("GET /sub/14900001: the stage word is not Grades ready")
            if b'estnote">grades ready' in body:
                fails.append("GET /sub/14900001: the redundant grades ready note is back")
            if b"Completing" in body:
                fails.append("GET /sub/14900001: the header rung still says Completing")
            # an ISO ship date reads like every other date, never raw (T183)
            body = check("GET /sub/14900004", "/sub/14900004", (200,), cookie,
                         must_have="Sep 6")
            if b"2026-09-06" in body:
                fails.append("GET /sub/14900004: the ISO ship date prints raw (T183)")
            body = check("GET /sub/14900002", "/sub/14900002", (200,), cookie)
            # prelim is said once, in the sub header, never per tile (T207)
            if body.count(b"Not graded yet") != 1 or not re.search(rb'<h1>#14900002</h1>\n?<div class="sub">[^<]*(<b[^>]*>[^<]*</b>[^<]*)*Not graded yet</div>', body):
                fails.append("GET /sub/14900002: Not graded yet is not said once in the header (T207)")
            # T160: an h2 per tile, a skip link, no empty alt, the lightbox is a
            # dialog, and no mouse-only title tooltips
            for p in ("/sub/14900001", "/sub/14900002", "/cards",
                      "/search?q=Charizard", "/search?q=Umbreon"):
                b = call(url, p, cookie)[1] or b""
                tiles = b.count(b'<div class="gc')
                if not tiles or b.count(b"<h2 ") < tiles or b.count(b'<h2 class="nm" title="') != tiles:
                    fails.append(f"GET {p}: {tiles} tiles but not an h2 each (T160)")
                if b'class="skip" href="#content"' not in b or b'id="content"' not in b:
                    fails.append(f"GET {p}: no working skip link (T160)")
                if b'alt=""' in b:
                    fails.append(f'GET {p}: an img with alt="" (T160)')
                if b'href="/img?' in b and b.count(b'aria-haspopup="dialog"') != b.count(b'href="/img?'):
                    fails.append(f"GET {p}: a lightbox link does not announce a dialog (T160)")
                if b'title="No cert number' in b or b'title="no price for' in b:
                    fails.append(f"GET {p}: a mouse-only title tooltip is back (T160)")
            sb = call(url, "/sub/14900001", cookie)[1] or b""
            if sb.count(b'<h2 class="nm"') != sb.count(b'<div class="gc'):
                fails.append("GET /sub/14900001: h2 count != tile count (T160)")
            for p in ("/",):
                if b'alt=""' in (call(url, p, cookie)[1] or b""):
                    fails.append(f'GET {p}: an img with alt="" (T160)')
            if b"<b>Arrived</b>" not in body or b"Grades ready" in body:
                fails.append("GET /sub/14900002: a sub with no grades yet lost its "
                             "own stage word (T114)")
            # the detail page counts days in the current stage; shipped and the
            # dashboard rows do not (T130)
            n = (datetime.date.today() - datetime.date(2026, 8, 1)).days
            if f"<b>Arrived</b> · <span>since Aug 1, {n} days</span></span>".encode() not in body:
                fails.append(f"GET /sub/14900002: no '{n} days' on the current stage (T130)")
            if re.search(rb", \d+ days?</span>", check("GET /sub/14900004 (T130)", "/sub/14900004",
                                                      (200,), cookie)):
                fails.append("GET /sub/14900004: a shipped sub still counts days (T130)")
            if re.search(rb'class="stage"><span>[^\n]*?, \d+ days?</span>',
                         check("GET / (T130)", "/", (200,), cookie)):
                fails.append("GET /: a dashboard row counts stage days (T130)")
            body = check("GET /sub/14900003 (unmapped status)", "/sub/14900003",
                         (200,), cookie, must_have="Status unknown")
            if b'<div class="bar">' in body:
                fails.append("GET /sub/14900003: the unmapped status still draws a stage bar")
            if b"stage 1 of" in body:
                fails.append("GET /sub/14900003: the unmapped status reads as stage 1")
            if b'<div class="gr"></div>' not in body:
                fails.append("GET /sub/14900003: an ungraded tile skips the grade line (T77)")
            # --- one vocabulary for the return date, and a hold keeps it (T65).
            # "Back <date>" everywhere, the year whenever it is not this one,
            # "Late · due <date>" in the ink pill once PSA is late, and a held
            # sub prints the hold AND the date on every surface.
            soon, nextyr = eta_text(ETA_SOON), eta_text(ETA_NEXT_YEAR)
            dash = check("GET / (T65 return dates)", "/", (200,), cookie) or b""

            def row(num):
                for chunk in dash.split(b'<div class="card'):
                    if b'data-sub="' + num + b'"' in chunk:
                        return chunk
                return b""

            if b"Back ~" in dash or b"Estimate pending" in dash:
                fails.append("GET /: the old ETA wording is still on the dashboard")
            if b"back " + nextyr.encode() not in row(b"14900001"):
                fails.append("GET /: a return date in another year prints no year")
            held = row(b"14900002")
            if b'class="pill hold"' not in held or b"<b>Arrived</b> \xc2\xb7 <span>back " + soon.encode() not in held:
                fails.append("GET /: a held sub does not show both the hold and its return date")
            # the row wears the hold class the muted-bar rule keys off (T75)
            if not held.startswith(b' hold"'):
                fails.append("GET /: a held row carries no hold class, its bar stays accent")
            if row(b"14900001").startswith(b' hold"'):
                fails.append("GET /: a live row is marked held, its bar is muted for nothing")
            late = row(b"14900003")
            if '<span class="late">late, due '.encode() + eta_text(ETA_PAST).encode() not in late:
                fails.append("GET /: a blown ETA does not read as late on the stage line (T117)")
            if b'class="late"' in row(b"14900001") or b'class="late"' in held:
                fails.append("GET /: an on-time ETA reads late (T117)")
            if css and b".stage .late{font-weight:650;color:var(--txt)}" not in css:
                fails.append("GET /app.css: .stage .late lost its weight and ink (T117)")
            # one status line per row: no stage N of 8, no ETA or Shipped pill,
            # a shipped row has no bar and one ship line (T205)
            if b" of 8" in dash or b'class="pill"' in dash or b"pill shipped" in dash:
                fails.append("GET /: a row still states its status twice (T205)")
            ship = row(b"14900004")
            if (b'<div class="bar">' in ship or ship.count(b"Sep 6") != 1
                    or not re.search(rb'<div class="stage nobar"[^>]*><span><b>Shipped</b> \xc2\xb7 Sep 6', ship)):
                fails.append("GET /: the shipped row is not one ship line without a bar (T205)")
            # what moved since the last look keys every row, no-bar lines too, and
            # the dot is the attention dot grammar, no new colour (T191)
            if (b'class="stage nobar" data-k="14900004" data-st="7"' not in ship
                    or b'data-k="14900003" data-st="u"' not in late
                    or b"psa_new" not in (js or b"")
                    or b".card.moved .num::after" not in (css or b"")):
                fails.append("GET /: rows are not keyed for the since-last-look marker (T191)")
            if b'class="pill hold"' in row(b"14900001") or b"pill hold" in late:
                fails.append("GET /: a pill shows on a row that is not held (T205)")

            # a window inside one year prints that year once, on the end
            for num, want in (("14900001", (ETA_NEXT_YEAR - datetime.timedelta(days=7))
                               .strftime("%b ") + str((ETA_NEXT_YEAR - datetime.timedelta(days=7)).day) + " to " + nextyr),
                              ("14900002", soon),
                              ("14900003", "Late · due " + eta_text(ETA_PAST))):
                dbody = call(url, "/sub/" + num, cookie)[1] or b""
                badge = re.search(rb'<h1>#\d+</h1>\n?<div class="sub">.*?</div>', dbody, re.S)
                badge = badge.group(0) if badge else b""
                if want.encode() not in badge:
                    fails.append(f"GET /sub/{num}: the ETA badge does not say {want!r}")
                if re.search(rb"\d{4}-\d{2}-\d{2}", badge):
                    fails.append(f"GET /sub/{num}: the ETA badge still prints an ISO date")
            hsub = call(url, "/sub/14900002", cookie)[1] or b""
            if b'class="holdb">On hold' not in hsub:
                fails.append("GET /sub/14900002: the detail badge dropped the hold")
            # a hold reads Paused with a muted bar and one sentence on the detail
            # and person pages, never on the dashboard; a blown date says PSA
            # has not re-estimated, and a held late sub still reads Paused (T147).
            # An unknown hold code promises nothing; a financial one (HOLD.DCC)
            # names the submitter, never the card owners
            hnote = b"PSA paused this submission. It moves again once PSA lifts the hold."
            fnote = b"PSA paused this submission until the submitter clears a financial hold with them."
            lnote = b"PSA has not issued a new estimate."
            if (b"PSA ETA paused" not in hsub or b'class="dstage hold"' not in hsub
                    or hsub.count(hnote) != 1 or b"Was " + soon.encode() not in hsub):
                fails.append("GET /sub/14900002: the hold does not read Paused with a muted bar and one note (T147)")
            if hnote in dash or lnote in dash:
                fails.append("GET /: the hold or late note leaked onto the dashboard (T147)")
            if lnote not in (call(url, "/sub/14900003", cookie)[1] or b""):
                fails.append("GET /sub/14900003: a past-due sub does not say PSA has not re-estimated (T147)")
            db = sqlite3.connect(os.path.join(base, "accounts", "demo", "psa.db"))
            db.execute("UPDATE subs SET on_hold = 1, hold_reason = 'HOLD.DCC' WHERE sub_number = '14900003'")
            db.commit()
            hl = call(url, "/sub/14900003", cookie)[1] or b""
            db.execute("UPDATE subs SET on_hold = 0, hold_reason = NULL WHERE sub_number = '14900003'")
            db.commit()
            db.close()
            if (b"PSA ETA paused" not in hl or "Late ·".encode() in hl or hl.count(fnote) != 1
                    or hnote in hl or b"Nothing is needed" in hl or lnote not in hl or b"Was due " + eta_text(ETA_PAST).encode() not in hl):
                fails.append("GET /sub/14900003: a held late financial-hold sub does not read Paused with the submitter note (T147)")

            # the person page runs the same pill, so a held sub reads the same there
            call(url, "/owner", cookie, {"cert_id": "spec:14900002:1", "owner": "Etaperson"})
            pbody = check("GET /cards?owner=Etaperson", "/cards?owner=Etaperson",
                          (200,), cookie) or b""
            if b'class="pill hold"' not in pbody or b"back " + soon.encode() not in pbody:
                fails.append("GET /cards?owner=Etaperson: the held sub loses its return date")
            if pbody.count(hnote) != 1:
                fails.append("GET /cards?owner=Etaperson: the held sub carries no hold note (T147)")
            call(url, "/owner", cookie, {"cert_id": "spec:14900002:1", "owner": ""})

            # --- retagging off the page's person drops the tile and the header
            # count in place; the reload agrees (T168)
            call(url, "/owner", cookie, {"cert_id": "99000001", "owner": "Bob"})
            call(url, "/owner", cookie, {"cert_id": "99000002", "owner": "Bob"})
            bob = check("GET /cards?owner=Bob", "/cards?owner=Bob", (200,), cookie,
                        must_have="2 cards with") or b""
            # one way into Discord pings on a one-owner sub and on the person
            # page; the sub link lands on the page with the panel open (T137)
            sb = call(url, "/sub/14900001", cookie)[1] or b""
            if (sb.count(b"#discord") != 1 or b'class="f dbtn" href="/cards?owner=Bob#discord">'
                    b"Get pinged when your cards move</a>" not in sb
                    or bob.count(b'id="dopen"') != 1 or b"#discord" in bob
                    or (js and b"if(location.hash==='#discord')" not in js)):
                fails.append("GET /sub/14900001, /cards?owner=Bob: not one way into Discord pings (T137)")
            # a mixed sub names each owner without pings, sorted, escaped; none
            # once everyone is on (T137)
            call(url, "/owner", cookie, {"cert_id": "99000002", "owner": "al & co"})
            al = '<a class="tlink" href="/cards?owner=al%20%26%20co#discord">al &amp; co</a>'
            bo = '<a class="tlink" href="/cards?owner=Bob#discord">Bob</a>'
            for linked, want in (((), f"move: {al} · {bo}</div>"), (("Bob",), f"move: {al}</div>"),
                                 (("Bob", "al & co"), None)):
                for o in linked:
                    call(url, "/discord", cookie, {"owner": o, "id": "123456789012345678"})
                sb = call(url, "/sub/14900001", cookie)[1] or b""
                ok = (want.encode() in sb and sb.count(b"#discord") == want.count("#discord")
                      if want else b"#discord" not in sb)
                if not ok:
                    fails.append(f"GET /sub/14900001: mixed sub pings line wrong with {linked} on (T137)")
            for o in ("Bob", "al & co"):
                call(url, "/discord", cookie, {"owner": o, "id": ""})
            check("GET /cards?owner=Bob (retagged)", "/cards?owner=Bob", (200,), cookie,
                  must_have="1 card with")
            if js and (b"function _recount(" not in js or b"leave=setTimeout(go,6000)" not in js
                       or b"if(!_mine(old))leave=setTimeout(go," not in js):
                fails.append("GET /app.js: a retag off the person page leaves the list stale (T168)")
            if js and b"if(had&&nx&&document.activeElement===document.body)nx.focus()" not in js:
                fails.append("GET /app.js: a retagged tile leaving drops focus to the body (T168)")
            # Enter and Escape hand focus back to the tag, and the chip sits in
            # the row in the pencil's place so a save never moves the grid (T136)
            if js and (b"} else { i.blur(); refocus(); }" not in js
                       or b"i.value=prev; i.blur(); refocus(); }" not in js
                       or b"row.appendChild(u);" not in js):
                fails.append("GET /app.js: an owner save drops focus or moves the grid (T136)")
            if css and b".ownrow:has(.undo) .ownedit{display:none}" not in css:
                fails.append("GET /app.css: the owner chip no longer takes the pencil's place (T136)")
            call(url, "/owner", cookie, {"cert_id": "99000001", "owner": ""})
            call(url, "/owner", cookie, {"cert_id": "99000002", "owner": ""})

            # --- the person page carries the dashboard's three sort pills, so
            # a person with two active subs can reorder their submission groups
            # by soonest return. SORT_JS needs #list plus data-sub/svc/eta on
            # every group card; the Archived pill shares the row in .rowend
            # and no longer owns a .filterrow of its own (T102)
            call(url, "/owner", cookie, {"cert_id": "99000001", "owner": "Twosub"})
            call(url, "/owner", cookie, {"cert_id": "spec:14900002:1", "owner": "Twosub"})
            tbody = check("GET /cards?owner=Twosub", "/cards?owner=Twosub",
                          (200,), cookie) or b""
            # same ?sort=&dir= as the dashboard, rendered server-side (T152)
            for q, want in (("", [b"14900002", b"14900001"]),
                            ("&sort=eta&dir=desc", [b"14900001", b"14900002"]),
                            ("&sort=nope&dir=desc", [b"14900002", b"14900001"])):
                got = re.findall(rb'<h2 class="num">#(\d+)</h2>',
                                 check("GET /cards?owner=Twosub" + q, "/cards?owner=Twosub" + q,
                                       (200,), cookie) or b"")
                if got != want:
                    fails.append(f"GET /cards?owner=Twosub{q}: order {got} (T152)")
            row = re.search(rb'<div class="filterrow">.*?(?=<div id="list")', tbody, re.S)
            row = row.group(0) if row else b""
            for want in (b'<div class="filters" role="group" aria-label="Sort submissions">',
                         b'data-sort="sub" aria-pressed="true">Newest<',
                         b'data-sort="svc" aria-pressed="false">Service<',
                         b'data-sort="eta" aria-pressed="false">Return<'):
                if want not in row:
                    fails.append("GET /cards?owner=Twosub: the sort capsule is missing "
                                 + want.decode())
            if b'<div id="list">' not in tbody:
                fails.append("GET /cards?owner=Twosub: no #list for the sort to reorder")
            grp = re.findall(rb'<div class="card grp[^>]*>', tbody)
            if len(grp) != 2:
                fails.append(f"GET /cards?owner=Twosub: {len(grp)} groups, want 2")
            # Service sorts by tier fee, so every group carries its price (T151)
            if row.count(b'class="f fsort') != 3 or not all(b'data-price="109.0"' in g for g in grp):
                fails.append("GET /cards?owner=Twosub: not three pills or a group lacks its tier price")
            for want in (b'data-sub="14900002"', b'data-sub="14900001"',
                         b'data-svc="Regular"',
                         b'data-eta="%s"' % ETA_SOON.isoformat().encode(),
                         b'data-eta="%s"' % ETA_NEXT_YEAR.isoformat().encode()):
                if not any(want in g for g in grp):
                    fails.append("GET /cards?owner=Twosub: no group carries "
                                 + want.decode())
            # styling rides on classes: the only style attributes left are served
            # values (bar width, --i stagger), JS-owned display:none and the
            # close icon's vertical-align (T180)
            for path, ck in (("/", cookie), ("/sub/14900001", cookie),
                             ("/cards?owner=Twosub", cookie), ("/search?q=pikachu", cookie),
                             ("/search?q=zzzz", cookie), ("/sub/99999999", cookie),
                             ("/settings", scookie), ("/app.js", None)):
                sb = call(url, path, ck)[1] or b""
                bad = set(STYLE_ATTR.findall(sb)) - STYLE_OK if sb else {b"<no body>"}
                bad = {v for v in bad if not STYLE_DYN.fullmatch(v)}
                if bad:
                    fails.append(f"GET {path}: static inline style left: "
                                 + ", ".join(sorted(v.decode() for v in bad)) + " (T180)")
            arch("14900001", "1")
            abody = call(url, "/cards?owner=Twosub", cookie)[1] or b""
            arow = re.search(rb'<div class="filterrow">.*?(?=<div id="list")', abody, re.S)
            arow = arow.group(0) if arow else b""
            if b'<div class="rowend"><button' not in arow or b'id="archtoggle"' not in arow:
                fails.append("GET /cards?owner=Twosub: Archived is not in the "
                             "sort row's .rowend")
            if abody.count(b'class="filterrow"') != 1:
                fails.append("GET /cards?owner=Twosub: Archived kept a second filter row")
            arch("14900001", "0")
            call(url, "/owner", cookie, {"cert_id": "99000001", "owner": ""})
            call(url, "/owner", cookie, {"cert_id": "spec:14900002:1", "owner": ""})

            check("GET /sub/nope (missing)", "/sub/99999999", (404,), cookie)
            if b"Try again" in check("GET /nope (unknown path)", "/nope", (404,), cookie):
                fails.append("GET /nope: 404 offers Try again, want Back only")
            check("GET /logout", "/logout", (302,), cookie)

            # --- sign out drops the settings cookie too (T6)
            _, _, lhdrs = call(url, "/logout", cookie)
            if not any(h.startswith("psa_settings=;")
                       for h in (lhdrs.get_all("Set-Cookie") or [])):
                fails.append("GET /logout: the settings cookie is left alive")
            # sign out lands on a gate that says so, once (T167)
            if lhdrs.get("Location") != "/?out":
                fails.append(f"GET /logout: Location {lhdrs.get('Location')!r}, want '/?out'")
            out = check("GET /?out (signed out)", "/?out", (200,),
                        must_have="You’re signed out.")
            if b"history.replaceState" not in out:
                fails.append("GET /?out: reload would repeat the signed-out line")
            if b"signed out" in check("GET / (plain gate)", "/", (200,)):
                fails.append("GET /: plain gate shows the signed-out line")

            # --- rotating the site password revokes outstanding cookies (T6)
            def site_pw(value, current=None):
                return call(url, "/settings/account", scookie,
                            {"acct": "demo", "action": "site_pw", "value": value, "value2": value,
                             **({} if current == "" else {"current": current or cur[0]})})

            cur = [SITE_PW]
            # the change needs the current site password, and says what it does (T132)
            check("GET /settings (site password helper)", "/settings", (200,), scookie,
                  must_have="Changing this signs out everyone who is currently signed in.")
            for label, current in (("missing", ""), ("wrong", "not-the-pw")):
                envf = os.path.join(base, "accounts", "demo", "account.env")
                ewas = open(envf, "rb").read()
                _, _, h = site_pw(SITE_PW + "-nope", current)
                body = call(url, h.get("Location") or "/settings", scookie)[1]
                if open(envf, "rb").read() != ewas or b"Current site password is wrong." not in body:
                    fails.append(f"POST /settings/account site_pw ({label} current): not refused")
                code, _, hdrs = call(url, "/login", form={"password": SITE_PW})
                if code != 302 or not (hdrs.get("Set-Cookie") or ""):
                    fails.append(f"POST /login after a {label}-current change: old password dead")
            code, _, h = site_pw(SITE_PW + "-rotated")
            cur[0] = SITE_PW + "-rotated"
            if code != 303 or ("Site password changed. Everyone signed in with the old one "
                               "has to sign in again.").encode() not in call(
                                   url, h.get("Location") or "/settings", scookie)[1]:
                fails.append("POST /settings/account site_pw: rotation refused or no success line")
            check("GET / (cookie after a password rotation)", "/", (200,), cookie,
                  must_have='action="/login"')
            check("GET /settings (settings session survives a rotation)", "/settings", (200,),
                  scookie, must_have="PSA accounts")
            code = site_pw(SITE_PW)[0]
            cur[0] = SITE_PW
            if code != 303:
                fails.append("POST /settings/account site_pw: restore refused")
            check("GET / (cookie after the password is restored)", "/", (200,),
                  cookie, must_have="14900001")

            # --- a newline in a settings value used to truncate account.env,
            # which dropped the account and reopened first-run setup (T18)
            envf = os.path.join(base, "accounts", "demo", "account.env")
            ewas = open(envf, "rb").read()
            site_pw("bad\npw")
            if open(envf, "rb").read() != ewas:
                fails.append("POST /settings/account site_pw (newline): account.env was rewritten")
            code, _, hdrs = call(url, "/login", form={"password": SITE_PW})
            if code != 302 or not (hdrs.get("Set-Cookie") or ""):
                fails.append(f"POST /login after a newline site password: got {code}, "
                             "the account no longer logs in")

            # --- a gear-mode admin session stays on its own account (T7)
            env2 = os.path.join(base, "accounts", "second", "account.env")
            was = open(env2, "rb").read()
            gcode = call(url, "/settings/account", cookie,
                         {"acct": "second", "action": "site_pw",
                          "value": "other-pw", "value2": "other-pw"})[0]
            if gcode != 403:
                fails.append(f"POST /settings/account (other account): got {gcode}, want 403")
            if open(env2, "rb").read() != was:
                fails.append("POST /settings/account: another account's env was rewritten")
            if call(url, "/settings/add", cookie,
                    {"psa_email": "third@example.com", "psa_pw": "x"})[0] != 403:
                fails.append("POST /settings/add (gear session): an account was added")
            body = check("GET /settings (gear session)", "/settings", (200,), cookie,
                         must_have="PSA accounts")
            if body and b'data-acct="second"' in body:
                fails.append("GET /settings (gear session): another account's chip renders")
            if body and b'data-acct="demo"' not in body:
                fails.append("GET /settings (gear session): the session's own chip is missing")
            body = call(url, "/settings?only=second", cookie)[1] or b""
            if b'data-acct="second"' in body:
                fails.append("GET /settings?only=second (gear session): another account's pane")
            genv = os.path.join(base, "global.env")
            gwas = open(genv, "rb").read()
            if call(url, "/settings/password", cookie,
                    {"new_pw": "hijacked1", "confirm_pw": "hijacked1"})[0] != 403:
                fails.append("POST /settings/password (gear session): got a reply, want 403")
            if open(genv, "rb").read() != gwas:
                fails.append("POST /settings/password (gear session): the settings password was rotated")

            # --- a POST carrying a foreign Origin is refused (T14)
            tag = {"cert_id": "99000001", "owner": "Mallory"}
            if call(url, "/owner", cookie, tag,
                    {"Origin": "https://demo.example.com"})[0] != 403:
                fails.append("POST /owner (foreign Origin): got a reply, want 403")
            body = check("GET /sub/14900001 (after a foreign-Origin POST)",
                         "/sub/14900001", (200,), cookie)
            if b"Mallory" in body:
                fails.append("POST /owner (foreign Origin): the tag was written anyway")
            if call(url, "/owner", cookie, tag, {"Origin": url})[0] != 204:
                fails.append("POST /owner (own Origin): refused, the page's own posts break")
            body = check("GET /sub/14900001 (after the page's own POST)", "/sub/14900001",
                         (200,), cookie, must_have="Mallory")
            # --- the owner tag says ONE sentence, tooltip and accessibility
            # tree alike, and hints Done on a touch keyboard (T56)
            own = re.search(rb'<input class="own"[^>]*>', body or b"")
            sent = (b"Owner: Mallory. Click or press Enter to open their cards, "
                    b"click again or type to rename.")
            if not own:
                fails.append("GET /sub/14900001: no owner tag")
            else:
                o = own.group(0)
                if b'title="' + sent + b'"' not in o or b'aria-label="' + sent + b'"' not in o:
                    fails.append("GET /sub/14900001: the owner tag's tooltip and "
                                 "accessible name are not the same sentence")
                if b'enterkeyhint="done"' not in o:
                    fails.append("GET /sub/14900001: the owner tag carries no enter-key hint")

            # --- a tag for a cert that has no card is refused, so owners.db
            # never grows an orphan row (T32)
            if call(url, "/owner", cookie, {"cert_id": "undefined", "owner": "Ghost"},
                    {"Origin": url})[0] != 400:
                fails.append("POST /owner (cert_id=undefined): got a reply, want 400")
            oc = sqlite3.connect(os.path.join(base, "accounts", "demo", "owners.db"))
            orphans = oc.execute("SELECT count(*) FROM owners WHERE cert_id=?",
                                 ("undefined",)).fetchone()[0]
            oc.close()
            if orphans:
                fails.append("POST /owner (cert_id=undefined): the tag was written anyway")

            # --- the dashboard's first paint carries the ACTIVE rows only:
            # archived ones are fetched by the Archived pill from /?arch=1 (T28)
            def archive(num, on):
                return call(url, "/archive", cookie, {"sub": num, "on": on},
                            {"Origin": url})[0]

            if archive("14900002", "1") != 204:
                fails.append("POST /archive: refused, nothing to test the fold with")
            body = check("GET / (one sub archived)", "/", (200,), cookie)
            if b'data-arch="1"' in body:
                fails.append("GET /: an archived row is still in the first paint")
            if b"14900002" in body:
                fails.append("GET /: the archived sub is still rendered on the dashboard")
            if b'id="archtoggle"' not in body:
                fails.append("GET /: no Archived pill to fetch the archived rows with")
            frag = check("GET /?arch=1", "/?arch=1", (200,), cookie,
                         must_have='data-arch="1"')
            if b"14900002" not in frag:
                fails.append("GET /?arch=1: the archived row is missing")
            if b"14900001" in frag:
                fails.append("GET /?arch=1: an active row rode along")
            # a slow archived fetch shows skeleton rows, never an empty list (T199)
            if (b"lst.setAttribute('aria-busy','true')" not in body
                    or b"#list .card:not(.skcard)" not in body):
                fails.append("GET /: the Archived pill has no skeleton while fetching (T199)")
            if archive("14900002", "0") != 204:
                fails.append("POST /archive (unarchive): refused")

            # --- ARCH_JS disables the button it was fired from, which drops
            # keyboard focus to body and strands the 6 second Undo chip (T52)
            js = check("GET /app.js (T52)", "/app.js", (200,), cookie)
            if js and b"back(u,foc)" not in js:
                fails.append("GET /: archiving does not move focus to the Undo chip")
            # one undo affordance: the chip names the action and stands in for
            # the row's button, and the row stays grey under the cursor (T133)
            if js and (b"(on?'Archived':'Unarchived')+' \\u00b7 Undo'" not in js
                       or b"f.insertBefore(u,b); b.hidden=true;" not in js
                       or js.count(b"b.hidden=false;") != 2):
                fails.append("GET /app.js: archiving leaves two undo words on the row (T133)")
            # a failed archive's label timer dies on the next click, and the
            # failure text builds from the action, not the last label (T216)
            if js and (b"clearTimeout(b._ft);" not in js
                       or b"label=on?'Archive':'Unarchive'" not in js):
                fails.append("GET /app.js: a stale failure timer outlives a retry (T216)")
            if css and b".card.arch:has(.undo):hover{filter:grayscale(.55)}" not in css:
                fails.append("GET /app.css: an archived row un-greys under the cursor (T133)")
            # the archive chip lasts 10s, holds while hovered or focused, pins to
            # the thumb zone at 44px on touch, and the detail page flips in place (T144)
            if js and (b"t=setTimeout(go,10000)" not in js
                       or b"u.onmouseenter=function(){hov=true;arm();}" not in js
                       or b"u.onfocus=function(){fcs=u.matches(':focus-visible');arm();}" not in js
                       or b"var o=document.querySelector('body>.undo'); if(o)o._go();" not in js
                       or b"document.body.appendChild(u);" not in js
                       or b"if(row&&!document.getElementById('archtoggle')){location.reload();return;}" not in js):
                fails.append("GET /app.js: the archive Undo chip is brief, unpausable, stacks or reloads /sub (T144)")
            # a tab back after over an hour hidden reloads once (T123)
            if js and (b"if(!hid||Date.now()-hid<=36e5)return;" not in js or b"return e.value!==e.defaultValue;});\n    if(!dirty){location.reload();}" not in js):
                fails.append("GET /app.js: no guarded reload when a tab returns after an hour hidden (T123)")
            if css and (b"body>.undo{position:fixed;left:20px;bottom:calc(20px + env(safe-area-inset-bottom,0px))" not in css
                        or b"min-height:44px" not in css.split(b"body>.undo{", 1)[-1].split(b"}", 1)[0]):
                fails.append("GET /app.css: the touch Undo chip is not a 44px thumb-zone chip (T144)")
            check("GET /sub/14900001 (archtag)", "/sub/14900001", (200,), cookie,
                  must_have='<div class="sub" id="archtag" hidden>Archived</div>')
            if b'title="Archived submissions are hidden from the list. Nothing is deleted."' not in body:
                fails.append("GET /: the Archived pill has no helper line (T133)")

            # --- one Escape closes the search preview: without preventDefault
            # the native type=search clear fires `input` and reopens it (T53)
            if js and b"'Escape'){e.preventDefault()" not in js:
                fails.append("GET /app.js: Escape still lets the search preview reopen")

            # --- re-clicking the active sort pill reverses the list; two of the
            # three pills keep their label, so the flip has to be spoken (T54)
            if js and b"if(again)_say(SAID[m][rev?1:0])" not in js:
                fails.append("GET /app.js: a sort reversal is not announced")

            # --- the submission list is a list and every row's sub number is
            # that row's heading, so a screen reader can skip rows instead of
            # tabbing through ten controls apiece (T55)
            dash = check("GET / (list semantics)", "/", (200,), cookie)
            if dash:
                if b'id="list" tabindex="-1" role="list"' not in dash:
                    fails.append("GET /: #list carries no list role")
                if dash.count(b'role="listitem"') != 4:
                    fails.append("GET /: the submission rows are not list items")
                if dash.count(b'<h2 class="num">') != 4:
                    fails.append("GET /: a submission row has no heading")
                if b"Shipped</b> \xc2\xb7 Sep 6" not in dash or b"2026-09-06" in dash:
                    fails.append("GET /: the ISO ship date prints raw (T183)")
                # the row settle staggers off a served --i, not an nth-child list (T178)
                if b'style="--i:0"' not in dash or b'style="--i:3"' not in dash:
                    fails.append("GET /: rows carry no --i stagger index (T178)")

            # --- an open lightbox locks the page: the drag must not chain to
            # the dashboard 900px behind the scrim, and close must give it back (T57)
            if js:
                if js.count(b"document.body.style.overflow") != 4:
                    fails.append("GET /app.js: the lightbox or a sheet does not lock the page")
                # Back closes the lightbox and the sheets: each open pushes one
                # entry, popstate closes, and every other close pops it (T127)
                if (js.count(b"history.pushState({ov:1},'')") != 2
                        or js.count(b"if(history.state&&history.state.ov)history.back();") != 2
                        or b"addEventListener('popstate', close);" not in js
                        or b"addEventListener('popstate',function(){\n    document.querySelectorAll('.smodal.on')" not in js):
                    fails.append("GET /app.js: Back does not close the lightbox or a sheet (T127)")
            if css and b"cursor:zoom-out;overscroll-behavior:contain" not in css:
                fails.append("GET /app.css: a drag on the lightbox scrim still chains")

            # --- the masthead scrolls away at every width, only the search field
            # sticks; the sort segment and solo pills carry no glass; the hint card
            # is gone, its words are the search placeholder (T209, was T58)
            if js and (b"tb.style.top=(10-(tt.offsetHeight" not in js
                       or b"if(!mq.matches){tb.style.top=''" in js):
                fails.append("GET /app.js: the masthead does not scroll away at every width (T209)")
            glass = re.findall(rb"([^{}]*)\{[^}]*backdrop-filter:blur\(16px\)", css or b"")
            if any(b".filters" in g or b"fsolo" in g for g in glass):
                fails.append("GET /app.css: the sort segment or a solo pill is still glass (T209)")
            _, db, _ = call(url, "/", cookie)
            if (b'id="hint"' in db or b"psa_hint_seen" in db
                    or b'placeholder="Type your name to find your cards"' not in db):
                fails.append("GET /: the hint card is back or the placeholder lost its words (T209)")

            # --- the sub number is a 22px line, so it needs the pills' hit
            # pseudo to reach the 44px floor, vertically only (T59)
            if css:
                if b".numlink{" in css and b"position:relative" not in re.search(
                        rb"\.numlink\{[^}]*\}", css).group(0):
                    fails.append("GET /app.css: .numlink is not a positioning box")
                if b".numlink::before{content:'';position:absolute;inset:-11px 0}" not in css:
                    fails.append("GET /app.css: the sub number has no 44px hit box")

            # --- login throttle: a spoofed header neither locks anyone else out
            # nor buys a fresh budget (T4). Keep before the db damage below.
            check("POST /login (wrong, spoofed header)", "/login", (200,),
                  form={"password": "nope"}, headers={"X-Forwarded-For": "9.9.9.9"},
                  must_have="Incorrect password")
            code, _, hdrs = call(url, "/login", form={"password": SITE_PW})
            if code != 302 or not (hdrs.get("Set-Cookie") or ""):
                fails.append("POST /login after a spoofed-header failure: "
                             f"got {code}, another visitor is locked out")
            # --- one guesser pauses itself, never the store's customers (T115)
            for i in range(MAX_FAILS):
                check(f"POST /login (one IP, wrong {i})", "/login", (200,),
                      form={"password": "nope"},
                      headers={"X-Forwarded-For": "10.0.0.7"},
                      must_have="Incorrect password")
            check("POST /login (offending IP, paused)", "/login", (200,),
                  form={"password": "nope"}, headers={"X-Forwarded-For": "10.0.0.7"},
                  must_have="paused for 15 minutes")
            # a second visitor still gets the gate, and the site-wide budget
            # only slows that attempt down (0.4s base, 2.4s while hot)
            t0 = time.time()
            check("POST /login (second visitor, wrong)", "/login", (200,),
                  form={"password": "nope"}, headers={"X-Forwarded-For": "10.0.1.1"},
                  must_have="Incorrect password")
            if time.time() - t0 < 2:
                fails.append("POST /login: a spread-out guess buys no site-wide delay")
            code, _, hdrs = call(url, "/login", form={"password": SITE_PW},
                                 headers={"X-Forwarded-For": "10.0.1.2"})
            if code != 302 or not (hdrs.get("Set-Cookie") or ""):
                fails.append(f"POST /login from a second visitor: got {code}, "
                             "one guesser locked the whole site out")

            # --- a failed read is a 500 page, never an empty account (T3)
            hub = "/api/hub.json?key=" + HUB_KEY
            check("GET /api/hub.json (key)", hub, (200,), must_have='"subs"')

            # --- the key rides a header, and the legacy query form never
            # reaches the log (T29)
            check("GET /api/hub.json (header key)", "/api/hub.json", (200,),
                  headers={"X-Hub-Key": HUB_KEY}, must_have='"subs"')
            check("GET /api/hub.json (bad header key)", "/api/hub.json", (404,),
                  headers={"X-Hub-Key": "nope"})

            # --- the card PNG the hub fetches on a change (T107). Same gate
            # as hub.json, so no key is a 404 and an unknown sub is a 404. On a
            # known sub the handler shells out to psa_shot.py, which imports
            # playwright: absent here, so the expected smoke answer is 503
            # "render failed" (a 200 PNG means the renderer happened to work).
            # Either way it must answer, not crash or hang.
            check("GET /api/shot (no key)", "/api/shot/14900003.png", (404,))
            check("GET /api/shot (bogus sub)", "/api/shot/14999999.png", (404,),
                  headers={"X-Hub-Key": HUB_KEY})
            check("GET /api/shot (known sub)", "/api/shot/14900003.png", (200, 503),
                  headers={"X-Hub-Key": HUB_KEY})

            # --- the hub alerts off the per-account health block, so it has
            # to carry every account and the cause line run_scan's scripts
            # write into .last_error (T105)
            errf = os.path.join(base, "accounts", "demo", ".last_error")
            with open(errf, "w", encoding="utf-8") as f:
                f.write("cookie expired: PSA answered the sign-in page\n")
            hb = check("GET /api/hub.json (accounts)", hub, (200,),
                       must_have='"accounts"')
            try:
                row = (json.loads(hb or b"{}").get("accounts") or {}).get("demo")
            except ValueError:
                row = None
            if not row:
                fails.append("GET /api/hub.json: no accounts entry for demo")
            elif "cookie expired" not in (row.get("error") or ""):
                fails.append(f"GET /api/hub.json: demo carries no .last_error ({row!r})")
            os.remove(errf)
            if HUB_KEY in open(logpath, encoding="utf-8", errors="replace").read():
                fails.append("log: /api/hub.json logged the key")

            # --- a settings POST answers a 303, so the reply page is a GET and
            # reloading it cannot resubmit the form. Add used to mint a second
            # account (with a second password) on every reload (T17)
            adir = os.path.join(base, "accounts")
            before = sorted(os.listdir(adir))
            acode, _, ahdrs = call(url, "/settings/add", scookie,
                                   {"psa_email": "t17@example.com", "psa_pw": "x"})
            loc = ahdrs.get("Location") or ""
            if acode != 303 or not loc.startswith("/settings?"):
                fails.append(f"POST /settings/add: got {acode} to {loc!r}, "
                             "want a 303 to /settings")
            else:
                check("GET the Add reply", loc, (200,), scookie,
                      must_have="site password is")
                check("GET the Add reply (reloaded)", loc, (200,), scookie)
            after = sorted(os.listdir(adir))
            if len(after) != len(before) + 1:
                fails.append(f"POST /settings/add: accounts went {before} -> {after}, "
                             "want exactly one more")
            dbf = os.path.join(base, "accounts", "demo", "psa.db")
            lock = sqlite3.connect(dbf, timeout=1)
            lock.execute("BEGIN EXCLUSIVE")  # readers now block, then time out
            try:
                check("GET / (db locked)", "/", (500,), cookie,
                      must_have="Something went wrong")
                check("GET /api/hub.json (db locked)", hub, (503,))
            finally:
                lock.rollback()
                lock.close()
            if os.geteuid() != 0:  # root reads a 000 file anyway
                os.chmod(dbf, 0)
                check("GET / (db unreadable)", "/", (500,), cookie,
                      must_have="Something went wrong")
                os.chmod(dbf, 0o644)
            # destroys the fixture db: keep these last
            with open(dbf, "wb") as f:
                f.write(os.urandom(40960))
            check("GET / (db corrupt)", "/", (500,), cookie,
                  must_have="Something went wrong")
            # the 500 retries the route that failed, the dashboard is secondary (T166)
            check("GET /sub/14900001 (db corrupt)", "/sub/14900001", (500,), cookie,
                  must_have='href="/sub/14900001">Try again</a><a class="view"')
            if b"style=" in (call(url, "/sub/14900001", cookie)[1] or b""):
                fails.append("GET /sub/14900001 (db corrupt): the 500 page has an inline style (T180)")
    finally:
        if proc and proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
        log.close()
        crash = open(logpath, encoding="utf-8", errors="replace").read()
        shutil.rmtree(base, ignore_errors=True)

    if fails:
        for f in fails:
            print("FAIL  " + f)
        tail = [ln for ln in crash.splitlines() if "Traceback" in ln or "Error" in ln]
        if tail:
            print("app.py said: " + " | ".join(tail[-3:]))
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
