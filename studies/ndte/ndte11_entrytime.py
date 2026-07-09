"""ENTRY-TIME sweep for the 0DTE CE spread (d=0.5% W=200), Oct'24->Jun'26, real 1-min premiums.
Question: does entering later than 09:16 (9:45-10:00 "or any time") lift win rate while keeping
net %margin intact? Two variants per time T:
  A RESTRIKE  - short = strike nearest spot(T)*1.005, wing +200 (strategy restated at T)
  B SAMESTRIKE- strikes fixed from the day OPEN (deployed geometry), entered at T (pure timing)
Entry = first option 1-min bar >= T (must be within 10 min), short at bar open, wing at last
close <= entry ts. Settle at intrinsic vs NIFTY daily close. Costs identical to ndte7:
2.5% of (s0+l0) + Rs20 x 4 legs / lot. Spot at T from Upstox v3 5-min index candles (cached).
Reported: ALL days and rv5<0.9 calm filter (deployed), plus deployed thin-credit gate row.
NOTE: 1-min premiums only exist Oct'24->; 2019-24 bhavcopy has open prints only, so this
sweep is single-regime evidence - any change still needs a forward paper-test.
"""
import sys, os, json, time
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import warnings; warnings.filterwarnings("ignore")
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from ndte2_bt import get_contracts, get_expiries
from ndte7_stops import spots                             # daily spot OHLC
from engine.data_fetcher import SESSION, UPSTOX_BASE
from engine.instruments import encode_key

SLIP_PCT = 2.5; BROKER = 20.0
CACHE = "/tmp/ndte_intra"; os.makedirs(CACHE, exist_ok=True)
SPOT_CACHE = "/tmp/ndte_spot5m"; os.makedirs(SPOT_CACHE, exist_ok=True)

def intra(key, day, tries=2):
    """Like ndte7's but caches EMPTY results too (far wings that never traded) and
    retries briefly — those repeated 3x25s+4s retry cycles were the slow path."""
    kk = key.replace("|", "_")
    cf = f"{CACHE}/{day}_{kk}.json"
    if os.path.exists(cf):
        v = json.load(open(cf))
        return v or None
    for _ in range(tries):
        try:
            r = SESSION.get(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/1minute/{day}/{day}", timeout=15)
            if r.status_code == 200 and r.json().get("status") == "success":
                cs = sorted(r.json()["data"].get("candles", []), key=lambda c: c[0])
                json.dump(cs, open(cf, "w"))              # cache even when empty
                return cs or None
        except Exception:
            pass
        time.sleep(1)
    return None
TIMES = ["09:16", "09:30", "09:45", "10:00", "10:30", "11:00", "11:30", "12:00", "13:00", "14:00"]

def spot5m(day, tries=3):
    cf = f"{SPOT_CACHE}/{day}.json"
    if os.path.exists(cf):
        v = json.load(open(cf)); return v or None
    k = encode_key("NSE_INDEX|Nifty 50")
    for _ in range(tries):
        try:
            r = SESSION.get(f"{UPSTOX_BASE}/v3/historical-candle/{k}/minutes/5/{day}/{day}", timeout=20)
            if r.status_code == 200 and r.json().get("status") == "success":
                cs = sorted(r.json()["data"].get("candles", []), key=lambda c: c[0])
                if cs:
                    json.dump(cs, open(cf, "w")); return cs
        except Exception:
            pass
        time.sleep(3)
    return None

def spot_at(bars, t):
    """open of the 5-min bar starting at t (bars are bar-start stamped)."""
    for c in bars:
        if c[0][11:16] == t: return c[1]
    return None

def entry_bar(bars, t):
    tmin = int(t[:2]) * 60 + int(t[3:])
    for c in bars:
        m = int(c[0][11:13]) * 60 + int(c[0][14:16])
        if m >= tmin:
            return c if m <= tmin + 10 else None
    return None

def wing_at(bars_l, ts):
    last = None
    for c in bars_l:
        if c[0] <= ts: last = c
        else: break
    return last[4] if last else None

def build_day(e):
    sp = spots.get(e)
    if not sp: return None
    sbars = spot5m(e)
    if not sbars: return None
    chain = get_contracts("NIFTY", e)
    ce = sorted([c for c in chain if c["instrument_type"] == "CE"], key=lambda c: float(c["strike_price"]))
    if len(ce) < 10: return None
    strikes = [float(c["strike_price"]) for c in ce]
    bykey = {float(c["strike_price"]): c["instrument_key"] for c in ce}
    lot = int(ce[0].get("lot_size") or 75)
    near = lambda x: min(strikes, key=lambda s: abs(s - x))
    # strike pairs needed: per time (RESTRIKE) + the open-based pair (SAMESTRIKE)
    pairs = {}
    for t in TIMES:
        s_t = sp[0] if t == "09:16" else spot_at(sbars, t)
        if s_t is None: continue
        Ks = near(s_t * 1.005); Kl = near(Ks + 200)
        if abs(Kl - Ks) < 100: continue
        pairs[t] = (Ks, Kl)
    if "09:16" not in pairs: return None
    need = sorted({k for p in pairs.values() for k in p})
    bars = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for K, b in zip(need, ex.map(lambda K: intra(bykey[K], e), need)):
            if b: bars[K] = b
    return dict(e=e, lot=lot, spot_close=sp[3], pairs=pairs, bars=bars)

def sim(day, t, Ks, Kl):
    bs, bl = day["bars"].get(Ks), day["bars"].get(Kl)
    if not bs or not bl: return None
    eb = entry_bar(bs, t)
    if not eb: return None
    s0 = eb[1]
    l0 = wing_at(bl, eb[0])
    if l0 is None:
        fb = entry_bar(bl, t)
        l0 = fb[1] if fb else None
    if l0 is None: return None
    credit = s0 - l0
    if s0 <= 0 or credit <= 0: return None
    cost = (s0 + l0) * SLIP_PCT / 100 + BROKER * 4 / day["lot"]
    si = max(0.0, day["spot_close"] - Ks); li = max(0.0, day["spot_close"] - Kl)
    net = (s0 - si) + (li - l0) - cost
    margin = abs(Kl - Ks) - credit
    return net / margin * 100, net * 75, credit

def main():
    exps = get_expiries("NIFTY")
    days = []
    for e in exps:
        try:
            d = build_day(e)
        except Exception as ex:
            print(f"  !! {e}: {ex}", flush=True); d = None
        if d: days.append(d)
        if len(days) and len(days) % 10 == 0: print(f"  ...{len(days)} days built ({e})", flush=True)
    print(f"{len(days)} expiry days ready", flush=True)
    sdays = sorted(spots)
    def rv5(ds):
        i = sdays.index(ds)
        closes = np.array([spots[sdays[j]][3] for j in range(i - 6, i)])
        return np.std(np.diff(np.log(closes))) * 100
    out = {}
    print(f"\n{'mode':10s} {'T':5s} {'filt':8s} | {'n':>3s} {'win%':>5s} {'avg%m':>6s} {'tot₹':>8s} {'worst₹':>8s} {'medCr':>5s}")
    for mode in ("RESTRIKE", "SAMESTRIKE"):
        for t in TIMES:
            for filt in ("all", "rv5", "rv5+cr"):
                res = []
                for d in days:
                    if filt != "all" and rv5(d["e"]) >= 0.9: continue
                    Ks, Kl = d["pairs"].get(t if mode == "RESTRIKE" else "09:16", (None, None))
                    if Ks is None: continue
                    r = sim(d, t, Ks, Kl)
                    if r is None: continue
                    if filt == "rv5+cr" and r[2] < 0.0002 * spots[d["e"]][0]: continue
                    res.append(r)
                if not res: continue
                pm = np.array([r[0] for r in res]); rp = np.array([r[1] for r in res]); cr = np.array([r[2] for r in res])
                out[f"{mode}|{t}|{filt}"] = dict(n=len(res), win=round((pm > 0).mean() * 100, 1),
                                                 avg=round(pm.mean(), 2), tot=round(rp.sum()),
                                                 worst=round(rp.min()), medcr=round(float(np.median(cr)), 1))
                print(f"{mode:10s} {t:5s} {filt:8s} | {len(res):3d} {(pm>0).mean()*100:5.1f} {pm.mean():+6.2f} {rp.sum():+8.0f} {rp.min():+8.0f} {np.median(cr):5.1f}", flush=True)
    json.dump(out, open("/tmp/ndte11_results.json", "w"), indent=1)
    print("DONE-NDTE11")

if __name__ == "__main__":
    main()
