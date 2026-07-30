"""OOS confirmation of the v1 exit-sweep winners (V1_WINRATE_SWEEP): fetch each v1-geometry
trade's daily premium path ONCE from Upstox expired-instruments (Oct'24->date), then evaluate
ALL candidate exits on the same paths: deployed (TP.75/stop2), TP.40/stop3, TP.50/no-stop,
TP.40/no-stop. Entry gates identical to deployed v1 (DC10, s1w3, c/w>=0.40, prem>=50) so n is
the SAME across configs (n-preserving constraint). Based on studies/stkfade_oos_v1.py."""
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
DC, SHORT, WIDTH = 10, 1, 3
EXITS = [("deployed TP.75 stop2.0", 0.75, 2.0), ("TP.40 stop3.0", 0.40, 3.0),
         ("TP.50 no-stop", 0.50, None), ("TP.40 no-stop", 0.40, None)]
OUT = "/tmp/v1_oos_exits.json"

def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0
def leg(key, d0, to):
    j = _gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}")
    if j.get("status") == "success":
        c = j.get("data", {}).get("candles", [])
        if c:
            df = pd.DataFrame(c, columns=["ts","O","H","L","C","V","OI"]); df["ts"] = pd.to_datetime(df["ts"])
            return df.set_index("ts").sort_index()["C"]
    return None

recs = []   # each: {y, credit, w, path:[[s,l]..], settle}
EXPC = {}; CHC = {}
import threading, concurrent.futures
LK = threading.Lock(); DONE = [0]

def do_stock(sym0):
    sym = sym0.replace(".NS", "")
    try:
        u = fetch_upstox_historical(sym0, unit="days", interval=1, from_date="2024-06-01", to_date=date.today().isoformat())
        if u is None or u.empty or len(u) < 30: raise ValueError("no underlying")
        u = u.sort_index()
        cb = {ix.date().isoformat(): float(u["Close"].loc[ix]) for ix in u.index}
        hi = u["High"].rolling(DC).max().shift(1); lo = u["Low"].rolling(DC).min().shift(1); last = {}
        for i in range(max(DC, 20), len(u) - 1):
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
            if se < MIN_PREM or credit <= 0 or credit >= w or credit / w < MIN_CW: continue
            last[typ] = day
            m = min(len(sp), len(lp))
            path = [[float(sp.iloc[t]), float(lp.iloc[t])] for t in range(1, m)]
            espot = cb.get(exp) or (cb[max(x for x in cb if x <= exp)] if any(x <= exp for x in cb) else c)
            intr = max(0.0, espot - sk) if typ == "CE" else max(0.0, sk - espot)
            intl = max(0.0, espot - lk) if typ == "CE" else max(0.0, lk - espot)
            settle = min(max(intr - intl, 0.0), w)
            with LK:
                recs.append(dict(y=day.year, credit=credit, w=w, se=se, le=le, path=path, settle=settle))
    except Exception:
        pass
    with LK:
        DONE[0] += 1
        if DONE[0] % 10 == 0:
            print(f"  …{DONE[0]}/{len(UNIVERSE)} stocks, {len(recs)} trades", flush=True)
            json.dump(recs, open(OUT, "w"))

print(f"OOS path fetch Oct'24->date, v1 geometry (DC{DC} s{SHORT} w{WIDTH})…", flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
    list(ex.map(do_stock, UNIVERSE))
json.dump(recs, open(OUT, "w"))
print(f"  fetched {len(recs)} trades -> {OUT}", flush=True)

def walk(r, tp, stop):
    credit = r["credit"]; w = r["w"]
    for s, l in r["path"]:
        cost = s - l
        if tp > 0 and cost <= credit * (1 - tp):
            return max(cost, 0.0) + (s * spf(s) + l * spf(l)) / 100.0
        if stop is not None and cost >= credit * stop:
            return min(cost, w) + (s * spf(s) + l * spf(l)) / 100.0
    return r["settle"]

print(f"\n=== OOS (Oct'24->date) — SAME {len(recs)} trades, four exits ===")
for lab, tp, stop in EXITS:
    nets = []; wins = 0; wsum = 0.0
    ys = {}
    for r in recs:
        close = walk(r, tp, stop)
        net = (r["credit"] - close) - (r["se"] * spf(r["se"]) + r["le"] * spf(r["le"])) / 100.0
        nets.append(net); wsum += r["w"]; wins += int(net > 0)
        ys.setdefault(r["y"], []).append((net, r["w"]))
    n = len(nets)
    yr = "  ".join(f"{y}:{sum(a for a,_ in g)/sum(b for _,b in g)*100:+.1f}%w/{sum(1 for a,_ in g if a>0)/len(g)*100:.0f}%"
                   for y, g in sorted(ys.items()))
    print(f"{lab:24s} n={n} win {wins/n*100:5.1f}%  net {sum(nets)/wsum*100:+6.1f}%w   [{yr}]", flush=True)
print("DONE-V1-OOS-EXITS")
