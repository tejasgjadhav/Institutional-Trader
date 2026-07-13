"""Fair options test: REV1-v2 signal, but exit the CALL on the same day the UNDERLYING hits
+2% TP / -5% SL (decaying TP to +1% after day 12) — matching the futures strategy's early exit,
valuing the option at its ACTUAL bhav CLOSE that day (not hold-to-expiry intrinsic).

This isolates whether capturing the +2% move EARLY on a long call beats the theta drag.
Premiums: /tmp/bhav_cache_stk OPTSTK closes 2019->Sep'24. IS<2024, OOS=2024.
"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, "studies/monthly_fut")
from bt import load, near_month, build_features, cycles, asof

CACHE = "/tmp/bhav_cache_stk"
OOS_YEAR = 2024
_DAYCACHE = {}

def day_opts(d):
    k = d.isoformat()
    if k in _DAYCACHE:
        return _DAYCACHE[k]
    f = os.path.join(CACHE, k + ".csv")
    df = None
    if os.path.exists(f):
        try:
            df = pd.read_csv(f)
            df = df[df["INSTRUMENT"] == "OPTSTK"].copy()
            df["EXPIRY_DT"] = pd.to_datetime(df["EXPIRY_DT"], format="mixed", dayfirst=True)
        except Exception:
            df = None
    if len(_DAYCACHE) > 400:
        _DAYCACHE.clear()
    _DAYCACHE[k] = df
    return df

def call_close(df, sym, exp_target, strike):
    if df is None:
        return None, None
    sub = df[(df["SYMBOL"] == sym) & (df["OPTION_TYP"] == "CE") & (df["CLOSE"] > 0)]
    if sub.empty:
        return None, None
    exps = sub["EXPIRY_DT"].unique()
    exp = min(exps, key=lambda e: abs((pd.Timestamp(e) - exp_target).days))
    chain = sub[sub["EXPIRY_DT"] == exp]
    row = chain.iloc[(chain["STRIKE_PR"] - strike).abs().argmin()]
    return float(row["STRIKE_PR"]), float(row["CLOSE"]), pd.Timestamp(exp)

def spf(p):
    return (min(6.0, max(1.0, 60.0 / p)) / 100.0) if p > 0 else 0.06

def sel(feats, reg, d):
    r = asof(reg, d)
    if r is None or not (r["px"] > r["ma200"]):
        return []
    rows = []
    for sym, f in feats.items():
        if sym in ("NIFTY", "BANKNIFTY", "FINNIFTY"):
            continue
        x = asof(f, d)
        if x is None or np.isnan(x["mom1"]) or np.isnan(x["ma200"]) or np.isnan(x["vol20"]):
            continue
        if x["px"] <= x["ma200"]:
            continue
        rows.append((sym, x["mom1"], x["vol20"]))
    rows.sort(key=lambda t: t[1])
    pool = rows[:8]; pool.sort(key=lambda t: -t[2])
    return [s for s, _, _ in pool[:5]]

def run(otm=0.0):
    p = load(); nm = near_month(p)
    cont = {s: g.set_index("date")["close"] for s, g in nm.groupby("symbol")}
    feats, reg = build_features(cont, cont["NIFTY"])
    cyc = cycles(nm)
    by_sym = {s: g.set_index("date") for s, g in nm.groupby("symbol")}
    trades = []
    for entry_d, exp in cyc:
        entry_d = pd.Timestamp(entry_d)
        picks = sel(feats, reg, entry_d)
        eday = day_opts(entry_d.date())
        if eday is None:
            continue
        for sym in picks:
            g = by_sym.get(sym)
            if g is None or entry_d not in g.index:
                continue
            e_fut = float(g.loc[entry_d]["close"])
            r0 = g.loc[entry_d]
            res = call_close(eday, sym, exp, e_fut * (1 + otm))
            if res is None or res[1] is None or res[1] <= 0:
                continue
            K, prem0, opt_exp = res
            path = g.loc[(g.index > entry_d) & (g.index <= exp)]
            path = path[path["expiry"] == r0["expiry"]]
            if path.empty:
                continue
            rets = (path["close"] / e_fut - 1)
            exit_prem = None
            for i, (d2, rr) in enumerate(rets.items()):
                tp = 0.01 if i + 1 > 12 else 0.02
                hit = rr >= tp or rr <= -0.05
                if hit:
                    dd = day_opts(pd.Timestamp(d2).date())
                    r2 = call_close(dd, sym, exp, K) if dd is not None else None
                    if r2 and r2[1] and r2[1] > 0:
                        exit_prem = r2[1]
                    else:  # fall back to intrinsic on that day
                        exit_prem = max(0.0, float(path.loc[d2]["close"]) - K)
                    break
            if exit_prem is None:  # held to expiry -> intrinsic
                last = path.iloc[-1]
                s_exp = float(last["settle"] if np.isfinite(last["settle"]) and last["settle"] > 0 else last["close"])
                exit_prem = max(0.0, s_exp - K)
            cost = (prem0 + exit_prem) * spf(prem0)     # round-trip friction on premium
            ret = (exit_prem - prem0 - cost) / prem0
            trades.append(dict(entry=entry_d, sym=sym, prem0=prem0, exit_prem=exit_prem,
                               K=K, ret=ret))
    return pd.DataFrame(trades)

def report(t, name):
    if t.empty:
        print(f"{name}: no trades"); return
    t = t.copy(); t["yr"] = t["entry"].dt.year
    def blk(x, lbl):
        if x.empty: return
        mo = x.groupby(x["entry"].dt.to_period("M"))["ret"].mean()
        print(f"  {lbl}: n={len(x)} win={(x['ret']>0).mean()*100:.0f}% "
              f"avg_on_capital={x['ret'].mean()*100:+.0f}% median={x['ret'].median()*100:+.0f}% "
              f"mo_mean={mo.mean()*100:+.0f}% worstmo={mo.min()*100:+.0f}%")
    print(f"\n=== {name} ===")
    blk(t[t['yr'] < OOS_YEAR], "IS  2019-23"); blk(t[t['yr'] == OOS_YEAR], "OOS 2024  ")
    for y in sorted(t["yr"].unique()):
        g = t[t["yr"] == y]
        print(f"    {y}: n={len(g):3d} win={(g['ret']>0).mean()*100:3.0f}% avg={g['ret'].mean()*100:+5.0f}%")

if __name__ == "__main__":
    for otm, nm in [(0.0, "ATM early-exit"), (0.02, "2%OTM early-exit")]:
        t = run(otm)
        report(t, f"REV1-v2 long call, {nm}")
        t.to_csv(f"studies/monthly_fut/opt2_{otm}.csv", index=False)
