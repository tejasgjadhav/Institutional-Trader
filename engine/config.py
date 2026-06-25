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
# Go-live bar. With +10% target / -15% stop the BREAKEVEN win rate is 15/25 = 60%. The 1-year
# real-option backtest realised only ~55% on stocks (-1.0% profit) — BELOW breakeven — so the
# 0.62 go-live bar correctly keeps the stock side in PAPER. It is NOT a proven profitable
# strategy; -15 (vs -20) is kept only because it loses LESS at a sub-breakeven win rate.
PAPER_TRADING_BREAKEVEN_WIN_RATE = 0.60
PAPER_TRADING_MIN_WIN_RATE = 0.62
PAPER_TRADING_MIN_PF = 1.0

# === UNIVERSE — reverted to the proven hand-picked 94 (beat the free-float-mcap 100
# head-to-head: 67% vs 61% win on the SAME 60-day window, gates 1-5 +10/-20; the mega-cap
# additions were net losers at 53%/-2.8%, the removed mid-caps were the best at 75%/+4.3%).
# + the 5 persistent-winner PRIORITY names not already in the 94 + ETERNAL (ex-ZOMATO).
# All F&O-eligible (live candles + resolvable option chains). ===
UNIVERSE = [
    # Reverted to the proven 94 (beat mcap-100 head-to-head 67% vs 61% on same window),
    # + 5 persistent-winner priority names not already in it + ETERNAL (ex-ZOMATO).
    "TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS", "MPHASIS.NS",
    "COFORGE.NS", "PERSISTENT.NS", "OFSS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS",
    "SBIN.NS", "AXISBANK.NS", "INDUSINDBK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS", "BANDHANBNK.NS",
    "BANKBARODA.NS", "PNB.NS", "UNIONBANK.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "HDFCLIFE.NS",
    "SBILIFE.NS", "CHOLAFIN.NS", "MUTHOOTFIN.NS", "SHRIRAMFIN.NS", "RECLTD.NS", "PFC.NS",
    "IRFC.NS", "RELIANCE.NS", "ONGC.NS", "BPCL.NS", "IOC.NS", "COALINDIA.NS",
    "POWERGRID.NS", "NTPC.NS", "TATAPOWER.NS", "ADANIGREEN.NS", "LT.NS", "ADANIENT.NS",
    "ADANIPORTS.NS", "SIEMENS.NS", "ABB.NS", "BHEL.NS", "HAVELLS.NS", "POLYCAB.NS",
    "VOLTAS.NS", "ULTRACEMCO.NS", "GRASIM.NS", "AMBUJACEM.NS", "ACC.NS", "JSWSTEEL.NS",
    "TATASTEEL.NS", "HINDALCO.NS", "VEDL.NS", "SAIL.NS", "NMDC.NS", "MARUTI.NS",
    "BAJAJ-AUTO.NS", "HEROMOTOCO.NS", "EICHERMOT.NS", "M&M.NS", "ASHOKLEY.NS", "BALKRISIND.NS",
    "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS", "ASIANPAINT.NS",
    "GODREJCP.NS", "MARICO.NS", "DABUR.NS", "PIDILITIND.NS", "SUNPHARMA.NS", "DRREDDY.NS",
    "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "LUPIN.NS", "TORNTPHARM.NS", "AUROPHARMA.NS",
    "ZYDUSLIFE.NS", "TITAN.NS", "DMART.NS", "TRENT.NS", "JUBLFOOD.NS", "BHARTIARTL.NS",
    "NAUKRI.NS", "INDIGO.NS", "DLF.NS", "GODREJPROP.NS", "JINDALSTEL.NS", "INDIANB.NS",
    "AUBANK.NS", "BAJAJHLDNG.NS", "TATAELXSI.NS", "ETERNAL.NS",
]
assert len(UNIVERSE) == 100, "Universe should have 100 stocks"

# PRIORITY stocks — the only names whose high gates-1-5 win rate PERSISTED out-of-sample.
# Found by a 365-day per-stock backtest split into train (older 60%) / held-out test (newer
# 40%): selecting the top-60 by *train* win rate overfit badly (64% train -> 49% test), but
# these 13 won in BOTH independent windows (combined ~75% over 110 trades). The engine still
# scans and fires on all 100; this list ONLY flags these in the read-only UI so you can choose
# to focus / size up on them. It does NOT change engine selection. Small sample — treat as a
# tilt, not a guarantee. See studies/PRIORITY_STOCKS_PERSISTENCE.md.
PRIORITY_STOCKS = [
    "BAJFINANCE.NS", "RECLTD.NS", "AUROPHARMA.NS", "JINDALSTEL.NS", "INDIANB.NS",
    "AUBANK.NS", "BAJAJHLDNG.NS", "POWERGRID.NS", "ASHOKLEY.NS", "TATAELXSI.NS",
    "SHRIRAMFIN.NS", "INDUSINDBK.NS", "PERSISTENT.NS",
]

# Index underlyings to scan for options (low capital, liquid weekly/monthly expiries)
SCAN_INDICES = ["NIFTY", "BANKNIFTY"]

# === DATA SOURCES ===
UPSTOX_ANALYTICS_TOKEN = os.getenv("UPSTOX_ANALYTICS_TOKEN")
USE_YAHOO_FALLBACK = True  # If Upstox fails, fall back to Yahoo (15-min delay)

# === TIMING (IST) ===
MARKET_OPEN = "09:15"
TRADING_START = "09:45"  # Scanning/observation starts; trades fire from here to the cutoff
NO_NEW_TRADES_AFTER = "13:00"  # No new signals after 1 PM (wider 9:45-1PM window kept —
# Run K showed 12:30-1PM is 77% vs 72% overall, but on only 13 trades = within noise,
# so we keep the wider, less-overfit window. In practice nothing fires before ~11:30.)
KILL_SWITCH_TIME = "15:10"  # Force close all positions
MARKET_CLOSE = "15:30"

# === SIGNAL GATES ===
ALPHA_Z_THRESHOLD = 0.55  # |alpha-z| must be strictly > this (0.55 does NOT trade)
MIN_FAMILIES_AGREE = 2  # At least 2 of 3 families must align
# Gate 3 — MARKET ALIGNMENT: block signals that FIGHT the Nifty's intraday direction
# (only LONG when Nifty is up, only SHORT when Nifty is down). 30-day backtest: lifts
# win rate 58%->60% and P&L +1.0%->+1.6% by cutting trend-fighting trades.
MARKET_ALIGN_FILTER = True
# Gate 4 — DON'T CHASE: skip a signal if the stock has already moved more than this %
# in the trade's direction from the day's open (you'd be buying a stock that already ran).
# Tuned to 2.9: cutting only the extreme chasers (>2.9%) beat the tighter 2.6 cap on every
# metric in both windows — 30d win 56%->58% P&L Rs9.3k->Rs13.1k, 60d win 60%->61% P&L
# Rs32.9k->Rs36.8k, return-on-capital 2.5%->2.8% — because the 2.6-2.9% band still holds
# decent trades. The 2.6 cap was over-aggressive.
# DISABLED 2026-06 after the REAL-option 180-day backtest (expired-instruments data): the
# extension filter looked good in-sample but did NOT hold out-of-sample (train win +14 pts ->
# test +0). Kept as a tunable but OFF. See studies/REAL_OPTION_OPTIMIZATION.md.
ENTRY_EXTENSION_FILTER = False
MAX_ENTRY_EXTENSION_PCT = 2.9
# Gate 5 — WIDE OPEN: only trade when the first-30-min opening range is at least this % of
# price wide. A wider opening range = real morning momentum (cleaner breakouts); a narrow,
# low-energy open is chop. Found via a 90-day option search, VALIDATED on 365 days (506
# trades): win 51%->54% directional, and option win 30d 61%->66% / 60d 66%->70% at +10/-20.
# DISABLED 2026-06: same reason — the ORB-width filter held in-sample (train win +7) but faded
# out-of-sample (test -2) on the real 180-day option backtest. OFF. See REAL_OPTION_OPTIMIZATION.md.
ORB_RANGE_FILTER = False
ORB_RANGE_WIDTH_MIN = 0.8   # opening-range width as % of price
# Gate 5b — MIN OPTION PREMIUM: only trade when the OTM+1 option premium >= this. It LOOKED
# like a profit edge on a 180-day window (54%->64% win) but that did NOT survive the 1-year
# backtest (55% win, -1.0% profit — overfit to a recent regime). KEPT anyway for a *cost*
# reason: cheap OTM lottery options (avg Rs38) have a ~3x WIDER % bid-ask spread than richer
# ones (avg Rs101), so this filter reduces the biggest hidden cost — NOT a proven profit edge.
# See studies/REAL_OPTION_OPTIMIZATION.md (the CORRECTION at the top).
MIN_OPTION_PREMIUM_FILTER = True
MIN_OPTION_PREMIUM = 30.0
# Gate 6 — LIQUIDITY: only fire if the exact option we'd trade has a real, tight market.
# Checked ONLY for signals that already clear Gates 1-5 (~1-2/day), so ~1-2 extra quote
# calls/day — negligible. With a +10% target you cannot afford a wide spread: you buy at
# the ask and sell at the bid, so a 4%+ spread eats the edge and the LTP may be stale.
LIQUIDITY_FILTER = True
MAX_OPTION_SPREAD_PCT = 4.0   # skip if (ask-bid)/mid > this %
MIN_OPTION_OI = 100           # skip if open interest below this (a real position base)
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
# No daily-trade cap — take EVERY qualifying signal (was 3). 0 = unlimited.
MAX_TRADES_PER_DAY = 0
CONSECUTIVE_LOSS_HALT = 3  # Halt trading after 3 stops in a row
STOP_LOSS_CAP_PCT = 1.0  # Stop can't be more than 1% away from entry

# === OPTIONS-ONLY BUYING MODE (validated profile) ===
# We BUY options only (never sell): LONG signal -> ATM CALL, SHORT signal -> ATM PUT.
# Exit on the OPTION PREMIUM (what you actually trade), NOT the underlying.
# Recent 20-day backtest on real premium: +10% target / -20% stop = 77% win rate,
# +3.74%/trade expectancy (13 trades — promising, must be confirmed forward).
OPTIONS_ONLY_MODE   = True    # all signals become buy-CALL / buy-PUT
PREMIUM_TARGET_PCT  = 10.0    # book profit at +10% on the option premium
PREMIUM_STOP_PCT    = 15.0    # cut loss at -15% (was -20; real-180d backtest: tighter stop + min-prem = +profit)
OPTION_IV_THRESHOLD = 60      # skip if ATM IV too high (very expensive premium)
# Strike offset from ATM: 0=ATM, +1=one strike OTM, -1=one strike ITM.
# Backtest (Run H) favoured OTM+1 (best expectancy + good win rate, cheap, liquid).
OPTION_STRIKE_OFFSET = 1      # OTM+1 (CALL: one strike above spot · PUT: one below)

# Legacy underlying targets (kept for the equity/future path if OPTIONS_ONLY_MODE=False)
TARGET_PCT_EQUITY     = 1.0
TARGET_PCT_DERIVATIVE = 5.0

# === ORB+VWAP INDEX STRATEGY (parallel paper forward-test) ===
# Runs ALONGSIDE the 3-Family system on NIFTY/BANKNIFTY and is reported in its own
# section on PM DECISIONS. Signal: 15-min ORB break on the index FUTURES + hold VWAP
# + 30-min trend aligned + entry before the cutoff. Buys ATM, exits +/-20% on premium.
# NOTE: Apr-Jun 2026 backtests show this is ~breakeven (NIFTY -0.5%, BANKNIFTY +0.3%);
# it runs LIVE here to forward-test it, NOT because it is proven profitable.
ORB_VWAP_ENABLED      = True
# EXIT: trend-ride (not a fixed target). ORB+VWAP is a trend setup — a fixed +20%
# cap chopped winners short while still eating full -20% stops (60d backtest: 27%
# win, -2.6%/trade). Trend-ride lets winners run and exits only when the futures
# reclaim VWAP (after the trade is in profit), keeping the -20% hard stop. 60d: 63%
# win, +0.8%/trade gross with the clean-trend entry filter.
ORB_VWAP_EXIT_MODE    = "trend_ride"  # "trend_ride" (live) | "fixed_target" (legacy)
ORB_VWAP_TARGET_PCT   = 20.0   # legacy fixed-target cap (only used if EXIT_MODE="fixed_target")
ORB_VWAP_STOP_PCT     = 15.0   # -15% premium hard stop (was -20; index real backtest best at -15)
ORB_VWAP_ARM_PCT      = 12.0   # trend-ride: arm the VWAP-reclaim exit only after +12% premium
ORB_VWAP_CLEAN_TREND  = True   # entry filter: require VWAP sloped the trade way + >0.25% extended
ORB_VWAP_ENTRY_CUTOFF = "11:00"  # no new ORB+VWAP entries after this (first-90-min filter)
ORB_VWAP_STRIKE_OFFSET = 0     # 0=ATM, -1=ITM, +1=OTM
ORB_VWAP_TREND_BARS    = 6     # 30-min trend filter (6 x 5-min bars)

# === INSTRUMENT SELECTION ===
# In OPTIONS_ONLY_MODE the instrument is always CALL (LONG) or PUT (SHORT).
# Otherwise: |alpha-z| 0.55-0.70 LONG=equity / SHORT=future; >0.70 = CALL/PUT.
OPTION_CONVICTION_THRESHOLD_NOTE = "see OPTION_CONVICTION_THRESHOLD above"

# === FACTOR WEIGHTS (backtested on 30-day history) ===
# Each family produces a z-score; families are weighted by real hit-rate
FAMILY_WEIGHTS = {
    "TREND": {
        "weight": 0.72,  # raised from 0.65 (the proven, dominant family)
        "factors": ["momentum", "trend_quality", "microstructure"],
        "factor_weights": {
            "momentum": 0.37,
            "trend_quality": 0.24,
            "microstructure": 0.04,
        },
    },
    "FLOW": {
        "weight": 0.18,  # macro regime (VIX, Nifty trend) + volume
        "factors": ["pcr_ratio", "macro_regime"],
    },
    "EVENT": {
        # Lowered 0.18 -> 0.10: live NSE-announcement sentiment is kept informative
        # but down-weighted — a 30-day historical test showed it didn't lift win rate
        # (crude keyword scoring), so it must not drag the vote. Still shown on ALPHA.
        "weight": 0.10,
        "factors": ["news_sentiment", "corporate_events"],
    },
}

# Sanity check: weights should sum to ~1.0
total_weight = sum(f["weight"] for f in FAMILY_WEIGHTS.values())
assert 0.95 < total_weight < 1.05, f"Family weights sum to {total_weight}, should be ~1.0"

# === TECHNICAL FILTERS ===
ORB_BARS = 6               # opening range = first 6 bars of 5-min = 30 min (9:15-9:44)
ORB_LOOKBACK_MINUTES = 6   # kept for backward-compat; now a BAR count (= ORB_BARS)
ORB_BREAKOUT_THRESHOLD_PCT = 0.01  # Close must be > ORB High (or < ORB Low) by this %
# Volume surge is now measured vs a ROLLING RECENT average (last VOL_LOOKBACK_BARS),
# NOT the opening range — so a genuine MIDDAY breakout (when alpha signals form, but
# opening-level volume has faded) can still confirm.
VOLUME_SURGE_MULTIPLIER = 1.2  # latest bar volume must be >= 1.2x the benchmark
VOL_LOOKBACK_BARS = 10         # recent-volume baseline window (last ~50 min)
# Volume benchmark: "rolling" = recent ~50 min (more signals); "opening" = the
# opening-range average (stricter — only the strongest breakouts pass, fewer signals).
VOLUME_BENCHMARK_MODE = "rolling"
# Bars used for the intraday momentum factor (12 x 5-min = 60 min). Made configurable
# so it can scale when the candle timeframe changes (e.g. 6 bars on 10-min = 60 min).
MOMENTUM_BARS = 12

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
