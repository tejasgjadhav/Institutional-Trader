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
    # === TIER-5 EXPANSION (2026-07-29, user-approved) — 13 F&O names that clear the c/w>=0.40
    # gate and ADD signals without diluting: blend 5.78->7.56 trades/mo (+31%), 84.1->85.5% win,
    # +25.7->+27.6% of width, +ve 6/6 yrs IS. IS-only (2019->Sep'24 bhavcopy; no per-name OOS —
    # Upstox premium history too short). Higher-priced/liquid mid-large caps. See
    # studies/UNIVERSE_EXPANSION.md. The c/w + live liquidity gates still decide each trade. ===
    "COLPAL.NS", "ASTRAL.NS", "INDIAMART.NS", "ALKEM.NS", "DALBHARAT.NS", "UBL.NS",
    "NAVINFLUOR.NS", "MRF.NS", "ATUL.NS", "CUMMINSIND.NS", "DEEPAKNTR.NS", "HAL.NS", "BOSCHLTD.NS",
]
assert len(UNIVERSE) == 113, "Universe should have 113 stocks (100 base + 13 Tier-5 expansion)"

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
KILL_SWITCH_TIME = "15:36"  # Force close all positions (moved 15:10 -> 15:36 with the scan)

# === NSE SESSION MODEL — REWRITTEN FOR THE 3-AUG-2026 CHANGE ===
# NSE moved the equity-derivatives close and introduced a Closing Auction Session (CAS):
#   F&O stocks   continuous cash trading now ENDS 15:15, then CAS 15:15-15:35
#                (orders 15:20-15:30, random cutoff 15:28-15:30, match 15:30-15:35).
#                Their official close is the AUCTION EQUILIBRIUM price, struck by 15:35.
#   other equity unchanged: continuous to 15:30, close = 15:00-15:30 VWAP.
#   DERIVATIVES  now trade to 15:40 (was 15:30) and use their own closing price
#                (VWAP window moved to 15:10-15:40), NOT the cash close.
# EVERY name in UNIVERSE is an F&O stock, so all of them are auction-priced now.
# Before this rewrite the close was a bare "15:30" literal in SEVEN separate places and
# MARKET_CLOSE was honoured by almost nothing — that is what made this dangerous.
CASH_CLOSE   = "15:30"   # non-F&O equities
CAS_END      = "15:35"   # F&O-stock cash close (auction equilibrium struck by here)
FNO_CLOSE    = "15:40"   # equity derivatives — what every one of our books actually trades
SETTLE_AFTER = "15:40"   # THE single settle knob: no position may settle before the F&O close
MARKET_CLOSE = CASH_CLOSE   # kept as an alias so existing readers keep their old meaning

# Grace window AFTER the F&O close during which the engine keeps its fast 5 s tick.
# Without this the settle lands in a dead spot: is_market_open() is inclusive to 15:40:00, so the
# cycle that actually settles (~15:40:0x) is the LAST fast cycle, and _outcomes() is throttled to
# 60 s — it almost always ran seconds earlier, so it skips. The loop then sleeps 300 s and every
# WIN/LOSS Telegram for the day lands ~15:45 instead of ~15:40. Six minutes of fast ticking costs
# nothing and puts the RESULT + PORTFOLIO messages out immediately after settlement.
SETTLE_GRACE_MIN = 6

# When the UNION WATCHLIST is built and its digest sent. 15:17 is the first moment the continuous
# session is complete (F&O stocks stop trading at 15:15) — it names the likely candidates ~19 min
# before the 15:36 scan so there is time to pre-stage. Kept in config, not as a bare literal in
# engine_runner, because the UI quotes it too and the two must never drift.
WATCHLIST_AFTER = "15:17"

# Morning re-check of the PREVIOUS session's stock-credit calls (engine/signal_recheck.py).
# 09:30, not 09:16: the first 15 minutes are the noisiest part of the day and the re-check's
# OTM gate reads live spot, so an opening spike would flip its verdict spuriously. By ~09:22
# option bid-ask is already back to 0.8-1.7% (measured 5-Aug on the open v1 legs) — as tight as
# mid-session and far better than the 2-4% at the 15:36 close. Read-only: it only notifies.
SIGNAL_RECHECK_AT = "09:30"
SIGNAL_RECHECK_ENABLED = True

# ── SESSION OBSERVER (engine/session_observer.py) — read-only recorder, no trading effect ──
# Records the option book through 15:15-15:40 every trading day, plus a 14:45 control. It exists
# because the 15:36 retiming was argued on a "2-4% spreads" figure that had NO artifact in the repo,
# and because nothing has ever verified that the scanner's daily bar carries TODAY's close by 15:36.
# Structural reason to expect a thin book after 15:15: the underlying stops trading continuously
# (auction to 15:35), so a market maker cannot delta-hedge and will quote wider or step away.
SESSION_OBSERVER_ENABLED  = True
SESSION_OBS_BASELINE      = "14:45"   # control sample: continuous session, underlying hedgeable
SESSION_OBS_FROM          = "15:15"   # continuous trading in F&O stocks ends here
SESSION_OBS_TO            = "15:40"   # derivatives close
SESSION_OBS_INTERVAL_SEC  = 60
SESSION_OBS_MAX_NAMES     = 25        # caps API load; watchlist is usually well under this

# 3-FAMILY 5-MIN SCAN (the BUY-side scorer). Disabled 2026-07-07 (user-approved): it fed only
# the hidden 3-Family paper book and caused options-flow 429 storms. The market snapshot/header
# (_market) and the 15:10 credit scans + 9:16 0DTE scans are INDEPENDENT and unaffected.
# Set True to resume the 3-Family paper forward-test.
SCAN_3FAMILY_ENABLED = False

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

# === SWING CREDIT SPREAD STRATEGY (multi-day · theta · FADE the breakout) ===
# A THIRD, separate parallel forward-test — distinct from the intraday stock & index
# option BUYING strategies. It SELLS a defined-risk credit spread AGAINST a daily
# Donchian breakout on the index (index breakouts mean-revert), mid-tenor, held to
# expiry — harvesting theta on the reversion. Shown in its own SWING CREDIT SPREADS
# section on PM DECISIONS, BETWEEN the stock and index sections.
#
# Validated on ~20 months of REAL expired-option data (engine/expired_options.py):
#   ALL +4.0% net/trade on capital-at-risk (real costs), PF 1.83, 67% win.
#   Replicated across two independent entry signals (Donchian-10 & -20), BOTH indices
#   positive (NIFTY +4.0% / BANKNIFTY +3.9%), survives 2x slippage (+3.0%), and the
#   held-out bootstrap 5th-percentile is +2.3% (robust, not outlier-driven).
# STILL A FORWARD-TEST: thin sample (~63 trades / ~21 holdout) and backtest fills are
# not live fills. It runs here to forward-test, NOT because it is proven profitable.
# Signals only — the user places the spread manually in Upstox; the system never trades.
# See studies/STOCK_OPTIONS_NO_EDGE.md (Part 6) for the full validation record.
SWING_CREDIT_ENABLED   = False  # REMOVED 2026-07-24: failed OOS (net -1.4%w, positive only 2019+2024). See STOCK_OPTIONS_NO_EDGE.md Parts 10-11.
# Lineup set by a robustness test (5 breakout defs × 5 indices, real costs): the FADE edge holds
# across ALL breakout definitions (D10/15/20/30/prior-week — genuine reversion, not a D10 fit),
# but NOT across all indices. NIFTY (PF 1.95) + FINNIFTY (PF 1.44) are the clean edges; BANKNIFTY
# tested NEGATIVE (−6.7%, 40 trades — its earlier +13% was 14-trade luck) and is DROPPED;
# MIDCPNIFTY (+2.4%, PF 1.05) is marginal with thin liquidity and is NOT deployed.
SWING_INDICES          = ["NIFTY", "FINNIFTY"]
SWING_DONCHIAN         = 10       # daily breakout lookback (edge robust across 10/15/20/30 + prior-week)
SWING_MIN_DTE          = 10       # MID tenor: nearest expiry >= 10 days out (the sweet spot)
SWING_SHORT_OFFSET     = 1        # short strike 1 step OTM from ATM
SWING_WIDTH            = 3        # long strike 3 steps further OTM (defined risk)
SWING_STOP_MULT        = 2.0     # stop if cost-to-close >= 2x the credit collected
# ── DIRECTIONAL + FLUSH gates — TESTED AND REVERTED (see STUDIES Part 11) ──
# On bhavcopy 2019→Sep24 these looked great: PE-only (fade DOWN-breaks) + flush ≥0.5% gave +15.1% net,
# 78% win, positive all 6 years, boot p5 +4.1%. BUT the out-of-sample test on REAL Upstox premiums
# Oct24→date FLIPPED the sign: there CE (fade UP-breaks) won +7.8% and PE LOST −8.7%; the deployed
# gate came in −2.8% (FINNIFTY −17.7%). The direction asymmetry was a 2019–24 BULL-REGIME artifact, not
# a structural drift edge. Reverted to neutral (fade both directions, no flush gate) — the index fade
# stays regime-dependent / unproven, run as a small forward-test only. Flip these back ONLY with a
# fresh cross-regime backtest that holds. Defaults below = original ungated behavior.
SWING_FADE_DOWN_ONLY   = False   # False = fade BOTH breakout directions (original). True = down-only.
SWING_MIN_BREAKOUT_PCT = 0.0     # 0 = no flush gate (original). >0 requires close that % beyond band.
SWING_TAKE_PROFIT      = 0.0     # 0 = HOLD TO EXPIRY (the validated backtest). Set 0.50–0.75 to
                                 # auto-BOOK a win once you've captured that fraction of max profit
                                 # (closes when cost-to-close <= credit×(1−TAKE_PROFIT)). De-risks
                                 # winners (locks gains, dodges expiry gamma) for a little less edge.
SWING_REENTRY_GAP_DAYS = 3        # min days between entries on the same index
SWING_SCAN_AFTER     = "15:36"  # scan once/day after this (a daily breakout needs ~the close)
SWING_RESOLVE_INTERVAL = 900      # mark-to-market open positions every 15 min (overnight carry)
# Lots per spread (paper sizing for the forward-test P&L). KEEP AT 1 to forward-test — the edge is
# +12%/trade but HIGH variance (a loss = ~full margin) on a thin sample; a 3-loss streak at many
# lots can exceed the account. Prudent ceiling ≈ 5 even after live confirmation. Per-index override.
SWING_LOTS             = {"NIFTY": 1, "FINNIFTY": 1}

# === MONTHLY FUTURES PULLBACK (the 5th — REV1-v2, signals-only paper forward-test) ===
# The one OOS survivor of the 2026-07 monthly-futures study (studies/monthly_fut/): at cycle
# start (first trading day after the prior monthly expiry), NIFTY>200DMA, buy the front-month
# futures of the 5 highest-vol names among the 8 worst 1-month losers still above their own
# 200DMA. Exits on daily closes. 75.7% win OOS, ~3.9%/mo on margin, worst month ~-20%.
# NEEDS ~Rs 15L capital at 5x Rs 10L notionals — paper-only until the user funds it.
MONTHLY_FUT_ENABLED    = True
MONTHLY_FUT_POOL       = 8       # worst-N 1-month losers above their 200DMA (candidate pool)
MONTHLY_FUT_TOPN       = 5       # of the pool, trade the N highest 20d-vol names
MONTHLY_FUT_TP         = 0.02    # take-profit +2% on close ...
MONTHLY_FUT_TP_LATE    = 0.01    # ... decaying to +1% after MONTHLY_FUT_DECAY_DAY sessions
MONTHLY_FUT_DECAY_DAY  = 12
MONTHLY_FUT_SL         = 0.05    # stop -5% on close (gaps can exceed it — avg real stop ≈ -6.3%)
MONTHLY_FUT_MIN_DTE    = 20      # only enter near cycle start (late/mid-cycle entries tested weak)
MONTHLY_FUT_EARNINGS_SKIP = True # live-only rule: skip names with results before expiry
MONTHLY_FUT_SCAN_AFTER     = "15:36" # entry decision needs ~the close
MONTHLY_FUT_RESOLVE_INTERVAL = 900

# === MONTHLY LONG-CALL PULLBACK (the 6th — SAME signal as the futures book, expressed as a
# bought ATM CALL instead of the future). OOS-validated: 5-pick simple config = 67% win,
# +6-7%/mo on premium OOS Oct'24→Jul'26. HIGH VARIANCE: -51% crash months are real (a bought
# call can lose ~100% of premium in a selloff). 8-pick + gates FAILED OOS (curve-fit) — kept at
# 5-pick, no extra gates. See studies/monthly_fut/MAX_TRADES_OPTIONS.md. Signals-only paper.
# SHELVED 2026-07-13 as UNRELIABLE: the 12-mo ledger showed +Rs63.8k/65% win was carried almost
# entirely by ONE trade (POLYCAB +Rs47k from a real +8.2% one-day GAP — the "+2% TP" rides
# gap-throughs, it doesn't cap wins); ex-POLYCAB the year was +Rs16.5k ≈ noise. Profit is
# luck/gap-dependent, not a steady edge. Code kept but dormant. See MAX_TRADES_OPTIONS.md.
MONTHLY_CALL_ENABLED   = False
MONTHLY_CALL_LOTS      = 1        # lots of the ATM call per pick (paper sizing)
# reuses MONTHLY_FUT_POOL/TOPN/TP/TP_LATE/DECAY_DAY/SL/MIN_DTE/EARNINGS_SKIP (identical signal)
MONTHLY_CALL_RESOLVE_INTERVAL = 900

# === STOCK CREDIT SPREAD STRATEGY (the 4th — same fade, on the full stock universe) ===
# The high-FREQUENCY sibling of the index swing: fade a daily Donchian-10 breakout on single
# stocks by SELLING a credit spread, but ONLY when richly paid relative to risk. A breakout
# spikes IV -> rich premium; fading sells the inflated premium AND rides the reversion + IV crush.
#
# Backtested on the FULL ~100-stock universe, ~19 months, REAL expired-option premiums:
#   credit/width>=0.40 + short premium>=Rs50: 307 trades (16/mo), 65% win, +16% net (5% slip
#   floor) / +25% (3%), holdout bootstrap p5 +6.8%, 76/100 stocks net-positive, survives 7%/leg
#   slippage. The credit/width gate is the edge — generic stock credit spreads LOSE (Part 4).
# STILL A FORWARD-TEST and almost certainly OPTIMISTIC: a ~20%/mo backtest return will shrink
# live — the real risk is fills/liquidity on mid-cap 4-leg spreads + gap risk on ~16 concurrent
# shorts. Hence the live LIQUIDITY GATE below and KEEP LOTS AT 1. See STOCK_OPTIONS_NO_EDGE Part 8.
STOCK_CREDIT_ENABLED      = True
STOCK_CREDIT_DONCHIAN     = 10
STOCK_CREDIT_MIN_DTE      = 10      # nearest monthly expiry >= 10 days out (stocks are monthly-only)
STOCK_CREDIT_SHORT_OFFSET = 1       # short 1 strike OTM
STOCK_CREDIT_WIDTH        = 3       # long 3 strikes further OTM (defined risk)
STOCK_CREDIT_MIN_CW       = 0.40    # THE EDGE: only trade when credit >= 40% of the strike width
STOCK_CREDIT_MIN_PREM     = 50.0    # short-leg premium >= Rs50 (avoid cheap/untradeable options)
STOCK_CREDIT_STOP_MULT    = 99.0    # NO stop (unreachable) — the bought wing caps risk at width-credit.
                                    # Sweep 2026-07-30 (V1_WINRATE_SWEEP.md): the 2x stop realized losses
                                    # that recover; removing it raised win AND net in IS and OOS.
STOCK_CREDIT_TAKE_PROFIT  = 0.40    # BOOK the win at 40% of credit (was 0.75). 85.0% IS / 86.0% OOS,
                                    # net +18.2/+17.6%w vs +10.3/+15.1 deployed — user-approved 2026-07-30.
                                    # tail (index stays at hold-to-expiry). 0 = hold to expiry.
STOCK_CREDIT_REENTRY_GAP_DAYS = 3   # min days between entries on the same stock
STOCK_CREDIT_MAX_SPREAD_PCT = 6.0   # live liquidity gate: short-leg bid-ask <= 6% (else skip)
STOCK_CREDIT_MIN_OI       = 100     # live liquidity gate: short-leg OI >= 100
# MAX EXPOSURE per spread: skip any trade whose width x lot exceeds this. 0 = NO CAP.
# HISTORY: hardcoded 40,000 -> 60,000 -> 0 (NO CAP), all on 2026-07-31, user's call.
# What no-cap admits TODAY: the largest width x lot in the 113-name universe at v2 geometry is
# HEROMOTOCO Rs90,000 (max loss ~Rs45k at c/w 0.5); median Rs30,000. A 60k cap already allowed
# 87 of 92 priced names, so removing it entirely adds only ~5 names — but it also removes the
# ceiling for any FUTURE high-priced listing, which is the real open risk here.
# MEASURED OOS Oct'24->Jul'26, v2 core at 1 lot: 40k -> 26 trades/Rs22.0k mo · 60k -> 27/Rs28.6k
# · no cap -> 43 trades at Rs47,824 avg. DO NOT TRUST that last mo-figure (~Rs278k/mo): it implies
# >100% monthly on deployed margin off a 43-trade sample and is a small-n artifact.
# THE REAL TRADE-OFF: big-exposure trades won 95.3% of the time in this window, which is exactly the
# whale profile the cap was written for — they nearly always win, and the one that does not cost
# -Rs84.7k (worst MONTH -Rs2.28L) on the longer window that produced the original 40k limit.
# On ~Rs5L capital a single -Rs85k trade is ~17% of the account. Keep lots at 1.
STOCK_CREDIT_MAX_EXPOSURE = 0      # 0 = NO CAP (user, 2026-07-31)
STOCK_CREDIT_MAX_NEW_PER_DAY = 5    # cap new entries/day (breakouts cluster -> avoid 1-day pile-on)
STOCK_CREDIT_MAX_OPEN     = 20      # cap total concurrent positions (margin + correlated-gap risk)
STOCK_CREDIT_LOTS         = 1       # paper sizing — KEEP AT 1 to forward-test
STOCK_CREDIT_SCAN_AFTER     = "15:36" # once/day after this (a daily breakout needs ~the close)
STOCK_CREDIT_RESOLVE_INTERVAL = 900 # mark-to-market every 15 min (overnight carry)

# ── STOCK CREDIT v0 (0.35-0.40 c/w) — forward paper-test, user-approved 2026-07-31 ──
# The v2 gate takes c/w >= 0.40. This runs the SAME geometry (short 2-OTM, width 4) on the band
# just below it, with the exits that half wants: TP-40 and NO stop.
#
# EVIDENCE IS DELIBERATELY THIN — read studies/LOWCW_BAND_RESCUE.md section 7 before trusting it:
#   IS  2019->Sep'24 : 77.4% win, +1.9% ROM, positive 4 of 6 years  (n=310)
#   OOS Oct'24->Jul'26: 90.7% win, +19.4% ROM, positive 3 of 3 years (n=43, 38 names)
# The in-sample leg is weak. The OOS leg is not: with the live Rs40k exposure cap applied so the
# numbers match what the engine can actually take, v0 does **Rs2,408 net/lot per trade at ~5.5
# signals/mo (~Rs13,300/mo scaled to 113 names)** vs the v2 core's Rs6,267 at 3.5/mo (~Rs22,000).
# Per rupee of margin v2 is still ~2.2x better (+41.2% vs +18.7%), but v2 is signal-starved -- the
# Rs40k cap blocks 17 of its 43 OOS trades and only 2 of v0's -- so v0 ADDS roughly +61% on top.
# (An earlier note here said "+9% net for +99% capital"; that compared the books in POINTS, not
# rupees, and ignored the cap. v0 trades big-lot names, so it was wrong.) KEEP LOTS AT 1.
STOCK_CREDIT_V0_ENABLED   = True
STOCK_CREDIT_V0_MIN_CW    = 0.35    # floor
STOCK_CREDIT_V0_MAX_CW    = 0.40    # ceiling (EXCLUSIVE) — at/above this v2 owns the trade
STOCK_CREDIT_V0_TAKE_PROFIT = 0.40  # book at 40% of credit (the exit this band wants)
STOCK_CREDIT_V0_STOP_MULT = 99.0    # NO stop — the bought wing caps risk at width-credit
STOCK_CREDIT_V0_MAX_NEW_PER_DAY = 3 # tighter than v2's 5 — this is the unproven book
STOCK_CREDIT_V0_MAX_OPEN  = 10      # tighter than v2's 20, caps the margin it can tie up
STOCK_CREDIT_V0_LOTS      = 1       # KEEP AT 1

# === 0DTE INTRADAY (the 5th strategy, paper forward-test) ===
# NIFTY expiry-day CALL credit spread: at the open, SELL the CE ~0.5% OTM of spot, BUY the CE
# 200 pts further out, hold to same-day settlement. NO intraday stop (backtested that way).
# Validated on REAL premiums: bhavcopy 2019->Sep'24 (282 expiry days) + Upstox OOS Oct'24->Jun'26
# (91): combined 373 trades, 85.0% win, +3.20% of margin/trade, positive EVERY year.
# See studies/INTRADAY_85PCT_0DTE_CE_SPREAD.md. Fires only on a weekly-expiry day (~4-5/month).
ZERO_DTE_ENABLED   = True
ZERO_DTE_INDEX     = "NIFTY"
ZERO_DTE_OTM_PCT   = 0.005   # short CE at the strike nearest spot*(1+0.5%)
ZERO_DTE_WIDTH_PTS = 200     # long wing ~200 pts further out (defined risk)
ZERO_DTE_LOTS      = 1       # paper sizing — KEEP AT 1 to forward-test
ZERO_DTE_RV5_MAX   = 0.9     # CALM-REGIME FILTER: skip the week when NIFTY 5-day realized vol
                             # (std of last 5 daily log-returns, %) >= this. Lifts 2019-26 to
                             # 87.8% win / +4.0%m (2025: +Rs1.7k -> +Rs23.2k at 1 lot); cost:
                             # 2019 ~flat (-Rs1.7k). Robust across thresholds 0.7-1.2 AND on the
                             # 0.75%-OTM sibling config. 0 = disabled. See study.
ZERO_DTE_MIN_CREDIT_PCT = 0.02  # THIN-CREDIT GATE (user-caught 2026-07-07): skip when the
                             # spread credit < 0.02% of spot (~Rs5 pts at 24.5k). RECALIBRATED
                             # trades: credit below this = -0.4%m dead weight (100 calm-week
                             # trades); above = +6.75%m, 87% win, +ve 2020-24. Same principle as
                             # stock fade v2's credit/width gate. 0 = disabled.
ZERO_DTE_STOP_MULT = 0.0     # OPTIONAL short-leg stop: buy back when short premium >= mult x
                             # entry. REAL 1-min backtest (91 expiries): with the rv5 filter ON,
                             # no-stop wins (90.4%/+5.85%m/worst -11.7k); x3.0 halves the worst
                             # trade (-6.5k) but costs ~Rs14k total and win drops to 82%. Tight
                             # stops (<=x2) whipsaw badly. 0 = disabled (recommended with filter).
ZERO_DTE_FLIP_RET5 = 1.0     # FLIP rule (user-approved 2026-07-07): if NIFTY 5-day return >=
                             # this %, SELL the PE spread (fade downside, ride momentum) instead
                             # of the CE. Since-inception 2019-26 (372 expiries, real premiums,
                             # W=200 both sides): FLIP 87.1% win / +Rs192k vs CE-always 84.7% /
                             # +Rs117k; OOS-era 91-94% win. Flip's weak years: 2019 (-Rs3.9k),
                             # 2021 (77% win). 0 = disabled (CE always). studies/FLIP_SIDE_CREDIT_FADE.md
# FLIP-CONDOR HYBRID (user-approved paper deploy 2026-07-31): at the same 9:16 scan, ALSO sell
# the OPPOSITE side (short ~1.0% OTM, same 200-pt wing) ONLY when that side's own credit/width
# >= the floor. Margin is shared (both wings W=200 -> condor margin = W - total credit; one
# side's wing covers both), so the add lifts return on the SAME capital and the worst case is
# identical to FLIP's. Evidence (studies/PATH_TO_1L.md iter-2, ndte24_flipcondor.py IS /
# ndte26_flipcondor_oos.py OOS, cells frozen before the OOS run): d=1.00 cw>=0.08 cell —
# IS 2019->Sep'24: 86.5% win / +Rs148,045 vs FLIP 85.8% / +Rs103,818; OOS Oct'24->Jul'26:
# 91.5% win / +Rs82,225 vs FLIP 91.6% / +Rs64,323; worst trade identical (-Rs12,975 IS /
# -Rs11,629 OOS — FLIP's own worst day). Fires on only ~12-14% of expiries (39/282 IS, 11/94
# OOS) — rich credit IS the gate, the stock-book lesson again. Honest prize: ~+Rs800-1,000/mo
# at 1 lot. Caveats: floor swept (robust neighborhood, but selection risk real); OOS add-count
# thin (11); bhav OPEN fills optimistic for 4 legs — hence paper forward-test, NOT proven.
ZERO_DTE_HYBRID_ENABLED = True   # False = plain FLIP (one side only)
ZERO_DTE_HYBRID_OTM     = 0.0100 # added (opposite) side: short strike nearest spot*(1 -/+ 1.0%)
ZERO_DTE_HYBRID_MIN_CW  = 0.08   # sell the added side only if ITS OWN credit/width >= this
# === 0DTE STRUCTURAL EXCLUSIONS (2026-07-19) ===
# Both added on STRUCTURAL grounds after the event-avoidance series (studies/ZERO_DTE_*.md).
# Neither is a statistical edge; both are risk exclusions. Set to [] / 0 to disable.
#
# ELECTION BLACKOUT — national election counting days + the exit-poll reaction session.
# Rationale: these are scheduled INSIDE-window binaries. IV widens, but the outcome distribution is
# bimodal, not fat-normal, and short premium is structurally the wrong trade against a binary.
# In 448 backtested expiries 2019→Jul'26 this NEVER ONCE triggered (2024-06-04, NIFTY −5.9%, was
# dodged by calendar luck, not design) — so its measured historical cost is exactly Rs0. It is
# zero-premium insurance against the book's known ruin mode, NOT a tested edge. Maintain by hand;
# national counting days + exit-poll sessions only. If this list starts growing, re-review it.
#
# *** THIS IS A HAND-MAINTAINED LIST. THERE IS NO NEWS ENGINE BEHIND IT. ***
# Nothing in this repo fetches election or policy dates at runtime. engine/events.py scrapes NSE
# CORPORATE announcements but feeds STOCK scoring only — it never touches the index 0DTE books.
# studies/ndte/event_calendar.json is research data and is NEVER read by the engine.
# So this filter can only ever fire on a date a human typed in below.
#
# MAINTENANCE: national election counting days are announced by the ECI weeks ahead. When one is
# announced, add BOTH the counting day AND the first session after exit polls. The engine logs a
# WARNING every scan while this list has no future dates, so a dead list is visible rather than
# silent. Next Lok Sabha is due 2029; dates are not yet published, which is why there is currently
# nothing to add and the filter cannot fire.
ZERO_DTE_ELECTION_BLACKOUT = [
    "2019-05-20", "2019-05-23",   # exit-poll session + Lok Sabha counting
    "2024-06-03", "2024-06-04",   # exit-poll session + Lok Sabha counting (NIFTY −5.9%)
]
# MINIMUM CREDIT/WIDTH — applies to the SENSEX + BANKNIFTY books only (dte_multi).
# NIFTY already embodies this principle via ZERO_DTE_MIN_CREDIT_PCT above and is left UNCHANGED.
# Rationale: pooled 448 expiries show a monotone c/W gradient where win rate is an inverse mirage —
# the CHEAPEST bucket (c/W<0.04) had the HIGHEST win rate (91.7%) and still LOST money (−0.49% of
# margin, −Rs1,878 over 60 trades). Selling near-zero credit against a full settlement tail is
# negative-EV by arithmetic, not by regime. 0.04 is deliberately the STRUCTURAL boundary of that
# dead bucket, NOT the P&L-maximising cutoff — the sweep's best numbers sat at 0.06-0.12 and were
# explicitly REJECTED as in-sample argmaxes on small skip-counts. Purpose is to stop carrying
# max-loss risk for zero compensation, not to harvest the Rs1,878.
ZERO_DTE_MULTI_MIN_CW = 0.04

# BANKNIFTY 0DTE — REJECTED and DISABLED 2026-07-19 (user decision, after an adversarial audit).
# 84 monthly expiries 2019→Jun'26, 1 lot, net of costs. It is not that the book "loses" — the MEDIAN
# trade is +14.1% of margin. It is that the edge is indistinguishable from zero and the tail swamps it:
#   * avg +0.55% of margin, t = +0.10, 95% CI [-9.98%, +11.09%]  -> NOT distinguishable from zero
#   * bootstrap p(mean <= 0) = 0.33
#   * the ENTIRE profit is 3 trades: drop the 3 best and the book is -Rs8 over 7.5 years
#   * +Rs141/month at 1 lot, while the worst single day was -Rs14,298 = ~102 months of profit
#   * the "91% win / ~Rs1,500 per month" figure it was carried on was never supported
# The monthly-expiry-should-win-more hypothesis was tested and rejected (ndte19): within Era A,
# MONTHLY 76.1% win / -1.55%m vs WEEKLY 80.4% / +8.51%m, z = -0.75.
# Audit (ndte20) found no bug that flips the sign; the one bias it did find (no CONTRACTS floor on the
# long wing) would FLATTER the book, so rejecting is the conservative side of that error.
# Set back to True only with fresh evidence — see studies/BANKNIFTY_0DTE_REJECTION.md.
DTE_MULTI_BANKNIFTY_ENABLED = False

ZERO_DTE_SCAN_AFTER   = "09:16"  # enter right after the open (matches the backtest's open fill)
ZERO_DTE_ENTRY_CUTOFF = "09:45"  # too far from the open after this — skip the day
# Settlement uses the ONE knob (SETTLE_AFTER = 15:40). Index option expiry settles against the
# INDEX CLOSING VALUE, which derives from constituent closes struck in the auction by 15:35 — that
# value does not change after 15:35, so reading it at 15:40 gets the identical number with no race
# against the auction match. Waiting costs nothing and removes a failure mode.
ZERO_DTE_SETTLE_AFTER = SETTLE_AFTER
ZERO_DTE_RESOLVE_INTERVAL = 120  # intraday mark-to-market cadence (s)
# EARLY PROFIT CLOSE (user-approved 2026-08-04) — applies to ALL THREE intraday expiries:
# NIFTY (Tue), SENSEX (Thu), BANKNIFTY (monthly, book currently disabled but wired).
# Close the spread once it has captured this fraction of its credit, instead of holding to expiry.
# A credit spread only pays FULL credit if both legs expire worthless; intraday it trades at
# 0.05-0.50, never exactly 0 — so this is a threshold, not an equality test.
#   close when  cost <= credit * (1 - ZERO_DTE_EARLY_CLOSE_FRAC)
# WHY 0.95 and not lower: at 95% the outcome is near-identical to holding, so it barely perturbs the
# validated hold-to-expiry distribution, while removing the tail where a late reversal turns a winner
# into a full-width loser. Costs ~5% of credit on nearly every winner (~Rs45/trade on SENSEX).
# ⚠️ CANNOT BE BACKTESTED. Both 0DTE books are validated AS HOLD-TO-EXPIRY (NIFTY 88.3%, SENSEX
# 89.0%) and intraday option premium history does not exist beyond ~1 month (DATA_AVAILABILITY_LIMITS)
# — unlike v1's TP-40 which was tested on 242 real trades, this ships UNMEASURED. Set to 0 to disable
# and fall back to pure hold-to-expiry for a forward-test comparison.
ZERO_DTE_EARLY_CLOSE_FRAC = 0.95

# === ORB+VWAP INDEX STRATEGY (parallel paper forward-test) ===
# Runs ALONGSIDE the 3-Family system on NIFTY/BANKNIFTY and is reported in its own
# section on PM DECISIONS. Signal: 15-min ORB break on the index FUTURES + hold VWAP
# + 30-min trend aligned + entry before the cutoff. Buys ATM, exits +/-20% on premium.
# NOTE: Apr-Jun 2026 backtests show this is ~breakeven (NIFTY -0.5%, BANKNIFTY +0.3%);
# it runs LIVE here to forward-test it, NOT because it is proven profitable.
ORB_VWAP_ENABLED      = False  # RETIRED 2026-07: thin/inconsistent on real 2019->date 5-min
                               # (+0.04%/tr, -ve ~2/8 yrs); PM slot replaced by STOCK CREDIT v2 (TP-50)
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
