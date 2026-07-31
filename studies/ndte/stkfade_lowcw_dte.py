"""LOW-C/W RESCUE — the remaining config lever: DAYS TO EXPIRY.

Width, target and stop were swept in stkfade_lowcw_geometry.py. The engine's other structural
choice is WHICH expiry it sells: STOCK_CREDIT_MIN_DTE = 10 takes the first monthly expiry at
least 10 days out. Stock options are monthly-only, so raising that threshold rolls the trade to
the NEXT month -- much more premium, much more time at risk. Since the 0.30-0.40 band's problem
is thin premium, this is the one untested knob that attacks the cause directly.

Population is fixed: the band as defined at the reference (S2/W4, first expiry >= 10 DTE), so
"rescue" keeps meaning the same set of blocked signals. Only the expiry sold changes.
"""
import warnings; warnings.filterwarnings("ignore")
import sys, json, collections
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np, pandas as pd
from datetime import date, timedelta

PKL, UND_CACHE = "/tmp/bhav_stk.pkl", "/tmp/lowcw_underlyings.json"
REENTRY, MIN_PREM, MIN_OI = 3, 50.0, 1
REF_DTE, REF_SHORT, REF_WIDTH = 10, 2, 4
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
close_by_sym = json.load(open(UND_CACHE))

sig_union = {}
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
            if typ: sig_union.setdefault((ds, sym), (typ, float(c)))
sigs = sorted((date.fromisoformat(d), s, t, c) for (d, s), (t, c) in sig_union.items())

def legs(ks, atm, typ, S, W):
    si, li = (atm + S, atm + S + W) if typ == "CE" else (atm - S, atm - S - W)
    return (si, li) if 0 <= si < len(ks) and 0 <= li < len(ks) else None

def expiry_for(sym, typ, day, dte):
    fut = sorted(e for e in exps_by.get((sym, typ), ()) if date.fromisoformat(e) >= day + timedelta(days=dte))
    return fut[0] if fut else None

band = []; last = {}
for (day, sym, typ, c) in sigs:
    kk = (sym, typ)
    if last.get(kk) and (day - last[kk]).days < REENTRY: continue
    ds = day.isoformat()
    exp = expiry_for(sym, typ, day, REF_DTE)
    if not exp: continue
    P = PX[(sym, exp, typ)]
    if ds not in P["didx"] or len(P["ks"]) < REF_SHORT + REF_WIDTH + 2: continue
    di = P["didx"][ds]; ks = P["ks"]
    atm = int(np.argmin(np.abs(ks - c)))
    lg = legs(ks, atm, typ, REF_SHORT, REF_WIDTH)
    if not lg: continue
    si, li = lg
    se, le = P["C"][di, si], P["C"][di, li]
    if not np.isfinite(se) or not np.isfinite(le) or se < MIN_PREM: continue
    if not np.isfinite(P["O"][di, si]) or P["O"][di, si] < MIN_OI: continue
    credit = float(se - le); w = float(abs(ks[si] - ks[li]))
    if credit <= 0 or credit >= w: continue
    last[kk] = day
    if 0.30 <= credit / w < 0.40:
        band.append((day, sym, typ, c))

print(f"band population (defined at DTE>={REF_DTE}, S2/W4): {len(band)}\n", flush=True)

def run(recs, dte, S, W, TP, STOP):
    out = []
    for (day, sym, typ, c) in recs:
        exp = expiry_for(sym, typ, day, dte)
        if not exp: continue
        key = (sym, exp, typ)
        if key not in PX: continue
        P = PX[key]; ds = day.isoformat()
        if ds not in P["didx"]: continue
        di = P["didx"][ds]; ks = P["ks"]
        atm = int(np.argmin(np.abs(ks - c)))
        sel = legs(ks, atm, typ, S, W)
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
        hold = (date.fromisoformat(exp) - day).days
        out.append((day.year, net, w, int(net > 0), w - credit, credit / w, hold))
    return out

def line(t, lab):
    if len(t) < 20: print(f"{lab:<34} n={len(t):>4}  (too few)"); return
    n = len(t)
    yrs = collections.defaultdict(list)
    for x in t: yrs[x[0]].append(x)
    pos = sum(1 for g in yrs.values() if sum(a[1] for a in g) > 0)
    print(f"{lab:<34} n={n:>4}  win {sum(x[3] for x in t)/n*100:5.1f}%  "
          f"ROM {sum(x[1] for x in t)/sum(x[4] for x in t)*100:+7.1f}%  "
          f"net {sum(x[1] for x in t)/sum(x[2] for x in t)*100:+6.1f}%w  +ve {pos}/{len(yrs)}  "
          f"c/w {sum(x[5] for x in t)/n:.2f}  hold {sum(x[6] for x in t)/n:.0f}d  "
          f"net/lot {sum(x[1] for x in t)/n:+.2f}pts")

for W in (4, 2, 1):
    print(f"--- width {W} strike step(s), short 2-OTM, TP-40, no stop ---")
    for dte in (5, 10, 15, 20, 25, 30, 40, 55):
        line(run(band, dte, 2, W, 0.40, None), f"  DTE >= {dte}")
    print()

print("--- deployed exits (TP-50, stop-3x) for contrast, width 4 ---")
for dte in (10, 25, 40):
    line(run(band, dte, 2, 4, 0.50, 3.0), f"  DTE >= {dte}")
print("\nDONE-DTE")
