"""Average WIN and average LOSS in rupees, per live book — no gaps, one consistent basis.

The STUDIES table had cells reading "not separately measured". This fills them. The three stock
books are all measured on the SAME window (NSE bhavcopy 2019 -> Sep 2024, the longest one that
covers every book) at their OWN deployed geometry and exits, so the column compares like with like:

    v2  short 2-OTM / width 4 · take profit at 50% of credit · stop 3x · c/w >= 0.40
    v1  short 1-OTM / width 3 · take profit at 40% of credit · no stop · c/w >= 0.40
    v0  short 2-OTM / width 4 · take profit at 40% of credit · no stop · c/w 0.35-0.40

Rupees use CURRENT lot sizes from the Upstox options master. Lot sizes have changed over the years,
so treat the absolute rupee figures as indicative; the WIN:LOSS RATIO, which is what the table is
really for, is unaffected by that because both legs of the ratio scale with the same lot.

The two expiry-day books come from their own saved backtests (ndte13_trades.json, ndte8_sensex.json),
which already store per-trade rupee P&L.
"""
import warnings; warnings.filterwarnings("ignore")
import sys, json, collections
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np, pandas as pd
from datetime import date, timedelta
from engine.options import _load_index
from engine.instruments import to_instrument_key

PKL, UND = "/tmp/bhav_stk.pkl", "/tmp/lowcw_underlyings.json"
MIN_DTE, REENTRY, MIN_PREM, MIN_OI = 10, 3, 50.0, 1
def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0

LOT = {}
for tk, cs in _load_index().items():
    for c in cs:
        l = int(c.get("lot", 0) or 0)
        if l: LOT[tk] = l; break
def lot_for(sym): return LOT.get(to_instrument_key(sym + ".NS"))

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
print(f"  {len(sigs)} union breakout signals screened", flush=True)

def run(S, W, TP, STOP, cw_lo, cw_hi):
    wins = []; losses = []; last = {}; screened = 0
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
        last[kk] = day; screened += 1
        cw = credit / w
        if not (cw_lo <= cw < cw_hi): continue
        lot = lot_for(sym)
        if not lot: continue
        path = P["C"][di + 1:, si] - P["C"][di + 1:, li]
        ok = np.isfinite(path); close = None
        if ok.any():
            tp_hit = ok & (path <= credit * (1 - TP)) if TP else np.zeros(len(path), bool)
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
        (wins if net > 0 else losses).append(net * lot)
    return screened, wins, losses

print(f"\n{'book':<34}{'screened':>10}{'analysed':>10}{'win%':>8}{'avg WIN':>12}{'avg LOSS':>12}{'W:L':>8}")
BOOKS = [("v2  S2/W4 TP-50 stop-3x  c/w>=.40", 2, 4, 0.50, 3.0, 0.40, 9.9),
         ("v1  S1/W3 TP-40 no-stop  c/w>=.40", 1, 3, 0.40, None, 0.40, 9.9),
         ("v0  S2/W4 TP-40 no-stop  c/w .35-.40", 2, 4, 0.40, None, 0.35, 0.40)]
for lab, S, W, TP, ST, lo, hi in BOOKS:
    scr, wins, losses = run(S, W, TP, ST, lo, hi)
    n = len(wins) + len(losses)
    aw = sum(wins) / len(wins) if wins else 0
    al = sum(losses) / len(losses) if losses else 0
    print(f"{lab:<34}{scr:>10,}{n:>10}{len(wins)/n*100:>7.1f}%{aw:>+12,.0f}{al:>+12,.0f}"
          f"{(abs(aw/al) if al else 0):>7.1f}:1")

# ── expiry-day books, from their own saved per-trade backtests ──
print()
t = [x for x in json.load(open("studies/ndte/ndte13_trades.json")) if x.get("traded")]
for bk in sorted({x["book"] for x in t}):
    g = [x for x in t if x["book"] == bk]
    w = [x["rs"] for x in g if x["win"]]; l = [x["rs"] for x in g if not x["win"]]
    if not w or not l: continue
    aw, al = sum(w)/len(w), sum(l)/len(l)
    print(f"{bk+' 0DTE (ndte13_trades.json)':<34}{len(g):>10}{len(g):>10}{len(w)/len(g)*100:>7.1f}%"
          f"{aw:>+12,.0f}{al:>+12,.0f}{abs(aw/al):>7.1f}:1")
sx = json.load(open("studies/ndte/ndte8_sensex.json"))
w = [r[2] for r in sx if r[1] > 0]; l = [r[2] for r in sx if r[1] <= 0]
if w and l:
    aw, al = sum(w)/len(w), -abs(sum(l)/len(l))
    print(f"{'SENSEX 0DTE (ndte8_sensex.json)':<34}{len(sx):>10}{len(sx):>10}{len(w)/len(sx)*100:>7.1f}%"
          f"{aw:>+12,.0f}{al:>+12,.0f}{abs(aw/al):>7.1f}:1")
print("\nDONE-SIZES")
