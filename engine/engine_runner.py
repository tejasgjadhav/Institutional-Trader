"""The headless engine. It runs the schedule; the desktop app only looks at what it wrote.

Every few seconds in market hours it writes a market snapshot, runs the example book's
screen inside its entry window, marks open paper positions to market and books anything that
has finished. The marking call keeps running after the close, so a position cannot be left
open over a weekend.

Run it with `python -m engine.engine_runner`, or once with `--once` to watch one cycle.

Study code. Not investment advice. The strategy it runs is an untested teaching example.
See DISCLAIMER.md.
"""
import os
import sys
import json
import time
import logging
import subprocess
from datetime import datetime

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import IST, DATA_DIR, LOG_DIR
from engine.agent import Agent
from engine.data_utils import get_market_snapshot
from engine import store
from engine.reader_edition import DISCLAIMER

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(),
              logging.FileHandler(os.path.join(LOG_DIR, "engine.log"))],
)
logger = logging.getLogger("engine_runner")

MARKET_SNAP = os.path.join(DATA_DIR, "market_snapshot.json")
TICK = 5               # wake every 5 s while the market is open


class EngineRunner:
    def __init__(self):
        self.agent = Agent()
        self._last_example_resolve = 0.0
        self._example_scan_day = None
        self._caffeinate = None

    # ── persistence ──────────────────────────────────────────────────────────
    @staticmethod
    def _write_json(path, obj):
        try:
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(obj, f, default=str)
            os.replace(tmp, path)   # atomic, so the viewer never reads half a file
        except Exception as e:
            logger.warning(f"write {path}: {e}")

    def _market(self, now):
        try:
            from engine.data_utils import market_is_trading_today, _market_is_open
            snap = get_market_snapshot()
            trading = market_is_trading_today()
            holiday = _market_is_open() and not trading   # open hours but no data
            self._write_json(MARKET_SNAP, {**snap, "ts": now.isoformat(),
                                           "trading": trading, "holiday": holiday})
            store.save_market(snap, now)
        except Exception as e:
            logger.warning(f"market snapshot: {e}")

    # ── the example book ─────────────────────────────────────────────────────
    def _example_book(self, now):
        """The worked VWAP example. It is the only strategy in this repository."""
        try:
            from engine import config
            if not getattr(config, "EXAMPLE_VWAP_ENABLED", False):
                return
            from engine import example_vwap
        except Exception as e:
            logger.warning(f"example book import: {e}")
            return

        if (time.time() - self._last_example_resolve) >= config.EXAMPLE_VWAP_RESOLVE_INTERVAL:
            self._last_example_resolve = time.time()
            try:
                n = example_vwap.resolve_positions()
                if n:
                    logger.info(f"example book: closed {n} position(s)")
            except Exception as e:
                logger.warning(f"example resolve: {e}")
            try:
                example_vwap.write_status()
            except Exception as e:
                logger.warning(f"example status: {e}")

        if not self.agent.is_market_open():
            return
        try:
            opened = example_vwap.scan_signals()
            if opened:
                self._example_scan_day = now.date()
                logger.info(f"example book: opened {len(opened)} position(s)")
        except Exception as e:
            logger.warning(f"example scan: {e}")

    # ── booking ──────────────────────────────────────────────────────────────
    # Each book marks and closes its own positions. The example book does it in
    # engine/example_vwap.py, on the interval set by EXAMPLE_VWAP_RESOLVE_INTERVAL, and it
    # force-closes anything still open once the exit time has passed. That call runs whether
    # or not the market is open, so a position cannot be stranded over a weekend.

    # ── housekeeping ─────────────────────────────────────────────────────────
    def _manage_wakelock(self):
        """Hold a power assertion while the market is open so an idle laptop cannot sleep
        mid-session. Released after the close. This prevents idle sleep only: closing the lid
        still sleeps the machine.
        """
        open_now = self.agent.is_market_open()
        alive = self._caffeinate is not None and self._caffeinate.poll() is None
        try:
            if open_now and not alive:
                self._caffeinate = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
                logger.info("wakelock: held (market open)")
            elif not open_now and alive:
                self._caffeinate.terminate()
                self._caffeinate = None
                logger.info("wakelock: released (market closed)")
        except Exception as e:
            logger.warning(f"wakelock: {e}")

    # ── the loop ─────────────────────────────────────────────────────────────
    def cycle(self):
        now = datetime.now(IST)
        self._market(now)
        self._manage_wakelock()
        self._example_book(now)

    def run(self):
        logger.warning(DISCLAIMER)
        logger.info(f"Engine started. DB stats: {store.stats()}")
        while True:
            try:
                self.cycle()
            except Exception as e:
                logger.error(f"cycle failed: {e}", exc_info=True)
            time.sleep(TICK if self.agent.is_market_open() else 300)


if __name__ == "__main__":
    if "--once" in sys.argv:
        r = EngineRunner()
        r.cycle()
        print("DB stats:", store.stats())
    else:
        EngineRunner().run()
