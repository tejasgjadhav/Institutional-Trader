"""
Local daily DB store for the headless engine.

Persists EVERY scan (all scored stocks + their gate state) and EVERY market snapshot to
`data/engine.db`, so the full day's data is saved locally — independent of the GUI and
apart from the trade log (which stays in trade_log.json). The read-only UI and any later
analysis read from here.
"""
import os
import sqlite3
import logging
from datetime import datetime

from engine.config import IST, DATA_DIR

logger = logging.getLogger(__name__)
DB_PATH = os.path.join(DATA_DIR, "engine.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scan_rows (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT,
    ts          TEXT,
    ticker      TEXT,
    alpha_z     REAL,
    direction   TEXT,
    breadth     INTEGER,
    gate1       INTEGER,
    gate2       INTEGER,
    gate3       INTEGER,
    gate4       INTEGER,
    gate5       INTEGER,
    trade_ready INTEGER,
    vol_ratio   REAL,
    ext_pct     REAL,
    orb_w       REAL,
    nifty_dir   INTEGER
);
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
CREATE INDEX IF NOT EXISTS idx_scan_date ON scan_rows(date);
CREATE INDEX IF NOT EXISTS idx_mkt_date  ON market_snapshots(date);
"""


def _conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=5)
    c.executescript(_SCHEMA)
    # migrate older DBs (CREATE TABLE IF NOT EXISTS won't add new columns)
    for col, typ in (("gate5", "INTEGER"), ("orb_w", "REAL")):
        try:
            c.execute(f"ALTER TABLE scan_rows ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass   # column already exists
    return c


def save_scan(results: list, ts: datetime = None) -> int:
    """Persist one scan cycle: one row per scored stock with its gate state."""
    ts = ts or datetime.now(IST)
    d, tss = ts.date().isoformat(), ts.isoformat()
    rows = []
    for r in (results or []):
        if "error" in r:
            continue
        rows.append((
            d, tss, r.get("ticker"), r.get("alpha_z"), r.get("direction"),
            r.get("breadth"),
            int(bool(r.get("passes_gate_1"))), int(bool(r.get("gate_2"))),
            int(bool(r.get("aligned"))), int(bool(r.get("not_extended"))),
            int(bool(r.get("wide_open"))),
            int(bool(r.get("trade_ready"))),
            r.get("vol_ratio"), r.get("entry_extension_pct"),
            r.get("orb_range_width"), r.get("nifty_dir"),
        ))
    if not rows:
        return 0
    try:
        with _conn() as c:
            c.executemany(
                "INSERT INTO scan_rows (date,ts,ticker,alpha_z,direction,breadth,"
                "gate1,gate2,gate3,gate4,gate5,trade_ready,vol_ratio,ext_pct,orb_w,nifty_dir) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        return len(rows)
    except Exception as e:
        logger.warning(f"store.save_scan failed: {e}")
        return 0


def save_market(snap: dict, ts: datetime = None) -> None:
    """Persist one market snapshot (NIFTY/BANKNIFTY/VIX)."""
    ts = ts or datetime.now(IST)
    n, b, v = snap.get("nifty", {}), snap.get("banknifty", {}), snap.get("vix", {})
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO market_snapshots (date,ts,nifty,nifty_pct,banknifty,"
                "banknifty_pct,vix,vix_pct) VALUES (?,?,?,?,?,?,?,?)",
                (ts.date().isoformat(), ts.isoformat(),
                 n.get("price"), n.get("pct"), b.get("price"), b.get("pct"),
                 v.get("price"), v.get("pct")))
    except Exception as e:
        logger.warning(f"store.save_market failed: {e}")


def stats() -> dict:
    """Quick counts for status/health."""
    try:
        with _conn() as c:
            scans = c.execute("SELECT COUNT(*) FROM scan_rows").fetchone()[0]
            days = c.execute("SELECT COUNT(DISTINCT date) FROM scan_rows").fetchone()[0]
            mkt = c.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0]
        return {"scan_rows": scans, "days": days, "market_snapshots": mkt}
    except Exception:
        return {}
