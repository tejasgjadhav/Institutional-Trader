"""Options exit-variant test: does the CONVEX payoff let us lift return without losing win rate?
Variants on the REV1-v2 ATM long call (bhav IS 2019->Sep24):
  base   : TP +2% underlying (decay +1% after d12), SL -5%   [current]
  wideTP : TP +4%, SL -5%
  noSL   : TP +2%/+1%, NO stop (rely on capped premium loss), else expiry
  runexp : NO TP, NO SL -> hold winners+losers to expiry intrinsic (pure convexity)
  trail  : exit when underlying gives back 2% from its peak after being +2% up; else expiry
"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, "studies/monthly_fut")
from bt import load, near_month, build_features, cycles, asof
from opt_bt2 import day_opts, call_close, spf, sel

def run(variant):
    p = load(); nm = near_month(p)
    cont = {s: g.set_index("date")["close"] for s, g in nm.groupby("symbol")}
    feats, reg = build_features(cont, cont["NIFTY"]); cyc = cycles(nm)
    by_sym = {s: g.set_index("date") for s, g in nm.groupby("symbol")}
    tr = []
    for entry_d, exp in cyc:
        entry_d = pd.Timestamp(entry_d)
        if entry_d.year >= 2024: continue   # IS only
        eday = day_opts(entry_d.date())
        if eday is None: continue
        for sym in sel(feats, reg, entry_d):
            g = by_sym.get(sym)
            if g is None or entry_d not in g.index: continue
            e = float(g.loc[entry_d]["close"]); r0 = g.loc[entry_d]
            res = call_close(eday, sym, exp, e)
            if not res or res[1] is None or res[1] <= 0: continue
            K, prem0, _ = res
            path = g.loc[(g.index > entry_d) & (g.index <= exp)]
            path = path[path["expiry"] == r0["expiry"]]
            if path.empty: continue
            rets = (path["close"] / e - 1); peak = -9; xp = None
            for i, (d2, rr) in enumerate(rets.items()):
                peak = max(peak, rr); hit = False
                if variant == "base":   hit = rr >= (0.01 if i+1>12 else 0.02) or rr <= -0.05
                elif variant == "wideTP":hit = rr >= 0.04 or rr <= -0.05
                elif variant == "noSL":  hit = rr >= (0.01 if i+1>12 else 0.02)
                elif variant == "runexp":hit = False
                elif variant == "trail": hit = (peak >= 0.02 and rr <= peak - 0.02)
                if hit:
                    dd = day_opts(pd.Timestamp(d2).date())
                    r2 = call_close(dd, sym, exp, K) if dd is not None else None
                    xp = r2[1] if (r2 and r2[1] and r2[1] > 0) else max(0.0, float(path.loc[d2]["close"]) - K)
                    break
            if xp is None:
                last = path.iloc[-1]
                se = float(last["settle"] if np.isfinite(last["settle"]) and last["settle"]>0 else last["close"])
                xp = max(0.0, se - K)
            cost = (prem0 + xp) * spf(prem0)
            tr.append((entry_d, (xp - prem0 - cost) / prem0))
    t = pd.DataFrame(tr, columns=["entry","ret"])
    mo = t.groupby(t.entry.dt.to_period("M"))["ret"].mean()
    print(f"{variant:8s}: n={len(t)} win={(t.ret>0).mean()*100:.0f}% avg={t.ret.mean()*100:+.0f}% "
          f"med={t.ret.median()*100:+.0f}% mo={mo.mean()*100:+.0f}% worstmo={mo.min()*100:+.0f}%")

for v in ("base","wideTP","noSL","runexp","trail"):
    run(v)
