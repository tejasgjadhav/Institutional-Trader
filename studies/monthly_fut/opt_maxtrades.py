"""MAX-trades / MAX-return monthly options on a FIXED Rs2L, 67% win acceptable.
Lever = how many pullback names to buy as calls each cycle. Same REV1-v2 signal, early-exit
(+2%/-5% underlying). Allocate Rs2L EQUALLY across that cycle's picks (capital-constrained: if
picks*premium > 2L, size down per name). Measure monthly return on Rs2L, win rate, worst month, DD.
IS = bhav stock-option premiums 2019->Sep24.
"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, "studies/monthly_fut")
from bt import load, near_month, build_features, cycles, asof
from opt_bt2 import day_opts, call_close, spf

CAP = 200000.0

def picks(feats, reg, d, n):
    r = asof(reg, d)
    if r is None or not (r["px"] > r["ma200"]): return []
    rows = []
    for sym, f in feats.items():
        if sym in ("NIFTY","BANKNIFTY","FINNIFTY"): continue
        x = asof(f, d)
        if x is None or np.isnan(x["mom1"]) or np.isnan(x["ma200"]) or np.isnan(x["vol20"]): continue
        if x["px"] <= x["ma200"]: continue
        rows.append((sym, x["mom1"], x["vol20"]))
    rows.sort(key=lambda t: t[1])                 # worst 1-mo losers
    pool = rows[:max(n, 8)]; pool.sort(key=lambda t: -t[2])   # top by vol
    return [s for s,_,_ in pool[:n]]

def trade_ret(sym, entry_d, exp, eday, by_sym):
    g = by_sym.get(sym)
    if g is None or entry_d not in g.index: return None
    e = float(g.loc[entry_d]["close"]); r0 = g.loc[entry_d]
    res = call_close(eday, sym, exp, e)
    if not res or res[1] is None or res[1] <= 0: return None
    K, prem0, _ = res
    path = g.loc[(g.index > entry_d) & (g.index <= exp)]
    path = path[path["expiry"] == r0["expiry"]]
    if path.empty: return None
    rets = (path["close"]/e - 1); xp = None
    for i,(d2,rr) in enumerate(rets.items()):
        tp = 0.01 if i+1>12 else 0.02
        if rr>=tp or rr<=-0.05:
            dd = day_opts(pd.Timestamp(d2).date())
            r2 = call_close(dd, sym, exp, K) if dd is not None else None
            xp = r2[1] if (r2 and r2[1] and r2[1]>0) else max(0.0, float(path.loc[d2]["close"])-K)
            break
    if xp is None:
        last = path.iloc[-1]
        se = float(last["settle"] if np.isfinite(last["settle"]) and last["settle"]>0 else last["close"])
        xp = max(0.0, se-K)
    cost = (prem0+xp)*spf(prem0)
    return (xp - prem0 - cost)/prem0, prem0     # ret on premium, premium/share

def run(n):
    p = load(); nm = near_month(p)
    cont = {s: g.set_index("date")["close"] for s,g in nm.groupby("symbol")}
    feats, reg = build_features(cont, cont["NIFTY"]); cyc = cycles(nm)
    by_sym = {s: g.set_index("date") for s,g in nm.groupby("symbol")}
    months = []; allwin = []
    for entry_d, exp in cyc:
        entry_d = pd.Timestamp(entry_d)
        if entry_d.year >= 2024: continue
        eday = day_opts(entry_d.date())
        if eday is None: continue
        rs = []
        for sym in picks(feats, reg, entry_d, n):
            t = trade_ret(sym, entry_d, exp, eday, by_sym)
            if t: rs.append(t[0])
        if not rs: continue
        # equal-weight Rs2L across the cycle's trades -> month return on Rs2L = mean(ret on premium)
        months.append(np.mean(rs)); allwin += rs
    m = np.array(months); w = np.array(allwin)
    eq = np.cumprod(1+m); dd = (eq/np.maximum.accumulate(eq)-1).min()
    return dict(n_pick=n, trades=len(w), win=(w>0).mean()*100, mo=m.mean()*100,
                med=np.median(m)*100, worst=m.min()*100, dd=dd*100, months=len(m),
                rs_mo=m.mean()*CAP)

print(f"{'picks/cyc':>9} {'trades':>6} {'win%':>5} {'mo_ret%':>7} {'worstmo':>7} {'maxDD':>6} {'Rs/mo on 2L':>12}")
for n in (3,5,8,12,20):
    r = run(n)
    print(f"{r['n_pick']:>9} {r['trades']:>6} {r['win']:>5.0f} {r['mo']:>7.1f} {r['worst']:>7.1f} {r['dd']:>6.0f} {r['rs_mo']:>12,.0f}")

# ---- circuit-breaker: deploy only DEPLOY_FRAC of Rs2L, rest cash (caps crash months) ----
def run_capped(n, deploy_frac):
    p = load(); nm = near_month(p)
    cont = {s: g.set_index("date")["close"] for s,g in nm.groupby("symbol")}
    feats, reg = build_features(cont, cont["NIFTY"]); cyc = cycles(nm)
    by_sym = {s: g.set_index("date") for s,g in nm.groupby("symbol")}
    months = []; win = []
    for entry_d, exp in cyc:
        entry_d = pd.Timestamp(entry_d)
        if entry_d.year >= 2024: continue
        eday = day_opts(entry_d.date())
        if eday is None: continue
        rs = []
        for sym in picks(feats, reg, entry_d, n):
            t = trade_ret(sym, entry_d, exp, eday, by_sym)
            if t: rs.append(t[0])
        if not rs: continue
        # only deploy_frac of Rs2L across the calls; rest earns 0 -> month return on FULL 2L
        months.append(np.mean(rs) * deploy_frac); win += rs
    m = np.array(months); w = np.array(win)
    eq = np.cumprod(1+m); dd = (eq/np.maximum.accumulate(eq)-1).min()
    print(f"  {n} picks, deploy {deploy_frac*100:.0f}% of 2L: win {(w>0).mean()*100:.0f}% "
          f"mo {m.mean()*100:.1f}% worstmo {m.min()*100:.0f}% maxDD {dd*100:.0f}% "
          f"Rs/mo {m.mean()*200000:,.0f}")

print("\n=== with cash-buffer circuit breaker ===")
for n, fr in [(8,0.6),(8,0.5),(12,0.6),(12,0.5),(8,0.4)]:
    run_capped(n, fr)
