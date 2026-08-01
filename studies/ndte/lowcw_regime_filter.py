"""LAST OPEN LEVER on the dead 0.30-0.35 band: a CALM-REGIME entry filter.

Everything else has been tried and failed. 432 configurations — geometry (strike-step short 0-3 x
width 1-5, and percent-of-spot short 1-4% x width 2-6%), targets 40/50/75/hold, stops none/2x/3x —
plus a DTE sweep 5->55 and adaptive-width rules. The sub-band split then showed the 0.30-0.35 half
is the dead one: +0.2% on margin in 2019-Sep'24 and -5.2% in Oct'24-Jul'26. Only the 0.35-0.40 half
survived, and that is now deployed as v0.

ONE PRE-REGISTERED HYPOTHESIS, not a sweep. This repo already has a VALIDATED calm-regime filter on
the 0DTE book: skip the week when 5-day realized vol is elevated, which took it 85.0% -> 87.8% win
and +3.2% -> +4.0% of margin. Mechanism: a short-premium book is paid for fear that has ALREADY been
priced, so it does badly when the tape is hot going in. If anything rescues the thin-premium band,
that is the candidate — thin credit plus a hot tape is exactly the losing combination.

HYPOTHESIS (fixed before looking): on the 0.30-0.35 band, entries taken when the UNDERLYING's 5-day
realized vol is LOW outperform entries taken when it is high, enough to turn the band positive.

BAR, also fixed before looking, per the repo's own rules:
  - must be positive in BOTH windows, not just one;
  - must hold across a THRESHOLD NEIGHBOURHOOD, not at one magic cut;
  - must keep enough trades to matter (>= ~100 in-sample);
  - if it only works in-sample it is REJECTED, like the width-1 re-cut before it.
In-sample runs first. If the band does not clearly turn positive here, the OOS run is NOT worth its
~3-5 hours of throttled API calls and the band stays rejected.
"""
import warnings; warnings.filterwarnings("ignore")
import sys, json, collections
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np, pandas as pd
from datetime import date, timedelta

PKL, UND = "/tmp/bhav_stk.pkl", "/tmp/lowcw_underlyings.json"
MIN_DTE, REENTRY, MIN_PREM, MIN_OI = 10, 3, 50.0, 1
S, W, TP, STOP = 2, 4, 0.40, None          # v0's exits, v2's geometry
BAND = (0.30, 0.35)                         # THE DEAD HALF — the whole point of this test
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
        ks=np.asarray(c.columns, dtype="float64"), didx={d: i for i, d in enumerate(days)},
        C=c.values.astype("float32"), O=o.reindex_like(c).values.astype("float32"))
del big
exps_by = collections.defaultdict(set)
for (sym, e, t) in PX: exps_by[(sym, t)].add(e)
close_by_sym = json.load(open(UND))

# rv5 per (symbol, day): 5-day realized vol from PRIOR closes only, so it is final before entry
RV = {}
for sym, bars in close_by_sym.items():
    days = sorted(bars); cl = np.array([bars[d][0] for d in days])
    r = np.diff(cl) / cl[:-1]
    for i in range(6, len(days)):
        RV[(sym, days[i])] = float(np.std(r[i - 6:i - 1]) * 100)

sig = {}
for sym, bars in close_by_sym.items():
    days = sorted(bars)
    cl = np.array([bars[d][0] for d in days]); hi = np.array([bars[d][1] for d in days])
    lo = np.array([bars[d][2] for d in days])
    for dc in (5, 10, 15, 20):
        for i in range(max(dc, 20), len(days) - 1):
            ds = days[i]
            if ds not in bset: continue
            c = cl[i]
            typ = "CE" if c > hi[i - dc:i].max() else ("PE" if c < lo[i - dc:i].min() else None)
            if typ: sig.setdefault((ds, sym), (typ, float(c)))
sigs = sorted((date.fromisoformat(d), s, t, c) for (d, s), (t, c) in sig.items())

trades = []; last = {}
for (day, sym, typ, c) in sigs:
    kk = (sym, typ)
    if last.get(kk) and (day - last[kk]).days < REENTRY: continue
    ds = day.isoformat()
    fut = sorted(e for e in exps_by.get(kk, ()) if date.fromisoformat(e) >= day + timedelta(days=MIN_DTE))
    if not fut: continue
    P = PX[(sym, fut[0], typ)]
    if ds not in P["didx"]: continue
    di = P["didx"][ds]; ks = P["ks"]
    atm = int(np.argmin(np.abs(ks - c)))
    si, li = (atm + S, atm + S + W) if typ == "CE" else (atm - S, atm - S - W)
    if not (0 <= si < len(ks) and 0 <= li < len(ks)): continue
    se, le = P["C"][di, si], P["C"][di, li]
    if not np.isfinite(se) or not np.isfinite(le) or se < MIN_PREM: continue
    if not np.isfinite(P["O"][di, si]) or P["O"][di, si] < MIN_OI: continue
    credit = float(se - le); w = float(abs(ks[si] - ks[li]))
    if credit <= 0 or credit >= w: continue
    last[kk] = day
    cw = credit / w
    if not (BAND[0] <= cw < BAND[1]): continue
    rv = RV.get((sym, ds))
    if rv is None: continue
    path = P["C"][di + 1:, si] - P["C"][di + 1:, li]
    ok = np.isfinite(path); close = None
    if ok.any():
        tp_hit = ok & (path <= credit * (1 - TP))
        st_hit = ok & (path >= credit * STOP) if STOP else np.zeros(len(path), bool)
        hit = tp_hit | st_hit
        if hit.any():
            j = int(np.argmax(hit))
            close = max(float(path[j]), 0.0) if tp_hit[j] else min(float(path[j]), w)
    if close is None:
        cb = close_by_sym.get(sym, {})
        espot = cb[fut[0]][0] if fut[0] in cb else None
        if espot is None:
            pr = [x for x in cb if x <= fut[0]]
            espot = cb[max(pr)][0] if pr else c
        sk, lk = float(ks[si]), float(ks[li])
        intr = max(0.0, espot - sk) if typ == "CE" else max(0.0, sk - espot)
        intl = max(0.0, espot - lk) if typ == "CE" else max(0.0, lk - espot)
        close = min(max(intr - intl, 0.0), w)
    net = (credit - close) - (float(se) * spf(float(se)) + float(le) * spf(float(le))) / 100.0
    trades.append(dict(y=day.year, net=net, margin=w - credit, win=int(net > 0), rv=rv))

print(f"\n0.30-0.35 band, 2019 -> Sep 2024: {len(trades)} trades with an rv5 reading\n")
def rep(t, lab):
    if len(t) < 10: print(f"{lab:<34} n={len(t):>4}  (too few to read)"); return
    n = len(t); nm = sum(x["net"] for x in t); mg = sum(x["margin"] for x in t)
    by = collections.defaultdict(list)
    for x in t: by[x["y"]].append(x)
    pos = sum(1 for g in by.values() if sum(a["net"] for a in g) > 0)
    print(f"{lab:<34} n={n:>4}  win {sum(x['win'] for x in t)/n*100:5.1f}%  "
          f"ROM {nm/mg*100:+7.1f}%  +ve yrs {pos}/{len(by)}")

rep(trades, "ALL (no filter — the baseline)")
print()
qs = np.percentile([x["rv"] for x in trades], [20, 30, 40, 50, 60])
print("threshold NEIGHBOURHOOD — calm side (rv5 below the cut):")
for q, lbl in zip(qs, ["20th pct", "30th pct", "40th pct", "median", "60th pct"]):
    rep([x for x in trades if x["rv"] <= q], f"  rv5 <= {q:.2f}%  ({lbl})")
print("\nthe HOT side, which the hypothesis says should be worse:")
for q, lbl in zip(qs, ["20th pct", "30th pct", "40th pct", "median", "60th pct"]):
    rep([x for x in trades if x["rv"] > q], f"  rv5 >  {q:.2f}%  ({lbl})")
print("\nDONE-REGIME")
