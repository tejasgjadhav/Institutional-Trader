"""LOW-C/W RESCUE — controls for stkfade_lowcw_geometry.py.

The band sweep is only worth reading if the same harness reproduces the numbers the deployed
book is already known to produce. This script runs, on identical machinery:

  A  FAITHFULNESS — c/w>=0.40 population at the deployed v2 config (S2/W4, TP-50, stop-3x).
                    Known IS target: ~370 trades, ~84% win, ~+25.7% of width, +ve 6/6 years.
  B  CONTROL      — the same c/w>=0.40 population at the band's winning config (W1, no stop).
                    If W1 also beats S2/W4 here, the finding is "narrow width is better
                    everywhere", not "the 0.30-0.40 band can be rescued".
  C  DETAIL       — per-year detail for the band's leading configs.
  D  SCALE        — average margin and net in POINTS, so the rupee size of a W1 trade is visible.
                    ROM says nothing about whether a trade is worth placing.
  E  NO-GATE      — the whole priced population (every c/w) at the winning config, i.e. what
                    happens if the gate is dropped entirely.
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys, json, collections
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np, pandas as pd
from datetime import date, timedelta
from engine.config import UNIVERSE

PKL, UND_CACHE = "/tmp/bhav_stk.pkl", "/tmp/lowcw_underlyings.json"
MIN_DTE, REENTRY, MIN_PREM, MIN_OI = 10, 3, 50.0, 1
REF_SHORT, REF_WIDTH = 2, 4
def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0

print("loading…", flush=True)
big = pd.read_pickle(PKL)
bdays = sorted(big["DAY"].astype(str).unique()); bset = set(bdays)
PX = {}
for key, sub in big.groupby(["SYM", "EXP", "TYP"], observed=True):
    c = sub.pivot_table(index="DAY", columns="STRIKE", values="CLOSE", aggfunc="last")
    o = sub.pivot_table(index="DAY", columns="STRIKE", values="OI", aggfunc="last")
    days = [str(d) for d in c.index]
    PX[(str(key[0]), str(key[1]), str(key[2]))] = dict(
        ks=np.asarray(c.columns, dtype="float64"), days=days,
        didx={d: i for i, d in enumerate(days)},
        C=c.values.astype("float32"), O=o.reindex_like(c).values.astype("float32"))
del big
exps_by = collections.defaultdict(set)
for (sym, e, t) in PX: exps_by[(sym, t)].add(e)
close_by_sym = json.load(open(UND_CACHE))
print(f"  {len(PX):,} chains, {len(close_by_sym)} underlyings", flush=True)

DCS = [5, 10, 15, 20]
sig_union = {}
for sym, bars in close_by_sym.items():
    days = sorted(bars)
    cl = np.array([bars[d][0] for d in days]); hi = np.array([bars[d][1] for d in days])
    lo = np.array([bars[d][2] for d in days])
    for dc in DCS:
        for i in range(max(dc, 20), len(days) - 1):
            ds = days[i]
            if ds not in bset: continue
            c = cl[i]
            typ = "CE" if c > hi[i - dc:i].max() else ("PE" if c < lo[i - dc:i].min() else None)
            if typ: sig_union.setdefault((ds, sym), (typ, float(c)))
sigs = sorted((date.fromisoformat(d), s, t, c) for (d, s), (t, c) in sig_union.items())

def legs_steps(ks, atm, typ, S, W):
    si, li = (atm + S, atm + S + W) if typ == "CE" else (atm - S, atm - S - W)
    if si < 0 or li < 0 or si >= len(ks) or li >= len(ks): return None
    return si, li

# ── population, split by reference c/w ─────────────────────────────────────
pops = {"band": [], "gate": [], "low": [], "all": []}
last = {}
for (day, sym, typ, c) in sigs:
    kk = (sym, typ)
    if last.get(kk) and (day - last[kk]).days < REENTRY: continue
    ds = day.isoformat()
    fut = sorted(e for e in exps_by.get(kk, ()) if date.fromisoformat(e) >= day + timedelta(days=MIN_DTE))
    if not fut: continue
    P = PX[(sym, fut[0], typ)]
    if ds not in P["didx"] or len(P["ks"]) < REF_SHORT + REF_WIDTH + 2: continue
    di = P["didx"][ds]; ks = P["ks"]
    atm = int(np.argmin(np.abs(ks - c)))
    lg = legs_steps(ks, atm, typ, REF_SHORT, REF_WIDTH)
    if not lg: continue
    si, li = lg
    se, le = P["C"][di, si], P["C"][di, li]
    if not np.isfinite(se) or not np.isfinite(le) or se < MIN_PREM: continue
    if not np.isfinite(P["O"][di, si]) or P["O"][di, si] < MIN_OI: continue
    credit = float(se - le); w = float(abs(ks[si] - ks[li]))
    if credit <= 0 or credit >= w: continue
    last[kk] = day
    rec = (day, sym, typ, c, fut[0], di, atm)
    cw = credit / w
    pops["all"].append(rec)
    pops["gate" if cw >= 0.40 else ("band" if cw >= 0.30 else "low")].append(rec)
print({k: len(v) for k, v in pops.items()}, flush=True)

def evaluate(pop, S, W, TP, STOP):
    out = []
    for (day, sym, typ, c, exp, di, atm) in pop:
        P = PX[(sym, exp, typ)]; ks = P["ks"]
        sel = legs_steps(ks, atm, typ, S, W)
        if not sel: continue
        si, li = sel
        se, le = P["C"][di, si], P["C"][di, li]
        if not np.isfinite(se) or not np.isfinite(le) or se < MIN_PREM: continue
        if not np.isfinite(P["O"][di, si]) or P["O"][di, si] < MIN_OI: continue
        credit = float(se - le); w = float(abs(ks[si] - ks[li]))
        if credit <= 0 or credit >= w: continue
        path = P["C"][di + 1:, si] - P["C"][di + 1:, li]
        ok = np.isfinite(path); close = None
        if ok.any():
            hit_tp = ok & (path <= credit * (1 - TP)) if TP is not None else np.zeros(len(path), bool)
            hit_st = ok & (path >= credit * STOP) if STOP is not None else np.zeros(len(path), bool)
            hit = hit_tp | hit_st
            if hit.any():
                j = int(np.argmax(hit))
                close = max(float(path[j]), 0.0) if hit_tp[j] else min(float(path[j]), w)
        if close is None:
            cb = close_by_sym.get(sym, {})
            espot = cb[exp][0] if exp in cb else None
            if espot is None:
                prior = [x for x in cb if x <= exp]
                espot = cb[max(prior)][0] if prior else c
            sk, lk = float(ks[si]), float(ks[li])
            intr = max(0.0, espot - sk) if typ == "CE" else max(0.0, sk - espot)
            intl = max(0.0, espot - lk) if typ == "CE" else max(0.0, lk - espot)
            close = min(max(intr - intl, 0.0), w)
        net = (credit - close) - (float(se) * spf(float(se)) + float(le) * spf(float(le))) / 100.0
        out.append((day.year, net, w, int(net > 0), w - credit, credit))
    return out

def rep(t, lab):
    if not t: print(f"{lab}: no trades"); return
    n = len(t)
    win = sum(x[3] for x in t) / n * 100
    rom = sum(x[1] for x in t) / sum(x[4] for x in t) * 100
    netw = sum(x[1] for x in t) / sum(x[2] for x in t) * 100
    by = collections.defaultdict(list)
    for x in t: by[x[0]].append(x)
    yrs = {y: sum(a[1] for a in g) / sum(a[4] for a in g) * 100 for y, g in by.items()}
    pos = sum(1 for v in yrs.values() if v > 0)
    avg_margin = sum(x[4] for x in t) / n; avg_net = sum(x[1] for x in t) / n
    avg_cw = sum(x[5] / x[2] for x in t) / n
    print(f"\n{lab}")
    print(f"  n={n}  win {win:.1f}%  ROM {rom:+.1f}%  net {netw:+.1f}% of width  +ve yrs {pos}/{len(yrs)}")
    print(f"  avg margin {avg_margin:.1f} pts/lot · avg net {avg_net:+.2f} pts/lot · avg c/w at this geometry {avg_cw:.2f}")
    print("  " + "  ".join(f"{y}:{v:+.0f}%" for y, v in sorted(yrs.items())))

print("\n" + "=" * 78)
print("A  FAITHFULNESS — does this harness reproduce the deployed book?")
print("=" * 78)
rep(evaluate(pops["gate"], 2, 4, 0.50, 3.0), "c/w>=0.40 @ DEPLOYED v2 (S2/W4 TP-50 stop-3x)  [target ~84% win, ~+25.7%w]")

print("\n" + "=" * 78)
print("B  CONTROL — is narrow width better EVERYWHERE, or only in the band?")
print("=" * 78)
for (S, W, TP, ST, tag) in [(2, 1, 0.40, None, ""), (2, 1, 0.50, None, ""), (1, 1, 0.50, None, ""),
                            (2, 4, 0.40, None, "  <- deployed geometry, no stop")]:
    rep(evaluate(pops["gate"], S, W, TP, ST), f"c/w>=0.40 @ S{S}/W{W} TP-{int(TP*100)} no-stop{tag}")

print("\n" + "=" * 78)
print("C+D  BAND detail + trade SIZE")
print("=" * 78)
rep(evaluate(pops["band"], 2, 4, 0.50, 3.0), "BAND @ deployed v2 config (the do-nothing baseline)")
for (S, W, TP) in [(0, 1, 0.75), (0, 1, 0.50), (2, 1, 0.40), (2, 1, 0.50), (1, 1, 0.40), (3, 1, 0.40)]:
    rep(evaluate(pops["band"], S, W, TP, None), f"BAND @ S{S}/W{W} TP-{int(TP*100)} no-stop")

print("\n" + "=" * 78)
print("E  NO-GATE — every priced signal, winning config (what if the gate goes away?)")
print("=" * 78)
rep(evaluate(pops["all"], 2, 1, 0.40, None), "ALL c/w @ S2/W1 TP-40 no-stop")
rep(evaluate(pops["low"], 2, 1, 0.40, None), "c/w<0.30 only @ S2/W1 TP-40 no-stop")
print("\nDONE-CONTROLS")
