"""CANDLE-CONJUNCTION SEARCH (17-Sep-2026) — the untested class from the WR70 verdict.

Goal set by the user: a NON-SPREAD (directional, futures-style) strategy with >75% win AND positive
net after cost, more signals. WR70 swept single-feature quintile gates (3,550 cells, 0 survivors).
This sweeps CONJUNCTIONS: a completed 5-min candle PATTERN x a LEVEL x VOLUME/TIME, entering at the
pattern bar's close, first-touch stop/target grid, same IS 2022-24 / OOS 2025-26 split, same 3 bps
cost, same Bonferroni. Reuses studies/wr70_search.py for bars, base features and outcomes.
Outputs research/candle_conj/{is_scan.csv, oos_verdict.csv, report.txt}.
"""
import os, sys, itertools, json
import numpy as np, pandas as pd
sys.path.insert(0, "."); sys.path.insert(0, "studies")
import wr70_search as W
W.CACHE = "research/m1cache"; W.OUT = "research/candle_conj"; os.makedirs(W.OUT, exist_ok=True)
W.ENTRY_EVERY = 5                                    # a pattern can complete on ANY bar
SIDES = ["LONG", "SHORT"]; COST = W.COST_BPS; MIN_N = 150

PATTERNS = ["bull_engulf", "bear_engulf", "hammer", "star", "inside_break_up", "inside_break_dn"]

def candle_feats(d):
    o, h, l, c = d.o, d.h, d.l, d.c
    body = (c - o); rng = (h - l).replace(0, np.nan); ab = body.abs()
    uw = h - np.maximum(o, c); lw = np.minimum(o, c) - l
    po, pc_, ph, pl = o.shift(1), c.shift(1), h.shift(1), l.shift(1)
    d["bull_engulf"] = ((c > o) & (pc_ < po) & (c >= po) & (o <= pc_) & (ab >= 0.5 * rng)).astype(int)
    d["bear_engulf"] = ((c < o) & (pc_ > po) & (c <= po) & (o >= pc_) & (ab >= 0.5 * rng)).astype(int)
    d["hammer"] = ((lw >= 2.0 * ab) & (uw <= 0.25 * rng) & (ab <= 0.35 * rng)).astype(int)
    d["star"]   = ((uw >= 2.0 * ab) & (lw <= 0.25 * rng) & (ab <= 0.35 * rng)).astype(int)
    inside_prev = (ph <= h.shift(2)) & (pl >= l.shift(2))          # previous bar was an inside bar
    d["inside_break_up"] = (inside_prev & (c > ph)).astype(int)
    d["inside_break_dn"] = (inside_prev & (c < pl)).astype(int)
    d["any_pattern"] = d[PATTERNS].max(axis=1)
    return d

_orig_features = W.features
def features_plus(g, sym):
    return candle_feats(_orig_features(g, sym))
W.features = features_plus

# masked outcomes: only bars where a pattern completed (bounded compute, no lookahead)
def outcomes_masked(d):
    recs = []; S, R = len(W.STOPS), len(W.RATIOS)
    for _, day in d.groupby("date"):
        h = day.h.to_numpy(); l = day.l.to_numpy(); c = day.c.to_numpy(); m = day["min"].to_numpy()
        pat = day.any_pattern.to_numpy(); n = len(day)
        idx = np.where((m >= W.ENTRY_FROM) & (m <= W.ENTRY_TO) & (pat > 0))[0]
        for i in idx:
            if i + 2 >= n: continue
            e = c[i]; fh, fl, fc, fm = h[i+1:], l[i+1:], c[i+1:], m[i+1:]
            if len(fh) < 2: continue
            eod = min(np.searchsorted(fm, W.EOD_M), len(fc) - 1)
            up = (fh - e) / e * 1e4; dn = (e - fl) / e * 1e4
            res = np.full((2, S, R), np.nan)
            for si, stp in enumerate(W.STOPS):
                t_sl_L = np.argmax(dn >= stp) if (dn >= stp).any() else 10**9
                t_sl_S = np.argmax(up >= stp) if (up >= stp).any() else 10**9
                for ri, rat in enumerate(W.RATIOS):
                    tgt = stp * rat
                    t_tp_L = np.argmax(up >= tgt) if (up >= tgt).any() else 10**9
                    t_tp_S = np.argmax(dn >= tgt) if (dn >= tgt).any() else 10**9
                    for k, (t_tp, t_sl, sgn) in enumerate(((t_tp_L, t_sl_L, 1), (t_tp_S, t_sl_S, -1))):
                        if t_sl <= t_tp and t_sl <= eod: res[k, si, ri] = -stp
                        elif t_tp < t_sl and t_tp <= eod: res[k, si, ri] = tgt
                        else: res[k, si, ri] = (fc[eod] - e) / e * 1e4 * sgn
            recs.append((day.index[i], res))
    if not recs: return None, None
    return np.array([r[0] for r in recs]), np.stack([r[1] for r in recs])
W.outcomes = outcomes_masked
EXTRA = PATTERNS + ["any_pattern"]
W.FEATS = W.FEATS + EXTRA

def cell(r):
    r = r[~np.isnan(r)]; n = len(r)
    if n < MIN_N: return None
    net = r.mean() - COST; win = (r > 0).mean(); sd = r.std(ddof=1)
    t = net / (sd / np.sqrt(n)) if sd > 0 else 0.0
    return dict(n=n, win=win * 100, net=net, t=t)

if __name__ == "__main__":
    feats, arrs = [], []
    for s in W.SYMS:
        f, a = W.build(s)
        if f is None: print(f"  skip {s}", flush=True); continue
        feats.append(f); arrs.append(a); print(f"  {s:<12} {len(f):>7} pattern entries", flush=True)
    F = pd.concat(feats, ignore_index=True); A = np.concatenate(arrs, axis=0)
    F.to_pickle(os.path.join(W.OUT, "F.pkl")); np.savez_compressed(os.path.join(W.OUT, "A.npz"), arr=A)
    dates = pd.to_datetime(F.date).dt.date; mask_is = (dates <= W.IS_END).to_numpy(); mask_oos = ~mask_is
    mo_is = len({(d.year, d.month) for d in dates[mask_is]}); mo_oos = len({(d.year, d.month) for d in dates[mask_oos]})
    print(f"\nBUILT {len(F):,} pattern entries · IS months {mo_is} · OOS months {mo_oos}", flush=True)
    # conjunction gates
    lvl = {"any": np.ones(len(F), bool),
           "at_PDL": (F.dist_pdl_atr.to_numpy() <= 0.5), "at_PDH": (F.dist_pdh_atr.to_numpy() <= 0.5),
           "at_VWAP": (F.vwap_dev_bps.abs().to_numpy() <= 0.3 * F.atr_bps.to_numpy())}
    vol = {"anyvol": np.ones(len(F), bool), "surge": (F.vol_surge.to_numpy() >= 1.5)}
    tod = {"anytime": np.ones(len(F), bool), "first_hr": (F.tod.to_numpy() <= 10 * 60 + 30),
           "last_hr": (F.tod.to_numpy() >= 13 * 60 + 30)}
    gates = {}
    for p in PATTERNS:
        pm = F[p].to_numpy() > 0
        for ln, lm in lvl.items():
            for vn, vm in vol.items():
                for tn, tm in tod.items():
                    g = pm & np.nan_to_num(lm, nan=False) & np.nan_to_num(vm, nan=False) & tm
                    if g.sum() >= 2 * MIN_N: gates[f"{p}|{ln}|{vn}|{tn}"] = g
    n_tests = len(gates) * 2 * len(W.STOPS) * len(W.RATIOS)
    try:
        from scipy.stats import norm; z_b = norm.ppf(1 - 0.05 / (2 * n_tests))
    except Exception: z_b = 4.0
    rows = []
    for gn, gm in gates.items():
        for k, si, ri in itertools.product(range(2), range(len(W.STOPS)), range(len(W.RATIOS))):
            s = cell(A[gm & mask_is, k, si, ri]); 
            if s is None: continue
            o = cell(A[gm & mask_oos, k, si, ri]) or dict(n=0, win=np.nan, net=np.nan, t=np.nan)
            rows.append(dict(gate=gn, side=SIDES[k], stop=W.STOPS[si], ratio=W.RATIOS[ri],
                             n_is=s["n"], win_is=s["win"], net_is=s["net"], t_is=s["t"],
                             n_oos=o["n"], win_oos=o["win"], net_oos=o["net"], t_oos=o["t"]))
    R = pd.DataFrame(rows); R.to_csv(os.path.join(W.OUT, "is_scan.csv"), index=False)
    lines = [f"gates {len(gates)} · tests {n_tests:,} · Bonferroni z {z_b:.2f} · entries {len(F):,}"]
    cand = R[(R.net_is > 0) & (R.t_is > z_b) & (R.win_is >= 75)]
    lines.append(f"IS candidates (win>=75%, net>0, t>{z_b:.2f}): {len(cand)}")
    surv = cand[(cand.net_oos > 0) & (cand.win_oos >= 75) & (cand.n_oos >= 100)]
    lines.append(f"OOS SURVIVORS (win>=75% AND net>0 on >=100 OOS trades): {len(surv)}")
    ok = R[(R.n_oos >= 100)]
    if len(ok) > 10:
        lines.append(f"IS->OOS net correlation over {len(ok)} cells: {np.corrcoef(ok.net_is, ok.net_oos)[0,1]:+.3f}")
        lines.append(f"cells net-positive OOS: {(ok.net_oos>0).mean()*100:.1f}% (50% = no information)")
    for lbl, df in (("TOP IS cells", cand.sort_values('net_is', ascending=False).head(10)),
                    ("OOS SURVIVORS", surv.sort_values('net_oos', ascending=False).head(10))):
        lines.append(f"\n{lbl}:"); lines.append(df.to_string(index=False, float_format=lambda v: f"{v:7.2f}") if len(df) else "  none")
    open(os.path.join(W.OUT, "report.txt"), "w").write("\n".join(lines)); print("\n".join(lines))
    surv.to_csv(os.path.join(W.OUT, "oos_verdict.csv"), index=False)
