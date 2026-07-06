"""0DTE NIFTY grid on NSE bhavcopy expiry days 2019-02 -> 2024-09 (real premiums, full OHLC).
Same rules as ndte2: entry=OPEN, per-leg stop vs HIGH (conservative), exit=CLOSE(=settlement),
costs 2.5% of gross credit + Rs.20x legs x2 /lot; margin = W*lot - net_credit*lot.
Per-year reporting; goal bar = win>=85 every year AND avg net >= 2% of margin AND net>0 every year.
Liquidity: short leg CONTRACTS >= 100, wing >= 1.
"""
import os, json, sys
import numpy as np
import pandas as pd

BHAV = "/tmp/ndte_bhav"
SPOT_CACHE = "/tmp/ndte_cache/spot2019.json"
DISTS = [0.0, 0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02]
WINGS = [100, 150, 200, 300]
STOPS = [2.0, 3.0, None]
GAPF = [None, 0.4]
SLIP_PCT = 2.5
BROKER = 20.0

def spot_daily():
    if os.path.exists(SPOT_CACHE):
        return json.load(open(SPOT_CACHE))
    sys.path.insert(0, "/Users/sayali/files/institutional-trader")
    import warnings; warnings.filterwarnings("ignore")
    from engine.data_fetcher import SESSION, UPSTOX_BASE
    from engine.instruments import encode_key
    out = {}
    for to, frm in (("2024-09-30", "2019-01-01"), ("2026-07-06", "2024-10-01")):
        r = SESSION.get(f"{UPSTOX_BASE}/v2/historical-candle/{encode_key('NSE_INDEX|Nifty 50')}/day/{to}/{frm}", timeout=30)
        for ts, o, h, l, c, *_ in r.json().get("data", {}).get("candles", []):
            out[ts[:10]] = [o, h, l, c]
    json.dump(out, open(SPOT_CACHE, "w"))
    return out

def lot_for(ds):
    if ds < "2021-04-01": return 75
    if ds < "2024-11-20": return 50   # (25 briefly Oct-Nov'24 — immaterial for % figures)
    return 75

def main():
    spots = spot_daily(); sdays = sorted(spots)
    days = []
    for f in sorted(os.listdir(BHAV)):
        if not f.endswith(".csv"): continue
        ds = f[:-4]
        sp = spots.get(ds)
        if not sp: continue
        i = sdays.index(ds)
        prevc = spots[sdays[i-1]][3] if i > 0 else None
        gap = abs(sp[0] - prevc) / prevc * 100 if prevc else None
        df = pd.read_csv(os.path.join(BHAV, f))
        legs = {}
        for _, r in df.iterrows():
            legs[(float(r["STRIKE_PR"]), r["OPTION_TYP"])] = (
                float(r["OPEN"]), float(r["HIGH"]), float(r["LOW"]), float(r["CLOSE"]),
                float(r.get("CONTRACTS", 0)))
        strikes = sorted(set(k[0] for k in legs))
        if len(strikes) < 10: continue
        days.append({"e": ds, "lot": lot_for(ds), "gap": gap, "spot": sp[0],
                     "legs": legs, "strikes": strikes})
    print(f"{len(days)} expiry days loaded ({days[0]['e']} -> {days[-1]['e']})")

    def spread(legs, Ks, Kl, typ, m):
        vs, vl = legs.get((Ks, typ)), legs.get((Kl, typ))
        if not vs or not vl or vs[0] <= 0 or vl[0] < 0: return None
        if vs[4] < 100 or vl[4] < 1: return None          # liquidity floor
        credit = vs[0] - vl[0]
        if credit <= 0: return None
        if m is not None and vs[1] >= m * vs[0]:
            pnl = (vs[0] - m * vs[0]) + (vl[3] - vl[0])
        else:
            pnl = (vs[0] - vs[3]) + (vl[3] - vl[0])
        return pnl, vs[0] + vl[0], credit

    def run(side, d, W, m, g):
        rows = []
        for r in days:
            if g is not None and (r["gap"] is None or r["gap"] > g): continue
            s, legs, strikes, lot = r["spot"], r["legs"], r["strikes"], r["lot"]
            near = lambda x: min(strikes, key=lambda st: abs(st - x))
            pnls, gcred, ncred = [], 0.0, 0.0
            bad = False
            for typ, sgn in (("CE", 1), ("PE", -1)):
                if side != "IC" and side != typ: continue
                Ks = near(s * (1 + sgn * d)); Kl = near(Ks + sgn * W)
                if abs(Kl - Ks) < W * 0.5: bad = True; break
                res = spread(legs, Ks, Kl, typ, m)
                if res is None: bad = True; break
                pnls.append(res[0]); gcred += res[1]; ncred += res[2]
            if bad or not pnls: continue
            nlegs = 4 if side == "IC" else 2
            cost = gcred * SLIP_PCT / 100 + BROKER * nlegs * 2 / lot
            net = sum(pnls) - cost
            margin_pts = W - ncred
            if margin_pts <= 0: continue
            rows.append((r["e"], net / margin_pts * 100))
        return rows

    print(f"\n{'config':40s} | {'n':>4s} {'win':>5s} {'avg%m':>6s} | per-year win/net%m (2019-24)")
    passes, nearmiss = [], []
    for side in ("IC", "CE", "PE"):
        for d in DISTS:
            for W in WINGS:
                for m in STOPS:
                    for g in GAPF:
                        rows = run(side, d, W, m, g)
                        if len(rows) < 150: continue
                        pm = np.array([x[1] for x in rows])
                        yr = {}
                        for e, v in rows:
                            yr.setdefault(e[:4], []).append(v)
                        ystats = {y: (np.mean([x > 0 for x in v]) * 100, float(np.mean(v)))
                                  for y, v in yr.items() if len(v) >= 20}
                        if len(ystats) < 6: continue
                        minwin = min(w for w, _ in ystats.values())
                        minnet = min(n_ for _, n_ in ystats.values())
                        rec = (minwin, minnet, pm.mean(), (pm > 0).mean() * 100, len(rows), side, d, W, m, g, ystats)
                        if minwin >= 80 and minnet > 0 and pm.mean() >= 2:
                            passes.append(rec)
                        elif minwin >= 70 and minnet > -2:
                            nearmiss.append(rec)
    def show(rec):
        minwin, minnet, avg, win, n, side, d, W, m, g, ystats = rec
        lbl = f"{side} d={d*100:.2f} W={W} stop={m or 'none'} gap<{g or '-'}"
        ys = " ".join(f"{y[2:]}:{w:.0f}/{v:+.1f}" for y, (w, v) in sorted(ystats.items()))
        print(f"{lbl:40s} | {n:4d} {win:5.1f} {avg:+6.2f} | {ys}")
    print(f"--- PASS (win>=80 every yr, net>0 every yr, avg>=2%m): {len(passes)} ---")
    for rec in sorted(passes, key=lambda r: -r[2]): show(rec)
    print(f"--- near-miss (min-yr win>=70, min-yr net>-2): {len(nearmiss)} (top 15 by avg) ---")
    for rec in sorted(nearmiss, key=lambda r: -r[2])[:15]: show(rec)
    print("DONE-NDTE3")

if __name__ == "__main__":
    main()
