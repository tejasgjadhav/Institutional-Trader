"""
Option-Aware Backtest + Parameter Sweep
─────────────────────────────────────────────────────────────────────────────
CALL/PUT signals are evaluated on the OPTION PREMIUM (what you actually exit on),
not the underlying. EQUITY/FUTURE signals stay on the underlying.

Two phases (so the expensive part runs once):
  1. COLLECT  — replay gates over N days, capture each signal's forward path
                (premium series for options, underlying series for equity/future).
  2. SWEEP    — for a grid of (cutoff, target%, stop%), simulate every signal's
                stored path in memory and report win rate / PF / frequency.

Goal: find the combo with the highest win rate (with R:R shown so a high win
rate from a tiny target isn't mistaken for edge).
"""
import logging
from datetime import datetime, timedelta
import pandas as pd

from engine.config import UNIVERSE, TRADING_START
from engine.data_fetcher import fetch_upstox_historical
from engine.signals import compute_all_families, is_orb_confirmed
from engine.portfolio import decide_instrument
from engine.options import get_atm_option, fetch_option_premium_5min

logger = logging.getLogger(__name__)


def _trading_days(n: int) -> list:
    days, day = [], datetime.now() - timedelta(days=1)
    while len(days) < n:
        if day.weekday() < 5:
            days.append(day.date())
        day -= timedelta(days=1)
    return sorted(days)


def _bar_min(ts) -> int:
    return ts.hour * 60 + ts.minute


def _hhmm(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m


# ── Phase 1: collect signals + forward paths ──────────────────────────────────

def collect_signals(n_days: int = 15, max_stocks: int = None, progress=None) -> list:
    """
    Replay gates; for every fired signal (entry before 15:00) capture its
    forward path. Returns a list of event dicts:
      {ticker, day, entry_time(min), instrument, direction, alpha_z,
       entry_price, path:[(high,low,close)...]}   # path = bars AFTER entry to ~15:10
    """
    days = _trading_days(n_days)
    universe = UNIVERSE[:max_stocks] if max_stocks else UNIVERSE
    from_d = (days[0] - timedelta(days=2)).strftime("%Y-%m-%d")
    to_d = (days[-1] + timedelta(days=1)).strftime("%Y-%m-%d")
    start_min = _hhmm(TRADING_START)
    latest_min = _hhmm("15:00")  # collect everything before 3 PM; cutoff applied in sweep

    # index context
    nifty_5m = fetch_upstox_historical("NIFTY", unit="minutes", interval=5, from_date=from_d, to_date=to_d)
    vix_daily = fetch_upstox_historical("VIX", unit="days", interval=1, from_date=from_d, to_date=to_d)

    def nifty_pct(day):
        if nifty_5m.empty: return 0.0
        d = nifty_5m[nifty_5m.index.date == day]
        if d.empty: return 0.0
        return round((float(d["Close"].iloc[-1]) - float(d["Open"].iloc[0])) / float(d["Open"].iloc[0]) * 100, 2)

    def vix(day):
        if vix_daily.empty: return 15.0
        d = vix_daily[vix_daily.index.date <= day]
        return float(d["Close"].iloc[-1]) if not d.empty else 15.0

    events = []
    for idx, ticker in enumerate(universe):
        if progress:
            progress(idx + 1, len(universe), ticker)
        daily_all = fetch_upstox_historical(ticker, unit="days", interval=1,
                                            from_date=(days[0]-timedelta(days=420)).strftime("%Y-%m-%d"), to_date=to_d)
        fivemin_all = fetch_upstox_historical(ticker, unit="minutes", interval=5, from_date=from_d, to_date=to_d)
        if fivemin_all.empty or daily_all.empty:
            continue

        for day in days:
            day5 = fivemin_all[fivemin_all.index.date == day]
            dfd = daily_all[daily_all.index.date < day]
            if len(day5) < 7 or len(dfd) < 30:
                continue
            v, npct = vix(day), nifty_pct(day)

            for i in range(6, len(day5)):
                ts = day5.index[i]
                m = _bar_min(ts)
                if m < start_min:   continue
                if m > latest_min:  break
                partial = day5.iloc[:i+1]
                sig = compute_all_families(ticker, partial, dfd, vix=v, nifty_pct=npct)
                if not sig["passes_gate_1"]:
                    continue
                orb_ok, orb_dir, _ = is_orb_confirmed(partial)
                if not (orb_ok and orb_dir == sig["direction"]):
                    continue

                dec = decide_instrument(sig["alpha_z"], sig["direction"])
                inst = dec["instrument"]
                entry_under = float(partial["Close"].iloc[-1])

                if inst in ("CALL", "PUT"):
                    opt = get_atm_option(ticker, entry_under, day, "CE" if inst == "CALL" else "PE")
                    if not opt:
                        continue
                    prem = fetch_option_premium_5min(opt["key"], day)
                    if prem.empty:
                        continue
                    # align entry to the option bar at/just before the signal time
                    sub = prem[prem.index <= ts]
                    if sub.empty:
                        continue
                    entry_price = float(sub["Close"].iloc[-1])
                    fwd = prem[prem.index > ts]
                    path = [(float(b.High), float(b.Low), float(b.Close)) for b in fwd.itertuples()]
                    long_premium = True   # buying a CALL or PUT = long the premium
                else:
                    entry_price = entry_under
                    fwd = day5.iloc[i+1:]
                    path = [(float(b.High), float(b.Low), float(b.Close)) for b in fwd.itertuples()]
                    long_premium = (inst == "EQUITY")  # equity long; future short

                if not path or entry_price <= 0:
                    continue
                events.append({
                    "ticker": ticker, "day": str(day), "entry_time": m,
                    "instrument": inst, "direction": sig["direction"],
                    "alpha_z": sig["alpha_z"], "entry_price": round(entry_price, 2),
                    "is_long": long_premium, "path": path,
                })
                break  # one signal per stock per day
    return events


# ── Phase 2: simulate one event under a (target%, stop%) rule ─────────────────

def _simulate(event: dict, target_pct: float, stop_pct: float) -> str:
    """Return 'WIN' | 'LOSS' | 'FORCED' for one event's stored path."""
    entry = event["entry_price"]
    long = event["is_long"]
    if long:
        tgt, stp = entry * (1 + target_pct/100), entry * (1 - stop_pct/100)
    else:  # short the underlying (futures): profit when price falls
        tgt, stp = entry * (1 - target_pct/100), entry * (1 + stop_pct/100)

    for hi, lo, _ in event["path"]:
        if long:
            if lo <= stp: return "LOSS"   # stop checked first (conservative)
            if hi >= tgt: return "WIN"
        else:
            if hi >= stp: return "LOSS"
            if lo <= tgt: return "WIN"
    return "FORCED"


def sweep(events: list, cutoffs, targets, stops, instruments=("CALL", "PUT")) -> list:
    """
    For each (cutoff, target%, stop%) combo, simulate the matching events.
    `instruments` filters which signals to include (default: options only).
    Returns rows sorted by win rate desc.
    """
    pool = [e for e in events if e["instrument"] in instruments]
    rows = []
    n_days = len({e["day"] for e in pool}) or 1
    for c in cutoffs:
        cm = _hhmm(c)
        elig = [e for e in pool if e["entry_time"] <= cm]
        for t in targets:
            for s in stops:
                outs = [_simulate(e, t, s) for e in elig]
                n = len(outs)
                if n == 0:
                    continue
                w = outs.count("WIN"); l = outs.count("LOSS"); f = outs.count("FORCED")
                # PF using target/stop magnitudes as proxy R multiples
                gross_w = w * t
                gross_l = l * s
                pf = round(gross_w / gross_l, 2) if gross_l else float("inf")
                rows.append({
                    "cutoff": c, "target": t, "stop": s,
                    "signals": n, "per_day": round(n / n_days, 1),
                    "win_rate": round(w / n, 3), "wins": w, "losses": l, "forced": f,
                    "rr": round(t / s, 2), "pf": pf,
                })
    rows.sort(key=lambda r: (r["win_rate"], r["pf"]), reverse=True)
    return rows


def print_sweep(rows: list, top: int = 20, title="OPTION PREMIUM SWEEP"):
    print("\n" + "=" * 86)
    print(f"{title}  —  ranked by win rate")
    print("=" * 86)
    print(f"{'cutoff':>6} {'tgt%':>5} {'stop%':>5} {'R:R':>5} {'signals':>8} {'/day':>5} "
          f"{'WIN%':>6} {'W/L/F':>10} {'PF':>6}")
    print("-" * 86)
    for r in rows[:top]:
        print(f"{r['cutoff']:>6} {r['target']:>5} {r['stop']:>5} {r['rr']:>5} "
              f"{r['signals']:>8} {r['per_day']:>5} {r['win_rate']*100:>5.0f}% "
              f"{r['wins']}/{r['losses']}/{r['forced']:>3} {r['pf']:>6}")
    print("=" * 86 + "\n")
