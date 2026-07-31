"""LOW-C/W RESCUE — the deployable form: ADAPTIVE WIDTH.

The band sweep showed the 0.30-0.40 signals are not premium-poor. Priced at width 4 their
credit/width is 0.34 and they lose money; priced at width 1 the SAME signals show c/w 0.42 and
88% win / +18% ROM. The gate was never the problem -- the fixed width was. A spread's c/w is a
function of how far the wing sits, so holding width constant and rejecting on c/w rejects names
whose strike ladder is coarse relative to their premium, not names whose premium is thin.

So the change to test is not "add a second book at width 1". It is: keep the c/w >= 0.40 gate
exactly as it is, and let the engine CHOOSE the width that clears it.

Rules compared (all on the full priced UNION population, IS 2019 -> Sep'24):
  DEPLOYED   width 4 fixed, take it only if c/w >= 0.40, TP-50, stop-3x
  NOSTOP     as deployed but no stop            (isolates the stop, geometry untouched)
  ADAPT-W    widest width in {4,2,1} that clears c/w >= 0.40, TP-40, no stop
  ADAPT-41   width 4 if it clears 0.40, else width 1 if IT clears 0.40, TP-40, no stop
  ADAPT-1ANY width 4 if it clears 0.40, else width 1 unconditionally, TP-40, no stop
Reported per rule and split by which population each trade came from, because the honest
question is what the CHANGE adds, not what the book totals.
"""
import warnings; warnings.filterwarnings("ignore")
import sys, json, collections
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np, pandas as pd
from datetime import date, timedelta

PKL, UND_CACHE = "/tmp/bhav_stk.pkl", "/tmp/lowcw_underlyings.json"
MIN_DTE, REENTRY, MIN_PREM, MIN_OI, GATE = 10, 3, 50.0, 1, 0.40
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

def quote(P, di, ks, atm, typ, S, W):
    si, li = (atm + S, atm + S + W) if typ == "CE" else (atm - S, atm - S - W)
    if not (0 <= si < len(ks) and 0 <= li < len(ks)): return None
    se, le = P["C"][di, si], P["C"][di, li]
    if not np.isfinite(se) or not np.isfinite(le) or se < MIN_PREM: return None
    if not np.isfinite(P["O"][di, si]) or P["O"][di, si] < MIN_OI: return None
    credit = float(se - le); w = float(abs(ks[si] - ks[li]))
    if credit <= 0 or credit >= w: return None
    return dict(si=si, li=li, credit=credit, w=w, se=float(se), le=float(le), cw=credit / w)

# priced population, tagged by reference c/w
pop = []; last = {}
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
    q = quote(P, di, ks, atm, typ, REF_SHORT, REF_WIDTH)
    if not q: continue
    last[kk] = day
    tag = "gate" if q["cw"] >= GATE else ("band" if q["cw"] >= 0.30 else "low")
    pop.append((day, sym, typ, c, fut[0], di, atm, tag))
print(f"priced population {len(pop)}  " + str(collections.Counter(p[7] for p in pop)), flush=True)

def settle(rec, q, TP, STOP):
    (day, sym, typ, c, exp, di, atm, tag) = rec
    P = PX[(sym, exp, typ)]; ks = P["ks"]
    credit, w, si, li = q["credit"], q["w"], q["si"], q["li"]
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
    net = (credit - close) - (q["se"] * spf(q["se"]) + q["le"] * spf(q["le"])) / 100.0
    return (day.year, net, w, int(net > 0), w - credit, tag, q["w"])

def apply_rule(rule):
    out = []
    for rec in pop:
        (day, sym, typ, c, exp, di, atm, tag) = rec
        P = PX[(sym, exp, typ)]; ks = P["ks"]
        pickd = rule(P, di, ks, atm, typ)
        if not pickd: continue
        q, TP, STOP = pickd
        out.append(settle(rec, q, TP, STOP))
    return out

def r_deployed(P, di, ks, atm, typ):
    q = quote(P, di, ks, atm, typ, 2, 4)
    return (q, 0.50, 3.0) if q and q["cw"] >= GATE else None

def r_nostop(P, di, ks, atm, typ):
    q = quote(P, di, ks, atm, typ, 2, 4)
    return (q, 0.40, None) if q and q["cw"] >= GATE else None

def r_adapt_w(P, di, ks, atm, typ):
    for W in (4, 2, 1):
        q = quote(P, di, ks, atm, typ, 2, W)
        if q and q["cw"] >= GATE: return (q, 0.40, None)
    return None

def r_adapt_41(P, di, ks, atm, typ):
    q = quote(P, di, ks, atm, typ, 2, 4)
    if q and q["cw"] >= GATE: return (q, 0.40, None)
    q1 = quote(P, di, ks, atm, typ, 2, 1)
    if q1 and q1["cw"] >= GATE: return (q1, 0.40, None)
    return None

def r_adapt_1any(P, di, ks, atm, typ):
    q = quote(P, di, ks, atm, typ, 2, 4)
    if q and q["cw"] >= GATE: return (q, 0.40, None)
    q1 = quote(P, di, ks, atm, typ, 2, 1)
    return (q1, 0.40, None) if q1 else None

def rep(t, lab):
    if not t: print(f"{lab}: none"); return
    n = len(t); months = 69.0                       # Jan'19 -> Sep'24
    yrs = collections.defaultdict(list)
    for x in t: yrs[x[0]].append(x)
    pos = sum(1 for g in yrs.values() if sum(a[1] for a in g) > 0)
    print(f"\n{lab}")
    print(f"  n={n} ({n/months:.1f}/mo)  win {sum(x[3] for x in t)/n*100:.1f}%  "
          f"ROM {sum(x[1] for x in t)/sum(x[4] for x in t)*100:+.1f}%  "
          f"net {sum(x[1] for x in t)/sum(x[2] for x in t)*100:+.1f}%w  +ve yrs {pos}/{len(yrs)}  "
          f"total net {sum(x[1] for x in t):+.0f} pts  avg margin {sum(x[4] for x in t)/n:.0f} pts")
    bysrc = collections.defaultdict(list)
    for x in t: bysrc[x[5]].append(x)
    for src in ("gate", "band", "low"):
        g = bysrc.get(src)
        if not g: continue
        print(f"    from {src:<5} n={len(g):>4}  win {sum(a[3] for a in g)/len(g)*100:5.1f}%  "
              f"ROM {sum(a[1] for a in g)/sum(a[4] for a in g)*100:+7.1f}%  "
              f"net {sum(a[1] for a in g):+8.0f} pts  avg width {sum(a[6] for a in g)/len(g):.0f}")
    print("    " + "  ".join(f"{y}:{sum(a[1] for a in g)/sum(a[4] for a in g)*100:+.0f}%"
                             for y, g in sorted(yrs.items())))

rep(apply_rule(r_deployed),   "DEPLOYED   W4 fixed, c/w>=0.40, TP-50, stop-3x")
rep(apply_rule(r_nostop),     "NOSTOP     W4 fixed, c/w>=0.40, TP-40, NO stop")
rep(apply_rule(r_adapt_w),    "ADAPT-W    widest of {4,2,1} clearing c/w>=0.40, TP-40, no stop")
rep(apply_rule(r_adapt_41),   "ADAPT-41   W4 if clears 0.40 else W1 if IT clears, TP-40, no stop")
rep(apply_rule(r_adapt_1any), "ADAPT-1ANY W4 if clears 0.40 else W1 unconditionally, TP-40, no stop")
print("\nDONE-ADAPTIVE")
