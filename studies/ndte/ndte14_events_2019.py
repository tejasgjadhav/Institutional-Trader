"""0DTE EVENT-DAY AVOIDANCE — 2019 -> Sep'24 era (NSE bhavcopy), extending ndte13_events.py back.

Same deployed geometry and the SAME row schema as ndte13_events.py, so the two eras concatenate
into one 2019->date sample:
  NIFTY     weekly  short CE 0.5% OTM, wing +200pts FIXED, FLIP ret5>=1.0 -> PE,
                    filters rv5 < 0.9 and credit >= 0.02% of spot
  BANKNIFTY monthly short CE 0.5% OTM, wing 0.83% of spot, CE-always, no extra filters
Entry = expiry-day OPEN, settle INTRINSIC vs that index's daily close, costs 2.5% of (short+long)
+ Rs20 x 4 legs / lot. Liquidity floor: short-leg CONTRACTS >= 100 (same as ndte3/ndte10).

SENSEX is absent here BY NECESSITY, not by choice: BSE SENSEX weekly options only launched in
2023 and are not in the NSE bhavcopy at all, so the pre-Oct'24 sample is NIFTY + BANKNIFTY only.

Rs figures use TODAY's lot sizes (NIFTY 75, BANKNIFTY 30) so the two eras are comparable; lot
sizes actually changed several times in this window. % of margin is the lot-independent headline.
Out: studies/ndte/ndte14_trades_2019.json
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys, json, time, glob
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np
import pandas as pd
from engine.data_fetcher import SESSION, UPSTOX_BASE
from engine.instruments import encode_key

BHAV = "/tmp/ndte_bhav_idx"
C = "/tmp/ndte_ev"; os.makedirs(C, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
SLIP, BROKER = 2.5, 20.0
MIN_CONTRACTS = 100

BOOKS = [
    dict(name="NIFTY", sym="NIFTY", spot_key="NSE_INDEX|Nifty 50", otm=0.005, wing_pts=200,
         lot=75, cadence="weekly", flip=1.0, rv5_max=0.9, min_credit_pct=0.0002),
    dict(name="BANKNIFTY", sym="BANKNIFTY", spot_key="NSE_INDEX|Nifty Bank", otm=0.005,
         wing_pct=0.0083, lot=30, cadence="monthly", flip=None, rv5_max=None, min_credit_pct=None),
]

def spot_daily(bk):
    cf = f"{C}/spot2019_{bk['name']}.json"
    if os.path.exists(cf): return json.load(open(cf))
    out = {}
    for to, frm in (("2024-09-30", "2018-11-01"),):
        for _ in range(4):
            try:
                r = SESSION.get(f"{UPSTOX_BASE}/v2/historical-candle/"
                                f"{encode_key(bk['spot_key'])}/day/{to}/{frm}", timeout=30)
                if r.status_code == 200:
                    for ts, o, h, l, c, *_ in r.json().get("data", {}).get("candles", []):
                        out[ts[:10]] = [o, h, l, c]
                    break
            except Exception: pass
            time.sleep(3)
    if out: json.dump(out, open(cf, "w"))
    return out

def load_bhav():
    """date -> symbol -> {(strike,typ): (open,high,low,close,contracts)}"""
    days = {}
    for f in sorted(glob.glob(f"{BHAV}/*.csv")):
        ds = os.path.basename(f)[:-4]
        try: df = pd.read_csv(f)
        except Exception: continue
        if df.empty: continue
        per = {}
        for r in df.itertuples(index=False):
            per.setdefault(r.SYMBOL, {})[(float(r.STRIKE_PR), r.OPTION_TYP)] = (
                float(r.OPEN), float(r.HIGH), float(r.LOW), float(r.CLOSE), float(r.CONTRACTS))
        days[ds] = per
    return days

def side_result(bk, legs, s_open, s_close, typ):
    sgn = 1 if typ == "CE" else -1
    st = sorted({k[0] for k in legs if k[1] == typ})
    if len(st) < 8: return None
    near = lambda x: min(st, key=lambda k: abs(k - x))
    Ks = near(s_open * (1 + sgn * bk["otm"]))
    wing = bk.get("wing_pts") or s_open * bk["wing_pct"]
    Kl = near(Ks + sgn * wing)
    W = abs(Kl - Ks)
    if W < wing * 0.5: return None
    vs = legs.get((Ks, typ)); vl = legs.get((Kl, typ))
    if not vs or not vl or vs[0] <= 0 or vs[4] < MIN_CONTRACTS: return None
    so, lo = vs[0], vl[0]
    credit = so - lo
    if credit <= 0 or credit >= W: return None
    intr = (max(0.0, s_close - Ks) - max(0.0, s_close - Kl)) if typ == "CE" \
        else (max(0.0, Ks - s_close) - max(0.0, Kl - s_close))
    settle = min(max(intr, 0.0), W)
    net = credit - settle - ((so + lo) * SLIP / 100 + BROKER * 4 / bk["lot"])
    return net / (W - credit) * 100, net * bk["lot"], credit, W

def main():
    days = load_bhav()
    print(f"loaded {len(days)} expiry days ({min(days)} -> {max(days)})", flush=True)
    rows = []
    for bk in BOOKS:
        spots = spot_daily(bk); sdays = sorted(spots)
        have = sorted(d for d in days if bk["sym"] in days[d] and d in spots)
        if bk["cadence"] == "monthly":       # deployed BANKNIFTY book = monthly expiry only
            by = {}
            for d in have: by[d[:7]] = max(by.get(d[:7], ""), d)
            have = sorted(by.values())
        print(f"[{bk['name']}] {len(have)} usable expiry days", flush=True)

        def rv5(ds):
            i = sdays.index(ds)
            if i < 6: return None
            return float(np.std(np.diff(np.log([spots[sdays[k]][3] for k in range(i - 6, i)]))) * 100)
        def ret5(ds):
            i = sdays.index(ds)
            if i < 6: return 0.0
            return (spots[sdays[i - 1]][3] / spots[sdays[i - 6]][3] - 1) * 100

        for ds in have:
            legs = days[ds][bk["sym"]]
            s_open, s_close = spots[ds][0], spots[ds][3]
            need = ["CE", "PE"] if bk["flip"] is not None else ["CE"]
            res = {}
            for typ in need:
                r = side_result(bk, legs, s_open, s_close, typ)
                if r: res[typ] = r
            if not res: continue
            r5 = ret5(ds)
            typ = "PE" if (bk["flip"] is not None and r5 >= bk["flip"] and "PE" in res) else "CE"
            if typ not in res: continue
            pm, rs, credit, W = res[typ]
            v5 = rv5(ds)
            traded = True
            if bk["rv5_max"] is not None and (v5 is None or v5 >= bk["rv5_max"]): traded = False
            if bk["min_credit_pct"] is not None and credit < bk["min_credit_pct"] * s_open: traded = False
            rows.append(dict(date=ds, book=bk["name"], side=typ, pm=pm, rs=rs, credit=credit,
                             W=W, rv5=v5, ret5=r5, traded=traded, win=int(pm > 0)))
    out = os.path.join(HERE, "ndte14_trades_2019.json")
    json.dump(rows, open(out, "w"), indent=1)
    print(f"\nwrote {len(rows)} rows -> {out}")
    for bk in BOOKS:
        sel = [r for r in rows if r["book"] == bk["name"] and r["traded"]]
        if not sel: continue
        pm = np.array([r["pm"] for r in sel])
        print(f"  {bk['name']:10s} n={len(sel):4d} win {(pm>0).mean()*100:5.1f}%  avg {pm.mean():+6.2f}%m")
    print("DONE-NDTE14")

if __name__ == "__main__":
    main()
