"""v2 UNION stock fade — win% + net by CREDIT/WIDTH bucket (user ask 2026-07-14).
Deployed v2 config EXCEPT the c/w gate is lowered to 0.30 so we can see the [0.30-0.35),
[0.35-0.40), [>=0.40] buckets. All other gates unchanged: prem>=50, live two-sided quote,
UNION Donchian (5,10,15,20), short 2-OTM, width 4, TP 50% of credit, stop 3x, reentry 3d,
min DTE 10. Real Upstox expired-option premiums Oct'24->date (~last 2 years — the only window
with real premiums). Costs: 2.5% slippage on legs + Rs20x4/lot. Settle intrinsic at expiry.
Answers: does 0.35 (or 0.30-0.35) win less AND lose money vs >=0.40? Out: /tmp/cw_buckets.json
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
MIN_CW = 0.30; MIN_PREM = 50.0                 # gate lowered to 0.30 to expose the buckets
UNION_DCS = (5, 10, 15, 20); SHORT = 2; WIDTH = 4; TP = 0.50; STOP = 3.0

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
        except Exception:
            pass
        time.sleep(2)
    return None

out = []; EXPC = {}; CHC = {}; LK = threading.Lock(); DONE = [0]

def do_stock(sym0):
    sym = sym0.replace(".NS", "")
    try:
        u = fetch_upstox_historical(sym0, unit="days", interval=1, from_date="2024-06-01", to_date=date.today().isoformat())
        if u is None or u.empty or len(u) < 30:
            with LK: DONE[0] += 1
            return
        u = u.sort_index()
        cb = {ix.date().isoformat(): float(u["Close"].loc[ix]) for ix in u.index}
        rolls = {dc: (u["High"].rolling(dc).max().shift(1), u["Low"].rolling(dc).min().shift(1)) for dc in UNION_DCS}
        last = {}
        for i in range(max(UNION_DCS) + 1, len(u) - 1):
            day = u.index[i].date()
            if day < START: continue
            c = float(u["Close"].iloc[i]); typ = None
            for dc in UNION_DCS:
                hi, lo = rolls[dc]
                if c > float(hi.iloc[i]): typ = "CE"; break
                if c < float(lo.iloc[i]): typ = "PE"; break
            if typ is None: continue
            if last.get(typ) and (day - last[typ]).days < REENTRY: continue
            try:
                if sym not in EXPC: EXPC[sym] = get_expiries(sym)
                exps = [e for e in EXPC[sym] if e >= (day + timedelta(days=MIN_DTE)).isoformat()]
                if not exps: continue
                exp = exps[0]; ck = (sym, exp, typ)
                if ck not in CHC:
                    CHC[ck] = sorted([ct for ct in get_contracts(sym, exp) if ct["instrument_type"] == typ],
                                     key=lambda ct: float(ct["strike_price"]))
                chain = CHC[ck]
            except Exception: continue
            ks = [float(ct["strike_price"]) for ct in chain]
            if len(ks) < SHORT + WIDTH + 2: continue
            atm = min(range(len(ks)), key=lambda j: abs(ks[j] - c))
            si, li = (atm + SHORT, atm + SHORT + WIDTH) if typ == "CE" else (atm - SHORT, atm - SHORT - WIDTH)
            if si < 0 or li < 0 or si >= len(ks) or li >= len(ks): continue
            sct, lct = chain[si], chain[li]; sk, lk = ks[si], ks[li]
            to = min(datetime.fromisoformat(exp).date(), day + timedelta(days=45)).isoformat()
            sp = leg(sct["instrument_key"], day.isoformat(), to); lp = leg(lct["instrument_key"], day.isoformat(), to)
            if sp is None or lp is None or len(sp) < 1 or len(lp) < 1: continue
            se = float(sp.iloc[0]); le = float(lp.iloc[0]); credit = se - le; w = abs(sk - lk)
            if se < MIN_PREM or credit <= 0 or credit >= w: continue
            cw = credit / w
            if cw < MIN_CW: continue                       # only the >=0.30 population
            last[typ] = day
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
            with LK: out.append(dict(y=day.year, cw=round(cw, 3), net=float(net), w=float(w), win=int(net > 0)))
    except Exception as e:
        with LK: print(f"  !! {sym}: {e}", flush=True)
    with LK:
        DONE[0] += 1
        if DONE[0] % 20 == 0:
            json.dump(out, open("/tmp/cw_buckets.json", "w"))
            print(f"  …{DONE[0]}/100 stocks, {len(out)} trades", flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    list(ex.map(do_stock, UNIVERSE))
json.dump(out, open("/tmp/cw_buckets.json", "w"))

t = pd.DataFrame(out)
print(f"\n=== v2 UNION fade, c/w buckets, Oct'24->date — {len(t)} trades ===")
BUCKETS = [(0.30, 0.35, "0.30-0.35"), (0.35, 0.40, "0.35-0.40"), (0.40, 9.9, ">=0.40 (deployed)")]
print(f"{'bucket':20s} {'n':>4s} {'win%':>6s} {'net %width':>11s} {'avgWin%w':>9s} {'avgLoss%w':>10s}")
for lo, hi, lab in BUCKETS:
    g = t[(t.cw >= lo) & (t.cw < hi)]
    if len(g) == 0: print(f"{lab:20s} {0:4d}"); continue
    wpct = g.win.mean()*100; netw = g.net.sum()/g.w.sum()*100
    aw = g[g.win==1]; al = g[g.win==0]
    awp = (aw.net/aw.w*100).mean() if len(aw) else 0; alp = (al.net/al.w*100).mean() if len(al) else 0
    print(f"{lab:20s} {len(g):4d} {wpct:6.1f} {netw:+11.1f} {awp:+9.1f} {alp:+10.1f}")
print("\n-- 0.35-0.40 bucket by year --")
b = t[(t.cw >= 0.35) & (t.cw < 0.40)]
for y in sorted(b.y.unique()):
    g = b[b.y == y]; print(f"  {y}: n={len(g):3d} win {g.win.mean()*100:3.0f}% net {g.net.sum()/g.w.sum()*100:+.1f}%w")
print("DONE-CWBUCKETS")
