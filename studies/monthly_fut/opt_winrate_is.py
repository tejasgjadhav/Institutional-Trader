"""Win-rate lever sweep on the 5-pick long-call book, IS bhav premiums 2019->Sep24.
Levers: TP {2%,1.5%,1%} x strike {ATM, ITM(-2%), ITM(-4%)}. Lower TP + deeper ITM = more wins
(mechanically). Reports win% + return so we see the win/return trade-off. -5% underlying stop.
Fetch each pick's call ONCE per strike, evaluate all TP variants on it."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "studies/monthly_fut")
from bt import load, near_month, build_features, cycles, asof
from opt_bt2 import day_opts, call_close, spf, sel

def eval_pick(sym, entry_d, exp, eday, by_sym, strike_off, tp_base):
    g = by_sym.get(sym)
    if g is None or entry_d not in g.index: return None
    e = float(g.loc[entry_d]["close"]); r0 = g.loc[entry_d]
    res = call_close(eday, sym, exp, e*(1+strike_off))
    if not res or res[1] is None or res[1] <= 0: return None
    K, prem0, _ = res
    path = g.loc[(g.index > entry_d) & (g.index <= exp)]; path = path[path["expiry"] == r0["expiry"]]
    if path.empty: return None
    rets = (path["close"]/e - 1); xp = None
    for i,(d2,rr) in enumerate(rets.items()):
        tp = (tp_base-0.01) if i+1>12 else tp_base
        if rr >= tp or rr <= -0.05:
            dd = day_opts(pd.Timestamp(d2).date()); r2 = call_close(dd, sym, exp, K) if dd is not None else None
            xp = r2[1] if (r2 and r2[1] and r2[1]>0) else max(0.0, float(path.loc[d2]["close"])-K); break
    if xp is None:
        last = path.iloc[-1]; se = float(last["settle"] if np.isfinite(last["settle"]) and last["settle"]>0 else last["close"]); xp = max(0.0, se-K)
    return (xp - prem0 - (prem0+xp)*spf(prem0))/prem0

def run(strike_off, tp_base):
    p = load(); nm = near_month(p)
    cont = {s: g.set_index("date")["close"] for s,g in nm.groupby("symbol")}
    feats, reg = build_features(cont, cont["NIFTY"]); cyc = cycles(nm)
    by_sym = {s: g.set_index("date") for s,g in nm.groupby("symbol")}
    win=[]; 
    for entry_d, exp in cyc:
        entry_d = pd.Timestamp(entry_d)
        if entry_d.year >= 2024: continue
        eday = day_opts(entry_d.date())
        if eday is None: continue
        for sym in sel(feats, reg, entry_d):
            r = eval_pick(sym, entry_d, exp, eday, by_sym, strike_off, tp_base)
            if r is not None: win.append(r)
    w = np.array(win)
    print(f"strike {strike_off*100:+.0f}%  TP {tp_base*100:.1f}%: n={len(w)} win={(w>0).mean()*100:.0f}% avg={w.mean()*100:+.0f}%")

print("IS 2019-23 win-rate levers (5-pick):")
for so in (0.0, -0.02, -0.04):
    for tp in (0.02, 0.015, 0.01):
        run(so, tp)
