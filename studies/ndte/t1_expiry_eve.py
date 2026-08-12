"""T-1 EXPIRY-EVE credit spread — enter 09:16 the day BEFORE expiry, hold through expiry.

USER HYPOTHESIS (2026-08-11): the deployed 0DTE books enter at 09:16 ON expiry day and harvest one
session of theta. Entering the SAME structure one session earlier (T-1) collects a materially larger
premium — two days of decay instead of one — and might still clear an 80%+ win rate because a ~2%
OTM strike is far from spot. Question: does a T-1 entry hold 80%+, and on what geometry?

WHY THIS IS TESTABLE AT ALL, when intraday option history is not. `studies/DATA_AVAILABILITY_LIMITS`
records that intraday option premiums do not exist beyond ~1 month, which is why the 0DTE books were
validated on daily bars. The same trick works here and is BETTER suited: the entry is 09:16, and the
DAILY candle's OPEN is the 09:15-09:16 print. So the daily OPEN of each leg on T-1 is a faithful
entry price, not a proxy — this is the one entry time daily bars can price exactly.

SETTLEMENT is the index close on expiry day, intrinsic vs the short/long strikes, capped at width —
identical to the deployed 0DTE settlement.

COSTS: entry slippage on both legs via the repo's standard spf() model, charged once. No exit cost:
the structure is held to expiry, which is the point of the trade.

SWEEP: OTM% {1.0 .. 3.0}, width in strike steps {2, 4, 6}, side {bear-call, bull-put, both}.
Maximising WIN RATE first per the user's instruction, with ROM reported alongside so a high win rate
with negative expectancy is visible rather than flattering (the 227k-trade lesson).
"""
import sys, os, json, warnings, collections, statistics as st
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import date, datetime, timedelta

from engine.data_fetcher import fetch_upstox_historical, UPSTOX_BASE
from engine.instruments import encode_key
from engine.expired_options import get_expiries, get_contracts, _get_json as _gj

INDICES = ["NIFTY", "SENSEX", "BANKNIFTY"]
START = date(2024, 10, 1)
OTM_PCTS = [1.0, 1.5, 2.0, 2.5, 3.0]
WIDTHS = [2, 4, 6]                      # in strike steps
OUT = "/tmp/t1_expiry_eve_results.json"
CACHE = "/tmp/t1_leg_cache.json"

def spf(p):
    return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0

try:
    LEGC = json.load(open(CACHE))
except Exception:
    LEGC = {}

def leg_bars(key, d0, d1):
    """Daily candles for one option leg between d0 and d1: {date: (open, close)}."""
    ck = f"{key}|{d0}|{d1}"
    if ck in LEGC:
        return {k: tuple(v) for k, v in LEGC[ck].items()}
    j = _gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{d1}/{d0}")
    out = {}
    if j.get("status") == "success":
        for c in j.get("data", {}).get("candles", []) or []:
            out[str(c[0])[:10]] = (float(c[1]), float(c[4]))   # open, close
    LEGC[ck] = {k: list(v) for k, v in out.items()}
    return out

def index_daily(idx):
    df = fetch_upstox_historical(idx, unit="days", interval=1,
                                 from_date="2024-09-01", to_date=date.today().isoformat())
    if df is None or df.empty:
        return {}
    df = df.sort_index()
    return {str(i)[:10]: (float(df["Open"].loc[i]), float(df["Close"].loc[i])) for i in df.index}

rows = []
for idx in INDICES:
    spot_by_day = index_daily(idx)
    if not spot_by_day:
        print(f"{idx}: no index bars", flush=True); continue
    days = sorted(spot_by_day)
    try:
        exps = [e for e in get_expiries(idx) if e >= START.isoformat()]
    except Exception as e:
        print(f"{idx}: expiries failed {e}", flush=True); continue
    print(f"{idx}: {len(exps)} expiries from {START}", flush=True)

    for n_exp, exp in enumerate(exps):
        if exp not in spot_by_day:
            continue
        prior = [d for d in days if d < exp]
        if not prior:
            continue
        t1 = prior[-1]                                  # the session BEFORE expiry
        t1_open = spot_by_day[t1][0]                    # 09:15-09:16 print
        exp_close = spot_by_day[exp][1]                 # settlement
        try:
            chain = get_contracts(idx, exp)
        except Exception:
            continue
        for opt in ("CE", "PE"):
            legs = sorted([c for c in chain if c["instrument_type"] == opt],
                          key=lambda c: float(c["strike_price"]))
            if len(legs) < 12:
                continue
            ks = [float(c["strike_price"]) for c in legs]
            step = st.median([b - a for a, b in zip(ks, ks[1:]) if b > a]) or 0
            if not step:
                continue
            for pct in OTM_PCTS:
                tgt = t1_open * (1 + pct / 100) if opt == "CE" else t1_open * (1 - pct / 100)
                si = min(range(len(ks)), key=lambda i: abs(ks[i] - tgt))
                for w in WIDTHS:
                    li = si + w if opt == "CE" else si - w
                    if not (0 <= li < len(ks)):
                        continue
                    sb = leg_bars(legs[si]["instrument_key"], t1, exp)
                    lb = leg_bars(legs[li]["instrument_key"], t1, exp)
                    if t1 not in sb or t1 not in lb:
                        continue
                    se, le = sb[t1][0], lb[t1][0]        # daily OPEN == the 09:16 entry
                    credit = se - le
                    width = abs(ks[si] - ks[li])
                    if credit <= 0 or credit >= width or se < 1.0:
                        continue
                    intr_s = max(0.0, exp_close - ks[si]) if opt == "CE" else max(0.0, ks[si] - exp_close)
                    intr_l = max(0.0, exp_close - ks[li]) if opt == "CE" else max(0.0, ks[li] - exp_close)
                    settle = min(max(intr_s - intr_l, 0.0), width)
                    cost = (se * spf(se) + le * spf(le)) / 100.0
                    net = (credit - settle) - cost
                    rows.append(dict(idx=idx, exp=exp, t1=t1, side=("BEAR_CALL" if opt == "CE" else "BULL_PUT"),
                                     pct=pct, w=w, credit=round(credit, 2), width=width,
                                     net=round(net, 2), margin=round(width - credit, 2),
                                     win=int(net > 0), cw=round(credit / width, 3)))
        if n_exp % 10 == 0:
            print(f"  {idx} {n_exp}/{len(exps)} · rows {len(rows)}", flush=True)
            json.dump(LEGC, open(CACHE, "w"))

json.dump(LEGC, open(CACHE, "w"))
json.dump(rows, open(OUT, "w"))
print(f"\nTOTAL rows {len(rows)} -> {OUT}", flush=True)

# ── report: win rate first, ROM alongside ──
def rep(sel, lab):
    if len(sel) < 12:
        print(f"{lab:<46} n={len(sel):>4}  (too few)"); return
    n = len(sel); wins = sum(x["win"] for x in sel)
    nm = sum(x["net"] for x in sel); mg = sum(x["margin"] for x in sel)
    print(f"{lab:<46} n={n:>4}  WIN {wins/n*100:5.1f}%  ROM {nm/mg*100:+7.1f}%  "
          f"avg credit {st.mean([x['credit'] for x in sel]):6.1f}  c/w {st.mean([x['cw'] for x in sel]):.2f}")

print("\n=== T-1 EXPIRY-EVE, Oct-2024 -> date · sorted by WIN RATE ===")
for idx in INDICES:
    print(f"\n--- {idx} ---")
    cells = []
    for side in ("BEAR_CALL", "BULL_PUT"):
        for pct in OTM_PCTS:
            for w in WIDTHS:
                sel = [x for x in rows if x["idx"] == idx and x["side"] == side
                       and x["pct"] == pct and x["w"] == w]
                if len(sel) >= 12:
                    cells.append((sum(x["win"] for x in sel) / len(sel), side, pct, w, sel))
    for wr, side, pct, w, sel in sorted(cells, reverse=True)[:8]:
        rep(sel, f"  {side} {pct:.1f}% OTM width {w}")
print("\nDONE-T1")
