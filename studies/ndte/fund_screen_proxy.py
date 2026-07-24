"""GOAL-LOOP fast PROXY: does a FUNDAMENTAL quality screen improve the stock-fade edge?
The fade (bear-call on up-break / bull-put on down-break) WINS when the breakout does NOT
follow through — the stock reverts/stalls. This tests that on the UNDERLYING (daily prices +
yfinance fundamentals) — a fast proxy for the option P&L (which needs the heavy premium fetch,
queued separately). Metric: after a Donchian-5 breakout, "fade-win proxy" = the stock did NOT
extend past the ~2-OTM short strike (~+3.5% for up-break / −3.5% for down-break) at any point in
the next 20 trading days (≈1 month). Compare QUALITY (ROE>12% & D/E<1.2 & +ve earnings growth)
vs NON-QUALITY. Out: prints the two hit rates + n. PROXY not P&L — flag as such.
"""
import sys, warnings; sys.path.insert(0, "/Users/sayali/files/institutional-trader")
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from datetime import date, timedelta
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical
import yfinance as yf
import concurrent.futures, threading

START = date(2024, 10, 1); DC = 5; REENTRY = 3; HORIZON = 20; OTM = 0.035
LK = threading.Lock(); res = {"Q": [], "N": []}; DONE = [0]

def quality(sym0):
    try:
        info = yf.Ticker(sym0).info
        roe = info.get("returnOnEquity"); de = info.get("debtToEquity"); eg = info.get("earningsQuarterlyGrowth")
        if roe is None: return None
        de = (de or 0) / 100.0 if de and de > 5 else (de or 0)   # yf sometimes reports D/E as %
        return (roe > 0.12) and (de < 1.2) and ((eg or 0) >= 0)
    except Exception:
        return None

def do_stock(sym0):
    try:
        q = quality(sym0)
        if q is None:
            with LK: DONE[0] += 1
            return
        u = fetch_upstox_historical(sym0, unit="days", interval=1, from_date="2024-06-01", to_date=date.today().isoformat())
        if u is None or u.empty or len(u) < 40:
            with LK: DONE[0] += 1
            return
        u = u.sort_index(); H = u["High"].values; L = u["Low"].values; C = u["Close"].values; idx = u.index
        hi = u["High"].rolling(DC).max().shift(1).values; lo = u["Low"].rolling(DC).min().shift(1).values
        last = {}; wins = []
        for i in range(DC + 1, len(u) - HORIZON):
            d = idx[i].date()
            if d < START: continue
            c = C[i]; typ = None
            if c > hi[i]: typ = "UP"
            elif c < lo[i]: typ = "DN"
            else: continue
            if last.get(typ) and (d - last[typ]).days < REENTRY: continue
            last[typ] = d
            fwd = C[i+1:i+1+HORIZON]                    # next 20 closes
            if typ == "UP":  win = 1 if fwd.max() <= c * (1 + OTM) else 0   # never breached short call
            else:            win = 1 if fwd.min() >= c * (1 - OTM) else 0   # never breached short put
            wins.append(win)
        with LK:
            res["Q" if q else "N"].extend(wins)
    except Exception as e:
        with LK: print(f" !! {sym0}: {e}", flush=True)
    with LK:
        DONE[0] += 1
        if DONE[0] % 20 == 0: print(f"  ...{DONE[0]}/{len(UNIVERSE)}", flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(do_stock, UNIVERSE))

print("\n=== FUNDAMENTAL SCREEN — underlying fade-win PROXY (D5, Oct'24->date, 20-day horizon) ===")
for k, lab in (("Q", "QUALITY (ROE>12%, D/E<1.2, +ve earnings)"), ("N", "NON-QUALITY")):
    w = res[k]
    if w: print(f"  {lab:44s} n={len(w):4d}  fade-win proxy {np.mean(w)*100:.1f}%")
    else: print(f"  {lab:44s} n=0")
allw = res["Q"] + res["N"]
if allw: print(f"  {'ALL (baseline)':44s} n={len(allw):4d}  fade-win proxy {np.mean(allw)*100:.1f}%")
print("DONE-FUNDPROXY")
