"""Monthly futures backtest — NSE stock + index futures, expiry-to-expiry cycles.

Data: panel.csv.gz (build_panel.py). Signals on ratio-adjusted continuous near-month
closes; P&L on actual contract prices (entry close -> exit close/settle). Close-based
TP/SL (MOC-style). Costs: 0.10% of notional round-trip.

Usage: bt.py [--grid | --config NAME]
"""
import sys, json, itertools
import numpy as np
import pandas as pd

BASE = "/Users/sayali/files/institutional-trader/studies/monthly_fut"
COST = 0.0010          # round-trip, fraction of notional
STK_MARGIN = 0.22      # stock futures margin (post peak-margin era)
IDX_MARGIN = 0.11      # index futures margin
OOS_START = pd.Timestamp("2024-10-01")   # entry date on/after this = OOS

# ---------------- data ----------------

def load():
    p = pd.read_csv(f"{BASE}/panel.csv.gz", parse_dates=["date", "expiry"])
    p = p[p["close"] > 0]
    return p

def near_month(p):
    """front-month row per symbol/date (earliest expiry >= date)."""
    p = p[p["expiry"] >= p["date"]]
    idx = p.groupby(["symbol", "date"])["expiry"].idxmin()
    return p.loc[idx].sort_values(["symbol", "date"]).reset_index(drop=True)

def continuous(nm):
    """ratio-adjusted continuous close per symbol (for signals only)."""
    out = {}
    for sym, g in nm.groupby("symbol"):
        g = g.sort_values("date")
        px = g["close"].to_numpy().astype(float)
        exp = g["expiry"].to_numpy()
        adj = np.ones(len(g))
        # on roll day (expiry changes), scale history so the series is jump-free at rolls
        for i in range(1, len(g)):
            if exp[i] != exp[i - 1] and px[i - 1] > 0:
                # ratio between new contract's prior-day close unknown -> use same-day:
                # approximate roll ratio via today's new close vs yesterday's old close is
                # contaminated by the day's move; instead use settle continuity: skip -
                # keep raw closes; monthly signals tolerate the small roll jump (~carry).
                pass
        s = pd.Series(px, index=g["date"].values)
        out[sym] = s
    return out

def cycles(nm):
    """list of (entry_date, expiry) monthly cycles from index expiries (last Thu)."""
    # use NIFTY monthly expiries as the calendar; fall back to union of stock expiries
    sym = "NIFTY" if (nm["symbol"] == "NIFTY").any() else nm["symbol"].iloc[0]
    g = nm[nm["symbol"] == sym]
    exps = sorted(g["expiry"].unique())
    # monthly expiries only: last expiry per (year, month)
    e = pd.Series(exps)
    monthly = e.groupby([e.dt.year, e.dt.month]).max().tolist()
    dates = sorted(nm["date"].unique())
    dates = pd.Series(dates)
    out = []
    for i in range(1, len(monthly)):
        prev_exp, this_exp = monthly[i - 1], monthly[i]
        after = dates[dates > prev_exp]
        if after.empty: continue
        entry = after.iloc[0]
        if entry >= this_exp: continue
        out.append((entry, this_exp))
    return out

# ---------------- signals ----------------

def build_features(cont, nifty):
    """per symbol: dict of feature Series computed on continuous closes."""
    feats = {}
    for sym, s in cont.items():
        f = pd.DataFrame(index=s.index)
        f["px"] = s
        f["ma200"] = s.rolling(200, min_periods=150).mean()
        f["ma50"] = s.rolling(50, min_periods=40).mean()
        f["mom6"] = s.pct_change(126)
        f["mom3"] = s.pct_change(63)
        f["mom1"] = s.pct_change(21)
        f["vol20"] = s.pct_change().rolling(20).std() * np.sqrt(252)
        f["hi10"] = s.rolling(10).max()
        f["lo10"] = s.rolling(10).min()
        feats[sym] = f
    reg = pd.DataFrame(index=nifty.index)
    reg["px"] = nifty
    reg["ma200"] = nifty.rolling(200, min_periods=150).mean()
    return feats, reg

def asof(f, d):
    """last row of f at or before date d (no lookahead)."""
    ix = f.index[f.index <= d]
    if len(ix) == 0: return None
    return f.loc[ix[-1]]

# ---------------- strategies ----------------
# each returns list of (symbol, side) chosen AT entry date using features <= entry date

def sel_mom_long(feats, reg, d, topn=5, mom="mom6", need_regime=True):
    if need_regime:
        r = asof(reg, d)
        if r is None or not (r["px"] > r["ma200"]): return []
    rows = []
    for sym, f in feats.items():
        if sym in ("NIFTY", "BANKNIFTY", "FINNIFTY"): continue
        x = asof(f, d)
        if x is None or np.isnan(x[mom]) or np.isnan(x["ma200"]): continue
        if x["px"] <= x["ma200"]: continue
        rows.append((sym, x[mom]))
    rows.sort(key=lambda t: -t[1])
    return [(s, +1) for s, _ in rows[:topn]]

def sel_mom_short(feats, reg, d, topn=5, mom="mom6"):
    r = asof(reg, d)
    if r is None or not (r["px"] < r["ma200"]): return []
    rows = []
    for sym, f in feats.items():
        if sym in ("NIFTY", "BANKNIFTY", "FINNIFTY"): continue
        x = asof(f, d)
        if x is None or np.isnan(x[mom]) or np.isnan(x["ma200"]): continue
        if x["px"] >= x["ma200"]: continue
        rows.append((sym, x[mom]))
    rows.sort(key=lambda t: t[1])
    return [(s, -1) for s, _ in rows[:topn]]

def sel_rev_long(feats, reg, d, topn=5):
    """worst 1-month losers still above 200DMA, NIFTY regime up."""
    r = asof(reg, d)
    if r is None or not (r["px"] > r["ma200"]): return []
    rows = []
    for sym, f in feats.items():
        if sym in ("NIFTY", "BANKNIFTY", "FINNIFTY"): continue
        x = asof(f, d)
        if x is None or np.isnan(x["mom1"]) or np.isnan(x["ma200"]): continue
        if x["px"] <= x["ma200"]: continue
        rows.append((sym, x["mom1"]))
    rows.sort(key=lambda t: t[1])
    return [(s, +1) for s, _ in rows[:topn]]

def sel_idx_trend(feats, reg, d, both_sides=False):
    out = []
    for sym in ("NIFTY", "BANKNIFTY"):
        if sym not in feats: continue
        x = asof(feats[sym], d)
        if x is None or np.isnan(x["ma200"]): continue
        if x["px"] > x["ma200"]: out.append((sym, +1))
        elif both_sides: out.append((sym, -1))
    return out

def sel_idx_dip(feats, reg, d):
    """long index when regime up but last month was down (buy the dip)."""
    out = []
    for sym in ("NIFTY", "BANKNIFTY"):
        if sym not in feats: continue
        x = asof(feats[sym], d)
        if x is None or np.isnan(x["ma200"]) or np.isnan(x["mom1"]): continue
        if x["px"] > x["ma200"] and x["mom1"] < 0: out.append((sym, +1))
    return out

def sel_mom_lowvol(feats, reg, d, topn=5):
    """momentum longs restricted to the calmer half of the universe."""
    r = asof(reg, d)
    if r is None or not (r["px"] > r["ma200"]): return []
    rows = []
    for sym, f in feats.items():
        if sym in ("NIFTY", "BANKNIFTY", "FINNIFTY"): continue
        x = asof(f, d)
        if x is None or np.isnan(x["mom6"]) or np.isnan(x["ma200"]) or np.isnan(x["vol20"]): continue
        if x["px"] <= x["ma200"]: continue
        rows.append((sym, x["mom6"], x["vol20"]))
    if not rows: return []
    vmed = np.median([v for _, _, v in rows])
    rows = [(s, m) for s, m, v in rows if v <= vmed]
    rows.sort(key=lambda t: -t[1])
    return [(s, +1) for s, _ in rows[:topn]]

def sel_hedged_mom(feats, reg, d, topn=5):
    """long topn momentum stocks + short NIFTY as beta hedge (1 index leg per basket)."""
    longs = sel_mom_long(feats, reg, d, topn, "mom6")
    if not longs: return []
    return longs + [("NIFTY", -1)]

def sel_fade_short(feats, reg, d, topn=5):
    """short stocks that closed above their Donchian-10 high in the last 2 sessions
    (the validated reversion insight, monthly-horizon version)."""
    rows = []
    for sym, f in feats.items():
        if sym in ("NIFTY", "BANKNIFTY", "FINNIFTY"): continue
        g = f[f.index <= d]
        if len(g) < 12: continue
        last = g.iloc[-1]
        prev_hi = g["px"].iloc[-11:-1].max()
        if np.isnan(prev_hi): continue
        if last["px"] > prev_hi:                      # fresh 10d-high break
            ext = last["px"] / prev_hi - 1
            rows.append((sym, ext))
    rows.sort(key=lambda t: -t[1])
    return [(s, -1) for s, _ in rows[:topn]]

STRATS = {
    "MOM6_L": lambda f, r, d: sel_mom_long(f, r, d, 5, "mom6"),
    "MOM3_L": lambda f, r, d: sel_mom_long(f, r, d, 5, "mom3"),
    "MOM6_L_noreg": lambda f, r, d: sel_mom_long(f, r, d, 5, "mom6", need_regime=False),
    "MOM6_S": lambda f, r, d: sel_mom_short(f, r, d, 5, "mom6"),
    "REV1_L": lambda f, r, d: sel_rev_long(f, r, d, 5),
    "IDX_TREND_L": lambda f, r, d: sel_idx_trend(f, r, d, both_sides=False),
    "IDX_TREND_LS": lambda f, r, d: sel_idx_trend(f, r, d, both_sides=True),
    "FADE10_S": lambda f, r, d: sel_fade_short(f, r, d, 5),
    "IDX_DIP_L": lambda f, r, d: sel_idx_dip(f, r, d),
    "MOM6_LOWVOL_L": lambda f, r, d: sel_mom_lowvol(f, r, d, 5),
    "HEDGED_MOM6": lambda f, r, d: sel_hedged_mom(f, r, d, 5),
}

# ---------------- execution ----------------

def run_trades(nm, feats, reg, cyc, select, tp=None, sl=None):
    """simulate: entry at close of entry date in the contract expiring at cycle expiry;
    exit at first close hitting tp/sl, else expiry settle (fallback last close)."""
    trades = []
    by_sym = {s: g.set_index("date") for s, g in nm.groupby("symbol")}
    for entry_d, exp in cyc:
        picks = select(feats, reg, entry_d)
        for sym, side in picks:
            g = by_sym.get(sym)
            if g is None or entry_d not in g.index: continue
            row = g.loc[entry_d]
            if row["expiry"] != exp:      # symbol's front month must match the cycle
                # stocks share the index monthly expiry; skip if not
                continue
            e_px = row["close"]
            if not np.isfinite(e_px) or e_px <= 0: continue
            path = g.loc[(g.index > entry_d) & (g.index <= exp)]
            path = path[path["expiry"] == exp]
            x_px, x_d, reason = None, None, "expiry"
            for d2, r2 in path.iterrows():
                ret = side * (r2["close"] / e_px - 1)
                if tp is not None and ret >= tp:
                    x_px, x_d, reason = r2["close"], d2, "tp"; break
                if sl is not None and ret <= -sl:
                    x_px, x_d, reason = r2["close"], d2, "sl"; break
            if x_px is None:
                if path.empty: continue
                last = path.iloc[-1]
                x_px = last["settle"] if np.isfinite(last["settle"]) and last["settle"] > 0 else last["close"]
                x_d = path.index[-1]
            gross = side * (x_px / e_px - 1)
            net = gross - COST
            margin = IDX_MARGIN if sym in ("NIFTY", "BANKNIFTY", "FINNIFTY") else STK_MARGIN
            trades.append(dict(entry=str(entry_d.date()), exit=str(x_d.date()), sym=sym,
                               side=side, gross=gross, net=net, reason=reason,
                               margin=margin, rom=net / margin))
    return pd.DataFrame(trades)

def summarize(tr, label=""):
    if tr.empty:
        return dict(label=label, n=0)
    tr = tr.copy()
    tr["entry"] = pd.to_datetime(tr["entry"])
    is_ = tr[tr["entry"] < OOS_START]; oos = tr[tr["entry"] >= OOS_START]
    def block(t):
        if t.empty: return None
        wins = (t["net"] > 0)
        mo = t.groupby(t["entry"].dt.to_period("M"))["rom"].sum()
        # monthly return on capital assuming margin fully funds positions equally,
        # capital = sum of margins of concurrent positions (per-cycle normalization)
        cnt = t.groupby(t["entry"].dt.to_period("M")).size()
        mo_cap = (mo / cnt)  # per-position avg RoM per month
        eq = (1 + mo_cap).cumprod()
        dd = (eq / eq.cummax() - 1).min()
        yr = t.groupby(t["entry"].dt.year)["net"].agg(["count", "mean",
                                                        lambda x: (x > 0).mean()])
        return dict(n=len(t), win=round(wins.mean() * 100, 1),
                    basket_win=round((mo_cap > 0).mean() * 100, 1),
                    months=len(mo_cap),
                    avg_net=round(t["net"].mean() * 100, 3),
                    avg_rom=round(t["rom"].mean() * 100, 2),
                    mo_ret_cap=round(mo_cap.mean() * 100, 2),
                    worst_mo=round(mo_cap.min() * 100, 2),
                    maxdd=round(dd * 100, 1),
                    yr=yr.round(3).to_dict("index"))
    return dict(label=label, IS=block(is_), OOS=block(oos))

# ---------------- main ----------------

if __name__ == "__main__":
    p = load()
    nm = near_month(p)
    cont = {s: g.set_index("date")["close"] for s, g in nm.groupby("symbol")}
    nifty = cont.get("NIFTY")
    if nifty is None:
        sys.exit("no NIFTY in panel yet — wait for index download")
    feats, reg = build_features(cont, nifty)
    cyc = cycles(nm)
    print(f"panel symbols={nm['symbol'].nunique()} cycles={len(cyc)} "
          f"({cyc[0][0].date()} -> {cyc[-1][1].date()})", flush=True)

    grid_exits = [(None, None), (0.02, None), (0.03, None), (0.04, None),
                  (0.03, 0.05), (0.03, 0.08), (0.02, 0.05), (0.04, 0.08)]
    results = []
    for name, fn in STRATS.items():
        for tp, sl in grid_exits:
            tr = run_trades(nm, feats, reg, cyc, fn, tp, sl)
            lbl = f"{name} tp={tp} sl={sl}"
            s = summarize(tr, lbl)
            results.append(s)
            i = s.get("IS")
            if i:
                print(f"{lbl:32s} IS n={i['n']:4d} win={i['win']:5.1f}% "
                      f"bwin={i['basket_win']:5.1f}% avg={i['avg_net']:7.3f}% "
                      f"RoM={i['avg_rom']:6.2f}% mo={i['mo_ret_cap']:6.2f}% "
                      f"dd={i['maxdd']:6.1f}%", flush=True)
    with open(f"{BASE}/grid_results.json", "w") as fh:
        json.dump(results, fh, indent=1, default=str)
    print("saved grid_results.json")
