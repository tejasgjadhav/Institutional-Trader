"""0DTE NIFTY expiry-day premium selling on REAL expired-option daily OHLC (Upstox).
Sell CE+PE at day OPEN at distance d% from spot open; per-leg stop at m x entry premium
(conservative: if day HIGH >= stop level, the leg is charged the full stop loss — assumes the
breach happened before any decay); survivors exit at CLOSE (= expiry settlement).
Variants: short strangle/straddle, and iron condor with wings W pts further out (defined risk).
Costs: 2.5% of total credit (slippage both sides on 4 legs) + Rs.20 x legs x 2 brokerage.
Split: TRAIN Oct'24-Dec'25 / TEST Jan'26-Jun'26.
"""
import sys, os, json, time
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import warnings; warnings.filterwarnings("ignore")
from engine.expired_options import get_expiries, get_contracts, _get_json
from engine.instruments import encode_key
from engine.data_fetcher import UPSTOX_BASE
import numpy as np

CACHE = "/tmp/ndte_cache"
os.makedirs(CACHE, exist_ok=True)
DISTS = [0.0, 0.0025, 0.005, 0.0075, 0.01]
STOPS = [1.25, 1.5, 2.0, 3.0]
WING = 300          # condor wing distance in points beyond short strike
SLIP_PCT = 2.5      # % of credit, total, both sides
BROKER = 20.0

def spot_daily():
    """NIFTY index daily OHLC 2024-09 -> today, via standard historical API."""
    cf = f"{CACHE}/spot.json"
    if os.path.exists(cf):
        return json.load(open(cf))
    j = _get_json(f"{UPSTOX_BASE}/v2/historical-candle/{encode_key('NSE_INDEX|Nifty 50')}/day/2026-07-06/2024-09-01")
    out = {}
    for ts, o, h, l, c, *_ in j.get("data", {}).get("candles", []):
        out[ts[:10]] = [o, h, l, c]
    json.dump(out, open(cf, "w"))
    return out

def leg_ohlc(key, day):
    """Daily O/H/L/C for an expired option on `day` (cache to disk)."""
    kk = key.replace("|", "_").replace(":", "_")
    cf = f"{CACHE}/{day}_{kk}.json"
    if os.path.exists(cf):
        v = json.load(open(cf))
        return v if v else None
    j = _get_json(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{day}/{day}")
    v = None
    cs = j.get("data", {}).get("candles", []) if j.get("status") == "success" else []
    if cs:
        ts, o, h, l, c, vol, oi = cs[0]
        v = [o, h, l, c, vol, oi]
    if v is not None:                 # never cache a failed fetch (401/429 poisoning)
        json.dump(v, open(cf, "w"))
    return v

def main():
    spots = spot_daily()
    exps = get_expiries("NIFTY")
    print(f"{len(exps)} NIFTY expiries, spot days {len(spots)}")
    trades = []   # per expiry: dict d -> legs
    for e in exps:
        sp = spots.get(e)
        if not sp:
            continue
        s_open = sp[0]
        chain = get_contracts("NIFTY", e)
        if not chain:
            continue
        bykey = {}
        lot = 75
        for ct in chain:
            k = (float(ct["strike_price"]), ct["instrument_type"])
            bykey[k] = ct["instrument_key"]
            if ct.get("lot_size"):
                lot = int(ct["lot_size"])
        strikes = sorted(set(k[0] for k in bykey))
        def near(x):
            return min(strikes, key=lambda s: abs(s - x))
        day = {}
        ok = True
        for d in DISTS:
            kce, kpe = near(s_open * (1 + d)), near(s_open * (1 - d))
            wce, wpe = near(kce + WING), near(kpe - WING)
            legs = {}
            for tag, K, typ in (("ce", kce, "CE"), ("pe", kpe, "PE"), ("wce", wce, "CE"), ("wpe", wpe, "PE")):
                key = bykey.get((K, typ))
                v = leg_ohlc(key, e) if key else None
                legs[tag] = (K, v)
            day[d] = legs
        trades.append((e, lot, day))
        if len(trades) % 20 == 0:
            print(f"  ...{len(trades)} expiries fetched", flush=True)
    print(f"usable expiry days: {len(trades)}")

    def run(structure, d, m):
        rows = []
        for e, lot, day in trades:
            legs = day[d]
            (kce, vce), (kpe, vpe) = legs["ce"], legs["pe"]
            if not vce or not vpe or vce[0] <= 0 or vpe[0] <= 0:
                continue
            credit = vce[0] + vpe[0]
            pnl = 0.0
            for v in (vce, vpe):
                o, h, l, c = v[0], v[1], v[2], v[3]
                stop_lvl = m * o
                if h >= stop_lvl:
                    pnl += o - stop_lvl
                else:
                    pnl += o - c
            wingcost = 0.0
            if structure == "IC":
                (kw1, vw1), (kw2, vw2) = legs["wce"], legs["wpe"]
                if not vw1 or not vw2:
                    continue
                pnl += (vw1[3] - vw1[0]) + (vw2[3] - vw2[0])
                wingcost = vw1[0] + vw2[0]
            cost_pts = credit * SLIP_PCT / 100 + BROKER * (8 if structure == "IC" else 4) / lot
            net = pnl - cost_pts
            rows.append((e, net, credit, net * lot, wingcost))
        return rows

    def report(rows, label, margin_rs):
        if not rows:
            print(f"{label}: n=0"); return None
        tr = [r for r in rows if r[0] <= "2025-12-31"]
        te = [r for r in rows if r[0] > "2025-12-31"]
        out = {}
        for nm, rs in (("TRAIN", tr), ("TEST", te), ("ALL", rows)):
            if not rs: continue
            net = np.array([r[1] for r in rs])
            rup = np.array([r[3] for r in rs])
            win = (net > 0).mean() * 100
            out[nm] = (len(rs), win, rup.mean(), rup.mean() / margin_rs * 100, rup.min())
        a = out.get("ALL")
        t1 = out.get("TRAIN"); t2 = out.get("TEST")
        print(f"{label:24s} | TR n={t1[0]:3d} win={t1[1]:5.1f} avg₹{t1[2]:+8.0f} ({t1[3]:+5.2f}%m) | "
              f"TE n={t2[0] if t2 else 0:3d} win={t2[1] if t2 else 0:5.1f} avg₹{t2[2] if t2 else 0:+8.0f} "
              f"({t2[3] if t2 else 0:+5.2f}%m) | worst₹{a[4]:+9.0f}")
        return out

    print("\n=== SHORT STRANGLE / STRADDLE (margin est Rs.1.6L/lot) ===")
    for d in DISTS:
        for m in STOPS:
            report(run("STR", d, m), f"STR d={d*100:.2f}% stop={m}x", 160000)
    print("\n=== IRON CONDOR wings +300pts (margin = width*lot - credit ~ defined) ===")
    for d in DISTS:
        for m in STOPS:
            rows = run("IC", d, m)
            # defined-risk margin: (WING pts) * lot - net credit (approx, per side max)
            report(rows, f"IC  d={d*100:.2f}% stop={m}x", WING * 75)
    print("DONE-NDTE")

if __name__ == "__main__":
    main()
