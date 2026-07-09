"""NON-FADE intraday search: LONG-GAMMA structures on NIFTY expiry day (goal loop 2026-07-09).
Everything short-premium ("fade family") is excluded by the user. Candidates:
  A STRADDLE   - buy ATM CE+PE at the OPEN, hold to same-day settlement (intrinsic vs debit)
  B GAPFOLLOW  - overnight gap >= thr%: buy ATM debit vertical in the gap direction at OPEN
                 (buy ATM, sell 200 pts further OTM), settle intrinsic
  C TRENDFOLLOW- (1-min era only) at T in {09:45,10:00,10:30}: open->spot(T) move >= thr%:
                 buy ATM(spot_T) debit vertical with the move, settle intrinsic
A+B run on bhavcopy 2019-02->Sep'24 (IS) AND Upstox 1-min era Oct'24->Jul'26 (OOS).
Subsets: all / calm (rv5<0.9) / hot (rv5>=0.9) - hypothesis: long gamma pays on the hot weeks
the deployed calm-filtered fade book skips.
Costs: 2.5% slippage on premium traded + Rs20 x 4 /lot. Liquidity (bhav): legs CONTRACTS>=100.
Return metric: net / debit paid (the capital at risk = margin for long structures).
Results JSON: /tmp/ndte12_results.json
"""
import sys, os, json, time
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import warnings; warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from ndte2_bt import get_contracts, get_expiries
from ndte11_entrytime import intra, spot5m, spot_at, entry_bar   # cached fetchers
from ndte3_bhav_bt import lot_for

BHAV = "/tmp/ndte_bhav"
SLIP_PCT = 2.5; BROKER = 20.0
spots = json.load(open("/tmp/ndte_cache/spot2019.json"))
sdays = sorted(spots)

def rv5(ds):
    i = sdays.index(ds)
    if i < 6: return None
    closes = np.array([spots[sdays[j]][3] for j in range(i - 6, i)])
    return np.std(np.diff(np.log(closes))) * 100

def gap_pct(ds):
    i = sdays.index(ds)
    if i < 1: return None
    prevc = spots[sdays[i - 1]][3]
    return (spots[ds][0] - prevc) / prevc * 100

def acc(res, r):
    if r: res.append(r)

# ---------- bhav era (entry = OPEN print, exit = settlement) ----------
def bhav_days():
    out = []
    for f in sorted(os.listdir(BHAV)):
        if not f.endswith(".csv"): continue
        ds = f[:-4]
        sp = spots.get(ds)
        if not sp or rv5(ds) is None: continue
        df = pd.read_csv(os.path.join(BHAV, f))
        legs = {(float(r["STRIKE_PR"]), r["OPTION_TYP"]): (float(r["OPEN"]), float(r["CLOSE"]), float(r.get("CONTRACTS", 0)))
                for _, r in df.iterrows()}
        strikes = sorted(set(k[0] for k in legs))
        if len(strikes) < 10: continue
        out.append(dict(e=ds, lot=lot_for(ds), spot=sp[0], close=sp[3], legs=legs, strikes=strikes))
    return out

def bhav_straddle(d):
    K = min(d["strikes"], key=lambda s: abs(s - d["spot"]))
    ce, pe = d["legs"].get((K, "CE")), d["legs"].get((K, "PE"))
    if not ce or not pe or ce[0] <= 0 or pe[0] <= 0 or ce[2] < 100 or pe[2] < 100: return None
    debit = ce[0] + pe[0]
    cost = debit * SLIP_PCT / 100 + BROKER * 4 / d["lot"]
    payoff = abs(d["close"] - K)
    net = payoff - debit - cost
    return net / debit * 100, net * d["lot"], debit

def bhav_gapfollow(d, thr, width=200):
    g = gap_pct(d["e"])
    if g is None or abs(g) < thr: return None
    typ = "CE" if g > 0 else "PE"
    K = min(d["strikes"], key=lambda s: abs(s - d["spot"]))
    Kw = min(d["strikes"], key=lambda s: abs(s - (K + width if typ == "CE" else K - width)))
    if abs(Kw - K) < 100: return None
    a, w = d["legs"].get((K, typ)), d["legs"].get((Kw, typ))
    if not a or not w or a[0] <= 0 or a[2] < 100 or w[2] < 1: return None
    debit = a[0] - w[0]
    if debit <= 0: return None
    cost = (a[0] + w[0]) * SLIP_PCT / 100 + BROKER * 4 / d["lot"]
    ai = max(0.0, (d["close"] - K) if typ == "CE" else (K - d["close"]))
    wi = max(0.0, (d["close"] - Kw) if typ == "CE" else (Kw - d["close"]))
    net = (ai - wi) - debit - cost
    return net / debit * 100, net * d["lot"], debit

# ---------- 1-min era (Oct'24->) ----------
def recent_days():
    out = []
    for e in get_expiries("NIFTY"):
        sp = spots.get(e)
        if not sp or rv5(e) is None: continue
        sbars = spot5m(e)
        if not sbars: continue
        chain = get_contracts("NIFTY", e)
        strikes = sorted({float(c["strike_price"]) for c in chain})
        bykey = {(float(c["strike_price"]), c["instrument_type"]): c["instrument_key"] for c in chain}
        lot = int(chain[0].get("lot_size") or 75)
        if len(strikes) < 10: continue
        out.append(dict(e=e, lot=lot, spot=sp[0], close=sp[3], sbars=sbars, strikes=strikes, bykey=bykey, bars={}))
    return out

def bars_for(d, K, typ):
    if (K, typ) not in d["bars"]:
        key = d["bykey"].get((K, typ))
        d["bars"][(K, typ)] = intra(key, d["e"]) if key else None
    return d["bars"][(K, typ)]

def open_prem(bars):
    eb = entry_bar(bars, "09:16") if bars else None
    return eb[1] if eb else None

def recent_straddle(d):
    K = min(d["strikes"], key=lambda s: abs(s - d["spot"]))
    ce, pe = open_prem(bars_for(d, K, "CE")), open_prem(bars_for(d, K, "PE"))
    if not ce or not pe: return None
    debit = ce + pe
    cost = debit * SLIP_PCT / 100 + BROKER * 4 / d["lot"]
    net = abs(d["close"] - K) - debit - cost
    return net / debit * 100, net * d["lot"], debit

def recent_gapfollow(d, thr, width=200):
    g = gap_pct(d["e"])
    if g is None or abs(g) < thr: return None
    typ = "CE" if g > 0 else "PE"
    K = min(d["strikes"], key=lambda s: abs(s - d["spot"]))
    Kw = min(d["strikes"], key=lambda s: abs(s - (K + width if typ == "CE" else K - width)))
    if abs(Kw - K) < 100: return None
    a, w = open_prem(bars_for(d, K, typ)), open_prem(bars_for(d, Kw, typ))
    if not a or w is None: return None
    debit = a - w
    if debit <= 0: return None
    cost = (a + w) * SLIP_PCT / 100 + BROKER * 4 / d["lot"]
    ai = max(0.0, (d["close"] - K) if typ == "CE" else (K - d["close"]))
    wi = max(0.0, (d["close"] - Kw) if typ == "CE" else (Kw - d["close"]))
    net = (ai - wi) - debit - cost
    return net / debit * 100, net * d["lot"], debit

def recent_trendfollow(d, T, thr, width=200):
    s_t = spot_at(d["sbars"], T)
    if s_t is None: return None
    mv = (s_t - d["spot"]) / d["spot"] * 100
    if abs(mv) < thr: return None
    typ = "CE" if mv > 0 else "PE"
    K = min(d["strikes"], key=lambda s: abs(s - s_t))
    Kw = min(d["strikes"], key=lambda s: abs(s - (K + width if typ == "CE" else K - width)))
    if abs(Kw - K) < 100: return None
    ba, bw = bars_for(d, K, typ), bars_for(d, Kw, typ)
    if not ba: return None
    eb = entry_bar(ba, T)
    if not eb: return None
    a = eb[1]
    w = 0.0
    if bw:
        last = None
        for c in bw:
            if c[0] <= eb[0]: last = c
            else: break
        w = last[4] if last else (entry_bar(bw, T) or [0, 0])[1]
    debit = a - w
    if debit <= 0 or a <= 0: return None
    cost = (a + w) * SLIP_PCT / 100 + BROKER * 4 / d["lot"]
    ai = max(0.0, (d["close"] - K) if typ == "CE" else (K - d["close"]))
    wi = max(0.0, (d["close"] - Kw) if typ == "CE" else (Kw - d["close"]))
    net = (ai - wi) - debit - cost
    return net / debit * 100, net * d["lot"], debit

def report(label, rows, out):
    for sub in ("all", "calm", "hot"):
        res = []
        for e, r in rows:
            v = rv5(e)
            if sub == "calm" and v >= 0.9: continue
            if sub == "hot" and v < 0.9: continue
            acc(res, r)
        if len(res) < 5: continue
        pm = np.array([x[0] for x in res]); rp = np.array([x[1] for x in res])
        out[f"{label}|{sub}"] = dict(n=len(res), win=round((pm > 0).mean() * 100, 1), avg=round(pm.mean(), 2),
                                     tot=round(rp.sum()), worst=round(rp.min()), best=round(rp.max()))
        print(f"{label:28s} {sub:4s} | {len(res):3d} {(pm>0).mean()*100:5.1f}% {pm.mean():+7.1f}%d {rp.sum():+9.0f} worst{rp.min():+8.0f}", flush=True)

def main():
    out = {}
    print("== BHAV era 2019->Sep'24 (IS) ==", flush=True)
    bd = bhav_days(); print(f"{len(bd)} bhav expiry days", flush=True)
    report("IS STRADDLE@open", [(d["e"], bhav_straddle(d)) for d in bd], out)
    for thr in (0.2, 0.4):
        report(f"IS GAPFOLLOW>={thr}%", [(d["e"], bhav_gapfollow(d, thr)) for d in bd], out)
    print("== 1-min era Oct'24->Jul'26 (OOS for A/B; only-era for C) ==", flush=True)
    rd = recent_days(); print(f"{len(rd)} recent expiry days", flush=True)
    with ThreadPoolExecutor(max_workers=6) as ex:   # warm ATM CE/PE caches in parallel
        list(ex.map(lambda d: (bars_for(d, min(d["strikes"], key=lambda s: abs(s - d["spot"])), "CE"),
                               bars_for(d, min(d["strikes"], key=lambda s: abs(s - d["spot"])), "PE")), rd))
    report("OOS STRADDLE@open", [(d["e"], recent_straddle(d)) for d in rd], out)
    for thr in (0.2, 0.4):
        report(f"OOS GAPFOLLOW>={thr}%", [(d["e"], recent_gapfollow(d, thr)) for d in rd], out)
    for T in ("09:45", "10:00", "10:30"):
        for thr in (0.15, 0.3):
            report(f"TRENDFOLLOW {T}>={thr}%", [(d["e"], recent_trendfollow(d, T, thr)) for d in rd], out)
    json.dump(out, open("/tmp/ndte12_results.json", "w"), indent=1)
    print("DONE-NDTE12")

if __name__ == "__main__":
    main()
