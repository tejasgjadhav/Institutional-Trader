"""PRODUCTION BACKTEST of the three DEPLOYED stock-credit books, IS and OOS, date-aligned.

Written 14-Aug-2026 after the leg-misalignment incident, to the standing rule that research
scripts are production code. This is the single harness of record for the deployed configs:

    v2  c/w >= 0.40    short 2-OTM width 4   TP-50   NO STOP
        (live config.STOCK_CREDIT_STOP_MULT = 99.0. A stop set as a multiple of the credit is
        UNREACHABLE above c/w 1/3: at c/w 0.40 a 3x-credit stop sits at 1.2x the width, and a
        vertical can never cost more than its width because the bought wing caps it. Full loss
        arrives at 1.0x width, i.e. 2.5x credit, long before any 3x trigger. The harness carried
        stop=3.0 while live carried 99.0 — numerically identical, since neither can fire, but the
        harness now mirrors live. User caught this on 17-Aug-2026.)
    v1  c/w >= 0.40    short 1-OTM width 3   TP-40   no stop
    v0  c/w 0.35-0.40  short 2-OTM width 4   TP-40   no stop

Engine rules modelled: the ONE-OPEN-POSITION-PER-SYMBOL rule (each book skips a name it already
holds open until that position closes - stock_credit.py:223, stock_credit_v2.py:372; added
16-Aug-2026 after an audit found 59% of IS trades and 31% of OOS trades were same-book re-entries
inside 35 days, which live could never have taken), premium >= 50 on the short, >= 10 DTE nearest
expiry, the CROSS-BOOK
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
# OPEN-INTEREST FLOOR (added 16-Aug-2026 — the audit's BLOCKER finding, matching the live gate).
# Bhavcopy publishes a CLOSE for every listed contract, and for one that never traded that CLOSE is
# NSE's THEORETICAL SETTLEMENT price, not a print. Measured on the strikes this harness actually
# sells: 24% of 1-OTM shorts and 30% of 2-OTM shorts had OPEN_INT == 0. The live engine refuses
# OI < 100 (`stock_credit_v2.py:411`), and out-of-sample cannot include such contracts at all
# because an Upstox expired candle exists only if the contract traded. Selling and buying back at a
# model mark harvests theta with no friction and no gap risk, which is the most likely single cause
# of the in-sample +30.7% against the out-of-sample +3.7%. Both legs must clear this on entry day.
MIN_OI = 1            # open interest must EXIST — mirrors config.STOCK_CREDIT_MIN_OI
# The floor MIRRORS LIVE (config.STOCK_CREDIT_MIN_OI = 1): the contract must have open interest at
# all. It is a fidelity rule, not an edge filter — an exchange CLOSE on a contract that never traded
# is a theoretical settlement price, not a fillable quote, and pricing off those halved the in-sample
# ROM when it was fixed. Bucketing by OI found no link between open interest and returns, so no lot
# multiple is justified; see engine/config.py for the numbers.
try:
    LOTMAP = json.load(open("research/lotmap.json"))
except Exception:
    LOTMAP = {}
# CORPORATE-ACTION SCALE FIX (15-Aug-2026, user-caught, audit-root-caused, then fixed properly).
# THE DEFECT: `fetch_upstox_historical` returns split/bonus-ADJUSTED closes, while bhavcopy
# STRIKE_PR and Upstox expired-contract strikes are the UNADJUSTED as-listed strikes of that date.
# On any name with a later split or bonus the two scales diverge, so `argmin(abs(ks - close))`
# picked legs that were DEEP IN THE MONEY in real terms: credit approached width, margin approached
# zero, and settling against the same adjusted price booked a guaranteed full-credit win. It
# returned +182.8% ROM and a 1.92:1 win:loss, both impossible for a defined-risk vertical.
# TWO HEURISTIC GUARDS WERE TRIED AND BOTH FAILED: rejecting on ATM-strike drift from the close
# (median c/w 0.78 -> 0.56) and additionally rejecting an ATM at the ladder edge (-> 0.54). Neither
# reached the 0.44-0.49 that names without corporate actions show, so both were removed.
# THE FIX: never ask the equity series where spot is. Ask the option chain. At the strike where the
# call and the put cost the same, that strike IS the forward, and put-call parity gives the level
# exactly: S = K + C - P. Both prices come from the same file, on the same date, on the same
# unadjusted scale as the strikes, so a split cannot desynchronise them. The adjusted equity series
# is still used for the Donchian breakout, where it is correct - a split-adjusted series is
# internally consistent, and the breakout only compares it against itself.
PARITY_MAX_SPAN = 0.02      # accept the parity anchor only if CE and PE agree within 2% of spot
# OOS CANNOT USE PARITY. Upstox expired-option candles exist only for strikes that traded that day,
# so demanding a call AND a put on the same strike on the entry day destroyed the sample: the first
# parity OOS run returned 0 trades for v2 and 9 for v1, against 96 and 268 before. Bhavcopy carries
# every listed strike, so IS keeps parity. OOS falls back to the two structural guards below, which
# need no extra data. They are weaker than parity - they caught the median c/w down to 0.54, not
# 0.47 - so the OOS headline is reported on the MEDIAN COHORT (c/w 0.40-0.50) where the residual
# contamination cannot reach. OOS contamination is milder anyway: its naive median c/w was already
# 0.45 against 0.78 in-sample, because the 2024-2026 window contains far fewer corporate actions.
ATM_MAX_DRIFT      = 0.05   # nearest strike must sit within 5% of the close
ATM_MIN_LADDER_POS = 0.15   # ATM must sit mid-ladder, not at its edge
BOOKS = {"v2": dict(S=2, W=4, tp=0.50, stop=None, band=(0.40, 99.0)),
         "v1": dict(S=1, W=3, tp=0.40, stop=None, band=(0.40, 99.0)),
         "v0": dict(S=2, W=4, tp=0.40, stop=None, band=(0.35, 0.40))}
spf = lambda p: min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0
OUT = f"research/deployed_bt_{WINDOW.lower()}_rows.json"

def parity_spot(ce_px, pe_px):
    """Implied spot from the chain itself: at the strike where |CE - PE| is smallest, S = K + C - P.

    ce_px / pe_px are {strike: close} for ONE symbol, expiry and date. Returns None when the two
    sides do not overlap or the anchor is too wide to trust. Immune to splits and bonuses, because
    both quotes and the strikes carry the same as-listed scale.
    """
    common = [k for k in ce_px if k in pe_px]
    if len(common) < 3:
        return None
    k = min(common, key=lambda x: abs(ce_px[x] - pe_px[x]))
    spot = k + ce_px[k] - pe_px[k]
    if spot <= 0 or abs(ce_px[k] - pe_px[k]) / spot > PARITY_MAX_SPAN:
        return None
    return spot

SETTLE_FALLBACKS = collections.Counter()
FETCHFAIL = collections.Counter()   # signals dropped because Upstox would not answer
_CNT_LK = threading.Lock()          # run_oos increments these from four worker threads

def settle(cb, exp, ks, si, li, typ, width, fallback_spot):
    """LAST RESORT only — used when a leg stopped trading before expiry, so the expiry-day option
    prices do not exist. Derives intrinsic from an underlying price, which is the path that can
    disagree with the strike scale on a split or bonus name. Counted so the report can state how
    often it ran instead of hiding it."""
    with _CNT_LK: SETTLE_FALLBACKS["used"] += 1
    es = cb.get(exp) or (cb[max(x for x in cb if x <= exp)] if any(x <= exp for x in cb) else fallback_spot)
    iS = max(0.0, es - ks[si]) if typ == "CE" else max(0.0, ks[si] - es)
    iL = max(0.0, es - ks[li]) if typ == "CE" else max(0.0, ks[li] - es)
    return min(max(iS - iL, 0.0), width)

def eval_books(day, sym, typ, ks, atm, px_short_long, cb, exp, spot, d10_hit, rows, open_until):
    """walk yields (walk_day, se, le) after entry, same-day pairs only. Applies the live hierarchy:
    v2 first; v1 only on a D10 breakout and only if v2 neither fires today nor holds the name; v0
    only if v1 did not fire. `open_until` is {book: exit_day} for THIS symbol - a book holding an
    open position in a name cannot re-enter it, which is what the live engine does. Returns
    (fired_any, {book: exit_day})."""
    fired = {}
    for bk, cfg in BOOKS.items():
        if bk == "v1" and not d10_hit: continue
        if open_until.get(bk) and day <= open_until[bk]: continue      # this book still holds it
        if bk == "v1" and open_until.get("v2") and day <= open_until["v2"]: continue  # defers to v2
        si = atm + cfg["S"] if typ == "CE" else atm - cfg["S"]
        li = si + cfg["W"] if typ == "CE" else si - cfg["W"]
        if not (0 <= si < len(ks) and 0 <= li < len(ks)): continue
        got = px_short_long(si, li)
        if got is None: continue
        se, le, walk = got[0], got[1], got[2]
        oi = got[3] if len(got) > 3 else None      # (oi_short, oi_long), IS only
        if se < MIN_PREM: continue
        _floor = MIN_OI
        if oi is not None and (oi[0] < _floor or oi[1] < _floor): continue
        credit = se - le; width = abs(ks[si] - ks[li])
        if credit <= 0 or credit >= width: continue
        cw = credit / width
        if not (cfg["band"][0] <= cw < cfg["band"][1]): continue
        fired[bk] = (si, li, se, le, credit, width, cw, walk, oi)
    if "v2" in fired and "v1" in fired:      # same-day: v1 defers to v2
        del fired["v1"]
    if "v1" in fired and "v0" in fired:      # engine rule: v1 wins the same-stock clash
        del fired["v0"]
    if not fired: return False, {}
    exits = {}
    for bk, (si, li, se, le, credit, width, cw, walk, oi) in fired.items():
        cfg = BOOKS[bk]; close = None; xc = 0.0; exit_day = exp
        for (wd, s2, l2) in walk:
            cost = s2 - l2
            if cost <= credit * (1 - cfg["tp"]):
                close = max(cost, 0.0); xc = (s2*spf(s2) + l2*spf(l2))/100.0; exit_day = wd; break
            if cfg["stop"] and cost >= credit * cfg["stop"] and cost <= width * 1.05:
                close = min(cost, width); xc = (s2*spf(s2) + l2*spf(l2))/100.0; exit_day = wd; break
        if close is None:
            # HELD TO EXPIRY. Read the spread's value straight off the two legs on expiry day: an
            # option's closing price ON expiry IS its settlement value, zero when out of the money
            # and intrinsic when in. Both legs come from the same file on the same unadjusted scale
            # as the strikes, so there is nothing to reconcile - no underlying price, no parity, no
            # split adjustment. (User's point, 17-Aug-2026, and it removes the whole class of bug:
            # the previous code derived intrinsic from the UNDERLYING close and silently fell back
            # to the split-ADJUSTED series when a better source was missing.)
            if walk and walk[-1][0] == exp:
                close = min(max(walk[-1][1] - walk[-1][2], 0.0), width)
            else:
                close = settle(cb, exp, ks, si, li, typ, width, spot)   # contract stopped trading early
        exits[bk] = exit_day
        net = (credit - close) - (se*spf(se) + le*spf(le))/100.0 - xc
        _lot = LOTMAP.get(sym, 0)
        # OI IS NOW CARRIED PER BOOK (fixed 20-Aug-2026). `oi` used to be read here from whatever
        # the LAST iteration of the gate loop above left behind, which is v0's legs, not this
        # book's. v0 and v2 share a geometry so they were unaffected, but v1 sells a different
        # strike and every v1 row therefore recorded the WRONG contract's open interest. The gate
        # itself always used the right value; only the recorded column was wrong — which matters
        # because the OI-bucket table below is what justified the floor.
        _oiu = min(oi) if oi is not None else None          # binding leg's OI, in units
        rows.append(dict(book=bk, sym=sym, day=day, yr=int(day[:4]), cw=round(cw, 3),
                         oi_units=_oiu, oi_lots=(round(_oiu / _lot, 1) if (_oiu and _lot) else None),
                         net=round(net, 2), margin=round(width - credit, 2), win=int(net > 0),
                         lot=_lot, net_rs=round(net * _lot, 2),
                         margin_rs=round((width - credit) * _lot, 2)))
    return True, exits

def breakout_days(u):
    """Yields (day, close, typ, d10_hit): typ from the UNION (v2/v0's scanner); d10_hit True when
    the DC-10 band alone triggers with the SAME direction — live v1's scanner."""
    days = [str(i)[:10] for i in u.index]
    cl, hi, lo = u["Close"].values, u["High"].values, u["Low"].values
    # `len(u) - 1` used to drop the FINAL bar, so the newest breakout was never evaluated —
    # out-of-sample that silently discarded the most recent signal on every symbol. Nothing here
    # looks ahead to i+1, so there is no reason to stop short (fixed 20-Aug-2026).
    for i in range(20, len(u)):
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
    frames = pickle.load(open("research/bhav_optstk.pkl", "rb"))
    big = []
    for d, df in frames:
        df = df.copy(); df["DAY"] = d; big.append(df)
    big = pd.concat(big, ignore_index=True); big.columns = [c.strip() for c in big.columns]
    big["EXP"] = pd.to_datetime(big["EXPIRY_DT"], format="mixed", dayfirst=True).dt.date.astype(str)
    for col in ("STRIKE_PR", "CLOSE", "OPEN_INT"): big[col] = big[col].astype(float)
    big["OPTION_TYP"] = big["OPTION_TYP"].astype(str).str.strip()
    big["SYMBOL"] = big["SYMBOL"].astype(str).str.strip()
    PX = {}
    for k, sub in big.groupby(["SYMBOL", "EXP", "OPTION_TYP"], observed=True):
        c = sub.pivot_table(index="DAY", columns="STRIKE_PR", values="CLOSE", aggfunc="last")
        o = sub.pivot_table(index="DAY", columns="STRIKE_PR", values="OPEN_INT",
                            aggfunc="last").reindex(index=c.index, columns=c.columns)
        PX[(str(k[0]), str(k[1]), str(k[2]))] = dict(
            ks=np.asarray(c.columns, dtype="float64"),
            didx={str(d): i for i, d in enumerate(c.index)}, C=c.values.astype("float32"),
            O=o.values.astype("float32"))
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
        last_entry = None; open_until = {}
        for d, c, typ, d10_hit in breakout_days(u):
            dd = date.fromisoformat(d)
            if last_entry and (dd - last_entry).days < REENTRY: continue   # CROSS-BOOK gap
            fut = sorted(e for e in exps_by.get((sym, typ), ())
                         if date.fromisoformat(e) >= dd + timedelta(days=MIN_DTE))
            if not fut: continue
            exp = fut[0]; P = PX.get((sym, exp, typ))
            Q = PX.get((sym, exp, "PE" if typ == "CE" else "CE"))
            if not P or d not in P["didx"] or not Q or d not in Q["didx"]: continue
            di = P["didx"][d]; ks = P["ks"]
            # spot from the chain, never from the adjusted equity series
            qi = Q["didx"][d]
            pxA = {float(k): float(v) for k, v in zip(P["ks"], P["C"][di]) if np.isfinite(v)}
            pxB = {float(k): float(v) for k, v in zip(Q["ks"], Q["C"][qi]) if np.isfinite(v)}
            spot_t = parity_spot(pxA, pxB) if typ == "CE" else parity_spot(pxB, pxA)
            if spot_t is None: continue
            atm = int(np.argmin(np.abs(ks - spot_t)))
            wdays = list(P["didx"].keys())
            def px(si, li, P=P, di=di, wdays=wdays):
                se, le = float(P["C"][di, si]), float(P["C"][di, li])
                if not (np.isfinite(se) and np.isfinite(le)): return None
                walk_all, _idx = [], []
                for t, (a, b) in enumerate(zip(P["C"][di+1:, si], P["C"][di+1:, li])):
                    if np.isfinite(a) and np.isfinite(b):
                        walk_all.append((wdays[di+1+t], float(a), float(b))); _idx.append(t)
                oS, oL = P["O"][di, si], P["O"][di, li]
                oS = 0.0 if not np.isfinite(oS) else float(oS)
                oL = 0.0 if not np.isfinite(oL) else float(oL)
                # THE EXIT MUST BE GATED TOO (audit blocker, 17-Aug-2026). The entry gate alone left
                # every take-profit free to fire on a bhavcopy close for a contract that never traded
                # that day - the same theoretical-settlement price the gate exists to exclude, and
                # the exit is where the P&L is actually realised. A walk day only counts if BOTH
                # legs carried real open interest on it.
                _f = MIN_OI
                walk = [w for t, w in enumerate(walk_all)
                        if (np.isfinite(P["O"][di+1+_idx[t], si]) and P["O"][di+1+_idx[t], si] >= _f
                            and np.isfinite(P["O"][di+1+_idx[t], li]) and P["O"][di+1+_idx[t], li] >= _f)]
                return se, le, walk, (oS, oL)
            cb_t = dict(cb)
            if exp in P["didx"] and exp in Q["didx"]:
                ei, fi = P["didx"][exp], Q["didx"][exp]
                eA = {float(k): float(v) for k, v in zip(P["ks"], P["C"][ei]) if np.isfinite(v)}
                eB = {float(k): float(v) for k, v in zip(Q["ks"], Q["C"][fi]) if np.isfinite(v)}
                es_t = parity_spot(eA, eB) if typ == "CE" else parity_spot(eB, eA)
                if es_t: cb_t[exp] = es_t          # settle on the chain's own scale
            ok, ex = eval_books(d, sym, typ, ks, atm, px, cb_t, exp, spot_t, d10_hit, rows, open_until)
            if ok:
                last_entry = dd
                for _b, _x in ex.items():
                    open_until[_b] = max(open_until.get(_b, ""), _x)
        if n % 15 == 0: print(f"  IS {n}/{len(UNIVERSE)} · {len(rows)} trades", flush=True)
    return rows

# ---------------- OOS: Upstox expired options, date-keyed ----------------
CACHE = "research/cache/oos_legcache_oi.json"   # {key: {date: [close, oi]}} — OI added 17-Aug-2026

def save_cache():
    """Write the leg cache atomically. `json.dump(LEGC, open(CACHE, "w"))` truncates the file the
    instant it opens, so a run killed mid-dump leaves a half-written or empty cache. That already
    happened: a crashed run on 20-Aug-2026 left the file holding a MIX of [close, oi] pairs and
    bare floats, and the next run had to normalise both formats on read. Writing to a temp file and
    renaming means the cache is either the old one or the new one, never a fragment."""
    import os, tempfile
    d = os.path.dirname(CACHE) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(LEGC, fh)
        os.replace(tmp, CACHE)          # atomic on POSIX
    except Exception:
        try: os.unlink(tmp)
        except Exception: pass
        raise
try: LEGC = json.load(open(CACHE))
except Exception: LEGC = {}
# SANITISE ON LOAD (added 20-Aug-2026 after this harness crashed on its own cache). The cache is
# SHARED with studies/ndte/dte_sweep*.py, which used to write a bare float where this file writes
# [close, open_interest]. 6,476 of 37,258 entries carried the wrong shape and px() died on
# `sp[x][1]`. Silently tolerating a bare float would be worse than crashing: it carries no open
# interest, so treating it as "unknown, let it pass" would quietly disable the OI gate on 17% of
# legs — a fidelity gate, in the harness of record. Drop them instead and let them refetch.
_bad = [k for k, v in LEGC.items()
        if not isinstance(v, dict) or any(not isinstance(x, list) or len(x) < 2 for x in v.values())]
for k in _bad: del LEGC[k]
if _bad:
    print(f"cache: dropped {len(_bad)} malformed entr(ies) of {len(_bad)+len(LEGC)}; they will refetch "
          f"with open interest", flush=True)
LK = threading.Lock()

def leg(key, d0, to):
    from engine.data_fetcher import UPSTOX_BASE
    from engine.instruments import encode_key
    from engine.expired_options import _get_json as _gj
    ck = f"{key}|{d0}|{to}"
    with LK:
        if ck in LEGC: return LEGC[ck]
    j = _gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}")
    # FETCH FAILURE IS NOT EVIDENCE OF NO TRADE (fixed 20-Aug-2026, found auditing this file).
    # _get_json returns {} after six failed attempts, and a contract that genuinely never traded
    # ALSO yields {}. Both used to return an empty dict, so every persistent network timeout
    # silently deleted a signal with no count and no log line. That made this harness
    # NON-DETERMINISTIC: the same run on a flaky morning produced fewer trades than on a good one,
    # and nothing in the output said so. Every OOS figure published before this date was produced
    # by that code. A failed request now returns None, only a `success` body counts as evidence of
    # no trade, and the drops are counted and printed.
    if not j or j.get("status") != "success":
        return None
    out = {}
    for c in j.get("data", {}).get("candles", []) or []:
        out[str(c[0])[:10]] = [float(c[4]), float(c[6]) if len(c) > 6 and c[6] is not None else 0.0]
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
        mine = []; last_entry = None; open_until = {}
        for d, c, typ, d10_hit in breakout_days(u):
            dd = date.fromisoformat(d)
            if dd < START: continue
            if last_entry and (dd - last_entry).days < REENTRY: continue
            try:
                exps = [e for e in get_expiries(sym) if e >= (dd + timedelta(days=MIN_DTE)).isoformat()]
                if not exps: continue
                exp = exps[0]
                chain = sorted([x for x in get_contracts(sym, exp) if x["instrument_type"] == typ],
                               key=lambda x: float(x["strike_price"]))
            except Exception: continue
            if len(chain) < 12: continue
            ks = [float(x["strike_price"]) for x in chain]
            to = min(datetime.fromisoformat(exp).date(), dd + timedelta(days=45)).isoformat()
            # No parity here (see the note at the top): guards instead of a chain-derived spot.
            atm = min(range(len(ks)), key=lambda j: abs(ks[j] - c))
            if abs(ks[atm] - c) / c > ATM_MAX_DRIFT: continue
            pos = atm / max(len(ks) - 1, 1)
            if not (ATM_MIN_LADDER_POS <= pos <= 1.0 - ATM_MIN_LADDER_POS): continue
            spot_t = c
            def px(si, li, chain=chain, d=d, to=to):
                sp = leg(chain[si]["instrument_key"], d, to)
                lp = leg(chain[li]["instrument_key"], d, to)
                if sp is None or lp is None:
                    with LK: FETCHFAIL["dropped"] += 1           # network, not liquidity
                    return None
                if d not in sp or d not in lp: return None       # both legs must trade on entry day
                both = sorted(set(sp) & set(lp))
                _f = MIN_OI
                # gate the walk out-of-sample too, exactly as in-sample
                walk = [(x, sp[x][0], lp[x][0]) for x in both
                        if x > d and sp[x][1] >= _f and lp[x][1] >= _f]
                return sp[d][0], lp[d][0], walk, (sp[d][1], lp[d][1])
            ok, ex = eval_books(d, sym, typ, ks, atm, px, cb, exp, spot_t, d10_hit, mine, open_until)
            if ok:
                last_entry = dd
                for _b, _x in ex.items():
                    open_until[_b] = max(open_until.get(_b, ""), _x)
        with LK:
            rows.extend(mine); done[0] += 1
            if done[0] % 5 == 0:
                print(f"  OOS {done[0]}/{len(UNIVERSE)} · {len(rows)} trades", flush=True)
                save_cache()
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(work, UNIVERSE))
    save_cache()
    return rows

# NO WORK AT IMPORT TIME (added 20-Aug-2026, found while unit-testing this file).
# Everything below used to run on import, so `import deployed_backtest` started a multi-hour
# backtest — and the json.dump three lines down OVERWRITES research/deployed_bt_<window>_rows.json,
# the stored results every study reads. A stray import could therefore destroy the record it was
# meant to reproduce. It also made the module impossible to unit-test.
if __name__ == "__main__":
    if WINDOW not in ("IS", "OOS"):
        # Defaulting an unrecognised argument to OOS silently ran the wrong window and wrote its
        # rows file. Refuse instead.
        sys.exit(f"usage: deployed_backtest.py IS|OOS   (got {WINDOW!r})")
    rows = run_is() if WINDOW == "IS" else run_oos()
    json.dump(rows, open(OUT, "w"))
    lbl = ("IS 2019-01-01 -> 2024-07-05 (bhavcopy, parity spot, OI>=100)" if WINDOW == "IS"
           else "OOS Oct-2024 -> date (Upstox, guards)")
    print(f"\n=== DEPLOYED CONFIGS · {lbl} ===")
    print("Read the MEDIAN COHORT (c/w 0.40-0.50; v0 0.35-0.40) — where all 21 real live fills sit.")
    print("ROM-pts pools strike points; ROM-Rs pools rupee margin, which is what an account commits.\n")
    for scope in ("MEDIAN COHORT", "FULL BAND"):
        print(f"--- {scope} ---")
        print(f"{'book':<5}{'n':>7}{'WIN':>8}{'ROM-pts':>10}{'ROM-Rs':>10}{'Rs/trade':>11}{'+ve yrs':>9}")
        for bk, cfg in BOOKS.items():
            g = [x for x in rows if x["book"] == bk]
            if scope == "MEDIAN COHORT":
                lo, hi = (0.35, 0.40) if bk == "v0" else (0.40, 0.50)
                g = [x for x in g if lo <= x["cw"] < hi]
            if len(g) < 20:
                print(f"{bk:<5}{len(g):>7}   (too few)"); continue
            by = collections.defaultdict(list)
            for x in g: by[x["yr"]].append(x["net_rs"])
            pos = sum(1 for v in by.values() if sum(v) > 0)
            mrs = sum(x["margin_rs"] for x in g)
            rom_rs = (sum(x["net_rs"] for x in g) / mrs * 100) if mrs else 0.0
            rs_tr = (sum(x["net_rs"] for x in g) / len(g)) if g else 0.0
            print(f"{bk:<5}{len(g):>7}{sum(x['win'] for x in g)/len(g)*100:>7.1f}%"
                  f"{sum(x['net'] for x in g)/sum(x['margin'] for x in g)*100:>+9.1f}%{rom_rs:>+9.1f}%"
                  f"{rs_tr:>+11,.0f}{pos:>6}/{len(by):<2}")
        print()
    # A run that silently lost signals to the network must not read as a clean run. State it either
    # way, so "0" is positive evidence rather than the absence of a warning.
    if WINDOW == "OOS":
        _fd = FETCHFAIL["dropped"]
        print(f"\nFETCH INTEGRITY: {_fd} signal(s) dropped because Upstox would not answer after six "
              f"retries." + ("  <-- these are NETWORK losses, not liquidity; the run is not "
                             "reproducible and the counts below are a FLOOR." if _fd else
                             "  Every candidate was decided on real data."))
    if SETTLE_FALLBACKS["used"]:
        print(f"NOTE: underlying-derived settlement used on {SETTLE_FALLBACKS['used']} legs "
              f"(contract stopped trading before expiry); every other held trade settled on its own "
              f"expiry-day option prices.")
    # ---- OI BUCKETS: does open interest actually predict outcome, or only exclude the untradeable? ----
    BUCKETS = [(0, 0.999, "0 lots"), (1, 2, "1-2"), (2, 5, "2-5"), (5, 10, "5-10"),
               (10, 25, "10-25"), (25, 1e9, "25+")]
    print("\n=== OI BUCKETS · median cohort · does OI predict win rate and ROM? ===")
    print("The gate is justified as a FIDELITY fix (untraded contracts are not fillable). This asks the")
    print("separate question: among tradeable contracts, does MORE open interest earn MORE?\n")
    for bk in ("v2", "v1", "v0"):
        lo, hi = (0.35, 0.40) if bk == "v0" else (0.40, 0.50)
        g0 = [x for x in rows if x["book"] == bk and lo <= x["cw"] < hi and x.get("oi_lots") is not None]
        if len(g0) < 40: 
            print(f"--- {bk}: only {len(g0)} rows carry OI, skipping"); continue
        print(f"--- {bk} (n={len(g0)}) ---")
        print(f"{'OI (lots)':<12}{'n':>7}{'WIN':>8}{'ROM-Rs':>10}{'Rs/trade':>11}")
        for a, b, lbl in BUCKETS:
            g = [x for x in g0 if a <= x["oi_lots"] < b]
            if len(g) < 10:
                print(f"{lbl:<12}{len(g):>7}   (too few)"); continue
            mrs = sum(x["margin_rs"] for x in g)
            rom = (sum(x["net_rs"] for x in g) / mrs * 100) if mrs else 0.0
            print(f"{lbl:<12}{len(g):>7}{sum(x['win'] for x in g)/len(g)*100:>7.1f}%{rom:>+9.1f}%"
                  f"{sum(x['net_rs'] for x in g)/len(g):>+11,.0f}")
        print()
    print(f"DONE-{WINDOW}")
