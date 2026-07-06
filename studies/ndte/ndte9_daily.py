"""(A) BANKNIFTY 0DTE on its monthly expiries. (B) NIFTY near-DAILY: every trading day sell the
CE 0.5% OTM on the NEAREST weekly expiry (DTE 0-6), wing +200, entry=day OPEN, exit same day —
intrinsic at close if DTE=0, else both legs' daily CLOSE (intraday round trip). Costs 2.5% of
credit + Rs20x4/lot. Report by DTE bucket. Caches /tmp/ndte_daily + reuse /tmp/ndte_cache legs.
"""
import sys, os, json, time
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import warnings; warnings.filterwarnings("ignore")
import numpy as np
from datetime import date
from engine.data_fetcher import SESSION, UPSTOX_BASE
from engine.instruments import encode_key

CACHE = "/tmp/ndte_daily"; os.makedirs(CACHE, exist_ok=True)
SLIP = 2.5; BROKER = 20.0

def gj(url, params=None, tries=4):
    for i in range(tries):
        try:
            r = SESSION.get(url, params=params, timeout=25)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(4)
    return {}

def contracts(ikey, e):
    cf = f"{CACHE}/chain_{ikey.replace('|','_')}_{e}.json"
    if os.path.exists(cf): return json.load(open(cf))
    j = gj(f"{UPSTOX_BASE}/v2/expired-instruments/option/contract", {"instrument_key": ikey, "expiry_date": e})
    out = j.get("data", []) or []
    if out: json.dump(out, open(cf, "w"))
    return out

def leg_day(key, day):
    kk = key.replace("|", "_")
    for base in (CACHE, "/tmp/ndte_cache"):
        cf = f"{base}/{day}_{kk}.json"
        if os.path.exists(cf):
            v = json.load(open(cf)); return v or None
    j = gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{day}/{day}")
    cs = j.get("data", {}).get("candles", []) if j.get("status") == "success" else []
    v = None
    if cs:
        ts, o, h, l, c, vol, oi = cs[0]
        v = [o, h, l, c, vol, oi]
        json.dump(v, open(f"{CACHE}/{day}_{kk}.json", "w"))
    return v

def run_index(name, ikey, spots, exps, wing_abs=None, wing_pct=None, start="2024-10-01"):
    sdays = sorted(spots)
    rows = []
    for ds in sdays:
        if ds < start or ds > "2026-06-30": continue
        fut = [e for e in exps if e >= ds]
        if not fut: continue
        e = fut[0]
        dte = (date.fromisoformat(e) - date.fromisoformat(ds)).days
        if dte > 6: continue
        ch = contracts(ikey, e)
        ce = sorted([c for c in ch if c["instrument_type"] == "CE"], key=lambda c: float(c["strike_price"]))
        if len(ce) < 10: continue
        strikes = [float(c["strike_price"]) for c in ce]
        bykey = {float(c["strike_price"]): c["instrument_key"] for c in ce}
        lot = int(ce[0].get("lot_size") or 75)
        sp = spots[ds]; s = sp[0]
        near = lambda x: min(strikes, key=lambda k: abs(k - x))
        Ks = near(s * 1.005)
        W_t = wing_abs if wing_abs else s * wing_pct
        Kl = near(Ks + W_t)
        W = Kl - Ks
        if W < W_t * 0.5: continue
        vs = leg_day(bykey[Ks], ds); vl = leg_day(bykey[Kl], ds)
        if not vs or not vl or vs[0] <= 0: continue
        credit = vs[0] - vl[0]
        if credit <= 0: continue
        if dte == 0:
            si = max(0.0, sp[3] - Ks); li = max(0.0, sp[3] - Kl)
        else:
            si, li = vs[3], vl[3]        # same-day close of each leg (intraday round trip)
        pnl = (vs[0] - si) + (li - vl[0])
        cost = (vs[0] + vl[0]) * SLIP / 100 + BROKER * 4 / lot
        net = pnl - cost
        margin = W - credit
        rows.append((ds, dte, net / margin * 100, net * lot))
        if len(rows) % 50 == 0: print(f"  {name} ...{len(rows)}", flush=True)
    print(f"\n=== {name}: {len(rows)} day-trades ===")
    for lab, sel in [("ALL", rows)] + [(f"DTE={d}", [r for r in rows if r[1] == d]) for d in range(7)]:
        if not sel: continue
        pm = np.array([r[2] for r in sel]); rp = np.array([r[3] for r in sel])
        print(f"  {lab:6s} n={len(sel):3d}  win {(pm>0).mean()*100:5.1f}%  avg {pm.mean():+6.2f}%m  tot Rs{rp.sum():+9,.0f}  worst Rs{rp.min():+8,.0f}")
    return rows

def main():
    nspots = json.load(open("/tmp/ndte_cache/spot2019.json"))
    # (A) BANKNIFTY 0DTE monthlies
    bkey = "NSE_INDEX|Nifty Bank"
    cf = f"{CACHE}/bnf_spot.json"
    if os.path.exists(cf):
        bspots = json.load(open(cf))
    else:
        j = gj(f"{UPSTOX_BASE}/v2/historical-candle/{encode_key(bkey)}/day/2026-07-06/2024-09-01")
        bspots = {ts[:10]: [o, h, l, c] for ts, o, h, l, c, *_ in j.get("data", {}).get("candles", [])}
        json.dump(bspots, open(cf, "w"))
    bexps = sorted(gj(f"{UPSTOX_BASE}/v2/expired-instruments/expiries", {"instrument_key": bkey}).get("data", []) or [])
    print(f"BANKNIFTY: {len(bexps)} expiries, {len(bspots)} spot days")
    bnf0 = [(e,) for e in bexps]
    # 0DTE only for BNF: run with a spots dict restricted to expiry days
    run_index("BANKNIFTY 0DTE (monthlies)", bkey, {d: v for d, v in bspots.items() if d in bexps},
              bexps, wing_pct=0.0083)
    # (B) NIFTY near-daily 0-6 DTE
    nexps = sorted(gj(f"{UPSTOX_BASE}/v2/expired-instruments/expiries", {"instrument_key": "NSE_INDEX|Nifty 50"}).get("data", []) or [])
    run_index("NIFTY near-daily (nearest weekly, exit same-day close)", "NSE_INDEX|Nifty 50",
              nspots, nexps, wing_abs=200)
    print("DONE-NDTE9")

if __name__ == "__main__":
    main()
