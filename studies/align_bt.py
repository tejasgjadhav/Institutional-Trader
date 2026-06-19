"""30-day backtest: market-alignment filter on the 3-Family stock signals.
Aligned = LONG when Nifty is up intraday / SHORT when Nifty is down. Exit +10/-20 (live).
Reports win% and rupee P&L (1 lot each) for ALL vs ALIGNED vs NOT-aligned."""
import sys
from datetime import datetime, timedelta
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from engine.config import (UNIVERSE, TRADING_START, NO_NEW_TRADES_AFTER,
                           OPTION_STRIKE_OFFSET, PREMIUM_TARGET_PCT, PREMIUM_STOP_PCT)
from engine.data_fetcher import fetch_upstox_historical
from engine.signals import compute_all_families, is_orb_confirmed
from engine.options import get_option_by_offset, fetch_option_premium_5min
from engine.backtest120 import _fetch_5min_chunked

def tdays(n):
    days, d = [], datetime.now() - timedelta(days=1)
    while len(days) < n:
        if d.weekday() < 5: days.append(d.date())
        d -= timedelta(days=1)
    return sorted(days)
def bmin(ts): return ts.hour * 60 + ts.minute
def hhmm(s): h, m = map(int, s.split(":")); return h * 60 + m

def outcome(prem, ts, tgt, stp):
    sub = prem[prem.index <= ts]
    if sub.empty: return None, None
    e = float(sub.Close.iloc[-1])
    if e <= 0: return None, None
    T, S, last = e * (1 + tgt / 100), e * (1 - stp / 100), e
    for v in prem[prem.index > ts].Close:
        last = float(v)
        if last <= S: return -stp, e
        if last >= T: return tgt, e
    return round((last / e - 1) * 100, 2), e

def collect(n_days=30):
    days = tdays(n_days)
    a, b = days[0] - timedelta(days=3), days[-1] + timedelta(days=1)
    start_min, cut_min = hhmm(TRADING_START), hhmm(NO_NEW_TRADES_AFTER)
    nifty5 = _fetch_5min_chunked("NIFTY", a, b)
    out = []
    for k, under in enumerate(UNIVERSE):
        if (k + 1) % 25 == 0: print(f"  ...{k+1}/{len(UNIVERSE)}", flush=True)
        daily = fetch_upstox_historical(under, unit="days", interval=1,
                from_date=(days[0] - timedelta(days=40)).strftime("%Y-%m-%d"),
                to_date=b.strftime("%Y-%m-%d"))
        five = _fetch_5min_chunked(under, a, b)
        if five.empty or daily.empty: continue
        for day in days:
            d5 = five[five.index.date == day]
            if len(d5) < 7: continue
            dfd = daily[daily.index.date < day]
            if len(dfd) < 20: continue
            nday = nifty5[nifty5.index.date == day]
            nopen = float(nday.Open.iloc[0]) if not nday.empty else 0
            for i in range(6, len(d5)):
                ts = d5.index[i]; m = bmin(ts)
                if m < start_min: continue
                if m > cut_min: break
                part = d5.iloc[:i + 1]
                sig = compute_all_families(under, part, dfd, vix=14.0, nifty_pct=0.0)
                if not sig["passes_gate_1"]: continue
                ok, od, vr = is_orb_confirmed(part)
                if not (ok and od == sig["direction"]): continue
                direction = sig["direction"]
                nifty_dir = 0
                if not nday.empty and nopen:
                    ns = nday[nday.index <= ts]
                    if not ns.empty:
                        nc = float(ns.Close.iloc[-1])
                        nifty_dir = 1 if nc > nopen else (-1 if nc < nopen else 0)
                aligned = 1 if ((direction == "LONG" and nifty_dir == 1) or
                                (direction == "SHORT" and nifty_dir == -1)) else 0
                spot = float(part.Close.iloc[-1])
                opt = get_option_by_offset(under, spot, day, "CE" if direction == "LONG" else "PE", OPTION_STRIKE_OFFSET)
                if not opt: break
                prem = fetch_option_premium_5min(opt["key"], day)
                if prem.empty: break
                pnl, entry = outcome(prem, ts, PREMIUM_TARGET_PCT, PREMIUM_STOP_PCT)
                if pnl is None: break
                lot = int(opt.get("lot", 0) or 0)
                out.append({"day": str(day), "under": under, "dir": direction,
                            "aligned": aligned, "pnl_pct": pnl, "entry": entry, "lot": lot})
                break
    return out

rows = collect(60)
def report(name, lst):
    if not lst: print(f"  {name:16}: none"); return
    n = len(lst); w = sum(1 for r in lst if r["pnl_pct"] > 0)
    pnl_rs = sum(r["entry"] * r["lot"] * r["pnl_pct"] / 100 for r in lst)
    cap = sum(r["entry"] * r["lot"] for r in lst)
    net = sum(r["pnl_pct"] for r in lst) / n
    print(f"  {name:16}: trades={n:3}  WIN={w/n*100:3.0f}%  net={net:+5.2f}%/trade  "
          f"P&L=Rs{pnl_rs:+11,.0f}  (on Rs{cap:,.0f} capital = {pnl_rs/cap*100:+.1f}%)")

print(f"\n=== 30-DAY · 3-Family stock signals · exit +{int(PREMIUM_TARGET_PCT)}%/-{int(PREMIUM_STOP_PCT)}% (live) ===")
print(f"  days {rows[0]['day'] if rows else '?'} .. {rows[-1]['day'] if rows else '?'}")
report("ALL signals", rows)
report("ALIGNED only", [r for r in rows if r["aligned"] == 1])
report("NOT aligned", [r for r in rows if r["aligned"] == 0])
