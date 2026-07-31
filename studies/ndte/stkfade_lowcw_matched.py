"""LOW-C/W RESCUE — matched-sample bias check.

The W1 re-cut prices 680 of the band's 782 signals; 102 drop out (short premium < Rs50 at the
new strike, or credit >= width). If those 102 are disproportionately the losers, the W1 vs
deployed comparison is rigged by selection rather than by geometry.

This re-runs the DEPLOYED geometry on exactly the 680 signals W1 keeps, and separately reports
the 102 it drops. Clean result = the deployed baseline stays bad on the matched subset.

Also reports physical-settlement exposure: NSE stock options are physically settled, so the
fraction of trades that reach expiry with the short strike in the money is an operational
number worth seeing, not just a P&L one.
"""
import warnings; warnings.filterwarnings("ignore")
import sys, json, collections
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np, pandas as pd
from datetime import date, timedelta

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

band = []; last = {}
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
        band.append((day, sym, typ, c, fut[0], di, atm))

def priceable(rec, S, W):
    (day, sym, typ, c, exp, di, atm) = rec
    P = PX[(sym, exp, typ)]; ks = P["ks"]
    sel = legs(ks, atm, typ, S, W)
    if not sel: return None
    si, li = sel
    se, le = P["C"][di, si], P["C"][di, li]
    if not np.isfinite(se) or not np.isfinite(le) or se < MIN_PREM: return None
    if not np.isfinite(P["O"][di, si]) or P["O"][di, si] < MIN_OI: return None
    credit = float(se - le); w = float(abs(ks[si] - ks[li]))
    if credit <= 0 or credit >= w: return None
    return si, li, credit, w, se, le

def run(recs, S, W, TP, STOP):
    out = []
    for rec in recs:
        pr = priceable(rec, S, W)
        if not pr: continue
        (day, sym, typ, c, exp, di, atm) = rec
        si, li, credit, w, se, le = pr
        P = PX[(sym, exp, typ)]; ks = P["ks"]
        path = P["C"][di + 1:, si] - P["C"][di + 1:, li]
        ok = np.isfinite(path); close = None; to_expiry = True
        if ok.any():
            hit_tp = ok & (path <= credit * (1 - TP)) if TP is not None else np.zeros(len(path), bool)
            hit_st = ok & (path >= credit * STOP) if STOP is not None else np.zeros(len(path), bool)
            hit = hit_tp | hit_st
            if hit.any():
                j = int(np.argmax(hit))
                close = max(float(path[j]), 0.0) if hit_tp[j] else min(float(path[j]), w)
                to_expiry = False
        itm = 0
        if close is None:
            cb = close_by_sym.get(sym, {})
            espot = cb[exp][0] if exp in cb else None
            if espot is None:
                prior = [x for x in cb if x <= exp]
                espot = cb[max(prior)][0] if prior else c
            sk, lk = float(ks[si]), float(ks[li])
            itm = int(espot > sk if typ == "CE" else espot < sk)
            intr = max(0.0, espot - sk) if typ == "CE" else max(0.0, sk - espot)
            intl = max(0.0, espot - lk) if typ == "CE" else max(0.0, lk - espot)
            close = min(max(intr - intl, 0.0), w)
        net = (credit - close) - (float(se) * spf(float(se)) + float(le) * spf(float(le))) / 100.0
        out.append((day.year, net, w, int(net > 0), w - credit, int(to_expiry), itm))
    return out

def rep(t, lab):
    if not t: print(f"{lab}: n=0"); return
    n = len(t)
    yrs = collections.defaultdict(list)
    for x in t: yrs[x[0]].append(x)
    pos = sum(1 for g in yrs.values() if sum(a[1] for a in g) > 0)
    print(f"{lab}")
    print(f"   n={n}  win {sum(x[3] for x in t)/n*100:.1f}%  ROM {sum(x[1] for x in t)/sum(x[4] for x in t)*100:+.1f}%"
          f"  net {sum(x[1] for x in t)/sum(x[2] for x in t)*100:+.1f}%w  +ve yrs {pos}/{len(yrs)}"
          f"  ·  held to expiry {sum(x[5] for x in t)/n*100:.0f}%  short ITM at expiry {sum(x[6] for x in t)/n*100:.0f}%")

kept = [r for r in band if priceable(r, 2, 1)]
drop = [r for r in band if not priceable(r, 2, 1)]
print(f"\nband={len(band)}  priceable at S2/W1={len(kept)}  dropped={len(drop)}\n")

print("=== MATCHED SAMPLE — same 680 signals, both geometries ===")
rep(run(kept, 2, 4, 0.50, 3.0), "  matched @ DEPLOYED S2/W4 TP-50 stop-3x")
rep(run(kept, 2, 4, 0.40, None), "  matched @ S2/W4 TP-40 no-stop")
rep(run(kept, 2, 1, 0.40, None), "  matched @ S2/W1 TP-40 no-stop   <- the candidate")
print("\n=== THE 102 SIGNALS W1 CANNOT PRICE (at deployed geometry) ===")
rep(run(drop, 2, 4, 0.50, 3.0), "  dropped @ DEPLOYED S2/W4 TP-50 stop-3x")
print("\n=== full band, for reference ===")
rep(run(band, 2, 4, 0.50, 3.0), "  all 782 @ DEPLOYED S2/W4 TP-50 stop-3x")
print("\nDONE-MATCHED")
