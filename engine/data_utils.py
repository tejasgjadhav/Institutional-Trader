"""
Data Utilities — Index closes (Nifty/BankNifty/VIX), API health check.
All via Upstox V3 (primary), no Yahoo latency.
"""
import logging
import requests
from datetime import datetime, timedelta

from engine.config import IST, MARKET_OPEN, MARKET_CLOSE
from engine.data_fetcher import (
    fetch_upstox_ltp, fetch_upstox_intraday, fetch_upstox_historical, fetch_historical,
    UPSTOX_BASE, _HEADERS,
)
from engine.instruments import to_instrument_key

logger = logging.getLogger(__name__)


def _batch_index_ltp(names: list) -> dict:
    """
    One batched LTP call for several indices (NIFTY/BANKNIFTY/VIX) instead of one
    request each — avoids Upstox 429 rate-limits on the fast live poll.
    Returns {name: price or None}.
    """
    out = {n: None for n in names}
    keymap = {}  # pipe instrument_key -> our name
    for n in names:
        k = to_instrument_key(n)
        if k:
            keymap[k] = n
    if not keymap:
        return out
    try:
        resp = requests.get(f"{UPSTOX_BASE}/v2/market-quote/ltp",
                            params={"instrument_key": ",".join(keymap.keys())},
                            headers=_HEADERS, timeout=6)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        # primary: match by instrument_token (== pipe key); fallback: colon dict-key
        colon = {k.replace("|", ":"): name for k, name in keymap.items()}
        for dk, q in data.items():
            name = keymap.get(q.get("instrument_token")) or colon.get(dk)
            if name and q.get("last_price") is not None:
                out[name] = float(q["last_price"])
    except Exception as e:
        logger.warning(f"Batch index LTP failed: {e}")
    return out


def _intraday_index_prices(names: list) -> dict:
    """
    Last 5-min candle close per index — near-live (<=5 min old) and served by a
    DIFFERENT Upstox endpoint (historical-candle/intraday) than the LTP quote, so it
    keeps working even when the LTP endpoint is rate-limited (429). Returns {name: price}.
    """
    out = {}
    for n in names:
        try:
            df = fetch_upstox_intraday(n, 5)
            if not df.empty:
                out[n] = float(df["Close"].iloc[-1])
        except Exception:
            pass
    return out


# Yahoo symbols for the indices — last-resort live-price fallback.
_YF_INDEX = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "VIX": "^INDIAVIX"}


def _yahoo_index_prices(names: list) -> dict:
    """
    Latest intraday index price from Yahoo (~15-min delayed) as a fallback when the
    Upstox LTP is rate-limited. Keeps the dashboard MOVING (and the % correct vs the
    previous close) even when Upstox returns 429. Returns {name: price}.
    """
    out = {}
    try:
        import yfinance as yf
        for n in names:
            sym = _YF_INDEX.get(n)
            if not sym:
                continue
            try:
                h = yf.Ticker(sym).history(period="1d", interval="5m")
                if not h.empty:
                    out[n] = float(h["Close"].dropna().iloc[-1])
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Yahoo index price fallback failed: {e}")
    return out


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
        return cached["prev_close"], cached["last_close"], cached["last_date"]

    df = fetch_upstox_historical(index_name, unit="days", interval=1)
    prev_close = last_close = last_date = None
    if not df.empty and len(df) >= 2:
        prev_close = float(df["Close"].iloc[-2])
        last_close = float(df["Close"].iloc[-1])
        last_date = df.index[-1].date()
    elif not df.empty:
        last_close = float(df["Close"].iloc[-1])
        last_date = df.index[-1].date()

    _ref_close_cache[index_name] = {
        "date": today, "prev_close": prev_close, "last_close": last_close, "last_date": last_date,
    }
    return prev_close, last_close, last_date


def _index_live_or_close(index_name: str, live_price: float = None,
                         fetch_if_missing: bool = True,
                         live_source: str = "Upstox (live)") -> dict:
    """
    Live price if market open, else last session close — change vs the *previous
    session* close (absolute + percent + direction).

    `live_price` lets a caller pass a price already fetched in a BATCH/fallback (so we
    don't make a second per-index call). The % reference is always the PREVIOUS
    SESSION close (the last daily close dated before today) so a live price is compared
    to yesterday, never to today's own partial candle.
    """
    prev_close, last_close, last_date = _reference_closes(index_name)
    today = datetime.now(IST).date()
    # previous-session close = last daily close NOT dated today
    prev_session = prev_close if last_date == today else last_close

    price = None
    source = "Upstox (last close)"

    if _market_is_open():
        lp = live_price
        if lp is None and fetch_if_missing:  # only the standalone getters fetch singly
            ltp = fetch_upstox_ltp(index_name)
            lp = ltp["price"] if ltp.get("success") else None
        if lp:
            price = lp
            ref = prev_session if prev_session else prev_close
            source = live_source

    if price is None:
        # After hours, or live fetch failed: last session close vs prior session close
        price = last_close if last_close else 0.0
        ref = prev_close if last_date == today else (prev_close or last_close)

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


def get_market_snapshot() -> dict:
    """
    NIFTY + BANKNIFTY + VIX in ONE batched LTP call (vs three separate calls).
    This is what the live dashboard polls — batching is what keeps it under the
    Upstox rate-limit so the values update LIVE instead of falling back to last close.
    """
    names = ["NIFTY", "BANKNIFTY", "VIX"]
    open_ = _market_is_open()
    prices = _batch_index_ltp(names) if open_ else {}
    src = {n: "Upstox (live)" for n in names if prices.get(n)}

    # If the LTP quote is rate-limited (429), fill missing LIVE prices so the dashboard
    # keeps moving and the % stays correct vs the previous close:
    #   1) Upstox 5-min intraday candle (near-live, separate endpoint, survives 429)
    #   2) Yahoo (~15-min delayed) as a last resort
    if open_:
        missing = [n for n in names if not prices.get(n)]
        if missing:
            for n, p in _intraday_index_prices(missing).items():
                prices[n] = p
                src[n] = "Upstox 5m"
        missing = [n for n in names if not prices.get(n)]
        if missing:
            for n, p in _yahoo_index_prices(missing).items():
                prices[n] = p
                src[n] = "Yahoo (~15m delay)"

    def build(name, ticker):
        d = _index_live_or_close(name, prices.get(name), fetch_if_missing=False,
                                 live_source=src.get(name, "Upstox (live)"))
        d["ticker"] = ticker
        return d

    nifty, bnf, vix = build("NIFTY", "NIFTY 50"), build("BANKNIFTY", "BANKNIFTY"), build("VIX", "VIX")
    if vix["price"] == 0.0:
        vix["price"] = 15.0
    return {"nifty": nifty, "banknifty": bnf, "vix": vix}


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
