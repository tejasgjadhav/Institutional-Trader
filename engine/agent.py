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
    UNIVERSE, PAPER_TRADING_PHASE, APP_LOG_PATH, SIGNALS_PATH, SCAN_INDICES
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
        # 3-Family system scans the STOCK universe only. NIFTY/BANKNIFTY are now
        # handled EXCLUSIVELY by the parallel ORB+VWAP index strategy (orb_vwap_live).
        self.universe = list(UNIVERSE)
        self.signals_fired = []
        # ORB+VWAP index strategy rows (runs in parallel, shown on PM DECISIONS)
        self.orbvwap_signals = []
        self._event_thread = None
        # Kick off an initial event scrape in the background at startup.
        self.maybe_refresh_events(force=True)

    def maybe_refresh_events(self, force: bool = False):
        """
        Refresh NSE event scores at ~9 AM and then hourly until 1 PM, in a
        background thread so it never blocks the 5-min signal scan.
        """
        import threading
        from engine import events
        now = datetime.now(IST)
        in_window = (9 * 60) <= (now.hour * 60 + now.minute) <= (13 * 60 + 5)  # 09:00-13:05
        # Poll ~every 20 min: NSE only shows the latest ~20 announcements, so frequent
        # polling + accumulation (see events.refresh_event_scores) catches large-cap
        # filings before they scroll out of the window.
        stale = events.cache_age_minutes() >= 20
        if not force and not (in_window and stale):
            return
        if self._event_thread and self._event_thread.is_alive():
            return  # a refresh is already running

        def _work():
            try:
                events.refresh_event_scores()
            except Exception as e:
                logger.warning(f"Event refresh failed: {e}")
        self._event_thread = threading.Thread(target=_work, daemon=True)
        self._event_thread.start()

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

            # EVENT family — real NSE announcement sentiment (scraped hourly)
            from engine.events import get_event_score
            news_sentiment, has_event = get_event_score(ticker)

            # FLOW family — real per-stock options flow (PCR + OI buildup) from the chain
            from engine.options_flow import fetch_options_flow
            flow_data = fetch_options_flow(ticker)

            # Compute signal
            signal = compute_all_families(
                ticker, df_5min, df_daily,
                vix=vix, nifty_pct=nifty_pct,
                news_sentiment=news_sentiment, has_event=has_event,
                flow_data=flow_data,
            )

            # Gate 1: alpha-z + breadth
            gate_1 = signal.get("passes_gate_1", False)

            # Gate 2: ORB confirmation
            orb_confirmed, orb_dir, vol_ratio = is_orb_confirmed(df_5min)
            gate_2 = orb_confirmed and (orb_dir == signal["direction"])

            # Gate 3: MARKET ALIGNMENT — don't fight the Nifty's intraday direction
            from engine.config import (MARKET_ALIGN_FILTER, ENTRY_EXTENSION_FILTER,
                                       MAX_ENTRY_EXTENSION_PCT)
            direction = signal["direction"]
            nifty_dir = 1 if (nifty_pct or 0) > 0 else (-1 if (nifty_pct or 0) < 0 else 0)
            aligned = ((direction == "LONG" and nifty_dir == 1) or
                       (direction == "SHORT" and nifty_dir == -1))

            # Gate 4: DON'T CHASE — skip if the stock already ran too far from the open
            # in the trade's direction (buying a stock that's already extended loses edge).
            day_open = float(df_5min["Open"].iloc[0]) if len(df_5min) else 0.0
            cur_px = float(df_5min["Close"].iloc[-1]) if len(df_5min) else 0.0
            ext_dir = 0.0
            if day_open:
                raw_ext = (cur_px - day_open) / day_open * 100
                ext_dir = raw_ext if direction == "LONG" else -raw_ext  # move in trade dir
            not_extended = (ext_dir <= MAX_ENTRY_EXTENSION_PCT)

            # All gates (each filter only enforced when its flag is on)
            trade_ready = (gate_1 and gate_2
                           and (aligned or not MARKET_ALIGN_FILTER)
                           and (not_extended or not ENTRY_EXTENSION_FILTER))

            return {
                "ticker": ticker,
                "alpha_z": signal["alpha_z"],
                "direction": signal["direction"],
                "breadth": signal["breadth"],
                "passes_gate_1": gate_1,
                "orb_confirmed": orb_confirmed,
                "gate_2": gate_2,
                "vol_ratio": vol_ratio,
                "aligned": aligned,
                "nifty_dir": nifty_dir,
                "entry_extension_pct": round(ext_dir, 2),
                "not_extended": not_extended,
                "trade_ready": trade_ready,
                "families_detail": signal.get("families_detail", {}),  # for ALPHA tab columns
                "current_price": signal.get("current_price"),
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

        # Refresh NSE event scores hourly (9 AM-1 PM), in the background
        self.maybe_refresh_events()

        # Kick off the ORB+VWAP INDEX strategy concurrently — it runs in PARALLEL
        # with the 3-Family stock scan and is reported in its own PM DECISIONS section.
        from concurrent.futures import ThreadPoolExecutor, as_completed
        ix_pool = ThreadPoolExecutor(max_workers=1)
        ix_future = None
        try:
            from engine.orb_vwap_live import scan_index_orbvwap
            ix_future = ix_pool.submit(scan_index_orbvwap)
        except Exception as e:
            logger.warning(f"ORB+VWAP submit failed: {e}")

        # Parallelize the per-stock scan — each scan_stock makes independent
        # network calls, so a thread pool turns ~40s sequential into a few seconds.
        results = []
        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = {pool.submit(self.scan_stock, t): t for t in self.universe}
            for fut in as_completed(futures):
                try:
                    results.append(fut.result())
                except Exception as e:
                    logger.warning(f"Scan failed for {futures[fut]}: {e}")

        # Collect the ORB+VWAP index result (ran alongside the stock scan)
        if ix_future is not None:
            try:
                self.orbvwap_signals = ix_future.result(timeout=30)
            except Exception as e:
                logger.warning(f"ORB+VWAP scan failed: {e}")
                self.orbvwap_signals = []
        ix_pool.shutdown(wait=False)

        # Log each ACTIVE ORB+VWAP index signal to the paper trade log (idempotent),
        # so it shows in the TRADE LOG and is resolved to WIN/LOSS like stock signals.
        for s in (self.orbvwap_signals or []):
            if not s.get("entry"):
                continue
            self.trade_log.log_signal_once({
                "ticker": s.get("index"), "direction": s.get("direction"),
                "instrument": s.get("kind"), "strategy": "ORB+VWAP",
                "option_key": s.get("option_key"),
                "entry": s.get("entry"), "entry_premium": s.get("entry"),
                "target": s.get("target"), "stop": s.get("stop"),
                "target_premium": s.get("target"), "stop_premium": s.get("stop"),
                "qty": s.get("lot"), "signal_time": s.get("fire_iso"),
            })

        # Keep ALL scored stocks (drop only hard errors) so the ALPHA tab shows the
        # full scan, WATCHLIST shows Gate-1 passers, and PM DECISIONS shows trade-ready.
        scored = [r for r in results if "error" not in r]
        # Sort by conviction (|alpha-z|) so the strongest sit on top of ALPHA.
        scored.sort(key=lambda r: abs(r.get("alpha_z", 0)), reverse=True)

        ready = [r for r in scored if r.get("trade_ready") and self.is_trading_window()]
        gate1 = [r for r in scored if r.get("passes_gate_1")]
        for r in ready:
            logger.info(
                f"TRADE READY: {r['ticker']} | α-z={r['alpha_z']:.2f} | "
                f"Dir={r['direction']} | Breadth={r['breadth']}/3 | ORB={r['vol_ratio']:.1f}×")
        logger.info(f"Scan complete: {len(scored)} scored · {len(gate1)} on watchlist · {len(ready)} trade-ready\n")
        return scored

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

            # Build the live OPTION order — captures the OPTION premium AT SIGNAL TIME
            # (the price you actually pay), the strike/expiry, and the contract key so
            # the trade resolves on the exact option later.
            order = None
            try:
                from engine.options import build_live_option_order
                order = build_live_option_order(ticker, entry, direction)
            except Exception as e:
                logger.warning(f"Option order build failed for {ticker}: {e}")

            trade_dict = {
                "ticker": ticker,
                "direction": direction,
                "alpha_z": alpha_z,
                "breadth": sig["breadth"],
                "entry": position["entry"],            # underlying price (reference)
                "stop": position["stop"],
                "target": position["target"],
                "qty": position["qty"],
                "reward_risk": position["reward_risk_ratio"],
                "instrument": (order["instrument"] if order else position["instrument"]),
                "vix": sig.get("vix"),
                "nifty_pct": sig.get("nifty_pct"),
            }
            if order:
                trade_dict.update({
                    "strategy": "3-Family",
                    "option_key": order["option_key"],
                    "strike": order["strike"],
                    "expiry": order["expiry"],
                    "entry_premium": order["premium"],          # LIVE option premium at signal
                    "target_premium": order["target_premium"],
                    "stop_premium": order["stop_premium"],
                    "qty": order["lot_size"] or position["qty"],  # OPTION lot for P&L
                })

            self.trade_log.add_signal(trade_dict)

            logger.info(
                f"SIGNAL: {ticker} {direction} {trade_dict['instrument']} | "
                f"entry premium={trade_dict.get('entry_premium', '?')} | "
                f"underlying={trade_dict['entry']}")

            # ── Notify (Telegram / WhatsApp / phone call) — each only if configured ──
            try:
                from engine.notifications import notify_signal
                if order:
                    notify_signal(order)
            except Exception as e:
                logger.warning(f"Notification failed for {ticker}: {e}")

            if PAPER_TRADING_PHASE:
                logger.info(f"PAPER MODE: Place order manually in Upstox app")

    def run_once(self):
        """Execute one scan cycle"""
        if not self.is_market_open():
            logger.info("Market closed")
            return

        scored = self.run_scan()
        ready = [s for s in scored if s.get("trade_ready")]
        if ready and self.is_trading_window():
            self.execute_signals(ready)

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
