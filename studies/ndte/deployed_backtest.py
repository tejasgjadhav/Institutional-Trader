"""PRODUCTION BACKTEST of the three DEPLOYED stock-credit books, IS and OOS, date-aligned.

Written 14-Aug-2026 after the leg-misalignment incident, to the standing rule that research
scripts are production code. This is the single harness of record for the deployed configs:

    v2  c/w >= 0.40    short 2-OTM width 4   TP-50   stop 3x credit
    v1  c/w >= 0.40    short 1-OTM width 3   TP-40   no stop
    v0  c/w 0.35-0.40  short 2-OTM width 4   TP-40   no stop

Engine rules modelled: premium >= 50 on the short, >= 10 DTE nearest expiry, the CROSS-BOOK
3-day re-entry gap (any book's entry blocks the symbol for all books), v1 scanning DONCHIAN-10
ONLY while v2/v0 scan the union D5/10/15/20 (STOCK_CREDIT_DONCHIAN=10 vs UNION_DCS — found by
the 15-Aug harness audit), v1 DEFERRING while v2 holds the name (stock_credit.py:221, tracked to
v2's actual exit date), and v1 winning a same-day same-stock clash against v0. Exit costs are charged on TP/stop closes (spf both legs); expiry
settlement is intrinsic, capped at width, no exit cost. NOT modelled (say so, never imply
otherwise): the live bid-ask/OI quote gate, the 5-per-day and 20-open caps, and fills at the
15:36-15:40 window rather than the close print.

Date alignment: IS pivots bhavcopy by day, so leg prices index by calendar day; OOS keys every
leg {date: close} and a trade exists only if BOTH legs have a candle on entry day. The
positional-join pattern is banned (CLAUDE.md, studies/DEPLOYED_EVIDENCE_AUDIT.md).

Run:  .venv/bin/python studies/ndte/deployed_backtest.py IS|OOS
"""
import sys, json, pickle, warnings, threading, collections
import concurrent.futures as cf
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd, numpy as np
from datetime import date, datetime, timedelta
from engine.config import UNIVERSE

WINDOW = sys.argv[1] if len(sys.argv) > 1 else "OOS"
MIN_DTE, REENTRY, MIN_PREM = 10, 3, 50.0
BOOKS = {"v2": dict(S=2, W=4, tp=0.50, stop=3.0, band=(0.40, 99.0)),
         "v1": dict(S=1, W=3, tp=0.40, stop=None, band=(0.40, 99.0)),
         "v0": dict(S=2, W=4, tp=0.40, stop=None, band=(0.35, 0.40))}
spf = lambda p: min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0
OUT = f"/tmp/deployed_bt_{WINDOW.lower()}_rows.json"

def settle(cb, exp, ks, si, li, typ, width, fallback_spot):
    es = cb.get(exp) or (cb[max(x for x in cb if x <= exp)] if any(x <= exp for x in cb) else fallback_spot)
    iS = max(0.0, es - ks[si]) if typ == "CE" else max(0.0, ks[si] - es)
    iL = max(0.0, es - ks[li]) if typ == "CE" else max(0.0, ks[li] - es)
    return min(max(iS - iL, 0.0), width)

def eval_books(day, sym, typ, ks, atm, px_short_long, cb, exp, spot, d10_hit, rows):
    """walk yields (walk_day, se, le) after entry, same-day pairs only. Applies the live hierarchy:
    v2 first; v1 only on a D10 breakout and only if v2 neither fires today nor holds the name
    (v2_hold_until, keyed by walk exit); v0 only if v1 did not fire. Returns (fired_any,
    v2_exit_day|None)."""
    fired = {}
    for bk, cfg in BOOKS.items():
        if bk == "v1" and not d10_hit: continue
        si = atm + cfg["S"] if typ == "CE" else atm - cfg["S"]
        li = si + cfg["W"] if typ == "CE" else si - cfg["W"]
        if not (0 <= si < len(ks) and 0 <= li < len(ks)): continue
        got = px_short_long(si, li)
        if got is None: continue
        se, le, walk = got
        if se < MIN_PREM: continue
        credit = se - le; width = abs(ks[si] - ks[li])
        if credit <= 0 or credit >= width: continue
        cw = credit / width
        if not (cfg["band"][0] <= cw < cfg["band"][1]): continue
        fired[bk] = (si, li, se, le, credit, width, cw, walk)
    if "v2" in fired and "v1" in fired:      # engine rule: v1 defers while v2 holds the name
        del fired["v1"]
    if "v1" in fired and "v0" in fired:      # engine rule: v1 wins the same-stock clash
        del fired["v0"]
    if not fired: return False, None
    v2_exit = None
    for bk, (si, li, se, le, credit, width, cw, walk) in fired.items():
        cfg = BOOKS[bk]; close = None; xc = 0.0; exit_day = exp
        for (wd, s2, l2) in walk:
            cost = s2 - l2
            if cost <= credit * (1 - cfg["tp"]):
                close = max(cost, 0.0); xc = (s2*spf(s2) + l2*spf(l2))/100.0; exit_day = wd; break
            if cfg["stop"] and cost >= credit * cfg["stop"] and cost <= width * 1.05:
                close = min(cost, width); xc = (s2*spf(s2) + l2*spf(l2))/100.0; exit_day = wd; break
        if close is None:
            close = settle(cb, exp, ks, si, li, typ, width, spot)
        if bk == "v2": v2_exit = exit_day
        net = (credit - close) - (se*spf(se) + le*spf(le))/100.0 - xc
        rows.append(dict(book=bk, sym=sym, day=day, yr=int(day[:4]), cw=round(cw, 3),
                         net=round(net, 2), margin=round(width - credit, 2), win=int(net > 0)))
    return True, v2_exit

def breakout_days(u):
    """Yields (day, close, typ, d10_hit): typ from the UNION (v2/v0's scanner); d10_hit True when
    the DC-10 band alone triggers with the SAME direction — live v1's scanner."""
    days = [str(i)[:10] for i in u.index]
    cl, hi, lo = u["Close"].values, u["High"].values, u["Low"].values
    for i in range(20, len(u) - 1):
        c = float(cl[i]); typ = None
        for dc in (5, 10, 15, 20):
            if c > float(hi[i-dc:i].max()): typ = "CE"; break
            if c < float(lo[i-dc:i].min()): typ = "PE"; break
        if not typ: continue
        d10 = "CE" if c > float(hi[i-10:i].max()) else ("PE" if c < float(lo[i-10:i].min()) else None)
        yield days[i], c, typ, (d10 == typ)

# ---------------- IS: bhavcopy pickle ----------------
def run_is():
    from engine.data_fetcher import fetch_upstox_historical
    frames = pickle.load(open("/tmp/bhav_optstk.pkl", "rb"))
    big = []
    for d, df in frames:
        df = df.copy(); df["DAY"] = d; big.append(df)
    big = pd.concat(big, ignore_index=True); big.columns = [c.strip() for c in big.columns]
    big["EXP"] = pd.to_datetime(big["EXPIRY_DT"], format="mixed", dayfirst=True).dt.date.astype(str)
    for col in ("STRIKE_PR", "CLOSE"): big[col] = big[col].astype(float)
    big["OPTION_TYP"] = big["OPTION_TYP"].astype(str).str.strip()
    big["SYMBOL"] = big["SYMBOL"].astype(str).str.strip()
    PX = {}
    for k, sub in big.groupby(["SYMBOL", "EXP", "OPTION_TYP"], observed=True):
        c = sub.pivot_table(index="DAY", columns="STRIKE_PR", values="CLOSE", aggfunc="last")
        PX[(str(k[0]), str(k[1]), str(k[2]))] = dict(
            ks=np.asarray(c.columns, dtype="float64"),
            didx={str(d): i for i, d in enumerate(c.index)}, C=c.values.astype("float32"))
    del big
    exps_by = collections.defaultdict(set)
    for (s, e, t) in PX: exps_by[(s, t)].add(e)
    rows = []
    for n, tk in enumerate(UNIVERSE):
        sym = tk.replace(".NS", "")
        if not any(k[0] == sym for k in PX): continue
        try:
            u = fetch_upstox_historical(tk, unit="days", interval=1,
                                        from_date="2018-11-01", to_date="2024-10-01")
        except Exception: continue
        if u is None or u.empty or len(u) < 30: continue
        u = u.sort_index()
        cb = {str(i)[:10]: float(u["Close"].loc[i]) for i in u.index}
        last_entry = None; v2_hold_until = None
        for d, c, typ, d10_hit in breakout_days(u):
            dd = date.fromisoformat(d)
            if last_entry and (dd - last_entry).days < REENTRY: continue   # CROSS-BOOK gap
            if v2_hold_until and d <= v2_hold_until: d10_hit = False       # v1 defers to open v2
            fut = sorted(e for e in exps_by.get((sym, typ), ())
                         if date.fromisoformat(e) >= dd + timedelta(days=MIN_DTE))
            if not fut: continue
            exp = fut[0]; P = PX.get((sym, exp, typ))
            if not P or d not in P["didx"]: continue
            di = P["didx"][d]; ks = P["ks"]
            atm = int(np.argmin(np.abs(ks - c)))
            wdays = list(P["didx"].keys())
            def px(si, li, P=P, di=di, wdays=wdays):
                se, le = float(P["C"][di, si]), float(P["C"][di, li])
                if not (np.isfinite(se) and np.isfinite(le)): return None
                walk = [(wdays[di+1+t], float(a), float(b)) for t, (a, b) in
                        enumerate(zip(P["C"][di+1:, si], P["C"][di+1:, li]))
                        if np.isfinite(a) and np.isfinite(b)]
                return se, le, walk
            ok, v2x = eval_books(d, sym, typ, ks, atm, px, cb, exp, c, d10_hit, rows)
            if ok:
                last_entry = dd
                if v2x: v2_hold_until = max(v2_hold_until or v2x, v2x)
        if n % 15 == 0: print(f"  IS {n}/{len(UNIVERSE)} · {len(rows)} trades", flush=True)
    return rows

# ---------------- OOS: Upstox expired options, date-keyed ----------------
CACHE = "/tmp/cw_band_legcache_dated.json"
try: LEGC = json.load(open(CACHE))
except Exception: LEGC = {}
LK = threading.Lock()

def leg(key, d0, to):
    from engine.data_fetcher import UPSTOX_BASE
    from engine.instruments import encode_key
    from engine.expired_options import _get_json as _gj
    ck = f"{key}|{d0}|{to}"
    with LK:
        if ck in LEGC: return LEGC[ck]
    j = _gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}")
    out = {}
    if j.get("status") == "success":
        for c in j.get("data", {}).get("candles", []) or []:
            out[str(c[0])[:10]] = float(c[4])
    if out:                                   # never cache an empty (network-poisoned) result
        with LK: LEGC[ck] = out
    return out

def run_oos():
    from engine.data_fetcher import fetch_upstox_historical
    from engine.expired_options import get_expiries, get_contracts
    START = date(2024, 10, 1)
    rows = []; done = [0]
    def work(tk):
        sym = tk.replace(".NS", "")
        try:
            u = fetch_upstox_historical(tk, unit="days", interval=1,
                                        from_date="2024-06-01", to_date=date.today().isoformat())
        except Exception: u = None
        if u is None or u.empty or len(u) < 30:
            with LK: done[0] += 1
            return
        u = u.sort_index()
        cb = {str(i)[:10]: float(u["Close"].loc[i]) for i in u.index}
        mine = []; last_entry = None; v2_hold_until = None
        for d, c, typ, d10_hit in breakout_days(u):
            dd = date.fromisoformat(d)
            if dd < START: continue
            if last_entry and (dd - last_entry).days < REENTRY: continue
            if v2_hold_until and d <= v2_hold_until: d10_hit = False       # v1 defers to open v2
            try:
                exps = [e for e in get_expiries(sym) if e >= (dd + timedelta(days=MIN_DTE)).isoformat()]
                if not exps: continue
                exp = exps[0]
                chain = sorted([x for x in get_contracts(sym, exp) if x["instrument_type"] == typ],
                               key=lambda x: float(x["strike_price"]))
            except Exception: continue
            if len(chain) < 12: continue
            ks = [float(x["strike_price"]) for x in chain]
            atm = min(range(len(ks)), key=lambda j: abs(ks[j] - c))
            to = min(datetime.fromisoformat(exp).date(), dd + timedelta(days=45)).isoformat()
            def px(si, li, chain=chain, d=d, to=to):
                sp = leg(chain[si]["instrument_key"], d, to)
                lp = leg(chain[li]["instrument_key"], d, to)
                if d not in sp or d not in lp: return None       # both legs must trade on entry day
                both = sorted(set(sp) & set(lp))
                walk = [(x, sp[x], lp[x]) for x in both if x > d]
                return sp[d], lp[d], walk
            ok, v2x = eval_books(d, sym, typ, ks, atm, px, cb, exp, c, d10_hit, mine)
            if ok:
                last_entry = dd
                if v2x: v2_hold_until = max(v2_hold_until or v2x, v2x)
        with LK:
            rows.extend(mine); done[0] += 1
            if done[0] % 5 == 0:
                print(f"  OOS {done[0]}/{len(UNIVERSE)} · {len(rows)} trades", flush=True)
                json.dump(LEGC, open(CACHE, "w"))
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(work, UNIVERSE))
    json.dump(LEGC, open(CACHE, "w"))
    return rows

rows = run_is() if WINDOW == "IS" else run_oos()
json.dump(rows, open(OUT, "w"))
lbl = "IS 2019->Sep-2024 (bhavcopy)" if WINDOW == "IS" else "OOS Oct-2024->date (Upstox, date-aligned)"
print(f"\n=== DEPLOYED CONFIGS · {lbl} · full universe · cross-book gap + v1-clash rule · exit costs charged ===")
print(f"{'book':<5}{'band':<12}{'n':>6}{'WIN':>8}{'ROM':>9}{'avg/tr':>9}{'+ve yrs':>9}")
for bk, cfg in BOOKS.items():
    s = [x for x in rows if x["book"] == bk]
    if not s: print(f"{bk:<5}  (none)"); continue
    by = collections.defaultdict(list)
    for x in s: by[x["yr"]].append(x["net"])
    pos = sum(1 for v in by.values() if sum(v) > 0)
    band = f"{cfg['band'][0]}-{cfg['band'][1] if cfg['band'][1]<90 else ''}"
    print(f"{bk:<5}{band:<12}{len(s):>6}{sum(x['win'] for x in s)/len(s)*100:>7.1f}%"
          f"{sum(x['net'] for x in s)/sum(x['margin'] for x in s)*100:>+8.1f}%"
          f"{sum(x['net'] for x in s)/len(s):>+9.2f}{pos:>6}/{len(by)}")
print(f"DONE-{WINDOW}")
