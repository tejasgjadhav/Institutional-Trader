"""
Data Utilities — Index closes (Nifty/BankNifty/VIX), API health check.
All via Upstox V3 (primary), no Yahoo latency.
"""
import logging
from datetime import datetime, timedelta

from engine.config import IST, MARKET_OPEN, MARKET_CLOSE
from engine.data_fetcher import (
    fetch_upstox_ltp, fetch_upstox_intraday, fetch_upstox_historical, fetch_historical
)

logger = logging.getLogger(__name__)


def _market_is_open() -> bool:
    """True during NSE trading hours (Mon–Fri, 09:15–15:30 IST)."""
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    o = datetime.strptime(MARKET_OPEN, "%H:%M").time()
    c = datetime.strptime(MARKET_CLOSE, "%H:%M").time()
    return o <= now.time() <= c


def _index_last_close(index_name: str) -> float:
    """Most recent daily close for an index via Upstox."""
    df = fetch_upstox_historical(index_name, unit="days", interval=1)
    if not df.empty:
        return float(df["Close"].iloc[-1])
    return 0.0


# Cache of daily reference closes per index, refreshed once per calendar day.
# {index_name: {"date": date, "prev_close": float, "last_close": float}}
_ref_close_cache = {}


def _reference_closes(index_name: str):
    """
    (prev_close, last_close) for an index, cached per day.
    Daily closes don't change intraday, so we fetch them at most once per day —
    this is what makes the live poll fast (LTP only).
    """
    today = datetime.now(IST).date()
    cached = _ref_close_cache.get(index_name)
    if cached and cached["date"] == today:
        return cached["prev_close"], cached["last_close"]

    df = fetch_upstox_historical(index_name, unit="days", interval=1)
    prev_close = last_close = None
    if not df.empty and len(df) >= 2:
        prev_close = float(df["Close"].iloc[-2])
        last_close = float(df["Close"].iloc[-1])
    elif not df.empty:
        last_close = float(df["Close"].iloc[-1])

    _ref_close_cache[index_name] = {
        "date": today, "prev_close": prev_close, "last_close": last_close,
    }
    return prev_close, last_close


def _index_live_or_close(index_name: str) -> dict:
    """
    Live LTP if market open, else last session close — plus change vs the
    *previous* day's close (absolute + percent + direction).
    """
    prev_close, last_close = _reference_closes(index_name)

    if _market_is_open():
        # Intraday: live price vs the previous session close
        ltp = fetch_upstox_ltp(index_name)
        if ltp["success"] and ltp["price"]:
            price = ltp["price"]
            ref = last_close if last_close else prev_close
            source = "Upstox (live)"
        else:
            price = last_close if last_close else 0.0
            ref = prev_close
            source = "Upstox (last close)"
    else:
        # After hours: show last session close vs the prior session close
        price = last_close if last_close else 0.0
        ref = prev_close
        source = "Upstox (last close)"

    change = pct = 0.0
    if ref and price:
        change = price - ref
        pct = (change / ref) * 100 if ref else 0.0

    return {
        "ticker": index_name,
        "price": price,
        "change": round(change, 2),
        "pct": round(pct, 2),
        "direction": "UP" if change > 0 else ("DOWN" if change < 0 else "FLAT"),
        "source": source,
    }


def get_nifty_close() -> dict:
    """NIFTY 50 — live or last close."""
    d = _index_live_or_close("NIFTY")
    d["ticker"] = "NIFTY 50"
    return d


def get_banknifty_close() -> dict:
    """BANKNIFTY — live or last close."""
    d = _index_live_or_close("BANKNIFTY")
    d["ticker"] = "BANKNIFTY"
    return d


def get_vix_close() -> dict:
    """India VIX — live or last close."""
    d = _index_live_or_close("VIX")
    d["ticker"] = "VIX"
    if d["price"] == 0.0:
        d["price"] = 15.0  # safe default
    return d


def check_api_health() -> dict:
    """Check all Upstox data paths."""
    health = {
        "upstox_ltp": False,
        "upstox_intraday": False,
        "upstox_historical": False,
        "nifty": False,
        "banknifty": False,
        "vix": False,
        "timestamp": datetime.now().isoformat(),
    }

    # Upstox LTP (equity)
    try:
        health["upstox_ltp"] = fetch_upstox_ltp("TCS.NS")["success"]
    except Exception as e:
        logger.warning(f"LTP health check failed: {e}")

    # Upstox intraday (today's 5-min — empty when market closed, that's OK)
    try:
        df = fetch_upstox_intraday("TCS.NS", interval=5)
        # Treat as healthy if call succeeds (even if empty pre-market)
        health["upstox_intraday"] = True
    except Exception as e:
        logger.warning(f"Intraday health check failed: {e}")

    # Upstox historical (daily)
    try:
        df = fetch_historical("TCS.NS", days=10)
        health["upstox_historical"] = not df.empty
    except Exception as e:
        logger.warning(f"Historical health check failed: {e}")

    # Indices
    try:
        health["nifty"] = get_nifty_close()["price"] > 0
    except Exception:
        pass
    try:
        health["banknifty"] = get_banknifty_close()["price"] > 0
    except Exception:
        pass
    try:
        health["vix"] = get_vix_close()["price"] > 0
    except Exception:
        pass

    return health


def get_last_5_trading_days() -> list:
    """Dates of the last 5 weekday trading days (excludes weekends)."""
    dates = []
    day = datetime.now()
    while len(dates) < 5:
        if day.weekday() < 5:  # Mon–Fri
            dates.append(day.date())
        day -= timedelta(days=1)
    return sorted(dates)
