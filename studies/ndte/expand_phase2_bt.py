"""PHASE 2 — real bhavcopy backtest of the deployed v2 UNION fade+gate on each expansion candidate,
identical geometry/gates/costs to stkfade_union.py (UNION Donchian 5/10/15/20 -> SELL 2-OTM credit
spread width 4, c/w>=0.40, prem>=50, OI>=1, min-DTE 10, reentry 3d, TP-50, stop-3x, settle intrinsic
at expiry, 2.5%/leg entry slippage). IS = NSE bhavcopy 2019->Sep'24.

Memory-safe: loads ONE symbol at a time from the per-symbol caches produced by
expand_split_bysym.py (/tmp/bysym_stk, /tmp/bysym_exp) — the full nested dict won't fit in 8 GB.
Runs the deployed UNIVERSE as BASELINE and every candidate individually, applies the decision rule
(gated_n>=15, win>=80%, net%w>0, positive in most years), and projects blended stats before/after.
Writes /tmp/expand_phase2.json. Gross of costs beyond the modeled 2.5%; single-regime IS only."""
import warnings; warnings.filterwarnings("ignore")
import os, sys, glob, collections, json, csv
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import date, timedelta
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical

MIN_DTE, REENTRY, MIN_CW, MIN_PREM, MIN_OI = 10, 3, 0.40, 50.0, 1
SHORT, WIDTH, TP, STOP = 2, 4, 0.5, 3.0
DCS = [5, 10, 15, 20]
def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0
def expiso(x): return pd.to_datetime(x).date()

# global set of option business days (union of all per-symbol day columns) — filled lazily
_ALLDAYS = {"stk": None, "exp": None}
def cache_days(kind):
    # business days == filenames of the ORIGINAL day-partitioned cache (instant, no row scan)
    if _ALLDAYS[kind] is None:
        base = "/tmp/bhav_cache_stk" if kind == "stk" else "/tmp/bhav_cache_expand"
        _ALLDAYS[kind] = sorted(os.path.basename(f)[:-4] for f in glob.glob(base + "/*.csv"))
    return _ALLDAYS[kind]

def load_symbol(kind, sym):
    """Return (prem, oi, strikes) dicts for ONE symbol from its per-symbol cache file.
    pandas C-parser + vectorized normalization, then dict build via zip over numpy arrays."""
    base = "/tmp/bysym_stk" if kind == "stk" else "/tmp/bysym_exp"
    path = os.path.join(base, sym + ".csv")
    prem = {}; oi = {}; strikes = collections.defaultdict(set)
    if not os.path.exists(path): return prem, oi, strikes
    try:
        df = pd.read_csv(path)
    except Exception:
        return prem, oi, strikes
    if df.empty: return prem, oi, strikes
    df = df.dropna(subset=["EXPIRY_DT", "STRIKE_PR", "OPTION_TYP", "CLOSE", "day"])
    exp = pd.to_datetime(df["EXPIRY_DT"], errors="coerce").dt.date.map(
        lambda x: x.isoformat() if pd.notna(x) else None)
    sk = df["STRIKE_PR"].astype(float).values
    ot = df["OPTION_TYP"].astype(str).str.strip().values
    cl = df["CLOSE"].astype(float).values
    oint = pd.to_numeric(df["OPEN_INT"], errors="coerce").fillna(0.0).astype(float).values
    day = df["day"].astype(str).values
    expv = exp.values
    for e, s, o, c, oi_, d in zip(expv, sk, ot, cl, oint, day):
        if e is None: continue
        k = (e, s, o)
        pm = prem.get(k)
        if pm is None: prem[k] = {d: c}; oi[k] = {d: oi_}
        else: pm[d] = c; oi[k][d] = oi_
        strikes[(e, o)].add(s)
    return prem, oi, strikes

_UND = {}
def underlying(sym, maxday):
    if sym in _UND: return _UND[sym]
    try:
        u = fetch_upstox_historical(sym + ".NS", unit="days", interval=1, from_date="2018-06-01", to_date=maxday)
    except Exception:
        u = None
    if u is None or u.empty or len(u) < 40:
        _UND[sym] = (None, {}); return _UND[sym]
    u = u.sort_index()
    cb = {ix.date().isoformat(): float(u["Close"].loc[ix]) for ix in u.index}
    _UND[sym] = (u, cb); return _UND[sym]

def signals_one(sym, bset, maxday):
    u, cb = underlying(sym, maxday)
    if u is None: return [], {}
    sig = {}
    for dc in DCS:
        hi = u["High"].rolling(dc).max().shift(1); lo = u["Low"].rolling(dc).min().shift(1)
        for i in range(max(dc, 20), len(u) - 1):
            day = u.index[i].date(); ds = day.isoformat()
            if ds not in bset: continue
            c = float(u["Close"].iloc[i])
            typ = "CE" if c > float(hi.iloc[i]) else ("PE" if c < float(lo.iloc[i]) else None)
            if not typ: continue
            if day not in sig: sig[day] = (typ, c)
    out = sorted((d, t, c) for d, (t, c) in sig.items())
    return out, cb

def run_symbol(sym, sig, cb, prem, oi, strikes, bdays):
    exps_by = {}
    for (e, t) in strikes: exps_by.setdefault(t, set()).add(e)
    trades = []; last = {}
    for (day, typ, c) in sig:
        if last.get(typ) and (day - last[typ]).days < REENTRY: continue
        fut = sorted(e for e in exps_by.get(typ, ()) if date.fromisoformat(e) >= day + timedelta(days=MIN_DTE))
        if not fut: continue
        exp = fut[0]; ks = sorted(strikes.get((exp, typ), []))
        if len(ks) < SHORT + WIDTH + 2: continue
        atm = min(range(len(ks)), key=lambda j: abs(ks[j] - c))
        si, li = (atm + SHORT, atm + SHORT + WIDTH) if typ == "CE" else (atm - SHORT, atm - SHORT - WIDTH)
        if si < 0 or li < 0 or si >= len(ks) or li >= len(ks): continue
        sk, lk = ks[si], ks[li]; ds = day.isoformat()
        se = prem.get((exp, sk, typ), {}).get(ds); le = prem.get((exp, lk, typ), {}).get(ds)
        soi = oi.get((exp, sk, typ), {}).get(ds, 0)
        if se is None or le is None or se < MIN_PREM or soi < MIN_OI: continue
        credit = se - le; w = abs(sk - lk)
        if credit <= 0 or credit >= w or credit / w < MIN_CW: continue
        last[typ] = day
        close = None
        for dd in (x for x in bdays if ds < x <= exp):
            a = prem.get((exp, sk, typ), {}).get(dd); b = prem.get((exp, lk, typ), {}).get(dd)
            if a is None or b is None: continue
            cost = a - b
            if TP > 0 and cost <= credit * (1 - TP): close = max(cost, 0.0); break
            if cost >= credit * STOP: close = min(cost, w); break
        if close is None:
            espot = cb.get(exp) or (cb[max(x for x in cb if x <= exp)] if any(x <= exp for x in cb) else c)
            intr = max(0.0, espot - sk) if typ == "CE" else max(0.0, sk - espot)
            intl = max(0.0, espot - lk) if typ == "CE" else max(0.0, lk - espot)
            close = min(max(intr - intl, 0.0), w)
        net = (credit - close) - (se * spf(se) + le * spf(le)) / 100.0
        trades.append((day, net, w, int(net > 0)))
    return trades

def backtest(kind, syms):
    bdays = cache_days(kind); bset = set(bdays); maxday = max(bdays)
    all_tr = {}
    for i, sym in enumerate(syms):
        prem, oi, strikes = load_symbol(kind, sym)
        if not strikes: all_tr[sym] = []; continue
        sig, cb = signals_one(sym, bset, maxday)
        all_tr[sym] = run_symbol(sym, sig, cb, prem, oi, strikes, bdays)
        if (i + 1) % 20 == 0: print(f"  {kind}: {i+1}/{len(syms)} symbols", flush=True)
    return all_tr

def stats(t):
    if not t: return dict(n=0)
    n = len(t); months = len({(x[0].year, x[0].month) for x in t})
    win = sum(x[3] for x in t) / n * 100
    netw = sum(x[1] for x in t) / sum(x[2] for x in t) * 100
    by = collections.defaultdict(list)
    for x in t: by[x[0].year].append(x)
    yrs = {y: (len(g), sum(a[3] for a in g)/len(g)*100, sum(a[1] for a in g)/sum(a[2] for a in g)*100)
           for y, g in by.items()}
    pos_yrs = sum(1 for y in yrs if yrs[y][2] > 0)
    return dict(n=n, months=months, per_mo=round(n/months, 2), win=round(win, 1),
                netw=round(netw, 1), pos_yrs=pos_yrs, tot_yrs=len(yrs),
                yrs={y: (yrs[y][0], round(yrs[y][1], 1), round(yrs[y][2], 1)) for y in sorted(yrs)})

# ---- BASELINE ----
print("BASELINE: deployed UNIVERSE (per-symbol cache)…", flush=True)
uni_syms = [s.replace(".NS", "") for s in UNIVERSE]
base_map = backtest("stk", uni_syms)
base_tr = [tr for lst in base_map.values() for tr in lst]
base = stats(base_tr)
print(f"BASELINE: {base['n']} trades, {base['per_mo']}/mo, win {base['win']}%, net {base['netw']}%w, "
      f"pos {base['pos_yrs']}/{base['tot_yrs']}yr", flush=True)

# ---- CANDIDATES ----
print("\nCANDIDATES…", flush=True)
cand_syms = sorted(os.path.basename(f)[:-4] for f in glob.glob("/tmp/bysym_exp/*.csv"))
cand_map = backtest("exp", cand_syms)
results = {s: stats(cand_map[s]) for s in cand_syms}

def qualifies(s):
    return s.get("n", 0) >= 15 and s.get("win", 0) >= 80 and s.get("netw", -1) > 0 \
        and s.get("pos_yrs", 0) >= s.get("tot_yrs", 99) - 1

proposed = [s for s in cand_syms if qualifies(results[s])]
proposed.sort(key=lambda s: results[s]["netw"], reverse=True)

print("\n==== PER-CANDIDATE (gated) — sorted by net%w ====", flush=True)
print(f"{'SYM':<13}{'n':>4}{'/mo':>6}{'win%':>6}{'net%w':>7}{'posYr':>7}  PROP", flush=True)
for s in sorted(cand_syms, key=lambda x: results[x].get("netw", -999), reverse=True):
    st = results[s]
    if st.get("n", 0) == 0:
        print(f"{s:<13}   0   (no gated trades)", flush=True); continue
    tag = "YES" if s in proposed else ""
    print(f"{s:<13}{st['n']:>4}{st['per_mo']:>6}{st['win']:>6}{st['netw']:>7}"
          f"{str(st['pos_yrs'])+'/'+str(st['tot_yrs']):>7}  {tag}", flush=True)

def scenario(names, label):
    tr = [t for s in names for t in cand_map[s]]
    add = stats(tr); blend = stats(base_tr + tr)
    print(f"\n[{label}] add {len(names)} names", flush=True)
    print(f"  names: {names}", flush=True)
    print(f"  ADDED  : n={add.get('n',0)} {add.get('per_mo',0)}/mo win {add.get('win',0)}% "
          f"net {add.get('netw',0)}%w pos {add.get('pos_yrs',0)}/{add.get('tot_yrs',0)}yr", flush=True)
    print(f"  BLEND  : n={blend['n']} {blend['per_mo']}/mo win {blend['win']}% "
          f"net {blend['netw']}%w pos {blend['pos_yrs']}/{blend['tot_yrs']}yr", flush=True)
    return {"names": names, "added": add, "blended": blend}

# scenario tiers (the gate is structural and transfers across names — see CW_BUCKET_ANALYSIS.md,
# FUNDAMENTAL_TECHNICAL_FINDING.md — so pooling small-n names is defensible; strict n>=15 is the
# conservative floor)
strict = proposed  # n>=15, win>=80, netw>0, pos most yrs
tier5 = sorted([s for s in cand_syms if results[s].get("n",0) >= 5 and results[s].get("win",0) >= 80
                and results[s].get("netw",-1) > 0
                and results[s].get("pos_yrs",0) >= results[s].get("tot_yrs",99)-1],
               key=lambda s: results[s]["netw"], reverse=True)
allpos = sorted([s for s in cand_syms if results[s].get("n",0) >= 1 and results[s].get("netw",-1) > 0],
                key=lambda s: results[s]["netw"], reverse=True)
allgated = sorted([s for s in cand_syms if results[s].get("n",0) >= 1],
                  key=lambda s: results[s].get("netw",-999), reverse=True)

print("\n==== BASELINE ====", flush=True)
print(f"BASELINE : n={base['n']} {base['per_mo']}/mo win {base['win']}% net {base['netw']}%w pos {base['pos_yrs']}/{base['tot_yrs']}yr", flush=True)
print("\n==== BLEND SCENARIOS ====", flush=True)
sc_strict = scenario(strict, "STRICT n>=15,win>=80,pos")
sc_tier5 = scenario(tier5, "TIER5 n>=5,win>=80,pos")
sc_allpos = scenario(allpos, "ALL-POSITIVE netw>0")
sc_allgated = scenario(allgated, "ALL-GATED (incl losers, sanity)")

out = {"baseline": base, "scenarios": {"strict": sc_strict, "tier5": sc_tier5,
       "all_positive": sc_allpos, "all_gated": sc_allgated}, "proposed_strict": strict,
       "per_candidate": results}
json.dump(out, open("/tmp/expand_phase2.json", "w"), indent=1, default=str)
print("\nwrote /tmp/expand_phase2.json\nDONE-PHASE2", flush=True)
