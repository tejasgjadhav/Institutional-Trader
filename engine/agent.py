"""The agent holds the session clock and the paper trade log.

It answers two questions the rest of the system keeps asking. Is the market open? And what
is in the book so far? It also refreshes the corporate-events cache in the background during
the morning, because a results date is worth knowing before you sell anything.

It does not screen and it does not decide. A strategy module does that. See
engine/example_vwap.py for the one that ships, and write your own beside it.

Study code. Not investment advice. See DISCLAIMER.md.
"""
import logging
import threading
from datetime import datetime

from engine.config import IST, MARKET_OPEN, MARKET_CLOSE, UNIVERSE, APP_LOG_PATH
from engine.trade_log import TradeLog

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.FileHandler(APP_LOG_PATH), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class Agent:
    """Session clock, universe and paper book."""

    def __init__(self):
        self.trade_log = TradeLog()
        self.universe = list(UNIVERSE)
        self._event_thread = None
        self.maybe_refresh_events(force=True)

    def maybe_refresh_events(self, force: bool = False):
        """Refresh the NSE corporate-events cache in a background thread.

        It runs at about 9 AM and then every twenty minutes until just after 1 PM. NSE shows
        only the most recent announcements, so polling often and accumulating them catches a
        filing before it scrolls out of the window. The thread is a daemon, so it can never
        hold the engine up.
        """
        from engine import events
        now = datetime.now(IST)
        mins = now.hour * 60 + now.minute
        in_window = (9 * 60) <= mins <= (13 * 60 + 5)
        stale = events.cache_age_minutes() >= 20
        if not force and not (in_window and stale):
            return
        if self._event_thread and self._event_thread.is_alive():
            return

        def _work():
            try:
                events.refresh_event_scores()
            except Exception as e:
                logger.warning(f"Event refresh failed: {e}")

        self._event_thread = threading.Thread(target=_work, daemon=True)
        self._event_thread.start()

    def is_market_open(self) -> bool:
        """True on a weekday between the open and the close, in IST.

        It does not know about holidays. `data_utils.market_is_trading_today` does, by
        checking whether any data arrived.
        """
        now = datetime.now(IST)
        if now.weekday() >= 5:
            return False
        open_t = datetime.strptime(MARKET_OPEN, "%H:%M").time()
        close_t = datetime.strptime(MARKET_CLOSE, "%H:%M").time()
        return open_t <= now.time() <= close_t
