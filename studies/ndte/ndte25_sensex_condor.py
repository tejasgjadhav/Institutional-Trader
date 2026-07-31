"""PATH_TO_1L iteration 2 (b): SENSEX 0DTE condor — deployed CE spread (short
0.5% OTM, wing 0.83% of spot) + added PE spread at d in {0.5,0.75,1.0}% gated
by the PE side's own credit/width floor. Real Upstox expired premiums,
Oct'24 -> Jul'26 (~89 expiries — THIN, 22 months, one regime). Entry OPEN,
intrinsic settle vs spot close, costs 2.5% of gross credit + Rs20 x legs x 2
per lot. Shared margin = max(W_ce, W_pe) - total credit. Cache /tmp/ndte_sensex
(built by ndte8_sensex.py + sensex_flip.py; this script fetches missing legs).
Baselines must reproduce: CE-always 88.8%/+7.57%m/+Rs67,248 (89 exp)."""
import warnings; warnings.filterwarnings("ignore")
import os, json, sys, time
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np
from engine.data_fetcher import SESSION, UPSTOX_BASE
from engine.instruments import encode_key

C = "/tmp/ndte_sensex"
SLIP, BROKER, WING_PCT = 2.5, 20.0, 0.0083
spots = json.load(open(f"{C}/spot.json"))
exps = sorted(f[6:-5] for f in os.listdir(C) if f.startswith("chain_"))

def leg(key, day, tries=4):
    kk = key.replace("|", "_")
    cf = f"{C}/{day}_{kk}.json"
    if os.path.exists(cf):
        v = json.load(open(cf)); return v[0] if v else None
    for i in range(tries):
        try:
            r = SESSION.get(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{day}/{day}", timeout=20)
            if r.status_code == 200 and r.json().get("status") == "success":
                cs = r.json()["data"].get("candles", [])
                if cs:
                    ts, o, h, l, c, vol, oi = cs[0]
                    json.dump([o, h, l, c, vol, oi], open(cf, "w")); return o
                json.dump(None, open(cf, "w")); return None
        except Exception:
            pass
        time.sleep(4)
    return None

def vertical(e, ch, s, sc, typ, sgn, d):
    """Returns (net_pts_before_shared_costs=credit-payout, gross_open, credit, W) or None."""
    side = [c for c in ch if c["instrument_type"] == typ]
    st = sorted(float(c["strike_price"]) for c in side)
    bk = {float(c["strike_price"]): c["instrument_key"] for c in side}
    if len(st) < 8: return None
    near = lambda x: min(st, key=lambda k: abs(k - x))
    Ks = near(s * (1 + sgn * d)); Kl = near(Ks + sgn * s * WING_PCT)
    W = abs(Kl - Ks)
    if W < s * WING_PCT * 0.5: return None
    so = leg(bk[Ks], e); lo = leg(bk[Kl], e)
    if so is None or lo is None or so <= 0: return None
    credit = so - lo
    if credit <= 0: return None
    pay = (max(0.0, sc - Ks) - max(0.0, sc - Kl)) if typ == "CE" else (max(0.0, Ks - sc) - max(0.0, Kl - sc))
    return credit - min(max(pay, 0.0), W), so + lo, credit, W

def build():
    rows = []
    for e in exps:
        if e not in spots: continue
        ch = json.load(open(f"{C}/chain_{e}.json"))
        s, sc = spots[e][0], spots[e][3]
        lot = int((ch[0].get("lot_size") if ch else 20) or 20)
        ce = vertical(e, ch, s, sc, "CE", 1, 0.005)
        if ce is None: continue
        pes = {d: vertical(e, ch, s, sc, "PE", -1, d) for d in (0.005, 0.0075, 0.01)}
        rows.append((e, lot, ce, pes))
        if len(rows) % 20 == 0: print(f"  ...{len(rows)}", flush=True)
    return rows

def run(rows, pe_d, floor):
    out = []
    for e, lot, ce, pes in rows:
        pnl, gross, cred, Wmax, nlegs = ce[0], ce[1], ce[2], ce[3], 2
        pe = pes.get(pe_d) if pe_d else None
        if pe is not None and (floor is None or pe[2] / pe[3] >= floor):
            pnl += pe[0]; gross += pe[1]; cred += pe[2]; Wmax = max(Wmax, pe[3]); nlegs = 4
        net = pnl - (gross * SLIP / 100 + BROKER * nlegs * 2 / lot)
        margin = Wmax - cred
        if margin <= 0: continue
        out.append((e, net / margin * 100, net * lot, nlegs))
    return out

def report(lbl, rows):
    pm = np.array([x[1] for x in rows]); rp = np.array([x[2] for x in rows])
    both = sum(1 for x in rows if x[3] == 4)
    yr = {}
    for e, v, r, _ in rows: yr.setdefault(e[:4], []).append((v, r))
    ys = " ".join(f"{y[2:]}:{np.mean([x[0]>0 for x in v])*100:.0f}%/Rs{sum(x[1] for x in v)/1000:+.0f}k"
                  for y, v in sorted(yr.items()))
    print(f"{lbl:30s} | n={len(rows):3d} (2-side:{both:3d}) win={(pm>0).mean()*100:5.1f}% "
          f"avg={pm.mean():+6.2f}%m total=Rs{rp.sum():+8,.0f} worst=Rs{rp.min():+7,.0f} | {ys}")

def main():
    rows = build()
    print(f"\n{len(rows)} SENSEX expiries with a valid CE side\n")
    report("CE-only (deployed baseline)", run(rows, None, None))
    for d in (0.005, 0.0075, 0.01):
        for floor in (None, 0.03, 0.04, 0.05, 0.06, 0.08):
            fl = "none" if floor is None else f"{floor:.2f}"
            report(f"IC +PE d={d*100:.2f} cw>={fl}", run(rows, d, floor))
        print()
    print("DONE-SX-CONDOR")

if __name__ == "__main__":
    main()
