"""
Signal Database — persistent SQLite store of every signal shown on PM DECISIONS.

Captures BOTH:
  - 3-Family Gate-2 (trade-ready) stock signals + their bought-option order
  - ORB+VWAP index signals (NIFTY/BANKNIFTY) + their ATM option order

Appended continuously; idempotent (one row per date+strategy+symbol+direction), so the
DB simply accumulates day by day. Query it with any SQLite tool, or:
    python -m engine.signal_db            # print recent rows + export CSV
"""
import os
import sqlite3
import logging
from datetime import datetime

from engine.config import DATA_DIR, IST

logger = logging.getLogger(__name__)
DB_PATH = os.path.join(DATA_DIR, "signals.db")
CSV_PATH = os.path.join(DATA_DIR, "signals_export.csv")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pm_signals (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    date           TEXT NOT NULL,
    time           TEXT,
    strategy       TEXT,      -- '3-Family' | 'ORB+VWAP'
    symbol         TEXT,      -- RELIANCE / NIFTY / BANKNIFTY
    direction      TEXT,      -- LONG | SHORT
    opt_type       TEXT,      -- CALL | PUT
    strike         REAL,
    expiry         TEXT,
    entry_premium  REAL,
    target_premium REAL,
    stop_premium   REAL,
    lot            INTEGER,
    capital        REAL,
    alpha_z        REAL,      -- 3-Family only
    breadth        INTEGER,   -- 3-Family only
    vol_ratio      REAL,      -- 3-Family only (ORB volume surge x)
    status         TEXT,      -- OPEN / WIN / LOSS (synced to trade log)
    recorded_at    TEXT,
    UNIQUE(date, strategy, symbol, direction)
);
"""

_FIELDS = ("date", "time", "strategy", "symbol", "direction", "opt_type", "strike",
           "expiry", "entry_premium", "target_premium", "stop_premium", "lot",
           "capital", "alpha_z", "breadth", "vol_ratio", "status", "recorded_at")


def _conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=5)
    c.execute(_SCHEMA)
    return c


def record_signal(**f) -> None:
    """
    Insert one PM signal. Idempotent per (date, strategy, symbol, direction) — re-scans
    of the same live signal are ignored, but its status is refreshed.
    """
    try:
        now = datetime.now(IST)
        row = {k: f.get(k) for k in _FIELDS}
        row["date"] = row["date"] or now.date().isoformat()
        row["time"] = row["time"] or now.strftime("%H:%M:%S")
        row["recorded_at"] = now.isoformat()
        with _conn() as c:
            c.execute(f"""
                INSERT INTO pm_signals ({','.join(_FIELDS)})
                VALUES ({','.join('?' for _ in _FIELDS)})
                ON CONFLICT(date, strategy, symbol, direction)
                DO UPDATE SET status=excluded.status
            """, tuple(row[k] for k in _FIELDS))
    except Exception as e:
        logger.warning(f"signal_db record failed: {e}")


def fetch_all() -> list:
    try:
        with _conn() as c:
            cur = c.execute("SELECT * FROM pm_signals ORDER BY date DESC, time DESC")
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception as e:
        logger.warning(f"signal_db fetch failed: {e}")
        return []


def export_csv(path: str = None) -> str:
    """Dump the whole DB to CSV (called daily / on demand)."""
    import csv
    rows = fetch_all()
    path = path or CSV_PATH
    if not rows:
        return ""
    try:
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        return path
    except Exception as e:
        logger.warning(f"signal_db export failed: {e}")
        return ""


if __name__ == "__main__":
    rows = fetch_all()
    print(f"signals.db — {len(rows)} signals")
    for r in rows[:30]:
        print(f"  {r['date']} {r['time']:>8} | {r['strategy']:9} | {r['symbol']:10} "
              f"{r['direction']:5} {r['opt_type'] or '':4} {r['strike'] or '':>8} "
              f"| entry={r['entry_premium']} status={r['status']}")
    csv_path = export_csv()
    if csv_path:
        print(f"exported -> {csv_path}")
