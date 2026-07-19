"""2019->Sep'24 (NSE bhavcopy) era of the D5/D10/D15/D20 standalone-Donchian study.
Adapted from stkfade_union.py: instead of merging DC{5,10,15,20} into one UNION stream, it runs
each window STANDALONE (its own breakout stream + its own re-entry gap) and reports each separately.
Deployed v2 config (identical to the Oct'24 era): short 2-OTM, width 4, TP 50% of credit, stop 3x,
gate credit/width>=0.40 + short prem>=50, min-DTE 10, reentry 3d. Entry at signal-day CLOSE (matches
the engine's 15:10 scan). Cost = prior-study spf per-leg slippage (se*spf(se)+le*spf(le))/100, the
same model the deployed-era cross-check script uses. Settle intrinsic at expiry.

TP/stop detection on daily CLOSE spread cost (short.CLOSE - long.CLOSE), TP checked first — the
SAME method as the documented v2 pipeline (stkfade_union.py) and the Oct'24 era, so the two eras
are comparable and D10 cross-checks the documented v2 IS figure (85.35% win / 273 trades / +26.2%w,
STOCK_FADE_TP50_UPGRADE.md). A daily-OHLC-LOW variant (short.LOW - long.HIGH) was tried and REJECTED:
it inflates win to ~98% by assuming both legs touch favorable extremes at the same instant — an
over-optimistic intraday-touch artifact that daily bhavcopy can't support. Close-only is honest here.
Out: /tmp/d5_10_15_20_bhav.json   Reports per config: n, /mo, win%, net %width, per-year.
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys, glob, collections, json
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import date, timedelta
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical

CACHE = "/tmp/bhav_cache_stk"
MIN_DTE, REENTRY, MIN_CW, MIN_PREM, MIN_OI = 10, 3, 0.40, 50.0, 1
SHORT, WIDTH, TP, STOP = 2, 4, 0.5, 3.0
DCS = [5, 10, 15, 20]
def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0
def expiso(x): return pd.to_datetime(x).date()

print("loading bhav cache…", flush=True)
# per (sym,exp,strike,typ): dict day-> (close, low, high, oi)
book = collections.defaultdict(dict)
strikes = collections.defaultdict(set); bdays = set()
for f in sorted(glob.glob(f"{CACHE}/*.csv")):
    d = os.path.basename(f)[:-4]
    try: df = pd.read_csv(f)
    except Exception: continue
    if df.empty or "OPTION_TYP" not in df: continue
    df = df[df["OPTION_TYP"].isin(["CE", "PE"])]
    if df.empty: continue
    bdays.add(d)
    for r in df.itertuples(index=False):
        try: e = expiso(r.EXPIRY_DT).isoformat()
        except Exception: continue
        k = (r.SYMBOL, e, float(r.STRIKE_PR), r.OPTION_TYP)
        book[k][d] = (float(r.CLOSE), float(r.LOW), float(r.HIGH), float(r.OPEN_INT))
        strikes[(r.SYMBOL, e, r.OPTION_TYP)].add(float(r.STRIKE_PR))
bdays = sorted(bdays); bset = set(bdays)
print(f"  {len(bdays)} days  ({bdays[0]} -> {bdays[-1]})", flush=True)

print("underlyings + breakouts…", flush=True)
streams = {dc: [] for dc in DCS}   # dc -> list of (day, sym, typ, close)
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
            streams[dc].append((day, sym, typ, c))
for dc in DCS: streams[dc].sort()
print("  signals: " + " ".join(f"D{dc}={len(streams[dc])}" for dc in DCS), flush=True)

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
        se_r = book.get((sym, exp, sk, typ), {}).get(ds); le_r = book.get((sym, exp, lk, typ), {}).get(ds)
        if se_r is None or le_r is None: continue
        se, le, soi = se_r[0], le_r[0], se_r[3]
        if se < MIN_PREM or soi < MIN_OI: continue
        credit = se - le; w = abs(sk - lk)
        if credit <= 0 or credit >= w or credit / w < MIN_CW: continue
        last[kk] = day
        close = None
        for dd in (x for x in bdays if ds < x <= exp):
            a = book.get((sym, exp, sk, typ), {}).get(dd); b = book.get((sym, exp, lk, typ), {}).get(dd)
            if a is None or b is None: continue
            cost = a[0] - b[0]         # daily-CLOSE spread cost (matches the documented v2 pipeline)
            if TP > 0 and cost <= credit * (1 - TP): close = max(cost, 0.0); break
            if cost >= credit * STOP: close = min(cost, w); break
        if close is None:
            cb = close_by_sym.get(sym, {})
            espot = cb.get(exp) or (cb[max(x for x in cb if x <= exp)] if any(x <= exp for x in cb) else c)
            intr = max(0.0, espot - sk) if typ == "CE" else max(0.0, sk - espot)
            intl = max(0.0, espot - lk) if typ == "CE" else max(0.0, lk - espot)
            close = min(max(intr - intl, 0.0), w)
        net = (credit - close) - (se * spf(se) + le * spf(le)) / 100.0
        trades.append(dict(y=day.year, net=float(net), w=float(w), win=int(net > 0), cw=round(credit / w, 3)))
    return trades

out = {}
print(f"\n=== v2 fade (gate>=0.40) STANDALONE D5/D10/D15/D20, bhavcopy 2019->Sep'24 ===")
print(f"{'cfg':4s} {'n':>4s} {'/mo':>5s} {'win%':>6s} {'net %width':>11s}")
for dc in DCS:
    t = run(streams[dc]); out[f"D{dc}"] = t
    df = pd.DataFrame(t)
    if len(df) == 0: print(f"D{dc:<3d} 0"); continue
    months = len({(x['y'], 0) for x in t}) or 1   # placeholder; real /mo computed on stitch
    permo = len(df) / (len(bdays) / 21.0)
    print(f"D{dc:<3d} {len(df):4d} {permo:5.1f} {df.win.mean()*100:6.1f} {df.net.sum()/df.w.sum()*100:+11.1f}")
json.dump(out, open("/tmp/d5_10_15_20_bhav.json", "w"))
print("\n-- per year --")
for dc in DCS:
    df = pd.DataFrame(out[f"D{dc}"])
    if len(df) == 0: continue
    ys = " · ".join(f"{y}:{g.win.mean()*100:.0f}%/{g.net.sum()/g.w.sum()*100:+.0f}%w(n{len(g)})" for y, g in df.groupby('y'))
    print(f"  D{dc}: {ys}")
print("DONE-BHAV")
