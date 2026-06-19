"""The local database the engine writes to.

Every market snapshot is saved to `data/engine.db`, so the day's index and volatility history
is kept on disk whether or not the dashboard was open. The dashboard reads it, and so can you,
with any SQLite client.

The paper book lives in its own JSON file beside it, not in here.

Study code. Not investment advice. See DISCLAIMER.md.
"""
import os
import sqlite3
import logging
from datetime import datetime

from engine.config import IST, DATA_DIR

logger = logging.getLogger(__name__)
DB_PATH = os.path.join(DATA_DIR, "engine.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS market_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT,
    ts            TEXT,
    nifty         REAL,
    nifty_pct     REAL,
    banknifty     REAL,
    banknifty_pct REAL,
    vix           REAL,
    vix_pct       REAL
);
CREATE INDEX IF NOT EXISTS idx_mkt_date ON market_snapshots(date);
"""


def _conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=5)
    c.executescript(_SCHEMA)
    return c


def save_market(snap: dict, ts: datetime = None) -> None:
    """Append one market snapshot. Never raises: a logging failure must not stop the loop."""
    ts = ts or datetime.now(IST)
    try:
        def _val(key, field):
            d = snap.get(key) or {}
            return d.get(field) if isinstance(d, dict) else None

        with _conn() as c:
            c.execute(
                "INSERT INTO market_snapshots "
                "(date,ts,nifty,nifty_pct,banknifty,banknifty_pct,vix,vix_pct) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (ts.date().isoformat(), ts.isoformat(),
                 _val("nifty", "price"), _val("nifty", "change_pct"),
                 _val("banknifty", "price"), _val("banknifty", "change_pct"),
                 _val("vix", "price"), _val("vix", "change_pct")))
    except Exception as e:
        logger.warning(f"store.save_market failed: {e}")


def stats() -> dict:
    """Row counts and the date range held, for the startup log."""
    try:
        with _conn() as c:
            rows = c.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0]
            span = c.execute("SELECT MIN(date), MAX(date) FROM market_snapshots").fetchone()
        return {"snapshots": rows, "from": span[0], "to": span[1]}
    except Exception as e:
        logger.warning(f"store.stats failed: {e}")
        return {}
