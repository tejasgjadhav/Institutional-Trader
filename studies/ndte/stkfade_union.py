"""UNION-Donchian stock fade: merge DC{5,10,15,20} breakout signals (all four individually
validated in the 96-config grid) into ONE stream to push v2-quality trades toward daily
frequency. v2 exits (short 2-OTM, width 4, TP 50% of credit, stop 3x) + v2 gates (c/w>=0.40,
prem>=50, OI, re-entry gap enforced ACROSS the union). Real bhavcopy premiums 2019->Sep'24,
entry at close (matches the engine's 15:10 scan). Reports frequency/quality vs DC10-only.
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys, glob, collections
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import date, timedelta
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical

CACHE = "/tmp/bhav_cache_stk"
MIN_DTE, REENTRY, MIN_CW, MIN_PREM, MIN_OI = 10, 3, 0.40, 50.0, 1
SHORT, WIDTH, TP, STOP = 2, 4, 0.5, 3.0
def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0
def expiso(x): return pd.to_datetime(x).date()

print("loading bhav cache…", flush=True)
prem = collections.defaultdict(dict); oi = collections.defaultdict(dict)
strikes = collections.defaultdict(set); bdays = set()
for f in sorted(glob.glob(f"{CACHE}/*.csv")):
    d = os.path.basename(f)[:-4]
    try: df = pd.read_csv(f)
    except Exception: continue
    if df.empty or "OPTION_TYP" not in df: continue
    df = df[df["OPTION_TYP"].isin(["CE", "PE"])]
    bdays.add(d)
    for r in df.itertuples(index=False):
        try: e = expiso(r.EXPIRY_DT).isoformat()
        except Exception: continue
        k = (r.SYMBOL, e, float(r.STRIKE_PR), r.OPTION_TYP)
        prem[k][d] = float(r.CLOSE); oi[k][d] = float(r.OPEN_INT)
        strikes[(r.SYMBOL, e, r.OPTION_TYP)].add(float(r.STRIKE_PR))
bdays = sorted(bdays); bset = set(bdays)
print(f"  {len(bdays)} days", flush=True)

DCS = [5, 10, 15, 20]
print("underlyings + breakouts…", flush=True)
sig_union = {}   # (day,sym) -> (typ, close, dc_that_fired_first)
sig_dc10 = []
close_by_sym = {}
for sym0 in UNIVERSE:
    sym = sym0.replace(".NS", "")
    u = fetch_upstox_historical(sym0, unit="days", interval=1, from_date="2018-06-01", to_date=max(bdays))
    if u is None or u.empty or len(u) < 40: continue
    u = u.sort_index()
    close_by_sym[sym] = {ix.date().isoformat(): float(u["Close"].loc[ix]) for ix in u.index}
    for dc in DCS:
        hi = u["High"].rolling(dc).max().shift(1); lo = u["Low"].rolling(dc).min().shift(1)
        for i in range(max(dc, 20), len(u) - 1):
            day = u.index[i].date(); ds = day.isoformat()
            if ds not in bset: continue
            c = float(u["Close"].iloc[i])
            typ = "CE" if c > float(hi.iloc[i]) else ("PE" if c < float(lo.iloc[i]) else None)
            if not typ: continue
            if dc == 10: sig_dc10.append((day, sym, typ, c))
            kk = (day, sym)
            if kk not in sig_union: sig_union[kk] = (typ, c, dc)
sig_u = sorted((d, s, t, c) for (d, s), (t, c, dc) in sig_union.items())
sig_dc10.sort()
print(f"  union signals {len(sig_u)} vs DC10-only {len(sig_dc10)}", flush=True)

exps_by = {}
for (sym, e, t) in strikes: exps_by.setdefault((sym, t), set()).add(e)

def run(sigs):
    trades = []; last = {}
    for (day, sym, typ, c) in sigs:
        kk = (sym, typ)
        if last.get(kk) and (day - last[kk]).days < REENTRY: continue
        fut = sorted(e for e in exps_by.get(kk, ()) if date.fromisoformat(e) >= day + timedelta(days=MIN_DTE))
        if not fut: continue
        exp = fut[0]; ks = sorted(strikes.get((sym, exp, typ), []))
        if len(ks) < SHORT + WIDTH + 2: continue
        atm = min(range(len(ks)), key=lambda j: abs(ks[j] - c))
        si, li = (atm + SHORT, atm + SHORT + WIDTH) if typ == "CE" else (atm - SHORT, atm - SHORT - WIDTH)
        if si < 0 or li < 0 or si >= len(ks) or li >= len(ks): continue
        sk, lk = ks[si], ks[li]; ds = day.isoformat()
        se = prem.get((sym, exp, sk, typ), {}).get(ds); le = prem.get((sym, exp, lk, typ), {}).get(ds)
        soi = oi.get((sym, exp, sk, typ), {}).get(ds, 0)
        if se is None or le is None or se < MIN_PREM or soi < MIN_OI: continue
        credit = se - le; w = abs(sk - lk)
        if credit <= 0 or credit >= w or credit / w < MIN_CW: continue
        last[kk] = day
        close = None
        for dd in (x for x in bdays if ds < x <= exp):
            a = prem.get((sym, exp, sk, typ), {}).get(dd); b = prem.get((sym, exp, lk, typ), {}).get(dd)
            if a is None or b is None: continue
            cost = a - b
            if TP > 0 and cost <= credit * (1 - TP): close = max(cost, 0.0); break
            if cost >= credit * STOP: close = min(cost, w); break
        if close is None:
            cb = close_by_sym.get(sym, {})
            espot = cb.get(exp) or (cb[max(x for x in cb if x <= exp)] if any(x <= exp for x in cb) else c)
            intr = max(0.0, espot - sk) if typ == "CE" else max(0.0, sk - espot)
            intl = max(0.0, espot - lk) if typ == "CE" else max(0.0, lk - espot)
            close = min(max(intr - intl, 0.0), w)
        net = (credit - close) - (se * spf(se) + le * spf(le)) / 100.0
        margin_ret = net / (w - credit) * 100
        trades.append((day, net, w, int(net > 0), margin_ret))
    return trades

def rep(t, lab):
    n = len(t); months = len({(x[0].year, x[0].month) for x in t})
    win = sum(x[3] for x in t) / n * 100
    netw = sum(x[1] for x in t) / sum(x[2] for x in t) * 100
    mr = sum(x[4] for x in t) / n
    days_with = len({x[0] for x in t})
    print(f"\n{lab}: n={n} ({n/months:.1f}/mo, fires on {days_with} distinct days) win {win:.1f}%  "
          f"net {netw:+.1f}% of width  avg {mr:+.1f}% on margin")
    by = collections.defaultdict(list)
    for x in t: by[x[0].year].append(x)
    for y in sorted(by):
        g = by[y]
        print(f"  {y}: n={len(g):3d} win {sum(a[3] for a in g)/len(g)*100:5.1f}%  net {sum(a[1] for a in g)/sum(a[2] for a in g)*100:+6.1f}%w  "
              f"margin {sum(a[4] for a in g)/len(g):+6.1f}%")
rep(run(sig_dc10), "DC10-ONLY (deployed v2 baseline)")
rep(run(sig_u), "UNION DC5+10+15+20 (candidate)")
print("DONE-UNION")
