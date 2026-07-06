"""OOS validation (Upstox expired instruments, Oct'24->Jun'26) of the 2019-24 bhavcopy winner:
CE credit spread, short d% OTM of spot open, wing +W pts, NO stop, exit at close (settlement).
Same cost model as ndte3. Per-year + distribution. Retry-hardened fetches (401 bursts).
"""
import sys, os, json
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import warnings; warnings.filterwarnings("ignore")
import numpy as np
from ndte2_bt import get_contracts, leg_ohlc, get_expiries   # retry-wrapped
from ndte_bt import spot_daily

SLIP_PCT = 2.5; BROKER = 20.0
CONFIGS = [(0.005, 100), (0.005, 150), (0.005, 200), (0.005, 300),
           (0.0075, 100), (0.0075, 150), (0.0075, 200), (0.0075, 300)]

def main():
    spots = spot_daily()
    exps = get_expiries("NIFTY")
    res = {c: [] for c in CONFIGS}
    done = 0
    for e in exps:
        sp = spots.get(e)
        if not sp: continue
        chain = get_contracts("NIFTY", e)
        if not chain: print(f"  !! no chain {e}", flush=True); continue
        bykey = {}
        lot = 75
        for ct in chain:
            bykey[(float(ct["strike_price"]), ct["instrument_type"])] = ct["instrument_key"]
            if ct.get("lot_size"): lot = int(ct["lot_size"])
        strikes = sorted(set(k[0] for k in bykey))
        near = lambda x: min(strikes, key=lambda s: abs(s - x))
        s = sp[0]
        memo = {}
        def leg(K):
            if K not in memo:
                key = bykey.get((K, "CE"))
                memo[K] = leg_ohlc(key, e) if key else None
            return memo[K]
        for d, W in CONFIGS:
            Ks = near(s * (1 + d)); Kl = near(Ks + W)
            if abs(Kl - Ks) < W * 0.5: continue
            vs, vl = leg(Ks), leg(Kl)
            if not vs or not vl or vs[0] <= 0 or vl[0] < 0: continue
            credit = vs[0] - vl[0]
            if credit <= 0: continue
            pnl = (vs[0] - vs[3]) + (vl[3] - vl[0])
            cost = (vs[0] + vl[0]) * SLIP_PCT / 100 + BROKER * 4 / lot
            net = pnl - cost
            margin_pts = W - credit
            if margin_pts <= 0: continue
            res[(d, W)].append((e, net / margin_pts * 100, net * lot))
        done += 1
        if done % 20 == 0: print(f"  ...{done} expiries", flush=True)
    print(f"\n=== OOS Oct'24->Jun'26, CE no-stop (cost 2.5% credit + brokerage) ===")
    print(f"{'config':22s} | {'n':>3s} {'win%':>5s} {'avg%m':>6s} {'med%m':>6s} {'worst%m':>7s} | per-year win/avg%m | avg₹(lot75)")
    for c in CONFIGS:
        rows = res[c]
        if not rows: print(f"d={c[0]*100:.2f} W={c[1]:3d} : n=0"); continue
        pm = np.array([r[1] for r in rows]); rp = np.array([r[2] for r in rows])
        yr = {}
        for e, v, _ in rows: yr.setdefault(e[:4], []).append(v)
        ys = " ".join(f"{y[2:]}:{np.mean([x>0 for x in v])*100:.0f}/{np.mean(v):+.1f}" for y, v in sorted(yr.items()))
        print(f"CE d={c[0]*100:.2f} W={c[1]:3d}      | {len(rows):3d} {(pm>0).mean()*100:5.1f} {pm.mean():+6.2f} "
              f"{np.median(pm):+6.2f} {pm.min():+7.1f} | {ys} | ₹{rp.mean():+.0f}")
    json.dump({f"{d}_{W}": v for (d, W), v in res.items()},
              open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ndte4_oos.json"), "w"))
    print("DONE-NDTE4")

if __name__ == "__main__":
    main()
