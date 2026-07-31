"""LOW-C/W RESCUE SWEEP (IN-SAMPLE) — can a different CONFIG make the 0.30-0.40 band tradeable?

The deployed v2 gate (c/w >= 0.40 at short-2-OTM / width-4) blocks most breakouts: a typical
watchlist day is 18 breakouts and 0 passes, all sitting at c/w 0.26-0.32. This asks whether that
band is genuinely un-tradeable or merely mis-parameterised.

Population  : UNION (DC5/10/15/20) breakouts whose REFERENCE c/w at S=2,W=4 falls in [0.30,0.40).
Sweep       : geometry  - strike-step (S in 0..3 x W in 1..5) AND percent-of-spot (S% x W%)
              exits     - TP in {0.40,0.50,0.75,hold} x stop in {none,2x,3x}
Metric      : win% + net as % of MARGIN (width-credit) -- the only money metric comparable
              across geometries -- plus per-year sign. %-of-width is reported only for
              continuity with the older studies and must NOT be compared across widths.
Data        : NSE FO bhavcopy daily closes 2019 -> Sep'24, compacted by bhav_stk_parquet.py.
              Entry at the signal close, matching the engine's 15:10 scan.

The OOS twin (stkfade_lowcw_oos.py) sweeps the SAME grid on Upstox expired options Oct'24->date.
Neither window selects the shortlist for the other; a config has to stand up in both.
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys, json, collections
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np, pandas as pd
from datetime import date, timedelta
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical

PARQ, UND_CACHE = "/tmp/bhav_stk.pkl", "/tmp/lowcw_underlyings.json"
MIN_DTE, REENTRY, MIN_PREM, MIN_OI = 10, 3, 50.0, 1
REF_SHORT, REF_WIDTH = 2, 4          # deployed v2 geometry -> defines the band
BAND = (0.30, 0.40)

def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0

# ── premiums: one dense matrix per (sym, expiry, type) ──────────────────────
print("loading parquet…", flush=True)
big = pd.read_pickle(PARQ)
bdays = sorted(big["DAY"].astype(str).unique()); bset = set(bdays)
print(f"  {len(big):,} rows, {len(bdays)} days {bdays[0]} -> {bdays[-1]}", flush=True)

PX = {}
for key, sub in big.groupby(["SYM", "EXP", "TYP"], observed=True):
    c = sub.pivot_table(index="DAY", columns="STRIKE", values="CLOSE", aggfunc="last")
    o = sub.pivot_table(index="DAY", columns="STRIKE", values="OI", aggfunc="last")
    days = [str(d) for d in c.index]
    PX[(str(key[0]), str(key[1]), str(key[2]))] = dict(
        ks=np.asarray(c.columns, dtype="float64"),
        sidx={float(k): j for j, k in enumerate(c.columns)},
        days=days, didx={d: i for i, d in enumerate(days)},
        C=c.values.astype("float32"), O=o.reindex_like(c).values.astype("float32"))
del big
print(f"  {len(PX):,} (sym,expiry,type) chains", flush=True)

exps_by = collections.defaultdict(set)
for (sym, e, t) in PX: exps_by[(sym, t)].add(e)

# ── underlyings (cached; the Upstox pull is the slow part) ─────────────────
if os.path.exists(UND_CACHE):
    close_by_sym = json.load(open(UND_CACHE))
    print(f"  underlyings from cache: {len(close_by_sym)} symbols", flush=True)
else:
    close_by_sym = {}
    for i, sym0 in enumerate(UNIVERSE):
        sym = sym0.replace(".NS", "")
        try:
            u = fetch_upstox_historical(sym0, unit="days", interval=1,
                                        from_date="2018-06-01", to_date=bdays[-1])
        except Exception:
            continue
        if u is None or u.empty or len(u) < 40: continue
        u = u.sort_index()
        close_by_sym[sym] = {ix.date().isoformat(): [float(u["Close"].loc[ix]),
                                                     float(u["High"].loc[ix]),
                                                     float(u["Low"].loc[ix])] for ix in u.index}
        if i % 20 == 0: print(f"  underlying {i}/{len(UNIVERSE)}", flush=True)
    json.dump(close_by_sym, open(UND_CACHE, "w"))
    print(f"  underlyings fetched: {len(close_by_sym)} symbols", flush=True)

# ── UNION breakout signals ─────────────────────────────────────────────────
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
            if not typ: continue
            sig_union.setdefault((ds, sym), (typ, float(c)))
sigs = sorted((date.fromisoformat(d), s, t, c) for (d, s), (t, c) in sig_union.items())
print(f"  union signals: {len(sigs)}", flush=True)

# ── geometry pickers ───────────────────────────────────────────────────────
def legs_steps(ks, atm, typ, S, W):
    si, li = (atm + S, atm + S + W) if typ == "CE" else (atm - S, atm - S - W)
    if si < 0 or li < 0 or si >= len(ks) or li >= len(ks): return None
    return si, li

def legs_pct(ks, c, typ, sp, wp):
    tgt_s = c * (1 + sp / 100) if typ == "CE" else c * (1 - sp / 100)
    si = int(np.argmin(np.abs(ks - tgt_s)))
    tgt_l = ks[si] + c * wp / 100 if typ == "CE" else ks[si] - c * wp / 100
    cand = np.where(ks > ks[si])[0] if typ == "CE" else np.where(ks < ks[si])[0]
    if len(cand) == 0: return None
    li = int(cand[np.argmin(np.abs(ks[cand] - tgt_l))])
    return si, li

def pick(ks, atm, c, typ, geo):
    return legs_steps(ks, atm, typ, int(geo[1]), int(geo[2])) if geo[0] == "step" \
        else legs_pct(ks, c, typ, float(geo[1]), float(geo[2]))

# ── stage 1: the band population, defined at the REFERENCE geometry ────────
band_pop = []; allsig_cw = []; last = {}
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
    cw = credit / w
    allsig_cw.append(cw)
    if BAND[0] <= cw < BAND[1]:
        band_pop.append((day, sym, typ, c, fut[0], di, atm, cw))

above = sum(1 for x in allsig_cw if x >= 0.40)
below = len(allsig_cw) - above - len(band_pop)
print(f"\nPOPULATION at reference geometry S{REF_SHORT}/W{REF_WIDTH}: {len(allsig_cw)} priced signals")
print(f"  c/w >= 0.40  (deployed — these trade) : {above:5d}  ({above/len(allsig_cw)*100:.1f}%)")
print(f"  c/w 0.30-0.40  (THE BAND)            : {len(band_pop):5d}  ({len(band_pop)/len(allsig_cw)*100:.1f}%)")
print(f"  c/w < 0.30                            : {below:5d}  ({below/len(allsig_cw)*100:.1f}%)", flush=True)

# ── stage 2: evaluate a config over the band ───────────────────────────────
def evaluate(pop, geo, TP, STOP, min_cw=0.0):
    out = []
    for (day, sym, typ, c, exp, di, atm, ref_cw) in pop:
        P = PX[(sym, exp, typ)]; ks = P["ks"]
        sel = pick(ks, atm, c, typ, geo)
        if not sel: continue
        si, li = sel
        if si == li: continue
        se, le = P["C"][di, si], P["C"][di, li]
        if not np.isfinite(se) or not np.isfinite(le) or se < MIN_PREM: continue
        if not np.isfinite(P["O"][di, si]) or P["O"][di, si] < MIN_OI: continue
        credit = float(se - le); w = float(abs(ks[si] - ks[li]))
        if credit <= 0 or credit >= w or credit / w < min_cw: continue

        path = P["C"][di + 1:, si] - P["C"][di + 1:, li]          # spread cost, entry+1 -> expiry
        ok = np.isfinite(path)
        close = None
        if ok.any():
            hit_tp = ok & (path <= credit * (1 - TP)) if TP is not None else np.zeros(len(path), bool)
            hit_st = ok & (path >= credit * STOP) if STOP is not None else np.zeros(len(path), bool)
            hit = hit_tp | hit_st
            if hit.any():
                j = int(np.argmax(hit))
                close = max(float(path[j]), 0.0) if hit_tp[j] else min(float(path[j]), w)
        if close is None:                                          # settle on underlying intrinsic
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
        margin = w - credit
        out.append((day.year, net, w, int(net > 0), margin))
    return out

def stats(t):
    if len(t) < 10: return None
    n = len(t)
    by = collections.defaultdict(list)
    for x in t: by[x[0]].append(x)
    yrs = {y: sum(a[1] for a in g) / sum(a[4] for a in g) * 100 for y, g in by.items()}
    return dict(n=n, win=sum(x[3] for x in t) / n * 100,
                rom=sum(x[1] for x in t) / sum(x[4] for x in t) * 100,
                netw=sum(x[1] for x in t) / sum(x[2] for x in t) * 100,
                pos=sum(1 for v in yrs.values() if v > 0), nyr=len(yrs), yrs=yrs)

base = stats(evaluate(band_pop, ("step", REF_SHORT, REF_WIDTH), 0.50, 3.0))
print(f"\nFAITHFULNESS CHECK — band at the DEPLOYED v2 config (S2/W4, TP-50, stop-3x):")
print(f"  n={base['n']}  win {base['win']:.1f}%  net {base['netw']:+.1f}% of width  "
      f"ROM {base['rom']:+.1f}%  +ve yrs {base['pos']}/{base['nyr']}")
print(f"  (CW_BUCKET_ANALYSIS reported ~77-78% win and +1 to +9% of width for this band)", flush=True)

GEOS  = [("step", S, W) for S in (0, 1, 2, 3) for W in (1, 2, 3, 4, 5)] + \
        [("pct", s, w) for s in (1.0, 2.0, 3.0, 4.0) for w in (2.0, 3.0, 4.0, 6.0)]
EXITS = [(tp, st) for tp in (0.40, 0.50, 0.75, None) for st in (None, 2.0, 3.0)]

rows = []
for geo in GEOS:
    for (tp, st) in EXITS:
        s = stats(evaluate(band_pop, geo, tp, st))
        if s: s.update(geo=geo, tp=tp, stop=st); rows.append(s)
print(f"\nswept {len(rows)} cells on the {len(band_pop)}-signal band", flush=True)

def lbl(r):
    g = r["geo"]
    gs = f"S{int(g[1])}/W{int(g[2])}" if g[0] == "step" else f"{g[1]:.0f}%/{g[2]:.0f}%"
    return f"{gs:>9} TP{'hold' if r['tp'] is None else int(r['tp']*100):>4} stop{'--' if r['stop'] is None else r['stop']:>4}"

print("\n=== TOP 20 by pooled RETURN ON MARGIN ===")
print(f"{'config':<30} {'n':>5} {'win%':>6} {'ROM%':>7} {'net%w':>7} {'+yrs':>6}")
for r in sorted(rows, key=lambda x: -x["rom"])[:20]:
    print(f"{lbl(r):<30} {r['n']:>5} {r['win']:>6.1f} {r['rom']:>+7.1f} {r['netw']:>+7.1f} {r['pos']}/{r['nyr']:>4}")

print("\n=== TOP 20 by WIN RATE (n>=40, ROM>0) ===")
for r in sorted([x for x in rows if x["n"] >= 40 and x["rom"] > 0], key=lambda x: -x["win"])[:20]:
    print(f"{lbl(r):<30} {r['n']:>5} {r['win']:>6.1f} {r['rom']:>+7.1f} {r['netw']:>+7.1f} {r['pos']}/{r['nyr']:>4}")

json.dump([{**r, "geo": list(r["geo"]), "yrs": {str(k): v for k, v in r["yrs"].items()}} for r in rows],
          open("/tmp/lowcw_sweep.json", "w"), indent=1)
print("\nwrote /tmp/lowcw_sweep.json")
print("DONE-LOWCW")
