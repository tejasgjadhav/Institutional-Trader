"""SENSEX weekly, SOLD DAILY (user question 18-Sep-2026).
Every trading day at 09:16: sell the CE nearest 0.5% ABOVE spot and/or the PE nearest 0.5% BELOW
spot, on the CURRENT weekly expiry; close at 15:29 the same day. Hedge = the spread WING (user: "we are doing bear call spread"): CE ~0.83% above spot / PE ~0.83% below,
the deployed 0DTE geometry on the week's first trading day at 09:16, hold it,
close at 15:29 on expiry day, then rotate. 1 lot. Prices = 1-minute expired-contract candles
(close of the 09:16 bar, close of the 15:29 bar). Spot = SENSEX 1-min cache. Win = P&L > 0.
Costs: Rs100 per round trip per leg (brokerage + charges + a tick), reported gross AND net."""
import os, sys, json, time
sys.path.insert(0, "."); import pandas as pd, numpy as np
from dotenv import load_dotenv; load_dotenv(".env")
from datetime import date, timedelta
from engine.expired_options import get_expiries, get_contracts
from engine.data_fetcher import UPSTOX_BASE, SESSION
from engine.instruments import encode_key
from engine import histdb
OUT = "research/sensex_daily"; CACHE = os.path.join(OUT, "px_cache.json")
px_cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
FAIL429 = [0]
COST_RT = 100.0
START = os.environ.get("SD_START"); END = os.environ.get("SD_END")
GENTLE = os.environ.get("SD_GENTLE") == "1"   # market hours: 1 req/s, abort on a second 429
def spot_series():
    import glob
    fs = sorted(glob.glob("research/m1cache/SENSEX_*.csv.gz")); d = pd.concat([pd.read_csv(f, parse_dates=["ts"]) for f in fs])
    d["day"] = d.ts.dt.date; d["hm"] = d.ts.dt.strftime("%H:%M"); return d
def intraday(key, day):
    """1-minute closes {HH:MM: close} via the market-history DB (fetch-through, rate-limit loop)."""
    b = histdb.opt_candles(key, day)
    return {hm: v[3] for hm, v in b.items()}
def at(bars, hm, fallback=None):
    if not bars: return None
    if hm in bars: return bars[hm]
    ks = sorted(k for k in bars if k <= hm); return bars[ks[-1]] if ks else fallback
if __name__ == "__main__":
    S = spot_series(); days_all = sorted(S.day.unique())
    exps = [date.fromisoformat(e) for e in get_expiries("SENSEX")]
    if START: exps = [e for e in exps if e >= date.fromisoformat(START)]
    if END: exps = [e for e in exps if e <= date.fromisoformat(END)]
    OUT_ROWS = os.path.join(OUT, "daily_rows.csv" if not (START or END) else f"daily_rows_{START}_{END}.csv")
    rows = []; prev = (exps[0] - timedelta(days=7)) if exps else None; n_call = 0   # first week = the 7 days before the first expiry, not all of history
    for E in exps:
        week = [d for d in days_all if (prev is None or d > prev) and d <= E]; prev = E
        if not week: continue
        try: ch = get_contracts("SENSEX", E.isoformat()); histdb.record_contracts("SENSEX", E.isoformat(), ch)
        except Exception: continue
        ce = sorted([c for c in ch if c["instrument_type"] == "CE"], key=lambda c: float(c["strike_price"]))
        pe = sorted([c for c in ch if c["instrument_type"] == "PE"], key=lambda c: float(c["strike_price"]))
        if len(ce) < 10 or len(pe) < 10: continue
        lot = int(ce[0].get("lot_size") or 20)
        def near(chain, target): return min(chain, key=lambda c: abs(float(c["strike_price"]) - target))
        hedge = {}
        for i, D in enumerate(week):
            sp = S[(S.day == D) & (S.hm == "09:16")]
            if sp.empty: continue
            spot = float(sp.c.iloc[0]); dte = (E - D).days
            sc, spu = near(ce, spot * 1.005), near(pe, spot * 0.995)
            if i == 0: hedge = {"CE": near(ce, spot * 1.0083), "PE": near(pe, spot * 0.9917), "px0": {}}
            rec = dict(day=D.isoformat(), expiry=E.isoformat(), dte=dte, spot=spot, lot=lot)
            for side, wc in (("CE", near(ce, spot * 1.0083)), ("PE", near(pe, spot * 0.9917))):
                b = intraday(wc["instrument_key"], D.isoformat()); n_call += 1
                w0, w1 = at(b, "09:16"), at(b, "15:29")
                rec[f"dwing_{side}_strike"] = float(wc["strike_price"])
                rec[f"dwing_{side}_pts"] = (w1 - w0) if (w0 is not None and w1 is not None) else None
            for side, c in (("CE", sc), ("PE", spu)):
                b = intraday(c["instrument_key"], D.isoformat()); n_call += 1
                e0, e1 = at(b, "09:16"), at(b, "15:29")
                rec[f"short_{side}_strike"] = float(c["strike_price"]); rec[f"short_{side}_in"] = e0; rec[f"short_{side}_out"] = e1
                rec[f"short_{side}_pts"] = (e0 - e1) if (e0 is not None and e1 is not None) else None
            for side in ("CE", "PE"):
                hc = hedge[side]; b = intraday(hc["instrument_key"], D.isoformat()); n_call += 1
                h0, h1 = at(b, "09:16"), at(b, "15:29")
                if i == 0: hedge["px0"][side] = h0
                rec[f"hedge_{side}_strike"] = float(hc["strike_price"]); rec[f"hedge_{side}_mark"] = h1
                # hedge P&L attributed daily as mark-to-mark (entry at week's first 09:16)
                prev_mark = hedge.get("last", {}).get(side, hedge["px0"].get(side))
                rec[f"hedge_{side}_pts"] = (h1 - prev_mark) if (h1 is not None and prev_mark is not None) else None
                hedge.setdefault("last", {})[side] = h1 if h1 is not None else prev_mark
            rows.append(rec)
        if len(rows) % 50 < 5: print(f"  {E} · days {len(rows)} · calls {n_call}", flush=True); json.dump(px_cache, open(CACHE, "w"))
    json.dump(px_cache, open(CACHE, "w"))
    df = pd.DataFrame(rows); df.to_csv(OUT_ROWS, index=False)
    print(f"DONE {len(df)} trading days · {df.expiry.nunique()} weeks · calls {n_call} · 429s waited out: {FAIL429[0]}", flush=True)
