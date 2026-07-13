"""v2 UNION fade — CE-vs-PE side breakdown + holding-period decay curve (goal-loop 2026-07-10).
Answers: (1) does the CALL side (bear-call, up-breaks) have a real edge or is it the weak side?
         (2) is the edge front-loaded ("active first week then diminishing")?
Deployed v2 config: UNION Donchian (5,10,15,20), short 2-OTM, width 4, TP 50% of credit, stop 3x,
gate credit/width>=0.40 + short prem>=50, reentry 3d, min DTE 10. Real Upstox expired premiums
Oct'24->date (same source/window/slippage as the deployed v2 OOS test). Records per trade:
side, net, width, win, days_held (trading bars to exit), exit_reason, dte_entry, and the
mark-to-market spread cost at each of the first 10 trading bars (as % of entry credit) so we can
plot when the profit is actually captured. Out: /tmp/stkfade_v2_side.json
"""
import sys, warnings, json
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import datetime, timedelta, date
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical, UPSTOX_BASE
from engine.instruments import encode_key
from engine.expired_options import get_expiries, get_contracts, _get_json as _gj
import threading, concurrent.futures

START = date(2024, 10, 1); MIN_DTE = 10; REENTRY = 3; MIN_CW = 0.40; MIN_PREM = 50.0
UNION_DCS = (5, 10, 15, 20); SHORT = 2; WIDTH = 4; TP = 0.50; STOP = 3.0

import time
def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0
def leg(key, d0, to):
    url = f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}"
    for attempt in range(4):                       # retry throttling / connection resets w/ backoff
        try:
            j = _gj(url)
            if j.get("status") == "success":
                c = j.get("data", {}).get("candles", [])
                if c:
                    df = pd.DataFrame(c, columns=["ts", "O", "H", "L", "C", "V", "OI"]); df["ts"] = pd.to_datetime(df["ts"])
                    return df.set_index("ts").sort_index()["C"]
                return None                          # genuine empty (not an error) — don't retry
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))
    return None

out = []
EXPC = {}; CHC = {}
LK = threading.Lock(); DONE = [0]

def do_stock(sym0):
    sym = sym0.replace(".NS", "")
    u = fetch_upstox_historical(sym0, unit="days", interval=1, from_date="2024-06-01", to_date=date.today().isoformat())
    if u is None or u.empty or len(u) < 30:
        with LK: DONE[0] += 1
        return
    u = u.sort_index()
    cb = {ix.date().isoformat(): float(u["Close"].loc[ix]) for ix in u.index}
    # UNION: first window (smallest DC) that breaks wins, like engine _todays_breakout
    rolls = {dc: (u["High"].rolling(dc).max().shift(1), u["Low"].rolling(dc).min().shift(1)) for dc in UNION_DCS}
    last = {}
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
        try:
            if sym not in EXPC: EXPC[sym] = get_expiries(sym)
            exps = [e for e in EXPC[sym] if e >= (day + timedelta(days=MIN_DTE)).isoformat()]
            if not exps: continue
            exp = exps[0]
            ck = (sym, exp, typ)
            if ck not in CHC:
                CHC[ck] = sorted([ct for ct in get_contracts(sym, exp) if ct["instrument_type"] == typ],
                                 key=lambda ct: float(ct["strike_price"]))
            chain = CHC[ck]
        except Exception: continue
        ks = [float(ct["strike_price"]) for ct in chain]
        if len(ks) < SHORT + WIDTH + 2: continue
        atm = min(range(len(ks)), key=lambda j: abs(ks[j] - c))
        si, li = (atm + SHORT, atm + SHORT + WIDTH) if typ == "CE" else (atm - SHORT, atm - SHORT - WIDTH)
        if si < 0 or li < 0 or si >= len(ks) or li >= len(ks): continue
        sct, lct = chain[si], chain[li]; sk, lk = ks[si], ks[li]
        to = min(datetime.fromisoformat(exp).date(), day + timedelta(days=45)).isoformat()
        sp = leg(sct["instrument_key"], day.isoformat(), to); lp = leg(lct["instrument_key"], day.isoformat(), to)
        if sp is None or lp is None or len(sp) < 1 or len(lp) < 1: continue
        se = float(sp.iloc[0]); le = float(lp.iloc[0]); credit = se - le; w = abs(sk - lk)
        if se < MIN_PREM or credit <= 0 or credit >= w or credit / w < MIN_CW: continue
        last[typ] = day
        m = min(len(sp), len(lp))
        # decay path: spread cost at each trading bar as % of entry credit (100% = no decay, 0% = full profit)
        path = []
        for t in range(1, min(m, 11)):
            cost_t = float(sp.iloc[t]) - float(lp.iloc[t])
            path.append(round(max(cost_t, 0.0) / credit * 100, 1))
        close = None; reason = "EXPIRY"; held = m - 1
        for t in range(1, m):
            a = float(sp.iloc[t]); b = float(lp.iloc[t]); cost = a - b
            if TP > 0 and cost <= credit * (1 - TP):
                close = max(cost, 0.0) + (a * spf(a) + b * spf(b)) / 100.0; reason = "TP"; held = t; break
            if cost >= credit * STOP:
                close = min(cost, w) + (a * spf(a) + b * spf(b)) / 100.0; reason = "STOP"; held = t; break
        if close is None:
            espot = cb.get(exp) or (cb[max(x for x in cb if x < exp)] if any(x < exp for x in cb) else c)
            intr = max(0.0, espot - sk) if typ == "CE" else max(0.0, sk - espot)
            intl = max(0.0, espot - lk) if typ == "CE" else max(0.0, lk - espot)
            close = min(max(intr - intl, 0.0), w)
        net = (credit - close) - (se * spf(se) + le * spf(le)) / 100.0
        dte = (datetime.fromisoformat(exp).date() - day).days
        with LK:
            out.append(dict(y=day.year, side=typ, net=float(net), w=float(w), win=int(net > 0),
                            held=held, reason=reason, dte=dte, path=path))
    with LK:
        DONE[0] += 1
        if DONE[0] % 10 == 0:
            json.dump(out, open("/tmp/stkfade_v2_side.json", "w"))    # checkpoint — survive stalls
            print(f"  …{DONE[0]}/100 stocks, {len(out)} trades (saved)", flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:      # gentler on the throttled API
    list(ex.map(do_stock, UNIVERSE))

json.dump(out, open("/tmp/stkfade_v2_side.json", "w"))
t = pd.DataFrame(out)
print(f"\n=== v2 UNION OOS Oct'24->date — {len(t)} trades ===")

def block(g, label):
    if len(g) == 0: print(f"{label:14s} n=0"); return
    print(f"{label:14s} n={len(g):3d}  win {g.win.mean()*100:4.0f}%  net {g.net.sum()/g.w.sum()*100:+6.1f}%w  "
          f"medHeld {g.held.median():.0f}bar  TP {(g.reason=='TP').mean()*100:.0f}% STOP {(g.reason=='STOP').mean()*100:.0f}% EXP {(g.reason=='EXPIRY').mean()*100:.0f}%")

print("\n-- BY SIDE --")
block(t[t.side == "CE"], "CALL (bear-c)")
block(t[t.side == "PE"], "PUT (bull-p)")
block(t, "BOTH")
print("\n-- CALL side by year --")
for y in sorted(t[t.side=="CE"].y.unique()):
    block(t[(t.side=="CE") & (t.y==y)], f"  CALL {y}")
print("\n-- HOLDING PERIOD (when the trade closes) --")
for lo, hi, lab in [(0,3,"week1 (<=3bar)"), (4,5,"~1wk (4-5)"), (6,10,"wk2 (6-10)"), (11,99,">2wk (11+)")]:
    g = t[(t.held >= lo) & (t.held <= hi)]
    print(f"  {lab:16s} n={len(g):3d} ({len(g)/len(t)*100:2.0f}%)  win {g.win.mean()*100 if len(g) else 0:3.0f}%  net {g.net.sum()/g.w.sum()*100 if len(g) else 0:+6.1f}%w")
print("\n-- AVG CREDIT-DECAY PATH (spread cost as % of entry credit; lower=more profit captured) --")
for bar in range(10):
    vals = [tr["path"][bar] for tr in out if len(tr["path"]) > bar]
    if vals: print(f"  bar {bar+1:2d}: {sum(vals)/len(vals):5.1f}%  (n={len(vals)})")
print("DONE-V2SIDE")
