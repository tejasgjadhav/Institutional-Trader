"""HOURLY first-touch c/w>=0.40 entry vs CLOSE-based entry — stock credit fade books v2 UNION & v1.
VALIDATION ONLY (paper) — does NOT touch the live engine.

Two entry rules on the SAME breakout universe + SAME strikes + SAME gate (c/w>=0.40 & prem>=50):
  CLOSE  (= deployed): evaluate c/w at the breakout-day CLOSE (~15:10); enter if >=0.40.
  HOURLY first-touch : step hourly through the breakout day's intraday option premiums; enter at the
                       FIRST hour c/w first touches >=0.40 (& short prem>=50). If none, fall back to the
                       CLOSE mark -> so HOURLY signals are a strict SUPERSET of CLOSE signals.

Both share: strikes fixed off the breakout-day close ATM (the engine geometry), and the identical
forward DAILY-close exit walk (TP / stop / intrinsic-at-expiry). Only the ENTRY premium/credit and
whether the gate fires differ. The HOURLY position is exposed to the breakout-day close as its first
mark (it is genuinely live intraday), so a spike that reverts by close shows up as an adverse first bar.

FLIP-SIDE metric: of HOURLY intraday entries, the fraction that are "reverting spikes" (c/w back <0.40
by that day's CLOSE — i.e. trades the CLOSE rule SKIPS) and how those specifically perform vs the ones
that held (c/w still >=0.40 at close).

FETCH BOUND (documented, conservative): intraday 1-min is fetched only for breakouts whose daily-CLOSE
c/w >= 0.30 & short prem >= 40 (a band around the 0.40 gate). A breakout that first-touches >=0.40
intraday yet closes with c/w < 0.30 would need a >0.10-of-width intraday c/w spike that fully reverts —
rare, and if it exists it is an even LOWER-quality reverting spike, so excluding it biases the result
TOWARD hourly (against the noise hypothesis). Flagged in the writeup.

Two configs:
  v2 UNION: short 2-OTM, width 4, TP 50% of credit, stop 3x, UNION Donchian(5,10,15,20)==D5, minDTE10, reentry3d.
  v1:       short 1-OTM, width 3, TP 75% of credit, stop 2x, Donchian 10,                      minDTE10, reentry3d.
Costs 2.5% slippage per leg + Rs20x4/lot. Settle intrinsic at expiry. Universe = engine.config.UNIVERSE.

Real Upstox expired-instrument premiums Oct'24->date (the only era with intraday option data). Single
regime -> report n, per-year, flag small subsets as noise.

Resumable + cached + checkpointed. Out: /tmp/hvc/hvc_results.json (per-breakout records; report by hvc_report.py).
"""
import sys, os, json, time, warnings, threading, concurrent.futures
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import datetime, timedelta, date
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical, SESSION, UPSTOX_BASE
from engine.instruments import encode_key
from engine.expired_options import get_expiries, get_contracts, _get_json as _gj

START = date(2024, 10, 1); MIN_DTE = 10; REENTRY = 3
MIN_CW = 0.40; MIN_PREM = 50.0
INTRA_CW_BAND = 0.30; INTRA_PREM_BAND = 40.0        # fetch intraday only near the gate (see header)
SLIP_PCT = 2.5; BROKER = 20.0                       # matches reference sims: spf() + Rs20x4/lot
HOUR_MARKS = ["09:15", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00"]

CONFIGS = {
    "v2_union": dict(dcs=(5, 10, 15, 20), short=2, width=4, tp=0.50, stop=3.0),
    "v1":       dict(dcs=(10,),           short=1, width=3, tp=0.75, stop=2.0),
}

CDIR = "/tmp/hvc"; os.makedirs(f"{CDIR}/daily", exist_ok=True)
os.makedirs(f"{CDIR}/intra", exist_ok=True); os.makedirs(f"{CDIR}/under", exist_ok=True)
RESF = f"{CDIR}/hvc_results.json"

def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0

# ---- fetch helpers (cached on disk; retries/backoff) ----
def under(sym0):
    sym = sym0.replace(".NS", ""); cf = f"{CDIR}/under/{sym}.json"
    if os.path.exists(cf):
        try:
            d = json.load(open(cf))
            if d: return pd.DataFrame(d["rows"], columns=["date", "H", "L", "C"])
            return None
        except Exception: pass
    u = fetch_upstox_historical(sym0, unit="days", interval=1, from_date="2024-06-01", to_date=date.today().isoformat())
    if u is None or u.empty or len(u) < 30:
        json.dump({}, open(cf, "w")); return None
    u = u.sort_index()
    rows = [[ix.date().isoformat(), float(u["High"].loc[ix]), float(u["Low"].loc[ix]), float(u["Close"].loc[ix])] for ix in u.index]
    json.dump({"rows": rows}, open(cf, "w"))
    return pd.DataFrame(rows, columns=["date", "H", "L", "C"])

def leg_daily(key, d0, to):
    """DAILY close series for one option instrument, breakout day..to. Cached. Returns list[float] closes."""
    cf = f"{CDIR}/daily/{key.replace('|','_')}_{d0}_{to}.json"
    if os.path.exists(cf):
        v = json.load(open(cf)); return v if v else None
    url = f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}"
    for a in range(6):
        try:
            j = _gj(url)
            if j.get("status") == "success":
                c = j.get("data", {}).get("candles", [])
                if c:
                    df = pd.DataFrame(c, columns=["ts", "O", "H", "L", "C", "V", "OI"])
                    df["ts"] = pd.to_datetime(df["ts"])
                    closes = [float(x) for x in df.set_index("ts").sort_index()["C"].tolist()]
                    json.dump(closes, open(cf, "w")); return closes
                json.dump([], open(cf, "w")); return None
        except Exception: pass
        time.sleep(min(2 + a * 2, 10))
    return None

def leg_intra(key, day, tries=5):
    """1-min candles for one option instrument on `day`. Caches even EMPTY (far wings never trade)."""
    cf = f"{CDIR}/intra/{key.replace('|','_')}_{day}.json"
    if os.path.exists(cf):
        v = json.load(open(cf)); return v or None
    url = f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/1minute/{day}/{day}"
    for a in range(tries):
        try:
            r = SESSION.get(url, timeout=20)
            if r.status_code == 200 and r.json().get("status") == "success":
                cs = sorted(r.json()["data"].get("candles", []), key=lambda c: c[0])
                json.dump(cs, open(cf, "w")); return cs or None
        except Exception: pass
        time.sleep(min(2 + a * 2, 10))
    return None

def _mins_ts(ts): return int(ts[11:13]) * 60 + int(ts[14:16])   # full ISO timestamp -> min-of-day
def _mins_hm(hm): return int(hm[:2]) * 60 + int(hm[3:5])         # bare "HH:MM" mark -> min-of-day
def bar_at(bars, mark):
    """close of the first 1-min bar at/after `mark` (within 15 min). mark is 'HH:MM'."""
    m = _mins_hm(mark)
    for c in bars:
        cm = _mins_ts(c[0])
        if cm >= m: return (float(c[4]), c[0]) if cm <= m + 15 else (None, None)
    return None, None
def wing_at(bars, ts):
    """close of the last long-wing 1-min bar at/before ts."""
    last = None
    for c in bars:
        if c[0] <= ts: last = c
        else: break
    return float(last[4]) if last else None

# ---- exit walk (shared) ----
def walk(sp, lp, credit, start_idx, w, tp, stop, espot, sk, lk, typ, se, le):
    """Forward daily-close exit from start_idx; TP/stop else intrinsic at expiry. Returns net (pts)."""
    close = None; m = min(len(sp), len(lp))
    for t in range(start_idx, m):
        a = sp[t]; b = lp[t]; cost = a - b
        if cost <= credit * (1 - tp): close = max(cost, 0.0) + (a * spf(a) + b * spf(b)) / 100.0; break
        if cost >= credit * stop: close = min(cost, w) + (a * spf(a) + b * spf(b)) / 100.0; break
    if close is None:
        intr = max(0.0, espot - sk) if typ == "CE" else max(0.0, sk - espot)
        intl = max(0.0, espot - lk) if typ == "CE" else max(0.0, lk - espot)
        close = min(max(intr - intl, 0.0), w)
    return (credit - close) - (se * spf(se) + le * spf(le)) / 100.0

EXPC = {}; CHC = {}; LK = threading.Lock()

def breakouts(u, dcs):
    """UNION-Donchian breakouts (first window that crosses wins), with per-side reentry gap.
    For v1 dcs=(10,) this reduces to a single Donchian-10 stream. Yields (day:date, typ, close)."""
    highs = {dc: u["H"].rolling(dc).max().shift(1) for dc in dcs}
    lows = {dc: u["L"].rolling(dc).min().shift(1) for dc in dcs}
    last = {}
    for i in range(max(dcs) + 1, len(u) - 1):
        day = date.fromisoformat(u["date"].iloc[i])
        if day < START: continue
        c = float(u["C"].iloc[i]); typ = None
        for dc in dcs:
            if c > float(highs[dc].iloc[i]): typ = "CE"; break
            if c < float(lows[dc].iloc[i]): typ = "PE"; break
        if typ is None: continue
        if last.get(typ) and (day - last[typ]).days < REENTRY: continue
        last[typ] = day
        yield day, typ, c

def eval_breakout(sym, cb, day, typ, c, cfg):
    """Return a per-breakout record with CLOSE + HOURLY outcomes, or None if no structure / no fire either rule."""
    SHORT, WIDTH, TP, STOP = cfg["short"], cfg["width"], cfg["tp"], cfg["stop"]
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
    sct, lct = chain[si], chain[li]; sk, lk = ks[si], ks[li]; w = abs(sk - lk)
    to = min(datetime.fromisoformat(exp).date(), day + timedelta(days=45)).isoformat()
    sp = leg_daily(sct["instrument_key"], day.isoformat(), to)
    lp = leg_daily(lct["instrument_key"], day.isoformat(), to)
    if sp is None or lp is None or len(sp) < 1 or len(lp) < 1: return None
    se_c = sp[0]; le_c = lp[0]; credit_c = se_c - le_c
    if credit_c <= 0 or credit_c >= w: return None
    cw_c = credit_c / w
    espot = cb.get(exp) or (cb[max(x for x in cb if x < exp)] if any(x < exp for x in cb) else c)

    rec = dict(sym=sym, y=day.year, day=day.isoformat(), typ=typ, w=float(w),
               cw_close=round(cw_c, 4), se_close=round(se_c, 2))

    # CLOSE rule
    if se_c >= MIN_PREM and cw_c >= MIN_CW:
        net = walk(sp, lp, credit_c, 1, w, TP, STOP, espot, sk, lk, typ, se_c, le_c)
        rec["close_fired"] = 1; rec["close_net"] = round(net, 3); rec["close_win"] = int(net > 0)
    else:
        rec["close_fired"] = 0

    # HOURLY first-touch — only fetch intraday when the close c/w is near the gate (documented bound)
    entry_hour = None; se_h = le_h = credit_h = cw_h = None
    rec["intra_fetched"] = 0; rec["short_intra_bars"] = 0; rec["long_intra_bars"] = 0
    if cw_c >= INTRA_CW_BAND and se_c >= INTRA_PREM_BAND:
        bs = leg_intra(sct["instrument_key"], day.isoformat())
        bl = leg_intra(lct["instrument_key"], day.isoformat())
        rec["intra_fetched"] = 1
        rec["short_intra_bars"] = len(bs) if bs else 0
        rec["long_intra_bars"] = len(bl) if bl else 0
        if bs:
            for mk in HOUR_MARKS:
                sprem, sts = bar_at(bs, mk)
                if sprem is None or sprem < MIN_PREM: continue
                lprem = wing_at(bl, sts) if bl else None
                if lprem is None:
                    lp2, _ = bar_at(bl, mk) if bl else (None, None)
                    lprem = lp2
                if lprem is None: continue
                cr = sprem - lprem
                if cr <= 0 or cr >= w: continue
                if cr / w >= MIN_CW:
                    entry_hour = mk; se_h = sprem; le_h = lprem; credit_h = cr; cw_h = cr / w
                    break
    if entry_hour is not None:
        # intraday first-touch fired; exit walk starts at the breakout-day CLOSE (bar 0) since the
        # position is genuinely live intraday and exposed to that day's close.
        net = walk(sp, lp, credit_h, 0, w, TP, STOP, espot, sk, lk, typ, se_h, le_h)
        rec["hourly_fired"] = 1; rec["hourly_net"] = round(net, 3); rec["hourly_win"] = int(net > 0)
        rec["entry_hour"] = entry_hour; rec["cw_entry"] = round(cw_h, 4)
        rec["reverting"] = int(cw_c < MIN_CW)          # first-touched >=0.40 intraday but back <0.40 by close
    elif rec["close_fired"]:
        # no earlier intraday touch -> HOURLY == CLOSE (fires at the close mark; superset property)
        rec["hourly_fired"] = 1; rec["hourly_net"] = rec["close_net"]; rec["hourly_win"] = rec["close_win"]
        rec["entry_hour"] = "close"; rec["cw_entry"] = round(cw_c, 4); rec["reverting"] = 0
    else:
        rec["hourly_fired"] = 0

    if rec["close_fired"] or rec["hourly_fired"]:
        return rec
    return None

# ---- driver ----
def load_res():
    if os.path.exists(RESF):
        try: return json.load(open(RESF))
        except Exception: pass
    return {"v2_union": {}, "v1": {}, "_done": []}

RES = load_res(); DONE = [len(RES["_done"])]

def do_stock(sym0):
    sym = sym0.replace(".NS", "")
    with LK:
        if sym in RES["_done"]: return
    try:
        u = under(sym0)
        if u is None:
            with LK:
                RES["_done"].append(sym); DONE[0] += 1
            return
        cb = {r["date"]: float(r["C"]) for _, r in u.iterrows()}
        recs = {"v2_union": [], "v1": []}
        for cname, cfg in CONFIGS.items():
            for day, typ, c in breakouts(u, cfg["dcs"]):
                try:
                    r = eval_breakout(sym, cb, day, typ, c, cfg)
                except Exception:
                    r = None
                if r: recs[cname].append(r)
        with LK:
            RES["v2_union"][sym] = recs["v2_union"]; RES["v1"][sym] = recs["v1"]
            RES["_done"].append(sym); DONE[0] += 1
            if DONE[0] % 3 == 0:
                json.dump(RES, open(RESF, "w"))
                nv2 = sum(len(v) for v in RES["v2_union"].values()); nv1 = sum(len(v) for v in RES["v1"].values())
                print(f"  ...{DONE[0]}/{len(UNIVERSE)} stocks | v2 recs={nv2} v1 recs={nv1}", flush=True)
    except Exception as e:
        with LK:
            RES["_done"].append(sym); DONE[0] += 1
            print(f"  !! {sym}: {e}", flush=True)

def main():
    print(f"HVC backtest start | already done: {len(RES['_done'])}/{len(UNIVERSE)}", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(do_stock, UNIVERSE))
    json.dump(RES, open(RESF, "w"))
    nv2 = sum(len(v) for v in RES["v2_union"].values()); nv1 = sum(len(v) for v in RES["v1"].values())
    print(f"DONE-HVC | stocks={len(RES['_done'])} v2 recs={nv2} v1 recs={nv1}", flush=True)

if __name__ == "__main__":
    main()
