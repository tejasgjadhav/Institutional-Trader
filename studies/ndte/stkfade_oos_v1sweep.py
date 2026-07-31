"""OOS confirmation (Oct'24 -> date, REAL Upstox expired-option premiums) for the top
n-preserving exit configs from stkfade_v1_sweep.py. Adapted from studies/stkfade_oos_v1.py
(same gate, same spf slippage incl. EXIT slippage on TP/stop, intrinsic settlement).

Usage: stkfade_oos_v1sweep.py LABEL:short,width,tp,stop [LABEL:...]
Leg premium series are cached in-process per (instrument_key) so multiple configs sharing
a geometry cost no extra network. Progress checkpointed to /tmp/stkfade_oos_v1sweep.json.
"""
import sys, warnings, json
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import datetime, timedelta, date
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical, UPSTOX_BASE
from engine.instruments import encode_key
from engine.expired_options import get_expiries, get_contracts, _get_json as _gj

START = date(2024, 10, 1); MIN_DTE = 10; REENTRY = 3; MIN_CW = 0.40; MIN_PREM = 50.0
CONFIGS = []
for arg in sys.argv[1:]:
    lab, rest = arg.split(":")
    s, w, tp, st = rest.split(",")
    CONFIGS.append((lab, 10, int(s), int(w), float(tp), float(st)))
assert CONFIGS, "pass at least one LABEL:short,width,tp,stop"
print("configs:", CONFIGS, flush=True)

def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0

LEGC = {}
def leg(key, d0, to):
    ck = (key, d0, to)
    if ck in LEGC: return LEGC[ck]
    out = None
    for _try in range(3):
        try:
            j = _gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}")
            if j.get("status") == "success":
                c = j.get("data", {}).get("candles", [])
                if c:
                    df = pd.DataFrame(c, columns=["ts", "O", "H", "L", "C", "V", "OI"])
                    df["ts"] = pd.to_datetime(df["ts"])
                    out = df.set_index("ts").sort_index()["C"]
                break
        except Exception:
            continue
    LEGC[ck] = out
    return out

out = {cid: [] for cid, *_ in CONFIGS}
EXPC = {}; CHC = {}
import threading, concurrent.futures
LK = threading.Lock(); DONE = [0]

def do_stock(sym0):
    sym = sym0.replace(".NS", "")
    try:
        u = fetch_upstox_historical(sym0, unit="days", interval=1, from_date="2024-06-01",
                                    to_date=date.today().isoformat())
    except Exception:
        u = None
    if u is None or u.empty or len(u) < 30:
        with LK: DONE[0] += 1
        return
    u = u.sort_index()
    cb = {ix.date().isoformat(): float(u["Close"].loc[ix]) for ix in u.index}
    for cid, dc, short, width, tp, stop in CONFIGS:
        hi = u["High"].rolling(dc).max().shift(1); lo = u["Low"].rolling(dc).min().shift(1); last = {}
        for i in range(max(dc, 20), len(u) - 1):
            day = u.index[i].date()
            if day < START: continue
            c = float(u["Close"].iloc[i]); typ = None
            if c > float(hi.iloc[i]): typ = "CE"
            elif c < float(lo.iloc[i]): typ = "PE"
            else: continue
            if last.get(typ) and (day - last[typ]).days < REENTRY: continue
            try:
                if sym not in EXPC: EXPC[sym] = get_expiries(sym)
                exps = [e for e in EXPC[sym] if e >= (day + timedelta(days=MIN_DTE)).isoformat()]
                if not exps: continue
                exp = exps[0]
                ck = (sym, exp, typ)
                if ck not in CHC:
                    CHC[ck] = sorted([ct for ct in get_contracts(sym, exp) if ct["instrument_type"] == typ],
                                     key=lambda ct: float(ct["strike_price"]))
                chain = CHC[ck]
            except Exception:
                continue
            ks = [float(ct["strike_price"]) for ct in chain]
            if len(ks) < short + width + 2: continue
            atm = min(range(len(ks)), key=lambda j: abs(ks[j] - c))
            si, li = (atm + short, atm + short + width) if typ == "CE" else (atm - short, atm - short - width)
            if si < 0 or li < 0 or si >= len(ks) or li >= len(ks): continue
            sct, lct = chain[si], chain[li]; sk, lk = ks[si], ks[li]
            to = min(datetime.fromisoformat(exp).date(), day + timedelta(days=45)).isoformat()
            sp = leg(sct["instrument_key"], day.isoformat(), to); lp = leg(lct["instrument_key"], day.isoformat(), to)
            if sp is None or lp is None or len(sp) < 1 or len(lp) < 1: continue
            se = float(sp.iloc[0]); le = float(lp.iloc[0]); credit = se - le; w = abs(sk - lk)
            if se < MIN_PREM or credit <= 0 or credit >= w or credit / w < MIN_CW: continue
            last[typ] = day
            close = None; m = min(len(sp), len(lp))
            for t in range(1, m):
                a = float(sp.iloc[t]); b = float(lp.iloc[t]); cost = a - b
                if tp > 0 and cost <= credit * (1 - tp): close = max(cost, 0.0) + (a * spf(a) + b * spf(b)) / 100.0; break
                if stop > 0 and cost >= credit * stop: close = min(cost, w) + (a * spf(a) + b * spf(b)) / 100.0; break
            if close is None:
                espot = cb.get(exp) or (cb[max(x for x in cb if x <= exp)] if any(x <= exp for x in cb) else c)
                intr = max(0.0, espot - sk) if typ == "CE" else max(0.0, sk - espot)
                intl = max(0.0, espot - lk) if typ == "CE" else max(0.0, lk - espot)
                close = min(max(intr - intl, 0.0), w)
            net = (credit - close) - (se * spf(se) + le * spf(le)) / 100.0
            with LK: out[cid].append(dict(y=day.year, net=float(net), w=float(w), win=int(net > 0)))
    with LK:
        DONE[0] += 1
        if DONE[0] % 10 == 0:
            print(f"  …{DONE[0]}/{len(UNIVERSE)} stocks, " +
                  " ".join(f"{cid}={len(out[cid])}" for cid, *_ in CONFIGS), flush=True)
            json.dump(out, open("/tmp/stkfade_oos_v1sweep.json", "w"))

with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
    list(ex.map(do_stock, UNIVERSE))

json.dump(out, open("/tmp/stkfade_oos_v1sweep.json", "w"))
for cid, dc, short, width, tp, stop in CONFIGS:
    t = pd.DataFrame(out[cid])
    print(f"\n=== OOS Oct24->date — {cid} (DC{dc} s{short} w{width} TP{tp} stop{stop}) — {len(t)} trades ===")
    if len(t) == 0: continue
    for y in sorted(t.y.unique()):
        g = t[t.y == y]; print(f"  {y}: n={len(g):3d}  win {g.win.mean()*100:3.0f}%  net {g.net.sum()/g.w.sum()*100:+6.1f}%")
    print(f"  ALL: n={len(t)}  win {t.win.mean()*100:.1f}%  net {t.net.sum()/t.w.sum()*100:+.1f}% of width")
print("DONE-OOS-SWEEP")
