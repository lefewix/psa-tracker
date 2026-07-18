#!/usr/bin/env python3
"""psa-watch: poll PSA orders page, upsert sub statuses into SQLite."""
import json, os, re, sqlite3, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from curl_cffi import requests as creq  # Chrome TLS impersonation; PSA is behind Cloudflare bot mgmt

ORDERS_URL = os.environ.get("PSA_ORDERS_URL", "")
# Locale/region of the PSA account being scraped (US self-hosters: en-US / US)
LOCALE = os.environ.get("PSA_LOCALE", "en-CA")
LOCATION = os.environ.get("PSA_LOCATION", "CA")

def build_url(page_length=100, location=None):
    location = location or LOCATION
    if ORDERS_URL:
        return ORDERS_URL
    import base64, urllib.parse
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
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "21600"))
WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

STEP_ORDER = ["Submitted", "OrderPrep", "ResearchAndID", "Grading", "Assembly", "QA", "Shipped"]
STEP_LABEL = {"Submitted": "Arrived", "OrderPrep": "Order Prep", "ResearchAndID": "Research & ID",
              "Grading": "Grading", "Assembly": "Assembly", "QA": "QA Check", "Shipped": "Shipped"}

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
  updated_at   TEXT
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

def log(msg):
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)

def db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    try:  # migration for DBs created before declared_value existed
        conn.execute("ALTER TABLE cards ADD COLUMN declared_value REAL")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    return conn

def fetch(url):
    cookie = os.environ.get("PSA_COOKIE")
    if not cookie:
        sys.exit("PSA_COOKIE not set")
    # Cookie-only auth (no Bearer — it resolves to an empty context). Cloudflare
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
    r = creq.get(url, headers=headers, impersonate="chrome", timeout=30)
    return r.headers.get("content-type", ""), r.text

def probe():
    ctype, body = fetch(build_url())
    out = Path("probe_dump"); out.mkdir(exist_ok=True)
    ext = "json" if "json" in ctype else "html"
    p = out / f"orders_{datetime.now():%Y%m%d_%H%M%S}.{ext}"
    p.write_text(body)
    log(f"content-type={ctype} bytes={len(body)} -> {p}")
    if "login" in body.lower()[:4000] and "password" in body.lower():
        log("WARNING: response looks like a login page -- cookie likely expired/invalid")

def parse(ctype, body):
    """Parse PSA tRPC batch response; orders.list is the last result."""
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
            total = j.get("totalCount")
            if total and len(orders) < total:
                log(f"WARNING: got {len(orders)} of {total} orders -- raise page_length")
            break
    if orders is None:
        return []
    out = []
    for o in orders:
        step = (o.get("progressSummary") or {}).get("lastCompletedStep") or o.get("status") or ""
        imgs = o.get("image") or []
        thumb = next((i.get("thumbnail") for i in imgs if i.get("imageSide") == 1), "")
        out.append({
            "sub_number": str(o.get("submissionNumber") or ""),
            "order_number": str(o.get("orderNumber") or ""),
            "service": o.get("service") or "",
            "status": STEP_LABEL.get(step, step),
            "raw_step": step,
            "card_count": int(o.get("itemCount") or 0),
            "destination": "Ship back" if not o.get("isPickup") else "Pickup",
            "arrived": o.get("dateArrived") or "",
            "est_start": (o.get("dueOutDate") or "")[:10],
            "est_end": (o.get("dueOutDateUpperRange") or "")[:10],
            "shipped": (o.get("dateShipped") or "").replace("N/A", ""),
            "tracking": o.get("trackingNumber") or "",
            "carrier": o.get("carrier") if o.get("carrier") != "None" else "",
            "grades_ready": bool((o.get("progressSummary") or {}).get("gradesReady")),
            "on_hold": bool(o.get("onHold")),
            "thumb": thumb or "",
            "cert_ids": json.dumps(o.get("certIds") or []),
        })
    return [s for s in out if s["sub_number"]]

def detail_url(sub_number):
    import base64, urllib.parse
    blob = base64.b64encode(json.dumps({"submissionNumber": str(sub_number)},
        separators=(",", ":")).encode()).decode().rstrip("=")
    return ("https://www.psacard.com/api/grading/trpc/orders.get?batch=1&input="
            + urllib.parse.quote(json.dumps({"0": blob}, separators=(",", ":"))))

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
            "cert_no": str(sp.get("certNo") or pc.get("certNo") or ""),
            "name": sp.get("specDescription") or pc.get("specDescription") or "",
            "line_number": sp.get("lineNumber") or 0,
            "front_thumb": front or "", "back_thumb": back or "",
            "grade": str(pc.get("grade") or pc.get("cardGrade") or ""),
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
SPEC_DEPT_ID = int(os.environ.get("PSA_SPEC_DEPT_ID", "10"))  # 10 = TCG/trading cards

def completed_url(sub_number):
    import base64, urllib.parse
    blob = base64.b64encode(json.dumps({"submissionNumber": int(sub_number)},
        separators=(",", ":")).encode()).decode().rstrip("=")
    return ("https://www.psacard.com/api/grading/trpc/submissions.completed?batch=1&input="
            + urllib.parse.quote(json.dumps({"0": blob}, separators=(",", ":"))))

def images_url(spec_ids):
    import base64, urllib.parse
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
            continue
        qty = int(ln.get("quantity") or 1)
        # declaredValue is the LINE total (per-card value × quantity) — store per card
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
    _, body = fetch(completed_url(sub_number))
    lines = parse_completed_lines(body)
    if not lines:
        return []
    _, ibody = fetch(images_url([l["spec_id"] for l in lines]))
    imgs = parse_spec_images(ibody)
    out = []
    for l in lines:
        pi = imgs.get(str(l["spec_id"]), {})
        out.append({"line_number": l["line_number"], "spec_id": l["spec_id"],
                    "name": l["name"], "quantity": l["quantity"], "dv": l.get("dv"),
                    "front": pi.get("front", ""), "back": pi.get("back", "")})
    return out

def prelim_cards(sub_number, spec_lines):
    """Turn spec lines into standalone prelim cards. Keys are namespaced by submission —
    'spec:<sub>:<specId>' — because the SAME card (specId) can appear in multiple subs, and
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
      1. uniform — every card on the form is declared at the same value: assign it
         to all cards (covers old line-0 subs too).
      2. positional — expanded form positions == card count: map in submission
         order (cards sorted by line_number, cert_id).
      3. identity — fall back to direct line_number match.
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

def carryover_owners(sub_number, old_rows, new_cards):
    """When prelim (spec:) cards are replaced by real cert cards, move owner tags
    across by line number. old_rows: list of (cert_id, line_number) pre-replacement."""
    old_by_line = {ln: cid for cid, ln in old_rows if str(cid).startswith("spec:")}
    targets = [c for c in new_cards if not str(c["cert_id"]).startswith("spec:")]
    if not old_by_line or not targets:
        return
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    oc = sqlite3.connect(OWN_DB)
    oc.execute("CREATE TABLE IF NOT EXISTS owners (cert_id TEXT PRIMARY KEY, owner TEXT, updated_at TEXT)")
    moved = 0
    for c in targets:
        old_cid = old_by_line.get(c["line_number"])
        if not old_cid:
            continue
        row = oc.execute("SELECT owner FROM owners WHERE cert_id=?", (old_cid,)).fetchone()
        if row and row[0]:
            oc.execute("INSERT OR REPLACE INTO owners(cert_id, owner, updated_at) VALUES (?,?,?)",
                       (c["cert_id"], row[0], now))
            oc.execute("DELETE FROM owners WHERE cert_id=?", (old_cid,))
            moved += 1
    oc.commit(); oc.close()
    if moved:
        log(f"sub {sub_number}: carried over {moved} owner tag(s) prelim -> cert")

def upsert_cards(conn, sub_number, cards):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    old_rows = conn.execute("SELECT cert_id, line_number FROM cards WHERE sub_number=?",
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
    for s in subs:
        sub = s["sub_number"]
        has_certs = bool(json.loads(s["cert_ids"] or "[]"))
        # A sub that was ALREADY Shipped before this scan is frozen — PSA won't
        # change its cards/images. Skip its detail fetch unless something is
        # missing (image or declared value) or --full was passed. Cuts PSA API
        # calls roughly in half once every sub is fully populated.
        if not full and s["status"] == "Shipped" and prev.get(sub) == "Shipped":
            row = conn.execute("""SELECT count(*), sum(front_thumb!=''),
                sum(declared_value IS NULL) FROM cards WHERE sub_number=?""", (sub,)).fetchone()
            if row[0] and row[0] == (row[1] or 0) and not (row[2] or 0):
                skipped += 1
                continue
        try:
            cards = []
            if has_certs:
                _, body = fetch(detail_url(sub))
                cards = parse_detail(sub, body)
                # orders.get knows nothing about declared values — carry the ones we
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
            # is missing an image or a declared value — or the sub has no cards at
            # all yet — fall back to the submission 'complete' page (spec images,
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
    log(f"cards refreshed: {total}" + (f" ({skipped} stable shipped subs skipped)" if skipped else ""))

def notify(text):
    if not WEBHOOK:
        return
    try:
        req = urllib.request.Request(WEBHOOK, data=json.dumps({"content": text}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        log(f"webhook failed: {e}")

def upsert(conn, subs):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    changes = []
    for s in subs:
        row = conn.execute("SELECT status, grades_ready FROM subs WHERE sub_number=?",
                           (s["sub_number"],)).fetchone()
        vals = (s["order_number"], s["service"], s["status"], s["card_count"],
                s["destination"], s["arrived"], s["est_start"], s["est_end"],
                s["shipped"], s["tracking"], s["carrier"], int(s["grades_ready"]),
                int(s["on_hold"]), s["thumb"], s["cert_ids"])
        if row is None:
            conn.execute("""INSERT INTO subs (sub_number, order_number, service, status,
                card_count, destination, arrived, est_start, est_end, shipped, tracking,
                carrier, grades_ready, on_hold, thumb, cert_ids, first_seen, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (s["sub_number"],) + vals + (now, now))
            conn.execute("INSERT INTO status_history(sub_number,status,seen_at) VALUES (?,?,?)",
                         (s["sub_number"], s["status"], now))
            changes.append(f"new sub #{s['sub_number']} ({s['service']}, {s['card_count']} cards) -- {s['status']}")
        else:
            if row[0] != s["status"] and s["status"]:
                conn.execute("INSERT INTO status_history(sub_number,status,seen_at) VALUES (?,?,?)",
                             (s["sub_number"], s["status"], now))
                changes.append(f"sub #{s['sub_number']}: {row[0]} -> {s['status']}")
            if not row[1] and s["grades_ready"]:
                changes.append(f"sub #{s['sub_number']}: grades are ready")
            conn.execute("""UPDATE subs SET order_number=?, service=?, status=?, card_count=?,
                destination=?, arrived=?, est_start=?, est_end=?, shipped=?, tracking=?,
                carrier=?, grades_ready=?, on_hold=?, thumb=?, cert_ids=?, updated_at=?
                WHERE sub_number=?""", vals + (now, s["sub_number"]))
    conn.commit()
    return changes

def cycle(conn):
    # one retry on the orders.list fetch — a transient blip otherwise loses a
    # whole scan window (we only run twice a day now)
    ctype = body = ""
    for attempt in (1, 2):
        try:
            ctype, body = fetch(build_url())
            break
        except Exception as e:
            log(f"orders.list fetch attempt {attempt} failed: {e}")
            if attempt == 1:
                time.sleep(5)
    subs = parse(ctype, body)
    if not subs:
        log("parsed 0 subs -- parser needs adjusting or cookie expired; run --probe")
        return
    # statuses BEFORE this scan's upsert — used to skip detail-fetching subs that
    # were already Shipped last time (their cards can no longer change)
    prev = {r[0]: r[1] for r in conn.execute("SELECT sub_number, status FROM subs")}
    changes = upsert(conn, subs)
    log(f"parsed {len(subs)} subs, {len(changes)} changes")
    for c in changes:
        log(f"  {c}")
    if changes:
        notify("**PSA update**\n" + "\n".join(changes))
    refresh_cards(conn, subs, prev, full="--full" in sys.argv)

def main():
    if "--probe" in sys.argv:
        probe(); return
    conn = db()
    if "--once" in sys.argv:
        cycle(conn); return
    log(f"daemon start, interval {POLL_INTERVAL}s")
    while True:
        try:
            cycle(conn)
        except Exception as e:
            log(f"cycle error: {e}")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
