#!/usr/bin/env python3
"""psa-values: pull PSA's own sales data for graded cards.

For each graded card (cert_no + grade known, which psa_watch fills as soon as
the submission's grades are ready, plus spec_id, PSA's id for the card itself)
we ask the logged-in psacard.com API what that card sold for AT THAT GRADE:
researchJourney.getSalesBySpecId, the call behind the "Sales History" tab on
psacard.com/spec/psa/<spec_id>. Newest sale first; the latest price is the value.

The public cert page (and its "PSA ESTIMATE") sits behind an interactive
Cloudflare challenge from the server since late Sep 2026, so there is no estimate any
more: `estimate` stays NULL and `last_sale` carries the value (T215). The call
needs the scanner's PSA_COOKIE; run_scan.sh only runs this after a clean scan.

Cards sharing (spec_id, grade) share a value, so ONE call per unique pair writes
every matching cert. Values are USD.

Everything lands in the additive `card_values` table - the rest of the schema is
untouched, so DROP TABLE card_values (or just unsetting PSA_VALUES for the web
app / run_scan.sh) fully reverts the feature.

Also refreshes the USDCAD rate into fx_rates each run (keyless public FX API);
app.py converts the stored USD values to CAD at render time.

Usage: psa_values.py [--all | --fx-only | --new-only]
       --new-only: only never-fetched certs, no FX; quiet when there are none, so
       run_scan.sh calls it every scan (values land the scan after grades do).
Env:   PSA_DB              account database (same as psa_watch.py)
       PSA_COOKIE          the scanner's psacard.com session
       PSA_VALUES_BATCH    max calls per run (default 40; --all = no cap)
       PSA_VALUES_MAX_AGE  refresh values older than this many days (default 14)
"""
import base64, json, os, re, sqlite3, sys, time, urllib.parse
from datetime import datetime, timezone, timedelta
from curl_cffi import requests as creq

import psa_common

DB_PATH = os.environ.get("PSA_DB", "/opt/psa-tracker/psa.db")
ACCT = os.environ.get("PSA_ACCT_ID", "account")
BATCH = int(os.environ.get("PSA_VALUES_BATCH", "40"))
MAX_AGE_DAYS = int(os.environ.get("PSA_VALUES_MAX_AGE", "14"))
log = psa_common.log(f"psa-values:{ACCT}")
# A Cloudflare challenge is not "no data": storing it as such blanked good values
# and froze them for MAX_AGE_DAYS (T215). A challenged run stores nothing and touches
# this marker; --new-only runs sit out BLOCK_HOURS after it, full runs always try.
BLOCKED = os.path.join(os.path.dirname(DB_PATH) or ".", ".values_blocked")
BLOCK_HOURS = 6
SALES_URL = "https://www.psacard.com/api/psa/trpc/researchJourney.getSalesBySpecId"
N_SALES = 5  # newest sales kept in sales_json

SCHEMA = """
CREATE TABLE IF NOT EXISTS card_values (
  cert_no        TEXT PRIMARY KEY,
  estimate       REAL,
  last_sale      REAL,
  last_sale_date TEXT,
  n_sales        INTEGER DEFAULT 0,
  sales_json     TEXT,
  fetched_at     TEXT,
  error          TEXT
);
CREATE TABLE IF NOT EXISTS fx_rates (
  pair       TEXT PRIMARY KEY,
  rate       REAL,
  fetched_at TEXT
);
"""

FX_URL = "https://open.er-api.com/v6/latest/USD"  # keyless USD->CAD source


def fetch_fx(conn):
    """Refresh the USDCAD rate (app.py renders card values in CAD with it).
    Failures keep the previous stored rate - stale beats absent."""
    import urllib.request
    try:
        with urllib.request.urlopen(FX_URL, timeout=15) as r:
            data = json.loads(r.read().decode())
        rate = float(data["rates"]["CAD"])
        if not (0.5 < rate < 3):  # sanity: a broken feed must not scale the site
            raise ValueError(f"implausible USDCAD rate {rate}")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn.execute("""INSERT INTO fx_rates (pair, rate, fetched_at) VALUES ('USDCAD',?,?)
            ON CONFLICT(pair) DO UPDATE SET rate=excluded.rate, fetched_at=excluded.fetched_at""",
            (rate, now))
        conn.commit()
        log(f"USDCAD rate {rate:.4f}")
        return True
    except Exception as ex:
        log(f"fx fetch failed: {str(ex)[:80]}")
        return False


class Blocked(Exception):
    pass


def fetch_sales(spec_id, grade):
    """(latest price, latest ISO date, total sale count, [(price, date), ...]) for one
    card at one grade. Raises Blocked on a challenge or a dead session."""
    m = re.match(r"(\d+(?:\.\d+)?)\s*(.*)", grade)
    inp = {"specId": str(spec_id), "grade": m.group(1) if m else grade,
           "gradingType": "ALL",
           # "9 OC" and friends are qualified grades, priced separately by PSA
           "qualifiers": "QUALIFIERS" if m and m.group(2) else "NON_QUALIFIERS",
           "pageSize": N_SALES, "cursor": 1, "timeRange": 0}
    blob = base64.b64encode(json.dumps({"json": inp}, separators=(",", ":")).encode()).decode().rstrip("=")
    url = SALES_URL + "?batch=1&input=" + urllib.parse.quote(json.dumps({"0": blob}, separators=(",", ":")))
    r = creq.get(url, headers={"Cookie": os.environ.get("PSA_COOKIE", ""), "Accept": "*/*",
                               "Referer": f"https://www.psacard.com/spec/psa/{spec_id}",
                               "sec-fetch-site": "same-origin", "sec-fetch-mode": "cors",
                               "sec-fetch-dest": "empty"},
                 impersonate="chrome", timeout=30, allow_redirects=False)
    if r.status_code in (401, 403) or "just a moment" in r.text[:2000].lower():
        raise Blocked(f"HTTP {r.status_code}" + (" Cloudflare challenge" if r.status_code == 403 else ""))
    d = r.json()[0]["result"]["data"]["json"]
    sales = [(x["salePrice"], (x.get("saleDate") or "")[:10])
             for x in (d.get("sales") or []) if x.get("salePrice") is not None]
    last, last_date = sales[0] if sales else (None, None)
    return last, last_date, d.get("totalCount") or len(sales), sales


def pick_groups(conn, new_only=False):
    """Unique (spec_id, grade) groups of graded certs needing a fetch: groups with
    any un-valued cert first, then stale ones (oldest first). Cert number, grade and
    spec_id are the whole precondition - psa_watch fills them at grades-ready, well
    before the submission ships."""
    conn.executescript(SCHEMA)
    have = {r[0]: r[1] for r in conn.execute("SELECT cert_no, fetched_at FROM card_values")}
    groups = {}
    for spec, grade, cert, name in conn.execute(
            """SELECT c.spec_id, c.grade, c.cert_no, c.name FROM cards c
               WHERE c.cert_no != '' AND c.grade != '' AND c.spec_id != ''
               ORDER BY c.cert_no"""):
        groups.setdefault((spec, grade), (name, []))[1].append(cert)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)).isoformat(timespec="seconds")
    todo = []
    for key, (name, certs) in groups.items():
        stamps = [have.get(c) for c in certs]
        if any(s is None for s in stamps):
            todo.append((0, "", key, name, certs))          # never fetched
        elif not new_only and min(stamps) < cutoff:
            todo.append((1, min(stamps), key, name, certs))  # stale
    todo.sort()
    return [(key, name, certs) for _, _, key, name, certs in todo]


def upsert(conn, certs, last, last_date, n, sales):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for cn in certs:
        conn.execute("""INSERT INTO card_values
            (cert_no, estimate, last_sale, last_sale_date, n_sales, sales_json, fetched_at, error)
            VALUES (?,NULL,?,?,?,?,?,?)
            ON CONFLICT(cert_no) DO UPDATE SET estimate=NULL,
              last_sale=excluded.last_sale, last_sale_date=excluded.last_sale_date,
              n_sales=excluded.n_sales, sales_json=excluded.sales_json,
              fetched_at=excluded.fetched_at, error=excluded.error""",
            (cn, last, last_date, n, json.dumps(sales), now, "" if sales else "no-data"))
    conn.commit()


def main():
    limit = None if "--all" in sys.argv else BATCH
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA busy_timeout=10000")
    conn.executescript(SCHEMA)
    new_only = "--new-only" in sys.argv
    if not new_only:
        fetch_fx(conn)
    if "--fx-only" in sys.argv:
        return 0
    if new_only and os.path.exists(BLOCKED) \
            and time.time() - os.path.getmtime(BLOCKED) < BLOCK_HOURS * 3600:
        return 0
    todo = pick_groups(conn, new_only)
    if limit is not None:
        todo = todo[:limit]
    if not todo:
        if not new_only:  # new-only runs every scan: stay quiet
            log("nothing to fetch (all values fresh)")
        return 0
    log(f"fetching {len(todo)} card/grade sales ({sum(len(c) for _, _, c in todo)} cards)")
    done = fails = 0
    for (spec, grade), name, certs in todo:
        try:
            last, last_date, n, sales = fetch_sales(spec, grade)
        except Blocked as ex:
            with open(BLOCKED, "w") as f:
                f.write(datetime.now(timezone.utc).isoformat(timespec="seconds") + "\n")
            log(f"spec {spec}: {ex} - stopping, nothing stored")
            return 1
        except Exception as ex:
            fails += 1
            log(f"spec {spec} PSA {grade} FAILED: {str(ex)[:120]}")
            if fails >= 3 and done == 0:
                log("first calls all failing - aborting run")
                return 1
            continue
        if os.path.exists(BLOCKED):
            os.remove(BLOCKED)
        upsert(conn, certs, last, last_date, n, sales)
        done += 1
        v = f"${last:,.2f} on {last_date}" if last is not None else "-"
        log(f"spec {spec} PSA {grade} {name[:48]!r}: last {v}, {n} sales"
            + (f" x{len(certs)} certs" if len(certs) > 1 else ""))
        time.sleep(1.0)
    log(f"done: {done} fetched, {fails} failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
