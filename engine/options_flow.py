"""
Per-stock OPTIONS FLOW — real derivatives positioning from the Upstox option chain.

Replaces the old market-wide VIX/Nifty proxy in the FLOW family with genuine per-stock
signals computed from the live option chain:

  - PCR (Put-Call Ratio by OI)         = total put OI / total call OI
  - PCR trend (vs prev_oi)             = is put OI growing vs call OI?
  - OI buildup (net put vs call OI Δ)  = which side are writers adding to?

Interpretation (OI-writing view): writers SELL puts when they expect SUPPORT (bullish)
and SELL calls when they expect RESISTANCE (bearish). So put OI accumulating / PCR
rising = bullish; call OI accumulating / PCR falling = bearish.

Cached ~10 min per ticker (OI moves slowly; keeps the 5-min scan light).
"""
import time
import logging
import requests
from datetime import datetime

from engine.config import IST, UPSTOX_ANALYTICS_TOKEN
from engine.instruments import to_instrument_key
from engine.options import _load_index

logger = logging.getLogger(__name__)

_BASE = "https://api.upstox.com"
_H = {"Authorization": f"Bearer {UPSTOX_ANALYTICS_TOKEN}", "Accept": "application/json"}
_CACHE = {}        # ticker -> (epoch_ts, flow_dict)
_TTL = 600         # seconds (10 min)


def _nearest_expiry(underlying_key: str):
    idx = _load_index()
    contracts = idx.get(underlying_key, [])
    if not contracts:
        return None
    now = datetime.now(IST)
    dm = int(datetime(now.year, now.month, now.day).timestamp() * 1000)
    future = sorted({c["expiry"] for c in contracts if c["expiry"] >= dm})
    return datetime.fromtimestamp(future[0] / 1000).date().isoformat() if future else None


def fetch_options_flow(ticker: str) -> dict:
    """
    Real options flow for a stock from the option chain. Returns {} if unavailable.
    Keys: pcr, pcr_prev, ce_oi, pe_oi, ce_oi_chg, pe_oi_chg, spot.
    """
    if not UPSTOX_ANALYTICS_TOKEN:
        return {}
    now = time.time()
    hit = _CACHE.get(ticker)
    if hit and (now - hit[0]) < _TTL:
        return hit[1]
    try:
        und = to_instrument_key(ticker)
        if not und:
            return {}
        exp = _nearest_expiry(und)
        if not exp:
            return {}
        r = requests.get(f"{_BASE}/v2/option/chain",
                         params={"instrument_key": und, "expiry_date": exp},
                         headers=_H, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            return {}
        ce_oi = pe_oi = ce_prev = pe_prev = 0.0
        spot = None
        for row in data:
            spot = row.get("underlying_spot_price") or spot
            cm = (row.get("call_options") or {}).get("market_data") or {}
            pm = (row.get("put_options") or {}).get("market_data") or {}
            ce_oi += cm.get("oi") or 0
            ce_prev += cm.get("prev_oi") or 0
            pe_oi += pm.get("oi") or 0
            pe_prev += pm.get("prev_oi") or 0
        flow = {
            "pcr": round(pe_oi / ce_oi, 3) if ce_oi else 0.0,
            "pcr_prev": round(pe_prev / ce_prev, 3) if ce_prev else 0.0,
            "ce_oi": ce_oi, "pe_oi": pe_oi,
            "ce_oi_chg": ce_oi - ce_prev, "pe_oi_chg": pe_oi - pe_prev,
            "spot": spot,
        }
        _CACHE[ticker] = (now, flow)
        return flow
    except Exception as e:
        logger.warning(f"options flow fetch failed for {ticker}: {e}")
        return {}
