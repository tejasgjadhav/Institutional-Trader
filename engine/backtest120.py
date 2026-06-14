"""
120-Day Underlying Backtest + Win-Rate Optimizer
─────────────────────────────────────────────────────────────────────────────
Collects every signal over a long window (default 120 trading days) on the
UNDERLYING (equity/futures — options can't be backtested this far back because
expired contracts are gone from the free instrument master).

Each signal records metadata (alpha_z, breadth, entry_time, direction) and its
forward price path. Then we sweep strategy filters (alpha threshold, breadth,
cutoff) and exit rules (target, with stop = target/2 → fixed 2:1 reward:risk)
to MAXIMISE WIN RATE.

A trade log for the chosen combo is written to data/trade_log_backtest.json.
"""
import json
import logging
from datetime import datetime, timedelta
import pandas as pd

from engine.config import UNIVERSE, TRADING_START, DATA_DIR
from engine.data_fetcher import fetch_upstox_historical
from engine.signals import compute_all_families, is_orb_confirmed
from engine.portfolio import decide_instrument

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


def _fetch_5min_chunked(ticker: str, from_date, to_date, chunk_days: int = 20) -> pd.DataFrame:
    """Fetch 5-min candles over a long range by stitching ~chunk_days windows."""
    frames = []
    start = from_date
    while start <= to_date:
        end = min(start + timedelta(days=chunk_days), to_date)
        df = fetch_upstox_historical(ticker, unit="minutes", interval=5,
                                     from_date=start.strftime("%Y-%m-%d"),
                                     to_date=end.strftime("%Y-%m-%d"))
        if not df.empty:
            frames.append(df)
        start = end + timedelta(days=1)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames)
    out = out[~out.index.duplicated(keep="first")].sort_index()
    return out


def collect120(n_days: int = 120, max_stocks: int = None, progress=None) -> list:
    """
    Collect signals over n_days. Returns list of events:
      {ticker, day, entry_time(min), direction, instrument, alpha_z, breadth,
       entry_price, path:[(high,low,close)...]}   # underlying, entry+1 .. EOD
    Captures the FIRST bar that passes the base gate (|alpha-z|>0.55, >=2/3).
    """
    days = _trading_days(n_days)
    universe = UNIVERSE[:max_stocks] if max_stocks else UNIVERSE
    from_d = days[0] - timedelta(days=3)
    to_d = days[-1] + timedelta(days=1)
    start_min = _hhmm(TRADING_START)
    latest_min = _hhmm("15:00")

    # index context once
    nifty_5m = _fetch_5min_chunked("NIFTY", from_d, to_d)
    vix_daily = fetch_upstox_historical("VIX", unit="days", interval=1,
                                        from_date=from_d.strftime("%Y-%m-%d"),
                                        to_date=to_d.strftime("%Y-%m-%d"))

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
                                            from_date=(days[0]-timedelta(days=420)).strftime("%Y-%m-%d"),
                                            to_date=to_d.strftime("%Y-%m-%d"))
        five_all = _fetch_5min_chunked(ticker, from_d, to_d)
        if five_all.empty or daily_all.empty:
            continue

        for day in days:
            day5 = five_all[five_all.index.date == day]
            dfd = daily_all[daily_all.index.date < day]
            if len(day5) < 7 or len(dfd) < 30:
                continue
            v, npct = vix(day), nifty_pct(day)
            for i in range(6, len(day5)):
                ts = day5.index[i]
                m = _bar_min(ts)
                if m < start_min:  continue
                if m > latest_min: break
                partial = day5.iloc[:i+1]
                sig = compute_all_families(ticker, partial, dfd, vix=v, nifty_pct=npct)
                if not sig["passes_gate_1"]:
                    continue
                orb_ok, orb_dir, _ = is_orb_confirmed(partial)
                if not (orb_ok and orb_dir == sig["direction"]):
                    continue
                dec = decide_instrument(sig["alpha_z"], sig["direction"])
                entry = float(partial["Close"].iloc[-1])
                fwd = day5.iloc[i+1:]
                path = [(float(b.High), float(b.Low), float(b.Close)) for b in fwd.itertuples()]
                if not path:
                    break
                events.append({
                    "ticker": ticker, "day": str(day), "entry_time": m,
                    "direction": sig["direction"], "instrument": dec["instrument"],
                    "alpha_z": round(sig["alpha_z"], 3), "breadth": sig["breadth"],
                    "entry_price": round(entry, 2),
                    "is_long": (sig["direction"] == "LONG"), "path": path,
                })
                break
    return events


def _simulate(event: dict, target_pct: float, stop_pct: float) -> dict:
    """Simulate with stop checked first (conservative). Returns outcome + pnl%."""
    entry = event["entry_price"]
    long = event["is_long"]
    if long:
        tgt, stp = entry*(1+target_pct/100), entry*(1-stop_pct/100)
    else:
        tgt, stp = entry*(1-target_pct/100), entry*(1+stop_pct/100)
    last = entry
    for hi, lo, cl in event["path"]:
        last = cl
        if long:
            if lo <= stp: return {"outcome": "LOSS", "pnl": -stop_pct, "exit": round(stp,2)}
            if hi >= tgt: return {"outcome": "WIN", "pnl": target_pct, "exit": round(tgt,2)}
        else:
            if hi >= stp: return {"outcome": "LOSS", "pnl": -stop_pct, "exit": round(stp,2)}
            if lo <= tgt: return {"outcome": "WIN", "pnl": target_pct, "exit": round(tgt,2)}
    pnl = (last/entry-1)*100 if long else (entry/last-1)*100
    return {"outcome": "FORCED", "pnl": round(pnl,2), "exit": round(last,2)}


def sweep_winrate(events, cutoffs, targets, alpha_min_list, breadth_list) -> list:
    """
    Sweep filters + target (stop = target/2, fixed 2:1). Counts FORCED-positive
    as wins-by-drift separately. Ranked by win rate (target-hit only).
    """
    n_days = len({e["day"] for e in events}) or 1
    rows = []
    for amin in alpha_min_list:
        for bmin in breadth_list:
            for c in cutoffs:
                cm = _hhmm(c)
                elig = [e for e in events
                        if abs(e["alpha_z"]) >= amin and e["breadth"] >= bmin and e["entry_time"] <= cm]
                if not elig:
                    continue
                for t in targets:
                    s = t/2.0   # fixed 2:1 reward:risk
                    outs = [_simulate(e, t, s) for e in elig]
                    n = len(outs)
                    w = sum(1 for o in outs if o["outcome"]=="WIN")
                    l = sum(1 for o in outs if o["outcome"]=="LOSS")
                    f = sum(1 for o in outs if o["outcome"]=="FORCED")
                    net = round(sum(o["pnl"] for o in outs), 1)
                    # expectancy per trade (%)
                    exp = round(net/n, 3) if n else 0
                    rows.append({
                        "alpha_min": amin, "breadth": bmin, "cutoff": c,
                        "target": t, "stop": round(s,2),
                        "signals": n, "per_day": round(n/n_days,1),
                        "win_rate": round(w/n,3), "w": w, "l": l, "f": f,
                        "net_pct": net, "exp_pct": exp,
                    })
    rows.sort(key=lambda r: (r["win_rate"], r["exp_pct"]), reverse=True)
    return rows


def build_trade_log(events, target_pct, alpha_min=0.55, breadth_min=2, cutoff="15:00") -> list:
    """Full trade log for one rule (stop = target/2)."""
    cm = _hhmm(cutoff); s = target_pct/2.0
    log = []
    for e in sorted(events, key=lambda x: (x["day"], x["entry_time"])):
        if abs(e["alpha_z"]) < alpha_min or e["breadth"] < breadth_min or e["entry_time"] > cm:
            continue
        r = _simulate(e, target_pct, s)
        log.append({
            "day": e["day"], "ticker": e["ticker"].replace(".NS",""),
            "dir": e["direction"], "instrument": e["instrument"],
            "entry_time": f"{e['entry_time']//60:02d}:{e['entry_time']%60:02d}",
            "entry": e["entry_price"], "alpha_z": e["alpha_z"], "breadth": e["breadth"],
            "target_pct": target_pct, "stop_pct": round(s,2),
            "outcome": r["outcome"], "exit": r["exit"], "pnl_pct": r["pnl"],
        })
    return log


def print_sweep(rows, top=25, title="WIN-RATE SWEEP (stop = target/2, 2:1 R:R)"):
    print("\n"+"="*100)
    print(title+"  —  ranked by win rate"); print("="*100)
    print(f"{'aMin':>4} {'br':>2} {'cut':>5} {'tgt%':>5} {'stop%':>5} {'sig':>5} {'/day':>5} "
          f"{'WIN%':>6} {'W/L/F':>12} {'net%':>8} {'exp%':>7}")
    print("-"*100)
    for r in rows[:top]:
        print(f"{r['alpha_min']:>4} {r['breadth']:>2} {r['cutoff']:>5} {r['target']:>5} {r['stop']:>5} "
              f"{r['signals']:>5} {r['per_day']:>5} {r['win_rate']*100:>5.0f}% "
              f"{r['w']}/{r['l']}/{r['f']:>3} {r['net_pct']:>8} {r['exp_pct']:>7}")
    print("="*100+"\n")
