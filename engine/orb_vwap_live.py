"""
ORB+VWAP Index Strategy — LIVE (parallel, paper-mode forward test).

Runs ALONGSIDE the 3-Family Alpha system. For NIFTY & BANKNIFTY each scan:
  - 15-min opening range on the index FUTURES (futures carry volume -> VWAP).
  - LONG (buy CALL) when futures breaks ORB high, holds ABOVE VWAP, and the 30-min
    trend is up; SHORT (buy PUT) on the mirror. New entries only before the cutoff.
  - CLEAN-TREND filter: only enter when VWAP is sloped the trade's way AND price is
    already >0.25% extended from the day's open (cuts marginal, chop-prone breaks).
  - Skip the option's own expiry day (0-DTE spikes).
  - One signal per index per day (the first qualifying bar — stable across scans).
  - Buy ATM option. Exit = TREND-RIDE: ride the winner, exit only when the futures
    reclaim VWAP after +ORB_VWAP_ARM_PCT% profit; hard -ORB_VWAP_STOP_PCT% stop; else
    square off at the close. (Replaced the old fixed +20% target.)

Returns one row per index (a live signal, or a WATCHING/SKIP placeholder) for the
dedicated ORB+VWAP section on the PM DECISIONS tab.

Backtests: the old fixed +20% target lost -2.6%/trade (27% win) over 60 days because it
capped winners while taking full -20% stops. Trend-ride + clean filter: 63% win,
+0.8%/trade gross (30d: 65% win, +1.2%) — roughly breakeven net of costs. Still a
FORWARD-TEST: marginal and fragile out-of-sample, not proven profitable.
"""
import json
import gzip
import logging
import requests
from datetime import datetime
import pandas as pd

from engine.config import (
    IST, SCAN_INDICES, ORB_VWAP_ENABLED, ORB_VWAP_TARGET_PCT, ORB_VWAP_STOP_PCT,
    ORB_VWAP_ENTRY_CUTOFF, ORB_VWAP_STRIKE_OFFSET, ORB_VWAP_TREND_BARS,
    ORB_VWAP_EXIT_MODE, ORB_VWAP_ARM_PCT, ORB_VWAP_CLEAN_TREND,
)
from engine.data_fetcher import fetch_upstox_intraday, fetch_upstox_ltp
from engine.options import get_option_by_offset

logger = logging.getLogger(__name__)

_COMPLETE_URL = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
_FUT_CACHE = {"date": None, "keys": {}}
_INDEXES = [i for i in SCAN_INDICES if i in ("NIFTY", "BANKNIFTY")]


def _near_future_key(index: str):
    """Near-month NIFTY/BANKNIFTY future instrument key, cached per day."""
    today = datetime.now(IST).date()
    if _FUT_CACHE["date"] != today:
        try:
            raw = json.loads(gzip.decompress(requests.get(_COMPLETE_URL, timeout=60).content))
        except Exception as e:
            logger.warning(f"ORB+VWAP futures master fetch failed: {e}")
            return _FUT_CACHE["keys"].get(index)
        fut = {}
        for i in raw:
            if (i.get("segment") == "NSE_FO" and i.get("instrument_type") == "FUT"
                    and (i.get("name") or "") in ("NIFTY", "BANKNIFTY")):
                fut.setdefault(i["name"], []).append((int(i["expiry"]), i["instrument_key"]))
        dm = int(datetime(today.year, today.month, today.day).timestamp() * 1000)
        keys = {}
        for nm, lst in fut.items():
            lst.sort()
            near = [k for e, k in lst if e >= dm]
            keys[nm] = near[0] if near else (lst[-1][1] if lst else None)
        _FUT_CACHE.update(date=today, keys=keys)
    return _FUT_CACHE["keys"].get(index)


def _vwap(df: pd.DataFrame) -> pd.Series:
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    return (tp * df["Volume"]).cumsum() / df["Volume"].cumsum()


def _bmin(ts) -> int:
    return ts.hour * 60 + ts.minute


def _hhmm(s: str) -> int:
    h, m = map(int, s.split(":"))
    return h * 60 + m


def trend_ride_walk(direction, ets, entry_prem, fut_df, vw, prem,
                    stop_pct=ORB_VWAP_STOP_PCT, arm_pct=ORB_VWAP_ARM_PCT):
    """Replay the trend-ride exit on the futures bars after entry.

    Rules (matches the 'breathe' backtest config):
      - HARD STOP: option premium <= entry*(1-stop_pct/100)            -> reason 'STOP'
      - ARM:       once premium >= +arm_pct%, the VWAP exit goes live
      - VWAP EXIT: armed AND futures close reclaims VWAP (LONG: below,
                   SHORT: above)                                       -> reason 'VWAP'
      - else ride to the end of available bars                         -> reason 'END'

    Returns (reason, exit_prem, pnl_pct, armed). 'END' means the caller decides
    ACTIVE (still intraday) vs EOD force-close.
    """
    stop_prem = entry_prem * (1 - stop_pct / 100)
    armed = False
    exit_prem, pnl = entry_prem, 0.0
    for ts in fut_df.index[fut_df.index > ets]:
        fc = float(fut_df["Close"].loc[ts])
        vv = float(vw.loc[ts]) if ts in vw.index else None
        psub = prem["Close"][prem.index <= ts]
        if psub.empty:
            continue
        cur = float(psub.iloc[-1])
        exit_prem = cur
        pnl = (cur / entry_prem - 1) * 100
        if cur <= stop_prem:
            return "STOP", round(stop_prem, 2), round(-stop_pct, 2), armed
        if pnl >= arm_pct:
            armed = True
        if armed and vv is not None and ((fc < vv) if direction == "LONG" else (fc > vv)):
            return "VWAP", round(cur, 2), round(pnl, 2), armed
    return "END", round(exit_prem, 2), round(pnl, 2), armed


def _build_row(index: str, direction: str, ets, fut_spot: float,
               fut_df=None, vw=None) -> dict:
    """Build the PM row for a fired ORB+VWAP signal: ATM option + live status."""
    today = datetime.now(IST).date()
    opt_type = "CE" if direction == "LONG" else "PE"

    # index spot for strike selection (fall back to futures price)
    ltp = fetch_upstox_ltp(index)
    spot = ltp.get("price") if ltp.get("success") and ltp.get("price") else fut_spot

    opt = get_option_by_offset(index, spot, today, opt_type, ORB_VWAP_STRIKE_OFFSET)
    if not opt:
        return {"index": index, "status": "NO OPTION"}
    if opt.get("expiry_date", "") == str(today):
        return {"index": index, "status": "SKIP (expiry day)"}

    prem = fetch_upstox_intraday(opt["key"], 5)
    if prem.empty:
        return {"index": index, "status": "WATCHING (no premium yet)"}

    # entry premium = option premium at/just after the signal bar
    psub = prem["Close"][prem.index <= ets]
    entry = float(psub.iloc[-1]) if len(psub) else float(prem["Close"].iloc[0])
    if entry <= 0:
        return {"index": index, "status": "NO PREMIUM"}

    stop = entry * (1 - ORB_VWAP_STOP_PCT / 100)

    # live current premium
    lt = fetch_upstox_ltp(opt["key"])
    current = lt.get("price") if lt.get("success") and lt.get("price") else float(prem["Close"].iloc[-1])

    # ── status ──
    fixed_target = ORB_VWAP_EXIT_MODE == "fixed_target"
    target = entry * (1 + ORB_VWAP_TARGET_PCT / 100) if fixed_target else None
    if fixed_target:
        status = "● ACTIVE"
        for px in prem["Close"][prem.index > ets]:
            if float(px) <= stop:
                status = "STOPPED -20%"; break
            if float(px) >= target:
                status = "TARGET +20%"; break
        exit_rule = f"+{int(ORB_VWAP_TARGET_PCT)}% / -{int(ORB_VWAP_STOP_PCT)}%"
    else:
        # trend-ride: ride the futures vs VWAP, hard -stop%; needs the futures frame
        exit_rule = "VWAP-break · -20% stop"
        if fut_df is not None and vw is not None and not fut_df.empty:
            reason, exitp, pnl, armed = trend_ride_walk(direction, ets, entry, fut_df, vw, prem)
            if reason == "STOP":
                status = "STOPPED -20%"
            elif reason == "VWAP":
                status = f"EXITED VWAP {pnl:+.0f}%"
            else:  # END — still riding intraday
                status = (f"● RIDING {pnl:+.0f}%" if armed else "● RIDING")
        else:
            status = "● RIDING"

    lot = int(opt.get("lot", 0) or 0)
    kind = "CALL" if opt_type == "CE" else "PUT"
    return {
        "index": index, "direction": direction, "kind": kind, "option_key": opt["key"],
        "time": ets.strftime("%H:%M") if hasattr(ets, "strftime") else str(ets),
        "fire_iso": ets.isoformat() if hasattr(ets, "isoformat") else None,
        "order_label": f"BUY {index} {int(opt['strike'])} {kind}",
        "strike": int(opt["strike"]), "expiry": opt.get("expiry_date", "—"),
        "entry": round(entry, 2),
        "target": round(target, 2) if target else None,
        "stop": round(stop, 2), "exit_rule": exit_rule,
        "current": round(float(current), 2) if current else None,
        "lot": lot, "capital": round(entry * lot, 0) if lot else None,
        "status": status,
    }


def _detect(index: str) -> dict:
    """Detect today's ORB+VWAP signal for one index; return a PM row dict."""
    fkey = _near_future_key(index)
    if not fkey:
        return {"index": index, "status": "NO FUTURES KEY"}
    df = fetch_upstox_intraday(fkey, 5)
    if df.empty or len(df) < 4:
        return {"index": index, "status": "WATCHING (no data yet)"}

    orb = df.iloc[:3]
    orb_hi, orb_lo = float(orb["High"].max()), float(orb["Low"].min())
    vw = _vwap(df)
    cutoff = _hhmm(ORB_VWAP_ENTRY_CUTOFF)

    day_open = float(df["Open"].iloc[0])
    for i in range(max(3, ORB_VWAP_TREND_BARS), len(df)):
        ts = df.index[i]
        m = _bmin(ts)
        if m < 9 * 60 + 30:
            continue
        if m >= cutoff:
            break
        c = float(df["Close"].iloc[i])
        v = float(vw.iloc[i])
        c30 = float(df["Close"].iloc[i - ORB_VWAP_TREND_BARS])
        # clean-trend filter: VWAP sloped the trade way (last 3 bars) AND price
        # extended >0.25% from the day's open. Cuts the marginal, chop-prone breaks.
        slope = v - float(vw.iloc[max(0, i - 3)])
        dmove = (c - day_open) / day_open if day_open else 0.0
        long_clean  = (not ORB_VWAP_CLEAN_TREND) or (slope > 0 and dmove > 0.0025)
        short_clean = (not ORB_VWAP_CLEAN_TREND) or (slope < 0 and dmove < -0.0025)
        if c > orb_hi * 1.0007 and c > v and c > c30 and long_clean:
            return _build_row(index, "LONG", ts, c, df, vw)
        if c < orb_lo * 0.9993 and c < v and c < c30 and short_clean:
            return _build_row(index, "SHORT", ts, c, df, vw)
    return {"index": index, "status": "WATCHING (no ORB+VWAP break)"}


def scan_index_orbvwap() -> list:
    """One row per index (NIFTY, BANKNIFTY): a live ORB+VWAP signal or a placeholder."""
    if not ORB_VWAP_ENABLED:
        return []
    rows = []
    for idx in _INDEXES:
        try:
            rows.append(_detect(idx))
        except Exception as e:
            logger.warning(f"ORB+VWAP scan failed for {idx}: {e}")
            rows.append({"index": idx, "status": "ERROR"})
    return rows
