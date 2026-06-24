"""
Paper-trade outcome resolver.

The trade log records signals as PENDING; this module CLOSES them — marking WIN / LOSS
by replaying the OPTION premium from signal time: buy OTM+1 (config), book at
+PREMIUM_TARGET_PCT%, cut at -PREMIUM_STOP_PCT%, else force-close after the kill switch.
Run each scan so the TRADE LOG and win/loss rate stay live.
"""
import time
import logging
from datetime import datetime

from engine.config import (IST, OPTION_STRIKE_OFFSET, PREMIUM_TARGET_PCT,
                           PREMIUM_STOP_PCT, MARKET_CLOSE,
                           ORB_VWAP_EXIT_MODE, ORB_VWAP_STOP_PCT)
from engine.data_fetcher import fetch_upstox_intraday, fetch_upstox_historical
from engine.options import get_option_by_offset, fetch_option_premium_5min
from engine.orb_vwap_live import _near_future_key, _vwap, trend_ride_walk

logger = logging.getLogger(__name__)


def _to_dt(iso: str):
    try:
        return datetime.fromisoformat(iso)
    except Exception:
        return None


def _opt_prem(opt_key, sig_date, today, attempts=3):
    """Option premium 5-min series for the signal date. TODAY must use the intraday
    endpoint (the historical endpoint lags T+1, so it's empty for today).

    Retries a few times: a single transient empty response at the 15:30 EOD book would
    otherwise strand the trade PENDING forever (the data is almost always there moments
    later — that exact glitch orphaned a BankNifty trade once)."""
    for i in range(attempts):
        df = fetch_upstox_intraday(opt_key, 5) if sig_date == today else fetch_option_premium_5min(opt_key, sig_date)
        if df is not None and not df.empty:
            return df
        if i < attempts - 1:
            time.sleep(0.4)
    return df  # last attempt (possibly empty — caller handles)


def resolve_pending(trade_log) -> int:
    """Resolve PENDING paper trades on the option premium, using each trade's OWN
    signal-date data (so yesterday's open trades close too). Returns count closed."""
    now = datetime.now(IST)
    today = now.date()
    close_t = datetime.strptime(MARKET_CLOSE, "%H:%M").time()  # 15:30 — book at the close
    resolved = 0

    for t in trade_log.trades:
        if t.get("outcome") is not None:
            continue
        st = _to_dt(t.get("signal_time", ""))
        ticker, direction = t.get("ticker"), t.get("direction")
        if not st or not ticker:
            continue
        sig_date = st.date()
        # a past session is fully settled; today's only after the kill switch / weekend
        session_over = (sig_date < today) or (now.time() >= close_t) or (now.weekday() >= 5)
        try:
            opt_key = t.get("option_key")

            # ── ORB+VWAP index trend-ride exit: ride the futures vs VWAP, hard -stop% ──
            if (opt_key and t.get("strategy") == "ORB+VWAP"
                    and ORB_VWAP_EXIT_MODE == "trend_ride"):
                prem = _opt_prem(opt_key, sig_date, today)
                if prem.empty:
                    continue
                esub = prem["Close"][prem.index <= st]
                entry = t.get("entry_premium") or (float(esub.iloc[-1]) if len(esub)
                                                   else float(prem["Close"].iloc[0]))
                if not entry or entry <= 0:
                    continue
                lot = int(t.get("qty", 0) or 0)
                t["lot"] = lot
                # futures + VWAP for the signal date (intraday if today, else historical)
                fkey = _near_future_key(ticker)
                fut = None
                if fkey:
                    if sig_date == today:
                        fut = fetch_upstox_intraday(fkey, 5)
                    else:
                        fut = fetch_upstox_historical(fkey, unit="minutes", interval=5,
                                                      from_date=sig_date.isoformat(),
                                                      to_date=sig_date.isoformat())
                if fut is not None and not fut.empty:
                    fut = fut[fut.index.date == sig_date]
                if fut is not None and not fut.empty:
                    vw = _vwap(fut)
                    reason, exitp, _pnl, _armed = trend_ride_walk(direction, st, entry, fut, vw, prem)
                else:
                    # no futures data → degrade to premium-only: -stop% or EOD
                    reason, exitp = "END", float(prem["Close"].iloc[-1])
                    stop_prem = entry * (1 - ORB_VWAP_STOP_PCT / 100)
                    for px in prem["Close"][prem.index > st]:
                        if float(px) <= stop_prem:
                            reason, exitp = "STOP", stop_prem
                            break
                if reason == "STOP":
                    outcome = "LOSS"
                elif reason == "VWAP":
                    outcome = "WIN" if exitp > entry else "LOSS"
                else:  # END — still riding intraday, or EOD force-close
                    if not session_over:
                        continue
                    exitp = float(prem["Close"].iloc[-1])
                    outcome = "WIN" if exitp > entry else "LOSS"
                t["entry_premium"] = round(entry, 2)
                t["exit_premium"] = round(float(exitp), 2)
                trade_log.book_trade(t, outcome, (float(exitp) - entry) * lot)
                resolved += 1
                continue

            # ── signals carrying their own option key + premium levels (fixed target) ──
            tgt_prem, stp_prem = t.get("target_premium"), t.get("stop_premium")
            if opt_key and tgt_prem and stp_prem:
                prem = _opt_prem(opt_key, sig_date, today)
                if prem.empty:
                    continue
                esub = prem["Close"][prem.index <= st]
                entry = t.get("entry_premium") or (float(esub.iloc[-1]) if len(esub)
                                                   else float(prem["Close"].iloc[0]))
                if not entry or entry <= 0:
                    continue
                lot = int(t.get("qty", 0) or 0)
                t["lot"] = lot   # option lot for the capital/P&L calc
                outcome = exitp = None
                for px in prem["Close"][prem.index > st]:
                    px = float(px)
                    if px <= float(stp_prem):
                        outcome, exitp = "LOSS", float(stp_prem); break
                    if px >= float(tgt_prem):
                        outcome, exitp = "WIN", float(tgt_prem); break
                if outcome is None:
                    if not session_over:
                        continue
                    exitp = float(prem["Close"].iloc[-1])
                    outcome = "WIN" if exitp > entry else "LOSS"
                t["entry_premium"] = round(entry, 2)
                t["exit_premium"] = round(exitp, 2)
                trade_log.book_trade(t, outcome, (exitp - entry) * lot)
                resolved += 1
                continue

            # ── stock 3-Family signals — reconstruct OTM+1 / +10-20 from the underlying ──
            # stock 5-min for the SIGNAL date (intraday endpoint if today, else historical)
            if sig_date == today:
                d5 = fetch_upstox_intraday(ticker, 5)
            else:
                d5 = fetch_upstox_historical(ticker, unit="minutes", interval=5,
                                             from_date=sig_date.isoformat(),
                                             to_date=sig_date.isoformat())
            if d5.empty:
                continue
            sub = d5["Close"][d5.index <= st]
            spot = float(sub.iloc[-1]) if len(sub) else float(d5["Close"].iloc[0])

            opt_type = "CE" if direction == "LONG" else "PE"
            opt = get_option_by_offset(ticker, spot, sig_date, opt_type, OPTION_STRIKE_OFFSET)
            if not opt:
                continue
            prem = _opt_prem(opt["key"], sig_date, today)
            if prem.empty:
                continue

            esub = prem["Close"][prem.index <= st]
            entry = float(esub.iloc[-1]) if len(esub) else float(prem["Close"].iloc[0])
            if entry <= 0:
                continue
            lot = int(opt.get("lot", 0) or t.get("qty", 0) or 0)
            t["lot"] = lot   # option lot (NOT the underlying share qty) for capital/P&L
            tgt = entry * (1 + PREMIUM_TARGET_PCT / 100)
            stp = entry * (1 - PREMIUM_STOP_PCT / 100)

            outcome = exitp = None
            for px in prem["Close"][prem.index > st]:
                px = float(px)
                if px <= stp:
                    outcome, exitp = "LOSS", stp
                    break
                if px >= tgt:
                    outcome, exitp = "WIN", tgt
                    break

            if outcome is None:
                if not session_over:
                    continue  # still open intraday — leave PENDING
                exitp = float(prem["Close"].iloc[-1])          # force-close at EOD
                outcome = "WIN" if exitp > entry else "LOSS"

            pnl = (exitp - entry) * lot
            # stash the option entry/exit premium for display/audit
            t["entry_premium"] = round(entry, 2)
            t["exit_premium"] = round(exitp, 2)
            trade_log.book_trade(t, outcome, pnl)
            resolved += 1
        except Exception as e:
            logger.warning(f"resolve {ticker} failed: {e}")
    return resolved
