"""CONDOR — OUT-OF-SAMPLE (Upstox expired options, Oct'24 -> Jul'26). The run that decides.

In-sample (studies/LOWCW_BAND_RESCUE.md sec 9) selling BOTH sides turned both low-c/w bands around:
    0.30-0.35  one side 81.4% / +3.5% ROM   -> condor opp>=0.30  62.7% / +34.6%  5/6 yrs
    0.35-0.40  one side 78.8% / +11.0% ROM  -> condor opp>=0.30  64.8% / +65.7%  6/6 yrs
This window was never used to pick any of that, and it is the window that killed the previous
in-sample winner in this study (the width-1 re-cut: +18.1% IS -> +1.4% OOS). Same bar as before:
beat the one-sided baseline clearly, hold across the opposite-side floor, positive in most years.

STRUCTURE: fade side = short 2-OTM / width 4 (v2 geometry) against the breakout, exactly as the
live books trade. Opposite side = same offset and width on the other option type, added only when
its OWN credit/width clears a floor. Take profit at 40% of TOTAL credit. No stop.

MARGIN = one width - total credit, i.e. the true MAX LOSS: with non-overlapping wings only one side
can finish in the money. NB this is return on RISK. If a broker refuses that offset and blocks both
spreads, cash deployed roughly doubles and every ROM here halves. That check is separate and is
being done in the Upstox app.

Costs: entry slippage on all four legs, plus exit slippage on a TP exit (the one-sided OOS runs
charged the same way, so the comparison is like-for-like).

Resumable: per-stock results checkpoint to /tmp/condor_oos_bysym.json and the leg cache writes
atomically, because the machine is memory-tight and a previous long run was killed by jetsam.
"""
import sys, os, warnings, json, threading, concurrent.futures, pickle, collections
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import datetime, timedelta, date
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical, UPSTOX_BASE
from engine.instruments import encode_key
from engine.expired_options import get_expiries, get_contracts, _get_json as _gj

START = date(2024, 10, 1)
MIN_DTE, REENTRY, MIN_PREM = 10, 3, 50.0
S, W = 2, 4
BANDS = {"b30": (0.30, 0.35), "b35": (0.35, 0.40)}
FLOORS = [None, 0.10, 0.20, 0.30]          # None = one-sided baseline
TP = 0.40
LEGCACHE = "/tmp/condor_legcache.pkl"
BYSYM = "/tmp/condor_oos_bysym.json"
SUBSET = UNIVERSE[::3]                      # same 38-name slice as the earlier OOS runs

def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0

def _load(path, default):
    try:
        with open(path, "rb" if path.endswith(".pkl") else "r") as f:
            return pickle.load(f) if path.endswith(".pkl") else json.load(f)
    except Exception:
        return default
LEGC = _load(LEGCACHE, {})
DONE_SYM = _load(BYSYM, {})
print(f"leg cache {len(LEGC)} · resuming {len(DONE_SYM)} stocks already complete", flush=True)
LK = threading.Lock(); DONE = [0]

def _save():
    for path, obj in ((LEGCACHE, LEGC), (BYSYM, DONE_SYM)):
        tmp = path + ".tmp"
        with open(tmp, "wb" if path.endswith(".pkl") else "w") as f:
            pickle.dump(obj, f) if path.endswith(".pkl") else json.dump(obj, f)
        os.replace(tmp, path)

def leg(key, d0, to):
    ck = (key, d0, to)
    with LK:
        if ck in LEGC: return LEGC[ck]
    j = _gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}")
    s = None
    if j.get("status") == "success":
        c = j.get("data", {}).get("candles", [])
        if c:
            df = pd.DataFrame(c, columns=["ts", "O", "H", "L", "C", "V", "OI"])
            df["ts"] = pd.to_datetime(df["ts"])
            s = df.set_index("ts").sort_index()["C"].to_numpy(dtype="float32")
    with LK: LEGC[ck] = s
    return s

out = collections.defaultdict(list)
for _s, _d in DONE_SYM.items():
    for k, v in _d.items(): out[k].extend(v)
EXPC = {}; CHC = {}

def do_stock(sym0):
    sym = sym0.replace(".NS", "")
    if sym in DONE_SYM:
        with LK: DONE[0] += 1
        return
    mine = collections.defaultdict(list)
    try:
        u = fetch_upstox_historical(sym0, unit="days", interval=1,
                                    from_date="2024-06-01", to_date=date.today().isoformat())
    except Exception:
        u = None
    if u is None or u.empty or len(u) < 30:
        with LK: DONE[0] += 1
        return
    u = u.sort_index()
    cb = {ix.date().isoformat(): float(u["Close"].loc[ix]) for ix in u.index}
    HIS = {d: u["High"].rolling(d).max().shift(1) for d in (5, 10, 15, 20)}
    LOS = {d: u["Low"].rolling(d).min().shift(1) for d in (5, 10, 15, 20)}
    last = {}
    for i in range(20, len(u) - 1):
        day = u.index[i].date()
        if day < START: continue
        c = float(u["Close"].iloc[i]); typ = None
        if any(c > float(HIS[d].iloc[i]) for d in (5, 10, 15, 20)): typ = "CE"
        elif any(c < float(LOS[d].iloc[i]) for d in (5, 10, 15, 20)): typ = "PE"
        else: continue
        if last.get(typ) and (day - last[typ]).days < REENTRY: continue
        other = "PE" if typ == "CE" else "CE"
        try:
            if sym not in EXPC: EXPC[sym] = get_expiries(sym)
            exps = [e for e in EXPC[sym] if e >= (day + timedelta(days=MIN_DTE)).isoformat()]
            if not exps: continue
            exp = exps[0]
            chains = {}
            for t in (typ, other):
                ck = (sym, exp, t)
                if ck not in CHC:
                    CHC[ck] = sorted([x for x in get_contracts(sym, exp) if x["instrument_type"] == t],
                                     key=lambda x: float(x["strike_price"]))
                chains[t] = CHC[ck]
        except Exception:
            continue
        d0 = day.isoformat()
        to = min(datetime.fromisoformat(exp).date(), day + timedelta(days=45)).isoformat()

        def side(t):
            ch = chains[t]; ks = [float(x["strike_price"]) for x in ch]
            if len(ks) < S + W + 2: return None
            atm = min(range(len(ks)), key=lambda j: abs(ks[j] - c))
            si, li = (atm + S, atm + S + W) if t == "CE" else (atm - S, atm - S - W)
            if not (0 <= si < len(ch) and 0 <= li < len(ch)): return None
            sp = leg(ch[si]["instrument_key"], d0, to)
            if sp is None or len(sp) < 1 or float(sp[0]) < MIN_PREM: return None
            lp = leg(ch[li]["instrument_key"], d0, to)
            if lp is None or len(lp) < 1: return None
            se, le = float(sp[0]), float(lp[0])
            credit = se - le; w = abs(ks[si] - ks[li])
            if credit <= 0 or credit >= w: return None
            return dict(sp=sp, lp=lp, se=se, le=le, credit=credit, w=w,
                        sk=ks[si], lk=ks[li], cw=credit / w, t=t)

        qf = side(typ)
        if not qf: continue
        last[typ] = day
        band = next((b for b, (lo, hi) in BANDS.items() if lo <= qf["cw"] < hi), None)
        if band is None: continue
        qo = side(other)

        for fl in FLOORS:
          try:
            legs = [qf]
            if fl is not None:
                if not qo or qo["cw"] < fl: continue
                legs = [qf, qo]
            credit = sum(q["credit"] for q in legs); width = qf["w"]
            if credit >= width: continue
            m = min(min(len(q["sp"]), len(q["lp"])) for q in legs)   # BOTH legs, not just shorts
            close = None
            for k in range(1, m):
                cost = sum(float(q["sp"][k]) - float(q["lp"][k]) for q in legs)
                if cost <= credit * (1 - TP):
                    ex = sum((float(q["sp"][k]) * spf(float(q["sp"][k])) +
                              float(q["lp"][k]) * spf(float(q["lp"][k]))) / 100.0 for q in legs)
                    close = max(cost, 0.0) + ex; break
            if close is None:
                es = cb.get(exp) or (cb[max(x for x in cb if x <= exp)] if any(x <= exp for x in cb) else c)
                tot = 0.0
                for q in legs:
                    intr = max(0.0, es - q["sk"]) if q["t"] == "CE" else max(0.0, q["sk"] - es)
                    intl = max(0.0, es - q["lk"]) if q["t"] == "CE" else max(0.0, q["lk"] - es)
                    tot += min(max(intr - intl, 0.0), q["w"])
                close = min(tot, width)
            entry = sum((q["se"] * spf(q["se"]) + q["le"] * spf(q["le"])) / 100.0 for q in legs)
            net = (credit - close) - entry
            key = f"{band}|{'one' if fl is None else f'{fl:.2f}'}"
            mine[key].append(dict(y=day.year, net=float(net), margin=float(width - credit),
                                  win=int(net > 0), cw=float(credit / width)))
          except Exception:
            continue        # a malformed series must not take the run down
    with LK:
        for k, v in mine.items(): out[k].extend(v)
        DONE_SYM[sym] = {k: v for k, v in mine.items()}
        DONE[0] += 1
        if DONE[0] % 3 == 0:
            print(f"  …{DONE[0]}/{len(SUBSET)} stocks · legs {len(LEGC)} · "
                  f"b30 {len(out.get('b30|one',[]))} b35 {len(out.get('b35|one',[]))}", flush=True)
            _save()

with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
    list(ex.map(do_stock, SUBSET))
_save()

def rep(rows, lab):
    if len(rows) < 15: print(f"{lab:<40} n={len(rows):>4}  (too few)"); return
    n = len(rows); nm = sum(x["net"] for x in rows); mg = sum(x["margin"] for x in rows)
    by = collections.defaultdict(list)
    for x in rows: by[x["y"]].append(x)
    pos = sum(1 for g in by.values() if sum(a["net"] for a in g) > 0)
    print(f"{lab:<40} n={n:>4}  win {sum(x['win'] for x in rows)/n*100:5.1f}%  "
          f"ROM {nm/mg*100:+7.1f}%  +ve {pos}/{len(by)}  c/w {sum(x['cw'] for x in rows)/n:.2f}")

print(f"\n=== CONDOR OOS Oct'24 -> Jul'26 · {len(SUBSET)} names · TP-{int(TP*100)} of total credit ===")
for b, (lo, hi) in BANDS.items():
    print(f"\nBAND {lo:.2f}-{hi:.2f}")
    rep(out.get(f"{b}|one", []), "  ONE SIDE (baseline)")
    for fl in FLOORS[1:]:
        rep(out.get(f"{b}|{fl:.2f}", []), f"  CONDOR · opposite side c/w >= {fl:.2f}")
print("\nDONE-CONDOR-OOS")
