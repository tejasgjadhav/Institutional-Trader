"""
Data Utilities — Index closes (Nifty/BankNifty/VIX), API health check.
All via Upstox V3 (primary), no Yahoo latency.
"""
import os
import logging
import requests
from datetime import datetime, timedelta, date

from engine.config import IST, MARKET_OPEN, MARKET_CLOSE, DATA_DIR
from engine.data_fetcher import (
    fetch_upstox_ltp, fetch_upstox_intraday, fetch_upstox_historical, fetch_historical,
    UPSTOX_BASE, _HEADERS, SESSION,
)
from engine.instruments import to_instrument_key

logger = logging.getLogger(__name__)


def _batch_index_net_change(names: list) -> dict:
    """One batched QUOTE call returning {name: net_change} straight from the exchange.

    Why this exists: the % on the ticker used to be derived from the DAILY history feed —
    "the last close not dated today". BSE publishes SENSEX's daily bar later than NSE
    publishes NIFTY's, so on 2026-08-04 the reference was still FRIDAY's close and SENSEX
    showed +0.88% when it was +0.19% (user-reported). net_change is the exchange's own
    day-change and can never be a session stale, so prev_close = last_price - net_change.
    """
    out = {}
    keymap = {}
    for n in names:
        k = to_instrument_key(n)
        if k:
            keymap[k] = n
    if not keymap:
        return out
    try:
        resp = SESSION.get(f"{UPSTOX_BASE}/v2/market-quote/quotes",
                           params={"instrument_key": ",".join(keymap.keys())}, timeout=6)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        colon = {k.replace("|", ":"): name for k, name in keymap.items()}
        for dk, q in data.items():
            name = keymap.get(q.get("instrument_token")) or colon.get(dk)
            nc = q.get("net_change")
            if name and isinstance(nc, (int, float)) and nc != 0:
                out[name] = float(nc)
    except Exception as e:
        logger.warning(f"Batch index net_change failed: {e}")
    return out


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
        resp = SESSION.get(f"{UPSTOX_BASE}/v2/market-quote/ltp",
                           params={"instrument_key": ",".join(keymap.keys())}, timeout=6)
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
_YF_INDEX = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "VIX": "^INDIAVIX", "SENSEX": "^BSESN"}


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
                if h.empty:
                    # ^BSESN carries no 5-minute series for much of the day, so SENSEX silently
                    # dropped out of this fallback entirely (found 21-Aug-2026). Daily is coarser
                    # but it is a real price, and SENSEX drives the 0DTE book.
                    h = yf.Ticker(sym).history(period="5d")
                if not h.empty:
                    out[n] = float(h["Close"].dropna().iloc[-1])
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Yahoo index price fallback failed: {e}")
    return out


def _market_is_open() -> bool:
    """True during NSE trading hours (Mon–Fri, 09:15–15:40 IST) — TIME ONLY (holiday-blind).
    Tracks FNO_CLOSE, not the cash close: since NSE's 3-Aug-2026 change derivatives run to 15:40
    and every one of our books trades options."""
    from engine.config import FNO_CLOSE
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    o = datetime.strptime(MARKET_OPEN, "%H:%M").time()
    c = datetime.strptime(FNO_CLOSE, "%H:%M").time()
    return o <= now.time() <= c


_trading_cache = {"date": None, "at": None, "trading": None}


def todays_close(ticker: str):
    """(price, source) for TODAY's close of one stock — or (None, "stale") if today's is not there.

    THE DEFECT THIS EXISTS FOR (confirmed live 5-Aug-2026). Every book took
    `fetch_upstox_historical(unit="days")["Close"].iloc[-1]` with no check that the last bar was
    today's. **The Upstox daily endpoint does not carry the current day's bar during the session** —
    at 15:41 on 5-Aug it still ended 04-Aug while the 5-min series had 05-Aug to 15:25. So every scan
    silently compared the PREVIOUS session's close against a one-day-shifted Donchian band, and the
    books fired yesterday's breakout today. GRASIM is the proof: it broke out 03-Aug and was traded
    04-Aug, on which day its own close was not a breakout at all.

    The close IS available same-day, just from the other endpoint. Measured against NSE bhavcopy over
    38 names on two sessions, the LAST 5-min bar equals the official close **33/38 exactly** on both;
    all but two mismatches are float rounding (<=0.07%), and only thin names (UBL, ATUL) differ
    materially (0.15-0.59%). That last bar is where the auction print lands — continuous trading in
    F&O stocks stops at 15:15 and the 15:10/15:15/15:20 bars carry an identical frozen price, while
    the 15:25 bar moves only once the auction matches at 15:30-15:35.

    Order: intraday first (it is the only source that has today at all), daily as a fallback for
    after-hours callers, and **never a bar that is not dated today**.
    """
    sym = ticker.replace(".NS", "")
    today = datetime.now(IST).date()
    try:
        df = fetch_upstox_intraday(sym, interval=5)
        if df is not None and not df.empty and df.index[-1].date() == today:
            return float(df["Close"].iloc[-1]), "intraday"
    except Exception as e:
        logger.debug(f"todays_close intraday {sym}: {e}")
    try:
        # Use the ticker AS GIVEN, not sym+".NS": stock callers pass "GRASIM.NS", index callers
        # pass "NIFTY". Re-appending ".NS" produced "NIFTY.NS", which has no instrument key, and
        # logged a warning on every index call (found 5-Aug).
        df = fetch_upstox_historical(ticker, unit="days", interval=1,
                                     from_date=(today - timedelta(days=7)).isoformat(),
                                     to_date=today.isoformat())
        if df is not None and not df.empty and df.sort_index().index[-1].date() == today:
            return float(df.sort_index()["Close"].iloc[-1]), "daily"
    except Exception as e:
        logger.debug(f"todays_close daily {sym}: {e}")
    return None, "stale"


def recent_entry_symbols(gap_days: int = None) -> frozenset:
    """Names entered by ANY stock-credit book (v0/v1/v2) within the last N days.

    The 3-day re-entry gap is now CROSS-BOOK (user rule, 2026-08-07): a repeat signal at new levels
    is a fine trade, but no book may fire on a name any book entered in the last
    STOCK_CREDIT_REENTRY_GAP_DAYS — firing on consecutive days of one continuing move is just
    playing the same breakout daily. This matches the backtests, whose REENTRY=3 is per symbol
    with no notion of separate books. Same-day tie-break (v1 scans before v0) is preserved: a
    same-cycle v1 entry is already in its book file when v0 scans, so 0 < gap blocks it.
    """
    from datetime import date as _date
    from engine import config as _c
    gap = int(gap_days if gap_days is not None else
              getattr(_c, "STOCK_CREDIT_REENTRY_GAP_DAYS", 3))
    today = _date.today()
    syms = set()
    for fname in ("stock_credit_positions.json", "stock_credit_v2_positions.json",
                  "stock_credit_v0_positions.json"):
        try:
            import json as _json
            with open(os.path.join(DATA_DIR, fname)) as f:
                for p in _json.load(f) or []:
                    sym, ed = p.get("symbol"), p.get("entry_date")
                    if not sym or not ed:
                        continue
                    try:
                        if (today - _date.fromisoformat(ed)).days < gap:
                            syms.add(sym)
                    except ValueError:
                        continue
        except Exception:
            continue
    return frozenset(syms)


def _snapshots_today() -> int:
    """How many market snapshots the engine has ALREADY written for today, from its own DB.

    This is the second opinion that does not need the network. The engine records a snapshot every
    few seconds all session, so a non-zero count is direct evidence the market traded today — and it
    survives any outage, because it is a local read of work already done.
    """
    try:
        import sqlite3
        db = DATA_DIR if os.path.isabs(DATA_DIR) else os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), DATA_DIR)
        con = sqlite3.connect(os.path.join(db, "engine.db"), timeout=3)
        try:
            return con.execute("SELECT COUNT(*) FROM market_snapshots WHERE date = ?",
                               (date.today().isoformat(),)).fetchone()[0]
        finally:
            con.close()
    except Exception as e:
        logger.warning("snapshot-count probe failed (%s) — this layer is blind, falling through", e)
        return 0


def market_is_trading_today() -> bool:
    """True only if the market is ACTUALLY trading now — weekday + hours AND live data flowing.

    Distinguishes a real session from an NSE HOLIDAY, when `_market_is_open()` still says open by
    the clock but no candles form and the LTP is frozen at the prior close. There is no hardcoded
    holiday calendar; it infers "not trading" from the absence of today's data.

    THE 17-AUG-2026 FAILURE, and why this now takes three sources instead of one. At 15:15 a DNS
    outage made every fetch fail — NIFTY, BANKNIFTY, SENSEX and the yfinance fallbacks all at once.
    Each raised an exception, `fetch_upstox_intraday` caught it and returned an EMPTY frame, and an
    empty frame was read as "nothing traded today". The engine logged "exchange holiday" for twelve
    minutes, and the 15:17 watchlist ran late on nothing: 0 breakouts, against 20 at the 15:31
    rebuild. A network failure and a holiday are completely different facts and had become
    indistinguishable.

    Three layers now, cheapest and most reliable first:
      1. The engine's OWN database. If snapshots exist dated today, the market traded — local, needs
         no network, and cannot be taken out by an outage.
      2. NIFTY intraday, as before.
      3. If both are silent, return UNKNOWN as True and DO NOT CACHE IT. Failing open is right here
         because the real safety is per-stock and fails closed: `todays_close()` returns
         (None, "stale") and every book refuses to fire on it. A false "holiday" silently skips a
         whole trading day; a false "trading" costs nothing, because the price guard still bites.
    Never cache a negative derived from an empty frame — that was the specific defect.
    """
    now = datetime.now(IST)
    if not _market_is_open():
        return False
    # Before ~09:25 the first 5-min candle may not have formed yet — assume trading.
    if now.time() < datetime.strptime("09:25", "%H:%M").time():
        return True
    c = _trading_cache
    if (c["date"] == now.date() and c["at"] and
            (now - c["at"]).total_seconds() < 300 and c["trading"] is not None):
        return c["trading"]

    # LAYER 1 — the engine's own record of today, no network involved.
    if _snapshots_today() > 0:
        _trading_cache.update(date=now.date(), at=now, trading=True)
        return True

    # LAYER 2 — live NIFTY candles.
    df = fetch_upstox_intraday("NIFTY", interval=5)
    if df is not None and not df.empty:
        trading = (df.index[-1].date() == now.date())
        _trading_cache.update(date=now.date(), at=now, trading=trading)
        return trading

    # LAYER 3 — nothing answered. UNKNOWN, not a holiday. Do not cache this.
    logger.warning("market_is_trading_today: no snapshots today and NIFTY intraday returned "
                   "nothing — treating as TRADING (unknown, not a holiday) and not caching")
    return True


def _prev_session_close_from_db(index_name: str) -> float:
    """Previous trading session's close from the engine's OWN stored snapshots (engine.db).

    This is immune to Upstox's daily-feed backfill lag: yesterday's daily candle often isn't in
    the feed early the next morning, so the feed's "last close" is actually TWO sessions ago,
    which inflates today's %% (e.g. NIFTY shown +1.5%% vs the real +0.65%%). The engine records
    a snapshot at the real close every day, so the latest snapshot dated BEFORE today is the
    correct previous-session close. Returns None if unavailable (caller falls back to the feed).
    """
    col = {"NIFTY": "nifty", "BANKNIFTY": "banknifty", "VIX": "vix"}.get(index_name)
    if not col:
        return None
    try:
        import sqlite3
        today = datetime.now(IST).date().isoformat()
        con = sqlite3.connect(os.path.join(DATA_DIR, "engine.db"), timeout=3)
        row = con.execute(
            f"SELECT {col} FROM market_snapshots WHERE date < ? AND {col} IS NOT NULL "
            f"ORDER BY date DESC, ts DESC LIMIT 1", (today,)).fetchone()
        con.close()
        return float(row[0]) if row and row[0] else None
    except Exception:
        return None


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

    # Only cache a SUCCESSFUL fetch. If the daily feed failed (e.g. no network at the 8 AM
    # wake), caching the empty result would freeze the % at 0.0/FLAT for the whole session
    # because daily closes are fetched at most once per day. Leaving it uncached lets the
    # next poll retry once the network is up, so the change/pct self-heals within ~5 s.
    if last_close is not None:
        _ref_close_cache[index_name] = {
            "date": today, "prev_close": prev_close, "last_close": last_close, "last_date": last_date,
        }
    return prev_close, last_close, last_date


def _index_live_or_close(index_name: str, live_price: float = None,
                         fetch_if_missing: bool = True,
                         live_source: str = "Upstox (live)",
                         net_change: float = None) -> dict:
    """
    Live price if market open, else last session close — change vs the *previous
    session* close (absolute + percent + direction).

    `live_price` lets a caller pass a price already fetched in a BATCH/fallback (so we
    don't make a second per-index call). The % reference is always the PREVIOUS
    SESSION close (the last daily close dated before today) so a live price is compared
    to yesterday, never to today's own partial candle.
    """
    prev_close, last_close, last_date = _reference_closes(index_name)
    # EXCHANGE-AUTHORITATIVE day change. Prefer it over anything derived from the daily
    # history feed: BSE publishes SENSEX's daily bar later than NSE publishes NIFTY's, so the
    # derived reference could still be the PREVIOUS session's close and the ticker showed
    # SENSEX +0.88% when it was +0.19% (2026-08-04). net_change cannot be a session stale.
    if net_change is not None and live_price:
        prev = live_price - net_change
        if prev > 0:
            return {"price": float(live_price), "change": round(float(net_change), 2),
                    "pct": round(net_change / prev * 100, 2),
                    "direction": "UP" if net_change > 0 else ("DOWN" if net_change < 0 else "FLAT"),
                    "source": live_source if _market_is_open() else "Upstox (last traded)"}
    today = datetime.now(IST).date()
    # previous-session close = last daily close NOT dated today
    prev_session = prev_close if last_date == today else last_close

    price = None
    source = "Upstox (last close)"

    # Prefer a FRESH traded price whenever we can get one — the LTP endpoint works
    # after hours too and returns the day's last traded price. The daily historical
    # feed lags T+1, so falling back to last_close would show YESTERDAY's close as if
    # it were today's. Use LTP both during and after the session.
    lp = live_price
    if lp is None and fetch_if_missing:  # only the standalone getters fetch singly
        ltp = fetch_upstox_ltp(index_name)
        lp = ltp["price"] if ltp.get("success") else None
    if lp:
        price = lp
        source = live_source if _market_is_open() else "Upstox (last traded)"

    if price is None:
        # No traded price at all (rare): fall back to last available daily close
        price = last_close if last_close else 0.0

    # Reference is ALWAYS the previous-session close (compare today vs yesterday).
    # PREFER the engine's stored close (engine.db) — it's immune to the daily-feed backfill lag
    # that otherwise uses a 2-sessions-ago close and inflates the %. Fall back to the daily feed.
    ref = _prev_session_close_from_db(index_name) or (prev_session if prev_session else (prev_close or last_close))

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
    names = ["NIFTY", "BANKNIFTY", "SENSEX", "VIX"]
    open_ = _market_is_open()
    # LTP works during AND after the session (returns the day's last traded price), so
    # fetch it unconditionally. Otherwise after-hours we'd fall back to the daily
    # historical close, which lags T+1 and shows YESTERDAY's value.
    prices = _batch_index_ltp(names)
    src = {n: ("Upstox (live)" if open_ else "Upstox (last traded)")
           for n in names if prices.get(n)}

    # If the LTP quote is rate-limited (429) or empty, fill missing prices so the
    # dashboard keeps moving and the % stays correct vs the previous close:
    #   1) Upstox 5-min intraday candle (near-live, separate endpoint, survives 429)
    #   2) Yahoo (~15-min delayed) as a last resort
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

    netchg = _batch_index_net_change(names)

    def build(name, ticker):
        d = _index_live_or_close(name, prices.get(name), fetch_if_missing=False,
                                 live_source=src.get(name, "Upstox (live)"),
                                 net_change=netchg.get(name))
        d["ticker"] = ticker
        return d

    nifty, bnf, vix = build("NIFTY", "NIFTY 50"), build("BANKNIFTY", "BANKNIFTY"), build("VIX", "VIX")
    sensex = build("SENSEX", "SENSEX")
    if vix["price"] == 0.0:
        vix["price"] = 15.0
    return {"nifty": nifty, "banknifty": bnf, "sensex": sensex, "vix": vix}


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
