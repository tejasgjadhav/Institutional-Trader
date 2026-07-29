"""PHASE 1 — cheap screen of the 88 expansion candidates.
For each candidate fetch DAILY underlying (Upstox, 2018-06 -> Sep'24) and count UNION Donchian
(5/10/15/20) breakout-days (raw signal frequency, PRE option-gate) matching stkfade_union.py's
signal logic (close>rolling(dc).max().shift(1)=>CE ; close<rolling(dc).min().shift(1)=>PE ; a
day is one union signal if ANY dc fires). Record last spot + median spot (the c/w>=0.40 gate
structurally favours higher-priced, rich-IV names). Ranks by union signals/mo. Writes
/tmp/expand_phase1.csv for the shortlist step."""
import warnings; warnings.filterwarnings("ignore")
import sys, csv
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import date as _date
from engine.data_fetcher import fetch_upstox_historical

CANDS = [x.strip() for x in open("/tmp/expand_candidates.txt") if x.strip()]
DCS = [5, 10, 15, 20]
FROM, TO = "2018-06-01", "2024-09-30"
# restrict signal counting to the option-backtest window so /mo matches Phase 2
WIN_START = _date(2019, 1, 1)

rows = []
for sym in CANDS:
    try:
        u = fetch_upstox_historical(sym + ".NS", unit="days", interval=1, from_date=FROM, to_date=TO)
    except Exception as e:
        rows.append((sym, "ERR", str(e)[:30], 0, 0, 0.0, 0.0)); continue
    if u is None or u.empty or len(u) < 60:
        rows.append((sym, "NODATA", "", 0, 0, 0.0, 0.0)); continue
    u = u.sort_index()
    sig_days = set()
    for dc in DCS:
        hi = u["High"].rolling(dc).max().shift(1); lo = u["Low"].rolling(dc).min().shift(1)
        for i in range(max(dc, 20), len(u) - 1):
            ts = u.index[i].date()
            if ts < WIN_START: continue
            c = float(u["Close"].iloc[i])
            if c > float(hi.iloc[i]) or c < float(lo.iloc[i]):
                sig_days.add(ts)
    if not sig_days:
        rows.append((sym, "OK", "nosig", 0, 0, float(u["Close"].iloc[-1]), 0.0)); continue
    months = len({(d.year, d.month) for d in sig_days})
    win_slice = u[u.index.map(lambda x: x.date()) >= WIN_START]
    last_spot = float(u["Close"].iloc[-1])
    med_spot = float(win_slice["Close"].median())
    rows.append((sym, "OK", "", len(sig_days), months, last_spot, med_spot))

# sort: OK rows by signals/mo desc
def rate(r):
    return (r[3] / r[4]) if r[4] else 0.0
ok = [r for r in rows if r[1] == "OK" and r[4] > 0]
bad = [r for r in rows if not (r[1] == "OK" and r[4] > 0)]
ok.sort(key=rate, reverse=True)

print(f"{'SYM':<13}{'sig':>5}{'mo':>4}{'/mo':>6}{'lastRs':>10}{'medRs':>10}", flush=True)
for r in ok:
    print(f"{r[0]:<13}{r[3]:>5}{r[4]:>4}{rate(r):>6.1f}{r[5]:>10.0f}{r[6]:>10.0f}", flush=True)
if bad:
    print("\n--- no data / no signal / error ---", flush=True)
    for r in bad:
        print(f"{r[0]:<13}{r[1]} {r[2]}", flush=True)

with open("/tmp/expand_phase1.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["sym","status","note","sig_days","months","sig_per_mo","last_spot","med_spot"])
    for r in ok + bad:
        w.writerow([r[0], r[1], r[2], r[3], r[4], round(rate(r), 2), round(r[5], 1), round(r[6], 1)])
print(f"\nscreened {len(rows)} candidates ({len(ok)} with signals). wrote /tmp/expand_phase1.csv", flush=True)
print("DONE-PHASE1", flush=True)
