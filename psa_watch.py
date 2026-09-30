#!/usr/bin/env python3
"""psa-watch: poll PSA orders page, upsert sub statuses into SQLite."""
import base64, json, os, re, sqlite3, subprocess, sys, time, urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from curl_cffi import requests as creq  # Chrome TLS impersonation; PSA is behind Cloudflare bot mgmt

import psa_common

# Locale/region of the PSA account being scraped (US self-hosters: en-US / US)
LOCALE = os.environ.get("PSA_LOCALE", "en-CA")
LOCATION = os.environ.get("PSA_LOCATION", "CA")

def build_url(page_length=100, location=None):
    location = location or LOCATION
    filt = base64.b64encode(json.dumps({"orderFilters": {"start": 0,
        "pageLength": page_length, "sort": "Arrived", "sortOrder": "desc",
        "location": location}}, separators=(",", ":")).encode()).decode().rstrip("=")
    banner = base64.b64encode(json.dumps({"slug": "order-dashboard-banner"},
        separators=(",", ":")).encode()).decode().rstrip("=")
    inp = urllib.parse.quote(json.dumps({"0": 0, "1": banner, "2": filt},
        separators=(",", ":")))
    return ("https://www.psacard.com/api/grading/trpc/"
            "orders.hasUsOrder,cms.getBanner,orders.list?batch=1&input=" + inp)

DB_PATH = os.environ.get("PSA_DB", "/opt/psa-tracker/psa.db")
# App owns owners.db; we only touch it to carry an owner tag from a prelim (spec-keyed)
# card to its real cert_id once a sub gets graded. Keyed the same as the app.
OWN_DB = os.environ.get("PSA_OWN_DB", os.path.join(os.path.dirname(DB_PATH) or ".", "owners.db"))
# Days after a sub ships before we stop waiting on a card's missing grade. Some
# certs never carry one, and without this the sub re-fetches every scan forever.
GRADE_GRACE_DAYS = 7
WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
ACCT = os.environ.get("PSA_ACCT_ID", "account")  # tags this run's log lines
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# orders.list reports progressSummary.lastCompletedStep, but psacard.com displays
# the stage currently IN PROGRESS -- the step AFTER the last completed one (in the
# order detail's orderProgressSteps, the first non-completed step is the one PSA
# highlights). Store that same current stage, else the site reads one stage behind
# PSA. "Submitted" done = package at PSA, prep not finished -> "Arrived".
# orders.list stops advancing lastCompletedStep at "QACheck" and signals the next
# step (detail's GradesReady) via progressSummary.gradesReady instead, so parse()
# promotes QACheck+gradesReady to GradesReady -> "Completing" (psacard.com's
# "completing soon"). "Shipped" still waits for the real ship event.
CURRENT_STAGE = {
    "Submitted": "Arrived",       "Arrived": "Order Prep",
    "OrderPrep": "Research & ID", "ResearchAndID": "Grading",
    "Grading": "Assembly",        "Assembly": "QA Check",
    "QA": "QA Check",             "QACheck": "QA Check",
    "GradesReady": "Completing",  "Shipped": "Shipped",
    "Completed": "Shipped",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS subs (
  sub_number   TEXT PRIMARY KEY,
  order_number TEXT,
  service      TEXT,
  status       TEXT,
  card_count   INTEGER,
  destination  TEXT,
  arrived      TEXT,
  est_start    TEXT,
  est_end      TEXT,
  shipped      TEXT,
  tracking     TEXT,
  carrier      TEXT,
  grades_ready INTEGER DEFAULT 0,
  on_hold      INTEGER DEFAULT 0,
  thumb        TEXT,
  cert_ids     TEXT,
  first_seen   TEXT,
  updated_at   TEXT,
  missing_since TEXT,
  acct         TEXT,
  hold_reason  TEXT
);
CREATE TABLE IF NOT EXISTS status_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sub_number TEXT NOT NULL,
  status     TEXT NOT NULL,
  seen_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cards (
  cert_id     TEXT PRIMARY KEY,
  sub_number  TEXT,
  cert_no     TEXT,
  name        TEXT,
  line_number INTEGER,
  front_thumb TEXT,
  back_thumb  TEXT,
  grade       TEXT,
  declared_value REAL,
  updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_cards_sub ON cards(sub_number);
"""

log = psa_common.log(f"psa-watch:{ACCT}")

def db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    for stmt in ("ALTER TABLE cards ADD COLUMN declared_value REAL",
                 "ALTER TABLE subs ADD COLUMN missing_since TEXT",
                 "ALTER TABLE subs ADD COLUMN acct TEXT",
                 "ALTER TABLE subs ADD COLUMN hold_reason TEXT"):
        try:  # migrations for DBs created before these columns existed
            conn.execute(stmt)
            conn.commit()
        except sqlite3.OperationalError:
            pass
    return conn

def fetch(url):
    cookie = os.environ.get("PSA_COOKIE")
    if not cookie:
        sys.exit("PSA_COOKIE not set")
    # Cookie-only auth (no Bearer - it resolves to an empty context). Cloudflare
    # bot mgmt requires a real browser TLS fingerprint, so use curl_cffi impersonation.
    headers = {
        "Cookie": cookie,
        "Accept": "*/*",
        "locale": LOCALE,
        "Referer": f"https://www.psacard.com/{LOCALE}/myaccount/myorders",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
    }
    # no redirect following: PSA answers a dead accessToken with a 307 to the same
    # URL (the SPA is meant to refresh in JS), which otherwise looks like a
    # transport failure after 30 hops instead of the expired cookie it is (T106)
    r = creq.get(url, headers=headers, impersonate="chrome", timeout=30,
                 allow_redirects=False)
    return r.status_code, r.headers.get("content-type", ""), r.text

# set by parse when PSA's payload is truncated; drained into the change list by
# cycle. A truncated page also hides subs, so cycle skips the missing check then.
SHORT_PAGE = []

def parse(ctype, body):
    """Parse PSA tRPC batch response; orders.list is the last result."""
    SHORT_PAGE.clear()
    try:
        data = json.loads(body)
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    orders = None
    for res in data:
        j = (((res or {}).get("result") or {}).get("data") or {}).get("json")
        if isinstance(j, dict) and "orders" in j:
            orders = j["orders"]
            if not isinstance(orders, list):
                log("WARNING: orders is not a list -- PSA changed the payload shape")
                return []
            total = j.get("totalCount")
            if total and len(orders) < total:
                SHORT_PAGE.append(f"PSA listed {total} orders but sent {len(orders)}"
                                  " - raise page_length")
                log(f"WARNING: {SHORT_PAGE[-1]}")
            break
    if orders is None:
        return []
    out = []
    for o in orders:
        summary = o.get("progressSummary") or {}
        grades_ready = bool(summary.get("gradesReady"))
        step = summary.get("lastCompletedStep") or o.get("status") or ""
        if step in ("QA", "QACheck") and grades_ready:
            step = "GradesReady"
        try:
            count = int(o.get("itemCount") or 0)
        except (TypeError, ValueError):
            count = 0
        imgs = o.get("image") or []
        thumb = next((i.get("thumbnail") for i in imgs if i.get("imageSide") == 1), "")
        out.append({
            "sub_number": str(o.get("submissionNumber") or ""),
            "order_number": str(o.get("orderNumber") or ""),
            "service": o.get("service") or "",
            "status": CURRENT_STAGE.get(step, step),
            "raw_step": step,
            "card_count": count,
            "destination": "Ship back" if not o.get("isPickup") else "Pickup",
            "arrived": o.get("dateArrived") or "",
            "est_start": (o.get("dueOutDate") or "")[:10],
            "est_end": (o.get("dueOutDateUpperRange") or "")[:10],
            "shipped": (o.get("dateShipped") or "").replace("N/A", ""),
            "tracking": o.get("trackingNumber") or "",
            "carrier": o.get("carrier") if o.get("carrier") != "None" else "",
            "grades_ready": grades_ready,
            # PSA signals some holds only via status (e.g. "ReceivedHold"
            # with onHold still false), so treat either as a hold
            "on_hold": bool(o.get("onHold")) or "hold" in (o.get("status") or "").lower(),
            # e.g. "HOLD.DCC" (a financial hold); psa_common.HOLD_LABELS names it
            "hold_reason": o.get("holdReasonCode") or "",
            "thumb": thumb or "",
            "cert_ids": json.dumps(o.get("certIds") or []),
        })
    return [s for s in out if s["sub_number"]]

def detail_url(sub_number):
    blob = base64.b64encode(json.dumps({"submissionNumber": str(sub_number)},
        separators=(",", ":")).encode()).decode().rstrip("=")
    return ("https://www.psacard.com/api/grading/trpc/orders.get?batch=1&input="
            + urllib.parse.quote(json.dumps({"0": blob}, separators=(",", ":"))))

def grade_str(pc):
    """psaCerts entry -> display grade, e.g. '10', '9 OC', or '' if not yet graded.
    validFlag/gradeValue guard against half-populated in-progress certs."""
    gv = pc.get("gradeValue")
    if not gv:
        return ""
    q = (pc.get("qualifier") or "").strip()
    return f"{gv} {q}".strip() if q and q.lower() not in ("none", "0") else str(gv)

def parse_detail(sub_number, body):
    """orders.get -> per-card {cert_id, cert_no, name, images, grade}."""
    try:
        data = json.loads(body)
    except ValueError:
        return []
    if not isinstance(data, list) or not data:
        return []
    d = (((data[0] or {}).get("result") or {}).get("data") or {}).get("json")
    if not isinstance(d, dict):
        return []
    images = d.get("images") or {}
    specs = {str(s.get("certID")): s for s in (d.get("specReviewResults") or [])}
    psa = {}
    for c in (d.get("psaCerts") or []):
        cid = str(c.get("certID") or c.get("certId") or "")
        if cid:
            psa[cid] = c
    cards = []
    for cid, imgs in images.items():
        front = next((i.get("thumbnail") for i in imgs if i.get("imageSide") == 1), "")
        back = next((i.get("thumbnail") for i in imgs if i.get("imageSide") == 2), "")
        sp = specs.get(cid, {})
        pc = psa.get(cid, {})
        cards.append({
            "sub_number": sub_number, "cert_id": cid,
            # once graded, specReviewResults empties out -> fall back to psaCerts
            "cert_no": str(sp.get("certNo") or pc.get("certNumber") or ""),
            "name": sp.get("specDescription") or pc.get("specDescription") or "",
            "line_number": sp.get("lineNumber") or 0,
            "front_thumb": front or "", "back_thumb": back or "",
            "grade": grade_str(pc),
        })
    # certs known but no image yet (early stages): still record from spec list
    for cid, sp in specs.items():
        if cid not in images:
            cards.append({
                "sub_number": sub_number, "cert_id": cid,
                "cert_no": str(sp.get("certNo") or ""),
                "name": sp.get("specDescription") or "", "line_number": sp.get("lineNumber") or 0,
                "front_thumb": "", "back_thumb": "", "grade": "",
            })
    cards.sort(key=lambda c: c["line_number"] or 0)
    return cards

# --- pre-grade path: submissions that don't have cert_ids yet -----------------
# Source: the .../submissions/<sub>/complete page. Two tRPC calls:
#   1. submissions.completed -> line items (specId + specDescription = prelim name)
#   2. imaging.imagesBySpecIds -> images keyed by specId on the /spec/<id>/ CDN path
# We store these as cards keyed by a synthetic cert_id "spec:<specId>" so they show
# and can be owner-tagged before PSA assigns real cert numbers. Once the sub grades,
# refresh_cards replaces them with real cert cards (owner tags carried over by line).
SPEC_DEPT_ID = 10  # PSA department id for TCG/trading cards

def completed_url(sub_number):
    blob = base64.b64encode(json.dumps({"submissionNumber": int(sub_number)},
        separators=(",", ":")).encode()).decode().rstrip("=")
    return ("https://www.psacard.com/api/grading/trpc/submissions.completed?batch=1&input="
            + urllib.parse.quote(json.dumps({"0": blob}, separators=(",", ":"))))

def images_url(spec_ids):
    blob = base64.b64encode(json.dumps({"specIds": [int(s) for s in spec_ids],
        "deptId": SPEC_DEPT_ID}, separators=(",", ":")).encode()).decode().rstrip("=")
    return ("https://www.psacard.com/api/grading/trpc/imaging.imagesBySpecIds?batch=1&input="
            + urllib.parse.quote(json.dumps({"0": blob}, separators=(",", ":"))))

def _trpc_json(body, key):
    """Pull result[0].result.data.json[key] from a tRPC batch response."""
    try:
        data = json.loads(body)
    except ValueError:
        return None
    if not isinstance(data, list) or not data:
        return None
    j = (((data[0] or {}).get("result") or {}).get("data") or {}).get("json")
    if not isinstance(j, dict):
        return None
    return j.get(key) if key else j

def parse_completed_lines(body):
    """submissions.completed -> [{line_number, spec_id, name}]. Ignores all PII fields."""
    j = _trpc_json(body, None) or {}
    summary = j.get("submissionCompletedLineSummary") or {}
    out = []
    for ln in (summary.get("submissionLines") or []):
        spec = ln.get("specId")
        if spec is None:
            log(f"completed line {ln.get('lineNumber')} skipped: no specId")
            continue
        qty = int(ln.get("quantity") or 1)
        # declaredValue is the LINE total (per-card value × quantity) - store per card
        line_dv = ln.get("declaredValue")
        unit_dv = (float(line_dv) / max(1, qty)) if line_dv is not None else None
        out.append({"line_number": ln.get("lineNumber") or 0, "spec_id": int(spec),
                    "name": ln.get("specDescription") or "",
                    "quantity": qty, "dv": unit_dv})
    return out

def parse_spec_images(body):
    """imaging.imagesBySpecIds -> {spec_id(str): {"front": url, "back": url}}."""
    docs = _trpc_json(body, "documents") or []
    imgs = {}
    for d in docs:
        rid = str(d.get("refId") or "")
        url = (d.get("url") or {}).get("thumbnail") or ""
        if not rid or not url:
            continue
        side = "back" if (d.get("attribute") or {}).get("imageSide") == 2 else "front"
        imgs.setdefault(rid, {}).setdefault(side, url)
    return imgs

def fetch_spec_lines(sub_number):
    """Submission 'complete' page -> [{line_number, spec_id, name, front, back}], or [].
    Shared by the prelim-card path and the image-backfill path."""
    _, _, body = fetch(completed_url(sub_number))
    lines = parse_completed_lines(body)
    if not lines:
        return []
    _, _, ibody = fetch(images_url([l["spec_id"] for l in lines]))
    imgs = parse_spec_images(ibody)
    out = []
    for l in lines:
        pi = imgs.get(str(l["spec_id"]), {})
        out.append({"line_number": l["line_number"], "spec_id": l["spec_id"],
                    "name": l["name"], "quantity": l["quantity"], "dv": l.get("dv"),
                    "front": pi.get("front", ""), "back": pi.get("back", "")})
    return out

def prelim_cards(sub_number, spec_lines):
    """Turn spec lines into standalone prelim cards. Keys are namespaced by submission -
    'spec:<sub>:<specId>' - because the SAME card (specId) can appear in multiple subs, and
    cert_id is a global PK; an un-namespaced 'spec:<specId>' would collide across subs and the
    last-written sub would steal the row. A line with quantity>1 (duplicates) expands into that
    many separate cards (copy 0 = base key, extras get a trailing ':<n>'), each an own tile
    sharing the single pre-grade image PSA exposes per spec."""
    cards = []
    seen = {}
    for l in spec_lines:
        spec = l["spec_id"]
        base = f"spec:{sub_number}:{spec}"
        for _ in range(max(1, l["quantity"])):
            idx = seen.get(spec, 0)
            seen[spec] = idx + 1
            cid = base if idx == 0 else f"{base}:{idx}"
            cards.append({
                "sub_number": sub_number, "cert_id": cid,
                "cert_no": "", "name": l["name"], "line_number": l["line_number"],
                "front_thumb": l["front"], "back_thumb": l["back"], "grade": "",
                "declared_value": l.get("dv"),
            })
    cards.sort(key=lambda c: c["line_number"] or 0)
    return cards

def backfill_images(cards, spec_lines):
    """Fill missing front/back images (and empty names) on real cert cards from the
    spec images, matched by line number. Returns True if anything was filled."""
    by_line = {l["line_number"]: l for l in spec_lines}
    filled = False
    for c in cards:
        if c["front_thumb"]:
            continue
        l = by_line.get(c["line_number"])
        if not l or not (l["front"] or l["back"]):
            continue
        c["front_thumb"] = l["front"] or c["front_thumb"]
        c["back_thumb"] = c["back_thumb"] or l["back"]
        if not c["name"]:
            c["name"] = l["name"]
        filled = True
    return filled

def assign_dv(cards, spec_lines):
    """Attach per-card declared values from the submission form lines to cert cards.

    Cert cards can't be line-matched naively: quantity>1 form lines expand into
    that many sequential cert lines, and old graded subs have line_number=0 on
    every card (no spec review data). Strategy, safest first:
      1. uniform - every card on the form is declared at the same value: assign it
         to all cards (covers old line-0 subs too).
      2. positional - expanded form positions == card count: map in submission
         order (cards sorted by line_number, cert_id).
      3. identity - fall back to direct line_number match.
    """
    units = []
    for l in sorted(spec_lines, key=lambda l: l["line_number"] or 0):
        units.extend([l.get("dv")] * max(1, l["quantity"]))
    known = {u for u in units if u is not None}
    if not known:
        return
    if len(known) == 1 and None not in units:
        u = units[0]
        for c in cards:
            if c.get("declared_value") is None:
                c["declared_value"] = u
    elif len(units) == len(cards):
        ordered = sorted(cards, key=lambda c: (c["line_number"] or 0, str(c["cert_id"])))
        for c, u in zip(ordered, units):
            if c.get("declared_value") is None and u is not None:
                c["declared_value"] = u
    else:
        by_line = {l["line_number"]: l.get("dv") for l in spec_lines}
        for c in cards:
            if c.get("declared_value") is None:
                c["declared_value"] = by_line.get(c["line_number"])

def _names_match(a, b):
    """PSA's prelim spec description and final cert label differ in formatting but
    share the card's identifying tokens. Require some real overlap before trusting
    a line-number match."""
    ta = {t for t in re.sub(r"[^a-z0-9 ]", " ", (a or "").lower()).split() if len(t) > 2}
    tb = {t for t in re.sub(r"[^a-z0-9 ]", " ", (b or "").lower()).split() if len(t) > 2}
    if not ta or not tb:
        return True  # no name to compare - fall back to line-number trust
    if len(ta & tb) / min(len(ta), len(tb)) < 0.5:
        return False
    # set words alone clear 50% ("2025 one piece championship ... event pack"), so the
    # tokens with digits in them (year, card number) must agree too (T213)
    na = {t for t in ta if any(ch.isdigit() for ch in t)}
    nb = {t for t in tb if any(ch.isdigit() for ch in t)}
    return not na or not nb or na <= nb or nb <= na

def _copy_idx(cid):
    """spec:<sub>:<specId>[:<n>] -> n (0 for the base key)."""
    parts = str(cid).split(":")
    return int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0

def pair_prelims(sub_number, old_rows, new_cards):
    """[(old_cid, old_name, cert_card)] for prelim -> cert carryover.

    Prelim cards carry the FORM line number (a quantity-3 line is three cards on
    one line), cert cards are numbered one per card, so the numbers drift apart
    after the first qty>1 line (T213). A form line PSA had no specId for yields no
    prelim at all, so the counts can differ too. Both lists are the same cards in
    submission order. When the counts agree once each missing form line number
    counts as one card, pair by that exact position (identical cards stay on the
    right slab). Otherwise align by name (longest common subsequence under
    _names_match), which keeps order and skips the extra card on either side.
    Either way a pair whose names disagree is dropped."""
    olds = sorted(((cid, ln or 0, nm) for cid, ln, nm in old_rows if str(cid).startswith("spec:")),
                  key=lambda o: (o[1], _copy_idx(o[0])))
    targets = sorted((c for c in new_cards if not str(c["cert_id"]).startswith("spec:")),
                     key=lambda c: (c["line_number"] or 0, str(c["cert_id"])))
    n, m = len(olds), len(targets)
    if not n or not m:
        return []
    present = {o[1] for o in olds}
    gaps = [ln for ln in range(1, max(present) + 1) if ln not in present]
    if n + len(gaps) == m:
        pairs = []
        for i, o in enumerate(olds):
            c = targets[i + sum(1 for g in gaps if g < o[1])]
            if _names_match(o[2], c.get("name") or ""):
                pairs.append((o[0], o[2], c))
        if len(pairs) < n:
            log(f"sub {sub_number}: {n - len(pairs)} of {n} prelim(s) renamed by PSA, owner left blank")
        return pairs
    eq = [[_names_match(o[2], c.get("name") or "") for c in targets] for o in olds]
    L = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            L[i][j] = L[i + 1][j + 1] + 1 if eq[i][j] else max(L[i + 1][j], L[i][j + 1])
    pairs, i, j = [], 0, 0
    while i < n and j < m:
        if eq[i][j] and L[i][j] == L[i + 1][j + 1] + 1:
            pairs.append((olds[i][0], olds[i][2], targets[j]))
            i += 1; j += 1
        elif L[i + 1][j] >= L[i][j + 1]:
            i += 1
        else:
            j += 1
    if len(pairs) < n:
        log(f"sub {sub_number}: {n - len(pairs)} of {n} prelim(s) found no cert with a matching name")
    return pairs

def carryover_owners(sub_number, old_rows, new_cards):
    """When prelim (spec:) cards are replaced by real cert cards, move owner tags
    across on the name-aligned pairs from pair_prelims, never over a tag already
    on the cert. Anything doubtful is left blank (and logged): a blank
    owner gets noticed and fixed, a wrong owner doesn't. old_rows: (cert_id,
    line_number, name). Returns the number of tags moved."""
    pairs = pair_prelims(sub_number, old_rows, new_cards)
    if not pairs:
        return 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    oc = sqlite3.connect(OWN_DB)
    oc.execute("CREATE TABLE IF NOT EXISTS owners (cert_id TEXT PRIMARY KEY, owner TEXT, updated_at TEXT)")
    moved = 0
    for old_cid, old_name, c in pairs:
        row = oc.execute("SELECT owner FROM owners WHERE cert_id=?", (old_cid,)).fetchone()
        if not (row and row[0]):
            continue
        have = oc.execute("SELECT owner FROM owners WHERE cert_id=?", (c["cert_id"],)).fetchone()
        if have and have[0]:
            continue  # someone tagged the cert by hand: theirs wins
        oc.execute("INSERT OR REPLACE INTO owners(cert_id, owner, updated_at) VALUES (?,?,?)",
                   (c["cert_id"], row[0], now))
        oc.execute("DELETE FROM owners WHERE cert_id=?", (old_cid,))
        moved += 1
    oc.commit(); oc.close()
    if moved:
        log(f"sub {sub_number}: carried over {moved} owner tag(s) prelim -> cert")
    return moved

def upsert_cards(conn, sub_number, cards):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    old_rows = conn.execute("SELECT cert_id, line_number, name FROM cards WHERE sub_number=?",
                            (sub_number,)).fetchall()
    carryover_owners(sub_number, old_rows, cards)
    conn.execute("DELETE FROM cards WHERE sub_number=?", (sub_number,))
    for c in cards:
        conn.execute("""INSERT OR REPLACE INTO cards
            (cert_id, sub_number, cert_no, name, line_number, front_thumb, back_thumb, grade, declared_value, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (c["cert_id"], c["sub_number"], c["cert_no"], c["name"], c["line_number"],
             c["front_thumb"], c["back_thumb"], c["grade"], c.get("declared_value"), now))
    conn.commit()

def refresh_cards(conn, subs, prev=None, full=False):
    prev = prev or {}
    total = 0
    skipped = 0
    short = 0
    # seen_at is always a UTC isoformat, so a string compare is the date math
    grade_cutoff = (datetime.now(timezone.utc)
                    - timedelta(days=GRADE_GRACE_DAYS)).isoformat(timespec="seconds")
    for s in subs:
        sub = s["sub_number"]
        has_certs = bool(json.loads(s["cert_ids"] or "[]"))
        # A sub that was ALREADY Shipped before this scan is frozen - PSA won't
        # change its cards/images. Skip its detail fetch unless something is
        # missing (image or declared value) or --full was passed. Cuts PSA API
        # calls roughly in half once every sub is fully populated.
        if not full and s["status"] == "Shipped" and prev.get(sub) == "Shipped":
            row = conn.execute("""SELECT count(*), sum(front_thumb!=''),
                sum(declared_value IS NULL), sum(grade='') FROM cards WHERE sub_number=?""",
                (sub,)).fetchone()
            # only skip once cards are fully imaged, valued, AND graded (if grades ready)
            need_grades = s["grades_ready"] and (row[3] or 0)
            if need_grades:
                # a card still ungraded a week after the sub shipped never will be:
                # let the skip fire instead of re-fetching a frozen sub forever
                shipped_at = conn.execute("""SELECT max(seen_at) FROM status_history
                    WHERE sub_number=? AND status='Shipped'""", (sub,)).fetchone()[0]
                if shipped_at and shipped_at < grade_cutoff:
                    need_grades = 0
            if row[0] and row[0] == (row[1] or 0) and not (row[2] or 0) and not need_grades:
                skipped += 1
                continue
        try:
            cards = []
            if has_certs:
                _, _, body = fetch(detail_url(sub))
                cards = parse_detail(sub, body)
                # orders.get knows nothing about declared values - carry the ones we
                # already learned forward by line number so we don't re-hit the spec
                # endpoint every scan for active subs
                if cards and any(c.get("declared_value") is None for c in cards):
                    prior = dict(conn.execute("""SELECT line_number, declared_value FROM cards
                        WHERE sub_number=? AND declared_value IS NOT NULL""", (sub,)))
                    for c in cards:
                        if c.get("declared_value") is None:
                            c["declared_value"] = prior.get(c["line_number"])
            # Double-check images regardless of stage: a sub can have cert_ids but
            # orders.get still returns no images (e.g. Order Prep). Whenever a card
            # is missing an image or a declared value - or the sub has no cards at
            # all yet - fall back to the submission 'complete' page (spec images,
            # prelim names, per-card declared values).
            if not cards or any(not c["front_thumb"] or c.get("declared_value") is None
                                for c in cards):
                spec_lines = fetch_spec_lines(sub)
                if spec_lines:
                    if cards:
                        backfill_images(cards, spec_lines)
                        assign_dv(cards, spec_lines)
                    else:
                        cards = prelim_cards(sub, spec_lines)
            if cards:
                upsert_cards(conn, sub, cards)
                total += len(cards)
                want = s.get("card_count") or 0
                if want and len(cards) != want:
                    short += 1
                    log(f"sub {sub}: stored {len(cards)} cards, PSA counts {want}")
                # give the dashboard a cover for subs whose orders.list had no image
                if not s.get("thumb"):
                    front = next((c["front_thumb"] for c in cards if c["front_thumb"]), "")
                    if front:
                        conn.execute("UPDATE subs SET thumb=? WHERE sub_number=? AND (thumb IS NULL OR thumb='')",
                                     (front, sub))
                        conn.commit()
        except Exception as e:
            log(f"detail {sub} error: {e}")
        time.sleep(0.3)
    log(f"cards refreshed: {total}" + (f" ({skipped} stable shipped subs skipped)" if skipped else "")
        + (f", {short} sub(s) off PSA's card count" if short else ""))

def discord_mentions(conn, sub_numbers):
    """Distinct Discord IDs to @-mention: owners whose cards sit in the changed
    subs and who linked an ID on their person page (owners.db discord_links)."""
    subs = [s for s in dict.fromkeys(sub_numbers)]
    if not subs:
        return []
    try:
        oc = sqlite3.connect(OWN_DB)
        links = {o.lower(): d for o, d in oc.execute(
            "SELECT owner, discord_id FROM discord_links WHERE discord_id != ''")}
        owners = {str(c): o for c, o in oc.execute(
            "SELECT cert_id, owner FROM owners WHERE owner != ''")} if links else {}
        oc.close()
    except sqlite3.Error:
        return []
    if not links:
        return []
    ids = []
    q = ",".join("?" * len(subs))
    for (cid,) in conn.execute(f"SELECT cert_id FROM cards WHERE sub_number IN ({q})", subs):
        did = links.get(owners.get(str(cid), "").lower())
        if did and did not in ids:
            ids.append(did)
    return ids

def archived_subs():
    """Sub numbers archived on the site (app.py owns owners.db). An archived sub is
    hidden from the dashboard and from hub's hub.json, so Discord stays quiet too."""
    try:
        oc = sqlite3.connect(OWN_DB)
        subs = {r[0] for r in oc.execute("SELECT sub_number FROM archived")}
        oc.close()
        return subs
    except sqlite3.Error:
        return set()

def upsert(conn, subs, quiet=()):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    changes, touched = [], []
    def note(sub, text):
        if sub in quiet:
            return
        changes.append(text)
        touched.append(sub)
    for s in subs:
        if not s["status"]:
            # a renamed PSA field parses as a blank stage; writing it would wipe
            # the sub's status, service, card count and tracking
            log(f"sub #{s['sub_number']}: parsed with no status -- row left untouched")
            continue
        row = conn.execute("SELECT status, grades_ready, on_hold, hold_reason FROM subs WHERE sub_number=?",
                           (s["sub_number"],)).fetchone()
        vals = (s["order_number"], s["service"], s["status"], s["card_count"],
                s["destination"], s["arrived"], s["est_start"], s["est_end"],
                s["shipped"], s["tracking"], s["carrier"], int(s["grades_ready"]),
                int(s["on_hold"]), s["thumb"], s["cert_ids"], s["hold_reason"])
        if row is None:
            conn.execute("""INSERT INTO subs (sub_number, order_number, service, status,
                card_count, destination, arrived, est_start, est_end, shipped, tracking,
                carrier, grades_ready, on_hold, thumb, cert_ids, hold_reason, first_seen,
                updated_at, acct)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (s["sub_number"],) + vals + (now, now, ACCT))
            conn.execute("INSERT INTO status_history(sub_number,status,seen_at) VALUES (?,?,?)",
                         (s["sub_number"], s["status"], now))
            note(s["sub_number"],
                 f"new sub #{s['sub_number']} ({s['service']}, {s['card_count']} cards) -- {s['status']}")
        else:
            fresh_grades = not row[1] and s["grades_ready"]
            if row[0] != s["status"] and s["status"]:
                conn.execute("INSERT INTO status_history(sub_number,status,seen_at) VALUES (?,?,?)",
                             (s["sub_number"], s["status"], now))
                # grades flipping with the stage is one event, as hub reads it
                note(s["sub_number"], f"sub #{s['sub_number']}: {row[0]} -> {s['status']}"
                     + (" - grades ready" if fresh_grades else ""))
            elif fresh_grades:
                note(s["sub_number"], f"sub #{s['sub_number']}: grades are ready")
            # a hold usually flips with the stage unchanged (14956985 went on
            # hold at QA Check, 2026-09) - status diff alone never saw it
            # a new reason on a standing hold is news too
            code = s["hold_reason"]
            why = (f" ({psa_common.HOLD_LABELS.get(code, code)})") if code else ""
            if bool(row[2]) != s["on_hold"]:
                note(s["sub_number"],
                     f"sub #{s['sub_number']}: {'ON HOLD' + why if s['on_hold'] else 'hold cleared'}")
            elif s["on_hold"] and (row[3] or "") != s["hold_reason"]:
                note(s["sub_number"], f"sub #{s['sub_number']}: hold reason now{why or ' unknown'}")
            conn.execute("""UPDATE subs SET order_number=?, service=?, status=?, card_count=?,
                destination=?, arrived=?, est_start=?, est_end=?, shipped=?, tracking=?,
                carrier=?, grades_ready=?, on_hold=?, thumb=?, cert_ids=?, hold_reason=?, updated_at=?,
                missing_since=NULL, acct=?
                WHERE sub_number=?""", vals + (now, ACCT, s["sub_number"]))
    conn.commit()
    return changes, touched

def cycle(conn):
    # exit codes: 0 ok, 3 cookie-dead (a JSON answer with no subs in it), 4 not
    # a cookie problem (transport error, non-JSON body, changed payload shape).
    # run_scan only spends a browser login on 3.
    # Every non-zero exit also writes the human cause to the account's
    # .last_error, which is what run_scan's alert and hub.json say out loud (T105).
    # one retry on the orders.list fetch - a transient blip otherwise loses a
    # whole scan window (we only run twice a day now)
    status = 0
    ctype = body = ""
    err = None
    for attempt in (1, 2):
        try:
            status, ctype, body = fetch(build_url())
            err = None
            break
        except Exception as e:
            err = e
            log(f"orders.list fetch attempt {attempt} failed: {e}")
            if attempt == 1:
                time.sleep(5)
    if err is not None:
        log("orders.list unreachable -- transport failure, not a dead cookie")
        psa_common.set_error(f"PSA unreachable: {err}")
        return 4
    if 300 <= status < 400:
        log(f"orders.list redirected (HTTP {status}) -- cookie expired")
        psa_common.set_error("cookie expired: PSA redirected orders.list")
        return 3
    if body.lstrip()[:1] not in ("[", "{"):
        low = body.lower()
        if "login" in low[:4000] and "password" in low:
            log("orders.list answered a login page -- cookie expired/invalid")
            psa_common.set_error("cookie expired: PSA answered the sign-in page")
            return 3
        log(f"orders.list answered {len(body)} non-JSON bytes (content-type {ctype!r}) "
            "-- blocked or erroring upstream, not a dead cookie")
        psa_common.set_error(f"PSA unreachable: {len(body)} non-JSON bytes, "
                             f"content-type {ctype or 'none'}")
        return 4
    subs = parse(ctype, body)
    if not subs:
        log("parsed 0 subs -- parser needs adjusting or cookie expired")
        psa_common.set_error("cookie expired: PSA listed no submissions at all")
        return 3
    blank = [s for s in subs if not s["status"]]
    if len(blank) * 2 > len(subs):
        log(f"{len(blank)} of {len(subs)} subs parsed with no status -- "
            "PSA payload shape changed; writing nothing")
        psa_common.set_error("PSA payload changed shape")
        return 4
    # statuses BEFORE this scan's upsert - used to skip detail-fetching subs that
    # were already Shipped last time (their cards can no longer change)
    prev = {r[0]: r[1] for r in conn.execute("SELECT sub_number, status FROM subs")}
    quiet = archived_subs()
    changes, touched = upsert(conn, subs, quiet)
    if SHORT_PAGE:
        changes += SHORT_PAGE
    else:
        # a sub PSA stopped listing freezes in place - say so once, then stamp it
        # so later scans stay quiet (a sub that comes back clears the stamp)
        seen = {s["sub_number"] for s in subs}
        # several PSA accounts can feed one db (PSA_MERGE_INTO): only this
        # account's own subs can be "gone" from this account's list
        gone = [r[0] for r in conn.execute(
            "SELECT sub_number FROM subs WHERE missing_since IS NULL AND acct=?", (ACCT,)).fetchall()
            if r[0] not in seen and r[0] not in quiet]
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for sub in gone:
            conn.execute("UPDATE subs SET missing_since=? WHERE sub_number=?", (stamp, sub))
            changes.append(f"sub #{sub}: no longer listed by PSA")
            touched.append(sub)
        if gone:
            conn.commit()
    log(f"parsed {len(subs)} subs, {len(changes)} changes")
    for c in changes:
        log(f"  {c}")
    if changes and not prev:
        # first scan for this account (or a restored db): the rows are history,
        # not news - seed them silently
        log(f"first scan -- {len(changes)} rows seeded, nothing posted")
        changes = []
    refresh_cards(conn, subs, prev, full="--full" in sys.argv)
    # post after refresh_cards: a first-seen sub only has its cards rows by now,
    # so discord_mentions can resolve its owner on the same run
    if changes:
        # no site link: the attached dashboard cards say it all (the owner, 2026-09-12)
        msg = "**PSA update**\n" + "\n".join(changes)
        ids = discord_mentions(conn, touched)
        if ids:
            msg += "\n" + " ".join(f"<@{i}>" for i in ids)
        psa_common.notify(WEBHOOK, msg, log, files=card_shots(touched))
    return 0

def card_shots(subs):
    """The dashboard card of each mentioned sub as a PNG, rendered by
    psa_shot.py against the site on this box (the owner, 2026-09-12: the post
    should look like the site, not a stack of embeds). A failed render is
    logged and skipped; the text still goes out."""
    shots, here = [], os.path.dirname(os.path.abspath(__file__))
    for n in list(dict.fromkeys(subs))[:10]:
        out = f"/tmp/psa-shot-{n}.png"
        try:
            r = subprocess.run([sys.executable, os.path.join(here, "psa_shot.py"), n, out],
                               capture_output=True, text=True, timeout=90)
            if r.returncode == 0 and os.path.exists(out):
                shots.append((f"sub-{n}.png", open(out, "rb").read()))
            else:
                log(f"card shot for #{n} failed: {(r.stderr or r.stdout).strip().splitlines()[-1:] or r.returncode}")
        except Exception as e:
            log(f"card shot for #{n} failed: {e}")
        finally:
            try: os.remove(out)
            except OSError: pass
    return shots

def main():
    sys.exit(cycle(db()))

if __name__ == "__main__":
    main()
