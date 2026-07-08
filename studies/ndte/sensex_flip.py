"""SENSEX FLIP test: expiry-day, if 5-day return >= +1% sell PE spread else CE spread.
Wing ~0.83% of spot both sides. 89 SENSEX weekly expiries Oct'24->Jun'26, real premiums.
Fetches PE-side legs (CE cached from earlier). Compares FLIP vs CE-always vs PE-always.
Frozen threshold from the NIFTY study (ret5>=1.0). Costs 2.5%+brokerage."""
import warnings; warnings.filterwarnings("ignore")
import os, json, sys, time
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np
from engine.data_fetcher import SESSION, UPSTOX_BASE
from engine.instruments import encode_key

C = "/tmp/ndte_sensex"
spots = json.load(open(f"{C}/spot.json"))
sdays = sorted(spots)
exps = sorted(f[6:-5] for f in os.listdir(C) if f.startswith("chain_"))
SLIP, BROKER = 2.5, 20.0

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

def ret5(ds):
    i = sdays.index(ds)
    if i < 6: return 0
    return (spots[sdays[i-1]][3] / spots[sdays[i-6]][3] - 1) * 100

rows = []; done = 0
for e in exps:
    if e not in spots: continue
    ch = json.load(open(f"{C}/chain_{e}.json"))
    s = spots[e][0]; sc = spots[e][3]; lot = int((ch[0].get("lot_size") if ch else 20) or 20)
    out = {}
    for typ, sgn in (("CE", 1), ("PE", -1)):
        side = [c for c in ch if c["instrument_type"] == typ]
        st = sorted(float(c["strike_price"]) for c in side)
        bk = {float(c["strike_price"]): c["instrument_key"] for c in side}
        if len(st) < 8: continue
        near = lambda x: min(st, key=lambda k: abs(k - x))
        Ks = near(s * (1 + sgn * 0.005)); Kl = near(Ks + sgn * s * 0.0083)
        W = abs(Kl - Ks)
        if W < s * 0.0083 * 0.5: continue
        so = leg(bk[Ks], e); lo = leg(bk[Kl], e)
        if so is None or lo is None or so <= 0: continue
        credit = so - lo
        if credit <= 0: continue
        cost = min(max((max(0.0, sc - Ks) - max(0.0, sc - Kl)) if typ == "CE" else (max(0.0, Ks - sc) - max(0.0, Kl - sc)), 0.0), W)
        net = credit - cost - ((so + lo) * SLIP / 100 + BROKER * 4 / lot)
        out[typ] = (net / (W - credit) * 100, net * lot)
    if len(out) == 2:
        rows.append((e, ret5(e), out))
    done += 1
    if done % 20 == 0: print(f"  ...{done}", flush=True)

print(f"\n=== SENSEX expiries with BOTH sides: {len(rows)} ===")
def ev(rule, lab):
    picks = [(d, o[rule(r)][0], o[rule(r)][1]) for d, r, o in rows if rule(r) in o]
    pm = np.array([p[1] for p in picks]); rp = np.array([p[2] for p in picks])
    print(f"{lab:34s} n={len(picks):3d} win {(pm>0).mean()*100:5.1f}%  avg {pm.mean():+6.2f}%m  Rs{rp.sum():+10,.0f}")
    return picks
ev(lambda r: "CE", "CE-always (current SENSEX rule)")
ev(lambda r: "PE", "PE-always")
picks = ev(lambda r: "PE" if r >= 1.0 else "CE", "FLIP (ret5>=1.0 -> PE)")
for y in ("2024", "2025", "2026"):
    s2 = [p for p in picks if p[0].startswith(y)]
    if not s2: continue
    p2 = np.array([p[1] for p in s2]); r2 = np.array([p[2] for p in s2])
    print(f"    {y}: n={len(s2):2d} win {(p2>0).mean()*100:5.1f}% avg {p2.mean():+6.2f}%m Rs{r2.sum():+8,.0f}")
print("DONE-SXFLIP")
