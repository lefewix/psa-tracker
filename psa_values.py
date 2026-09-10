#!/usr/bin/env python3
"""psa-values: pull PSA's own value data for graded cards of completed orders.

For each card of a Shipped submission (cert_no + grade known) we open the PUBLIC
cert-verification page https://www.psacard.com/cert/<cert_no>/psa in a real
Chromium (headful under xvfb - the same Cloudflare-passing recipe as
psa_login.py; plain-HTTP requests get challenged, no login/cookie is needed)
and read off the rendered text:
  - "PSA ESTIMATE"            PSA's published estimate for this card AT THIS GRADE
  - "Sales of Similar Items"  recent comp sales, newest first (price + date)

Cards sharing (name, grade) share a value, so we visit ONE cert page per unique
pair and write the result to every matching cert. Values are USD.

Everything lands in the additive `card_values` table - the rest of the schema is
untouched, so DROP TABLE card_values (or just unsetting PSA_VALUES for the web
app / run_scan.sh) fully reverts the feature.

Also refreshes the USDCAD rate into fx_rates each run (keyless public FX API);
app.py converts the stored USD values to CAD at render time.

Usage: psa_values.py [--all | --fx-only]
Env:   PSA_DB              account database (same as psa_watch.py)
       PSA_VALUES_BATCH    max cert pages per run (default 40; --all = no cap)
       PSA_VALUES_MAX_AGE  refresh values older than this many days (default 14)
"""
import json, os, re, sqlite3, sys, time
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

DB_PATH = os.environ.get("PSA_DB", "/opt/psa-tracker/psa.db")
ACCT = os.environ.get("PSA_ACCT_ID", "account")
BATCH = int(os.environ.get("PSA_VALUES_BATCH", "40"))
MAX_AGE_DAYS = int(os.environ.get("PSA_VALUES_MAX_AGE", "14"))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

MONEY = re.compile(r"^\$([\d,]+(?:\.\d{2})?)$")
DATE = re.compile(r"^\d{2}/\d{2}/\d{2}$")

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


def log(m):
    print(f"[psa-values:{ACCT}] {m}", flush=True)


def parse_cert_text(text):
    """Rendered cert-page text -> (estimate, [(price, 'MM/DD/YY'), ...] newest first)."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    est = None
    for i, l in enumerate(lines):
        if l.upper() == "PSA ESTIMATE":
            for j in range(i + 1, min(i + 4, len(lines))):
                m = MONEY.match(lines[j])
                if m:
                    est = float(m.group(1).replace(",", ""))
                    break
            break
    sales, seen = [], set()
    start = next((i for i, l in enumerate(lines) if l.lower().startswith("sales of similar")), None)
    if start is not None:
        price = None
        for l in lines[start + 1:start + 90]:
            m = MONEY.match(l)
            if m:
                price = float(m.group(1).replace(",", ""))
            elif price is not None and DATE.match(l):
                if (price, l) not in seen:  # page can render the list twice (responsive)
                    seen.add((price, l))
                    sales.append((price, l))
                price = None
    return est, sales


def pick_groups(conn):
    """Unique (name, grade) groups of shipped+graded certs needing a fetch:
    groups with any un-valued cert first, then stale ones (oldest first)."""
    conn.executescript(SCHEMA)
    have = {r[0]: r[1] for r in conn.execute("SELECT cert_no, fetched_at FROM card_values")}
    groups = {}
    for name, grade, cert in conn.execute(
            """SELECT c.name, c.grade, c.cert_no FROM cards c
               JOIN subs s ON s.sub_number = c.sub_number
               WHERE s.status = 'Shipped' AND c.cert_no != '' AND c.grade != ''
               ORDER BY c.cert_no"""):
        groups.setdefault((name, grade), []).append(cert)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)).isoformat(timespec="seconds")
    todo = []
    for key, certs in groups.items():
        stamps = [have.get(c) for c in certs]
        if any(s is None for s in stamps):
            todo.append((0, "", key, certs))          # never fetched
        elif min(stamps) < cutoff:
            todo.append((1, min(stamps), key, certs))  # stale
    todo.sort()
    return [(key, certs) for _, _, key, certs in todo]


def upsert(conn, certs, est, sales, error=""):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    last, last_date = (sales[0] if sales else (None, None))
    for cn in certs:
        conn.execute("""INSERT INTO card_values
            (cert_no, estimate, last_sale, last_sale_date, n_sales, sales_json, fetched_at, error)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(cert_no) DO UPDATE SET estimate=excluded.estimate,
              last_sale=excluded.last_sale, last_sale_date=excluded.last_sale_date,
              n_sales=excluded.n_sales, sales_json=excluded.sales_json,
              fetched_at=excluded.fetched_at, error=excluded.error""",
            (cn, est, last, last_date, len(sales), json.dumps(sales), now, error))
    conn.commit()


def main():
    limit = None if "--all" in sys.argv else BATCH
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA busy_timeout=10000")
    conn.executescript(SCHEMA)
    fetch_fx(conn)
    if "--fx-only" in sys.argv:
        return 0
    todo = pick_groups(conn)
    if limit is not None:
        todo = todo[:limit]
    if not todo:
        log("nothing to fetch (all values fresh)")
        return 0
    log(f"fetching {len(todo)} cert pages ({sum(len(c) for _, c in todo)} cards)")
    done = hard_fails = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                  "--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, locale="en-CA",
                                  viewport={"width": 1366, "height": 900})
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()
        try:
            for (name, grade), certs in todo:
                cert = certs[0]
                try:
                    page.goto(f"https://www.psacard.com/cert/{cert}/psa",
                              wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(3200)
                    est, sales = parse_cert_text(page.inner_text("body"))
                    if est is None and not sales:      # slow render? one more beat
                        page.wait_for_timeout(2500)
                        est, sales = parse_cert_text(page.inner_text("body"))
                    upsert(conn, certs, est, sales, "" if (est or sales) else "no-data")
                    done += 1
                    e = f"${est:,.0f}" if est is not None else "-"
                    log(f"{cert} PSA {grade} {name[:48]!r}: est {e}, {len(sales)} sales"
                        + (f" x{len(certs)} certs" if len(certs) > 1 else ""))
                except Exception as ex:
                    hard_fails += 1
                    log(f"{cert} FAILED: {str(ex)[:120]}")
                    if hard_fails >= 3 and done == 0:
                        log("first pages all failing - aborting run (blocked?)")
                        return 1
                time.sleep(1.0)
        finally:
            ctx.close(); browser.close()
    log(f"done: {done} fetched, {hard_fails} failed, {len(todo) - done - hard_fails} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
