"""RETURN ON CAPITAL + HOLDING PERIOD per book (user request 2026-07-19).

"Capital" = the margin actually blocked = (width - credit) x qty, i.e. the MAX LOSS. That is the
correct denominator for return on capital on a defined-risk credit spread.

TWO TRAPS this script exists to avoid:

1. MEAN-OF-RATIOS BLOWUP. A naive mean of per-trade net/margin gives v2 UNION +302%/trade, which is
   impossible — a credit spread's max gain is the credit itself. Cause: 16 of 569 trades print
   c/W > 0.95, so margin collapses to ~0.5 points and the ratio explodes. Those are almost certainly
   stale/illiquid option prints (a spread paying 99.5% of its width is free money). We therefore
   (a) EXCLUDE c/W > 0.90 as bad prints, and (b) report the CAPITAL-WEIGHTED aggregate
   sum(net)/sum(margin) alongside the median, never the raw mean of ratios.

2. ASSERTED HOLDING PERIODS. The v2 holding period is measured by re-simulating the bhav era and
   recording the actual exit date, not quoted from the config's min-DTE.
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys, glob, json, collections
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np, pandas as pd
from datetime import date, timedelta
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical

HERE = os.path.dirname(os.path.abspath(__file__))

def roc(nets, margins, lab):
    nets = np.asarray(nets); margins = np.asarray(margins)
    per = nets / margins * 100
    agg = nets.sum() / margins.sum() * 100
    wins = per[per > 0]; loss = per[per <= 0]
    print(f"  {lab:26s} n={len(per):4d}  capital-wtd {agg:+7.2f}%  median {np.median(per):+7.2f}%  "
          f"win {(per>0).mean()*100:5.1f}%  avgW {wins.mean():+7.1f}%  avgL {loss.mean():+7.1f}%")
    return agg

print("=" * 112)
print("RETURN ON CAPITAL per trade  (capital = margin blocked = width - credit = MAX LOSS)")
print("=" * 112)

v2 = []
for f in ("/tmp/d5_10_15_20_bhav.json", "/tmp/d5_10_15_20_oct24.json"):
    if os.path.exists(f): v2 += json.load(open(f)).get("D5", [])
clean = [x for x in v2 if x["cw"] <= 0.90]
print(f"  [v2] dropped {len(v2)-len(clean)} of {len(v2)} trades with c/W>0.90 (stale-print guard)")
roc([x["net"] for x in clean], [x["w"] * (1 - x["cw"]) for x in clean], "v2 UNION (stock fade)")

rows = []
for fn in ("ndte14_trades_2019.json", "ndte13_trades.json"):
    p = os.path.join(HERE, fn)
    if os.path.exists(p): rows += json.load(open(p))
rows = [r for r in rows if r["traded"]]
for b in ("NIFTY", "SENSEX", "BANKNIFTY"):
    s = [r for r in rows if r["book"] == b]
    if s: roc([r["pm"] for r in s], [100.0] * len(s), f"0DTE {b}")   # pm already = net/margin %

print("\n" + "=" * 112)
print("HOLDING PERIOD — measured, not asserted")
print("=" * 112)
print("  0DTE NIFTY / SENSEX      : SAME DAY (enter 09:16, settle 15:30) = ~6h, 0 nights of gap risk")

# v2 holding period: re-simulate the bhav era recording the actual exit date
CACHE = "/tmp/bhav_cache_stk"
if not glob.glob(f"{CACHE}/*.csv"):
    print("  v2 UNION                 : bhav cache absent — cannot measure; re-run bhav_dl_stk_opt.py")
else:
    MIN_DTE, REENTRY, MIN_CW, MIN_PREM, MIN_OI = 10, 3, 0.40, 50.0, 1
    SHORT, WIDTH, TP, STOP = 2, 4, 0.5, 3.0
    book = collections.defaultdict(dict); strikes = collections.defaultdict(set); bdays = set()
    for f in sorted(glob.glob(f"{CACHE}/*.csv")):
        d = os.path.basename(f)[:-4]
        try: df = pd.read_csv(f)
        except Exception: continue
        if df.empty or "OPTION_TYP" not in df: continue
        df = df[df["OPTION_TYP"].isin(["CE", "PE"])]
        if df.empty: continue
        bdays.add(d)
        for r in df.itertuples(index=False):
            try: e = pd.to_datetime(r.EXPIRY_DT).date().isoformat()
            except Exception: continue
            book[(r.SYMBOL, e, float(r.STRIKE_PR), r.OPTION_TYP)][d] = (float(r.CLOSE), float(r.OPEN_INT))
            strikes[(r.SYMBOL, e, r.OPTION_TYP)].add(float(r.STRIKE_PR))
    bdays = sorted(bdays); bset = set(bdays)
    exps_by = {}
    for (sym, e, t) in strikes: exps_by.setdefault((sym, t), set()).add(e)

    holds = {"TP": [], "STOP": [], "EXPIRY": []}
    for sym0 in UNIVERSE:
        sym = sym0.replace(".NS", "")
        u = fetch_upstox_historical(sym0, unit="days", interval=1, from_date="2018-06-01", to_date=max(bdays))
        if u is None or u.empty or len(u) < 40: continue
        u = u.sort_index()
        hi = u["High"].rolling(5).max().shift(1); lo = u["Low"].rolling(5).min().shift(1)
        last = {}
        for i in range(20, len(u) - 1):
            day = u.index[i].date(); ds = day.isoformat()
            if ds not in bset: continue
            c = float(u["Close"].iloc[i])
            typ = "CE" if c > float(hi.iloc[i]) else ("PE" if c < float(lo.iloc[i]) else None)
            if not typ: continue
            kk = (sym, typ)
            if last.get(kk) and (day - last[kk]).days < REENTRY: continue
            fut = sorted(e for e in exps_by.get(kk, ()) if date.fromisoformat(e) >= day + timedelta(days=MIN_DTE))
            if not fut: continue
            exp = fut[0]; ks = sorted(strikes.get((sym, exp, typ), []))
            if len(ks) < SHORT + WIDTH + 2: continue
            atm = min(range(len(ks)), key=lambda j: abs(ks[j] - c))
            si, li = (atm + SHORT, atm + SHORT + WIDTH) if typ == "CE" else (atm - SHORT, atm - SHORT - WIDTH)
            if si < 0 or li < 0 or si >= len(ks) or li >= len(ks): continue
            sk, lk = ks[si], ks[li]
            sr = book.get((sym, exp, sk, typ), {}).get(ds); lr = book.get((sym, exp, lk, typ), {}).get(ds)
            if sr is None or lr is None: continue
            se, le = sr[0], lr[0]
            if se < MIN_PREM or sr[1] < MIN_OI: continue
            credit = se - le; w = abs(sk - lk)
            if credit <= 0 or credit >= w or credit / w < MIN_CW: continue
            last[kk] = day
            kind, exit_d = "EXPIRY", exp
            for dd in (x for x in bdays if ds < x <= exp):
                a = book.get((sym, exp, sk, typ), {}).get(dd); b = book.get((sym, exp, lk, typ), {}).get(dd)
                if a is None or b is None: continue
                cost = a[0] - b[0]
                if cost <= credit * (1 - TP): kind, exit_d = "TP", dd; break
                if cost >= credit * STOP: kind, exit_d = "STOP", dd; break
            holds[kind].append((date.fromisoformat(exit_d) - day).days)
    tot = sum(len(v) for v in holds.values())
    if tot:
        allh = [d for v in holds.values() for d in v]
        print(f"  v2 UNION (stock fade)    : MEASURED over {tot} bhav-era trades")
        print(f"      avg {np.mean(allh):.1f} calendar days · median {np.median(allh):.0f} · "
              f"p90 {np.percentile(allh,90):.0f} · max {max(allh)}")
        for k in ("TP", "STOP", "EXPIRY"):
            if holds[k]:
                print(f"      {k:7s} {len(holds[k]):4d} trades ({len(holds[k])/tot*100:4.1f}%)  "
                      f"avg {np.mean(holds[k]):5.1f}d  median {np.median(holds[k]):4.0f}d")
print("\nDONE-NDTE21")
