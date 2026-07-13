"""Express the validated REV1-v2 monthly pullback signal as OPTIONS instead of futures, and
measure return on CAPITAL DEPLOYED (premium, not margin) on real NSE stock-option premiums.

Signal (unchanged, from bt.py): each monthly cycle, NIFTY>200DMA, worst-8 1-month losers above
their own 200DMA, keep top-5 by 20d vol. Instead of buying the future:
  LONGCALL_ATM   buy the ATM call expiring at cycle expiry, hold to expiry (payoff=intrinsic)
  LONGCALL_OTM   buy the ~2% OTM call, same
  CALLSPREAD     buy ATM call, sell ~5% OTM call (debit spread — cuts premium + decay)
Return on capital = (exit_value - entry_premium) / entry_premium  (spread: /net debit).
Costs: ₹ per-leg friction via a spread-fraction model (same spirit as stkfade).

Option premiums: /tmp/bhav_cache_stk OPTSTK rows (CLOSE) 2019→Sep'24. IS=<2024, OOS=2024.
"""
import os, glob, sys
import numpy as np, pandas as pd
sys.path.insert(0, "studies/monthly_fut")
from bt import load, near_month, build_features, cycles, asof  # reuse infra

CACHE = "/tmp/bhav_cache_stk"
OOS_YEAR = 2024   # bhav option data ends Sep'24; treat 2024 as the held-out slice

def _opt_rows_for_day(d):
    """Return DataFrame of OPTSTK rows for date d (or None)."""
    f = os.path.join(CACHE, d.isoformat() + ".csv")
    if not os.path.exists(f):
        return None
    try:
        df = pd.read_csv(f)
    except Exception:
        return None
    df = df[df["INSTRUMENT"] == "OPTSTK"]
    return df if not df.empty else None

def _call(df, sym, expiry, strike):
    """Nearest-strike CE close for sym/expiry at/above `strike` (buy side)."""
    sub = df[(df["SYMBOL"] == sym) & (df["OPTION_TYP"] == "CE")]
    if sub.empty:
        return None, None
    sub = sub.copy()
    sub["EXPIRY_DT"] = pd.to_datetime(sub["EXPIRY_DT"], format="mixed", dayfirst=True)
    # nearest listed expiry to the target cycle expiry
    exps = sub["EXPIRY_DT"].unique()
    exp = min(exps, key=lambda e: abs((pd.Timestamp(e) - expiry).days))
    chain = sub[sub["EXPIRY_DT"] == exp]
    chain = chain[chain["CLOSE"] > 0]
    if chain.empty:
        return None, None
    row = chain.iloc[(chain["STRIKE_PR"] - strike).abs().argmin()]
    return float(row["STRIKE_PR"]), float(row["CLOSE"])

def spf(p):
    return min(6.0, max(1.0, 60.0 / p)) / 100.0 if p > 0 else 0.06  # spread fraction

def run(structure):
    p = load(); nm = near_month(p)
    cont = {s: g.set_index("date")["close"] for s, g in nm.groupby("symbol")}
    feats, reg = build_features(cont, cont["NIFTY"])
    cyc = cycles(nm)
    by_sym = {s: g.set_index("date") for s, g in nm.groupby("symbol")}
    trades = []
    for entry_d, exp in cyc:
        entry_d = pd.Timestamp(entry_d)
        picks = sel_rev_ranked_v2(feats, reg, entry_d)   # 5 names
        eday = _opt_rows_for_day(entry_d.date())
        xday = _opt_rows_for_day(exp.date())
        if eday is None:
            continue
        for sym in picks:
            g = by_sym.get(sym)
            if g is None or entry_d not in g.index:
                continue
            spot0 = float(g.loc[entry_d]["close"])
            # underlying spot at expiry (last cash proxy = future settle near expiry)
            path = g.loc[(g.index > entry_d) & (g.index <= exp)]
            path = path[path["expiry"] == g.loc[entry_d]["expiry"]]
            if path.empty:
                continue
            spot_exp = float(path.iloc[-1]["settle"] if np.isfinite(path.iloc[-1]["settle"]) and path.iloc[-1]["settle"] > 0 else path.iloc[-1]["close"])
            if structure in ("ATM", "OTM"):
                tgt = spot0 * (1.0 if structure == "ATM" else 1.02)
                K, prem = _call(eday, sym, exp, tgt)
                if K is None or prem <= 0:
                    continue
                payoff = max(0.0, spot_exp - K)
                cost = prem * (1 + spf(prem))            # entry friction
                ret = (payoff - cost) / cost
                trades.append(dict(entry=entry_d, sym=sym, structure=structure,
                                   prem=prem, K=K, spot0=spot0, spot_exp=spot_exp, ret=ret))
            else:  # CALLSPREAD ATM/+5%
                Kl, pl = _call(eday, sym, exp, spot0)
                Ks, ps = _call(eday, sym, exp, spot0 * 1.05)
                if Kl is None or Ks is None or Ks <= Kl:
                    continue
                debit = pl - ps
                if debit <= 0:
                    continue
                payoff = min(max(0.0, spot_exp - Kl), Ks - Kl) - max(0.0, spot_exp - Ks)
                payoff = min(max(0.0, spot_exp - Kl), Ks - Kl)
                cost = debit * (1 + spf(pl))
                ret = (payoff - cost) / cost
                trades.append(dict(entry=entry_d, sym=sym, structure=structure,
                                   prem=debit, K=Kl, spot0=spot0, spot_exp=spot_exp, ret=ret))
    return pd.DataFrame(trades)

def sel_rev_ranked_v2(feats, reg, d):
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

def report(t, name):
    if t.empty:
        print(f"{name}: no trades"); return
    t = t.copy(); t["yr"] = t["entry"].dt.year
    is_ = t[t["yr"] < OOS_YEAR]; oos = t[t["yr"] == OOS_YEAR]
    def blk(x, lbl):
        if x.empty: return
        mo = x.groupby(x["entry"].dt.to_period("M"))["ret"].mean()
        print(f"  {lbl}: n={len(x)} win={(x['ret']>0).mean()*100:.0f}% "
              f"avg_ret_on_capital={x['ret'].mean()*100:+.0f}% median={x['ret'].median()*100:+.0f}% "
              f"mo_mean={mo.mean()*100:+.0f}% worstmo={mo.min()*100:+.0f}%")
    print(f"\n=== {name} ===")
    blk(is_, "IS  2019-23"); blk(oos, "OOS 2024  ")
    for y in sorted(t["yr"].unique()):
        g = t[t["yr"] == y]
        print(f"    {y}: n={len(g):3d} win={(g['ret']>0).mean()*100:3.0f}% avg={g['ret'].mean()*100:+5.0f}%")

if __name__ == "__main__":
    for s in ("ATM", "OTM", "CALLSPREAD"):
        t = run(s)
        report(t, f"REV1-v2 as {s} call")
        t.to_csv(f"studies/monthly_fut/opt_{s}.csv", index=False)
