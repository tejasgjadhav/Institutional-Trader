"""
Configuration — 3-Family Alpha NSE Intraday Trading System
All strategy parameters. Edit here to change behavior.
Paper trading mode: signals only, manual order placement in Upstox.
"""
import pytz
import os
from dotenv import load_dotenv

load_dotenv()

# Timezone
IST = pytz.timezone("Asia/Kolkata")

# === EXECUTION ===
EXECUTION_MODE = "PAPER"  # "PAPER" = signals only (manual orders in Upstox), "LIVE" = auto orders (not yet implemented)
PAPER_TRADING_PHASE = True  # If True, paper-log all signals before going live
PAPER_TRADING_MIN_SIGNALS = 30
PAPER_TRADING_MIN_WIN_RATE = 0.52
PAPER_TRADING_MIN_PF = 1.0

# === UNIVERSE ===
UNIVERSE = [
    "TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS",
    "MPHASIS.NS", "COFORGE.NS", "PERSISTENT.NS", "OFSS.NS",
    "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "SBIN.NS", "AXISBANK.NS",
    "INDUSINDBK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS", "BANDHANBNK.NS",
    "BANKBARODA.NS", "PNB.NS", "UNIONBANK.NS",
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "HDFCLIFE.NS", "SBILIFE.NS",
    "CHOLAFIN.NS", "MUTHOOTFIN.NS", "SHRIRAMFIN.NS", "RECLTD.NS", "PFC.NS", "IRFC.NS",
    "RELIANCE.NS", "ONGC.NS", "BPCL.NS", "IOC.NS", "COALINDIA.NS",
    "POWERGRID.NS", "NTPC.NS", "TATAPOWER.NS", "ADANIGREEN.NS",
    "LT.NS", "ADANIENT.NS", "ADANIPORTS.NS", "SIEMENS.NS", "ABB.NS",
    "BHEL.NS", "HAVELLS.NS", "POLYCAB.NS", "VOLTAS.NS",
    "ULTRACEMCO.NS", "GRASIM.NS", "AMBUJACEM.NS", "ACC.NS",
    "JSWSTEEL.NS", "TATASTEEL.NS", "HINDALCO.NS", "VEDL.NS", "SAIL.NS", "NMDC.NS",
    "MARUTI.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS",
    "EICHERMOT.NS", "M&M.NS", "ASHOKLEY.NS", "BALKRISIND.NS",
    "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS",
    "TATACONSUM.NS", "ASIANPAINT.NS", "GODREJCP.NS", "MARICO.NS", "DABUR.NS", "PIDILITIND.NS",
    "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS",
    "LUPIN.NS", "TORNTPHARM.NS", "AUROPHARMA.NS", "ZYDUSLIFE.NS",
    "TITAN.NS", "DMART.NS", "TRENT.NS", "JUBLFOOD.NS",
    "BHARTIARTL.NS", "NAUKRI.NS", "INDIGO.NS", "DLF.NS", "GODREJPROP.NS", "ZOMATO.NS",
]
assert len(UNIVERSE) == 95, "Universe should have 95 stocks"

# === DATA SOURCES ===
UPSTOX_ANALYTICS_TOKEN = os.getenv("UPSTOX_ANALYTICS_TOKEN")
USE_YAHOO_FALLBACK = True  # If Upstox fails, fall back to Yahoo (15-min delay)

# === TIMING (IST) ===
MARKET_OPEN = "09:15"
TRADING_START = "09:45"  # First 30 min is observation only
NO_NEW_TRADES_AFTER = "13:00"  # No new signals after 1 PM (afternoon entries can't reach target before close)
KILL_SWITCH_TIME = "15:10"  # Force close all positions
MARKET_CLOSE = "15:30"

# === SIGNAL GATES ===
ALPHA_Z_THRESHOLD = 0.55  # |alpha-z| must be strictly > this (0.55 does NOT trade)
MIN_FAMILIES_AGREE = 2  # At least 2 of 3 families must align
OPTION_CONVICTION_THRESHOLD = 0.70  # |alpha-z| > 0.70 trades as CALL/PUT instead of EQ/FUT

# === TRADING UNIVERSE FILTER (PF>1 / EXPECTANCY) ===
BACKTEST_LOOKBACK_DAYS = 60  # Re-rank daily after close
BACKTEST_REFRESH_TIME = "15:35"  # Time to refresh PF rankings (after market close)
TOP_N_TRADEABLE = 10  # Expand from 2 to 10 names (less overfitting)
EXPECTANCY_BLEND = {"60d": 0.65, "30d": 0.35, "live": 0.0}  # Live trade influence starts at 0%, grows to 50% max
EXPECTANCY_LIVE_MAX_INFLUENCE = 0.50

# === POSITION SIZING ===
CAPITAL = 100_000  # INR
RISK_PER_TRADE_INR = 2_000  # Fixed risk amount (stop-loss sized)
REWARD_RISK_RATIO = 2.0  # (legacy) generic target = Entry + 2x stop distance
MAX_TRADES_PER_DAY = 3
CONSECUTIVE_LOSS_HALT = 3  # Halt trading after 3 stops in a row
STOP_LOSS_CAP_PCT = 1.0  # Stop can't be more than 1% away from entry

# === TARGETS BY INSTRUMENT (underlying % move) ===
# Cash equity is unleveraged → small 1% target.
# Futures & options are leveraged → larger 5% underlying target (premium/contract
# gain is amplified by leverage, so a 5% underlying move is the exit trigger).
TARGET_PCT_EQUITY     = 1.0   # cash equity (|alpha-z| 0.55-0.70 LONG)
TARGET_PCT_DERIVATIVE = 5.0   # futures + CALL/PUT options (SHORT, or |alpha-z| > 0.70)

# === INSTRUMENT SELECTION ===
# Conviction levels determine instrument type
# LONG: 0.55-0.70 = equity, >0.70 = CALL
# SHORT: 0.55-0.70 = future, >0.70 = PUT
OPTION_IV_THRESHOLD = 40  # If IV > 40, fall back to futures (options too expensive)

# === FACTOR WEIGHTS (backtested on 30-day history) ===
# Each family produces a z-score; families are weighted by real hit-rate
FAMILY_WEIGHTS = {
    "TREND": {
        "weight": 0.65,  # sum of momentum(0.37) + trend_quality(0.24) + microstructure(0.04)
        "factors": ["momentum", "trend_quality", "microstructure"],
        "factor_weights": {
            "momentum": 0.37,
            "trend_quality": 0.24,
            "microstructure": 0.04,
        },
    },
    "FLOW": {
        "weight": 0.17,  # options PCR + macro regime (VIX, Nifty, FII/DII)
        "factors": ["pcr_ratio", "macro_regime"],
    },
    "EVENT": {
        "weight": 0.18,  # news + filings (unbacktested, use with caution)
        "factors": ["news_sentiment", "corporate_events"],
    },
}

# Sanity check: weights should sum to ~1.0
total_weight = sum(f["weight"] for f in FAMILY_WEIGHTS.values())
assert 0.95 < total_weight < 1.05, f"Family weights sum to {total_weight}, should be ~1.0"

# === TECHNICAL FILTERS ===
ORB_LOOKBACK_MINUTES = 30  # 9:15-9:44 AM
ORB_BREAKOUT_THRESHOLD_PCT = 0.01  # Close must be > ORB High (or < ORB Low) by this %
VOLUME_SURGE_MULTIPLIER = 1.2  # 5-min volume must be ≥ 1.2× average (conservative)

# === BACKTEST CONFIG ===
BACKTEST_MIN_WIN_RATE = 0.60  # Minimum win rate to include in PF>1 universe
BACKTEST_COMMISSION_PER_TRADE = 20  # INR
BACKTEST_SLIPPAGE_PCT = 0.001  # 0.1%

# === PATHS ===
DATA_DIR = "data"
LOG_DIR = "logs"
TRADE_LOG_PATH = f"{DATA_DIR}/trade_log.json"
SIGNALS_PATH = f"{DATA_DIR}/signals.json"
UNIVERSE_RANKING_PATH = f"{DATA_DIR}/universe_ranking.json"
APP_LOG_PATH = f"{LOG_DIR}/app.log"

# Create directories if missing
for d in [DATA_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)
