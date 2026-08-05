"""
CAS NIFTY AND SENSEX DATA — daily close-window recorder.

NSE's Aug-2026 session change split the close in two: cash/index prints stop at 15:30, but
equity derivatives keep trading to 15:40 (CAS). That last 25 minutes is now its own regime —
the index goes dark while option premiums keep moving — and nothing in the engine was
capturing it. This records it, every session, so it can be studied later.

Per session, per index (NIFTY, SENSEX) it stores:
  * index behaviour into the close (OHLC, prev close, 15:15 spot, close-vs-high, last-60m move)
  * the ATM CALL and ATM PUT for the nearest expiry on/after the day, picked off the 15:15 spot
  * marks on those premiums at 15:15 / 15:30 / 15:36 / close, plus the 15:15-15:40 high/low
  * gross P&L per 1 lot for a 15:15 buy exited at each of those marks
  * traded volume before and after 15:30 (the liquidity question for a post-15:30 exit)

Fill convention: a mark at time T is that minute bar's OPEN (what you'd pay entering at T).
The closing mark is the last bar's CLOSE. India VIX at close is stored alongside, because
premium decay in this window tracks IV, not just spot.

Writes to BOTH:
  * data/engine.db          -> tables cas_index_close, cas_option_close (idempotent upsert)
  * studies/CAS_NIFTY_SENSEX_DATA/  -> cas_index.csv, cas_options.csv, raw/<date>_<idx>.json

Run:  python -m engine.cas_recorder              # today
      python -m engine.cas_recorder 2026-08-03   # one past day
      python -m engine.cas_recorder 2026-07-01 2026-08-05   # backfill a range
"""
import os
import json
import time
import sqlite3
import logging
from datetime import date, datetime, timedelta

import pandas as pd

from engine.config import IST, DATA_DIR
from engine.data_fetcher import fetch_upstox_historical, fetch_upstox_intraday
from engine.instruments import to_instrument_key
from engine import expired_options as EO
from engine import options as OPT
from engine import dte_multi as DM

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(DATA_DIR, "engine.db")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDY_DIR = os.path.join(ROOT, "studies", "CAS_NIFTY_SENSEX_DATA")
RAW_DIR = os.path.join(STUDY_DIR, "raw")

INDICES = ["NIFTY", "SENSEX"]
ENTRY = (15, 15)          # entry / ATM reference
MARKS = {"1530": (15, 30), "1536": (15, 36)}
WINDOW_START = (15, 0)    # raw series saved from here

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cas_index_close (
    date          TEXT,
    idx           TEXT,
    open          REAL,
    high          REAL,
    low           REAL,
    close         REAL,
    prev_close    REAL,
    chg_pct       REAL,
    spot_1515     REAL,
    mv_1515_close REAL,
    close_vs_high REAL,
    mv_last60     REAL,
    vix_close     REAL,
    last_print    TEXT,
    recorded_at   TEXT,
    PRIMARY KEY (date, idx)
);
CREATE TABLE IF NOT EXISTS cas_option_close (
    date            TEXT,
    idx             TEXT,
    opt_type        TEXT,
    strike          REAL,
    expiry          TEXT,
    dte             INTEGER,
    lot             INTEGER,
    instrument_key  TEXT,
    spot_1515       REAL,
    entry_1515      REAL,
    p_1530          REAL,
    p_1536          REAL,
    p_close         REAL,
    hi_window       REAL,
    lo_window       REAL,
    pnl_1530        REAL,
    pnl_1536        REAL,
    pnl_close       REAL,
    vol_1515_1530   REAL,
    vol_post_1530   REAL,
    last_print      TEXT,
    src             TEXT,
    recorded_at     TEXT,
    PRIMARY KEY (date, idx, opt_type)
);
CREATE INDEX IF NOT EXISTS idx_cas_idx_date ON cas_index_close(date);
CREATE INDEX IF NOT EXISTS idx_cas_opt_date ON cas_option_close(date);
"""


def _conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.executescript(_SCHEMA)
    return c


# ── helpers ───────────────────────────────────────────────────────────────────

def _today():
    return datetime.now(IST).date()


def _mins(df):
    return df.index.hour * 60 + df.index.minute


def _bar(df, hm):
    """The minute bar starting at (h, m), or None."""
    s = df[_mins(df) == hm[0] * 60 + hm[1]]
    return s.iloc[0] if len(s) else None


def _open_at(df, hm):
    b = _bar(df, hm)
    return round(float(b.Open), 2) if b is not None else None


def _hist_day(ticker, day, interval=1):
    """Historical minute bars for ONE past session.

    Asks for day..day+1 and filters, rather than from=day&to=day. The endpoint returns
    NOTHING for from==to on the most recently published session for some instruments
    (reproduced on NIFTY for 5-Aug when queried on 6-Aug; SENSEX served the same request
    fine), so a same-day range silently loses yesterday on backfill. The wider range is
    served reliably; the filter drops the extra day it brings back."""
    df = fetch_upstox_historical(ticker, unit="minutes", interval=interval,
                                 from_date=day.isoformat(),
                                 to_date=(day + timedelta(days=1)).isoformat())
    return df[df.index.date == day] if not df.empty else df


def _index_1min(ticker, day):
    """1-min index bars. Same-day needs the intraday endpoint — the historical feed has no
    same-session data (the stale-bar trap documented in HANDOFF.md). Note the 1-min and
    5-min historical feeds also lag ~1 session; 15-min and coarser publish sooner."""
    if day == _today():
        return fetch_upstox_intraday(ticker, interval=1)
    return _hist_day(ticker, day, interval=1)


def _prev_close(ticker, day):
    daily = fetch_upstox_historical(ticker, unit="days", interval=1,
                                    from_date=(day - timedelta(days=20)).isoformat(),
                                    to_date=day.isoformat())
    if daily.empty:
        return None
    prior = daily[daily.index.date < day]
    return round(float(prior.Close.iloc[-1]), 2) if len(prior) else None


def _vix_close(day):
    v = fetch_upstox_intraday("VIX", interval=1) if day == _today() else _hist_day("VIX", day, 1)
    return round(float(v.Close.iloc[-1]), 2) if not v.empty else None


def _master(ticker, opt_type):
    """Live contract master — NSE_FO for NIFTY, the separate BSE master for SENSEX."""
    if ticker == "SENSEX":
        rows = DM._bse_sensex_options()
    else:
        rows = OPT._load_index().get(to_instrument_key(ticker), [])
    return [c for c in rows if c["type"] == opt_type]


_EXP_CACHE = {}


def _expired_expiries(ticker):
    """Expiry dates the expired-instruments API knows about. Rate-limits to [] silently,
    so retry — an empty list here is indistinguishable from 'nothing expired' and that is
    what makes the failure below silent."""
    if ticker in _EXP_CACHE:
        return _EXP_CACHE[ticker]
    for _ in range(5):
        e = EO.get_expiries(ticker)
        if e:
            _EXP_CACHE[ticker] = e
            return e
        time.sleep(2)
    return []


def _resolve_atm(ticker, spot, day, opt_type):
    """ATM contract for the nearest expiry on/after `day`, chosen off the 15:15 spot.

    Must consult BOTH masters. The live master drops contracts once they expire — and not
    immediately, but some days later — so resolving a backfill off it alone silently picks a
    LATER expiry and records the wrong instrument. Reproduced 6-Aug: backfilling 4-Aug NIFTY
    resolved to the 11-Aug weekly (entry 182.05) instead of the 4-Aug 0DTE (entry 75.55),
    overwriting a correct row. The answer therefore depends on WHEN you backfill unless the
    expired list is consulted."""
    cands = []
    fut = [e for e in _expired_expiries(ticker) if e >= day.isoformat()]
    if fut:
        cands.append(date.fromisoformat(fut[0]))
    chain = _master(ticker, opt_type)
    live = sorted({datetime.fromtimestamp(c["expiry"] / 1000).date() for c in chain
                   if datetime.fromtimestamp(c["expiry"] / 1000).date() >= day})
    if live:
        cands.append(live[0])
    if not cands:
        return None
    expiry = min(cands)

    if expiry.isoformat() in _expired_expiries(ticker):
        for _ in range(4):
            cs = EO.get_contracts(ticker, expiry.isoformat())
            if cs:
                break
            time.sleep(2)
        else:
            return None
        legs = [c for c in cs if c.get("instrument_type") == opt_type]
        if not legs:
            return None
        c = min(legs, key=lambda x: abs(float(x["strike_price"]) - spot))
        return dict(key=c["instrument_key"], strike=float(c["strike_price"]),
                    lot=int(c.get("lot_size") or 0), expiry=expiry)

    ms_day = expiry
    same = [c for c in chain if datetime.fromtimestamp(c["expiry"] / 1000).date() == ms_day]
    if not same:
        return None
    c = min(same, key=lambda x: abs(x["strike"] - spot))
    return dict(key=c["key"], strike=float(c["strike"]), lot=int(c.get("lot") or 0),
                expiry=expiry)


def _expired_series(ticker, opt, day):
    """Premiums for a contract that has already expired, via the expired-instruments API.
    That API rate-limits hard, so both steps retry."""
    contracts = []
    for _ in range(4):
        contracts = EO.get_contracts(ticker, opt["expiry"].isoformat())
        if contracts:
            break
        time.sleep(2)
    hit = next((c for c in contracts
                if c.get("instrument_type") == opt["opt_type"]
                and float(c.get("strike_price", 0)) == opt["strike"]), None)
    if not hit:
        return pd.DataFrame(), None, opt["lot"]
    lot = int(hit.get("lot_size") or opt["lot"])
    for _ in range(3):
        df = EO.fetch_expired_premium_5min(hit["instrument_key"], day, interval="1minute")
        if not df.empty:
            return df, hit["instrument_key"], lot
        time.sleep(2)
    return pd.DataFrame(), hit["instrument_key"], lot


def _premium_series(ticker, opt, day):
    """1-min premiums, picking the endpoint that actually serves this contract+day.
    Returns (df, source, instrument_key, lot)."""
    if opt["expiry"] < _today():
        df, key, lot = _expired_series(ticker, opt, day)
        return df, "expired-api", key or opt["key"], lot
    if day == _today():
        df = fetch_upstox_intraday(opt["key"], interval=1)
        if not df.empty:
            return df, "intraday", opt["key"], opt["lot"]
        # a contract expiring today can drop out of the intraday feed after the close
        df, key, lot = _expired_series(ticker, opt, day)
        return df, "expired-api", key or opt["key"], lot
    df = _hist_day(opt["key"], day, interval=1)
    if not df.empty:
        return df, "historical", opt["key"], opt["lot"]
    df, key, lot = _expired_series(ticker, opt, day)
    return df, "expired-api", key or opt["key"], lot


# ── recording ─────────────────────────────────────────────────────────────────

def record_index(ticker, day, idf):
    o, h = float(idf.Open.iloc[0]), float(idf.High.max())
    l, c = float(idf.Low.min()), float(idf.Close.iloc[-1])
    spot = _open_at(idf, ENTRY)
    b1430 = _bar(idf, (14, 30))
    prev = _prev_close(ticker, day)
    return dict(
        date=day.isoformat(), idx=ticker,
        open=round(o, 2), high=round(h, 2), low=round(l, 2), close=round(c, 2),
        prev_close=prev,
        chg_pct=round((c / prev - 1) * 100, 3) if prev else None,
        spot_1515=spot,
        mv_1515_close=round(c - spot, 2) if spot else None,
        close_vs_high=round(c - h, 2),
        mv_last60=round(c - float(b1430.Open), 2) if b1430 is not None else None,
        vix_close=_vix_close(day),
        last_print=str(idf.index[-1].time()),
        recorded_at=datetime.now(IST).isoformat(timespec="seconds"),
    )


def record_option(ticker, day, spot, opt_type):
    opt = _resolve_atm(ticker, spot, day, opt_type)
    if not opt:
        logger.warning(f"CAS {ticker} {day} {opt_type}: no contract resolved")
        return None, None
    opt["opt_type"] = opt_type
    pdf, src, key, lot = _premium_series(ticker, opt, day)
    if pdf.empty:
        logger.warning(f"CAS {ticker} {day} {opt_type} {opt['strike']:.0f}: no premium data ({src})")
        return None, None

    entry = _open_at(pdf, ENTRY)
    if entry is None:
        logger.warning(f"CAS {ticker} {day} {opt_type}: no 15:15 bar")
        return None, None

    marks = {k: _open_at(pdf, hm) for k, hm in MARKS.items()}
    p_close = round(float(pdf.Close.iloc[-1]), 2)
    win = pdf[_mins(pdf) >= ENTRY[0] * 60 + ENTRY[1]]
    hi, lo = round(float(win.High.max()), 2), round(float(win.Low.min()), 2)
    pre = pdf[(_mins(pdf) >= ENTRY[0] * 60 + ENTRY[1]) & (_mins(pdf) < 15 * 60 + 30)]
    post = pdf[_mins(pdf) >= 15 * 60 + 30]
    pnl = lambda p: round((p - entry) * lot, 2) if p is not None and lot else None

    row = dict(
        date=day.isoformat(), idx=ticker, opt_type=opt_type,
        strike=opt["strike"], expiry=opt["expiry"].isoformat(),
        dte=(opt["expiry"] - day).days, lot=lot, instrument_key=key,
        spot_1515=spot, entry_1515=entry,
        p_1530=marks["1530"], p_1536=marks["1536"], p_close=p_close,
        hi_window=hi, lo_window=lo,
        pnl_1530=pnl(marks["1530"]), pnl_1536=pnl(marks["1536"]), pnl_close=pnl(p_close),
        vol_1515_1530=round(float(pre.Volume.sum()), 0),
        vol_post_1530=round(float(post.Volume.sum()), 0),
        last_print=str(pdf.index[-1].time()), src=src,
        recorded_at=datetime.now(IST).isoformat(timespec="seconds"),
    )
    return row, pdf


def _series_json(df):
    w = df[_mins(df) >= WINDOW_START[0] * 60 + WINDOW_START[1]]
    return [dict(t=str(ts.time()), o=float(r.Open), h=float(r.High),
                 l=float(r.Low), c=float(r.Close), v=float(r.Volume))
            for ts, r in w.iterrows()]


def _upsert(conn, table, rows):
    if not rows:
        return 0
    cols = list(rows[0].keys())
    q = (f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) "
         f"VALUES ({','.join('?' * len(cols))})")
    conn.executemany(q, [[r[c] for c in cols] for r in rows])
    conn.commit()
    return len(rows)


def _dump_csv(conn):
    os.makedirs(STUDY_DIR, exist_ok=True)
    for table, name in (("cas_index_close", "cas_index.csv"),
                        ("cas_option_close", "cas_options.csv")):
        df = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY date, idx", conn)
        df.to_csv(os.path.join(STUDY_DIR, name), index=False)


def record_day(day, conn=None):
    """Record one session. Returns (index_rows, option_rows)."""
    own = conn is None
    conn = conn or _conn()
    irows, orows = [], []
    try:
        for ticker in INDICES:
            idf = _index_1min(ticker, day)
            if idf.empty:
                logger.info(f"CAS {ticker} {day}: no session data (holiday / not yet traded)")
                continue
            irow = record_index(ticker, day, idf)
            irows.append(irow)

            raw = {"date": day.isoformat(), "index": ticker, "index_1min": _series_json(idf)}
            for opt_type in ("CE", "PE"):
                orow, pdf = record_option(ticker, day, irow["spot_1515"], opt_type)
                if orow:
                    orows.append(orow)
                    raw[f"{opt_type}_{int(orow['strike'])}_1min"] = _series_json(pdf)

            os.makedirs(RAW_DIR, exist_ok=True)
            with open(os.path.join(RAW_DIR, f"{day.isoformat()}_{ticker}.json"), "w") as f:
                json.dump(raw, f, indent=1)

        _upsert(conn, "cas_index_close", irows)
        _upsert(conn, "cas_option_close", orows)
        _dump_csv(conn)
    finally:
        if own:
            conn.close()
    logger.info(f"CAS {day}: {len(irows)} index rows, {len(orows)} option rows")
    return irows, orows


def record_range(start, end):
    conn = _conn()
    try:
        d, total = start, (0, 0)
        while d <= end:
            if d.weekday() < 5:
                i, o = record_day(d, conn)
                total = (total[0] + len(i), total[1] + len(o))
            d += timedelta(days=1)
    finally:
        conn.close()
    return total


def main():
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    args = sys.argv[1:]
    if len(args) == 2:
        n = record_range(date.fromisoformat(args[0]), date.fromisoformat(args[1]))
        print(f"recorded {n[0]} index rows, {n[1]} option rows")
    else:
        day = date.fromisoformat(args[0]) if args else _today()
        i, o = record_day(day)
        for r in i:
            print(f"{r['idx']:7s} {r['date']} close {r['close']:>10.2f} "
                  f"({r['chg_pct']:+.2f}%)  15:15->close {r['mv_1515_close']:+.1f}")
        for r in o:
            print(f"{r['idx']:7s} {r['opt_type']} {int(r['strike'])} {r['dte']}DTE  "
                  f"entry {r['entry_1515']:>7.2f} -> 15:36 {r['p_1536']}  "
                  f"P&L/lot {r['pnl_1536']:+,.0f}")


if __name__ == "__main__":
    main()
