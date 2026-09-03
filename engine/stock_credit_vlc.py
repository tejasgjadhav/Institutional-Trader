"""SIDEWISE LOW CREDIT strategy ("vlc") — forward paper-test book, user-ordered 2026-08-28.

Band c/w 0.30-0.40 at v0's geometry (short 2-OTM, width 4, TP-40, NO stop), restricted to the
21 name x side cells that cleared win >= 80% AND net ROM > +5% in BOTH windows of
studies/BAND_030_040_NAMEWISE.md: 12 bear-call names and 9 bull-put names. A name trades ONLY
its qualified side (SIDE_WHITELIST hook in stock_credit_v2.py).

READ THIS BEFORE TRUSTING IT. The evidence is thin and the study says so: the pooled IS-qualifier
screen measured -3.5% ROM out of sample, most of these cells hold under 10 OOS trades, and at
232-cell screening intensity this survivor count is consistent with luck. The book exists to put
the 21 cells on a LIVE forward record so they can be promoted or killed on evidence at ~30 fills.
It is not a proven edge and must not be sized past 1 lot.

IMPLEMENTATION — same pattern as v0: a second, independent instance of stock_credit_v2.py with
its constants rebound. The SIDE_WHITELIST hook is a no-op (None) in every other instance.
Scans AFTER v2/v1/v0 in the engine cycle, so the cross-book 3-day entry gap (which now includes
this book's file) makes every other book win a same-day clash automatically.
"""
import os
import json
import logging
import importlib.util

from engine import config
from engine.config import DATA_DIR

logger = logging.getLogger(__name__)

_V2_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_credit_v2.py")
_spec = importlib.util.spec_from_file_location("engine._stock_credit_vlc_impl", _V2_PATH)
_impl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_impl)

# ── rebind the instance onto its own book, band, exits and whitelist ──
_impl.BOOK_PATH = os.path.join(DATA_DIR, "stock_credit_vlc_positions.json")
_impl.SNAP_PATH = os.path.join(DATA_DIR, "stock_credit_vlc.json")
_impl.logger = logger
_impl._FR_BOOK = "vlc"

_impl.STOCK_CREDIT_ENABLED     = bool(getattr(config, "STOCK_CREDIT_VLC_ENABLED", False))
_impl.STOCK_CREDIT_MIN_CW      = float(getattr(config, "STOCK_CREDIT_VLC_MIN_CW", 0.30))
_impl.STOCK_CREDIT_MAX_CW      = float(getattr(config, "STOCK_CREDIT_VLC_MAX_CW", 0.40))
_impl.STOCK_CREDIT_TAKE_PROFIT = float(getattr(config, "STOCK_CREDIT_VLC_TAKE_PROFIT", 0.40))
_impl.STOCK_CREDIT_MAX_NEW_PER_DAY = int(getattr(config, "STOCK_CREDIT_VLC_MAX_NEW_PER_DAY", 3))
_impl.STOCK_CREDIT_MAX_OPEN    = int(getattr(config, "STOCK_CREDIT_VLC_MAX_OPEN", 10))
_impl.STOCK_CREDIT_LOTS        = int(getattr(config, "STOCK_CREDIT_VLC_LOTS", 1))
_impl.SIDE_WHITELIST = {k: frozenset(v) for k, v in
                        getattr(config, "STOCK_CREDIT_VLC_WHITELIST", {}).items()}

# geometry and every other gate stay exactly as v2 has them (short 2-OTM, width 4, DTE >= 10,
# premium >= Rs50, live spread/OI, exposure cap, cross-book re-entry gap).

BAND_LABEL = f"c/w {_impl.STOCK_CREDIT_MIN_CW:.2f}-{_impl.STOCK_CREDIT_MAX_CW:.2f}"


def scan_signals() -> list:
    """Open vlc spreads. Runs AFTER v2/v1/v0: their same-cycle entries are already in their book
    files, so the cross-book gap blocks vlc on any name another book just took (0 < 3 days)."""
    return _impl.scan_signals()


def resolve_positions() -> int:
    return _impl.resolve_positions()


def rows_for_ui(max_closed: int = 30) -> list:
    return _impl.rows_for_ui(max_closed)


def book_path() -> str:
    return _impl.BOOK_PATH
