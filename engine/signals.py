"""
Signal Engine — 3-Family Alpha Scoring
TREND (momentum, trend quality, microstructure)
FLOW (options, macro regime)
EVENT (news, filings)
"""
import numpy as np
import pandas as pd
from scipy import stats
from engine.config import (
    FAMILY_WEIGHTS, ALPHA_Z_THRESHOLD, MIN_FAMILIES_AGREE,
    ORB_LOOKBACK_MINUTES, ORB_BREAKOUT_THRESHOLD_PCT, VOLUME_SURGE_MULTIPLIER
)


def _zscore_latest(series: pd.Series, clip: float = 3.0) -> float:
    """
    Z-score the latest value of a series against the series' own distribution.
    Returns 0.0 if there isn't enough spread/history. Clipped to ±clip.
    """
    s = series.dropna()
    if len(s) < 5:
        return 0.0
    mean = float(s.mean())
    std = float(s.std())
    if std < 1e-9:
        return 0.0
    z = (float(s.iloc[-1]) - mean) / std
    return float(max(-clip, min(clip, z)))


def compute_trend_family(df_5min: pd.DataFrame, df_daily: pd.DataFrame) -> dict:
    """
    TREND family = momentum + trend quality + microstructure.
    Each factor is z-scored against its OWN distribution (not a single point),
    so the readings are real numbers in roughly [-3, +3].
    """
    if df_5min.empty or df_daily.empty:
        return {"z_score": 0.0, "verdict": "NEUTRAL", "components": {}}

    close_now = float(df_5min["Close"].iloc[-1])

    # ── Momentum ──────────────────────────────────────────────────
    # Series of 1-hour (12-bar) intraday returns; z-score the latest.
    ret_1h = df_5min["Close"].pct_change(12) * 100
    momentum_z = _zscore_latest(ret_1h)

    # ── Trend Quality ─────────────────────────────────────────────
    # EMA(9)-EMA(21) spread over daily history; z-score the latest.
    if len(df_daily) >= 21:
        ema9 = df_daily["Close"].ewm(span=9, adjust=False).mean()
        ema21 = df_daily["Close"].ewm(span=21, adjust=False).mean()
        spread = (ema9 - ema21) / ema21 * 100
        trend_z = _zscore_latest(spread)
    else:
        trend_z = 0.0

    # ── Microstructure ────────────────────────────────────────────
    # ORB breakout (clean ±1 signal).
    orb_high = float(df_5min["High"].iloc[:ORB_LOOKBACK_MINUTES].max())
    orb_low = float(df_5min["Low"].iloc[:ORB_LOOKBACK_MINUTES].min())
    is_above_orb = close_now > orb_high * (1 + ORB_BREAKOUT_THRESHOLD_PCT)
    is_below_orb = close_now < orb_low * (1 - ORB_BREAKOUT_THRESHOLD_PCT)
    microstructure_z = 1.0 if is_above_orb else (-1.0 if is_below_orb else 0.0)

    # ── Aggregate (weighted average of the three factor z-scores) ──
    weights = FAMILY_WEIGHTS["TREND"]["factor_weights"]
    weighted_z = (
        momentum_z * weights["momentum"]
        + trend_z * weights["trend_quality"]
        + microstructure_z * weights["microstructure"]
    ) / sum(weights.values())

    verdict = "LONG" if weighted_z > 0.1 else ("SHORT" if weighted_z < -0.1 else "NEUTRAL")

    return {
        "z_score": round(weighted_z, 2),
        "verdict": verdict,
        "components": {
            "momentum_z": round(momentum_z, 2),
            "trend_quality_z": round(trend_z, 2),
            "microstructure_z": round(microstructure_z, 2),
        },
    }


def compute_flow_family(df_5min: pd.DataFrame, vix: float = None, nifty_pct: float = None) -> dict:
    """
    FLOW family = options PCR + macro regime (VIX, Nifty, FII/DII)
    Returns: {"z_score": float, "verdict": "LONG" | "SHORT" | "NEUTRAL", "components": {...}}
    """
    components = {}
    parts = []  # collect available sub-signals, then average

    # ── Macro regime: VIX ───────────────────────────────────────
    if vix is not None:
        # VIX < 15 = calm (risk-on, bullish), VIX > 18 = fear (bearish)
        vix_z = 1.0 if vix < 15 else (-1.0 if vix > 18 else 0.0)
        components["vix_z"] = round(vix_z, 2)
        parts.append(vix_z)

    # ── Macro regime: Nifty trend ───────────────────────────────
    if nifty_pct is not None:
        nifty_z = 1.0 if nifty_pct > 0.3 else (-1.0 if nifty_pct < -0.3 else 0.0)
        components["nifty_z"] = round(nifty_z, 2)
        parts.append(nifty_z)

    # ── Volume confirmation ─────────────────────────────────────
    if not df_5min.empty and len(df_5min) >= 10:
        vol_recent = df_5min["Volume"].iloc[-5:].mean()
        vol_avg = df_5min["Volume"].iloc[:-5].mean()
        vol_ratio = vol_recent / vol_avg if vol_avg > 0 else 1.0
        vol_z = 1.0 if vol_ratio > 1.2 else (-1.0 if vol_ratio < 0.8 else 0.0)
        components["volume_z"] = round(vol_z, 2)
        parts.append(vol_z)

    # Average of available sub-signals → keeps FLOW in [-1, 1]
    flow_z = sum(parts) / len(parts) if parts else 0.0

    verdict = "LONG" if flow_z > 0.1 else ("SHORT" if flow_z < -0.1 else "NEUTRAL")

    return {
        "z_score": round(flow_z, 2),
        "verdict": verdict,
        "components": components,
    }


def compute_event_family(news_sentiment: float = 0.0, has_corporate_event: bool = False) -> dict:
    """
    EVENT family = news + corporate events
    NOTE: This family cannot be backtested on free data; treat as experimental.
    Returns: {"z_score": float, "verdict": "LONG" | "SHORT" | "NEUTRAL", "components": {...}}
    """
    # EVENT is driven by the DIRECTION of the news, not merely its presence.
    # news_sentiment is the scraped NSE-announcement score in [-1, +1]:
    #   +1 = clearly bullish filing, -1 = clearly bearish, 0 = neutral/no event.
    # A neutral filing (has_corporate_event but sentiment 0) stays NEUTRAL — it
    # must NOT bias the vote bullish.
    event_z = float(news_sentiment)
    verdict = "LONG" if event_z > 0.1 else ("SHORT" if event_z < -0.1 else "NEUTRAL")

    return {
        "z_score": round(event_z, 2),
        "verdict": verdict,
        "components": {
            "news_sentiment": round(news_sentiment, 2),
            "has_event": has_corporate_event,
        },
    }


def compute_alpha_z(trend: dict, flow: dict, event: dict) -> dict:
    """
    Weighted average of 3 families into single alpha-z score.
    alpha-z = (z_trend × w_trend + z_flow × w_flow + z_event × w_event) / (w_trend + w_flow + w_event)

    Returns:
    {
        "alpha_z": float,
        "passes_gate_1": bool,  # |alpha_z| > ALPHA_Z_THRESHOLD AND ≥ 2 families agree
        "direction": "LONG" | "SHORT" | "NEUTRAL",
        "breadth": int,  # number of families agreeing with direction
        "families_detail": {...},
    }
    """
    families = {
        "TREND": trend,
        "FLOW": flow,
        "EVENT": event,
    }

    # Weighted sum
    numerator = (
        trend["z_score"] * FAMILY_WEIGHTS["TREND"]["weight"]
        + flow["z_score"] * FAMILY_WEIGHTS["FLOW"]["weight"]
        + event["z_score"] * FAMILY_WEIGHTS["EVENT"]["weight"]
    )
    denominator = sum(f["weight"] for f in FAMILY_WEIGHTS.values())
    alpha_z = numerator / denominator if denominator > 0 else 0.0

    # Direction: sign of alpha_z
    direction = "LONG" if alpha_z > 0.1 else ("SHORT" if alpha_z < -0.1 else "NEUTRAL")

    # Breadth: how many families agree with direction
    breadth = 0
    for family_name, family_result in families.items():
        if direction == "LONG" and family_result["verdict"] == "LONG":
            breadth += 1
        elif direction == "SHORT" and family_result["verdict"] == "SHORT":
            breadth += 1

    # Gate 1: |alpha_z| > threshold AND breadth ≥ 2
    passes_gate_1 = abs(alpha_z) > ALPHA_Z_THRESHOLD and breadth >= MIN_FAMILIES_AGREE

    return {
        "alpha_z": round(alpha_z, 2),
        "direction": direction,
        "breadth": breadth,
        "passes_gate_1": passes_gate_1,
        "families_detail": families,
    }


def compute_all_families(ticker: str, df_5min: pd.DataFrame, df_daily: pd.DataFrame,
                         vix: float = None, nifty_pct: float = None,
                         news_sentiment: float = 0.0, has_event: bool = False) -> dict:
    """
    Full signal computation: 3 families → alpha-z → Gate 1 verdict
    """
    trend = compute_trend_family(df_5min, df_daily)
    flow = compute_flow_family(df_5min, vix, nifty_pct)
    event = compute_event_family(news_sentiment, has_event)
    alpha_result = compute_alpha_z(trend, flow, event)

    return {
        "ticker": ticker,
        "trend": trend,
        "flow": flow,
        "event": event,
        "alpha_z": alpha_result["alpha_z"],
        "direction": alpha_result["direction"],
        "breadth": alpha_result["breadth"],
        "passes_gate_1": alpha_result["passes_gate_1"],
        "families_detail": alpha_result["families_detail"],
    }


def is_orb_confirmed(df_5min: pd.DataFrame) -> tuple:
    """
    ORB confirmation: latest 5-min bar closes beyond the 30-min opening range
    (first 6 bars) with a volume surge vs the RECENT rolling average.

    The volume benchmark is the recent VOL_LOOKBACK_BARS (not the opening range),
    so a real midday breakout — when alpha signals actually form but opening-level
    volume has faded — can still confirm.

    Returns: (confirmed: bool, direction: str, volume_ratio: float)
    """
    from engine.config import ORB_BARS, VOL_LOOKBACK_BARS
    if df_5min.empty or len(df_5min) < ORB_BARS + 1:
        return False, "NEUTRAL", 0.0

    # Opening range = first 6 bars (9:15-9:44)
    orb_high = float(df_5min["High"].iloc[:ORB_BARS].max())
    orb_low = float(df_5min["Low"].iloc[:ORB_BARS].min())

    latest_close = float(df_5min["Close"].iloc[-1])
    latest_volume = float(df_5min["Volume"].iloc[-1])

    # Volume surge vs the RECENT rolling average (exclude the latest bar)
    recent = df_5min["Volume"].iloc[-(VOL_LOOKBACK_BARS + 1):-1]
    recent_avg = float(recent.mean()) if len(recent) else 0.0
    volume_ratio = latest_volume / recent_avg if recent_avg > 0 else 0.0

    is_above_orb = latest_close > orb_high * (1 + ORB_BREAKOUT_THRESHOLD_PCT)
    is_below_orb = latest_close < orb_low * (1 - ORB_BREAKOUT_THRESHOLD_PCT)
    vol_confirmed = volume_ratio >= VOLUME_SURGE_MULTIPLIER

    confirmed = (is_above_orb or is_below_orb) and vol_confirmed
    direction = "LONG" if (is_above_orb and vol_confirmed) else ("SHORT" if (is_below_orb and vol_confirmed) else "NEUTRAL")
    return confirmed, direction, round(volume_ratio, 2)
