"""PATH_TO_1L iteration 2 (a) OOS: NIFTY FLIP-CONDOR hybrid, Oct'24 -> Jul'26,
real Upstox expired premiums (same era/machinery as the FLIP OOS test).
Cells FROZEN from IS before this run: add-side d=0.75 cw>=0.07 and d=1.00
cw>=0.08 (neighbors printed for robustness only). FLIP side d=0.5%, W=200 pts
both sides, entry OPEN, intrinsic settle vs spot close, costs 2.5% of gross
credit + Rs20 x legs x 2 per lot, shared margin = W - total credit. ret5 =
prev close vs close 5 sessions earlier, >= +1.0% -> PE else CE (deployed).
Cache /tmp/ndte_nifty_oos (resumable)."""
import warnings; warnings.filterwarnings("ignore")
import os, json, sys, time
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np
from engine.data_fetcher import SESSION, UPSTOX_BASE
from engine.instruments import encode_key

C = "/tmp/ndte_nifty_oos"; os.makedirs(C, exist_ok=True)
KEY = "NSE_INDEX|Nifty 50"
SLIP, BROKER, W = 2.5, 20.0, 200.0

def gj(url, params=None, tries=5):
    for i in range(tries):
        try:
            r = SESSION.get(url, params=params, timeout=25)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(4)
    return {}

def spot_daily():
    cf = f"{C}/spot.json"
    if os.path.exists(cf): return json.load(open(cf))
    out = {}
    j = gj(f"{UPSTOX_BASE}/v2/historical-candle/{encode_key(KEY)}/day/2026-07-30/2024-08-01")
    for ts, o, h, l, c, *_ in j.get("data", {}).get("candles", []):
        out[ts[:10]] = [o, h, l, c]
    json.dump(out, open(cf, "w"))
    return out

def contracts(e):
    cf = f"{C}/chain_{e}.json"
    if os.path.exists(cf): return json.load(open(cf))
    j = gj(f"{UPSTOX_BASE}/v2/expired-instruments/option/contract",
           {"instrument_key": KEY, "expiry_date": e})
    out = j.get("data", []) or []
    if out: json.dump(out, open(cf, "w"))
    return out

def leg(key, day):
    kk = key.replace("|", "_")
    cf = f"{C}/{day}_{kk}.json"
    if os.path.exists(cf):
        v = json.load(open(cf)); return v[0] if v else None
    j = gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{day}/{day}", tries=4)
    cs = j.get("data", {}).get("candles", []) if j.get("status") == "success" else []
    v = None
    if cs:
        ts, o, h, l, c, vol, oi = cs[0]
        v = [o, h, l, c, vol, oi]
    json.dump(v, open(cf, "w"))
    return v[0] if v else None

def vertical(e, ch, s, sc, typ, sgn, d):
    side = [c for c in ch if c["instrument_type"] == typ]
    st = sorted(float(c["strike_price"]) for c in side)
    bk = {float(c["strike_price"]): c["instrument_key"] for c in side}
    if len(st) < 8: return None
    near = lambda x: min(st, key=lambda k: abs(k - x))
    Ks = near(s * (1 + sgn * d)); Kl = near(Ks + sgn * W)
    Wr = abs(Kl - Ks)
    if Wr < W * 0.5: return None
    so = leg(bk[Ks], e); lo = leg(bk[Kl], e)
    if so is None or lo is None or so <= 0: return None
    credit = so - lo
    if credit <= 0: return None
    pay = (max(0.0, sc - Ks) - max(0.0, sc - Kl)) if typ == "CE" else (max(0.0, Ks - sc) - max(0.0, Kl - sc))
    return credit - min(max(pay, 0.0), Wr), so + lo, credit, Wr

def build():
    spots = spot_daily(); sdays = sorted(spots)
    j = gj(f"{UPSTOX_BASE}/v2/expired-instruments/expiries", {"instrument_key": KEY})
    exps = sorted(e for e in (j.get("data", []) or []) if e >= "2024-10-01")
    print(f"{len(exps)} NIFTY expiries Oct'24->, {len(spots)} spot days")
    rows = []
    for e in exps:
        if e not in spots: continue
        i = sdays.index(e)
        if i < 6: continue
        r5 = (spots[sdays[i-1]][3] / spots[sdays[i-6]][3] - 1) * 100
        ch = contracts(e)
        if not ch: continue
        s, sc = spots[e][0], spots[e][3]
        lot = int((ch[0].get("lot_size") if ch else 75) or 75)
        ft, fsgn = ("PE", -1) if r5 >= 1.0 else ("CE", 1)
        prim = vertical(e, ch, s, sc, ft, fsgn, 0.005)
        if prim is None: continue
        ot, osgn = ("CE", 1) if ft == "PE" else ("PE", -1)
        adds = {d: vertical(e, ch, s, sc, ot, osgn, d) for d in (0.0075, 0.01)}
        rows.append((e, lot, prim, adds))
        if len(rows) % 20 == 0: print(f"  ...{len(rows)}", flush=True)
    return rows

def run(rows, add_d, floor):
    out = []
    for e, lot, prim, adds in rows:
        pnl, gross, cred, nlegs = prim[0], prim[1], prim[2], 2
        ad = adds.get(add_d) if add_d else None
        if ad is not None and ad[2] / ad[3] >= (floor or 0):
            pnl += ad[0]; gross += ad[1]; cred += ad[2]; nlegs = 4
        net = pnl - (gross * SLIP / 100 + BROKER * nlegs * 2 / lot)
        margin = W - cred
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
    print(f"\n{len(rows)} OOS expiries with a valid FLIP side\n")
    report("FLIP (deployed baseline)", run(rows, None, None))
    print("-- FROZEN cells (the decision) --")
    report("HYB d=0.75 cw>=0.07 [frozen]", run(rows, 0.0075, 0.07))
    report("HYB d=1.00 cw>=0.08 [frozen]", run(rows, 0.01, 0.08))
    print("-- neighbors (robustness only) --")
    for d in (0.0075, 0.01):
        for fl in (0.05, 0.06, 0.08, 0.10):
            report(f"HYB d={d*100:.2f} cw>={fl:.2f}", run(rows, d, fl))
    print("DONE-FLIPCONDOR-OOS")

if __name__ == "__main__":
    main()
