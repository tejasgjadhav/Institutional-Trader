"""
Weighted-composite backtest with train/test validation.

Instead of a hard "K signals must agree" cutoff, each of the 6 signals gets a
WEIGHT and we form a composite score:

    composite = sum( weight_i * vote_i )      vote_i in {+1, 0, -1}

Enter at the first bar where |composite| >= threshold; direction = sign(composite).
Weights are DERIVED on a training window (from each signal's own edge), then the
threshold is chosen on train and the whole rule is validated OUT-OF-SAMPLE on a
held-out test window. Exit = buy OTM+1, +10%/-20% on premium (comparable to live).

Phase 1 (collect, expensive, once): for each stock/day store the per-bar votes and
both CE+PE OTM+1 premium series. Phase 2 (sweep weights/threshold) is in-memory.
"""
import json
import logging
from datetime import datetime, timedelta
import pandas as pd

from engine.config import UNIVERSE, TRADING_START, OPTION_STRIKE_OFFSET, PREMIUM_TARGET_PCT, PREMIUM_STOP_PCT
from engine.data_fetcher import fetch_upstox_historical
from engine.options import get_option_by_offset, fetch_option_premium_5min
from engine.backtest120 import _fetch_5min_chunked
from engine.confluence_backtest import _votes, _bmin, _hhmm, _tdays

logger = logging.getLogger(__name__)
SIGNALS = ["RS", "VWAP", "GAP", "MOM", "VOL", "ORB"]


def _premium_outcome(prem, ts):
    sub = prem[prem.index <= ts]
    if sub.empty: return None
    entry = float(sub.Close.iloc[-1])
    if entry <= 0: return None
    tgt, stp = entry*(1+PREMIUM_TARGET_PCT/100), entry*(1-PREMIUM_STOP_PCT/100)
    last = entry
    for b in prem[prem.index > ts].itertuples():
        last = float(b.Close)
        if last <= stp: return ("LOSS", round((stp/entry-1)*100, 2))
        if last >= tgt: return ("WIN", round((tgt/entry-1)*100, 2))
    return ("FORCED", round((last/entry-1)*100, 2))


def collect(n_days=15, cutoff="13:00", progress=None) -> list:
    """
    Returns a list of stock-day records:
      {day, votes:[(bar_time_iso, {sig:vote}, spot)...],
       ce: {bar_time_iso: premium}, pe: {bar_time_iso: premium}}
    where vote is +1/-1/0. Premium series let us simulate any (weights,threshold).
    """
    days = _tdays(n_days)
    from_dt = days[0]-timedelta(days=3); to_dt = days[-1]+timedelta(days=1)
    start_min, cut_min = _hhmm(TRADING_START), _hhmm(cutoff)
    nifty5 = _fetch_5min_chunked("NIFTY", from_dt, to_dt)

    recs = []
    for idx, under in enumerate(UNIVERSE):
        if progress: progress(idx+1, len(UNIVERSE), under)
        daily = fetch_upstox_historical(under, unit="days", interval=1,
                from_date=(days[0]-timedelta(days=30)).strftime("%Y-%m-%d"), to_date=to_dt.strftime("%Y-%m-%d"))
        five = _fetch_5min_chunked(under, from_dt, to_dt)
        if five.empty or daily.empty: continue
        for day in days:
            d5 = five[five.index.date == day]
            if len(d5) < 7: continue
            prev = daily[daily.index.date < day]
            if prev.empty: continue
            prev_close = float(prev.Close.iloc[-1]); day_open = float(d5.Open.iloc[0])
            nday = nifty5[nifty5.index.date == day]; nifty_open = float(nday.Open.iloc[0]) if not nday.empty else 0
            orb = d5.iloc[:6]; orb_hi = float(orb.High.max()); orb_lo = float(orb.Low.min()); orb_va = float(orb.Volume.mean())

            vote_series = []
            any_long = any_short = False
            for i in range(6, len(d5)):
                ts = d5.index[i]; m = _bmin(ts)
                if m < start_min: continue
                if m > cut_min: break
                part = d5.iloc[:i+1]; npart = nday[nday.index <= ts] if not nday.empty else None
                vv = _votes(part, day_open, prev_close, npart, nifty_open, orb_hi, orb_lo, orb_va)
                vote = {s: (1 if vv[s]=="LONG" else (-1 if vv[s]=="SHORT" else 0)) for s in SIGNALS}
                vote_series.append((ts.isoformat(), vote, float(part.Close.iloc[-1])))
                if any(x==1 for x in vote.values()): any_long = True
                if any(x==-1 for x in vote.values()): any_short = True
            if not vote_series: continue

            rec = {"under": under, "day": str(day), "votes": vote_series, "ce": {}, "pe": {}}
            spot0 = vote_series[0][2]
            if any_long:
                opt = get_option_by_offset(under, spot0, day, "CE", OPTION_STRIKE_OFFSET)
                p = fetch_option_premium_5min(opt["key"], day) if opt else pd.DataFrame()
                rec["ce"] = {t.isoformat(): float(c) for t, c in p["Close"].items()} if not p.empty else {}
            if any_short:
                opt = get_option_by_offset(under, spot0, day, "PE", OPTION_STRIKE_OFFSET)
                p = fetch_option_premium_5min(opt["key"], day) if opt else pd.DataFrame()
                rec["pe"] = {t.isoformat(): float(c) for t, c in p["Close"].items()} if not p.empty else {}
            recs.append(rec)
    return recs


def _series_from(d: dict) -> pd.Series:
    if not d: return pd.Series(dtype=float)
    s = pd.Series(d); s.index = pd.to_datetime(s.index); return s.sort_index()


def _eval_rule(recs, weights, threshold):
    """Apply (weights, threshold) to records; return list of (outcome,pnl)."""
    out = []
    for r in recs:
        fire = None
        for tiso, vote, spot in r["votes"]:
            comp = sum(weights[s]*vote[s] for s in SIGNALS)
            if abs(comp) >= threshold:
                fire = (tiso, "LONG" if comp > 0 else "SHORT"); break
        if not fire: continue
        tiso, direction = fire
        prem = _series_from(r["ce"] if direction == "LONG" else r["pe"])
        if prem.empty: continue
        res = _premium_outcome(prem, pd.to_datetime(tiso))
        if res: out.append(res)
    return out


def _winrate(lst):
    n = len(lst)
    if not n: return (0, 0, 0)
    g = sum(1 for o in lst if o[1] > 0); net = sum(o[1] for o in lst)
    return (n, round(g/n*100), round(net/n, 2))


def derive_weights(recs):
    """
    Weight each signal by its own option win-rate edge on these records:
    weight = max(0, win_rate - 50). Correlated signals will get similar weights.
    """
    per = {s: [] for s in SIGNALS}
    for r in recs:
        ce = _series_from(r["ce"]); pe = _series_from(r["pe"])
        seen = {s: False for s in SIGNALS}
        for tiso, vote, spot in r["votes"]:
            for s in SIGNALS:
                if vote[s] != 0 and not seen[s]:
                    seen[s] = True
                    prem = ce if vote[s] == 1 else pe
                    if not prem.empty:
                        res = _premium_outcome(prem, pd.to_datetime(tiso))
                        if res: per[s].append(res)
    weights = {}
    for s in SIGNALS:
        n, w, _ = _winrate(per[s])
        weights[s] = max(0.0, (w - 50)) if n >= 20 else 0.0
    return weights, {s: _winrate(per[s]) for s in SIGNALS}
