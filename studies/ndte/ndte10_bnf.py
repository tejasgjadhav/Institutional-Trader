"""BANKNIFTY weekly 0DTE CE spread 2019->Sep'24 on NSE bhavcopy (real premiums).
Short CE at spot_open*1.005, wing ~0.83% of spot (nearest 100), entry=OPEN, exit=CLOSE
(bhav close on expiry ~ settlement), costs 2.5% credit + Rs20x4/lot. Rs normalized to lot=30
(today's). Per-year. Liquidity floor: short CONTRACTS >= 100.
"""
import os, json, sys, time
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import warnings; warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

BHAV = "/tmp/ndte_bhav_bnf"
SPOT_CACHE = "/tmp/ndte_cache/bnfspot2019.json"
SLIP = 2.5; BROKER = 20.0; LOT = 30

def spot_daily():
    if os.path.exists(SPOT_CACHE):
        return json.load(open(SPOT_CACHE))
    from engine.data_fetcher import SESSION, UPSTOX_BASE
    from engine.instruments import encode_key
    out = {}
    for to, frm in (("2024-09-30", "2019-01-01"), ("2026-07-06", "2024-10-01")):
        r = SESSION.get(f"{UPSTOX_BASE}/v2/historical-candle/{encode_key('NSE_INDEX|Nifty Bank')}/day/{to}/{frm}", timeout=30)
        for ts, o, h, l, c, *_ in r.json().get("data", {}).get("candles", []):
            out[ts[:10]] = [o, h, l, c]
    json.dump(out, open(SPOT_CACHE, "w"))
    return out

def main():
    spots = spot_daily()
    rows = []
    for fn in sorted(os.listdir(BHAV)):
        if not fn.endswith(".csv"): continue
        ds = fn[:-4]
        sp = spots.get(ds)
        if not sp: continue
        df = pd.read_csv(os.path.join(BHAV, fn))
        ce = df[df.OPTION_TYP == "CE"].set_index("STRIKE_PR")
        st = sorted(ce.index)
        if len(st) < 10: continue
        s = sp[0]
        near = lambda x: min(st, key=lambda k: abs(k - x))
        Ks = near(s * 1.005); Kl = near(Ks + s * 0.0083)
        if Kl - Ks < s * 0.0083 * 0.5: continue
        try: vs, vl = ce.loc[Ks], ce.loc[Kl]
        except Exception: continue
        if vs.OPEN <= 0 or vs.CONTRACTS < 100: continue
        credit = vs.OPEN - vl.OPEN
        if credit <= 0: continue
        W = Kl - Ks
        net = (vs.OPEN - vs.CLOSE) + (vl.CLOSE - vl.OPEN) - ((vs.OPEN + vl.OPEN) * SLIP / 100 + BROKER * 4 / LOT)
        m = W - credit
        rows.append((ds, net / m * 100, net * LOT))
    print(f"BANKNIFTY weekly 0DTE, bhavcopy: {len(rows)} expiries")
    pm = np.array([r[1] for r in rows]); rp = np.array([r[2] for r in rows])
    print(f"ALL: win {(pm>0).mean()*100:.1f}%  avg {pm.mean():+.2f}%m  total Rs{rp.sum():+,.0f} (lot {LOT})  worst Rs{rp.min():+,.0f}")
    for y in map(str, range(2019, 2025)):
        s_ = [r for r in rows if r[0].startswith(y)]
        if not s_: continue
        p2 = np.array([r[1] for r in s_]); r2 = np.array([r[2] for r in s_])
        print(f"  {y}: n={len(s_):3d} win {(p2>0).mean()*100:5.1f}% avg {p2.mean():+6.2f}%m Rs{r2.sum():+10,.0f}")
    json.dump([[r[0], r[1], r[2]] for r in rows],
              open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ndte10_bnf.json"), "w"))
    print("DONE-NDTE10")

if __name__ == "__main__":
    main()
