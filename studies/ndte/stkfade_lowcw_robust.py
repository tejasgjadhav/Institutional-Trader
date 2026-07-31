"""LOW-C/W RESCUE — robustness of the ADAPT-41 rule (in-sample).

Two questions a positive backtest does not answer, both of which have killed prior candidates
in this repo (see the index-fade salvage attempt in CLAUDE.md Part 11):

  CONCENTRATION  is the gain broad, or is it a handful of names and a handful of months?
                 A rule carried by 5 symbols is a fit, not an edge.
  BOOTSTRAP      what does a bad draw look like? Block-bootstrap by MONTH (not by trade --
                 fade losses cluster on shared down-days, so trade-level resampling would
                 understate the tail) and report the 5th percentile.

Also splits the added trades by side (bear-call vs bull-put), since SWING_PUTCALL_STOP_ANALYSIS
found the put/call tilt reverses out-of-sample -- worth knowing before anyone tilts.
"""
import warnings; warnings.filterwarnings("ignore")
import sys, json, collections, random
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np, pandas as pd
from datetime import date, timedelta

PKL, UND_CACHE = "/tmp/bhav_stk.pkl", "/tmp/lowcw_underlyings.json"
MIN_DTE, REENTRY, MIN_PREM, MIN_OI, GATE = 10, 3, 50.0, 1, 0.40
def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0
random.seed(7); np.random.seed(7)

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

def settle(P, ks, di, exp, sym, typ, c, q, TP, STOP):
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
    return (credit - close) - (q["se"] * spf(q["se"]) + q["le"] * spf(q["le"])) / 100.0

def build(rule_w1=True):
    """ADAPT-41 (rule_w1=True) or DEPLOYED. Returns trade dicts."""
    out = []; last = {}
    for (day, sym, typ, c) in sigs:
        kk = (sym, typ)
        if last.get(kk) and (day - last[kk]).days < REENTRY: continue
        ds = day.isoformat()
        fut = sorted(e for e in exps_by.get(kk, ()) if date.fromisoformat(e) >= day + timedelta(days=MIN_DTE))
        if not fut: continue
        exp = fut[0]; P = PX[(sym, exp, typ)]
        if ds not in P["didx"] or len(P["ks"]) < 8: continue
        di = P["didx"][ds]; ks = P["ks"]
        atm = int(np.argmin(np.abs(ks - c)))
        q4 = quote(P, di, ks, atm, typ, 2, 4)
        if not q4: continue
        last[kk] = day
        ref_cw = q4["cw"]
        if ref_cw >= GATE:
            q, TP, STOP, src = q4, (0.40 if rule_w1 else 0.50), (None if rule_w1 else 3.0), "core"
        elif rule_w1:
            q1 = quote(P, di, ks, atm, typ, 2, 1)
            if not q1 or q1["cw"] < GATE: continue
            q, TP, STOP, src = q1, 0.40, None, "added"
        else:
            continue
        net = settle(P, ks, di, exp, sym, typ, c, q, TP, STOP)
        out.append(dict(day=day, ym=(day.year, day.month), sym=sym, typ=typ, src=src,
                        net=net, margin=q["w"] - q["credit"], win=int(net > 0)))
    return out

adapt = build(True); dep = build(False)
print(f"ADAPT-41 n={len(adapt)}  ·  DEPLOYED n={len(dep)}\n")

def summ(t, lab):
    n = len(t); nm = sum(x["net"] for x in t); mg = sum(x["margin"] for x in t)
    print(f"{lab:<26} n={n:>4}  win {sum(x['win'] for x in t)/n*100:5.1f}%  "
          f"ROM {nm/mg*100:+6.1f}%  net {nm:+8.0f} pts")

print("=== 1. WHERE THE MONEY COMES FROM ===")
summ(dep, "DEPLOYED (baseline)")
summ(adapt, "ADAPT-41 (all)")
summ([x for x in adapt if x["src"] == "core"], "  core (c/w>=0.40 @ W4)")
summ([x for x in adapt if x["src"] == "added"], "  ADDED (band/low @ W1)")

added = [x for x in adapt if x["src"] == "added"]
print("\n=== 2. CONCENTRATION of the ADDED trades ===")
bysym = collections.defaultdict(list)
for x in added: bysym[x["sym"]].append(x)
tot = sum(x["net"] for x in added)
rank = sorted(bysym.items(), key=lambda kv: -sum(a["net"] for a in kv[1]))
print(f"  {len(bysym)} distinct symbols contribute the {len(added)} added trades")
for k, g in rank[:5]:
    print(f"    top: {k:<12} n={len(g):>3}  net {sum(a['net'] for a in g):+8.0f} pts "
          f"({sum(a['net'] for a in g)/tot*100:4.1f}% of added net)")
print(f"  top 5 symbols = {sum(sum(a['net'] for a in g) for _, g in rank[:5])/tot*100:.1f}% of added net")
print(f"  symbols with POSITIVE net: {sum(1 for _, g in bysym.items() if sum(a['net'] for a in g) > 0)}/{len(bysym)}")
bym = collections.defaultdict(list)
for x in added: bym[x["ym"]].append(x)
posm = sum(1 for g in bym.values() if sum(a["net"] for a in g) > 0)
print(f"  months with POSITIVE net: {posm}/{len(bym)}")

print("\n=== 3. SIDE SPLIT of the ADDED trades (put/call tilt reverses OOS — see SWING_PUTCALL) ===")
for t in ("CE", "PE"):
    g = [x for x in added if x["typ"] == t]
    if g: summ(g, f"  {'bear-call' if t=='CE' else 'bull-put'}")

print("\n=== 4. BLOCK BOOTSTRAP by month (5,000 draws) ===")
def boot(trades, lab):
    months = sorted({x["ym"] for x in trades})
    bym = collections.defaultdict(list)
    for x in trades: bym[x["ym"]].append(x)
    roms = []
    for _ in range(5000):
        pick = [random.choice(months) for _ in range(len(months))]
        nm = mg = 0.0
        for m in pick:
            for x in bym[m]: nm += x["net"]; mg += x["margin"]
        if mg > 0: roms.append(nm / mg * 100)
    roms = np.array(roms)
    print(f"  {lab:<24} mean {roms.mean():+6.1f}%   p5 {np.percentile(roms,5):+6.1f}%   "
          f"p50 {np.percentile(roms,50):+6.1f}%   p95 {np.percentile(roms,95):+6.1f}%   "
          f"P(loss) {(roms<0).mean()*100:.1f}%")
boot(dep, "DEPLOYED")
boot(adapt, "ADAPT-41")
boot(added, "ADDED trades only")

print("\n=== 5. WORST OUTCOMES (added trades) ===")
w = sorted(added, key=lambda x: x["net"] / x["margin"])[:5]
for x in w:
    print(f"  {x['day']} {x['sym']:<12} {x['typ']}  net {x['net']:+8.1f} pts on margin "
          f"{x['margin']:.0f}  = {x['net']/x['margin']*100:+.0f}% of margin")
print("\nDONE-ROBUST")
