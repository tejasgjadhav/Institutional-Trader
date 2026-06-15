"""
Alternative entry-signal backtest — Relative Strength, Opening Gap, VWAP.

Tests three different entry ideas on the SAME option exit as the live system
(buy OTM+1, +10% target / -20% stop on premium) so win rates compare directly
to the current 3-family system. One pass over the data evaluates all signals;
capped at the first few fires per stock-day to mirror the max-trades/day reality.
"""
import logging
from datetime import datetime, timedelta
import pandas as pd

from engine.config import UNIVERSE, TRADING_START
from engine.data_fetcher import fetch_upstox_historical
from engine.options import get_option_by_offset, fetch_option_premium_5min
from engine.backtest120 import _fetch_5min_chunked
from engine.config import OPTION_STRIKE_OFFSET, PREMIUM_TARGET_PCT, PREMIUM_STOP_PCT

logger = logging.getLogger(__name__)


def _trading_days(n):
    days, d = [], datetime.now() - timedelta(days=1)
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d.date())
        d -= timedelta(days=1)
    return sorted(days)

def _bmin(ts): return ts.hour * 60 + ts.minute
def _hhmm(s): h, m = map(int, s.split(":")); return h*60+m


def _vwap(df):
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    return (tp * df["Volume"]).cumsum() / df["Volume"].cumsum()


# ── the three signals (return 'LONG'|'SHORT'|None at the current bar) ─────────

def sig_relative_strength(part, day_open, nifty_part, nifty_open):
    """Stock outperforming Nifty and moving with it."""
    if nifty_part is None or len(nifty_part) == 0 or day_open <= 0 or nifty_open <= 0:
        return None
    px = float(part["Close"].iloc[-1])
    sret = (px - day_open) / day_open * 100
    nret = (float(nifty_part["Close"].iloc[-1]) - nifty_open) / nifty_open * 100
    rs = sret - nret
    if rs > 0.5 and sret > 0.2:
        return "LONG"
    if rs < -0.5 and sret < -0.2:
        return "SHORT"
    return None


def sig_opening_gap(part, day_open, prev_close):
    """Gap-and-go: gapped open and holding the gap."""
    if prev_close <= 0 or day_open <= 0:
        return None
    gap = (day_open - prev_close) / prev_close * 100
    px = float(part["Close"].iloc[-1])
    if gap > 0.5 and px > day_open:
        return "LONG"
    if gap < -0.5 and px < day_open:
        return "SHORT"
    return None


def sig_vwap(part):
    """Above VWAP and rising = LONG; below and falling = SHORT."""
    if len(part) < 4:
        return None
    v = float(_vwap(part).iloc[-1])
    px = float(part["Close"].iloc[-1]); px3 = float(part["Close"].iloc[-4])
    if px > v and px > px3:
        return "LONG"
    if px < v and px < px3:
        return "SHORT"
    return None


SIGNALS = {"RELATIVE_STRENGTH": "rs", "OPENING_GAP": "gap", "VWAP": "vwap"}


def _simulate_option(under, day, ts, spot, direction):
    """Buy OTM+1 option, exit +10%/-20% on premium. Returns ('WIN'|'LOSS'|'FORCED', pnl%)."""
    opt_type = "CE" if direction == "LONG" else "PE"
    opt = get_option_by_offset(under, spot, day, opt_type, OPTION_STRIKE_OFFSET)
    if not opt:
        return None
    prem = fetch_option_premium_5min(opt["key"], day)
    if prem.empty:
        return None
    sub = prem[prem.index <= ts]
    if sub.empty:
        return None
    entry = float(sub["Close"].iloc[-1])
    if entry <= 0:
        return None
    tgt, stp = entry*(1+PREMIUM_TARGET_PCT/100), entry*(1-PREMIUM_STOP_PCT/100)
    last = entry
    for b in prem[prem.index > ts].itertuples():
        last = float(b.Close)
        if last <= stp: return ("LOSS", round((stp/entry-1)*100, 2))
        if last >= tgt: return ("WIN", round((tgt/entry-1)*100, 2))
    return ("FORCED", round((last/entry-1)*100, 2))


def run(n_days=20, cutoff="13:00", max_per_day=3, progress=None) -> dict:
    days = _trading_days(n_days)
    from_dt = days[0] - timedelta(days=3); to_dt = days[-1] + timedelta(days=1)
    start_min, cut_min = _hhmm(TRADING_START), _hhmm(cutoff)

    nifty5 = _fetch_5min_chunked("NIFTY", from_dt, to_dt)

    results = {name: [] for name in SIGNALS}   # name -> list of (outcome, pnl)
    for k, under in enumerate(UNIVERSE):
        if progress: progress(k+1, len(UNIVERSE), under)
        daily = fetch_upstox_historical(under, unit="days", interval=1,
                  from_date=(days[0]-timedelta(days=30)).strftime("%Y-%m-%d"), to_date=to_dt.strftime("%Y-%m-%d"))
        five = _fetch_5min_chunked(under, from_dt, to_dt)
        if five.empty or daily.empty:
            continue
        for day in days:
            d5 = five[five.index.date == day]
            if len(d5) < 7:
                continue
            prev = daily[daily.index.date < day]
            if prev.empty:
                continue
            prev_close = float(prev["Close"].iloc[-1])
            day_open = float(d5["Open"].iloc[0])
            nday = nifty5[nifty5.index.date == day]
            nifty_open = float(nday["Open"].iloc[0]) if not nday.empty else 0
            fired = {name: 0 for name in SIGNALS}        # cap per day
            first_seen = {name: False for name in SIGNALS}

            for i in range(6, len(d5)):
                ts = d5.index[i]; m = _bmin(ts)
                if m < start_min: continue
                if m > cut_min: break
                part = d5.iloc[:i+1]
                npart = nday[nday.index <= ts] if not nday.empty else None
                spot = float(part["Close"].iloc[-1])
                checks = {
                    "RELATIVE_STRENGTH": sig_relative_strength(part, day_open, npart, nifty_open),
                    "OPENING_GAP": sig_opening_gap(part, day_open, prev_close),
                    "VWAP": sig_vwap(part),
                }
                for name, direction in checks.items():
                    if direction and not first_seen[name] and fired[name] < max_per_day:
                        first_seen[name] = True   # one entry per stock/day per signal
                        out = _simulate_option(under, day, ts, spot, direction)
                        if out:
                            results[name].append(out)
                            fired[name] += 1
    # summarise
    summary = {}
    for name, lst in results.items():
        n = len(lst)
        if not n:
            summary[name] = {"trades": 0, "win": 0, "exp": 0}; continue
        green = sum(1 for o in lst if o[1] > 0)
        net = sum(o[1] for o in lst)
        summary[name] = {"trades": n, "win": round(green/n*100), "exp": round(net/n, 2)}
    return summary
