"""V1 WIN-RATE SWEEP (IS 2019->Sep'24) — n-preserving exit/geometry levers only.

GOAL: raise Stock Credit v1's win rate WITHOUT touching the entry gates (DC10 + universe +
c/w>=0.40 + prem>=50 + minDTE10 + reentry3 stay FIXED -> signal count preserved).
Levers swept: TP fraction x stop mult x (short,width) geometry, + a time-exit overlay.

Harness: EXACT copy of studies/ndte/stkfade_v1_is.py (validated) — cache loader from
/tmp/bhav_cache_stk, DC10 signal builder, entry-slippage-only spf() model, intrinsic
settlement. FAITHFULNESS: first reproduces deployed v1 (expect n=755 / 64.0% / +10.3%w)
and the v2 cross-check (s2w4 TP.5 stop3 -> ~273 tr / 85.3%) before the sweep is trusted.

Costs: entry slippage only (same as the validated IS harness) — gross of exit slippage
and brokerage/taxes. Geometry rows change which trades pass the c/w gate, so n varies by
geometry; that is reported, not hidden.
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys, glob, json, pickle, collections
from bisect import bisect_right
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import date, timedelta

CACHE = "/tmp/bhav_cache_stk"
SCRATCH = "/private/tmp/claude-501/-Users-sayali-files/d62dc509-cfa1-4925-8c10-c57a2151b1c9/scratchpad"
os.makedirs(SCRATCH, exist_ok=True)
UPICKLE = os.path.join(SCRATCH, "v1sweep_underlyings.pkl")
OUTJSON = os.path.join(SCRATCH, "v1sweep_results.json")

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

# ---- underlyings + DC10 signals (network; disk-cached for reruns) ----
if os.path.exists(UPICKLE):
    print("underlyings from disk cache…", flush=True)
    sig_dc10, close_by_sym = pickle.load(open(UPICKLE, "rb"))
else:
    from engine.config import UNIVERSE
    from engine.data_fetcher import fetch_upstox_historical
    print("underlyings + DC10 breakouts (network)…", flush=True)
    sig_dc10 = []; close_by_sym = {}
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
    pickle.dump((sig_dc10, close_by_sym), open(UPICKLE, "wb"))
print(f"  DC10 signals {len(sig_dc10)}", flush=True)

exps_by = {}
for (sym, e, t) in strikes: exps_by.setdefault((sym, t), set()).add(e)

def run(sigs, SHORT, WIDTH, TP, STOP, TIME_N=0):
    """EXACT logic of stkfade_v1_is.run() (itself stkfade_union.run), parameterized.
    STOP=0 -> no stop. TP=0 -> hold. TIME_N>0 -> book on trading-day N if profitable."""
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
        close = None; t = 0
        for dd in bdays[bisect_right(bdays, ds):bisect_right(bdays, exp)]:
            a = prem.get((sym, exp, sk, typ), {}).get(dd); b = prem.get((sym, exp, lk, typ), {}).get(dd)
            if a is None or b is None: continue
            t += 1; cost = a - b
            if TP > 0 and cost <= credit * (1 - TP): close = max(cost, 0.0); break
            if STOP > 0 and cost >= credit * STOP: close = min(cost, w); break
            if TIME_N > 0 and t >= TIME_N and cost < credit: close = max(cost, 0.0); break
        if close is None:
            cb = close_by_sym.get(sym, {})
            espot = cb.get(exp) or (cb[max(x for x in cb if x <= exp)] if any(x <= exp for x in cb) else c)
            intr = max(0.0, espot - sk) if typ == "CE" else max(0.0, sk - espot)
            intl = max(0.0, espot - lk) if typ == "CE" else max(0.0, lk - espot)
            close = min(max(intr - intl, 0.0), w)
        net = (credit - close) - (se * spf(se) + le * spf(le)) / 100.0
        trades.append((day, net, w, int(net > 0)))
    return trades

def stats(t):
    n = len(t)
    if n == 0: return dict(n=0)
    win = sum(x[3] for x in t) / n * 100
    netw = sum(x[1] for x in t) / sum(x[2] for x in t) * 100
    by = collections.defaultdict(list)
    for x in t: by[x[0].year].append(x)
    peryear = {y: dict(n=len(g), win=sum(a[3] for a in g)/len(g)*100,
                       netw=sum(a[1] for a in g)/sum(a[2] for a in g)*100)
               for y, g in by.items()}
    wy = min(peryear.values(), key=lambda v: v["win"])
    return dict(n=n, win=round(win, 1), netw=round(netw, 1),
                worst_year_win=round(wy["win"], 1),
                neg_years=sum(1 for v in peryear.values() if v["netw"] <= 0),
                peryear={str(y): {k: round(v2, 1) for k, v2 in v.items()} for y, v in sorted(peryear.items())})

# ---- FAITHFULNESS ----
b_v2 = stats(run(sig_dc10, 2, 4, 0.50, 3.0))
b_v1 = stats(run(sig_dc10, 1, 3, 0.75, 2.0))
print(f"\nCROSS-CHECK v2 (s2w4 TP.5 stop3): n={b_v2['n']} win {b_v2['win']}% net {b_v2['netw']:+}%w  (expect ~273/85.3%)")
print(f"BASELINE  v1 (s1w3 TP.75 stop2): n={b_v1['n']} win {b_v1['win']}% net {b_v1['netw']:+}%w  (expect 755/64.0%/+10.3%)", flush=True)

results = {"baseline_v1": b_v1, "crosscheck_v2": b_v2, "grid": [], "time_overlay": []}

# ---- FULL GRID: geometry x TP x stop ----
GEOMS = [(1, 3), (2, 4), (2, 3), (1, 4)]
TPS = [0.40, 0.50, 0.60, 0.75, 0.90, 0.0]     # 0.0 = hold to expiry
STOPS = [1.5, 2.0, 2.5, 3.0, 0.0]             # 0.0 = no stop
print("\n--- IS GRID (config / n / win% / net%w / worst-yr win% / #neg yrs) ---", flush=True)
for (S, W) in GEOMS:
    for TP in TPS:
        for ST in STOPS:
            r = stats(run(sig_dc10, S, W, TP, ST))
            row = dict(short=S, width=W, tp=TP, stop=ST, **{k: r[k] for k in r})
            results["grid"].append(row)
            tps = "hold" if TP == 0 else f"TP{TP:.2f}"
            sts = "none" if ST == 0 else f"x{ST:.1f}"
            if r["n"]:
                print(f"s{S}w{W} {tps} stop{sts}: n={r['n']:4d} win {r['win']:5.1f}% net {r['netw']:+6.1f}%w "
                      f"worstYrWin {r['worst_year_win']:5.1f}% negYrs {r['neg_years']}", flush=True)
            else:
                print(f"s{S}w{W} {tps} stop{sts}: NO TRADES", flush=True)

# ---- TIME-EXIT OVERLAY on deployed geometry ----
print("\n--- TIME-EXIT OVERLAY (s1w3, book on day N if profitable) ---", flush=True)
for TP in (0.75, 0.50):
    for ST in (2.0,):
        for N in (3, 5, 8):
            r = stats(run(sig_dc10, 1, 3, TP, ST, TIME_N=N))
            results["time_overlay"].append(dict(short=1, width=3, tp=TP, stop=ST, time_n=N, **r))
            print(f"s1w3 TP{TP:.2f} stop x{ST:.1f} +day{N}: n={r['n']:4d} win {r['win']:5.1f}% "
                  f"net {r['netw']:+6.1f}%w worstYrWin {r['worst_year_win']:5.1f}% negYrs {r['neg_years']}", flush=True)

json.dump(results, open(OUTJSON, "w"), indent=1)
print(f"\nresults -> {OUTJSON}")
print("DONE-V1-SWEEP")
