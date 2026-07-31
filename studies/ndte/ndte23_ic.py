"""0DTE NIFTY iron-condor quick test (PATH_TO_1L iteration 1).
Same conventions as studies/ndte/ndte3_bhav_bt.py: NSE bhavcopy expiry days
2019-02 -> 2024-09, entry=OPEN, exit=CLOSE(=settlement), no stop, liquidity
short CONTRACTS>=100 / wing>=1, costs 2.5% of gross credit + Rs20 x legs x 2
per lot, margin = W - net_credit (one-sided for the condor). Lot sizes per era.
Configs: CE d=0.5% W=200 (deployed baseline, must reproduce ~84.4%/+3.17%m),
PE-only at d in {0.5,0.75,1.0,1.5}%, IC = CE0.5 + PE at each d.
"""
import os, json, sys
import numpy as np
import pandas as pd

BHAV = "/tmp/ndte_bhav"
SPOT_CACHE = "/tmp/ndte_cache/spot2019.json"
SLIP_PCT, BROKER, W = 2.5, 20.0, 200.0

def spot_daily():
    os.makedirs("/tmp/ndte_cache", exist_ok=True)
    if os.path.exists(SPOT_CACHE):
        return json.load(open(SPOT_CACHE))
    sys.path.insert(0, "/Users/sayali/files/institutional-trader")
    import warnings; warnings.filterwarnings("ignore")
    from engine.data_fetcher import SESSION, UPSTOX_BASE
    from engine.instruments import encode_key
    out = {}
    for to, frm in (("2024-09-30", "2019-01-01"),):
        r = SESSION.get(f"{UPSTOX_BASE}/v2/historical-candle/{encode_key('NSE_INDEX|Nifty 50')}/day/{to}/{frm}", timeout=30)
        for ts, o, h, l, c, *_ in r.json().get("data", {}).get("candles", []):
            out[ts[:10]] = [o, h, l, c]
    json.dump(out, open(SPOT_CACHE, "w"))
    return out

def lot_for(ds):
    if ds < "2021-04-01": return 75
    if ds < "2024-11-20": return 50
    return 75

def load_days():
    spots = spot_daily()
    days = []
    for f in sorted(os.listdir(BHAV)):
        if not f.endswith(".csv"): continue
        ds = f[:-4]
        sp = spots.get(ds)
        if not sp: continue
        df = pd.read_csv(os.path.join(BHAV, f))
        legs = {}
        for _, r in df.iterrows():
            legs[(float(r["STRIKE_PR"]), r["OPTION_TYP"])] = (
                float(r["OPEN"]), float(r["HIGH"]), float(r["LOW"]), float(r["CLOSE"]),
                float(r.get("CONTRACTS", 0)))
        strikes = sorted(set(k[0] for k in legs))
        if len(strikes) < 10: continue
        days.append({"e": ds, "lot": lot_for(ds), "spot": sp[0],
                     "legs": legs, "strikes": strikes})
    return days

def spread(legs, Ks, Kl, typ):
    vs, vl = legs.get((Ks, typ)), legs.get((Kl, typ))
    if not vs or not vl or vs[0] <= 0 or vl[0] < 0: return None
    if vs[4] < 100 or vl[4] < 1: return None
    credit = vs[0] - vl[0]
    if credit <= 0: return None
    pnl = (vs[0] - vs[3]) + (vl[3] - vl[0])       # no stop
    return pnl, vs[0] + vl[0], credit

def run(days, ce_d, pe_d):
    """ce_d/pe_d = fractional OTM distance or None to skip that side."""
    rows = []
    for r in days:
        s, legs, strikes, lot = r["spot"], r["legs"], r["strikes"], r["lot"]
        near = lambda x: min(strikes, key=lambda st: abs(st - x))
        pnls, gcred, ncred, nlegs = [], 0.0, 0.0, 0
        bad = False
        for typ, sgn, d in (("CE", 1, ce_d), ("PE", -1, pe_d)):
            if d is None: continue
            Ks = near(s * (1 + sgn * d)); Kl = near(Ks + sgn * W)
            if abs(Kl - Ks) < W * 0.5: bad = True; break
            res = spread(legs, Ks, Kl, typ)
            if res is None: bad = True; break
            pnls.append(res[0]); gcred += res[1]; ncred += res[2]; nlegs += 2
        if bad or not pnls: continue
        cost = gcred * SLIP_PCT / 100 + BROKER * nlegs * 2 / lot
        net = sum(pnls) - cost
        margin_pts = W - ncred
        if margin_pts <= 0: continue
        rows.append((r["e"], net / margin_pts * 100, net * lot))
    return rows

def report(lbl, rows):
    if not rows:
        print(f"{lbl:26s} | no trades"); return
    pm = np.array([x[1] for x in rows]); rup = np.array([x[2] for x in rows])
    losses = rup[rup <= 0]
    yr = {}
    for e, v, _ in rows: yr.setdefault(e[:4], []).append(v)
    ys = " ".join(f"{y[2:]}:{np.mean([x>0 for x in v])*100:.0f}/{np.mean(v):+.1f}"
                  for y, v in sorted(yr.items()))
    print(f"{lbl:26s} | n={len(rows):3d} win={(pm>0).mean()*100:5.1f}% avg={pm.mean():+5.2f}%m "
          f"total=Rs{rup.sum():+9,.0f} avgLoss=Rs{losses.mean() if len(losses) else 0:+8,.0f} "
          f"worst=Rs{rup.min():+8,.0f} | {ys}")

def main():
    days = load_days()
    print(f"{len(days)} expiry days loaded ({days[0]['e']} -> {days[-1]['e']})\n")
    print("Per-year format YY:win/avg%m. 1 lot, net of slippage+brokerage. IS 2019-Sep'24 ONLY.\n")
    report("CE d=0.50 (deployed base)", run(days, 0.005, None))
    for d in (0.005, 0.0075, 0.01, 0.015):
        report(f"PE-only d={d*100:.2f}", run(days, None, d))
    for d in (0.005, 0.0075, 0.01, 0.015):
        report(f"IC CE0.50 + PE{d*100:.2f}", run(days, 0.005, d))
    print("\nDONE-IC-TEST")

if __name__ == "__main__":
    main()
