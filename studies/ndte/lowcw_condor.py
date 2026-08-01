"""0.30-0.35 band, last STRUCTURAL idea: stop selling one side, sell BOTH (iron condor).

Why this and not another sweep. Every previous attempt changed WHERE the single spread sits
(offset, width, expiry) or WHEN it is taken (regime filter). None of them fixed the actual defect:
at c/w 0.30 the trade simply does not collect enough premium for the risk it carries. A condor
attacks that directly — sell the fade side AND the opposite side, collect twice, against a width
that barely grows, because at expiry only ONE side can finish in the money when the strikes do not
overlap. Combined credit/width is therefore close to the SUM of the two sides' c/w: a 0.30 fade
side plus a ~0.25-0.30 opposite side lands the structure near 0.55-0.60, i.e. above the gate that
is the book's proven edge.

In-house precedent, which is why this is a pre-registered hypothesis and not data-mining: the
FLIP-CONDOR HYBRID on 0DTE NIFTY was tested, validated and DEPLOYED on exactly this reasoning —
add the opposite side when its own credit/width clears a floor, sharing margin.

HYPOTHESIS (fixed before looking): on 0.30-0.35 signals, the two-sided condor turns the band
positive, because the combined structure clears the c/w level that the one-sided trade cannot.

BAR (fixed before looking, same as every other candidate in this study):
  - beat the one-sided baseline on the SAME signals, clearly, not by a point or two;
  - positive in most years, not carried by one;
  - hold across the opposite-side floor (a neighbourhood, not one magic value);
  - IS first. If it does not clearly turn positive here, the band is finished and OOS is not bought.

Margin convention: for a condor with non-overlapping wings the broker risk is ONE side's width
minus the TOTAL credit, which is what is used here.
"""
import warnings; warnings.filterwarnings("ignore")
import sys, json, collections
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np, pandas as pd
from datetime import date, timedelta

PKL, UND = "/tmp/bhav_stk.pkl", "/tmp/lowcw_underlyings.json"
MIN_DTE, REENTRY, MIN_PREM, MIN_OI = 10, 3, 50.0, 1
S, W = 2, 4
BAND = (0.30, 0.35)
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

def quote(sym, exp, typ, di_day, atm_spot):
    """(short_k, long_k, credit, width, se, le) for one side, or None."""
    key = (sym, exp, typ)
    if key not in PX: return None
    P = PX[key]
    if di_day not in P["didx"]: return None
    di = P["didx"][di_day]; ks = P["ks"]
    atm = int(np.argmin(np.abs(ks - atm_spot)))
    si, li = (atm + S, atm + S + W) if typ == "CE" else (atm - S, atm - S - W)
    if not (0 <= si < len(ks) and 0 <= li < len(ks)): return None
    se, le = P["C"][di, si], P["C"][di, li]
    if not np.isfinite(se) or not np.isfinite(le) or se < MIN_PREM: return None
    if not np.isfinite(P["O"][di, si]) or P["O"][di, si] < MIN_OI: return None
    credit = float(se - le); w = float(abs(ks[si] - ks[li]))
    if credit <= 0 or credit >= w: return None
    return dict(P=P, di=di, si=si, li=li, sk=float(ks[si]), lk=float(ks[li]),
                credit=credit, w=w, se=float(se), le=float(le), cw=credit / w)

def settle_side(q, espot, typ):
    intr = max(0.0, espot - q["sk"]) if typ == "CE" else max(0.0, q["sk"] - espot)
    intl = max(0.0, espot - q["lk"]) if typ == "CE" else max(0.0, q["lk"] - espot)
    return min(max(intr - intl, 0.0), q["w"])

def expiry_spot(sym, exp, fallback):
    cb = close_by_sym.get(sym, {})
    if exp in cb: return cb[exp][0]
    pr = [x for x in cb if x <= exp]
    return cb[max(pr)][0] if pr else fallback

def run(opp_floor, TP):
    """opp_floor = minimum c/w the OPPOSITE side must itself pay to be added. None = one-sided."""
    out = []; last = {}
    for (day, sym, typ, c) in sigs:
        kk = (sym, typ)
        if last.get(kk) and (day - last[kk]).days < REENTRY: continue
        ds = day.isoformat()
        fut = sorted(e for e in exps_by.get(kk, ()) if date.fromisoformat(e) >= day + timedelta(days=MIN_DTE))
        if not fut: continue
        exp = fut[0]
        qf = quote(sym, exp, typ, ds, c)
        if not qf: continue
        last[kk] = day
        if not (BAND[0] <= qf["cw"] < BAND[1]): continue
        other = "PE" if typ == "CE" else "CE"
        qo = quote(sym, exp, other, ds, c) if opp_floor is not None else None
        if opp_floor is not None:
            if not qo or qo["cw"] < opp_floor: continue        # opposite side must pay its way
        credit = qf["credit"] + (qo["credit"] if qo else 0.0)
        width = qf["w"]                                         # only one side can finish ITM
        if credit >= width: continue
        legs = [(qf, typ)] + ([(qo, other)] if qo else [])
        # daily path of the whole structure
        P0 = qf["P"]; n = P0["C"].shape[0]
        cost = np.zeros(n - qf["di"] - 1)
        okall = np.ones(len(cost), bool)
        for q, t in legs:
            seg = q["P"]["C"][q["di"] + 1:, q["si"]] - q["P"]["C"][q["di"] + 1:, q["li"]]
            m = min(len(seg), len(cost))
            cost = cost[:m] + seg[:m]; okall = okall[:m] & np.isfinite(seg[:m])
        close = None
        if okall.any():
            hit = okall & (cost <= credit * (1 - TP))
            if hit.any(): close = max(float(cost[int(np.argmax(hit))]), 0.0)
        if close is None:
            es = expiry_spot(sym, exp, c)
            close = sum(settle_side(q, es, t) for q, t in legs)
            close = min(close, width)
        entry_cost = sum((q["se"] * spf(q["se"]) + q["le"] * spf(q["le"])) / 100.0 for q, _ in legs)
        net = (credit - close) - entry_cost
        out.append(dict(y=day.year, net=net, margin=width - credit, win=int(net > 0), cw=credit / width))
    return out

def rep(t, lab):
    if len(t) < 20: print(f"{lab:<40} n={len(t):>4}  (too few)"); return
    n = len(t); nm = sum(x["net"] for x in t); mg = sum(x["margin"] for x in t)
    by = collections.defaultdict(list)
    for x in t: by[x["y"]].append(x)
    pos = sum(1 for g in by.values() if sum(a["net"] for a in g) > 0)
    print(f"{lab:<40} n={n:>4}  win {sum(x['win'] for x in t)/n*100:5.1f}%  "
          f"ROM {nm/mg*100:+7.1f}%  +ve {pos}/{len(by)}  combined c/w {sum(x['cw'] for x in t)/n:.2f}")

print("\n0.30-0.35 band — one side vs BOTH sides (condor), 2019 -> Jul 2024\n")
for TP in (0.40, 0.50):
    print(f"--- take profit at {TP:.0%} of total credit ---")
    rep(run(None, TP), f"  ONE SIDE (baseline)")
    for fl in (0.10, 0.15, 0.20, 0.25, 0.30):
        rep(run(fl, TP), f"  CONDOR · opposite side c/w >= {fl:.2f}")
    print()
print("DONE-CONDOR")
