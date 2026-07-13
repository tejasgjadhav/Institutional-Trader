"""DECISIVE OOS: REV1-v2 signal as an early-exit ATM long call, on REAL Upstox expired-option
premiums Oct'24 -> date (the 21-month window the futures/v2 tests used; the window bhav can't
reach). Picks come from the futures panel (extends to 2026); call premiums via expired-instruments.

For each monthly cycle entry >= 2024-10-01: 5 picks (worst-8 pullbacks above 200DMA -> top-5 vol,
NIFTY>200DMA). Buy the ~ATM call at cycle expiry. Walk the underlying (futures panel close) day by
day; on the day it hits +2% (decay to +1% after d12) / -5%, value the call at its Upstox CLOSE that
day; else intrinsic at expiry. Return on premium deployed. Round-trip spread-fraction cost.
"""
import sys, warnings, json
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
sys.path.insert(0, "studies/monthly_fut")
import numpy as np, pandas as pd
from datetime import datetime, timedelta, date
from bt import load, near_month, build_features, cycles, asof
from engine.instruments import encode_key
from engine.expired_options import get_expiries, get_contracts, _get_json as _gj
from engine.data_fetcher import UPSTOX_BASE

def spf(p):
    return (min(6.0, max(1.0, 60.0 / p)) / 100.0) if p > 0 else 0.06

def opt_series(key, d0, to):
    j = _gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}")
    if j.get("status") == "success":
        c = j.get("data", {}).get("candles", [])
        if c:
            df = pd.DataFrame(c, columns=["ts", "O", "H", "L", "C", "V", "OI"])
            df["ts"] = pd.to_datetime(df["ts"]).dt.tz_localize(None)
            return df.set_index("ts").sort_index()["C"]
    return None

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

p = load(); nm = near_month(p)
cont = {s: g.set_index("date")["close"] for s, g in nm.groupby("symbol")}
feats, reg = build_features(cont, cont["NIFTY"])
cyc = cycles(nm)
by_sym = {s: g.set_index("date") for s, g in nm.groupby("symbol")}
EXP = {}; CHAIN = {}
trades = []

for entry_d, exp in cyc:
    entry_d = pd.Timestamp(entry_d)
    if entry_d < pd.Timestamp("2024-10-01"):
        continue
    picks = sel(feats, reg, entry_d)
    for sym in picks:
        g = by_sym.get(sym)
        if g is None or entry_d not in g.index:
            continue
        e_fut = float(g.loc[entry_d]["close"])
        r0 = g.loc[entry_d]
        try:
            if sym not in EXP:
                EXP[sym] = get_expiries(sym)
            cands = [e for e in EXP[sym] if e >= exp.date().isoformat()]
            oexp = cands[0] if cands else (max(EXP[sym]) if EXP[sym] else None)
            if not oexp:
                continue
            ck = (sym, oexp)
            if ck not in CHAIN:
                CHAIN[ck] = sorted([c for c in get_contracts(sym, oexp) if c["instrument_type"] == "CE"],
                                   key=lambda c: float(c["strike_price"]))
            chain = CHAIN[ck]
        except Exception:
            continue
        if not chain:
            continue
        ks = [float(c["strike_price"]) for c in chain]
        ai = min(range(len(ks)), key=lambda i: abs(ks[i] - e_fut))
        K = ks[ai]; key = chain[ai]["instrument_key"]
        to = min(datetime.fromisoformat(oexp).date(), entry_d.date() + timedelta(days=45)).isoformat()
        ser = opt_series(key, entry_d.date().isoformat(), to)
        if ser is None or ser.empty:
            continue
        prem0 = float(ser.iloc[0])
        if prem0 <= 0:
            continue
        path = g.loc[(g.index > entry_d) & (g.index <= exp)]
        path = path[path["expiry"] == r0["expiry"]]
        if path.empty:
            continue
        rets = (path["close"] / e_fut - 1)
        exit_prem = None
        for i, (d2, rr) in enumerate(rets.items()):
            tp = 0.01 if i + 1 > 12 else 0.02
            if rr >= tp or rr <= -0.05:
                d2n = pd.Timestamp(d2).normalize()
                v = ser[ser.index.normalize() == d2n]
                if len(v):
                    exit_prem = float(v.iloc[-1])
                else:
                    exit_prem = max(0.0, float(path.loc[d2]["close"]) - K)
                break
        if exit_prem is None:
            last = path.iloc[-1]
            s_exp = float(last["settle"] if np.isfinite(last["settle"]) and last["settle"] > 0 else last["close"])
            exit_prem = max(0.0, s_exp - K)
        cost = (prem0 + exit_prem) * spf(prem0)
        ret = (exit_prem - prem0 - cost) / prem0
        trades.append(dict(entry=str(entry_d.date()), sym=sym, prem0=prem0, exit_prem=exit_prem, ret=ret))
    print(f"  ...through {entry_d.date()}, {len(trades)} trades", flush=True)

t = pd.DataFrame(trades)
t.to_csv("studies/monthly_fut/opt_oos_trades.csv", index=False)
if not t.empty:
    t["entry"] = pd.to_datetime(t["entry"])
    mo = t.groupby(t["entry"].dt.to_period("M"))["ret"].mean()
    print(f"\n=== REV1-v2 ATM early-exit call — OOS Oct'24->date (Upstox premiums) ===")
    print(f"n={len(t)} win={(t['ret']>0).mean()*100:.0f}% avg_on_capital={t['ret'].mean()*100:+.0f}% "
          f"median={t['ret'].median()*100:+.0f}% mo_mean={mo.mean()*100:+.0f}% "
          f"worstmo={mo.min()*100:+.0f}% +months={(mo>0).mean()*100:.0f}%")
    for y in sorted(t["entry"].dt.year.unique()):
        gy = t[t["entry"].dt.year == y]
        print(f"  {y}: n={len(gy)} win={(gy['ret']>0).mean()*100:.0f}% avg={gy['ret'].mean()*100:+.0f}%")
print("DONE-OPT-OOS")
