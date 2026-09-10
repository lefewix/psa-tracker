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
import hashlib, json, os, re, shutil, signal, socket, sqlite3, subprocess
import sys, tempfile, time, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_PW = "smoke-site-pw"
SET_PW = "smoke-settings-pw"
SET_HASH = hashlib.sha256(SET_PW.encode()).hexdigest()
HUB_KEY = "smoke-hub-key"
MAX_FAILS = 8  # app.py's login budget, per IP and site-wide
NOW = "2026-01-01T00:00:00+00:00"


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
        f.write(f"LABEL='Smoke Store'\nSITE_PASSWORD='{SITE_PW}'\n"
                "PSA_LOGIN_EMAIL='smoke@example.com'\nPSA_LOGIN_PW='x'\n"
                "PSA_COOKIE='fake'\n")
    open(os.path.join(base, "global.env"), "w").close()
    c = sqlite3.connect(os.path.join(acct, "psa.db"))
    c.executescript(schema("psa_watch.py"))
    c.executescript(schema("psa_values.py"))
    subs = [("14900001", "Completing", 2, "2026-09-10", "", 1, 0),
            ("14900002", "Arrived", 1, "", "", 0, 1),
            # a step the stage map does not know (T19)
            ("14900003", "ReceivedHold", 1, "", "", 0, 0)]
    for num, status, cnt, shipped, tracking, ready, hold in subs:
        c.execute("INSERT INTO subs (sub_number, order_number, service, status, "
                  "card_count, destination, arrived, est_start, est_end, shipped, "
                  "tracking, carrier, grades_ready, on_hold, thumb, cert_ids, "
                  "first_seen, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (num, "O-" + num, "Regular", status, cnt, "Ship back", "2026-08-01",
                   "2026-09-05", "2026-09-12", shipped, tracking, "UPS", ready, hold,
                   "", json.dumps([]), NOW, NOW))
        c.execute("INSERT INTO status_history (sub_number, status, seen_at) VALUES (?,?,?)",
                  (num, status, NOW))
    # front_thumb is PSA's own thumbnail asset: what the scanner stores and what
    # the filmstrip must serve unrewritten (T20)
    thumb = "https://d1htnxwo4o0jhw.cloudfront.net/thumbnail/%s.jpg"
    cards = [("99000001", "14900001", "99000001", "Charizard 4/102 Base Set Holo", 1, "10"),
             ("99000002", "14900001", "99000002", "Pikachu VMAX 044/185", 2, "9"),
             ("spec:14900002:1", "14900002", "", "Umbreon VMAX 215/203", 1, "")]
    for cid, num, cert_no, name, line, grade in cards:
        c.execute("INSERT INTO cards (cert_id, sub_number, cert_no, name, line_number, "
                  "front_thumb, back_thumb, grade, declared_value, updated_at) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (cid, num, cert_no, name, line, thumb % cid.replace(":", "-"),
                   "", grade, 120.0, NOW))
    c.execute("INSERT INTO card_values (cert_no, estimate, last_sale, last_sale_date, "
              "n_sales, sales_json, fetched_at, error) VALUES (?,?,?,?,?,?,?,?)",
              ("99000001", 310.0, 290.0, "2026-08-15", 3,
               json.dumps([{"price": 290.0, "date": "2026-08-15"}]), NOW, ""))
    c.execute("INSERT INTO fx_rates (pair, rate, fetched_at) VALUES ('USDCAD',1.36,?)", (NOW,))
    c.commit()
    c.close()


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
        check("GET /app.js", "/app.js", (200,))

        # --- the pencil hides on the INPUT's focus, not the row's: :focus-within
        # also matched the pencil's own focus, so a tap removed the button
        # before its click and a filled tag could not be edited on a phone (T16)
        if css:
            if b":focus-within .ownedit" in css:
                fails.append("GET /app.css: the pencil still hides on the row's focus")
            if b".own:focus + .ownedit{display:none}" not in css:
                fails.append("GET /app.css: the pencil no longer hides while the tag is edited")
        check("GET /logo", "/logo", (200,))
        check("GET /favicon.png", "/favicon.png", (200,))
        check("GET /apple-touch-icon.png", "/apple-touch-icon.png", (200,))
        check("GET /api/hub.json (no key)", "/api/hub.json", (404,))
        check("GET /setup (setup closed)", "/setup", (302,))
        setup_instance_checks(fails)

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

                # --- an unmapped PSA step reads as unknown, not as stage 1 of 8,
                # and draws no bar: one bar per sub the stage map knows (T19)
                if b"Status unknown" not in body:
                    fails.append("GET /: the unmapped status does not read as unknown")
                if body.count(b'<div class="bar">') != 2:
                    fails.append("GET /: the unmapped status still draws a stage bar")

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
            check("GET /cards", "/cards", (200,), cookie)
            check("GET /cards?owner=", "/cards?owner=Nobody", (200,), cookie)
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
            check("GET /sub/14900001", "/sub/14900001", (200,), cookie,
                  must_have="Charizard")
            check("GET /sub/14900002", "/sub/14900002", (200,), cookie)
            body = check("GET /sub/14900003 (unmapped status)", "/sub/14900003",
                         (200,), cookie, must_have="Status unknown")
            if b'<div class="bar">' in body:
                fails.append("GET /sub/14900003: the unmapped status still draws a stage bar")
            if b"stage 1 of" in body:
                fails.append("GET /sub/14900003: the unmapped status reads as stage 1")
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
            check("GET /sub/14900001 (after the page's own POST)", "/sub/14900001",
                  (200,), cookie, must_have="Mallory")

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
