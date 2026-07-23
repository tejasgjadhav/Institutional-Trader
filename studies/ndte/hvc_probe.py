"""Probe: count v2 UNION and v1 D10 breakouts Oct'24->date to size the intraday fetch.
Underlying-only (cheap) — no option fetches. Out: prints counts + a rough intraday-call budget."""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from datetime import date, timedelta
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical
import concurrent.futures, threading

START = date(2024, 10, 1); REENTRY = 3
UNION_DCS = (5, 10, 15, 20)
LK = threading.Lock()
v2n = [0]; v1n = [0]; done = [0]; nostock = [0]

def do(sym0):
    sym = sym0.replace(".NS", "")
    try:
        u = fetch_upstox_historical(sym0, unit="days", interval=1,
                                    from_date="2024-06-01", to_date=date.today().isoformat())
        if u is None or u.empty or len(u) < 30:
            with LK: nostock[0] += 1; done[0] += 1
            return
        u = u.sort_index()
        # v2 UNION
        rolls = {dc: (u["High"].rolling(dc).max().shift(1), u["Low"].rolling(dc).min().shift(1)) for dc in UNION_DCS}
        last = {}; c2 = 0
        for i in range(max(UNION_DCS) + 1, len(u) - 1):
            day = u.index[i].date()
            if day < START: continue
            c = float(u["Close"].iloc[i]); typ = None
            for dc in UNION_DCS:
                hi, lo = rolls[dc]
                if c > float(hi.iloc[i]): typ = "CE"; break
                if c < float(lo.iloc[i]): typ = "PE"; break
            if typ is None: continue
            if last.get(typ) and (day - last[typ]).days < REENTRY: continue
            last[typ] = day; c2 += 1
        # v1 D10
        hi = u["High"].rolling(10).max().shift(1); lo = u["Low"].rolling(10).min().shift(1); last = {}; c1 = 0
        for i in range(11, len(u) - 1):
            day = u.index[i].date()
            if day < START: continue
            c = float(u["Close"].iloc[i]); typ = None
            if c > float(hi.iloc[i]): typ = "CE"
            elif c < float(lo.iloc[i]): typ = "PE"
            else: continue
            if last.get(typ) and (day - last[typ]).days < REENTRY: continue
            last[typ] = day; c1 += 1
        with LK:
            v2n[0] += c2; v1n[0] += c1; done[0] += 1
    except Exception as e:
        with LK:
            done[0] += 1
            print(f"  !! {sym}: {e}", flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
    list(ex.map(do, UNIVERSE))

print(f"\nstocks ok: {done[0]-nostock[0]}/{len(UNIVERSE)} (no-data: {nostock[0]})")
print(f"v2 UNION breakouts (pre-gate): {v2n[0]}")
print(f"v1 D10   breakouts (pre-gate): {v1n[0]}")
tot = v2n[0] + v1n[0]
print(f"combined breakouts: {tot}")
print(f"~intraday fetch budget: {tot} breakouts x 2 legs = {tot*2} 1-min calls (+ {tot*2} daily leg calls, shared w/ close sim)")
print("DONE-PROBE")
