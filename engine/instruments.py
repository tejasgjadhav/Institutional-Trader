"""
Instrument Resolver — Maps NSE symbols to Upstox ISIN-based instrument keys.
Upstox V3 API requires instrument keys like 'NSE_EQ|INE467B01029', not 'NSE_EQ|TCS'.

The instrument master is downloaded once and cached locally. Refresh weekly
(ISINs are stable, but new listings/changes happen).
"""
import os
import json
import gzip
import logging
from datetime import datetime, timedelta
import requests

from engine.config import DATA_DIR

logger = logging.getLogger(__name__)

INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
CACHE_PATH = os.path.join(DATA_DIR, "upstox_instruments.json")
CACHE_MAX_AGE_DAYS = 7

# Index instrument keys (these are fixed, not in the equity master)
INDEX_KEYS = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "VIX": "NSE_INDEX|India VIX",
}


def _download_instruments() -> list:
    """Download and decompress the Upstox NSE instrument master."""
    logger.info("Downloading Upstox NSE instrument master...")
    r = requests.get(INSTRUMENTS_URL, timeout=30)
    r.raise_for_status()
    data = json.loads(gzip.decompress(r.content))
    logger.info(f"Downloaded {len(data)} NSE instruments")
    return data


def _build_symbol_map(instruments: list) -> dict:
    """Build {trading_symbol: instrument_key} for NSE_EQ equities only."""
    symbol_map = {}
    for inst in instruments:
        if inst.get("segment") == "NSE_EQ" and inst.get("instrument_type") == "EQ":
            symbol = inst.get("trading_symbol")
            key = inst.get("instrument_key")
            if symbol and key:
                symbol_map[symbol] = key
    return symbol_map


def _cache_is_fresh() -> bool:
    """Check if the cached instrument map exists and is recent."""
    if not os.path.exists(CACHE_PATH):
        return False
    try:
        with open(CACHE_PATH) as f:
            cache = json.load(f)
        cached_at = datetime.fromisoformat(cache["cached_at"])
        age = datetime.now() - cached_at
        return age < timedelta(days=CACHE_MAX_AGE_DAYS)
    except Exception:
        return False


def _load_or_refresh() -> dict:
    """Load symbol map from cache, or download and rebuild if stale."""
    if _cache_is_fresh():
        with open(CACHE_PATH) as f:
            return json.load(f)["symbol_map"]

    instruments = _download_instruments()
    symbol_map = _build_symbol_map(instruments)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump({
            "cached_at": datetime.now().isoformat(),
            "symbol_map": symbol_map,
        }, f)
    logger.info(f"Cached {len(symbol_map)} equity instrument keys")
    return symbol_map


# Module-level singleton
_SYMBOL_MAP = None


def _get_symbol_map() -> dict:
    global _SYMBOL_MAP
    if _SYMBOL_MAP is None:
        _SYMBOL_MAP = _load_or_refresh()
    return _SYMBOL_MAP


def to_instrument_key(ticker: str) -> str:
    """
    Convert a ticker to an Upstox instrument key.

    Accepts:
      - 'TCS.NS' or 'TCS'        → 'NSE_EQ|INE467B01029'
      - '^NSEI' / 'NIFTY'        → 'NSE_INDEX|Nifty 50'
      - '^NSEBANK' / 'BANKNIFTY' → 'NSE_INDEX|Nifty Bank'
      - '^INDIAVIX' / 'VIX'      → 'NSE_INDEX|India VIX'

    Returns None if the symbol can't be resolved.
    """
    # Index aliases
    index_aliases = {
        "^NSEI": "NIFTY", "NIFTY": "NIFTY", "NIFTY 50": "NIFTY",
        "^NSEBANK": "BANKNIFTY", "BANKNIFTY": "BANKNIFTY", "NIFTY BANK": "BANKNIFTY",
        "^INDIAVIX": "VIX", "VIX": "VIX", "INDIA VIX": "VIX",
    }
    if ticker in index_aliases:
        return INDEX_KEYS[index_aliases[ticker]]

    # Equity: strip .NS suffix
    symbol = ticker.replace(".NS", "").strip()
    symbol_map = _get_symbol_map()
    key = symbol_map.get(symbol)
    if key is None:
        logger.warning(f"No instrument key found for '{ticker}' (symbol '{symbol}')")
    return key


def encode_key(instrument_key: str) -> str:
    """URL-encode an instrument key (the '|' must become %7C)."""
    return instrument_key.replace("|", "%7C")


def resolve_universe(tickers: list) -> dict:
    """Resolve a list of tickers to {ticker: instrument_key}, skipping unresolved."""
    result = {}
    for t in tickers:
        key = to_instrument_key(t)
        if key:
            result[t] = key
    return result
