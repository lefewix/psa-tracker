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
MAX_FAILS = 8  # app.py's login budget, per IP and site-wide
NOW = "2026-01-01T00:00:00+00:00"
# ETA dates are relative to the run: one still to come, one next year (the year
# has to print), one PSA has blown through (T65)
TODAY = datetime.date.today()
ETA_SOON = TODAY + datetime.timedelta(days=45)
ETA_NEXT_YEAR = datetime.date(TODAY.year + 1, 6, 15)
ETA_PAST = TODAY - datetime.timedelta(days=45)


def eta_text(d):
    """What short_date must print for a date: 'Sep 25', 'Jun 15, 2027'."""
    return d.strftime("%b %d") + (f", {d.year}" if d.year != TODAY.year else "")
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
            ("14900003", "ReceivedHold", 1, "", "", 0, 0, ETA_PAST, ETA_PAST)]
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


def boot(base, port, log):
    env = dict(os.environ,
               PSA_PORT=str(port), PSA_BIND="127.0.0.1", PSA_COOKIE_SECURE="0",
               PSA_SECRET="smoke-secret-not-real", PSA_SETTINGS_PW_HASH=SET_HASH,
               PSA_ACCOUNTS_DIR=os.path.join(base, "accounts"),
               PSA_GLOBAL_ENV=os.path.join(base, "global.env"),
               PSA_IMG_CACHE=os.path.join(base, "imgcache"),
               PSA_LOGO=os.path.join(ROOT, "logo.svg"),
               PSA_FAVICON=os.path.join(ROOT, "favicon.png"),
               PSA_TOUCH_ICON=os.path.join(ROOT, "apple-touch-icon.png"),
               PSA_HUB_KEY=HUB_KEY, PSA_VALUES="1", PSA_THEME="light")
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
            fails.append(f"app.py: {phrase!r} is back, the scan timer is hourly (T68)")
    if src.count("within the hour") < 2:
        fails.append("app.py: the setup note and the first sync note must both say "
                     "within the hour (T68)")


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
        check("GET /sub/14900001 (no session)", "/sub/14900001", (200,))
        check("GET / (bad token)", "/", (200,), cookie="psa_session=nope.nope.nope",
              must_have='action="/login"')
        css = check("GET /app.css", "/app.css", (200,))
        js = check("GET /app.js", "/app.js", (200,))
        # the sheet every browser downloads is CSS, not an essay. Source comments
        # are stripped when the served copy is built, so this caps the RULES, not
        # the prose - app.py may explain itself at length (T82, T112)
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

        # --- the pencil hides on the INPUT's focus, not the row's: :focus-within
        # also matched the pencil's own focus, so a tap removed the button
        # before its click and a filled tag could not be edited on a phone (T16)
        if css:
            if b":focus-within .ownedit" in css:
                fails.append("GET /app.css: the pencil still hides on the row's focus")
            if b".own:focus + .ownedit{display:none}" not in css:
                fails.append("GET /app.css: the pencil no longer hides while the tag is edited")
            # archived cards carry grayscale only, in every view: an opacity wash
            # fades the card's own surface and takes the text under 4.5:1 (T51)
            if b".card.arch{filter:grayscale(" not in css:
                fails.append("GET /app.css: archived cards no longer read as past")
            if b".card.arch{opacity" in css or b"archview .card.arch" in css:
                fails.append("GET /app.css: an archived card is washed with opacity again")
            # a held sub's bar drops to the muted grey, so it stops painting
            # full accent under the red hold pill (T75)
            if b".card.hold .bar i{background:var(--m1)}" not in css:
                fails.append("GET /app.css: a held card still paints an accent stage bar")
            if b".gc.arch .ph" in css:
                fails.append("GET /app.css: the archived no-scan placeholder is dimmed again")
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
            # under 640 the header note goes full width and left aligned, so its
            # right-align margin must be cleared or it floats mid column (T79)
            if b".hrow>.synced .estnote{margin-left:0}" not in css:
                fails.append("GET /app.css: the header note keeps its right-align "
                             "margin on phones")
            # above 640 a filmstrip has no bleed, so an overflowing one fades the
            # edge that still has tiles beyond it. The fade is driven by .sl/.sr,
            # so a strip that fits gets none of it (T80)
            if b".strip.sl{--fadel:28px}" not in css or b".strip.sr{--fader:28px}" not in css:
                fails.append("GET /app.css: an overflowing filmstrip has no edge cue "
                             "above 640px")
            if js and b"querySelectorAll('.filters,.strip')" not in js:
                fails.append("GET /app.js: the scroll cue no longer runs on filmstrips")
            # a tap that lands mid scroll must fall through the corner orbs to
            # the owner pencil or View card underneath, on touch only (T60)
            if b"html.scrolling #gearbtn,html.scrolling #themeflip{pointer-events:none" \
                    not in css:
                fails.append("GET /app.css: the corner orbs still take taps mid scroll")
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
            if [i["src"] for i in man.get("icons", [])] != ["/apple-touch-icon.png"]:
                fails.append("GET /manifest.json: the install icon is not the 180px PNG")
        check("GET / (manifest link)", "/", (200,), must_have='rel="manifest"')
        check("GET / (theme-color)", "/", (200,), must_have='name="theme-color"')
        check("GET /api/hub.json (no key)", "/api/hub.json", (404,))
        check("GET /setup (setup closed)", "/setup", (302,))
        keepalive_checks(port, fails)
        setup_instance_checks(fails)
        copy_checks(fails)
        env_checks(fails)
        common_checks(fails)
        tracking_checks(fails)
        comment_checks(fails)

        # --- non-ASCII credentials compare, they don't crash the handler (T5)
        check("GET /api/hub.json (non-ASCII key)", "/api/hub.json?key=caf%C3%A9", (404,))
        check("GET / (non-ASCII token)", "/", (200,),
              cookie="psa_session=demo.9999999999.caf\u00e9",
              must_have='action="/login"')
        check("POST /login (non-ASCII password)", "/login", (200,),
              form={"password": "caf\u00e9"}, must_have="Incorrect password")

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
            # about, and never auto-refreshes under a code field (T11)
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
            if b'http-equiv="refresh"' not in b_armed:
                fails.append("GET /settings (otp armed): no auto-refresh while waiting for the SMS")
            b_wait = otp("armed", "waiting")
            if b'value="otp_code"' not in b_wait:
                fails.append("GET /settings (otp waiting): no code field")
            if b'http-equiv="refresh"' in b_wait:
                fails.append("GET /settings (otp waiting): auto-refresh would wipe the code being typed")
            b_clear = otp()
            if b'att" data-group="o"' in b_clear or b'http-equiv="refresh"' in b_clear:
                fails.append("GET /settings (otp clear): a marker or a refresh survived")

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

            # --- the need-owners link is a row control, not a fourth sort pill:
            # it sits outside the sort capsule so it cannot spill it (T15)
            if body:
                cap = re.search(rb'<div class="filters".*?</div>', body, re.S)
                if not cap:
                    fails.append("GET /: no sort capsule")
                elif b"need owners" in cap.group(0):
                    fails.append("GET /: the need-owners link is inside the sort capsule")
                if b'class="f fsolo" href="/cards?owner=unassigned"' not in body:
                    fails.append("GET /: the need-owners link is missing from the filter row")

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
                if "<b>Grades ready</b> · stage 7 of 8".encode() not in body:
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

                # --- the corner orbs sit inside one landmark, not loose on the
                # body: the gear ships the nav, the theme orb joins it (T60)
                if (b'<nav id="sitectl" aria-label="Site controls"><a id="gearbtn"'
                        not in body):
                    fails.append("GET /: the gear orb is outside the Site controls nav")

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
            # the toolbar says the same thing in one dot and one word (T104)
            if b'<div class="sync stale">' not in body or b">Stale<" not in body:
                fails.append("GET /: a stale scan does not read as a stale sync dot")
            last_ok(0)
            body = check("GET / (scans current)", "/", (200,), cookie)
            if b"Not connecting to PSA" in body:
                fails.append("GET /: a fresh scan still reads as a broken PSA link")
            if b'<div class="sync live">' not in body or b">Live<" not in body:
                fails.append("GET /: a fresh scan does not read as a live sync dot")
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
            # the worklist link says needs an owner for a single card (T64)
            def arch(num, on):
                return call(url, "/archive", cookie, {"sub": num, "on": on})[0]

            arch("14900001", "1")
            arch("14900003", "1")
            check("GET / (one card untagged)", "/", (200,), cookie,
                  must_have="1 needs an owner")
            check("GET /cards (one card untagged)", "/cards", (200,), cookie,
                  must_have="1 card awaiting an owner")
            arch("14900001", "0")
            arch("14900003", "0")
            if call(url, "/owner", cookie,
                    {"cert_id": "99000002", "owner": "Solo"})[0] != 204:
                fails.append("POST /owner: tagging one card was refused")
            sbody = check("GET /cards?owner=Solo", "/cards?owner=Solo", (200,), cookie,
                          must_have="1 card with")
            # one money format in the person page value block: every figure
            # carries the currency, the fee total prints no cents (T71)
            for want in (b"Est. grading cost<b>$109 CAD</b>", b"<b>$120 CAD</b>",
                         b"<b>$204 CAD</b>"):
                if want not in sbody:
                    fails.append("GET /cards?owner=Solo: the value block is missing "
                                 + want.decode())
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
            if b'$0<span title="no price for Wibble Tier">+</span> CAD' \
                    not in priced_as("Wibble Tier"):
                fails.append("GET /cards?owner=Solo: an unpriced service has no "
                             "+ naming itself in the title")
            priced_as("Regular")
            check("GET /sub/14900002 (one card)", "/sub/14900002", (200,), cookie,
                  must_have="1 card \u00b7")
            for label in ("/", "/sub/14900002", "/cards", "/cards?owner=Solo"):
                if re.search(rb"(?<!\d)1 cards", call(url, label, cookie)[1] or b""):
                    fails.append(f'GET {label}: a single card still reads "1 cards"')
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
            if b'<a class="view" href="/">Home</a>' not in \
                    (call(url, "/cards?owner=Solo", cookie)[1] or b""):
                fails.append("GET /cards?owner=Solo: no Home link beside Back (T103)")
            call(url, "/owner", cookie, {"cert_id": "99000001", "owner": ""})
            call(url, "/owner", cookie, {"cert_id": "99000002", "owner": ""})
            check("GET /search", "/search?q=Charizard", (200,), cookie)
            check("GET /search (empty q)", "/search?q=", (200,), cookie)
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
            if b'<div class="cn">99000001</div>' not in body:
                fails.append("GET /sub/14900001: a graded tile lost its cert number")
            # --- the detail page says the same word on the same rung, and the
            # old lowercase note under the ETA badge is gone (T114)
            if "<b>Grades ready</b> · stage 7 of 8".encode() not in body:
                fails.append("GET /sub/14900001: the stage word is not Grades ready")
            if b'estnote">grades ready' in body:
                fails.append("GET /sub/14900001: the redundant grades ready note is back")
            if b"Completing" in body:
                fails.append("GET /sub/14900001: the header rung still says Completing")
            body = check("GET /sub/14900002", "/sub/14900002", (200,), cookie)
            if b'class="cn pre" title="No cert number until PSA grades it"' not in body:
                fails.append("GET /sub/14900002: the Prelim slot is unexplained again")
            if b"<b>Arrived</b>" not in body or b"Grades ready" in body:
                fails.append("GET /sub/14900002: a sub with no grades yet lost its "
                             "own stage word (T114)")
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
            # "Was due <date>" in the muted pill once PSA is late, and a held
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
            if b"Back " + nextyr.encode() not in row(b"14900001"):
                fails.append("GET /: a return date in another year prints no year")
            held = row(b"14900002")
            if b'class="pill hold"' not in held or b"Back " + soon.encode() not in held:
                fails.append("GET /: a held sub does not show both the hold and its return date")
            # the row wears the hold class the muted-bar rule keys off (T75)
            if not held.startswith(b' hold"'):
                fails.append("GET /: a held row carries no hold class, its bar stays accent")
            if row(b"14900001").startswith(b' hold"'):
                fails.append("GET /: a live row is marked held, its bar is muted for nothing")
            late = row(b"14900003")
            if b'class="pill pending"' not in late or b"Was due " + eta_text(ETA_PAST).encode() not in late:
                fails.append("GET /: a blown ETA does not read as Was due in the muted pill")

            # a window inside one year prints that year once, on the end
            for num, want in (("14900001", (ETA_NEXT_YEAR - datetime.timedelta(days=7))
                               .strftime("%b %d") + " to " + nextyr),
                              ("14900002", soon),
                              ("14900003", "Was due " + eta_text(ETA_PAST))):
                dbody = call(url, "/sub/" + num, cookie)[1] or b""
                badge = re.search(rb'<div class="synced">.*?</div>', dbody, re.S)
                badge = badge.group(0) if badge else b""
                if want.encode() not in badge:
                    fails.append(f"GET /sub/{num}: the ETA badge does not say {want!r}")
                if re.search(rb"\d{4}-\d{2}-\d{2}", badge):
                    fails.append(f"GET /sub/{num}: the ETA badge still prints an ISO date")
            if b'class="holdb">On hold' not in (call(url, "/sub/14900002", cookie)[1] or b""):
                fails.append("GET /sub/14900002: the detail badge dropped the hold")

            # the person page runs the same pill, so a held sub reads the same there
            call(url, "/owner", cookie, {"cert_id": "spec:14900002:1", "owner": "Etaperson"})
            pbody = check("GET /cards?owner=Etaperson", "/cards?owner=Etaperson",
                          (200,), cookie) or b""
            if b'class="pill hold"' not in pbody or b"Back " + soon.encode() not in pbody:
                fails.append("GET /cards?owner=Etaperson: the held sub loses its return date")
            call(url, "/owner", cookie, {"cert_id": "spec:14900002:1", "owner": ""})

            # --- the person page carries the dashboard's three sort pills, so
            # a person with two active subs can reorder their submission groups
            # by soonest return. SORT_JS needs #list plus data-sub/svc/eta on
            # every group card; the Archived pill shares the row in .rowend
            # and no longer owns a .filterrow of its own (T102)
            call(url, "/owner", cookie, {"cert_id": "99000001", "owner": "Twosub"})
            call(url, "/owner", cookie, {"cert_id": "spec:14900002:1", "owner": "Twosub"})
            tbody = check("GET /cards?owner=Twosub", "/cards?owner=Twosub",
                          (200,), cookie) or b""
            row = re.search(rb'<div class="filterrow">.*?(?=<div id="list")', tbody, re.S)
            row = row.group(0) if row else b""
            for want in (b'<div class="filters" role="group" aria-label="Sort submissions">',
                         b'data-sort="sub" aria-pressed="true">Newest<',
                         b'data-sort="svc" aria-pressed="false">Order type<',
                         b'data-sort="eta" aria-pressed="false">Return<'):
                if want not in row:
                    fails.append("GET /cards?owner=Twosub: the sort capsule is missing "
                                 + want.decode())
            if b'<div id="list" style="margin-top:0">' not in tbody:
                fails.append("GET /cards?owner=Twosub: no #list for the sort to reorder")
            grp = re.findall(rb'<div class="card grp[^>]*>', tbody)
            if len(grp) != 2:
                fails.append(f"GET /cards?owner=Twosub: {len(grp)} groups, want 2")
            for want in (b'data-sub="14900002"', b'data-sub="14900001"',
                         b'data-svc="Regular"',
                         b'data-eta="%s"' % ETA_SOON.isoformat().encode(),
                         b'data-eta="%s"' % ETA_NEXT_YEAR.isoformat().encode()):
                if not any(want in g for g in grp):
                    fails.append("GET /cards?owner=Twosub: no group carries "
                                 + want.decode())
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
            check("GET /nope (unknown path)", "/nope", (404,), cookie)
            check("GET /logout", "/logout", (302,), cookie)

            # --- sign out drops the settings cookie too (T6)
            _, _, lhdrs = call(url, "/logout", cookie)
            if not any(h.startswith("psa_settings=;")
                       for h in (lhdrs.get_all("Set-Cookie") or [])):
                fails.append("GET /logout: the settings cookie is left alive")

            # --- rotating the site password revokes outstanding cookies (T6)
            def site_pw(value):
                return call(url, "/settings/account", scookie,
                            {"acct": "demo", "action": "site_pw",
                             "value": value, "value2": value})[0]

            if site_pw(SITE_PW + "-rotated") != 303:
                fails.append("POST /settings/account site_pw: rotation refused")
            check("GET / (cookie after a password rotation)", "/", (200,), cookie,
                  must_have='action="/login"')
            if site_pw(SITE_PW) != 303:
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
            if archive("14900002", "0") != 204:
                fails.append("POST /archive (unarchive): refused")

            # --- ARCH_JS disables the button it was fired from, which drops
            # keyboard focus to body and strands the 6 second Undo chip (T52)
            js = check("GET /app.js (T52)", "/app.js", (200,), cookie)
            if js and b"back(u,foc)" not in js:
                fails.append("GET /: archiving does not move focus to the Undo chip")

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
                if dash.count(b'role="listitem"') != 3:
                    fails.append("GET /: the submission rows are not list items")
                if dash.count(b'<h2 class="num">') != 3:
                    fails.append("GET /: a submission row has no heading")

            # --- an open lightbox locks the page: the drag must not chain to
            # the dashboard 900px behind the scrim, and close must give it back (T57)
            if js:
                if js.count(b"document.body.style.overflow") != 2:
                    fails.append("GET /app.js: the lightbox does not lock the page")
            if css and b"cursor:zoom-out;overscroll-behavior:contain" not in css:
                fails.append("GET /app.css: a drag on the lightbox scrim still chains")

            # --- a landscape phone is wider than 640px and half as tall, so the
            # masthead condenses on height as well as width (T58)
            if js and b"matchMedia('(max-width:640px),(max-height:500px)')" not in js:
                fails.append("GET /app.js: the masthead does not condense on a short viewport")

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
            for i in range(MAX_FAILS):  # a rotating header still fills one budget
                check(f"POST /login (rotating header {i})", "/login", (200,),
                      form={"password": "nope"},
                      headers={"X-Forwarded-For": f"10.0.0.{i}"},
                      must_have="Incorrect password")
            check("POST /login (rotating header, locked)", "/login", (200,),
                  form={"password": "nope"}, headers={"X-Forwarded-For": "10.0.1.1"},
                  must_have="Too many attempts")

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
            check("GET /sub/14900001 (db corrupt)", "/sub/14900001", (500,), cookie)
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
