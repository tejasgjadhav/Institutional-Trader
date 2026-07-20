"""0DTE EVENT-DAY AVOIDANCE study — data collector (user ask 2026-07-19).
Question: for the three deployed 0DTE books (NIFTY weekly, SENSEX weekly, BANKNIFTY monthly),
Oct'24->date: if we had KNOWN IN ADVANCE that a scheduled macro event (RBI MPC decision, Union
Budget, FOMC spillover) fell on that expiry day and SKIPPED the trade, what happens to win% and
net% vs trading every expiry?

This script only COLLECTS per-expiry outcomes (the expensive part). Event tagging + the
avoid-vs-not comparison lives in ndte13_report.py, so the calendar can be revised without
refetching. Results are persisted IN-REPO (studies/ndte/ndte13_trades.json) because /tmp is
periodically purged.

Deployed geometry (engine/zero_dte.py + engine/dte_multi.py BOOKS):
  NIFTY     weekly  short CE at spot_open*1.005, wing +200pts FIXED, lot 75,
                    FLIP: ret5 >= 1.0 -> sell the PE spread instead (ZERO_DTE_FLIP_RET5)
                    filters: rv5 < 0.9, credit >= 0.02% of spot
  SENSEX    weekly  otm 0.5%, wing 0.83% of spot, CE-always, NO extra filters, lot 20
  BANKNIFTY monthly otm 0.5%, wing 0.83% of spot, CE-always, monthly expiry only, lot 30
Entry = expiry-day OPEN, settle INTRINSIC vs that index's daily close.
Costs 2.5% of (short+long entry) + Rs20 x 4 legs / lot — identical to ndte7/ndte8/sensex_flip.
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys, json, time
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from engine.data_fetcher import SESSION, UPSTOX_BASE
from engine.instruments import encode_key

C = "/tmp/ndte_ev"; os.makedirs(C, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
SLIP, BROKER = 2.5, 20.0
START = "2024-10-01"; END = "2026-07-19"

BOOKS = [
    dict(name="NIFTY",     key="NSE_INDEX|Nifty 50",  otm=0.005, wing_pts=200,   lot=75,
         cadence="weekly",  flip=1.0, rv5_max=0.9, min_credit_pct=0.0002),
    dict(name="SENSEX",    key="BSE_INDEX|SENSEX",    otm=0.005, wing_pct=0.0083, lot=20,
         cadence="weekly",  flip=None, rv5_max=None, min_credit_pct=None),
    dict(name="BANKNIFTY", key="NSE_INDEX|Nifty Bank", otm=0.005, wing_pct=0.0083, lot=30,
         cadence="monthly", flip=None, rv5_max=None, min_credit_pct=None),
]

def gj(url, params=None, tries=5):
    for _ in range(tries):
        try:
            r = SESSION.get(url, params=params, timeout=25)
            if r.status_code == 200: return r.json()
        except Exception: pass
        time.sleep(3)
    return {}

def spot_daily(bk):
    cf = f"{C}/spot_{bk['name']}.json"
    if os.path.exists(cf): return json.load(open(cf))
    out = {}
    j = gj(f"{UPSTOX_BASE}/v2/historical-candle/{encode_key(bk['key'])}/day/{END}/2024-08-01")
    for ts, o, h, l, c, *_ in j.get("data", {}).get("candles", []):
        out[ts[:10]] = [o, h, l, c]
    if out: json.dump(out, open(cf, "w"))
    return out

def expiries(bk):
    cf = f"{C}/exps_{bk['name']}.json"
    if os.path.exists(cf): return json.load(open(cf))
    j = gj(f"{UPSTOX_BASE}/v2/expired-instruments/expiries", {"instrument_key": bk["key"]})
    out = sorted(j.get("data", []) or [])
    if out: json.dump(out, open(cf, "w"))
    return out

def contracts(bk, e):
    cf = f"{C}/chain_{bk['name']}_{e}.json"
    if os.path.exists(cf): return json.load(open(cf))
    j = gj(f"{UPSTOX_BASE}/v2/expired-instruments/option/contract",
           {"instrument_key": bk["key"], "expiry_date": e})
    out = j.get("data", []) or []
    if out: json.dump(out, open(cf, "w"))
    return out

def leg_open(key, day, tries=4):
    """entry-day OPEN of that option (daily candle)."""
    cf = f"{C}/leg_{day}_{key.replace('|','_')}.json"
    if os.path.exists(cf):
        v = json.load(open(cf)); return v[0] if v else None
    for _ in range(tries):
        try:
            r = SESSION.get(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/"
                            f"{encode_key(key)}/day/{day}/{day}", timeout=20)
            if r.status_code == 200 and r.json().get("status") == "success":
                cs = r.json()["data"].get("candles", [])
                if cs:
                    ts, o, h, l, c, vol, oi = cs[0]
                    json.dump([o, h, l, c, vol, oi], open(cf, "w")); return o
                json.dump(None, open(cf, "w")); return None
        except Exception: pass
        time.sleep(3)
    return None

def monthly_only(exps):
    """keep the LAST expiry of each calendar month (BANKNIFTY is deployed monthly-only)."""
    by = {}
    for e in exps: by[e[:7]] = max(by.get(e[:7], ""), e)
    return sorted(by.values())

def side_result(bk, ch, e, s_open, s_close, typ):
    """one side's spread outcome; returns (net%margin, net_rs, credit, W) or None."""
    sgn = 1 if typ == "CE" else -1
    side = [c for c in ch if c["instrument_type"] == typ]
    st = sorted(float(c["strike_price"]) for c in side)
    bkey = {float(c["strike_price"]): c["instrument_key"] for c in side}
    if len(st) < 8: return None
    near = lambda x: min(st, key=lambda k: abs(k - x))
    Ks = near(s_open * (1 + sgn * bk["otm"]))
    wing = bk.get("wing_pts") or s_open * bk["wing_pct"]
    Kl = near(Ks + sgn * wing)
    W = abs(Kl - Ks)
    if W < wing * 0.5: return None
    so = leg_open(bkey[Ks], e); lo = leg_open(bkey[Kl], e)
    if so is None or lo is None or so <= 0: return None
    credit = so - lo
    if credit <= 0 or credit >= W: return None
    intr = (max(0.0, s_close - Ks) - max(0.0, s_close - Kl)) if typ == "CE" \
        else (max(0.0, Ks - s_close) - max(0.0, Kl - s_close))
    settle = min(max(intr, 0.0), W)
    lot = int(side[0].get("lot_size") or bk["lot"])
    net = credit - settle - ((so + lo) * SLIP / 100 + BROKER * 4 / lot)
    return net / (W - credit) * 100, net * lot, credit, W

def collect(bk):
    spots = spot_daily(bk); sdays = sorted(spots)
    exps = [e for e in expiries(bk) if START <= e <= END]
    if bk["cadence"] == "monthly": exps = monthly_only(exps)
    print(f"[{bk['name']}] {len(exps)} expiries, {len(spots)} spot days", flush=True)

    def rv5(ds):
        i = sdays.index(ds)
        if i < 6: return None
        return float(np.std(np.diff(np.log([spots[sdays[k]][3] for k in range(i - 6, i)]))) * 100)
    def ret5(ds):
        i = sdays.index(ds)
        if i < 6: return 0.0
        return (spots[sdays[i - 1]][3] / spots[sdays[i - 6]][3] - 1) * 100

    rows = []
    for n, e in enumerate(exps, 1):
        if e not in spots: continue
        ch = contracts(bk, e)
        if not ch: continue
        s_open, s_close = spots[e][0], spots[e][3]
        need = ["CE", "PE"] if bk["flip"] is not None else ["CE"]
        res = {}
        for typ in need:
            r = side_result(bk, ch, e, s_open, s_close, typ)
            if r: res[typ] = r
        if not res: continue
        # deployed side selection
        r5 = ret5(e)
        typ = "PE" if (bk["flip"] is not None and r5 >= bk["flip"] and "PE" in res) else "CE"
        if typ not in res: continue
        pm, rs, credit, W = res[typ]
        v5 = rv5(e)
        # deployed filters -> 'traded' flag (we keep the row either way for transparency)
        traded = True
        if bk["rv5_max"] is not None and (v5 is None or v5 >= bk["rv5_max"]): traded = False
        if bk["min_credit_pct"] is not None and credit < bk["min_credit_pct"] * s_open: traded = False
        rows.append(dict(date=e, book=bk["name"], side=typ, pm=pm, rs=rs, credit=credit,
                         W=W, rv5=v5, ret5=r5, traded=traded, win=int(pm > 0)))
        if n % 20 == 0: print(f"  [{bk['name']}] ...{n}/{len(exps)}", flush=True)
    print(f"[{bk['name']}] collected {len(rows)} rows ({sum(r['traded'] for r in rows)} pass deployed filters)", flush=True)
    return rows

def main():
    allrows = []
    for bk in BOOKS:
        try: allrows += collect(bk)
        except Exception as ex: print(f"!! {bk['name']}: {ex}", flush=True)
    out = os.path.join(HERE, "ndte13_trades.json")
    json.dump(allrows, open(out, "w"), indent=1)
    print(f"\nwrote {len(allrows)} rows -> {out}")
    for bk in BOOKS:
        sel = [r for r in allrows if r["book"] == bk["name"] and r["traded"]]
        if not sel: continue
        pm = np.array([r["pm"] for r in sel])
        print(f"  {bk['name']:10s} n={len(sel):3d} win {(pm>0).mean()*100:5.1f}%  avg {pm.mean():+6.2f}%m")
    print("DONE-NDTE13")

if __name__ == "__main__":
    main()
