"""IN-SAMPLE test of the DEPLOYED Stock Credit v1 book with its live TP-75 exit.

Closes a known gap: v1's TP-75 exit was only ever measured OOS (Oct'24->, 73.4% via
stkfade_oos_v1.py). Its IS number under the SAME early-book exit was never run — only the
hold-to-expiry base (~54%). This runs v1's deployed config on the cached NSE F&O stock-option
bhavcopy 2019->Sep'24, reusing the EXACT validated IS harness from stkfade_union.py
(cache loader + gate/exit walk + intrinsic settlement + entry-slippage spf model).

v1 DEPLOYED (engine/config.py): DC10 only, short 1-OTM, width 3, TP 0.75 (book when
cost-to-close <= 0.25*credit), stop 2x credit, gates credit/width>=0.40 + short prem>=Rs50,
min-DTE 10, re-entry 3 days, entry at close.

FAITHFULNESS CROSS-CHECK: the SAME harness is also run with the v2 config (short 2-OTM,
width 4, TP 0.50, stop 3x) on DC10 signals -> must reproduce the known ~273-trade / 85.3% IS
"DC10-ONLY (deployed v2 baseline)" number from stkfade_union.py. If it does, the v1 result is
trustworthy.

Costs: entry slippage only, via the validated spf() model (matches v2/validated IS sim). Net is
gross of exit slippage and of brokerage/taxes -- report caveat.
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys, glob, collections
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import date, timedelta
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical

CACHE = "/tmp/bhav_cache_stk"
# gates identical to the validated IS harness
MIN_DTE, REENTRY, MIN_CW, MIN_PREM, MIN_OI = 10, 3, 0.40, 50.0, 1
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
print(f"  {len(bdays)} days ({bdays[0]} -> {bdays[-1]})", flush=True)

# v1 is Donchian-10 ONLY (not the union)
print("underlyings + DC10 breakouts…", flush=True)
sig_dc10 = []
close_by_sym = {}
for sym0 in UNIVERSE:
    sym = sym0.replace(".NS", "")
    u = fetch_upstox_historical(sym0, unit="days", interval=1, from_date="2018-06-01", to_date=max(bdays))
    if u is None or u.empty or len(u) < 40: continue
    u = u.sort_index()
    close_by_sym[sym] = {ix.date().isoformat(): float(u["Close"].loc[ix]) for ix in u.index}
    dc = 10
    hi = u["High"].rolling(dc).max().shift(1); lo = u["Low"].rolling(dc).min().shift(1)
    for i in range(max(dc, 20), len(u) - 1):
        day = u.index[i].date(); ds = day.isoformat()
        if ds not in bset: continue
        c = float(u["Close"].iloc[i])
        typ = "CE" if c > float(hi.iloc[i]) else ("PE" if c < float(lo.iloc[i]) else None)
        if not typ: continue
        sig_dc10.append((day, sym, typ, c))
sig_dc10.sort()
print(f"  DC10 signals {len(sig_dc10)}", flush=True)

exps_by = {}
for (sym, e, t) in strikes: exps_by.setdefault((sym, t), set()).add(e)

def run(sigs, SHORT, WIDTH, TP, STOP):
    """EXACT copy of stkfade_union.run(), config parameterized. Entry-slippage only."""
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
    n = len(t)
    if n == 0:
        print(f"\n{lab}: NO TRADES"); return
    months = len({(x[0].year, x[0].month) for x in t})
    win = sum(x[3] for x in t) / n * 100
    netw = sum(x[1] for x in t) / sum(x[2] for x in t) * 100
    mr = sum(x[4] for x in t) / n
    print(f"\n{lab}: n={n} ({n/months:.1f}/mo) win {win:.1f}%  net {netw:+.1f}% of width  avg {mr:+.1f}% on margin")
    by = collections.defaultdict(list)
    for x in t: by[x[0].year].append(x)
    for y in sorted(by):
        g = by[y]
        print(f"  {y}: n={len(g):3d} win {sum(a[3] for a in g)/len(g)*100:5.1f}%  "
              f"net {sum(a[1] for a in g)/sum(a[2] for a in g)*100:+6.1f}%w  "
              f"margin {sum(a[4] for a in g)/len(g):+6.1f}%")

# --- FAITHFULNESS CROSS-CHECK: v2 config on DC10 signals -> expect ~273 tr / 85.3% ---
rep(run(sig_dc10, SHORT=2, WIDTH=4, TP=0.5, STOP=3.0), "CROSS-CHECK v2 DC10-ONLY (expect ~273 tr / 85.3%)")
# --- TARGET: v1 DEPLOYED config, TP-75 ---
rep(run(sig_dc10, SHORT=1, WIDTH=3, TP=0.75, STOP=2.0), "v1 DEPLOYED (DC10 s1 w3 TP0.75 stop2x) -- TP-75 IS")
# --- INFORMATIVE: v1 geometry held to expiry (TP off) -- context for the ~54% base ---
rep(run(sig_dc10, SHORT=1, WIDTH=3, TP=0.0, STOP=2.0), "v1 geometry HOLD-TO-EXPIRY (TP off, stop2x) -- base context")
print("\nDONE-V1-IS")
