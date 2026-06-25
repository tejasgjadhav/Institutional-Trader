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
import logging
import pandas as pd
from datetime import datetime, date

from engine.data_fetcher import SESSION, UPSTOX_BASE
from engine.instruments import to_instrument_key, encode_key

logger = logging.getLogger(__name__)

_EXPIRIES = {}    # underlying_key -> sorted [YYYY-MM-DD]
_CONTRACTS = {}   # (underlying_key, expiry) -> [contract dicts]


def get_expiries(ticker: str) -> list:
    """Sorted list of available expiry dates (YYYY-MM-DD) for an underlying."""
    uk = to_instrument_key(ticker)
    if not uk:
        return []
    if uk in _EXPIRIES:
        return _EXPIRIES[uk]
    try:
        r = SESSION.get(f"{UPSTOX_BASE}/v2/expired-instruments/expiries",
                        params={"instrument_key": uk}, timeout=20)
        r.raise_for_status()
        exps = sorted(r.json().get("data", []) or [])
    except Exception as e:
        logger.warning(f"expiries fetch failed for {ticker}: {e}")
        exps = []
    _EXPIRIES[uk] = exps
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
    try:
        r = SESSION.get(f"{UPSTOX_BASE}/v2/expired-instruments/option/contract",
                        params={"instrument_key": uk, "expiry_date": expiry}, timeout=20)
        r.raise_for_status()
        out = r.json().get("data", []) or []
    except Exception as e:
        logger.warning(f"contracts fetch failed for {ticker} {expiry}: {e}")
        out = []
    _CONTRACTS[ck] = out
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
    try:
        url = f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(expired_key)}/{interval}/{d}/{d}"
        r = SESSION.get(url, timeout=20)
        r.raise_for_status()
        j = r.json()
        if j.get("status") == "success":
            return _candles_to_df(j.get("data", {}).get("candles", []))
    except Exception as e:
        logger.warning(f"expired premium fetch failed for {expired_key} {d}: {e}")
    return pd.DataFrame()
