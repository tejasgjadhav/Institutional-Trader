"""D5-only vs D10-only breakout for the deployed v2 fade (user ask 2026-07-17).
The UNION scanner effectively = D5 (D10/15/20 breaks are a subset of D5 breaks), so this
compares the two real breakout definitions. Deployed v2 config: short 2-OTM, width 4, TP 50%,
stop 3x, gate credit/width>=0.40 + prem>=50, min-DTE 10, reentry 3d. Real Upstox premiums
Oct'24->date. Costs 2.5% slippage + Rs20x4/lot. Settle intrinsic at expiry.
Out: /tmp/d5_v_d10.json. Reports per config: n, win%, net %width, per-year.
"""
import sys, warnings, json, time
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import datetime, timedelta, date
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical, UPSTOX_BASE
from engine.instruments import encode_key
from engine.expired_options import get_expiries, get_contracts, _get_json as _gj
import threading, concurrent.futures

START = date(2024, 10, 1); MIN_DTE = 10; REENTRY = 3
MIN_CW = 0.40; MIN_PREM = 50.0; SHORT = 2; WIDTH = 4; TP = 0.50; STOP = 3.0
CONFIGS = [("D5", 5), ("D10", 10)]

def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0
def leg(key, d0, to):
    url = f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}"
    for _ in range(3):
        try:
            j = _gj(url)
            if j.get("status") == "success":
                c = j.get("data", {}).get("candles", [])
                if c:
                    df = pd.DataFrame(c, columns=["ts","O","H","L","C","V","OI"]); df["ts"]=pd.to_datetime(df["ts"])
                    return df.set_index("ts").sort_index()["C"]
                return None
        except Exception: pass
        time.sleep(2)
    return None

out = {cid: [] for cid, _ in CONFIGS}
EXPC = {}; CHC = {}; LK = threading.Lock(); DONE = [0]

def sim_one(sym, cb, day, typ, c):
    if sym not in EXPC: EXPC[sym] = get_expiries(sym)
    exps = [e for e in EXPC[sym] if e >= (day + timedelta(days=MIN_DTE)).isoformat()]
    if not exps: return None
    exp = exps[0]; ck = (sym, exp, typ)
    if ck not in CHC:
        CHC[ck] = sorted([ct for ct in get_contracts(sym, exp) if ct["instrument_type"] == typ],
                         key=lambda ct: float(ct["strike_price"]))
    chain = CHC[ck]; ks = [float(ct["strike_price"]) for ct in chain]
    if len(ks) < SHORT + WIDTH + 2: return None
    atm = min(range(len(ks)), key=lambda j: abs(ks[j] - c))
    si, li = (atm + SHORT, atm + SHORT + WIDTH) if typ == "CE" else (atm - SHORT, atm - SHORT - WIDTH)
    if si < 0 or li < 0 or si >= len(ks) or li >= len(ks): return None
    sct, lct = chain[si], chain[li]; sk, lk = ks[si], ks[li]
    to = min(datetime.fromisoformat(exp).date(), day + timedelta(days=45)).isoformat()
    sp = leg(sct["instrument_key"], day.isoformat(), to); lp = leg(lct["instrument_key"], day.isoformat(), to)
    if sp is None or lp is None or len(sp) < 1 or len(lp) < 1: return None
    se = float(sp.iloc[0]); le = float(lp.iloc[0]); credit = se - le; w = abs(sk - lk)
    if se < MIN_PREM or credit <= 0 or credit >= w or credit / w < MIN_CW: return None
    close = None; m = min(len(sp), len(lp))
    for t in range(1, m):
        a = float(sp.iloc[t]); b = float(lp.iloc[t]); cost = a - b
        if cost <= credit * (1 - TP): close = max(cost, 0.0) + (a*spf(a)+b*spf(b))/100.0; break
        if cost >= credit * STOP: close = min(cost, w) + (a*spf(a)+b*spf(b))/100.0; break
    if close is None:
        espot = cb.get(exp) or (cb[max(x for x in cb if x < exp)] if any(x < exp for x in cb) else c)
        intr = max(0.0, espot - sk) if typ == "CE" else max(0.0, sk - espot)
        intl = max(0.0, espot - lk) if typ == "CE" else max(0.0, lk - espot)
        close = min(max(intr - intl, 0.0), w)
    net = (credit - close) - (se*spf(se)+le*spf(le))/100.0
    return dict(y=day.year, net=float(net), w=float(w), win=int(net > 0), cw=round(credit/w, 3))

def do_stock(sym0):
    sym = sym0.replace(".NS", "")
    try:
        u = fetch_upstox_historical(sym0, unit="days", interval=1, from_date="2024-06-01", to_date=date.today().isoformat())
        if u is None or u.empty or len(u) < 30:
            with LK: DONE[0]+=1
            return
        u = u.sort_index(); cb = {ix.date().isoformat(): float(u["Close"].loc[ix]) for ix in u.index}
        for cid, dc in CONFIGS:
            hi = u["High"].rolling(dc).max().shift(1); lo = u["Low"].rolling(dc).min().shift(1); last = {}
            for i in range(dc + 1, len(u) - 1):
                day = u.index[i].date()
                if day < START: continue
                c = float(u["Close"].iloc[i]); typ = None
                if c > float(hi.iloc[i]): typ = "CE"
                elif c < float(lo.iloc[i]): typ = "PE"
                else: continue
                if last.get(typ) and (day - last[typ]).days < REENTRY: continue
                r = sim_one(sym, cb, day, typ, c)
                if r is None: continue
                last[typ] = day
                with LK: out[cid].append(r)
    except Exception as e:
        with LK: print(f"  !! {sym}: {e}", flush=True)
    with LK:
        DONE[0] += 1
        if DONE[0] % 20 == 0:
            json.dump(out, open("/tmp/d5_v_d10.json", "w"))
            print(f"  ...{DONE[0]}/100 stocks | D5={len(out['D5'])} D10={len(out['D10'])}", flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    list(ex.map(do_stock, UNIVERSE))
json.dump(out, open("/tmp/d5_v_d10.json", "w"))

print(f"\n=== v2 fade (gate>=0.40) D5-only vs D10-only, Oct'24->date ===")
print(f"{'cfg':4s} {'n':>4s} {'/mo':>5s} {'win%':>6s} {'net %width':>11s}")
for cid, _ in CONFIGS:
    t = pd.DataFrame(out[cid])
    if len(t) == 0: print(f"{cid:4s} 0"); continue
    permo = len(t) / 21.0
    print(f"{cid:4s} {len(t):4d} {permo:5.1f} {t.win.mean()*100:6.1f} {t.net.sum()/t.w.sum()*100:+11.1f}")
print("\n-- per year --")
for cid, _ in CONFIGS:
    t = pd.DataFrame(out[cid])
    if len(t) == 0: continue
    ys = " · ".join(f"{y}:{g.win.mean()*100:.0f}%/{g.net.sum()/g.w.sum()*100:+.0f}%w" for y, g in t.groupby('y'))
    print(f"  {cid}: {ys}")
print("DONE-D5D10")
