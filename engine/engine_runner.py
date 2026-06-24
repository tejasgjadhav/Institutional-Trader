"""
Headless engine runner — the trading engine, decoupled from the GUI.

Runs the FULL daily schedule independent of whether the desktop app is open:
  - every 5 min during market hours: scan (3-Family stocks + ORB+VWAP indices),
    fire ready signals, record to the signal DB + daily engine DB, resolve paper trades;
  - at the 15:30 close (Mon-Fri): force-book every open paper trade;
  - every cycle: write a market snapshot + the latest scan to disk for the read-only UI.

Launched by launchd (com.sayali.institutionaltrader.engine). The GUI is a read-only
viewer of what this writes (data/latest_scan.json, data/market_snapshot.json, the DBs,
and trade_log.json). All data is saved locally daily; trade outcomes stay in trade_log.json.
"""
import os
import sys
import json
import time
import logging
from datetime import datetime

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import IST, DATA_DIR, LOG_DIR
from engine.agent import Agent
from engine.paper_resolver import resolve_pending
from engine.data_utils import get_market_snapshot
from engine import signal_db, store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(),
              logging.FileHandler(os.path.join(LOG_DIR, "engine.log"))],
)
logger = logging.getLogger("engine_runner")

LATEST_SCAN = os.path.join(DATA_DIR, "latest_scan.json")
MARKET_SNAP = os.path.join(DATA_DIR, "market_snapshot.json")
SCAN_INTERVAL = 300   # 5 min
TICK = 5              # wake every 5 s in market hours (tight scan timing + live bar)


class EngineRunner:
    def __init__(self):
        self.agent = Agent()
        self._last_scan = 0.0
        self._eod_day = None
        self._notified = set()
        self._notified_day = None

    # ── persistence helpers ──────────────────────────────────────────────────
    @staticmethod
    def _write_json(path, obj):
        try:
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(obj, f, default=str)
            os.replace(tmp, path)   # atomic — the UI never reads a half-written file
        except Exception as e:
            logger.warning(f"write {path}: {e}")

    def _market(self, now):
        try:
            snap = get_market_snapshot()
            self._write_json(MARKET_SNAP, {**snap, "ts": now.isoformat()})
            store.save_market(snap, now)
        except Exception as e:
            logger.warning(f"market snapshot: {e}")

    def _record_stock_db(self, ready, now):
        from engine.options import build_live_option_order
        from engine.data_fetcher import get_cached_ltp
        for s in ready:
            try:
                spot = get_cached_ltp(s["ticker"]) or 0
                order = build_live_option_order(s["ticker"], spot, s.get("direction", "LONG"))
                o = order or {}
                signal_db.record_signal(
                    time=now.strftime("%H:%M:%S"), strategy="3-Family",
                    symbol=s["ticker"].replace(".NS", ""), direction=s.get("direction"),
                    opt_type=o.get("instrument"), strike=o.get("strike"), expiry=o.get("expiry"),
                    entry_premium=o.get("premium"), target_premium=o.get("target_premium"),
                    stop_premium=o.get("stop_premium"), lot=o.get("lot_size"),
                    capital=o.get("capital"), alpha_z=s.get("alpha_z"),
                    breadth=s.get("breadth"), vol_ratio=s.get("vol_ratio"), status="OPEN")
            except Exception as e:
                logger.warning(f"signal_db stock {s.get('ticker')}: {e}")

    def _record_index_db(self):
        for s in (getattr(self.agent, "orbvwap_signals", []) or []):
            if not s.get("entry"):
                continue
            try:
                signal_db.record_signal(
                    time=s.get("time"), strategy="ORB+VWAP", symbol=s.get("index"),
                    direction=s.get("direction"), opt_type=s.get("kind"),
                    strike=s.get("strike"), expiry=s.get("expiry"),
                    entry_premium=s.get("entry"), target_premium=s.get("target"),
                    stop_premium=s.get("stop"), lot=s.get("lot"),
                    capital=s.get("capital"), status=s.get("status"))
            except Exception as e:
                logger.warning(f"signal_db index {s.get('index')}: {e}")

    # ── the work ─────────────────────────────────────────────────────────────
    def _scan(self, now):
        scored = self.agent.run_scan()   # stock scan + index ORB+VWAP; logs index trades
        self._write_json(LATEST_SCAN, {
            "ts": now.isoformat(),
            "results": scored,
            "orbvwap": getattr(self.agent, "orbvwap_signals", []),
        })
        store.save_scan(scored, now)

        if self._notified_day != now.date():        # reset the daily fired set
            self._notified_day = now.date()
            self._notified = set()

        if self.agent.is_trading_window():
            ready = [s for s in scored if s.get("trade_ready")]
            new = [s for s in ready if s.get("ticker") not in self._notified]
            for s in new:
                self._notified.add(s["ticker"])
            if new:
                try:
                    self.agent.execute_signals(new)      # -> trade_log + notifications
                except Exception as e:
                    logger.warning(f"execute_signals: {e}")
                self._record_stock_db(new, now)

        self._record_index_db()
        try:
            n = resolve_pending(self.agent.trade_log)    # close PENDING paper trades
            if n:
                logger.info(f"resolved {n} paper trade(s)")
        except Exception as e:
            logger.warning(f"resolve_pending: {e}")
        rdy = sum(1 for s in scored if s.get("trade_ready"))
        logger.info(f"scan done: {len(scored)} scored, {rdy} trade-ready")

    def _maybe_eod(self, now):
        """Force-book every open paper trade once its session is over.

        Runs EVERY cycle after the 15:30 close (and on weekends) and KEEPS RETRYING until
        nothing is left PENDING — so a transient data glitch at 15:30 can no longer orphan a
        trade in the log forever (that's exactly what stranded a BankNifty trade). The
        trade log is the critical record; no trade may be left unbooked once the day is done.
        """
        m = now.hour * 60 + now.minute
        after_close = now.weekday() >= 5 or m >= 15 * 60 + 30
        if not after_close:
            return
        pending = [t for t in self.agent.trade_log.trades if t.get("outcome") is None]
        if not pending:
            return
        logger.info(f"EOD booking — {len(pending)} open paper trade(s) pending; force-closing")
        try:
            resolve_pending(self.agent.trade_log)
            still = sum(1 for t in self.agent.trade_log.trades if t.get("outcome") is None)
            if still:
                logger.warning(f"EOD booking: {still} still pending — will retry next cycle")
            else:
                logger.info("EOD booking — all trades booked")
        except Exception as e:
            logger.warning(f"EOD booking: {e}")

    def cycle(self):
        now = datetime.now(IST)
        self._market(now)
        self._maybe_eod(now)
        if self.agent.is_market_open() and (time.time() - self._last_scan) >= SCAN_INTERVAL:
            self._last_scan = time.time()
            try:
                self._scan(now)
            except Exception as e:
                logger.error(f"scan cycle failed: {e}", exc_info=True)

    def run(self):
        logger.info(f"Engine runner started. DB stats: {store.stats()}")
        while True:
            try:
                self.cycle()
            except Exception as e:
                logger.error(f"cycle failed: {e}", exc_info=True)
            # tight loop during market hours; idle slowly when closed (still writes a
            # market snapshot every cycle and catches the 15:31-15:55 EOD window).
            time.sleep(TICK if self.agent.is_market_open() else 300)


if __name__ == "__main__":
    if "--once" in sys.argv:        # one cycle (for testing), forces a scan
        r = EngineRunner()
        now = datetime.now(IST)
        r._market(now)
        if r.agent.is_market_open():
            r._scan(now)
        else:
            logger.info("market closed — wrote market snapshot only")
        print("DB stats:", store.stats())
    else:
        EngineRunner().run()
