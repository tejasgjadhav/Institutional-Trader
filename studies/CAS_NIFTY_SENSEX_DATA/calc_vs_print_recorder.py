"""Daily calc-vs-print recorder.

After each close, reconstruct NIFTY and SENSEX from their constituents (per-day least-squares
weights, fit 09:20-15:09) and record, per index:
    print@15:15 · calc@15:15 · calc@15:18 · official close · auction gap · fit RMSE · timestamp

Writes engine.db table `cas_calc_vs_print` (idempotent upsert on date+idx) and dumps
`cas_calc_vs_print.csv` beside this file. The UI's summary table reads this via /summary.

Run:  python studies/CAS_NIFTY_SENSEX_DATA/calc_vs_print_recorder.py              # today
      python studies/CAS_NIFTY_SENSEX_DATA/calc_vs_print_recorder.py 2026-08-03   # one day
      python studies/CAS_NIFTY_SENSEX_DATA/calc_vs_print_recorder.py 2026-08-03 2026-08-05
Scheduled: chained after engine.cas_recorder in com.sayali.cas-recorder (15:50 + 16:20 retry).
"""
import os, sys, json, sqlite3
from datetime import date, datetime, timedelta

PROJECT = os.path.expanduser("~/files/institutional-trader")
HERE = os.path.join(PROJECT, "studies", "CAS_NIFTY_SENSEX_DATA")
os.chdir(PROJECT)
sys.path.insert(0, PROJECT)

import numpy as np
import pandas as pd
from engine.config import IST, DATA_DIR
from engine.data_fetcher import fetch_upstox_historical, fetch_upstox_intraday
from engine.instruments import to_instrument_key

DB = os.path.join(DATA_DIR, "engine.db")
BKEY = json.load(open(os.path.join(HERE, "bse_keys.json")))

SENSEX30 = """ADANIPORTS ASIANPAINT AXISBANK BAJFINANCE BAJAJFINSV BEL BHARTIARTL ETERNAL
HCLTECH HDFCBANK HINDUNILVR ICICIBANK INDIGO INFY ITC KOTAKBANK LT M&M MARUTI NTPC
POWERGRID RELIANCE SBIN SUNPHARMA TCS TATASTEEL TECHM TITAN TRENT ULTRACEMCO""".split()
NIFTY50 = """ADANIENT ADANIPORTS APOLLOHOSP ASIANPAINT AXISBANK BAJAJ-AUTO BAJFINANCE
BAJAJFINSV BEL BHARTIARTL CIPLA COALINDIA DRREDDY EICHERMOT ETERNAL GRASIM HCLTECH
HDFCBANK HDFCLIFE HINDALCO HINDUNILVR ICICIBANK INDIGO INFY ITC JIOFIN JSWSTEEL
KOTAKBANK LT M&M MARUTI MAXHEALTH NESTLEIND NTPC ONGC POWERGRID RELIANCE SBILIFE
SHRIRAMFIN SBIN SUNPHARMA TCS TATACONSUM TMPV TATASTEEL TECHM TITAN TRENT ULTRACEMCO
WIPRO""".split()
CFG = {"SENSEX": (SENSEX30, lambda s: BKEY.get(s), "BSE_INDEX|SENSEX"),
       "NIFTY": (NIFTY50, to_instrument_key, "NSE_INDEX|Nifty 50")}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cas_calc_vs_print (
    date           TEXT,
    idx            TEXT,
    print_1515     REAL,
    calc_1515      REAL,
    calc_1518      REAL,
    official_close REAL,
    auction_gap    REAL,
    fit_rmse       REAL,
    n_stocks       INTEGER,
    recorded_at    TEXT,
    PRIMARY KEY (date, idx)
);
"""


def _minutes(key, day):
    if day == datetime.now(IST).date():
        return fetch_upstox_intraday(key, interval=1)
    m = fetch_upstox_historical(key, unit="minutes", interval=1,
                                from_date=day.isoformat(),
                                to_date=(day + timedelta(days=1)).isoformat())
    return m[m.index.date == day] if not m.empty else m


def _official_close(key, day):
    d = fetch_upstox_historical(key, unit="days", interval=1,
                                from_date=(day - timedelta(days=5)).isoformat(),
                                to_date=(day + timedelta(days=1)).isoformat())
    r = d[d.index.date == day] if not d.empty else d
    return float(r.Close.iloc[0]) if len(r) else None


def record_one(name, day):
    members, keyfn, idx_key = CFG[name]
    px = {}
    for s in members:
        k = keyfn(s)
        if not k:
            continue
        m = _minutes(k, day)
        if not m.empty:
            px[s] = m.Close
    im = _minutes(idx_key, day)
    if im.empty or len(px) < len(members) - 2:
        print(f"  {name} {day}: insufficient data ({len(px)} stocks, idx {len(im)} bars)")
        return None
    P = pd.DataFrame(px).dropna()
    y = im.Close.reindex(P.index).dropna()
    P = P.reindex(y.index)
    mins = P.index.hour * 60 + P.index.minute
    fm = (mins >= 9 * 60 + 20) & (mins <= 15 * 60 + 9)
    if fm.sum() < 60:
        print(f"  {name} {day}: only {fm.sum()} fit bars — skipping")
        return None
    w, *_ = np.linalg.lstsq(P[fm].values, y[fm].values, rcond=None)
    pred = P.values @ w
    rmse = float(np.sqrt(((pred[fm] - y.values[fm]) ** 2).mean()))

    def at(hm):
        b = mins == hm[0] * 60 + hm[1]
        return (float(pred[b][0]), float(y.values[b][0])) if b.any() else (None, None)

    c1515, p1515 = at((15, 15))
    c1518, _ = at((15, 18))
    off = _official_close(idx_key, day)
    if c1518 is None or off is None:
        print(f"  {name} {day}: missing 15:18 bar or official close")
        return None
    return dict(date=day.isoformat(), idx=name,
                print_1515=round(p1515, 2), calc_1515=round(c1515, 2),
                calc_1518=round(c1518, 2), official_close=round(off, 2),
                auction_gap=round(off - c1518, 2), fit_rmse=round(rmse, 2),
                n_stocks=len(P.columns),
                recorded_at=datetime.now(IST).isoformat(timespec="seconds"))


def record_day(day):
    conn = sqlite3.connect(DB, timeout=10)
    conn.executescript(_SCHEMA)
    rows = []
    for name in ("SENSEX", "NIFTY"):
        r = record_one(name, day)
        if r:
            rows.append(r)
            cols = list(r.keys())
            conn.execute(f"INSERT OR REPLACE INTO cas_calc_vs_print ({','.join(cols)}) "
                         f"VALUES ({','.join('?' * len(cols))})", [r[c] for c in cols])
    conn.commit()
    df = pd.read_sql_query("SELECT * FROM cas_calc_vs_print ORDER BY date, idx", conn)
    df.to_csv(os.path.join(HERE, "cas_calc_vs_print.csv"), index=False)
    conn.close()
    for r in rows:
        print(f"  {r['idx']:7s} {r['date']}  print1515 {r['print_1515']:>10.2f}  "
              f"calc1515 {r['calc_1515']:>10.2f}  close {r['official_close']:>10.2f}  "
              f"gap {r['auction_gap']:>+8.2f}  rmse {r['fit_rmse']}")
    return rows


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 2:
        d = date.fromisoformat(args[0])
        while d <= date.fromisoformat(args[1]):
            if d.weekday() < 5:
                print(d)
                record_day(d)
            d += timedelta(days=1)
    else:
        day = date.fromisoformat(args[0]) if args else datetime.now(IST).date()
        record_day(day)
