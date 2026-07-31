"""OOS exit sweep for the INDEX swing fade (NIFTY only): was the v1-stock early-booking exit
(TP-40/TP-50 of credit, no stop) ever tried on the index? Clone of stkfade_v1_oos_exits.py:
fetch each trade's daily premium path ONCE from Upstox expired-instruments (Oct'24->date), then
evaluate ALL candidate exits on the SAME trades (n-preserving). Geometry mirrors the deployed
engine/swing_credit.py: Donchian-10 daily breakout, FADE (up-break->bear-call CE, down->bull-put
PE), nearest expiry >= 10 DTE, short 1-OTM, long +3 strikes, entry at close, reentry 3d.
NO credit/width or premium gate (index c/w runs ~0.2-0.35); each trade's c/w is recorded."""
import sys, time, warnings, json
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import datetime, timedelta, date
from engine.data_fetcher import fetch_upstox_historical, UPSTOX_BASE
from engine.instruments import encode_key
from engine.expired_options import get_expiries as _ge, get_contracts as _gc, _get_json as _gj

SYM = "NIFTY"
START = date(2024, 10, 1); MIN_DTE = 10; REENTRY = 3
DC, SHORT, WIDTH = 10, 1, 3
EXITS = [("deployed hold stop2.0", None, 2.0), ("TP.75 stop2.0", 0.75, 2.0),
         ("TP.50 no-stop", 0.50, None), ("TP.40 no-stop", 0.40, None)]
OUT = "/private/tmp/claude-501/-Users-sayali-files/d62dc509-cfa1-4925-8c10-c57a2151b1c9/scratchpad/idxfade_oos_trades.json"

def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0

def get_expiries(sym, tries=5):
    for i in range(tries):
        out = _ge(sym)
        if out: return out
        time.sleep(6)
    return []

def get_contracts(sym, e, tries=5):
    for i in range(tries):
        out = _gc(sym, e)
        if out: return out
        time.sleep(6)
    return []

def leg(key, d0, to, tries=3):
    for i in range(tries):
        j = _gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}")
        if j.get("status") == "success":
            c = j.get("data", {}).get("candles", [])
            if c:
                df = pd.DataFrame(c, columns=["ts","O","H","L","C","V","OI"]); df["ts"] = pd.to_datetime(df["ts"])
                return df.set_index("ts").sort_index()["C"]
        time.sleep(4)
    return None

print(f"INDEX fade OOS path fetch Oct'24->date, {SYM} (DC{DC} s{SHORT} w{WIDTH}, >= {MIN_DTE} DTE)…", flush=True)
u = fetch_upstox_historical(SYM, unit="days", interval=1, from_date="2024-06-01", to_date=date.today().isoformat())
if u is None or u.empty or len(u) < 30:
    print("FATAL: no underlying data from Upstox", flush=True); sys.exit(1)
u = u.sort_index()
cb = {ix.date().isoformat(): float(u["Close"].loc[ix]) for ix in u.index}
hi = u["High"].rolling(DC).max().shift(1); lo = u["Low"].rolling(DC).min().shift(1)
exps_all = get_expiries(SYM)
if not exps_all:
    print("FATAL: no expiries from expired-instruments API (Upstox unreachable?)", flush=True); sys.exit(1)

recs = []; CHC = {}; last = {}
for i in range(max(DC, 20), len(u) - 1):
    day = u.index[i].date()
    if day < START: continue
    c = float(u["Close"].iloc[i]); typ = None
    if c > float(hi.iloc[i]): typ = "CE"
    elif c < float(lo.iloc[i]): typ = "PE"
    else: continue
    if last.get(typ) and (day - last[typ]).days < REENTRY: continue
    exps = [e for e in exps_all if e >= (day + timedelta(days=MIN_DTE)).isoformat()]
    if not exps: continue
    exp = exps[0]; ck = (exp, typ)
    if ck not in CHC:
        CHC[ck] = sorted([ct for ct in get_contracts(SYM, exp) if ct["instrument_type"] == typ],
                         key=lambda ct: float(ct["strike_price"]))
    chain = CHC[ck]
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
    if credit <= 0 or credit >= w: continue   # sanity only — NO c/w or premium gate
    last[typ] = day
    m = min(len(sp), len(lp))
    path = [[float(sp.iloc[t]), float(lp.iloc[t])] for t in range(1, m)]
    espot = cb.get(exp) or (cb[max(x for x in cb if x <= exp)] if any(x <= exp for x in cb) else c)
    intr = max(0.0, espot - sk) if typ == "CE" else max(0.0, sk - espot)
    intl = max(0.0, espot - lk) if typ == "CE" else max(0.0, lk - espot)
    settle = min(max(intr - intl, 0.0), w)
    recs.append(dict(d=day.isoformat(), y=day.year, typ=typ, exp=exp, credit=credit, w=w,
                     cw=credit / w, se=se, le=le, path=path, settle=settle))
    print(f"  {day} {typ} exp {exp} short {sk:.0f} credit {credit:.1f} w {w:.0f} c/w {credit/w:.2f} pathdays {len(path)}", flush=True)
    json.dump(recs, open(OUT, "w"))

json.dump(recs, open(OUT, "w"))
print(f"  fetched {len(recs)} trades -> {OUT}", flush=True)

def walk(r, tp, stop):
    credit = r["credit"]; w = r["w"]
    for s, l in r["path"]:
        cost = s - l
        if tp is not None and cost <= credit * (1 - tp):
            return max(cost, 0.0) + (s * spf(s) + l * spf(l)) / 100.0
        if stop is not None and cost >= credit * stop:
            return min(cost, w) + (s * spf(s) + l * spf(l)) / 100.0
    return r["settle"]

cws = sorted(r["cw"] for r in recs)
if cws:
    med = cws[len(cws) // 2]
    print(f"\nc/w distribution (n={len(cws)}): min {cws[0]:.2f}  p25 {cws[len(cws)//4]:.2f}  "
          f"median {med:.2f}  p75 {cws[3*len(cws)//4]:.2f}  max {cws[-1]:.2f}", flush=True)

print(f"\n=== INDEX fade OOS (Oct'24->date, {SYM}) — SAME {len(recs)} trades, four exits ===")
for lab, tp, stop in EXITS:
    nets = []; wins = 0; wsum = 0.0; ys = {}
    for r in recs:
        close = walk(r, tp, stop)
        net = (r["credit"] - close) - (r["se"] * spf(r["se"]) + r["le"] * spf(r["le"])) / 100.0
        nets.append((net, r["w"])); wsum += r["w"]; wins += int(net > 0)
        ys.setdefault(r["y"], []).append((net, r["w"]))
    n = len(nets)
    if not n: break
    wn = [a / b for a, b in nets if a > 0]; ln = [a / b for a, b in nets if a <= 0]
    aw = sum(wn) / len(wn) * 100 if wn else 0.0; al = sum(ln) / len(ln) * 100 if ln else 0.0
    yr = "  ".join(f"{y}:{sum(a for a,_ in g)/sum(b for _,b in g)*100:+.1f}%w/{sum(1 for a,_ in g if a>0)/len(g)*100:.0f}%(n={len(g)})"
                   for y, g in sorted(ys.items()))
    print(f"{lab:22s} n={n} win {wins/n*100:5.1f}%  net {sum(a for a,_ in nets)/wsum*100:+6.1f}%w  "
          f"avgWin {aw:+5.1f}%w avgLoss {al:+6.1f}%w   [{yr}]", flush=True)
print("DONE-IDX-OOS-EXITS")
