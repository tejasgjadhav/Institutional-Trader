"""Win rate for the c/w bands BELOW the deployed gates — 0.25-0.30 and 0.30-0.35 — priced at each
book's own geometry and exit. Information only (user, 2026-08-13); nothing deployed.

The deployed gate is c/w >= 0.40 (v2, v1) and 0.35-0.40 (v0). LOWCW_BAND_RESCUE already showed the
blended 0.30-0.40 band at 81.7% OOS win but only +2.2% ROM, and that its 0.30-0.35 half is dead
(+0.2% IS, -5.2% OOS). 0.25-0.30 has never been measured. Both bands are scored here at:
    v2  short 2-OTM, width 4, TP-50, stop 3x
    v1  short 1-OTM, width 3, TP-40, no stop
    v0  short 2-OTM, width 4, TP-40, no stop
so the answer is per-BOOK, not a blended average that hides which exit does the work.

OOS only (Upstox expired options Oct-24 -> date). The in-sample leg needs the bhavcopy option pickle
rebuilt (~40 min) and is deliberately left for a second pass — the OOS window is the one that has
killed every previous rescue attempt, so it is the cheaper decisive test.
"""
import sys, os, json, warnings, threading, collections, statistics as st
import concurrent.futures as cf
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import date, datetime, timedelta
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical, UPSTOX_BASE
from engine.instruments import encode_key
from engine.expired_options import get_expiries, get_contracts, _get_json as _gj

START = date(2024, 10, 1)
MIN_DTE, REENTRY, MIN_PREM = 10, 3, 50.0
BANDS = {"0.25-0.30": (0.25, 0.30), "0.30-0.35": (0.30, 0.35), "0.35-0.40": (0.35, 0.40)}
BOOKS = {"v2": dict(S=2, W=4, tp=0.50, stop=3.0),
         "v1": dict(S=1, W=3, tp=0.40, stop=None),
         "v0": dict(S=2, W=4, tp=0.40, stop=None)}
CACHE = "/tmp/cw_band_legcache.json"
SUBSET = UNIVERSE[::3]                      # same 38-name slice the other OOS runs used
spf = lambda p: min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0
try: LEGC = json.load(open(CACHE))
except Exception: LEGC = {}
LK = threading.Lock(); rows = []; done = [0]

def leg(key, d0, to):
    ck = f"{key}|{d0}|{to}"
    with LK:
        if ck in LEGC: return LEGC[ck]
    j = _gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}")
    out = []
    if j.get("status") == "success":
        c = j.get("data", {}).get("candles", []) or []
        if c:
            df = pd.DataFrame(c, columns=["ts","O","H","L","C","V","OI"]).sort_values("ts")
            out = [float(x) for x in df["C"]]
    with LK: LEGC[ck] = out
    return out

def work(tk):
    sym = tk.replace(".NS", "")
    try:
        u = fetch_upstox_historical(tk, unit="days", interval=1,
                                    from_date="2024-06-01", to_date=date.today().isoformat())
    except Exception: u = None
    if u is None or u.empty or len(u) < 30:
        with LK: done[0] += 1
        return
    u = u.sort_index()
    cb = {str(i)[:10]: float(u["Close"].loc[i]) for i in u.index}
    HI = {d: u["High"].rolling(d).max().shift(1) for d in (5,10,15,20)}
    LO = {d: u["Low"].rolling(d).min().shift(1) for d in (5,10,15,20)}
    last = {}; mine = []
    for i in range(20, len(u) - 1):
        day = u.index[i].date()
        if day < START: continue
        c = float(u["Close"].iloc[i]); typ = None
        if any(c > float(HI[d].iloc[i]) for d in (5,10,15,20)): typ = "CE"
        elif any(c < float(LO[d].iloc[i]) for d in (5,10,15,20)): typ = "PE"
        else: continue
        if last.get(typ) and (day - last[typ]).days < REENTRY: continue
        try:
            exps = [e for e in get_expiries(sym) if e >= (day + timedelta(days=MIN_DTE)).isoformat()]
            if not exps: continue
            exp = exps[0]
            chain = sorted([x for x in get_contracts(sym, exp) if x["instrument_type"] == typ],
                           key=lambda x: float(x["strike_price"]))
        except Exception: continue
        if len(chain) < 12: continue
        last[typ] = day
        ks = [float(x["strike_price"]) for x in chain]
        atm = min(range(len(ks)), key=lambda j: abs(ks[j] - c))
        d0 = day.isoformat()
        to = min(datetime.fromisoformat(exp).date(), day + timedelta(days=45)).isoformat()
        for bk, cfg in BOOKS.items():
            si = atm + cfg["S"] if typ == "CE" else atm - cfg["S"]
            li = si + cfg["W"] if typ == "CE" else si - cfg["W"]
            if not (0 <= si < len(ks) and 0 <= li < len(ks)): continue
            sp = leg(chain[si]["instrument_key"], d0, to)
            if not sp or sp[0] < MIN_PREM: continue
            lp = leg(chain[li]["instrument_key"], d0, to)
            if not lp: continue
            credit = sp[0] - lp[0]; width = abs(ks[si] - ks[li])
            if credit <= 0 or credit >= width: continue
            cw = credit / width
            band = next((b for b,(lo,hi) in BANDS.items() if lo <= cw < hi), None)
            if band is None: continue
            m = min(len(sp), len(lp)); close = None
            for k in range(1, m):
                cost = sp[k] - lp[k]
                if cost <= credit * (1 - cfg["tp"]):
                    close = max(cost, 0.0) + (sp[k]*spf(sp[k]) + lp[k]*spf(lp[k]))/100.0; break
                if cfg["stop"] and cost >= credit * cfg["stop"]:
                    close = min(cost, width) + (sp[k]*spf(sp[k]) + lp[k]*spf(lp[k]))/100.0; break
            if close is None:
                es = cb.get(exp) or (cb[max(x for x in cb if x <= exp)] if any(x <= exp for x in cb) else c)
                iS = max(0.0, es-ks[si]) if typ=="CE" else max(0.0, ks[si]-es)
                iL = max(0.0, es-ks[li]) if typ=="CE" else max(0.0, ks[li]-es)
                close = min(max(iS-iL, 0.0), width)
            net = (credit - close) - (sp[0]*spf(sp[0]) + lp[0]*spf(lp[0]))/100.0
            mine.append(dict(book=bk, band=band, yr=day.year, net=float(net),
                             margin=float(width-credit), win=int(net > 0), cw=float(cw)))
    with LK:
        rows.extend(mine); done[0] += 1
        if done[0] % 4 == 0:
            print(f"  {done[0]}/{len(SUBSET)} names · {len(rows)} trades", flush=True)
            json.dump(LEGC, open(CACHE, "w"))

with cf.ThreadPoolExecutor(max_workers=6) as ex: list(ex.map(work, SUBSET))
json.dump(LEGC, open(CACHE, "w")); json.dump(rows, open("/tmp/cw_band_rows.json", "w"))
print(f"\n=== c/w BANDS at each book's OWN geometry + exit · OOS Oct-24 -> date ===")
print(f"{'band':<12}{'book':<5}{'n':>5}{'WIN':>8}{'ROM':>9}{'avg credit':>12}{'+ve yrs':>9}")
for band in ("0.25-0.30","0.30-0.35","0.35-0.40"):
    for bk in ("v2","v1","v0"):
        s = [x for x in rows if x["band"] == band and x["book"] == bk]
        if len(s) < 10:
            print(f"{band:<12}{bk:<5}{len(s):>5}   (too few)"); continue
        by = collections.defaultdict(list)
        for x in s: by[x["yr"]].append(x["net"])
        pos = sum(1 for v in by.values() if sum(v) > 0)
        print(f"{band:<12}{bk:<5}{len(s):>5}{sum(x['win'] for x in s)/len(s)*100:>7.1f}%"
              f"{sum(x['net'] for x in s)/sum(x['margin'] for x in s)*100:>8.1f}%"
              f"{st.mean([x['cw'] for x in s])*100:>11.1f}%{pos:>6}/{len(by)}")
    print()
print("DEPLOYED BENCHMARK: c/w >= 0.40 at v2 = 95.8% win / +219% ROM (LOWCW_BAND_RESCUE)")
print("DONE-CWBANDS")
