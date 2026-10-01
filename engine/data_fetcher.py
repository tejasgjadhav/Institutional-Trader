"""
Data Fetcher — Upstox V3 (primary) + Yahoo (fallback only)

Upstox is the primary source for both real-time LTP and 5-min candles
(low latency). Yahoo is a degraded fallback if the Upstox token is
missing/expired. NSE public API is used for options chain / filings.

Upstox V3 endpoints:
  LTP:        GET v2/market-quote/ltp?instrument_key=NSE_EQ|<ISIN>
  Intraday:   GET v3/historical-candle/intraday/<key>/minutes/5
  Historical: GET v3/historical-candle/<key>/minutes/5/<to_date>/<from_date>
              GET v3/historical-candle/<key>/days/1/<to_date>/<from_date>

All instrument keys are ISIN-based (NSE_EQ|INE467B01029), resolved via
engine.instruments.
"""
import pandas as pd
import numpy as np
import requests
import threading
import time
from datetime import datetime, timedelta
import logging

from engine.config import UPSTOX_ANALYTICS_TOKEN, USE_YAHOO_FALLBACK, IST
from engine.instruments import to_instrument_key, encode_key

logger = logging.getLogger(__name__)

UPSTOX_BASE = "https://api.upstox.com"
_HEADERS = {
    "Authorization": f"Bearer {UPSTOX_ANALYTICS_TOKEN}",
    "Accept": "application/json",
}

# Shared pooled session — reuses TCP/TLS connections (keep-alive) instead of a fresh
# handshake on every call. ~2.3x faster across the 95-stock scan. Reused by data_utils
# and options_flow too. pool_maxsize covers the parallel scan workers.
SESSION = requests.Session()
SESSION.headers.update(_HEADERS)
_adapter = requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=32, max_retries=0)
SESSION.mount("https://", _adapter)
SESSION.mount("http://", _adapter)

# RATE-LIMIT WAIT (30-Sep-2026). On 29-Sep, the first scan on the AWS server, Upstox answered 51
# requests with HTTP 429 inside 1.3 s at 15:36:38, and about 45 of 116 names were scanned without
# data. The server sits next to Upstox in Mumbai, so it spends the per-minute allowance faster
# than the Mac did. Each 429 used to fail at once. Now a 429 waits and retries, with the waits
# capped in total so a long throttle can never push the scan past the 15:40 close.
#
# PACING (1-Oct-2026). The retry alone failed on 30-Sep: the scan's first 429 came at 15:36:14 and
# the 45 s budget went on one name (POLYCAB), after which all 117 names failed at once and the
# "no signal" verdict was reached on no data. Upstox counts requests per minute, and the server
# sends them faster than that limit allows. So every Upstox call through SESSION is now spaced
# UPSTOX_MIN_GAP_S apart (at most 400 a minute, under the 500/minute limit, leaving room for the
# Mac's CAS page on the same token), and a 429 waits for the next minute window rather than a few
# seconds. Calls per minute are logged 15:10-15:45 so the real load is on record.
UPSTOX_MIN_GAP_S = 0.15
_429_STEPS = (5, 15, 30, 30)        # seconds to wait before each retry (reaches a fresh minute)
_429_BUDGET_S = 120                 # most 429-waiting allowed in any 300 s window
_429_WAITS = []                     # (time, seconds) of recent waits
_429_LOCK = threading.Lock()        # the scan sentinel thread shares this session
_PACE_LOCK = threading.Lock()
_PACE_LAST = [0.0]
_MIN_COUNT = [None, 0]              # (HH:MM, Upstox calls in that minute)


def _reserve_429_wait(wait: float) -> bool:
    """True if `wait` seconds still fit in the rolling 429 budget, and books them."""
    with _429_LOCK:
        now = time.time()
        _429_WAITS[:] = [(t, w) for t, w in _429_WAITS if now - t < 300]
        if sum(w for _, w in _429_WAITS) + wait > _429_BUDGET_S:
            return False
        _429_WAITS.append((now, wait))
        return True


_RAW_REQUEST = SESSION.request


def _paced_request(method, url, *a, **kw):
    """SESSION.request for every caller (data_utils, options_flow, dte_multi, histdb share SESSION):
    Upstox calls are spaced UPSTOX_MIN_GAP_S apart, and a 429 waits and retries within the budget.
    Non-Upstox URLs pass straight through."""
    if "api.upstox.com" not in str(url):
        return _RAW_REQUEST(method, url, *a, **kw)
    for wait in _429_STEPS + (None,):
        with _PACE_LOCK:
            gap = time.time() - _PACE_LAST[0]
            if gap < UPSTOX_MIN_GAP_S:
                time.sleep(UPSTOX_MIN_GAP_S - gap)
            _PACE_LAST[0] = time.time()
            hm = datetime.now(IST).strftime("%H:%M")
            if _MIN_COUNT[0] != hm:
                if _MIN_COUNT[0] and "15:10" <= _MIN_COUNT[0] <= "15:45":
                    logger.info(f"Upstox calls in {_MIN_COUNT[0]}: {_MIN_COUNT[1]}")
                _MIN_COUNT[:] = [hm, 0]
            _MIN_COUNT[1] += 1
        resp = _RAW_REQUEST(method, url, *a, **kw)
        if resp.status_code != 429 or wait is None or not _reserve_429_wait(wait):
            return resp
        logger.info(f"Upstox 429 — waiting {wait}s, then retrying {str(url)[len(UPSTOX_BASE):][:70]}")
        time.sleep(wait)
    return resp


SESSION.request = _paced_request


def _upstox_get(url: str, timeout: float, **kw):
    """SESSION.get; pacing and the 429 retry now live in _paced_request for every caller."""
    return SESSION.get(url, timeout=timeout, **kw)


def _candles_to_df(candles: list) -> pd.DataFrame:
    """
    Convert Upstox candle array to OHLCV DataFrame.
    Each candle: [timestamp, open, high, low, close, volume, open_interest]
    Upstox returns newest-first; we sort oldest-first.
    """
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume", "OI"])
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df = df.set_index("Timestamp").sort_index()
    return df[["Open", "High", "Low", "Close", "Volume"]].astype(float)


# ── Batched LTP (low latency — all instruments in one call) ───────────────────

def fetch_ltp_batch(tickers: list, chunk_size: int = 100) -> dict:
    """
    Fetch LTP for many instruments in a few batched calls (vs one-per-stock).
    Upstox accepts comma-separated instrument keys. ~300ms for 100 names vs ~18s.
    Returns {ticker: price} (missing tickers omitted).
    """
    if not UPSTOX_ANALYTICS_TOKEN or not tickers:
        return {}
    key_to_ticker = {}
    for t in tickers:
        k = to_instrument_key(t)
        if k:
            key_to_ticker[k] = t
    out = {}
    keys = list(key_to_ticker.keys())
    for i in range(0, len(keys), chunk_size):
        chunk = keys[i:i + chunk_size]
        try:
            resp = SESSION.get(f"{UPSTOX_BASE}/v2/market-quote/ltp",
                                params={"instrument_key": ",".join(chunk)}, timeout=10)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            for q in data.values():
                tok = q.get("instrument_token")
                tk = key_to_ticker.get(tok)
                if tk and q.get("last_price") is not None:
                    out[tk] = float(q["last_price"])
        except Exception as e:
            logger.warning(f"Batch LTP chunk {i//chunk_size} failed: {e}")
    return out


# ── Real-time LTP ─────────────────────────────────────────────────────────────

def fetch_upstox_ltp(ticker: str) -> dict:
    """
    Live last-traded price from Upstox.
    Returns: {"price": float, "timestamp": str, "success": bool, "error": str?}
    """
    if not UPSTOX_ANALYTICS_TOKEN:
        return {"price": None, "timestamp": None, "success": False, "error": "Token not configured"}

    key = to_instrument_key(ticker)
    if not key:
        return {"price": None, "timestamp": None, "success": False, "error": f"No instrument key for {ticker}"}

    try:
        url = f"{UPSTOX_BASE}/v2/market-quote/ltp"
        resp = SESSION.get(url, params={"instrument_key": key}, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "success":
            return {"price": None, "timestamp": None, "success": False, "error": data.get("message", "API error")}

        # Response: {"data": {"NSE_EQ:TCS": {"last_price": 2161.4, "instrument_token": "..."}}}
        quotes = data.get("data", {})
        if not quotes:
            return {"price": None, "timestamp": None, "success": False, "error": "Empty data (market closed?)"}

        # Take the first (only) quote
        quote = next(iter(quotes.values()))
        ltp = float(quote["last_price"])
        return {"price": ltp, "timestamp": datetime.now(IST).isoformat(), "success": True}

    except Exception as e:
        logger.warning(f"Upstox LTP fetch failed for {ticker}: {e}")
        return {"price": None, "timestamp": None, "success": False, "error": str(e)}


QUOTE_TTL_S = 60          # shared by the four stock books at 15:36 (1-Oct-2026), see fetch_daily_prior
_QUOTE_CACHE = {}         # instrument_key -> (time, quote dict)


def fetch_upstox_quote(instrument_key: str) -> dict:
    """Full market quote for ONE instrument key (used for the liquidity gate): best bid/ask
    from the depth, open interest, day volume, LTP. Returns {} on any failure.
    Response is keyed by trading symbol (not the instrument_key), so we take the one entry.
    A successful quote is reused for QUOTE_TTL_S: v2, v0 and vlc price the SAME legs one after
    another at 15:36, and used to fetch each of them three times."""
    if not UPSTOX_ANALYTICS_TOKEN or not instrument_key:
        return {}
    hit = _QUOTE_CACHE.get(instrument_key)
    if hit and time.time() - hit[0] < QUOTE_TTL_S:
        return dict(hit[1])
    try:
        resp = _upstox_get(f"{UPSTOX_BASE}/v2/market-quote/quotes",
                           params={"instrument_key": instrument_key}, timeout=6)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        if not data:
            return {}
        q = next(iter(data.values()))
        depth = q.get("depth", {}) or {}
        buy = depth.get("buy") or []
        sell = depth.get("sell") or []
        bid = float(buy[0]["price"]) if buy and buy[0].get("price") else 0.0
        ask = float(sell[0]["price"]) if sell and sell[0].get("price") else 0.0
        out = {"ltp": q.get("last_price"), "bid": bid, "ask": ask,
               "oi": q.get("oi") or 0, "volume": q.get("volume") or 0}
        _QUOTE_CACHE[instrument_key] = (time.time(), out)
        return dict(out)
    except Exception as e:
        logger.warning(f"Upstox quote fetch failed for {instrument_key}: {e}")
        return {}


# ── Intraday 5-min candles (today, live) ──────────────────────────────────────

def fetch_upstox_intraday(ticker: str, interval: int = 5) -> pd.DataFrame:
    """
    Live intraday candles for TODAY from Upstox V3.
    interval: minutes (1-300). Default 5.
    Returns OHLCV DataFrame (oldest-first). Empty before market open.
    """
    if not UPSTOX_ANALYTICS_TOKEN:
        return pd.DataFrame()

    key = to_instrument_key(ticker)
    if not key:
        return pd.DataFrame()

    try:
        url = f"{UPSTOX_BASE}/v3/historical-candle/intraday/{encode_key(key)}/minutes/{interval}"
        resp = _upstox_get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "success":
            return _candles_to_df(data.get("data", {}).get("candles", []))
        return pd.DataFrame()
    except Exception as e:
        logger.warning(f"Upstox intraday failed for {ticker}: {e}")
        return pd.DataFrame()


# ── Historical candles (past sessions) ────────────────────────────────────────

def fetch_upstox_historical(ticker: str, unit: str = "days", interval: int = 1,
                            from_date: str = None, to_date: str = None) -> pd.DataFrame:
    """
    Historical candles from Upstox V3.
      unit:     'minutes' | 'hours' | 'days' | 'weeks' | 'months'
      interval: 1-300 for minutes, 1-5 hours, 1 for days/weeks/months
      from_date / to_date: 'YYYY-MM-DD' (defaults: last 60 days → today)
    Returns OHLCV DataFrame (oldest-first).
    """
    if not UPSTOX_ANALYTICS_TOKEN:
        return pd.DataFrame()

    key = to_instrument_key(ticker)
    if not key:
        return pd.DataFrame()

    if to_date is None:
        to_date = datetime.now(IST).strftime("%Y-%m-%d")
    if from_date is None:
        from_date = (datetime.now(IST) - timedelta(days=400)).strftime("%Y-%m-%d")

    try:
        url = f"{UPSTOX_BASE}/v3/historical-candle/{encode_key(key)}/{unit}/{interval}/{to_date}/{from_date}"
        resp = _upstox_get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "success":
            return _candles_to_df(data.get("data", {}).get("candles", []))
        return pd.DataFrame()
    except Exception as e:
        logger.warning(f"Upstox historical failed for {ticker}: {e}")
        return pd.DataFrame()


# ── Unified accessors (used by the engine) ────────────────────────────────────

def fetch_intraday_5min(ticker: str, days: int = 1) -> pd.DataFrame:
    """
    5-min bars for signal generation. Upstox intraday (today) primary.
    Falls back to Yahoo only if Upstox returns nothing AND fallback enabled.
    """
    df = fetch_upstox_intraday(ticker, interval=5)
    if not df.empty:
        return df

    if USE_YAHOO_FALLBACK:
        return _yahoo_intraday_fallback(ticker, days)
    return pd.DataFrame()


# Daily bars don't change during the session → cache per (ticker, date) so the
# 5-min scan loop doesn't refetch 400 days of history every cycle.
_daily_hist_cache = {}

# ONE DAILY-HISTORY FETCH PER STOCK PER DAY for the breakout scanners (1-Oct-2026). The bars before
# today do not change during the session, yet the 15:31 build and all four 15:36 books (v2, v1, v0,
# vlc) downloaded them again: five fetches of the same data per stock, about 580 calls a day, and
# the main reason the 15:36 scan hit Upstox's per-minute limit on the server. Callers only use bars
# dated BEFORE today (today's close comes from data_utils.todays_close), so a copy fetched earlier
# in the day is exactly as good. A failed or empty fetch is never cached, so it is retried.
PRIOR_DAYS = 120          # covers v2 (85 days) and v1 (55 days) lookbacks with room to spare
_PRIOR_CACHE = {}         # (ticker, date) -> DataFrame


def fetch_daily_prior(ticker: str) -> pd.DataFrame:
    """Daily bars for the last PRIOR_DAYS calendar days, fetched once per stock per day."""
    today = datetime.now(IST).date()
    key = (ticker, today)
    if key in _PRIOR_CACHE:
        return _PRIOR_CACHE[key]
    for k in [k for k in _PRIOR_CACHE if k[1] != today]:
        del _PRIOR_CACHE[k]
    df = fetch_upstox_historical(ticker, unit="days", interval=1,
                                 from_date=(today - timedelta(days=PRIOR_DAYS)).isoformat(),
                                 to_date=today.isoformat())
    if df is not None and not df.empty:
        _PRIOR_CACHE[key] = df
    return df


def fetch_historical(ticker: str, days: int = 400) -> pd.DataFrame:
    """
    Daily bars for backtesting / indicator history. Upstox V3 primary.
    Cached per calendar day. Falls back to Yahoo only if Upstox returns nothing.
    """
    today = datetime.now(IST).date()
    cache_key = (ticker, today, days)
    if cache_key in _daily_hist_cache:
        return _daily_hist_cache[cache_key]
    # prune prior-day entries so this dict can't grow unbounded in the long-running daemon
    stale = [k for k in _daily_hist_cache if k[1] != today]
    for k in stale:
        del _daily_hist_cache[k]

    from_date = (datetime.now(IST) - timedelta(days=days)).strftime("%Y-%m-%d")
    to_date = datetime.now(IST).strftime("%Y-%m-%d")
    df = fetch_upstox_historical(ticker, unit="days", interval=1, from_date=from_date, to_date=to_date)
    if df.empty and USE_YAHOO_FALLBACK:
        df = _yahoo_historical_fallback(ticker, days)
    if not df.empty:
        _daily_hist_cache[cache_key] = df
    return df


# Backwards-compat alias (older modules import fetch_yahoo_historical)
def fetch_yahoo_historical(ticker: str, period: str = "2y") -> pd.DataFrame:
    """Deprecated name — now routes through Upstox-first fetch_historical."""
    days = {"1d": 1, "5d": 5, "10d": 10, "1mo": 31, "2mo": 62, "3mo": 93,
            "6mo": 186, "1y": 366, "2y": 731}.get(period, 400)
    return fetch_historical(ticker, days=days)


# ── Yahoo fallback (only when Upstox unavailable) ─────────────────────────────

def _yahoo_intraday_fallback(ticker: str, days: int = 1) -> pd.DataFrame:
    try:
        import yfinance as yf
        logger.info(f"Yahoo intraday fallback for {ticker}")
        yf_ticker = ticker if ticker.endswith(".NS") or ticker.startswith("^") else f"{ticker}.NS"
        df = yf.download(yf_ticker, period=f"{days}d", interval="5m", progress=False)
        if not df.empty:
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            return df[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    except Exception as e:
        logger.warning(f"Yahoo intraday fallback failed for {ticker}: {e}")
    return pd.DataFrame()


def _yahoo_historical_fallback(ticker: str, days: int = 400) -> pd.DataFrame:
    try:
        import yfinance as yf
        logger.info(f"Yahoo historical fallback for {ticker}")
        yf_ticker = ticker if ticker.endswith(".NS") or ticker.startswith("^") else f"{ticker}.NS"
        period = "2y" if days > 366 else ("1y" if days > 186 else "6mo")
        df = yf.download(yf_ticker, period=period, progress=False)
        if not df.empty:
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            return df[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    except Exception as e:
        logger.warning(f"Yahoo historical fallback failed for {ticker}: {e}")
    return pd.DataFrame()


# ── Index data (Nifty, BankNifty, VIX) ────────────────────────────────────────

def fetch_index_ltp(index_name: str) -> float:
    """Get index LTP via Upstox. index_name: 'NIFTY' | 'BANKNIFTY' | 'VIX'."""
    result = fetch_upstox_ltp(index_name)
    return result["price"] if result["success"] else None


def fetch_vix() -> float:
    """India VIX current level via Upstox; fallback 15.0."""
    price = fetch_index_ltp("VIX")
    if price is not None:
        return price
    # Last-resort: most recent daily close
    df = fetch_upstox_historical("VIX", unit="days", interval=1)
    if not df.empty:
        return float(df["Close"].iloc[-1])
    return 15.0


def fetch_nifty_pct() -> float:
    """Nifty % change from today's open via Upstox intraday."""
    df = fetch_upstox_intraday("NIFTY", interval=5)
    if not df.empty and len(df) > 0:
        open_p = float(df["Open"].iloc[0])
        close_p = float(df["Close"].iloc[-1])
        return round((close_p - open_p) / open_p * 100, 2)
    return 0.0


# ── NSE public API (options chain, PCR, filings) — placeholders ───────────────

def get_option_chain(ticker: str) -> dict:
    """NSE options chain (PCR, max-pain, IV). Placeholder for NSE API integration."""
    return {"pcr": 1.0, "max_pain": 0.0, "iv": 20.0}


def get_news_sentiment(ticker: str, hours_back: int = 12) -> float:
    """News sentiment (-1..+1). Placeholder for news API integration."""
    return 0.0


def fetch_nse_filings(ticker: str, hours_back: int = 12) -> list:
    """Recent NSE corporate filings. Placeholder for NSE API integration."""
    return []


# ── Caching layer ─────────────────────────────────────────────────────────────

_ltp_cache = {}
_vix_cache = None
_vix_cache_time = None
_nifty_pct_cache = None
_nifty_pct_cache_time = None


def get_cached_ltp(ticker: str, max_age_sec: int = 10) -> float:
    """LTP with 10-sec cache."""
    now = datetime.now(IST)
    if ticker in _ltp_cache:
        price, ts = _ltp_cache[ticker]
        if (now - ts).total_seconds() < max_age_sec:
            return price
    result = fetch_upstox_ltp(ticker)
    if result["success"]:
        _ltp_cache[ticker] = (result["price"], now)
        return result["price"]
    return None


def get_cached_vix(max_age_sec: int = 60) -> float:
    """VIX with 60-sec cache."""
    global _vix_cache, _vix_cache_time
    now = datetime.now(IST)
    if _vix_cache is not None and _vix_cache_time is not None:
        if (now - _vix_cache_time).total_seconds() < max_age_sec:
            return _vix_cache
    _vix_cache = fetch_vix()
    _vix_cache_time = now
    return _vix_cache


def get_cached_nifty_pct(max_age_sec: int = 60) -> float:
    """Nifty % change with 60-sec cache."""
    global _nifty_pct_cache, _nifty_pct_cache_time
    now = datetime.now(IST)
    if _nifty_pct_cache is not None and _nifty_pct_cache_time is not None:
        if (now - _nifty_pct_cache_time).total_seconds() < max_age_sec:
            return _nifty_pct_cache
    _nifty_pct_cache = fetch_nifty_pct()
    _nifty_pct_cache_time = now
    return _nifty_pct_cache
