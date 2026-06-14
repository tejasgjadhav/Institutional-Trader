"""Every tunable the engine reads.

DISCLAIMER. This code is the companion to the book The Algo Trading Bible. It is published for
study and nothing else. It is not investment advice, not a recommendation and not a signal
service. If you run it, or trade anything on the back of it, you do so entirely at your own
risk and on your own decision. Tejas Jadhav accepts no responsibility and no liability for any
trade you place or any loss you suffer. Speak to a licensed advisor before you trade.

WHAT IS AND IS NOT IN THIS FILE.

The settings above the strategy line are plumbing. They say where the data comes from, when the
market opens, where files are written and how big a paper position may be. Change them freely.

Below the strategy line there is one book, and it is a worked example built on VWAP. It is
written out in full, with every number visible, in engine/example_vwap.py. It runs, it screens
the index, it buys a paper option and it books the result. Use it to learn the machine.

It is a teaching example and nothing more. The author does not trade it. It has not been
backtested, it has not been validated and it is not recommended. Every number in its block was
chosen to be readable, not because a test said so. If you run it, or act on anything it prints,
that is your decision and your risk.

The strategies the author actually trades are not in this repository, in any form. They are not
withheld behind a blank, they are not described in a comment and they are not hinted at in a
file name. They are simply not here. The book explains how he did the research. Do your own,
and write your own book into this file beside the example.
"""
import pytz
import os
from dotenv import load_dotenv

load_dotenv()

# Timezone
IST = pytz.timezone("Asia/Kolkata")

# === EXECUTION ===
EXECUTION_MODE = "PAPER"   # signals only. There is no live order path in this edition.
PAPER_TRADING_PHASE = True

# === UNIVERSE — every NSE F&O stock, not a selection. ===
# The full list of stocks with NSE futures and options as of 31 Oct 2026 (218 names), taken from
# the public Upstox instruments file. NSE revises it from time to time.
# The author trades a smaller list chosen by backtest. That list is not published. Choose and
# test your own subset with your own backtests, and trim this list to it.
UNIVERSE = [
    "360ONE.NS", "ABB.NS", "ABCAPITAL.NS", "ADANIENSOL.NS", "ADANIENT.NS", "ADANIGREEN.NS", "ADANIPORTS.NS", "ADANIPOWER.NS",
    "ALKEM.NS", "AMBER.NS", "AMBUJACEM.NS", "ANANDRATHI.NS", "ANGELONE.NS", "APLAPOLLO.NS", "APOLLOHOSP.NS", "ASHOKLEY.NS",
    "ASIANPAINT.NS", "ASTRAL.NS", "ATHERENERG.NS", "AUBANK.NS", "AUROPHARMA.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJAJFINSV.NS",
    "BAJFINANCE.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BANKINDIA.NS", "BDL.NS", "BEL.NS", "BHARATFORG.NS", "BHARTIARTL.NS",
    "BHEL.NS", "BIOCON.NS", "BLUESTARCO.NS", "BOSCHLTD.NS", "BPCL.NS", "BRITANNIA.NS", "BSE.NS", "CAMS.NS",
    "CANBK.NS", "CDSL.NS", "CGPOWER.NS", "CHOLAFIN.NS", "CIPLA.NS", "COALINDIA.NS", "COCHINSHIP.NS", "COFORGE.NS",
    "COLPAL.NS", "CONCOR.NS", "COROMANDEL.NS", "CROMPTON.NS", "CUB.NS", "CUMMINSIND.NS", "DABUR.NS", "DATAPATTNS.NS",
    "DELHIVERY.NS", "DIVISLAB.NS", "DIXON.NS", "DLF.NS", "DMART.NS", "DRREDDY.NS", "EICHERMOT.NS", "ENRIN.NS",
    "ETERNAL.NS", "FEDERALBNK.NS", "FORCEMOT.NS", "FORTIS.NS", "GAIL.NS", "GLENMARK.NS", "GMRAIRPORT.NS", "GODFRYPHLP.NS",
    "GODREJCP.NS", "GODREJPROP.NS", "GRASIM.NS", "GVT&D.NS", "HAL.NS", "HAVELLS.NS", "HCLTECH.NS", "HDFCAMC.NS",
    "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDPETRO.NS", "HINDUNILVR.NS", "HINDZINC.NS", "HYUNDAI.NS",
    "ICICIBANK.NS", "ICICIGI.NS", "ICICILIFE.NS", "IDEA.NS", "IDFCFIRSTB.NS", "IEX.NS", "INDHOTEL.NS", "INDIANB.NS",
    "INDIGO.NS", "INDUSINDBK.NS", "INDUSTOWER.NS", "INFY.NS", "INOXWIND.NS", "IOC.NS", "IREDA.NS", "IRFC.NS",
    "ITC.NS", "JINDALSTEL.NS", "JIOFIN.NS", "JSWENERGY.NS", "JSWSTEEL.NS", "JUBLFOOD.NS", "KALYANKJIL.NS", "KARURVYSYA.NS",
    "KAYNES.NS", "KEI.NS", "KFINTECH.NS", "KOTAKBANK.NS", "KPITTECH.NS", "LAURUSLABS.NS", "LICHSGFIN.NS", "LICI.NS",
    "LODHA.NS", "LT.NS", "LTF.NS", "LTM.NS", "LUPIN.NS", "M&M.NS", "MAHABANK.NS", "MANAPPURAM.NS",
    "MANKIND.NS", "MARICO.NS", "MARUTI.NS", "MAXHEALTH.NS", "MAZDOCK.NS", "MCX.NS", "MFSL.NS", "MOTHERSON.NS",
    "MOTILALOFS.NS", "MPHASIS.NS", "MUTHOOTFIN.NS", "NAM-INDIA.NS", "NATIONALUM.NS", "NAUKRI.NS", "NAVINFLUOR.NS", "NBCC.NS",
    "NESTLEIND.NS", "NHPC.NS", "NMDC.NS", "NTPC.NS", "NYKAA.NS", "OBEROIRLTY.NS", "OFSS.NS", "OIL.NS",
    "ONGC.NS", "PAGEIND.NS", "PATANJALI.NS", "PAYTM.NS", "PERSISTENT.NS", "PETRONET.NS", "PFC.NS", "PGEL.NS",
    "PHOENIXLTD.NS", "PIDILITIND.NS", "PIIND.NS", "PNB.NS", "PNBHOUSING.NS", "POLICYBZR.NS", "POLYCAB.NS", "POWERGRID.NS",
    "POWERINDIA.NS", "PREMIERENE.NS", "PRESTIGE.NS", "RADICO.NS", "RBLBANK.NS", "RECLTD.NS", "RELIANCE.NS", "RVNL.NS",
    "SAGILITY.NS", "SAIL.NS", "SBICARD.NS", "SBILIFE.NS", "SBIN.NS", "SHREECEM.NS", "SHRIRAMFIN.NS", "SIEMENS.NS",
    "SOLARINDS.NS", "SONACOMS.NS", "SRF.NS", "SUNPHARMA.NS", "SUPREMEIND.NS", "SUZLON.NS", "SWIGGY.NS", "SYRMA.NS",
    "TATACONSUM.NS", "TATAELXSI.NS", "TATAPOWER.NS", "TATASTEEL.NS", "TCS.NS", "TECHM.NS", "TIINDIA.NS", "TITAN.NS",
    "TMPV.NS", "TORNTPHARM.NS", "TRENT.NS", "TVSMOTOR.NS", "UJJIVANSFB.NS", "ULTRACEMCO.NS", "UNIONBANK.NS", "UNITDSPR.NS",
    "UNOMINDA.NS", "UPL.NS", "VBL.NS", "VEDL.NS", "VMM.NS", "VOLTAS.NS", "WAAREEENER.NS", "WIPRO.NS",
    "YESBANK.NS", "ZYDUSLIFE.NS",
]
# PRIORITY stocks — an optional UI flag for names you want highlighted. Blank on purpose.
PRIORITY_STOCKS = []

# Index underlyings available for option work.
SCAN_INDICES = ["NIFTY", "BANKNIFTY"]

# === DATA SOURCES ===
UPSTOX_ANALYTICS_TOKEN = os.getenv("UPSTOX_ANALYTICS_TOKEN")
USE_YAHOO_FALLBACK = True   # if Upstox fails, fall back to Yahoo (delayed)

# === TIMING (IST) ===
MARKET_OPEN  = "09:15"
MARKET_CLOSE = "15:30"

# === OPTION LIQUIDITY — housekeeping, not an edge ===
# These two keep the engine from pricing a contract nobody is quoting. They are not a strategy
# filter and they were not optimised.
MAX_OPTION_SPREAD_PCT = 4.0    # skip a quote if (ask - bid) / mid is wider than this
MIN_OPTION_OI         = 100    # skip a contract with less open interest than this

# === PAPER SIZING ===
CAPITAL = 100_000              # INR, notional, for the capital line on the dashboard only

# === PATHS ===
DATA_DIR = "data"
LOG_DIR  = "logs"
TRADE_LOG_PATH = f"{DATA_DIR}/trade_log.json"
SIGNALS_PATH   = f"{DATA_DIR}/signals.json"
APP_LOG_PATH   = f"{LOG_DIR}/app.log"

# =====================================================================================
# THE STRATEGY LINE. Everything below decides what to trade. All of it is an example.
# =====================================================================================

# ---------------------------------------------------------------------------
# BOOK 1 — the worked example. A VWAP pullback on a stock.
#
# READ THIS BEFORE YOU ENABLE IT. This book exists so you can watch the machine work
# end to end: a screen, a signal, an option order, a paper fill, a resolve and a row on
# the dashboard. It is a teaching example. The author does not trade it. It has not been
# backtested on real data, it has not been validated out of sample, and it is not
# recommended. Every number below was chosen to be readable, not because it was tested.
# Switch it on to learn the plumbing. Do not switch it on to make money. If you deploy it
# or act on what it prints, that is your decision and your risk alone.
# ---------------------------------------------------------------------------
EXAMPLE_VWAP_ENABLED   = True    # it runs. Read the warning above: you own the outcome.
EXAMPLE_VWAP_SYMBOL    = "RELIANCE.NS"   # a stock, not an index. VWAP needs volume, and a
                                         # spot index series has none. Pick a liquid name whose
                                         # options are quoted at a spread you would pay.
EXAMPLE_VWAP_BAR       = "5minute"
EXAMPLE_VWAP_STRETCH   = 0.30    # how far below VWAP the index must trade, in percent
EXAMPLE_VWAP_TURN_BARS = 1       # bars of recovery required before entry
EXAMPLE_VWAP_ENTRY_FROM = "09:45"
EXAMPLE_VWAP_ENTRY_TO   = "13:30"
EXAMPLE_VWAP_TARGET_PCT = 25.0   # take profit, percent of the option premium paid
EXAMPLE_VWAP_STOP_PCT   = 25.0   # stop loss, percent of the option premium paid
EXAMPLE_VWAP_EXIT_AT    = "15:15"
EXAMPLE_VWAP_LOTS       = 1
EXAMPLE_VWAP_MAX_PER_DAY = 1
EXAMPLE_VWAP_RESOLVE_INTERVAL = 120
