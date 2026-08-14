"""DATE-ALIGNED re-run of the OOS c/w band sweep — the audit fix (14-Aug-2026).

The original cw_band_sweep.py dropped candle timestamps in leg() and walked the two legs
POSITIONALLY (sp[k]-lp[k]). Upstox expired options only carry candles on traded days, so 47% of
multi-leg windows had unequal counts and the "spread" compared different dates; even the entry
credit could pair mismatched days. This version keys every leg by DATE, requires BOTH legs to have
a candle on the entry day, and marks the path only on days where both legs traded. Everything else
(geometry, exits, gates, universe slice) is identical, so any change in the result is the bug.
"""
import sys, os, json, warnings, threading, collections
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
CACHE = "/tmp/cw_band_legcache_dated.json"
SUBSET = UNIVERSE[::3]
spf = lambda p: min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0
try: LEGC = json.load(open(CACHE))
except Exception: LEGC = {}
LK = threading.Lock(); rows = []; done = [0]

def leg(key, d0, to):
    """{iso_date: close} for one option leg. Date-keyed — THE fix."""
    ck = f"{key}|{d0}|{to}"
    with LK:
        if ck in LEGC: return LEGC[ck]
    j = _gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}")
    out = {}
    if j.get("status") == "success":
        for c in j.get("data", {}).get("candles", []) or []:
            out[str(c[0])[:10]] = float(c[4])
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
            lp = leg(chain[li]["instrument_key"], d0, to)
            # THE FIX: both legs must have a candle ON THE ENTRY DAY, else no fillable spread
            if d0 not in sp or d0 not in lp: continue
            if sp[d0] < MIN_PREM: continue
            credit = sp[d0] - lp[d0]; width = abs(ks[si] - ks[li])
            if credit <= 0 or credit >= width: continue
            cw = credit / width
            band = next((b for b,(lo,hi) in BANDS.items() if lo <= cw < hi), None)
            if band is None: continue
            close = None
            both = sorted(set(sp) & set(lp))          # only days BOTH legs traded
            for dd in both:
                if dd <= d0: continue
                cost = sp[dd] - lp[dd]
                if cost <= credit * (1 - cfg["tp"]):
                    close = max(cost, 0.0) + (sp[dd]*spf(sp[dd]) + lp[dd]*spf(lp[dd]))/100.0; break
                if cfg["stop"] and cost >= credit * cfg["stop"]:
                    close = min(cost, width) + (sp[dd]*spf(sp[dd]) + lp[dd]*spf(lp[dd]))/100.0; break
            if close is None:
                es = cb.get(exp) or (cb[max(x for x in cb if x <= exp)] if any(x <= exp for x in cb) else c)
                intr_s = max(0.0, es - ks[si]) if typ == "CE" else max(0.0, ks[si] - es)
                intr_l = max(0.0, es - ks[li]) if typ == "CE" else max(0.0, ks[li] - es)
                close = min(max(intr_s - intr_l, 0.0), width)
            net = (credit - close) - (sp[d0]*spf(sp[d0]) + lp[d0]*spf(lp[d0]))/100.0
            mine.append(dict(book=bk, band=band, sym=sym, day=d0, yr=day.year,
                             net=round(net,2), margin=round(width-credit,2),
                             win=int(net>0), cw=round(cw,3)))
    with LK:
        rows.extend(mine); done[0] += 1
        if done[0] % 5 == 0:
            print(f"  {done[0]}/{len(SUBSET)} names · {len(rows)} trades", flush=True)
            json.dump(LEGC, open(CACHE, "w"))

with cf.ThreadPoolExecutor(max_workers=4) as ex:
    list(ex.map(work, SUBSET))
json.dump(LEGC, open(CACHE, "w"))
json.dump(rows, open("/tmp/cw_dated_rows.json", "w"))

print(f"\n=== DATE-ALIGNED OOS Oct-24 -> date · both legs required on entry day ===")
print(f"{'band':<12}{'book':<5}{'n':>5}{'WIN':>8}{'ROM':>9}{'avg/trade':>11}{'+ve yrs':>9}")
for band in BANDS:
    for bk in ("v2","v1","v0"):
        s = [x for x in rows if x["band"]==band and x["book"]==bk]
        if len(s) < 12:
            print(f"{band:<12}{bk:<5}{len(s):>5}   (too few)"); continue
        by = collections.defaultdict(list)
        for x in s: by[x["yr"]].append(x["net"])
        pos = sum(1 for v in by.values() if sum(v)>0)
        print(f"{band:<12}{bk:<5}{len(s):>5}{sum(x['win'] for x in s)/len(s)*100:>7.1f}%"
              f"{sum(x['net'] for x in s)/sum(x['margin'] for x in s)*100:>8.1f}%"
              f"{sum(x['net'] for x in s)/len(s):>+10.2f}{pos:>6}/{len(by)}")
    print()
print("DONE-DATED")
