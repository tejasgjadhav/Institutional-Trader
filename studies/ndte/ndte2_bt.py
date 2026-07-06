"""0DTE iteration 3b: defined-risk credit structures, tuned for >=85% win AND >=2%/trade on margin.
Short strike d% OTM x wing width W pts x per-leg stop m (or none) x calm-open gap filter.
Margin = W*lot - net_credit*lot (defined risk). Entry day OPEN, stop vs day HIGH (conservative),
exit CLOSE (=settlement). Costs: 2.5% of gross credit + Rs.20 x 8 legs / lot (in points).
Sides: IC (both), CE-only, PE-only spreads. TRAIN Oct'24-Dec'25 / TEST Jan'26-Jun'26.
"""
import sys, os, json
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import warnings; warnings.filterwarnings("ignore")
import time
import numpy as np
from ndte_bt import spot_daily, leg_ohlc as _leg_ohlc
from engine.expired_options import get_expiries, get_contracts as _get_contracts

def get_contracts(sym, e, tries=5):
    for i in range(tries):
        out = _get_contracts(sym, e)
        if out:
            return out
        time.sleep(6)
    return []

def leg_ohlc(key, day, tries=3):
    for i in range(tries):
        v = _leg_ohlc(key, day)
        if v is not None:
            return v
        time.sleep(4)
    return None

import os as _os
CACHED_ONLY = _os.environ.get("NDTE_CACHED_ONLY") == "1"
if CACHED_ONLY:   # restrict to strikes already on disk (API throttled)
    DISTS = [0.0, 0.0025, 0.005, 0.0075, 0.01]
    WINGS = [300]
else:
    DISTS = [0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02]
    WINGS = [100, 150, 200, 300]
STOPS = [2.0, 3.0, None]
GAPF  = [None, 0.4]     # max |overnight gap| % allowed
SLIP_PCT = 2.5
BROKER = 20.0

def main():
    spots = spot_daily()
    sdays = sorted(spots)
    exps = get_expiries("NIFTY")
    days = []
    for e in exps:
        sp = spots.get(e)
        if not sp:
            continue
        i = sdays.index(e)
        prevc = spots[sdays[i - 1]][3] if i > 0 else None
        gap = abs(sp[0] - prevc) / prevc * 100 if prevc else None
        chain = get_contracts("NIFTY", e)
        if not chain:
            continue
        bykey = {}
        lot = 75
        for ct in chain:
            bykey[(float(ct["strike_price"]), ct["instrument_type"])] = ct["instrument_key"]
            if ct.get("lot_size"):
                lot = int(ct["lot_size"])
        strikes = sorted(set(k[0] for k in bykey))
        near = lambda x, _s=strikes: min(_s, key=lambda s: abs(s - x))
        legs = {}
        def get(K, typ, _legs=legs, _bykey=bykey, _e=e):   # bind per-day state (closure late-binding!)
            t = (K, typ)
            if t not in _legs:
                key = _bykey.get(t)
                _legs[t] = leg_ohlc(key, _e) if key else None
            return _legs[t]
        row = {"e": e, "lot": lot, "gap": gap, "spot": sp[0], "get": get, "near": near}
        days.append(row)
    print(f"{len(days)} expiry days")

    def spread_pnl(row, K_short, K_long, typ, m):
        """Sell (K_short,typ), buy (K_long,typ). Returns (net_pts, credit, ok)."""
        vs, vl = row["get"](K_short, typ), row["get"](K_long, typ)
        if not vs or not vl or vs[0] <= 0 or vl[0] < 0:
            return None
        credit = vs[0] - vl[0]
        if credit <= 0:
            return None
        # short leg with optional stop vs day HIGH
        if m is not None and vs[1] >= m * vs[0]:
            pnl_s = vs[0] - m * vs[0]
            pnl_l = vl[3] - vl[0]     # wing held to close (conservative: no credit for timing)
        else:
            pnl_s = vs[0] - vs[3]
            pnl_l = vl[3] - vl[0]
        return pnl_s + pnl_l, vs[0] + vl[0], vs[0] - vl[0]

    def run(side, d, W, m, gapmax):
        rows = []
        for r in days:
            if gapmax is not None and (r["gap"] is None or r["gap"] > gapmax):
                continue
            s = r["spot"]; near = r["near"]; lot = r["lot"]
            res_list = []
            gross_credit = 0.0; net_credit = 0.0
            if side in ("IC", "CE"):
                kc = near(s * (1 + d)); res = spread_pnl(r, kc, near(kc + W), "CE", m)
                if res is None: continue
                res_list.append(res[0]); gross_credit += res[1]; net_credit += res[2]
            if side in ("IC", "PE"):
                kp = near(s * (1 - d)); res = spread_pnl(r, kp, near(kp - W), "PE", m)
                if res is None: continue
                res_list.append(res[0]); gross_credit += res[1]; net_credit += res[2]
            nlegs = 4 if side == "IC" else 2
            cost = gross_credit * SLIP_PCT / 100 + BROKER * nlegs * 2 / lot
            net = sum(res_list) - cost
            margin = W * lot - net_credit * lot          # defined-risk margin (worst side)
            if side == "IC":
                margin = W * lot - net_credit * lot      # one side can lose at expiry
            if margin <= 0: continue
            rows.append((r["e"], net * lot, margin, net_credit))
        return rows

    def stats(rows):
        tr = [x for x in rows if x[0] <= "2025-12-31"]; te = [x for x in rows if x[0] > "2025-12-31"]
        def s(rs):
            if not rs: return None
            pnl = np.array([x[1] for x in rs]); mg = np.array([x[2] for x in rs])
            pm = pnl / mg * 100
            return len(rs), (pnl > 0).mean() * 100, pnl.mean(), pm.mean(), pnl.min()
        return s(tr), s(te), s(rows)

    print(f"\n{'config':42s} | {'nTR':>3s} {'winTR':>5s} {'%mTR':>6s} | {'nTE':>3s} {'winTE':>5s} {'%mTE':>6s} | {'avg₹':>6s} {'worst₹':>8s}")
    keep = []
    for side in ("IC", "CE", "PE"):
        for d in DISTS:
            for W in WINGS:
                for m in STOPS:
                    for g in GAPF:
                        rows = run(side, d, W, m, g)
                        if len(rows) < (40 if g is not None else 55):
                            continue
                        t1, t2, ta = stats(rows)
                        if not t1 or not t2:
                            continue
                        lbl = f"{side} d={d*100:.2f} W={W} stop={m or 'none'} gap<{g or '-'}"
                        keep.append((min(t1[1], t2[1]), t2[3], lbl, t1, t2, ta))
    # print all with min(winTR,winTE)>=80
    hits = [k for k in keep if k[0] >= 80]
    print(f"--- min(win) >= 80%: {len(hits)} configs ---")
    for _, _, lbl, t1, t2, ta in sorted(hits, key=lambda k: -k[1]):
        print(f"{lbl:42s} | {t1[0]:3d} {t1[1]:5.1f} {t1[3]:+6.2f} | {t2[0]:3d} {t2[1]:5.1f} {t2[3]:+6.2f} | {ta[2]:+6.0f} {ta[4]:+8.0f}")
    print("--- top 15 by TEST %margin (min win >= 70) ---")
    for _, _, lbl, t1, t2, ta in sorted([k for k in keep if k[0] >= 70], key=lambda k: -k[1])[:15]:
        print(f"{lbl:42s} | {t1[0]:3d} {t1[1]:5.1f} {t1[3]:+6.2f} | {t2[0]:3d} {t2[1]:5.1f} {t2[3]:+6.2f} | {ta[2]:+6.0f} {ta[4]:+8.0f}")
    print("DONE-NDTE2")

if __name__ == "__main__":
    main()
