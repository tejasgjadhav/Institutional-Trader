"""
Agent — Main Orchestrator
Runs every 5 min during market hours. Scans all stocks, fires signals, tracks outcomes.
"""
import logging
import json
from datetime import datetime, time
from pathlib import Path

from engine.config import (
    IST, MARKET_OPEN, TRADING_START, NO_NEW_TRADES_AFTER, KILL_SWITCH_TIME,
    UNIVERSE, PAPER_TRADING_PHASE, APP_LOG_PATH, SIGNALS_PATH
)
from engine.data_fetcher import (
    fetch_intraday_5min, fetch_yahoo_historical, get_cached_vix, get_cached_nifty_pct
)
from engine.signals import compute_all_families, is_orb_confirmed
from engine.portfolio import TradeCalculator, format_trade_for_log
from engine.trade_log import TradeLog

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(APP_LOG_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Agent:
    """Main trading agent"""

    def __init__(self):
        self.trade_log = TradeLog()
        self.universe = UNIVERSE
        self.signals_fired = []

    def is_market_open(self) -> bool:
        """Check if market is open (Mon-Fri, 9:15-15:30 IST)"""
        now = datetime.now(IST)
        weekday = now.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
        if weekday >= 5:  # Weekend
            return False

        market_open = datetime.strptime(MARKET_OPEN, "%H:%M").time()
        market_close_time = datetime.strptime("15:30", "%H:%M").time()

        return market_open <= now.time() <= market_close_time

    def is_trading_window(self) -> bool:
        """Check if we're in the trading window (9:45-15:00 IST)"""
        now = datetime.now(IST)
        trading_start = datetime.strptime(TRADING_START, "%H:%M").time()
        no_new_trades = datetime.strptime(NO_NEW_TRADES_AFTER, "%H:%M").time()

        return trading_start <= now.time() <= no_new_trades

    def should_kill_switch(self) -> bool:
        """Check if it's time to force-close all positions (15:10 IST)"""
        now = datetime.now(IST)
        kill_time = datetime.strptime(KILL_SWITCH_TIME, "%H:%M").time()
        return now.time() >= kill_time

    def scan_stock(self, ticker: str) -> dict:
        """
        Scan one stock: get data, compute all families, check gates.
        Returns: {
            "ticker": str,
            "alpha_z": float,
            "direction": str,
            "passes_gate_1": bool,
            "orb_confirmed": bool,
            "trade_ready": bool,  # Both gates passed
            "signal_details": {...}
        }
        """
        try:
            # Fetch data
            df_5min = fetch_intraday_5min(ticker, days=1)
            df_daily = fetch_yahoo_historical(ticker, period="2y")

            if df_5min.empty or df_daily.empty:
                return {"ticker": ticker, "error": "Data unavailable"}

            # Market data
            vix = get_cached_vix()
            nifty_pct = get_cached_nifty_pct()

            # Compute signal
            signal = compute_all_families(
                ticker, df_5min, df_daily,
                vix=vix, nifty_pct=nifty_pct,
                news_sentiment=0.0, has_event=False  # TODO: fetch news/events
            )

            # Gate 1: alpha-z + breadth
            gate_1 = signal.get("passes_gate_1", False)

            # Gate 2: ORB confirmation
            orb_confirmed, orb_dir, vol_ratio = is_orb_confirmed(df_5min)
            gate_2 = orb_confirmed and (orb_dir == signal["direction"])

            # Both gates?
            trade_ready = gate_1 and gate_2

            return {
                "ticker": ticker,
                "alpha_z": signal["alpha_z"],
                "direction": signal["direction"],
                "breadth": signal["breadth"],
                "passes_gate_1": gate_1,
                "orb_confirmed": orb_confirmed,
                "vol_ratio": vol_ratio,
                "trade_ready": trade_ready,
                "signal_details": signal,
                "vix": vix,
                "nifty_pct": nifty_pct,
            }

        except Exception as e:
            logger.warning(f"Error scanning {ticker}: {e}")
            return {"ticker": ticker, "error": str(e)}

    def run_scan(self) -> list:
        """Scan all stocks, return trade-ready signals"""
        logger.info(f"\n{'='*60}\nSCAN START\n{'='*60}")

        now = datetime.now(IST)
        logger.info(f"Time: {now.strftime('%H:%M:%S')} IST")
        logger.info(f"Market open: {self.is_market_open()}")
        logger.info(f"In trading window: {self.is_trading_window()}")

        if not self.is_market_open():
            logger.info("Market closed, skipping scan")
            return []

        signals_fired = []

        for ticker in self.universe:
            result = self.scan_stock(ticker)

            if "error" in result:
                continue

            # Log ready-to-trade signals
            if result.get("trade_ready") and self.is_trading_window():
                logger.info(
                    f"TRADE READY: {ticker} | "
                    f"α-z={result['alpha_z']:.2f} | "
                    f"Dir={result['direction']} | "
                    f"Breadth={result['breadth']}/3 | "
                    f"ORB={result['vol_ratio']:.1f}×"
                )
                signals_fired.append(result)

        logger.info(f"Scan complete: {len(signals_fired)} signals ready\n")
        return signals_fired

    def execute_signals(self, signals: list):
        """
        Paper mode: log signals, don't execute.
        Manual placement: user places orders in Upstox app at shown levels.
        """
        for sig in signals:
            ticker = sig["ticker"]
            direction = sig["direction"]
            alpha_z = sig["alpha_z"]

            # Calculate position
            entry = sig["signal_details"]["trend"]["components"].get("microstructure", 0)
            if entry == 0 or entry == 1 or entry == -1:
                # Not a real price; would fetch live LTP here
                from engine.data_fetcher import get_cached_ltp
                entry = get_cached_ltp(ticker) or 100.0

            # Position sizing
            position = TradeCalculator.calculate_position(entry, alpha_z, None)
            if "error" in position:
                logger.warning(f"Position calc failed for {ticker}: {position['error']}")
                continue

            # Format for log
            trade_dict = {
                "ticker": ticker,
                "direction": direction,
                "alpha_z": alpha_z,
                "breadth": sig["breadth"],
                "entry": position["entry"],
                "stop": position["stop"],
                "target": position["target"],
                "qty": position["qty"],
                "reward_risk": position["reward_risk_ratio"],
                "instrument": position["instrument"],
                "vix": sig.get("vix"),
                "nifty_pct": sig.get("nifty_pct"),
            }

            # Add to paper log
            self.trade_log.add_signal(trade_dict)

            # Print to console
            logger.info(
                f"SIGNAL: {ticker} {direction} | "
                f"Entry={trade_dict['entry']} | "
                f"Stop={trade_dict['stop']} | "
                f"Target={trade_dict['target']} | "
                f"Qty={trade_dict['qty']} | "
                f"Instrument={trade_dict['instrument']}"
            )

            if PAPER_TRADING_PHASE:
                logger.info(f"PAPER MODE: Place order manually in Upstox app")

    def run_once(self):
        """Execute one scan cycle"""
        if not self.is_market_open():
            logger.info("Market closed")
            return

        signals = self.run_scan()
        if signals and self.is_trading_window():
            self.execute_signals(signals)

        # Print status
        self.trade_log.print_status()

    def run_continuous(self):
        """Run in loop (background daemon)"""
        logger.info("Starting continuous scan (every 5 min)")
        while True:
            try:
                self.run_once()
            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in scan loop: {e}", exc_info=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Run continuous loop")
    args = parser.parse_args()

    agent = Agent()

    if args.loop:
        agent.run_continuous()
    else:
        agent.run_once()
