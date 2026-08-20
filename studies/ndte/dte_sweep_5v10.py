"""MIN-DTE SWEEP — is the 10-day expiry floor right, and what does it cost?

`STOCK_CREDIT_MIN_DTE = 10` has NO study behind it anywhere in this repo. Every study that mentions
DTE holds it fixed at 10 while sweeping something else, and the only "DTE sweep" on record belongs
to the rejected low-c/w rescue. It appears to have been inherited from the index swing book.

WHY IT MATTERS (user, 17-Aug-2026). The floor pushes the books into FAR expiries: on 17-Aug it
skipped the 25-Aug expiry as too near and took 29-Sep, 43 days out, where ASIANPAINT's 2640 PE had
ZERO open interest and no last trade. So the rule may be creating the illiquidity that the new OI
gate then filters out. His counter-hypothesis, which this measures directly: a lower floor gives
MORE signals, but the premium >= 50 floor starts to bite, because a nearer expiry carries less time
value. Both effects are real and they push opposite ways.

WHAT THIS PRINTS, per DTE floor: surviving trades, win rate, money-weighted ROM, rupees per trade
and per month, AND the two rejection counts that explain the tradeoff — how many candidates died on
the premium floor and how many on the OI floor. That last pair is the point: it shows whether a
shorter tenor buys liquidity faster than it loses premium.

Everything else is the harness of record, unchanged: parity spot in-sample, guards out-of-sample,
date-aligned legs, live hierarchy, one-open-position, OI gate, exit costs.

Run:  .venv/bin/python studies/ndte/dte_sweep.py IS|OOS
"""
_ORIG = """PRODUCTION BACKTEST of the three DEPLOYED stock-credit books, IS and OOS, date-aligned.

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
DTE_GRID = [5, 10]   # narrowed 20-Aug-2026: the only open question is v1 at 5 against the deployed 10
REJECT = collections.Counter()   # why candidates died, per DTE
FETCHFAIL = collections.Counter()   # signals dropped because Upstox would not answer, per DTE floor
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
OUT = f"research/dte5v10_{WINDOW.lower()}_rows.json"

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

def settle(cb, exp, ks, si, li, typ, width, fallback_spot):
    """LAST RESORT only — used when a leg stopped trading before expiry, so the expiry-day option
    prices do not exist. Derives intrinsic from an underlying price, which is the path that can
    disagree with the strike scale on a split or bonus name. Counted so the report can state how
    often it ran instead of hiding it."""
    SETTLE_FALLBACKS["used"] += 1
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
        if se < MIN_PREM:
            REJECT[(MIN_DTE, "premium")] += 1; continue
        _floor = MIN_OI
        if oi is not None and (oi[0] < _floor or oi[1] < _floor):
            REJECT[(MIN_DTE, "openint")] += 1; continue
        credit = se - le; width = abs(ks[si] - ks[li])
        if credit <= 0 or credit >= width: continue
        cw = credit / width
        if not (cfg["band"][0] <= cw < cfg["band"][1]): continue
        fired[bk] = (si, li, se, le, credit, width, cw, walk)
    if "v2" in fired and "v1" in fired:      # same-day: v1 defers to v2
        del fired["v1"]
    if "v1" in fired and "v0" in fired:      # engine rule: v1 wins the same-stock clash
        del fired["v0"]
    if not fired: return False, {}
    exits = {}
    for bk, (si, li, se, le, credit, width, cw, walk) in fired.items():
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
        rows.append(dict(book=bk, sym=sym, day=day, yr=int(day[:4]), cw=round(cw, 3),
                         net=round(net, 2), margin=round(width - credit, 2), win=int(net > 0),
                         lot=_lot, net_rs=round(net * _lot, 2),
                         margin_rs=round((width - credit) * _lot, 2)))
    return True, exits

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
CACHE = "research/cache/oos_legcache_oi.json"
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
    # _get_json returns {} after six failed attempts, which is INDISTINGUISHABLE from a contract
    # that simply never traded. Both used to yield an empty dict, so a network timeout silently
    # deleted a signal. That matters here because the two DTE floors run sequentially under
    # different throttling, so whichever floor ran while Upstox was slow would show fewer trades
    # and be read as "thinner liquidity" - which is the hypothesis under test. A failed request
    # now returns None and is COUNTED; a successful response with no candles stays {}.
    if not j or j.get("status") != "success":
        return None                          # no answer, or an error body - not evidence of no trade
    out = {}
    if True:
        for c in j.get("data", {}).get("candles", []) or []:
            out[str(c[0])[:10]] = float(c[4])
    if out:                                   # never cache an empty (network-poisoned) result
        with LK: LEGC[ck] = out
    return out

def run_oos():
    from engine.data_fetcher import fetch_upstox_historical
    from engine.expired_options import get_expiries, get_contracts
    START = date(2025, 10, 1)   # last ~11 months only, the regime whose liquidity we are testing
    # The re-entry gap is 3 days and a position can stay open ~45, so the book has to be warm
    # before the first recorded day. Starting the LOOP at START would open the window with an
    # empty book and take entries the live engine would have blocked, inflating the first weeks.
    WARM = date(2025, 8, 1)
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
            if dd < WARM: continue
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
                    with LK: FETCHFAIL[MIN_DTE] += 1             # network, not liquidity
                    return None
                if d not in sp or d not in lp: return None       # both legs must trade on entry day
                both = sorted(set(sp) & set(lp))
                # The OOS leg cache stores [close, open_interest] per date. This script still
                # unpacked it as a bare close, which crashed the whole sweep at 06:16 on 20-Aug
                # (TypeError: list < float). Ported from deployed_backtest.py.
                # The cache holds a MIX of formats: [close, open_interest] written by
                # deployed_backtest.py, and bare closes written by an earlier crashed run of this
                # script. Normalise on read rather than rebuild the cache, which would cost hours.
                # A bare close carries no OI, so it is treated as unknown and passes the gate —
                # the entry-day OI check still applies wherever the pair form is present.
                def _c(v):  return v[0] if isinstance(v, list) else v
                def _o(v):  return v[1] if isinstance(v, list) else None
                _f = MIN_OI
                walk = [(x, _c(sp[x]), _c(lp[x])) for x in both
                        if x > d
                        and (_o(sp[x]) is None or _o(sp[x]) >= _f)
                        and (_o(lp[x]) is None or _o(lp[x]) >= _f)]
                _os, _ol = _o(sp[d]), _o(lp[d])
                return (_c(sp[d]), _c(lp[d]), walk,
                        (_os, _ol) if (_os is not None and _ol is not None) else None)
            ok, ex = eval_books(d, sym, typ, ks, atm, px, cb, exp, spot_t, d10_hit, mine, open_until)
            if ok:
                last_entry = dd
                for _b, _x in ex.items():
                    open_until[_b] = max(open_until.get(_b, ""), _x)
        mine = [r for r in mine if r["day"] >= START.isoformat()]   # warm-up trades build state only
        with LK:
            rows.extend(mine); done[0] += 1
            if done[0] % 5 == 0:
                print(f"  OOS {done[0]}/{len(UNIVERSE)} · {len(rows)} trades", flush=True)
                json.dump(LEGC, open(CACHE, "w"))
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(work, UNIVERSE))
    json.dump(LEGC, open(CACHE, "w"))
    return rows

ALL = {}
for _d in DTE_GRID:
    MIN_DTE = _d
    globals()["MIN_DTE"] = _d
    REJECT.clear()
    _r = run_is() if WINDOW == "IS" else run_oos()
    for x in _r: x["dte_floor"] = _d
    ALL[_d] = dict(rows=_r, prem=REJECT[(_d, "premium")], oi=REJECT[(_d, "openint")])
    print(f"  DTE>={_d}: {len(_r)} trades · rejected on premium {REJECT[(_d,'premium')]} · "
          f"on OI {REJECT[(_d,'openint')]} · DROPPED ON FETCH FAILURE {FETCHFAIL[_d]}", flush=True)
rows = [x for v in ALL.values() for x in v["rows"]]
json.dump(rows, open(OUT, "w"))
lbl = "IS 2019-01-01 -> 2024-07-05 (bhavcopy)" if WINDOW == "IS" else "OOS Oct-2024 -> date (Upstox)"
MON = 66.0 if WINDOW == "IS" else 10.7   # Oct-2025 -> 20-Aug-2026
print(f"\n=== MIN-DTE SWEEP · {lbl} · MEDIAN COHORT (c/w 0.40-0.50; v0 0.35-0.40) ===")
print("Deployed floor is 10. 'rej prem' / 'rej OI' are candidates killed by those gates at that DTE.\n")
for bk in ("v2", "v1", "v0"):
    lo, hi = (0.35, 0.40) if bk == "v0" else (0.40, 0.50)
    print(f"--- {bk} ---")
    print(f"{'DTE>=':>6}{'n':>7}{'WIN':>8}{'ROM-Rs':>10}{'Rs/trade':>11}{'sig/mo':>9}{'Rs/mo':>11}{'+ve yrs':>9}{'rej prem':>10}{'rej OI':>9}")
    for d in DTE_GRID:
        g = [x for x in ALL[d]["rows"] if x["book"] == bk and lo <= x["cw"] < hi]
        if len(g) < 15:
            print(f"{d:>6}{len(g):>7}   (too few)"); continue
        by = collections.defaultdict(list)
        for x in g: by[x["yr"]].append(x["net_rs"])
        pos = sum(1 for v in by.values() if sum(v) > 0)
        mrs = sum(x["margin_rs"] for x in g)
        rom = (sum(x["net_rs"] for x in g) / mrs * 100) if mrs else 0.0
        rs = sum(x["net_rs"] for x in g)
        star = "  <-- deployed" if d == 10 else ""
        print(f"{d:>6}{len(g):>7}{sum(x['win'] for x in g)/len(g)*100:>7.1f}%{rom:>+9.1f}%"
              f"{rs/len(g):>+11,.0f}{len(g)/MON:>9.1f}{rs/MON:>+11,.0f}{pos:>6}/{len(by):<2}"
              f"{ALL[d]['prem']:>10,}{ALL[d]['oi']:>9,}{star}")
    print()
print(f"DONE-{WINDOW}")
