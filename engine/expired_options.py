"""
Expired-instruments option data (Upstox Plus) — REAL historical option premiums for ANY past
day, including expired contracts. Breaks the ~1-month live-instrument-master wall, so the
option strategy can be backtested on real premiums over months/years (not just the underlying
proxy).

Flow (all GET, Bearer auth via the shared SESSION):
  1. /v2/expired-instruments/expiries?instrument_key=<underlying>            -> [expiry dates]
  2. /v2/expired-instruments/option/contract?instrument_key=&expiry_date=    -> [contracts]
  3. /v2/expired-instruments/historical-candle/<expired_key>/<iv>/<to>/<from>-> OHLC+vol+OI

`expired_instrument_key` is "NSE_FO|<token>|DD-MM-YYYY" (returned by step 2). Underlying key is
the normal instrument key: NSE_INDEX|Nifty 50 for indices, NSE_EQ|<ISIN> for stocks.
"""
import time
import logging
import pandas as pd
from datetime import datetime, date

from engine.data_fetcher import SESSION, UPSTOX_BASE
from engine.instruments import to_instrument_key, encode_key

logger = logging.getLogger(__name__)

_EXPIRIES = {}    # underlying_key -> sorted [YYYY-MM-DD]
_CONTRACTS = {}   # (underlying_key, expiry) -> [contract dicts]


def _get_json(url, params=None, attempts=6):
    """GET with exponential backoff on HTTP 429 (the expired-instruments API rate-limits
    hard under heavy backtest load). Returns {} on persistent failure."""
    for i in range(attempts):
        try:
            r = SESSION.get(url, params=params, timeout=25)
            if r.status_code == 429:
                time.sleep(1.5 * (i + 1))   # 1.5, 3, 4.5, ... seconds
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i == attempts - 1:
                logger.warning(f"_get_json failed {url}: {e}")
            time.sleep(1.0 * (i + 1))
    return {}


def get_expiries(ticker: str) -> list:
    """Sorted list of available expiry dates (YYYY-MM-DD) for an underlying."""
    uk = to_instrument_key(ticker)
    if not uk:
        return []
    if uk in _EXPIRIES:
        return _EXPIRIES[uk]
    j = _get_json(f"{UPSTOX_BASE}/v2/expired-instruments/expiries", {"instrument_key": uk})
    exps = sorted(j.get("data", []) or [])
    if exps: _EXPIRIES[uk] = exps   # never cache an empty (rate-limited) result
    return exps


def _nearest_expiry(ticker: str, on_day: date) -> str:
    """The nearest expiry ON OR AFTER on_day (the contract a trade that day would use)."""
    ds = on_day.isoformat()
    fut = [e for e in get_expiries(ticker) if e >= ds]
    return fut[0] if fut else None


def get_contracts(ticker: str, expiry: str) -> list:
    """Option contracts for an underlying + expiry. Each: instrument_key, strike_price,
    instrument_type (CE/PE), lot_size (if present)."""
    uk = to_instrument_key(ticker)
    if not uk or not expiry:
        return []
    ck = (uk, expiry)
    if ck in _CONTRACTS:
        return _CONTRACTS[ck]
    j = _get_json(f"{UPSTOX_BASE}/v2/expired-instruments/option/contract",
                  {"instrument_key": uk, "expiry_date": expiry})
    out = j.get("data", []) or []
    if out: _CONTRACTS[ck] = out   # never cache an empty (rate-limited) result
    return out


def get_expired_option_by_offset(ticker: str, spot: float, on_day: date, opt_type: str, offset: int) -> dict:
    """Resolve the strike at `offset` from ATM for the nearest expiry on/after on_day, using
    EXPIRED-instrument data (works for any past day). Mirrors options.get_option_by_offset:
    CALL OTM = higher strike (atm+offset), PUT OTM = lower (atm-offset). Returns a dict with
    'key' (the expired_instrument_key), 'strike', 'lot', 'expiry_date', or None."""
    exp = _nearest_expiry(ticker, on_day)
    if not exp:
        return None
    chain = [c for c in get_contracts(ticker, exp) if c.get("instrument_type") == opt_type]
    if not chain:
        return None
    chain = sorted(chain, key=lambda c: float(c.get("strike_price", 0)))
    strikes = [float(c.get("strike_price", 0)) for c in chain]
    atm_i = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot))
    idx = atm_i + offset if opt_type == "CE" else atm_i - offset
    idx = max(0, min(len(chain) - 1, idx))
    c = chain[idx]
    return {"key": c.get("instrument_key"), "strike": float(c.get("strike_price", 0)),
            "lot": int(c.get("lot_size", 0) or 0), "expiry_date": exp,
            "moneyness_offset": offset}


def _candles_to_df(candles: list) -> pd.DataFrame:
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume", "OI"])
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    return df.set_index("Timestamp").sort_index()[["Open", "High", "Low", "Close", "Volume"]].astype(float)


def fetch_expired_premium_5min(expired_key: str, on_day: date, interval: str = "5minute") -> pd.DataFrame:
    """5-min premium candles for an EXPIRED option contract on a single day (oldest-first)."""
    if not expired_key:
        return pd.DataFrame()
    d = on_day.isoformat()
    url = f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(expired_key)}/{interval}/{d}/{d}"
    j = _get_json(url)
    if j.get("status") == "success":
        return _candles_to_df(j.get("data", {}).get("candles", []))
    return pd.DataFrame()
