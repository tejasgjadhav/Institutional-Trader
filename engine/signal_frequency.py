"""
Signal Frequency Backtest
─────────────────────────────────────────────────────────────────────────────
Answers the practical question: "Will this strategy give me 1-2 tradeable
names per day for intraday?"

For each recent trading day it replays the REAL gate logic on every stock:
  Gate 1  |alpha-z| > threshold AND >=2 of 3 families agree
  Gate 2  a 5-min ORB breakout with volume occurs, same direction

A stock 'fires' if both gates align at any scan bar between 09:45 and 15:00.
Reports names/day so you can see the realistic signal count.
"""
import logging
from datetime import datetime, timedelta
import pandas as pd

from engine.config import (
    UNIVERSE, TRADING_START, NO_NEW_TRADES_AFTER, KILL_SWITCH_TIME,
    STOP_LOSS_CAP_PCT,
)
from engine.data_fetcher import fetch_upstox_historical
from engine.signals import compute_all_families, is_orb_confirmed
from engine.portfolio import decide_instrument

logger = logging.getLogger(__name__)


def _trading_days(n: int) -> list:
    days, day = [], datetime.now()
    # start from yesterday to ensure complete sessions
    day -= timedelta(days=1)
    while len(days) < n:
        if day.weekday() < 5:
            days.append(day.date())
        day -= timedelta(days=1)
    return sorted(days)


def _bar_minutes(ts) -> int:
    return ts.hour * 60 + ts.minute


def _scan_window(start="09:45", end="15:00"):
    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    return sh * 60 + sm, eh * 60 + em


def _simulate_outcome(day_5min: pd.DataFrame, entry_idx: int, entry: float,
                      direction: str, target_pct: float) -> dict:
    """
    Simulate a trade from the bar AFTER entry to the kill-switch time.
      stop   = ±STOP_LOSS_CAP_PCT (1%) from entry
      target = ±target_pct from entry (1% equity, 5% futures/options)
    Returns {'outcome': WIN|LOSS|FORCED, 'pnl_pct': float, 'exit': float, 'exit_time': str}.
    """
    kh, km = map(int, KILL_SWITCH_TIME.split(":"))
    kill_min = kh * 60 + km

    if direction == "LONG":
        stop = entry * (1 - STOP_LOSS_CAP_PCT / 100)
        target = entry * (1 + target_pct / 100)
    else:
        stop = entry * (1 + STOP_LOSS_CAP_PCT / 100)
        target = entry * (1 - target_pct / 100)

    last_close = entry
    last_ts = day_5min.index[entry_idx]
    for j in range(entry_idx + 1, len(day_5min)):
        bar = day_5min.iloc[j]
        ts = day_5min.index[j]
        last_close, last_ts = float(bar["Close"]), ts
        hi, lo = float(bar["High"]), float(bar["Low"])

        if direction == "LONG":
            # If both touched in one bar, assume stop first (conservative)
            if lo <= stop:
                return {"outcome": "LOSS", "pnl_pct": round((stop/entry-1)*100, 2),
                        "exit": round(stop, 2), "exit_time": str(ts)[11:16]}
            if hi >= target:
                return {"outcome": "WIN", "pnl_pct": round((target/entry-1)*100, 2),
                        "exit": round(target, 2), "exit_time": str(ts)[11:16]}
        else:
            if hi >= stop:
                return {"outcome": "LOSS", "pnl_pct": round((entry/stop-1)*100, 2),
                        "exit": round(stop, 2), "exit_time": str(ts)[11:16]}
            if lo <= target:
                return {"outcome": "WIN", "pnl_pct": round((entry/target-1)*100, 2),
                        "exit": round(target, 2), "exit_time": str(ts)[11:16]}

        if _bar_minutes(ts) >= kill_min:
            break

    # Forced close at last seen bar
    pnl = (last_close/entry - 1) * 100 if direction == "LONG" else (entry/last_close - 1) * 100
    return {"outcome": "FORCED", "pnl_pct": round(pnl, 2),
            "exit": round(last_close, 2), "exit_time": str(last_ts)[11:16]}


def _stock_fires_on_day(day_5min: pd.DataFrame, df_daily: pd.DataFrame,
                        vix: float, nifty_pct: float) -> dict:
    """
    Replay scans across one day; if a signal fires, simulate its outcome.
    Returns {'fired', 'dir', 'bar_time', 'entry', 'outcome', 'pnl_pct', 'target', 'exit', 'exit_time'}.
    """
    if day_5min.empty or len(day_5min) < 7:
        return {"fired": False}

    start_min, end_min = _scan_window(TRADING_START, NO_NEW_TRADES_AFTER)

    for i in range(6, len(day_5min)):  # bar 6 ≈ 09:45 (ORB = first 6 bars)
        ts = day_5min.index[i]
        m = _bar_minutes(ts)
        if m < start_min:
            continue
        if m > end_min:
            break

        partial = day_5min.iloc[: i + 1]
        sig = compute_all_families("X", partial, df_daily, vix=vix, nifty_pct=nifty_pct)
        if not sig.get("passes_gate_1"):
            continue
        orb_ok, orb_dir, _ = is_orb_confirmed(partial)
        if orb_ok and orb_dir == sig["direction"]:
            entry = float(partial["Close"].iloc[-1])
            decision = decide_instrument(sig["alpha_z"], sig["direction"])
            tpct = decision["target_pct"]
            out = _simulate_outcome(day_5min, i, entry, sig["direction"], tpct)
            tgt = (entry * (1 + tpct / 100) if sig["direction"] == "LONG"
                   else entry * (1 - tpct / 100))
            return {"fired": True, "dir": sig["direction"], "alpha_z": sig["alpha_z"],
                    "instrument": decision["instrument"], "target_pct": tpct,
                    "bar_time": str(ts)[11:16], "entry": round(entry, 2),
                    "target": round(tgt, 2), **out}
    return {"fired": False}


def run_frequency_test(n_days: int = 3, max_stocks: int = None, progress=None) -> dict:
    """
    Replay the strategy over the last n_days trading sessions.
    Returns per-day fired names + summary.
    """
    days = _trading_days(n_days)
    universe = UNIVERSE[:max_stocks] if max_stocks else UNIVERSE

    # date range covering all test days (+ a buffer day each side)
    from_d = (days[0] - timedelta(days=2)).strftime("%Y-%m-%d")
    to_d = (days[-1] + timedelta(days=1)).strftime("%Y-%m-%d")

    # Pre-fetch index context per day
    nifty_daily = fetch_upstox_historical("NIFTY", unit="days", interval=1,
                                          from_date=from_d, to_date=to_d)
    vix_daily = fetch_upstox_historical("VIX", unit="days", interval=1,
                                        from_date=from_d, to_date=to_d)
    nifty_5m = fetch_upstox_historical("NIFTY", unit="minutes", interval=5,
                                       from_date=from_d, to_date=to_d)

    def nifty_pct_for(day):
        if nifty_5m.empty:
            return 0.0
        d = nifty_5m[nifty_5m.index.date == day]
        if d.empty:
            return 0.0
        return round((float(d["Close"].iloc[-1]) - float(d["Open"].iloc[0])) / float(d["Open"].iloc[0]) * 100, 2)

    def vix_for(day):
        if vix_daily.empty:
            return 15.0
        d = vix_daily[vix_daily.index.date <= day]
        return float(d["Close"].iloc[-1]) if not d.empty else 15.0

    per_day = {str(d): [] for d in days}
    total_evaluated = 0

    for idx, ticker in enumerate(universe):
        if progress:
            progress(idx + 1, len(universe), ticker)

        # daily history (once per stock) and 5-min over the range (once per stock)
        df_daily_all = fetch_upstox_historical(ticker, unit="days", interval=1,
                                               from_date=(days[0] - timedelta(days=420)).strftime("%Y-%m-%d"),
                                               to_date=to_d)
        df_5m_all = fetch_upstox_historical(ticker, unit="minutes", interval=5,
                                            from_date=from_d, to_date=to_d)
        if df_5m_all.empty or df_daily_all.empty:
            continue

        for day in days:
            day_5min = df_5m_all[df_5m_all.index.date == day]
            df_daily = df_daily_all[df_daily_all.index.date < day]
            if day_5min.empty or len(df_daily) < 30:
                continue
            total_evaluated += 1
            res = _stock_fires_on_day(day_5min, df_daily, vix_for(day), nifty_pct_for(day))
            if res.get("fired"):
                per_day[str(day)].append({
                    "ticker": ticker, "dir": res["dir"], "alpha_z": res["alpha_z"],
                    "instrument": res["instrument"], "target_pct": res["target_pct"],
                    "time": res["bar_time"], "entry": res["entry"], "target": res["target"],
                    "outcome": res["outcome"], "pnl_pct": res["pnl_pct"],
                    "exit": res["exit"], "exit_time": res["exit_time"],
                })

    counts = {d: len(names) for d, names in per_day.items()}
    avg = round(sum(counts.values()) / len(counts), 1) if counts else 0

    # Aggregate outcomes across all fired signals
    all_sigs = [s for names in per_day.values() for s in names]
    wins = [s for s in all_sigs if s["outcome"] == "WIN"]
    losses = [s for s in all_sigs if s["outcome"] == "LOSS"]
    forced = [s for s in all_sigs if s["outcome"] == "FORCED"]
    n = len(all_sigs)
    gross_win = sum(s["pnl_pct"] for s in all_sigs if s["pnl_pct"] > 0)
    gross_loss = abs(sum(s["pnl_pct"] for s in all_sigs if s["pnl_pct"] < 0))
    return {
        "days": [str(d) for d in days],
        "per_day": per_day,
        "counts": counts,
        "avg_per_day": avg,
        "universe_size": len(universe),
        "total_evaluated": total_evaluated,
        "outcomes": {
            "total": n,
            "wins": len(wins), "losses": len(losses), "forced": len(forced),
            "win_rate": round(len(wins) / n, 3) if n else 0,
            "total_pnl_pct": round(sum(s["pnl_pct"] for s in all_sigs), 2),
            "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else float("inf"),
        },
    }


def print_report(result: dict):
    print("\n" + "=" * 72)
    print("SIGNAL FREQUENCY + OUTCOME TEST")
    print("=" * 72)
    print(f"Universe: {result['universe_size']} stocks · Days tested: {len(result['days'])}")
    for day in result["days"]:
        names = result["per_day"][day]
        print(f"\n{day}  —  {len(names)} signal(s)")
        for s in names:
            mark = "✓ WIN " if s["outcome"] == "WIN" else ("✗ LOSS" if s["outcome"] == "LOSS" else "= FLAT")
            print(f"   {mark}  {s['ticker'].replace('.NS',''):12} {s['dir']:5} {s['instrument']:6} "
                  f"tgt{s['target_pct']:.0f}% in@{s['time']} {s['entry']:>8.2f}→{s['target']:>8.2f} · "
                  f"exit {s['exit']:>8.2f}@{s['exit_time']} ({s['pnl_pct']:+.2f}%)")
    o = result["outcomes"]
    print("\n" + "-" * 72)
    print(f"Signals: {o['total']}   ·   WINS {o['wins']}  LOSSES {o['losses']}  FORCED {o['forced']}")
    print(f"Win rate: {o['win_rate']:.0%}   ·   Profit factor: {o['profit_factor']}   ·   "
          f"Net: {o['total_pnl_pct']:+.2f}% (sum of per-trade %)")
    avg = result["avg_per_day"]
    print(f"Frequency: {avg} names/day  {'✓ meets 1-2/day' if avg >= 1 else '✗ below 1/day'}")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    def prog(i, total, ticker):
        if i % 10 == 0 or i == total:
            print(f"  scanned {i}/{total} ... ({ticker})", flush=True)

    print("Running signal-frequency backtest (last 3 trading days, all 95 stocks)...")
    res = run_frequency_test(n_days=3, progress=prog)
    print_report(res)
