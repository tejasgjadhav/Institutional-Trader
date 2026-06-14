"""
Recent Option-Premium Backtest (BUY-only CALL/PUT)
─────────────────────────────────────────────────────────────────────────────
The definitive "does it work with options" test. Limited to RECENT sessions
because expired option contracts aren't in the free instrument master.

For each signal it BUYS the ATM option (CALL for LONG, PUT for SHORT), then
exits on an underlying trigger (favorable move = book, adverse move = cut) and
records the REAL option-premium P&L. Reports option win rate + premium expectancy.

Underlyings include indices (NIFTY, BANKNIFTY) + the stock universe.
"""
import logging
from datetime import datetime, timedelta
import pandas as pd

from engine.config import UNIVERSE, TRADING_START
from engine.data_fetcher import fetch_upstox_historical
from engine.signals import compute_all_families, is_orb_confirmed
from engine.options import get_atm_option, fetch_option_premium_5min

logger = logging.getLogger(__name__)

INDEX_UNDERLYINGS = ["NIFTY", "BANKNIFTY"]   # buy index options (low capital, liquid)


def _trading_days(n):
    days, d = [], datetime.now() - timedelta(days=1)
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d.date())
        d -= timedelta(days=1)
    return sorted(days)


def _bmin(ts): return ts.hour * 60 + ts.minute
def _hhmm(s): h, m = map(int, s.split(":")); return h*60+m


def collect_option_trades(n_days=20, max_stocks=None, cutoff="13:00", progress=None):
    """
    Replay gates on indices + stocks over recent days. For each signal, BUY the
    ATM option and capture the aligned premium path. Returns trade dicts with the
    premium series so exits can be swept.
    """
    days = _trading_days(n_days)
    unders = INDEX_UNDERLYINGS + (UNIVERSE[:max_stocks] if max_stocks else UNIVERSE)
    from_d = (days[0] - timedelta(days=3)).strftime("%Y-%m-%d")
    to_d = (days[-1] + timedelta(days=1)).strftime("%Y-%m-%d")
    start_min, cut_min = _hhmm(TRADING_START), _hhmm(cutoff)

    nifty5 = fetch_upstox_historical("NIFTY", unit="minutes", interval=5, from_date=from_d, to_date=to_d)
    vixd = fetch_upstox_historical("VIX", unit="days", interval=1, from_date=from_d, to_date=to_d)
    def npct(day):
        if nifty5.empty: return 0.0
        d = nifty5[nifty5.index.date == day]
        return 0.0 if d.empty else round((float(d.Close.iloc[-1])-float(d.Open.iloc[0]))/float(d.Open.iloc[0])*100,2)
    def vix(day):
        if vixd.empty: return 15.0
        d = vixd[vixd.index.date <= day]; return float(d.Close.iloc[-1]) if not d.empty else 15.0

    trades = []
    for k, under in enumerate(unders):
        if progress: progress(k+1, len(unders), under)
        daily = fetch_upstox_historical(under, unit="days", interval=1,
                  from_date=(days[0]-timedelta(days=420)).strftime("%Y-%m-%d"), to_date=to_d)
        five = fetch_upstox_historical(under, unit="minutes", interval=5, from_date=from_d, to_date=to_d)
        if five.empty or daily.empty: continue

        for day in days:
            d5 = five[five.index.date == day]
            dfd = daily[daily.index.date < day]
            if len(d5) < 7 or len(dfd) < 30: continue
            v, np_ = vix(day), npct(day)
            for i in range(6, len(d5)):
                ts = d5.index[i]; m = _bmin(ts)
                if m < start_min: continue
                if m > cut_min: break
                part = d5.iloc[:i+1]
                sig = compute_all_families(under, part, dfd, vix=v, nifty_pct=np_)
                if not sig["passes_gate_1"]: continue
                ok, odir, _ = is_orb_confirmed(part)
                if not (ok and odir == sig["direction"]): continue

                opt_type = "CE" if sig["direction"] == "LONG" else "PE"
                spot = float(part.Close.iloc[-1])
                opt = get_atm_option(under, spot, day, opt_type)
                if not opt: break
                prem = fetch_option_premium_5min(opt["key"], day)
                if prem.empty: break
                sub = prem[prem.index <= ts]
                if sub.empty: break
                entry_prem = float(sub.Close.iloc[-1])
                if entry_prem <= 0: break

                # forward: align underlying bar -> option premium bar by timestamp
                fwd_u = d5.iloc[i+1:]
                rows = []
                for b in fwd_u.itertuples():
                    t = b.Index
                    pm = prem[prem.index == t]
                    pclose = float(pm.Close.iloc[0]) if not pm.empty else None
                    rows.append((float(b.High), float(b.Low), float(b.Close), pclose))
                if not rows: break

                trades.append({
                    "under": under, "day": str(day), "entry_time": m,
                    "direction": sig["direction"], "opt_type": opt_type,
                    "strike": opt["strike"], "expiry": opt["expiry_date"], "lot": opt.get("lot"),
                    "alpha_z": round(sig["alpha_z"], 3), "breadth": sig["breadth"],
                    "spot_entry": round(spot, 2), "entry_prem": round(entry_prem, 2),
                    "is_long": sig["direction"] == "LONG", "path": rows,
                })
                break
    return trades


def simulate_option(tr, target_pct, stop_pct):
    """
    Exit on underlying trigger; realise the actual option premium P&L.
      LONG (CALL): win when underlying +target%, stop when -stop%
      SHORT (PUT): win when underlying -target%, stop when +stop%
    Returns (outcome, premium_pnl_pct).
    """
    spot0, prem0, long = tr["spot_entry"], tr["entry_prem"], tr["is_long"]
    if long: up, dn = spot0*(1+target_pct/100), spot0*(1-stop_pct/100)
    else:    up, dn = spot0*(1-target_pct/100), spot0*(1+stop_pct/100)
    last_prem = prem0
    for hi, lo, cl, pclose in tr["path"]:
        if pclose is not None: last_prem = pclose
        hit_win = (hi >= up) if long else (lo <= up)
        hit_stop = (lo <= dn) if long else (hi >= dn)
        if hit_stop:  # stop checked first (conservative)
            return ("LOSS", round((last_prem/prem0-1)*100, 2))
        if hit_win:
            return ("WIN", round((last_prem/prem0-1)*100, 2))
    return ("FORCED", round((last_prem/prem0-1)*100, 2))


def simulate_premium(tr, prem_target_pct, prem_stop_pct):
    """
    Exit directly on the OPTION PREMIUM (how you actually trade a bought option):
      WIN  when premium >= entry*(1+target%)
      LOSS when premium <= entry*(1-stop%)
    Returns (outcome, premium_pnl_pct).
    """
    prem0 = tr["entry_prem"]
    tgt, stp = prem0*(1+prem_target_pct/100), prem0*(1-prem_stop_pct/100)
    last = prem0
    for _, _, _, pclose in tr["path"]:
        if pclose is None:
            continue
        last = pclose
        if pclose <= stp:
            return ("LOSS", round((stp/prem0-1)*100, 2))
        if pclose >= tgt:
            return ("WIN", round((tgt/prem0-1)*100, 2))
    return ("FORCED", round((last/prem0-1)*100, 2))


def sweep_premium(trades, targets, stops):
    """Sweep premium target/stop. WIN = exited green. Reports win rate + expectancy."""
    rows = []
    n_days = len({t["day"] for t in trades}) or 1
    for t in targets:
        for s in stops:
            res = [simulate_premium(tr, t, s) for tr in trades]
            n = len(res)
            if not n: continue
            wins = sum(1 for o in res if o[1] > 0)
            net = sum(o[1] for o in res)
            rows.append({
                "p_target": t, "p_stop": s, "trades": n, "per_day": round(n/n_days, 1),
                "win_rate": round(wins/n, 3), "wins": wins,
                "prem_exp": round(net/n, 2), "prem_net": round(net, 1),
                "rr": round(t/s, 2),
            })
    rows.sort(key=lambda r: (r["win_rate"], r["prem_exp"]), reverse=True)
    return rows


def sweep_options(trades, targets, stops):
    rows = []
    n_days = len({t["day"] for t in trades}) or 1
    for t in targets:
        for s in stops:
            res = [simulate_option(tr, t, s) for tr in trades]
            n = len(res)
            if not n: continue
            # WIN = premium ended positive (you booked a profit on the option)
            wins = sum(1 for o in res if o[1] > 0)
            net = sum(o[1] for o in res)
            rows.append({
                "u_target": t, "u_stop": s, "trades": n, "per_day": round(n/n_days,1),
                "win_rate": round(wins/n, 3), "wins": wins,
                "prem_exp": round(net/n, 2), "prem_net": round(net, 1),
            })
    rows.sort(key=lambda r: (r["win_rate"], r["prem_exp"]), reverse=True)
    return rows
