"""
Options Resolver — find the ATM CALL/PUT contract for a stock on a given day
and fetch its historical 5-min premium from Upstox.

Used by the option-aware backtest so CALL/PUT signals are evaluated on the
OPTION PREMIUM (what a trader actually exits on), not the underlying stock.
"""
import os
import json
import gzip
import logging
from datetime import datetime, date
import requests

from engine.config import DATA_DIR, UPSTOX_ANALYTICS_TOKEN, IST
from engine.data_fetcher import fetch_upstox_historical
from engine.instruments import to_instrument_key

logger = logging.getLogger(__name__)

COMPLETE_URL = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
OPT_CACHE = os.path.join(DATA_DIR, "upstox_options.json")
CACHE_MAX_AGE_DAYS = 1  # option chains change daily (new strikes/expiries)

_OPT_INDEX = None  # {underlying_key: [contract, ...]}


def _download_options() -> dict:
    """Download complete master, keep NSE_FO CE/PE, index by underlying_key."""
    logger.info("Downloading Upstox options master...")
    raw = json.loads(gzip.decompress(requests.get(COMPLETE_URL, timeout=60).content))
    index = {}
    for i in raw:
        if i.get("segment") == "NSE_FO" and i.get("instrument_type") in ("CE", "PE"):
            uk = i.get("underlying_key")
            if not uk:
                continue
            index.setdefault(uk, []).append({
                "key": i["instrument_key"],
                "type": i["instrument_type"],
                "strike": float(i["strike_price"]),
                "expiry": int(i["expiry"]),  # epoch ms
                "lot": int(i.get("lot_size", 0)),
            })
    logger.info(f"Indexed options for {len(index)} underlyings")
    return index


def _cache_fresh() -> bool:
    if not os.path.exists(OPT_CACHE):
        return False
    try:
        age = datetime.now().timestamp() - os.path.getmtime(OPT_CACHE)
        return age < CACHE_MAX_AGE_DAYS * 86400
    except Exception:
        return False


def _load_index() -> dict:
    global _OPT_INDEX
    if _OPT_INDEX is not None:
        return _OPT_INDEX
    if _cache_fresh():
        with open(OPT_CACHE) as f:
            _OPT_INDEX = json.load(f)
        return _OPT_INDEX
    _OPT_INDEX = _download_options()
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OPT_CACHE, "w") as f:
        json.dump(_OPT_INDEX, f)
    return _OPT_INDEX


def get_atm_option(ticker: str, spot: float, on_day: date, opt_type: str) -> dict:
    """
    Find the ATM CALL ('CE') or PUT ('PE') for `ticker` whose expiry is the
    nearest one on/after `on_day`. Returns the contract dict or None.
    """
    underlying = to_instrument_key(ticker)
    if not underlying:
        return None
    index = _load_index()
    contracts = [c for c in index.get(underlying, []) if c["type"] == opt_type]
    if not contracts:
        return None

    day_ms = int(datetime(on_day.year, on_day.month, on_day.day).timestamp() * 1000)
    # nearest expiry on/after the signal day
    future = sorted({c["expiry"] for c in contracts if c["expiry"] >= day_ms})
    if not future:
        return None
    near = future[0]
    chain = [c for c in contracts if c["expiry"] == near]
    atm = min(chain, key=lambda c: abs(c["strike"] - spot))
    atm["expiry_date"] = str(datetime.fromtimestamp(near / 1000).date())
    return atm


def fetch_option_premium_5min(option_key: str, on_day: date):
    """5-min premium candles for an option contract on a single day (oldest-first)."""
    d = on_day.strftime("%Y-%m-%d")
    return fetch_upstox_historical(option_key, unit="minutes", interval=5,
                                   from_date=d, to_date=d)
