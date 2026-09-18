"""MARKET HISTORY DATABASE (18-Sep-2026, user: "record all data in database which can be retrieved
whenever required"). One SQLite file, data/market_history.db, holding every bar this project has
fetched so no study ever refetches what another already paid for, and the daily cleanup that wiped
/tmp cannot touch it.

Tables
  idx_1m       1-minute OHLCV for indices and stocks (imported from research/m1cache and any new fetch)
  contracts    option contracts per (symbol, expiry): instrument_key, strike, type, lot
  opt_1m       1-minute OHLCV+OI for option contracts (expired-instruments endpoint)
  opt_days     which (instrument_key, day) pairs have been fetched - an EMPTY day (no trades) is
               recorded too, so it is never refetched and never mistaken for a missing fetch
Every read goes through here; a miss is fetched from Upstox at <= 1 req/s with a 429 wait-and-loop
(the token is shared with the live engine) and stored before it is returned.

CLI:  python -m engine.histdb opt <instrument_key> <YYYY-MM-DD>
      python -m engine.histdb idx <SYMBOL> <YYYY-MM-DD>
      python -m engine.histdb stats
"""
import os, sys, time, gzip, glob, sqlite3, logging, urllib.parse
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "market_history.db")
M1CACHE = os.path.join(ROOT, "research", "m1cache")
SCHEMA = """
CREATE TABLE IF NOT EXISTS idx_1m (symbol TEXT NOT NULL, ts TEXT NOT NULL, o REAL, h REAL, l REAL, c REAL, v REAL,
    PRIMARY KEY (symbol, ts));
CREATE TABLE IF NOT EXISTS contracts (symbol TEXT NOT NULL, expiry TEXT NOT NULL, instrument_key TEXT PRIMARY KEY,
    strike REAL, type TEXT, lot INTEGER, fetched_at TEXT);
CREATE INDEX IF NOT EXISTS ix_contracts ON contracts(symbol, expiry);
CREATE TABLE IF NOT EXISTS opt_1m (instrument_key TEXT NOT NULL, day TEXT NOT NULL, hm TEXT NOT NULL,
    o REAL, h REAL, l REAL, c REAL, v REAL, oi REAL, PRIMARY KEY (instrument_key, day, hm));
CREATE TABLE IF NOT EXISTS opt_days (instrument_key TEXT NOT NULL, day TEXT NOT NULL, n_rows INTEGER,
    fetched_at TEXT, PRIMARY KEY (instrument_key, day));
"""
_PACE = [0.0]


def conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB, timeout=30)
    c.executescript(SCHEMA)
    return c


# ── option 1-minute candles: read-through cache ──────────────────────────────
def opt_candles(instrument_key, day, fetch=True):
    """{HH:MM: (o,h,l,c,v,oi)} for one contract-day. Empty dict = fetched, no trades. None = not
    fetched and fetch=False."""
    with conn() as c:
        row = c.execute("SELECT n_rows FROM opt_days WHERE instrument_key=? AND day=?", (instrument_key, day)).fetchone()
        if row is not None:
            r = c.execute("SELECT hm,o,h,l,c,v,oi FROM opt_1m WHERE instrument_key=? AND day=? ORDER BY hm",
                          (instrument_key, day)).fetchall()
            return {x[0]: tuple(x[1:]) for x in r}
    if not fetch:
        return None
    from engine.data_fetcher import UPSTOX_BASE, SESSION
    from engine.instruments import encode_key
    url = f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(instrument_key)}/1minute/{day}/{day}"
    cs = None
    for a in range(120):
        gap = time.time() - _PACE[0]
        if gap < 1.0: time.sleep(1.0 - gap)          # <= 1 req/s: shared with the live engine
        _PACE[0] = time.time()
        try:
            r = SESSION.get(url, timeout=30)
            if r.status_code == 200:
                cs = r.json().get("data", {}).get("candles", []); break
            if r.status_code == 429:
                time.sleep(60); continue              # loop as per the rate limit (user, 18-Sep)
            cs = []; break                            # 4xx other than 429: nothing to fetch
        except Exception:
            time.sleep(5)
    if cs is None:
        raise RuntimeError(f"histdb: {instrument_key} {day} still failing after 2 h of rate-limit waits")
    rows = [(instrument_key, day, x[0][11:16], float(x[1]), float(x[2]), float(x[3]), float(x[4]),
             float(x[5] or 0), float(x[6] or 0)) for x in cs]
    with conn() as c:
        c.executemany("INSERT OR REPLACE INTO opt_1m VALUES (?,?,?,?,?,?,?,?,?)", rows)
        c.execute("INSERT OR REPLACE INTO opt_days VALUES (?,?,?,?)",
                  (instrument_key, day, len(rows), datetime.now().isoformat(timespec="seconds")))
    return {r[2]: tuple(r[3:]) for r in rows}


def opt_close_at(instrument_key, day, hm, fetch=True):
    """Close of the bar at HH:MM, or the last bar at or before it."""
    b = opt_candles(instrument_key, day, fetch=fetch)
    if not b:
        return None
    if hm in b:
        return b[hm][3]
    ks = sorted(k for k in b if k <= hm)
    return b[ks[-1]][3] if ks else None


def record_contracts(symbol, expiry, chain):
    rows = [(symbol, expiry, c["instrument_key"], float(c.get("strike_price") or 0), c.get("instrument_type"),
             int(c.get("lot_size") or 0), datetime.now().isoformat(timespec="seconds")) for c in chain if c.get("instrument_key")]
    with conn() as c:
        c.executemany("INSERT OR REPLACE INTO contracts VALUES (?,?,?,?,?,?,?)", rows)
    return len(rows)


# ── index / stock 1-minute bars ──────────────────────────────────────────────
def index_1m(symbol, day):
    with conn() as c:
        r = c.execute("SELECT ts,o,h,l,c,v FROM idx_1m WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts",
                      (symbol, day + " 00:00:00", day + " 23:59:59")).fetchall()
    return pd.DataFrame(r, columns=["ts", "o", "h", "l", "c", "v"])


def import_m1cache(limit=None):
    """Bulk-import research/m1cache/*.csv.gz into idx_1m. Idempotent (INSERT OR REPLACE)."""
    files = sorted(glob.glob(os.path.join(M1CACHE, "*.csv.gz")))[:limit]
    n = 0
    with conn() as c:
        for i, f in enumerate(files, 1):
            sym = os.path.basename(f).rsplit("_", 1)[0]
            d = pd.read_csv(f)
            c.executemany("INSERT OR REPLACE INTO idx_1m VALUES (?,?,?,?,?,?,?)",
                          [(sym, str(t)[:19], float(o), float(h), float(l), float(cl), float(v))
                           for t, o, h, l, cl, v in zip(d.ts, d.o, d.h, d.l, d.c, d.v)])
            n += len(d)
            if i % 100 == 0:
                c.commit(); print(f"  imported {i}/{len(files)} files · {n:,} rows", flush=True)
    return n


def stats():
    with conn() as c:
        out = {}
        for t in ("idx_1m", "contracts", "opt_1m", "opt_days"):
            out[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        out["idx_symbols"] = c.execute("SELECT COUNT(DISTINCT symbol) FROM idx_1m").fetchone()[0]
        out["opt_contract_days_empty"] = c.execute("SELECT COUNT(*) FROM opt_days WHERE n_rows=0").fetchone()[0]
    out["db_mb"] = round(os.path.getsize(DB) / 1e6, 1) if os.path.exists(DB) else 0
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "stats":
        print(stats())
    elif a[0] == "opt":
        b = opt_candles(a[1], a[2]); print(f"{len(b)} bars"); [print(k, v) for k, v in list(b.items())[:5]]
    elif a[0] == "idx":
        print(index_1m(a[1], a[2]).head())
    elif a[0] == "import":
        print("rows:", import_m1cache())
