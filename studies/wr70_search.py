"""WR70 SEARCH — reverse-engineered hunt for a >=70% win-rate, >=3%/month intraday book.

NOT a fade and NOT a credit spread. This is a systematic gate search over intraday features,
with the geometry solved backwards from the target rather than copied from a source strategy.

REVERSE ENGINEERING (the spec this search must fill)
----------------------------------------------------
On a driftless walk with the stop at -1R, P(reach +kR first) = 1/(1+k), so a 70% win rate
means the target sits at k = 0.4286R and expectancy is exactly zero. Profit requires the
observed win rate to EXCEED that baseline:

    net_per_trade_bps = (w*k - (1-w)) * R_bps - cost_bps

Solving for the required w at cost = 3bps:

    R =   7 bps -> w >= 91.4%     (this is why the 1-min-candle stop of the sweep fade died:
    R =  20 bps -> w >= 80.5%      the cost was half the risk)
    R =  40 bps -> w >= 75.3%
    R =  60 bps -> w >= 73.5%
    R = 100 bps -> w >= 72.1%

Adding the 3%/month-on-margin hurdle (~20 trades/month, 7x leverage => 2.1 bps/trade net on
notional => 5.1 bps gross) at R = 60 bps gives the full spec:

    TARGET: win rate >= ~76% at k=0.43R with a ~60bps stop  ==>  ~6pp of edge over baseline.

So the geometry is fixed by arithmetic (wide stop, target at 0.43R) and the ONLY open question
is whether any entry gate delivers ~6pp. That is what this scans for.

METHOD
------
- 5-minute bars built from cached 1-minute data (see fetch note below).
- Candidate entries every 15 min, 09:30-14:30, on every instrument.
- 14 no-lookahead features computed at the entry bar's close.
- Univariate gate scan: each feature x quintile bucket x {long, short}.
- Geometry grid: stop in {20,30,50,80,120} bps x target ratio in {0.25,0.43,0.6,1.0,1.5}.
- IN-SAMPLE 2022-2024 for the search; OUT-OF-SAMPLE 2025-2026 reported as the verdict.
- Multiple testing: Bonferroni on the IS scan, and an OOS confirmation that was never searched.

Honest expectation: most or all gates will fail OOS. The point of the harness is that a
survivor, if one exists, is one that was never fitted to the data it is judged on.

DATA: /tmp/m1cache/{SYM}_{YYYY-MM}.csv.gz, from Upstox v3 historical-candle (public, no auth):
  https://api.upstox.com/v3/historical-candle/{urlencoded_key}/minutes/1/{to}/{from}
  1-min history starts Jan 2022. See ~/files/HANDOFF-turtlesoup.md for the fetchers.
"""
import os, sys, glob, json, itertools
import numpy as np
import pandas as pd
from datetime import time as dtime, date

CACHE = "/tmp/m1cache"
OUT = "/tmp/wr70"
os.makedirs(OUT, exist_ok=True)

COST_BPS = 3.0
SESS_START, SESS_END = dtime(9, 15), dtime(15, 29)
ENTRY_FROM, ENTRY_TO = 9 * 60 + 30, 14 * 60 + 30
ENTRY_EVERY = 15          # minutes between candidate entries
EOD_M = 15 * 60 + 20

STOPS = np.array([20.0, 30.0, 50.0, 80.0, 120.0])        # bps
RATIOS = np.array([0.25, 0.4286, 0.6, 1.0, 1.5])         # target = ratio * stop
IS_END = date(2024, 12, 31)

INDICES = {"NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY", "NEXT50"}
SYMS = ["NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY", "NEXT50",
        "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK",
        "KOTAKBANK", "ITC", "LT", "BHARTIARTL", "MARUTI", "TATASTEEL", "JSWSTEEL",
        "SUNPHARMA", "HINDUNILVR", "TITAN", "BAJFINANCE", "ADANIENT", "ONGC",
        "NTPC", "POWERGRID", "COALINDIA", "HINDALCO"]


# ── data ──────────────────────────────────────────────────────────────────────

def load5(sym):
    """1-min cache -> 5-min bars, regular session only."""
    files = sorted(glob.glob(os.path.join(CACHE, f"{sym}_*.csv.gz")))
    if not files:
        return None
    parts = []
    for f in files:
        try:
            d = pd.read_csv(f, parse_dates=["ts"])
            if len(d):
                parts.append(d)
        except Exception:
            pass
    if not parts:
        return None
    df = pd.concat(parts, ignore_index=True).sort_values("ts")
    t = df.ts.dt.time
    df = df[(t >= SESS_START) & (t <= SESS_END)].set_index("ts")
    g = df.resample("5min").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"),
                                c=("c", "last"), v=("v", "sum")).dropna(subset=["o"])
    g = g.reset_index()
    g["date"] = g.ts.dt.date
    g["min"] = g.ts.dt.hour * 60 + g.ts.dt.minute
    n = g.groupby("date").size()
    return g[g.date.isin(n[n >= 60].index)].reset_index(drop=True)


# ── features (all computed at the entry bar's close — no lookahead) ───────────

def features(g, sym):
    d = g.copy()
    is_idx = sym in INDICES
    day = d.groupby("date")

    d["day_open"] = day.o.transform("first")
    d["run_hi"] = day.h.cummax()
    d["run_lo"] = day.l.cummin()
    prev_close = day.c.last().shift(1)
    prev_hi = day.h.max().shift(1)
    prev_lo = day.l.min().shift(1)
    prev_ret = (day.c.last() / day.o.first() - 1).shift(1) * 1e4
    d["prev_close"] = d.date.map(prev_close)
    d["prev_hi"] = d.date.map(prev_hi)
    d["prev_lo"] = d.date.map(prev_lo)
    d["prev_ret"] = d.date.map(prev_ret)

    # true range -> ATR in bps (20 bars, shifted so the current bar is excluded)
    pc = d.c.shift(1)
    tr = np.maximum(d.h - d.l, np.maximum((d.h - pc).abs(), (d.l - pc).abs()))
    d["atr_bps"] = (tr.rolling(20).mean().shift(1) / d.c) * 1e4

    d["gap_bps"] = (d.day_open - d.prev_close) / d.prev_close * 1e4
    d["ret_open_bps"] = (d.c - d.day_open) / d.day_open * 1e4
    rng = (d.run_hi - d.run_lo).replace(0, np.nan)
    d["pos_in_range"] = (d.c - d.run_lo) / rng
    d["mom_30_bps"] = (d.c / d.c.shift(6) - 1) * 1e4
    d["mom_5_bps"] = (d.c / d.c.shift(1) - 1) * 1e4
    d["dist_pdh_atr"] = (d.prev_hi - d.c) / d.c * 1e4 / d.atr_bps
    d["dist_pdl_atr"] = (d.c - d.prev_lo) / d.c * 1e4 / d.atr_bps
    d["rng_so_far_atr"] = (d.run_hi - d.run_lo) / d.c * 1e4 / d.atr_bps
    d["tod"] = d["min"]
    d["dow"] = pd.to_datetime(pd.Series(d.date.values)).dt.dayofweek.to_numpy()

    # session VWAP deviation and volume surge — stocks only (indices carry no volume)
    if not is_idx:
        tp = (d.h + d.l + d.c) / 3
        cum_pv = (tp * d.v).groupby(d.date).cumsum()
        cum_v = d.v.groupby(d.date).cumsum().replace(0, np.nan)
        d["vwap_dev_bps"] = (d.c - cum_pv / cum_v) / d.c * 1e4
        vmean = d.v.rolling(78 * 5).mean().shift(1)
        d["vol_surge"] = d.v.rolling(6).sum().shift(0) / (vmean * 6)
    else:
        d["vwap_dev_bps"] = np.nan
        d["vol_surge"] = np.nan

    # consecutive same-direction 5-min bars
    sgn = np.sign(d.c - d.o)
    streak = np.zeros(len(d))
    for i in range(1, len(d)):
        streak[i] = streak[i - 1] + sgn.iloc[i] if sgn.iloc[i] == sgn.iloc[i - 1] else sgn.iloc[i]
    d["streak"] = streak
    return d


FEATS = ["gap_bps", "ret_open_bps", "pos_in_range", "mom_30_bps", "mom_5_bps",
         "dist_pdh_atr", "dist_pdl_atr", "rng_so_far_atr", "atr_bps", "streak",
         "vwap_dev_bps", "vol_surge", "prev_ret", "tod"]


# ── outcomes: first-touch over the whole geometry grid, vectorised per entry ───

def outcomes(d):
    """For every candidate entry bar, the (stop x ratio x side) first-touch return in bps."""
    recs = []
    S, R = len(STOPS), len(RATIOS)
    for _, day in d.groupby("date"):
        h = day.h.to_numpy(); l = day.l.to_numpy(); c = day.c.to_numpy()
        m = day["min"].to_numpy(); n = len(day)
        idx = np.where((m >= ENTRY_FROM) & (m <= ENTRY_TO) &
                       ((m - ENTRY_FROM) % ENTRY_EVERY == 0))[0]
        for i in idx:
            if i + 2 >= n:
                continue
            e = c[i]
            fh, fl, fc, fm = h[i + 1:], l[i + 1:], c[i + 1:], m[i + 1:]
            if len(fh) < 2:
                continue
            eod = np.searchsorted(fm, EOD_M)
            eod = min(eod, len(fc) - 1)
            up = (fh - e) / e * 1e4          # favourable excursion for a long
            dn = (e - fl) / e * 1e4
            res = np.full((2, S, R), np.nan)
            for si, stp in enumerate(STOPS):
                # long: stop below (dn >= stp), target above (up >= tgt)
                t_sl_L = np.argmax(dn >= stp) if (dn >= stp).any() else 10**9
                t_sl_S = np.argmax(up >= stp) if (up >= stp).any() else 10**9
                for ri, rat in enumerate(RATIOS):
                    tgt = stp * rat
                    t_tp_L = np.argmax(up >= tgt) if (up >= tgt).any() else 10**9
                    t_tp_S = np.argmax(dn >= tgt) if (dn >= tgt).any() else 10**9
                    # stop priority on ties (same bar could touch both)
                    for k, (t_tp, t_sl, sgn) in enumerate(((t_tp_L, t_sl_L, 1),
                                                           (t_tp_S, t_sl_S, -1))):
                        if t_sl <= t_tp and t_sl <= eod:
                            res[k, si, ri] = -stp
                        elif t_tp < t_sl and t_tp <= eod:
                            res[k, si, ri] = tgt
                        else:
                            res[k, si, ri] = (fc[eod] - e) / e * 1e4 * sgn
            recs.append((day.index[i], res))
    if not recs:
        return None, None
    ii = np.array([r[0] for r in recs])
    arr = np.stack([r[1] for r in recs])          # (n_entries, 2, S, R)
    return ii, arr


def build(sym):
    p = os.path.join(OUT, f"{sym}.npz")
    if os.path.exists(p):
        z = np.load(p, allow_pickle=True)
        return pd.read_pickle(os.path.join(OUT, f"{sym}_f.pkl")), z["arr"]
    g = load5(sym)
    if g is None or g.date.nunique() < 300:
        return None, None
    d = features(g, sym)
    ii, arr = outcomes(d)
    if ii is None:
        return None, None
    f = d.loc[ii, ["date"] + FEATS].reset_index(drop=True)
    f["sym"] = sym
    f.to_pickle(os.path.join(OUT, f"{sym}_f.pkl"))
    np.savez_compressed(p, arr=arr)
    return f, arr


if __name__ == "__main__":
    feats, arrs = [], []
    for s in SYMS:
        f, a = build(s)
        if f is None:
            print(f"  skip {s}", flush=True); continue
        feats.append(f); arrs.append(a)
        print(f"  {s:<12} {len(f):>7} entries", flush=True)
    F = pd.concat(feats, ignore_index=True)
    A = np.concatenate(arrs, axis=0)
    F.to_pickle(os.path.join(OUT, "F.pkl"))
    np.savez_compressed(os.path.join(OUT, "A.npz"), arr=A)
    print(f"\nBUILT {len(F):,} candidate entries x {A.shape[1]} sides x "
          f"{A.shape[2]} stops x {A.shape[3]} ratios")
