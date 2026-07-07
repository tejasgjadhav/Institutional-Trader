"""SENSEX daily-ladder full backtest: enter EVERY trading day on the nearest weekly SENSEX
expiry, sell CE 0.5% OTM + wing ~0.83% of spot, hold to expiry settlement. Deployed gates
applied (rv5<0.9 calm + credit>=0.02% spot). Real premiums; fetches all missing legs with
retries. Compares to NIFTY ladder (81.2% gated). Cache /tmp/ndte_sensex."""
import warnings; warnings.filterwarnings("ignore")
import os, json, sys, time
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np
from datetime import date
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
                    json.dump([o, h, l, c, vol, oi], open(cf, "w"))
                    return o
                json.dump(None, open(cf, "w")); return None
        except Exception:
            pass
        time.sleep(4)
    return None

def rv5(ds):
    i = sdays.index(ds)
    if i < 6: return 9
    c = np.array([spots[sdays[k]][3] for k in range(i - 6, i)])
    return np.std(np.diff(np.log(c))) * 100

res = []; done = 0
for ds in sdays:
    if ds < "2024-10-01" or ds > "2026-06-30": continue
    fut = [e for e in exps if e >= ds]
    if not fut: continue
    e = fut[0]; dte = (date.fromisoformat(e) - date.fromisoformat(ds)).days
    if dte > 6 or e not in spots: continue
    if rv5(ds) >= 0.9: continue
    ch = json.load(open(f"{C}/chain_{e}.json"))
    ce = sorted([c for c in ch if c["instrument_type"] == "CE"], key=lambda c: float(c["strike_price"]))
    st = [float(c["strike_price"]) for c in ce]
    bk = {float(c["strike_price"]): c["instrument_key"] for c in ce}
    lot = int(ce[0].get("lot_size") or 20)
    s = spots[ds][0]
    near = lambda x: min(st, key=lambda k: abs(k - x))
    Ks = near(s * 1.005); Kl = near(Ks + s * 0.0083)
    W = Kl - Ks
    if W < s * 0.0083 * 0.5: continue
    so = leg(bk[Ks], ds); lo = leg(bk[Kl], ds)
    if so is None or lo is None or so <= 0: continue
    credit = so - lo
    if credit <= 0 or credit < s * 0.0002: continue
    sc = spots[e][3]
    cost = min(max(max(0.0, sc - Ks) - max(0.0, sc - Kl), 0.0), W)
    net = credit - cost - ((so + lo) * SLIP / 100 + BROKER * 4 / lot)
    res.append((ds, max(dte, 1), net / (W - credit) * 100, net * lot))
    done += 1
    if done % 30 == 0: print(f"  ...{done}", flush=True)

pm = np.array([r[2] for r in res]); rp = np.array([r[3] for r in res]); dh = np.array([r[1] for r in res])
print(f"\n=== SENSEX DAILY LADDER (gated), Oct'24-Jun'26 — {len(res)} entries ===")
print(f"win {(pm>0).mean()*100:.1f}%  avg {pm.mean():+.2f}%m/trade  {np.mean(pm/dh):+.2f}%m/day-held  total Rs{rp.sum():+,.0f}  worst Rs{rp.min():+,.0f}")
for y in ("2024", "2025", "2026"):
    s2 = [r for r in res if r[0].startswith(y)]
    if not s2: continue
    p2 = np.array([r[2] for r in s2]); r2 = np.array([r[3] for r in s2])
    print(f"  {y}: n={len(s2):3d} win {(p2>0).mean()*100:5.1f}% avg {p2.mean():+6.2f}%m Rs{r2.sum():+9,.0f}")
for d in range(7):
    sub = [r for r in res if r[1] == d]
    if not sub: continue
    p2 = np.array([r[2] for r in sub])
    print(f"  DTE={d}: n={len(sub):3d} win {(p2>0).mean()*100:5.1f}%  avg {p2.mean():+6.2f}%m")
print("NIFTY ladder for comparison: 81.2% win, +9.06%m/trade, +Rs2.66L")
print("DONE-SXLADDER")
EOF
