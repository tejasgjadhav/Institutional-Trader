"""SENSEX 0DTE CE credit spread — same structure as the validated NIFTY Tuesday trade.
91 expired weekly expiries Oct'24->Jul'26 (BSE, Thursdays era-dependent). Short CE at
spot_open*(1+0.5%), wing ~0.83% of spot further (NIFTY-200pt equivalent), entry=day OPEN,
settle INTRINSIC vs spot close. Costs 2.5% credit + Rs20x4/lot. rv5 filter from SENSEX closes.
"""
import sys, os, json, time
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import warnings; warnings.filterwarnings("ignore")
import numpy as np
from engine.data_fetcher import SESSION, UPSTOX_BASE
from engine.instruments import encode_key

CACHE = "/tmp/ndte_sensex"; os.makedirs(CACHE, exist_ok=True)
KEY = "BSE_INDEX|SENSEX"
SLIP = 2.5; BROKER = 20.0
WING_PCT = 0.0083

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
    cf = f"{CACHE}/spot.json"
    if os.path.exists(cf): return json.load(open(cf))
    out = {}
    j = gj(f"{UPSTOX_BASE}/v2/historical-candle/{encode_key(KEY)}/day/2026-07-06/2024-09-01")
    for ts, o, h, l, c, *_ in j.get("data", {}).get("candles", []):
        out[ts[:10]] = [o, h, l, c]
    json.dump(out, open(cf, "w"))
    return out

def contracts(e):
    cf = f"{CACHE}/chain_{e}.json"
    if os.path.exists(cf): return json.load(open(cf))
    j = gj(f"{UPSTOX_BASE}/v2/expired-instruments/option/contract",
           {"instrument_key": KEY, "expiry_date": e})
    out = j.get("data", []) or []
    if out: json.dump(out, open(cf, "w"))
    return out

def leg_day(key, day):
    kk = key.replace("|", "_")
    cf = f"{CACHE}/{day}_{kk}.json"
    if os.path.exists(cf):
        v = json.load(open(cf)); return v or None
    j = gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{day}/{day}")
    cs = j.get("data", {}).get("candles", []) if j.get("status") == "success" else []
    v = None
    if cs:
        ts, o, h, l, c, vol, oi = cs[0]
        v = [o, h, l, c, vol, oi]
        json.dump(v, open(cf, "w"))
    return v

def main():
    spots = spot_daily(); sdays = sorted(spots)
    j = gj(f"{UPSTOX_BASE}/v2/expired-instruments/expiries", {"instrument_key": KEY})
    exps = sorted(j.get("data", []) or [])
    print(f"{len(exps)} SENSEX expiries, {len(spots)} spot days")
    rows = []
    for e in exps:
        sp = spots.get(e)
        if not sp: continue
        ch = contracts(e)
        ce = sorted([c for c in ch if c["instrument_type"] == "CE"], key=lambda c: float(c["strike_price"]))
        if len(ce) < 10: continue
        strikes = [float(c["strike_price"]) for c in ce]
        bykey = {float(c["strike_price"]): c["instrument_key"] for c in ce}
        lot = int(ce[0].get("lot_size") or 20)
        s = sp[0]
        near = lambda x: min(strikes, key=lambda k: abs(k - x))
        Ks = near(s * 1.005); Kl = near(Ks + s * WING_PCT)
        W = Kl - Ks
        if W < s * WING_PCT * 0.5: continue
        vs = leg_day(bykey[Ks], e); vl = leg_day(bykey[Kl], e)
        if not vs or not vl or vs[0] <= 0: continue
        credit = vs[0] - vl[0]
        if credit <= 0: continue
        si = max(0.0, sp[3] - Ks); li = max(0.0, sp[3] - Kl)
        pnl = (vs[0] - si) + (li - vl[0])
        cost = (vs[0] + vl[0]) * SLIP / 100 + BROKER * 4 / lot
        net = pnl - cost
        margin = W - credit
        # rv5 from prior 5 SENSEX closes
        i = sdays.index(e)
        rv = np.std(np.diff(np.log(np.array([spots[sdays[k]][3] for k in range(i - 6, i)])))) * 100 if i >= 6 else None
        rows.append((e, net / margin * 100, net * lot, rv, credit, W, lot))
        if len(rows) % 20 == 0: print(f"  ...{len(rows)}", flush=True)
    print(f"\n{len(rows)} tradeable expiries; lot={rows[-1][6]}, typical W={rows[-1][5]:.0f}")
    for label, sel in (("ALL (no filter)", rows), ("rv5<0.9 filter", [r for r in rows if r[3] is not None and r[3] < 0.9])):
        pm = np.array([r[1] for r in sel]); rp = np.array([r[2] for r in sel])
        w = pm > 0
        print(f"--- {label}: n={len(sel)}  win {w.mean()*100:.1f}%  avg {pm.mean():+.2f}%m  "
              f"total Rs{rp.sum():+,.0f}  worst Rs{rp.min():+,.0f}")
        for y in ("2024", "2025", "2026"):
            s_ = [r for r in sel if r[0].startswith(y)]
            if not s_: continue
            pm2 = np.array([r[1] for r in s_]); rp2 = np.array([r[2] for r in s_])
            print(f"    {y}: n={len(s_):2d} win {(pm2>0).mean()*100:5.1f}% avg {pm2.mean():+6.2f}%m Rs{rp2.sum():+9,.0f}")
    json.dump([[r[0], r[1], r[2], r[3]] for r in rows],
              open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ndte8_sensex.json"), "w"))
    print("DONE-NDTE8")

if __name__ == "__main__":
    main()
