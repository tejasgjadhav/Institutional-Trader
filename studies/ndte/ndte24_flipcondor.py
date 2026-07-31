"""PATH_TO_1L iteration 2 (a): FLIP-CONDOR HYBRID on NIFTY 0DTE.

Deployed FLIP rule (frozen 2026-07-07): expiry morning, NIFTY 5-day return
(prev close vs close 5 sessions earlier) >= +1.0% -> sell PE spread (short
0.5% OTM below, wing 200 beyond), else CE spread. Hybrid: keep the FLIP side
as deployed AND add the OPPOSITE side (same 0.5% or wider 0.75% short) only
when the added side's own credit/width >= floor. Margin is shared: both wings
W=200, so condor margin = W - total credit (one side's max loss covers both).

Machinery = ndte23_ic.py (NSE expiry bhavcopy /tmp/ndte_bhav, 282 expiries
2019-02 -> Sep'24, entry OPEN, settle CLOSE, no stop, CONTRACTS>=100 short /
>=1 wing, costs 2.5% of gross credit + Rs20 x legs x 2 per lot).
GATE: the FLIP baseline must reproduce ~85.8% / +Rs137,523 before variants
are trusted; both settlement conventions (option-close vs intrinsic) printed.
"""
import os, json
import numpy as np
import pandas as pd

BHAV = "/tmp/ndte_bhav"
SPOT_CACHE = "/tmp/ndte_cache/spot2019.json"
SLIP_PCT, BROKER, W = 2.5, 20.0, 200.0

def lot_for(ds):
    if ds < "2021-04-01": return 75
    if ds < "2024-11-20": return 50
    return 75

def load_days():
    spots = json.load(open(SPOT_CACHE))
    sdays = sorted(spots)
    days = []
    for f in sorted(os.listdir(BHAV)):
        if not f.endswith(".csv"): continue
        ds = f[:-4]
        if ds not in spots: continue
        i = sdays.index(ds)
        if i < 6: continue
        r5 = (spots[sdays[i-1]][3] / spots[sdays[i-6]][3] - 1) * 100
        df = pd.read_csv(os.path.join(BHAV, f))
        legs = {}
        for _, r in df.iterrows():
            legs[(float(r["STRIKE_PR"]), r["OPTION_TYP"])] = (
                float(r["OPEN"]), float(r["HIGH"]), float(r["LOW"]), float(r["CLOSE"]),
                float(r.get("CONTRACTS", 0)))
        strikes = sorted(set(k[0] for k in legs))
        if len(strikes) < 10: continue
        days.append({"e": ds, "lot": lot_for(ds), "spot": spots[ds][0],
                     "close": spots[ds][3], "ret5": r5,
                     "legs": legs, "strikes": strikes})
    return days

def spread(day, typ, sgn, d, settle):
    """One vertical: short d-OTM, wing W beyond. settle='close'|'intr'.
    Returns (pnl_pts, gross_open_prem, net_credit) or None."""
    legs, strikes, s = day["legs"], day["strikes"], day["spot"]
    near = lambda x: min(strikes, key=lambda st: abs(st - x))
    Ks = near(s * (1 + sgn * d)); Kl = near(Ks + sgn * W)
    if abs(Kl - Ks) < W * 0.5: return None
    vs, vl = legs.get((Ks, typ)), legs.get((Kl, typ))
    if not vs or not vl or vs[0] <= 0 or vl[0] < 0: return None
    if vs[4] < 100 or vl[4] < 1: return None
    credit = vs[0] - vl[0]
    if credit <= 0: return None
    if settle == "close":
        pnl = (vs[0] - vs[3]) + (vl[3] - vl[0])
    else:
        sc, Wr = day["close"], abs(Kl - Ks)
        if typ == "CE":
            pay = max(0.0, sc - Ks) - max(0.0, sc - Kl)
        else:
            pay = max(0.0, Ks - sc) - max(0.0, Kl - sc)
        pnl = credit - min(max(pay, 0.0), Wr)
    return pnl, vs[0] + vl[0], credit

def run(days, picker, settle="close"):
    """picker(day) -> list of (typ, sgn, d) legs to sell. Returns trade rows."""
    rows = []
    for day in days:
        want = picker(day)
        if not want: continue
        pnl, gcred, ncred, nlegs, bad, got_primary = 0.0, 0.0, 0.0, 0, False, False
        for j, (typ, sgn, d, optional) in enumerate(want):
            res = spread(day, typ, sgn, d, settle)
            if res is None:
                if optional: continue
                bad = True; break
            pnl += res[0]; gcred += res[1]; ncred += res[2]; nlegs += 2
            if not optional: got_primary = True
        if bad or not got_primary: continue
        cost = gcred * SLIP_PCT / 100 + BROKER * nlegs * 2 / day["lot"]
        net = pnl - cost
        margin_pts = W - ncred
        if margin_pts <= 0: continue
        rows.append((day["e"], net / margin_pts * 100, net * day["lot"], nlegs))
    return rows

def report(lbl, rows):
    if not rows:
        print(f"{lbl:34s} | no trades"); return
    pm = np.array([x[1] for x in rows]); rup = np.array([x[2] for x in rows])
    both = sum(1 for x in rows if x[3] == 4)
    yr = {}
    for e, v, rp, _ in rows: yr.setdefault(e[:4], []).append((v, rp))
    ys = " ".join(f"{y[2:]}:{np.mean([x[0]>0 for x in v])*100:.0f}%/Rs{sum(x[1] for x in v)/1000:+.0f}k"
                  for y, v in sorted(yr.items()))
    print(f"{lbl:34s} | n={len(rows):3d} (2-side:{both:3d}) win={(pm>0).mean()*100:5.1f}% "
          f"avg={pm.mean():+5.2f}%m total=Rs{rup.sum():+9,.0f} worst=Rs{rup.min():+8,.0f} | {ys}")

def flip_leg(day):
    return ("PE", -1, 0.005) if day["ret5"] >= 1.0 else ("CE", 1, 0.005)

def main():
    days = load_days()
    print(f"{len(days)} expiry days loaded ({days[0]['e']} -> {days[-1]['e']})")
    print("IS 2019-Sep'24. 1 lot, net of slippage+brokerage. per-year = win%/total Rs.\n")

    print("=== GATE: baseline reproduction, both settlement conventions ===")
    for settle in ("close", "intr"):
        report(f"CE-always d=0.50 [{settle}]",
               run(days, lambda d: [("CE", 1, 0.005, False)], settle))
        report(f"FLIP (deployed) [{settle}]",
               run(days, lambda d: [flip_leg(d) + (False,)], settle))
        print()

    for settle in ("close", "intr"):
        print(f"=== HYBRID sweeps [{settle}] ===")
        for add_d in (0.005, 0.0075):
            for floor in (None, 0.03, 0.04, 0.05, 0.06):
                def picker(day, add_d=add_d, floor=floor):
                    t, sg, d = flip_leg(day)
                    legs = [(t, sg, d, False)]
                    ot, osg = ("PE", -1) if t == "CE" else ("CE", 1)
                    res = spread(day, ot, osg, add_d, "close")
                    if res is not None and (floor is None or res[2] / W >= floor):
                        legs.append((ot, osg, add_d, True))
                    return legs
                fl = "none" if floor is None else f"{floor:.2f}"
                report(f"HYB add d={add_d*100:.2f} cw>={fl}", run(days, picker, settle))
        print()
    print("DONE-FLIPCONDOR")

if __name__ == "__main__":
    main()
