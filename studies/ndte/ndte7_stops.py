"""REAL intraday stop-loss study for the 0DTE CE spread (d=0.5% W=200), Oct'24->Jun'26.
1-minute expired-contract candles (Upstox). Entry = 09:16 bar open (fallback 09:15). Stops on the
SHORT leg premium (m x entry) and on SPREAD cost (m x credit); no-stop baseline settles at
INTRINSIC vs NIFTY daily close (fixes stale-close bias; also re-verifies the 4 suspect rows).
Stop fill = max(level, bar open) * 1.01 slippage; wing sold at its last-known 1-min close then.
Costs: 2.5% of credit + Rs20 x 4 legs / lot. Cache: /tmp/ndte_intra/.
"""
import sys, os, json, time
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import warnings; warnings.filterwarnings("ignore")
import numpy as np
from ndte2_bt import get_contracts, get_expiries          # retry-wrapped
from engine.data_fetcher import SESSION, UPSTOX_BASE
from engine.instruments import encode_key

CACHE = "/tmp/ndte_intra"; os.makedirs(CACHE, exist_ok=True)
SLIP_PCT = 2.5; BROKER = 20.0
STOP_SLIP = 1.01
spots = json.load(open("/tmp/ndte_cache/spot2019.json"))

def intra(key, day, tries=3):
    kk = key.replace("|", "_")
    cf = f"{CACHE}/{day}_{kk}.json"
    if os.path.exists(cf):
        v = json.load(open(cf))
        return v or None
    for i in range(tries):
        try:
            r = SESSION.get(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/1minute/{day}/{day}", timeout=25)
            if r.status_code == 200 and r.json().get("status") == "success":
                cs = r.json()["data"].get("candles", [])
                if cs:
                    cs = sorted(cs, key=lambda c: c[0])
                    json.dump(cs, open(cf, "w"))
                    return cs
        except Exception:
            pass
        time.sleep(4)
    return None

def build_day(e):
    sp = spots.get(e)
    if not sp: return None
    chain = get_contracts("NIFTY", e)
    ce = sorted([c for c in chain if c["instrument_type"] == "CE"], key=lambda c: float(c["strike_price"]))
    if len(ce) < 10: return None
    strikes = [float(c["strike_price"]) for c in ce]
    bykey = {float(c["strike_price"]): c["instrument_key"] for c in ce}
    lot = int(ce[0].get("lot_size") or 75)
    near = lambda x: min(strikes, key=lambda s: abs(s - x))
    Ks = near(sp[0] * 1.005); Kl = near(Ks + 200)
    if abs(Kl - Ks) < 100: return None
    cs_s = intra(bykey[Ks], e); cs_l = intra(bykey[Kl], e)
    if not cs_s or not cs_l: return None
    return dict(e=e, Ks=Ks, Kl=Kl, lot=lot, spot_close=sp[3], bars_s=cs_s, bars_l=cs_l)

def entry_bar(bars):
    for c in bars:
        hh, mm = int(c[0][11:13]), int(c[0][14:16])
        if hh * 60 + mm >= 9 * 60 + 16:
            return c
    return bars[0]

def wing_at(bars_l, ts):
    last = None
    for c in bars_l:
        if c[0] <= ts: last = c
        else: break
    return last[4] if last else None      # close of last bar <= ts

def sim(day, mode, m):
    """mode: NONE | LEG (short prem >= m x short entry) | SPR (spread cost >= m x credit)."""
    eb_s = entry_bar(day["bars_s"])
    s0 = eb_s[1]                          # short entry = bar open
    l0 = wing_at(day["bars_l"], eb_s[0]) or day["bars_l"][0][1]
    credit = s0 - l0
    if s0 <= 0 or credit <= 0: return None
    base_cost = (s0 + l0) * SLIP_PCT / 100 + BROKER * 4 / day["lot"]
    stopped = None
    if mode != "NONE":
        lvl = m * s0 if mode == "LEG" else None
        for c in day["bars_s"]:
            if c[0] <= eb_s[0]: continue
            if mode == "LEG":
                if c[2] >= lvl:           # bar high >= stop level
                    fill_s = max(lvl, c[1]) * STOP_SLIP
                    fill_l = wing_at(day["bars_l"], c[0]) or 0.0
                    stopped = (c[0], fill_s, fill_l)
                    break
            else:                          # SPR: need concurrent wing value
                wl = wing_at(day["bars_l"], c[0])
                if wl is None: continue
                cost = c[4] - wl           # short close - wing
                if cost >= m * credit:
                    stopped = (c[0], c[4] * STOP_SLIP, wl)
                    break
    if stopped:
        _, fs, fl = stopped
        pnl = (s0 - fs) + (fl - l0)
    else:
        si = max(0.0, day["spot_close"] - day["Ks"]); li = max(0.0, day["spot_close"] - day["Kl"])
        pnl = (s0 - si) + (li - l0)
    net = pnl - base_cost
    margin = 200 - credit
    return net / margin * 100, net * 75, credit, bool(stopped)

def main():
    exps = get_expiries("NIFTY")
    days = []
    for e in exps:
        d = build_day(e)
        if d: days.append(d)
        if len(days) % 20 == 0: print(f"  ...{len(days)} days built", flush=True)
    print(f"{len(days)} expiry days with 1-min data")
    # rv5 filter flags
    sdays = sorted(spots)
    def rv5(ds):
        i = sdays.index(ds)
        closes = np.array([spots[sdays[j]][3] for j in range(i - 6, i)])
        return np.std(np.diff(np.log(closes))) * 100
    CONFIGS = [("NO-STOP", "NONE", 0)] + [(f"LEG x{m}", "LEG", m) for m in (1.5, 2.0, 2.5, 3.0, 4.0)] \
              + [(f"SPREAD x{m}", "SPR", m) for m in (2.0, 3.0, 4.0)]
    print(f"\n{'config':12s} {'filt':4s} | {'n':>3s} {'win%':>5s} {'avg%m':>6s} {'tot₹':>8s} {'worst₹':>8s} {'stopped':>7s}")
    for label, mode, m in CONFIGS:
        for filt in (False, True):
            res = []
            for d in days:
                if filt and rv5(d["e"]) >= 0.9: continue
                r = sim(d, mode, m)
                if r: res.append(r)
            if not res: continue
            pm = np.array([r[0] for r in res]); rp = np.array([r[1] for r in res])
            ns = sum(1 for r in res if r[3])
            print(f"{label:12s} {'rv5' if filt else 'all':4s} | {len(res):3d} {(pm>0).mean()*100:5.1f} {pm.mean():+6.2f} {rp.sum():+8.0f} {rp.min():+8.0f} {ns:7d}")
    print("DONE-NDTE7")

if __name__ == "__main__":
    main()
