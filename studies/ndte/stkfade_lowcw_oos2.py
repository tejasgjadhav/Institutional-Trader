"""LOW-C/W RESCUE — focused OUT-OF-SAMPLE confirmation (Upstox expired options, Oct'24 -> date).

Replaces the 432-cell OOS grid, which needed ~25k calls against a rate-limited endpoint (~10h).
The in-sample sweep has already narrowed the question to two claims; this confirms exactly those,
and nothing else, so the run costs ~7 legs per signal instead of ~15.

CLAIM 1 (the deployed book, geometry UNCHANGED — needs no extra legs at all):
    v2's 3x stop costs money. S2/W4 TP-40 or TP-50 with NO stop should beat the deployed
    TP-50/stop-3x on the SAME c/w>=0.40 signals. IS: 89.4% win / +70.4% ROM vs 82.9% / +58.1%.

CLAIM 2 (the 0.30-0.40 band — the user's question):
    the band is dead at the deployed width-4 geometry (IS 74.3% win, -1.1% ROM, +ve 3/6 yrs)
    but tradeable when the wing is bought 1 strike away instead of 4, TP-40/50, no stop.
    IS: 87.8% win / +18.1% ROM / +ve 6/6 yrs on 680 trades.

Both were selected on 2019->Sep'24 bhavcopy. This window is untouched by that selection.
Leg series are cached to disk so an interrupted run resumes cheaply.
"""
import sys, os, warnings, json, threading, concurrent.futures, pickle
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
REF_SHORT, REF_WIDTH = 2, 4
BAND = (0.30, 0.40)
LEGCACHE = "/tmp/lowcw_legcache.pkl"

# (label, population, S, W, TP, STOP)
CONFIGS = [
    ("GATE  S2/W4 TP-50 stop-3x  [DEPLOYED]", "gate", 2, 4, 0.50, 3.0),
    ("GATE  S2/W4 TP-40 no-stop",             "gate", 2, 4, 0.40, None),
    ("GATE  S2/W4 TP-50 no-stop",             "gate", 2, 4, 0.50, None),
    ("GATE  S2/W4 TP-75 no-stop",             "gate", 2, 4, 0.75, None),
    ("BAND  S2/W4 TP-50 stop-3x  [baseline]", "band", 2, 4, 0.50, 3.0),
    ("BAND  S2/W4 TP-40 no-stop",             "band", 2, 4, 0.40, None),
    ("BAND  S1/W1 TP-40 no-stop",             "band", 1, 1, 0.40, None),
    ("BAND  S2/W1 TP-40 no-stop",             "band", 2, 1, 0.40, None),
    ("BAND  S2/W1 TP-50 no-stop",             "band", 2, 1, 0.50, None),
]

# The expired-instruments endpoint throttles each call to ~7 s, and ~80% of the calls go on
# pricing the reference geometry just to bucket a signal. The full 113-name universe needs ~30k
# legs (~10 h). This runs every 3rd name BY POSITION IN config.UNIVERSE -- an arbitrary slice with
# respect to performance, not a pick of good names -- for a tractable run at ample sample size.
SUBSET = UNIVERSE[::3]

def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0

def _load_cache():
    """Tolerant load: a run killed mid-dump leaves a truncated pickle, and losing the cache is
    far better than refusing to start."""
    try:
        with open(LEGCACHE, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        print(f"  leg cache unreadable ({e.__class__.__name__}) — starting empty", flush=True)
        return {}

def _save_cache():
    """Atomic: dump to a temp file then rename, so a kill can never truncate the real one."""
    tmp = LEGCACHE + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(LEGC, f)
    os.replace(tmp, LEGCACHE)

LEGC = _load_cache() if os.path.exists(LEGCACHE) else {}
print(f"leg cache: {len(LEGC)} entries", flush=True)
LEGLK = threading.Lock()

def leg(key, d0, to):
    ck = (key, d0, to)
    with LEGLK:
        if ck in LEGC: return LEGC[ck]
    j = _gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}")
    s = None
    if j.get("status") == "success":
        c = j.get("data", {}).get("candles", [])
        if c:
            df = pd.DataFrame(c, columns=["ts", "O", "H", "L", "C", "V", "OI"])
            df["ts"] = pd.to_datetime(df["ts"])
            s = df.set_index("ts").sort_index()["C"].astype("float32")
    with LEGLK: LEGC[ck] = s
    return s

out = {i: [] for i in range(len(CONFIGS))}
seen = {"gate": 0, "band": 0, "low": 0}
EXPC = {}; CHC = {}; LK = threading.Lock(); DONE = [0]

def do_stock(sym0):
    sym = sym0.replace(".NS", "")
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
        try:
            if sym not in EXPC: EXPC[sym] = get_expiries(sym)
            exps = [e for e in EXPC[sym] if e >= (day + timedelta(days=MIN_DTE)).isoformat()]
            if not exps: continue
            exp = exps[0]; ck = (sym, exp, typ)
            if ck not in CHC:
                CHC[ck] = sorted([ct for ct in get_contracts(sym, exp) if ct["instrument_type"] == typ],
                                 key=lambda ct: float(ct["strike_price"]))
            chain = CHC[ck]
        except Exception:
            continue
        ks = [float(ct["strike_price"]) for ct in chain]
        if len(ks) < REF_SHORT + REF_WIDTH + 2: continue
        atm = min(range(len(ks)), key=lambda j: abs(ks[j] - c))
        to = min(datetime.fromisoformat(exp).date(), day + timedelta(days=45)).isoformat()
        d0 = day.isoformat()

        def idx(S, W):
            si, li = (atm + S, atm + S + W) if typ == "CE" else (atm - S, atm - S - W)
            return (si, li) if 0 <= si < len(ks) and 0 <= li < len(ks) else None

        # ── classify on the REFERENCE geometry ──
        ref = idx(REF_SHORT, REF_WIDTH)
        if not ref: continue
        rs, rl = ref
        # short leg FIRST: ~40% of signals fail the Rs50 premium gate, and bailing here saves
        # the long-leg call on every one of them. The endpoint is the binding constraint.
        rsp = leg(chain[rs]["instrument_key"], d0, to)
        if rsp is None or len(rsp) < 1: continue
        rse = float(rsp.iloc[0])
        if rse < MIN_PREM: continue
        rlp = leg(chain[rl]["instrument_key"], d0, to)
        if rlp is None or len(rlp) < 1: continue
        rle = float(rlp.iloc[0])
        rcredit = rse - rle; rw = abs(ks[rs] - ks[rl])
        if rcredit <= 0 or rcredit >= rw: continue
        last[typ] = day
        cw = rcredit / rw
        pop = "gate" if cw >= 0.40 else ("band" if cw >= BAND[0] else "low")
        with LK: seen[pop] += 1
        if pop == "low": continue

        for ci, (lab, want, S, W, TP, STOP) in enumerate(CONFIGS):
            if want != pop: continue
            sel = idx(S, W)
            if not sel: continue
            si, li = sel
            if si == li: continue
            sp_ = leg(chain[si]["instrument_key"], d0, to); lp_ = leg(chain[li]["instrument_key"], d0, to)
            if sp_ is None or lp_ is None or len(sp_) < 1 or len(lp_) < 1: continue
            se, le = float(sp_.iloc[0]), float(lp_.iloc[0])
            credit = se - le; w = abs(ks[si] - ks[li])
            if se < MIN_PREM or credit <= 0 or credit >= w: continue
            close = None; m = min(len(sp_), len(lp_))
            for t in range(1, m):
                a, b = float(sp_.iloc[t]), float(lp_.iloc[t]); cost = a - b
                if TP is not None and cost <= credit * (1 - TP):
                    close = max(cost, 0.0) + (a * spf(a) + b * spf(b)) / 100.0; break
                if STOP is not None and cost >= credit * STOP:
                    close = min(cost, w) + (a * spf(a) + b * spf(b)) / 100.0; break
            if close is None:
                espot = cb.get(exp) or (cb[max(x for x in cb if x <= exp)] if any(x <= exp for x in cb) else c)
                intr = max(0.0, espot - ks[si]) if typ == "CE" else max(0.0, ks[si] - espot)
                intl = max(0.0, espot - ks[li]) if typ == "CE" else max(0.0, ks[li] - espot)
                close = min(max(intr - intl, 0.0), w)
            net = (credit - close) - (se * spf(se) + le * spf(le)) / 100.0
            with LK:
                out[ci].append(dict(y=day.year, net=float(net), w=float(w),
                                    margin=float(w - credit), win=int(net > 0)))
    with LK:
        DONE[0] += 1
        if DONE[0] % 3 == 0:
            print(f"  …{DONE[0]}/{len(SUBSET)} stocks · gate={seen['gate']} band={seen['band']} "
                  f"low={seen['low']} · legs cached {len(LEGC)}", flush=True)
            json.dump({str(k): v for k, v in out.items()}, open("/tmp/lowcw_oos2.json", "w"))
            _save_cache()

with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
    list(ex.map(do_stock, SUBSET))
json.dump({str(k): v for k, v in out.items()}, open("/tmp/lowcw_oos2.json", "w"))
_save_cache()

print(f"\n=== OOS Oct'24 -> date · signals: gate(c/w>=0.40)={seen['gate']}  "
      f"band(0.30-0.40)={seen['band']}  below={seen['low']} ===")
print(f"{'config':<40} {'n':>5} {'win%':>6} {'ROM%':>8} {'net%w':>7} {'+yrs':>6}  per-year ROM")
for ci, (lab, *_rest) in enumerate(CONFIGS):
    t = pd.DataFrame(out[ci])
    if len(t) == 0:
        print(f"{lab:<40} {'0':>5}   no trades"); continue
    yrs = {int(y): g.net.sum() / g.margin.sum() * 100 for y, g in t.groupby("y")}
    pos = sum(1 for v in yrs.values() if v > 0)
    print(f"{lab:<40} {len(t):>5} {t.win.mean()*100:>6.1f} {t.net.sum()/t.margin.sum()*100:>+8.1f} "
          f"{t.net.sum()/t.w.sum()*100:>+7.1f} {pos}/{len(yrs):>4}  "
          + "  ".join(f"{y}:{v:+.0f}%" for y, v in sorted(yrs.items())))
print("DONE-LOWCW-OOS2")
