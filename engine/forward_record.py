"""The forward-record database — the instrument that decides whether lots go up.

WHY IT EXISTS (21-Aug-2026). The backtest is finished. It says v2 +27.2% and v1 +9.5% out-of-sample
with intervals excluding zero, and it CANNOT say whether that survives real fills. Only a forward
record can, and the paper position files are JSON blobs with no schema, no rejection history and no
query surface.

WHAT IT STORES, AND WHY EACH PIECE.
  * P&L stays on MIDS, exactly as the books already compute it. The user's point, and it is correct:
    bhavcopy has no bid/ask, so in-sample can never be on crossing prices. Switching the forward
    record to crossing prices would make it incomparable with both backtest windows, breaking the
    one clean comparison this system has.
  * `spread_pct` is stored as ONE diagnostic column. The live gate already caps the short leg at 6%,
    and at that boundary crossing costs about 6% of the credit and ~11% of ROM — real but bounded,
    and c/w only moves 0.500 -> 0.470, nowhere near the 0.40 gate. So the open question is not
    WHETHER crossing costs something but WHERE inside the 0-6% band real trades actually sit. One
    number answers it; four bid/ask columns were overkill.
  * REJECTIONS get their own table. A candidate the gate blocks leaves no trace anywhere today, so
    the fraction of backtest trades that are actually takeable is unmeasured. On 17-Aug the live
    gates rejected 10 of 17 candidates. That ratio decides how much of a backtested ROM you can
    actually collect, and nothing records it.

Nothing here may ever break trading: every public function swallows its own exceptions.
"""
import os
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "forward_record.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS fills (
    id            TEXT PRIMARY KEY,
    book          TEXT NOT NULL,          -- v2 / v1 / v0 / 0DTE-NIFTY / 0DTE-SENSEX
    symbol        TEXT NOT NULL,
    side          TEXT,
    entry_ts      TEXT NOT NULL,
    entry_date    TEXT NOT NULL,
    expiry        TEXT,
    short_strike  REAL, long_strike REAL, width REAL,
    lot           INTEGER, num_lots INTEGER, qty INTEGER,
    credit        REAL,                   -- on MIDS, same basis as both backtest windows
    cw            REAL,
    spread_pct    REAL,                   -- short-leg bid-ask at entry, diagnostic only
    -- EXIT
    exit_ts       TEXT, exit_date TEXT, exit_reason TEXT,
    exit_cost     REAL, pnl_rs REAL, margin_rs REAL,
    status        TEXT NOT NULL DEFAULT 'OPEN',
    advisory      INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS rejections (
    ts        TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    book      TEXT NOT NULL,
    symbol    TEXT NOT NULL,
    reason    TEXT NOT NULL,              -- spread / open_interest / premium / credit_width / other
    detail    TEXT,
    spread_pct REAL, oi REAL, premium REAL, cw REAL
);
CREATE INDEX IF NOT EXISTS ix_fills_book   ON fills(book, status);
CREATE INDEX IF NOT EXISTS ix_rej_date     ON rejections(trade_date, book);
"""


def _conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB, timeout=10)
    c.executescript(SCHEMA)
    return c


def record_entry(book, pos, spread_pct=None):
    """Store a new paper position. Credit and c/w come straight off the position dict, so they are
    on the same MID basis as both backtest windows. `spread_pct` is the short leg's live bid-ask,
    which the books already compute for the liquidity gate and currently discard."""
    try:
        qty = int(pos.get("qty") or 0)
        width = float(pos.get("width_pts") or 0)
        credit = pos.get("credit")
        with _conn() as c:
            c.execute("""INSERT OR REPLACE INTO fills
                (id, book, symbol, side, entry_ts, entry_date, expiry, short_strike, long_strike,
                 width, lot, num_lots, qty, credit, cw, spread_pct, margin_rs, status, advisory)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'OPEN',?)""",
                (pos.get("id"), book, pos.get("symbol"), pos.get("side"),
                 datetime.now().isoformat(timespec="seconds"), pos.get("entry_date"), pos.get("expiry"),
                 pos.get("short_strike"), pos.get("long_strike"), width,
                 pos.get("lot"), pos.get("num_lots"), qty, credit,
                 pos.get("credit_width"), spread_pct,
                 ((width - (credit or 0)) * qty) if width else None,
                 1 if pos.get("advisory") else 0))
    except Exception as e:
        logger.warning(f"forward_record.record_entry: {e}")


def record_exit(pos_id, reason, exit_cost=None, pnl_rs=None):
    """Close a stored position. P&L on mids, same basis as entry."""
    try:
        with _conn() as c:
            r = c.execute("SELECT credit, qty FROM fills WHERE id=?", (pos_id,)).fetchone()
            if not r:
                return
            credit, qty = r[0], (r[1] or 0)
            if pnl_rs is None and credit is not None and exit_cost is not None:
                pnl_rs = (credit - exit_cost) * qty
            c.execute("""UPDATE fills SET exit_ts=?, exit_date=?, exit_reason=?,
                         exit_cost=?, pnl_rs=?, status='CLOSED' WHERE id=?""",
                      (datetime.now().isoformat(timespec="seconds"),
                       datetime.now().date().isoformat(), reason, exit_cost, pnl_rs, pos_id))
    except Exception as e:
        logger.warning(f"forward_record.record_exit: {e}")


def record_rejection(book, symbol, reason, detail="", spread_pct=None, oi=None, premium=None, cw=None):
    """A candidate the live gate blocked. These leave no trace anywhere else, so the fraction of
    backtest trades that are actually takeable is otherwise unmeasured. On 17-Aug-2026 the live gates
    rejected 10 of 17 candidates; nothing recorded it."""
    try:
        now = datetime.now()
        with _conn() as c:
            c.execute("""INSERT INTO rejections
                (ts, trade_date, book, symbol, reason, detail, spread_pct, oi, premium, cw)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (now.isoformat(timespec="seconds"), now.date().isoformat(), book, symbol,
                 reason, str(detail)[:200], spread_pct, oi, premium, cw))
    except Exception as e:
        logger.warning(f"forward_record.record_rejection: {e}")


def summary():
    """Counts, P&L, and the two diagnostics the backtest cannot produce:
    where real spreads sit, and what fraction of candidates the live gates actually take."""
    try:
        with _conn() as c:
            out = {"closed": 0, "open": 0}
            for st, n in c.execute("SELECT status, COUNT(*) FROM fills GROUP BY status"):
                out["closed" if st == "CLOSED" else "open"] = n
            r = c.execute("""SELECT COUNT(*), SUM(pnl_rs), SUM(margin_rs),
                                    SUM(CASE WHEN pnl_rs>0 THEN 1 ELSE 0 END)
                             FROM fills WHERE status='CLOSED' AND pnl_rs IS NOT NULL
                               AND advisory=0""").fetchone()
            n, pnl, mgn, wins = r[0] or 0, r[1] or 0.0, r[2] or 0.0, r[3] or 0
            out.update(n=n, pnl_rs=pnl, win_pct=(100.0*wins/n if n else None),
                       rom_pct=(100.0*pnl/mgn if mgn else None))
            out["spread_med"] = c.execute(
                "SELECT AVG(spread_pct) FROM fills WHERE spread_pct IS NOT NULL").fetchone()[0]
            out["rejections"] = c.execute("SELECT COUNT(*) FROM rejections").fetchone()[0]
            out["rej_by_reason"] = dict(c.execute(
                "SELECT reason, COUNT(*) FROM rejections GROUP BY reason").fetchall())
            taken = out["closed"] + out["open"]
            tot = taken + out["rejections"]
            out["take_rate_pct"] = (100.0 * taken / tot) if tot else None
            return out
    except Exception as e:
        logger.warning(f"forward_record.summary: {e}")
        return {}


BOOK_FILES = {"v2": "stock_credit_v2_positions.json",
              "v1": "stock_credit_positions.json",
              "v0": "stock_credit_v0_positions.json",
              "0DTE-NIFTY": "zero_dte_positions.json",
              "0DTE-SENSEX": "sensex_dte_positions.json"}


def sync():
    """Reconcile the DB against the JSON books. Idempotent, so it is safe to run every cycle.

    Positions close down several paths - take-profit, stop, and expiry settlement - and hooking each
    site would mean three chances to miss one. Reconciling instead catches every path, including any
    added later, and doubles as the backfill for trades that predate this table. Entry rows are still
    written by record_entry() at signal time because that is the only moment `spread_pct` exists.
    """
    import json as _json
    n_new = n_closed = 0
    try:
        with _conn() as c:
            have = {r[0]: r[1] for r in c.execute("SELECT id, status FROM fills")}
            for book, fn in BOOK_FILES.items():
                fp = os.path.join(os.path.dirname(DB), fn)
                if not os.path.exists(fp):
                    continue
                try:
                    rows = _json.load(open(fp))
                except Exception:
                    continue
                for p in rows:
                    pid, st = p.get("id"), (p.get("status") or "").upper()
                    if not pid:
                        continue
                    closed = st not in ("OPEN", "")
                    if pid not in have:
                        qty = int(p.get("qty") or 0)
                        width = float(p.get("width_pts") or 0)
                        credit = p.get("credit")
                        c.execute("""INSERT INTO fills
                            (id, book, symbol, side, entry_ts, entry_date, expiry, short_strike,
                             long_strike, width, lot, num_lots, qty, credit, cw, margin_rs, status,
                             advisory)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (pid, book, p.get("symbol"), p.get("side"),
                             p.get("entry_date"), p.get("entry_date"), p.get("expiry"),
                             p.get("short_strike"), p.get("long_strike"), width, p.get("lot"),
                             p.get("num_lots"), qty, credit, p.get("credit_width"),
                             ((width - (credit or 0)) * qty) if width else None,
                             "CLOSED" if closed else "OPEN", 1 if p.get("advisory") else 0))
                        n_new += 1
                        have[pid] = "CLOSED" if closed else "OPEN"
                    if closed and have.get(pid) != "CLOSED":
                        ec = p.get("exit_cost")
                        qty = int(p.get("qty") or 0)
                        pnl = (p.get("pnl_pts") or 0) * qty
                        c.execute("""UPDATE fills SET exit_date=?, exit_reason=?, exit_cost=?,
                                     pnl_rs=?, status='CLOSED' WHERE id=?""",
                                  (p.get("closed_date"), st, ec, pnl, pid))
                        n_closed += 1
                    elif closed:
                        # already CLOSED in the DB, but refresh P&L in case the book re-marked it
                        c.execute("UPDATE fills SET pnl_rs=?, exit_cost=? WHERE id=? AND status='CLOSED'",
                                  ((p.get("pnl_pts") or 0) * int(p.get("qty") or 0),
                                   p.get("exit_cost"), pid))
            # ORPHAN GUARD (audit 24-Aug-2026): a fill inserted at entry whose position JSON was
            # never saved (crash between record_entry and _save_book) would sit OPEN forever. Any
            # OPEN fill older than a day with no JSON counterpart is marked ORPHAN, out of every
            # headline query, loudly.
            known = set()
            for _, fn in BOOK_FILES.items():
                fp = os.path.join(os.path.dirname(DB), fn)
                try:
                    known |= {q.get("id") for q in _json.load(open(fp))}
                except Exception:
                    pass
            for (oid,) in c.execute("""SELECT id FROM fills WHERE status='OPEN'
                                       AND entry_ts < datetime('now','-1 day')""").fetchall():
                if oid not in known:
                    c.execute("UPDATE fills SET status='ORPHAN' WHERE id=?", (oid,))
                    logger.warning(f"forward_record: fill {oid} has no book counterpart — marked ORPHAN")
    except Exception as e:
        logger.warning(f"forward_record.sync: {e}")
    return n_new, n_closed
