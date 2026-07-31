"""STOCK CREDIT v0 (c/w 0.35-0.40) — forward paper-test book, user-approved 2026-07-31.

v2 trades credit/width >= 0.40. This trades the band just BELOW that gate, at the SAME geometry
(short 2-OTM, width 4), with the exits that band wants: take profit at 40% of credit, NO stop.

READ THIS BEFORE TRUSTING IT — studies/LOWCW_BAND_RESCUE.md section 7:
    IS  2019->Sep'24 : 77.4% win, +1.9% ROM, positive 4 of 6 years   (n=310)
    OOS Oct'24->Jul'26: 90.7% win, +19.4% ROM, positive 3 of 3 years (n=43)
The in-sample leg is inside noise of zero, and against the core book this adds ~+9% net for ~+99%
capital — the same capital in one more CORE lot returned 82% more. It exists to accumulate a live
track record so the tier can later be promoted or killed on evidence, not because it is proven.

NOTE what this is NOT: the width-1 "rescue" of the 0.30-0.40 band was REJECTED (strong in-sample
in both halves, dead out-of-sample in both), and the 0.30-0.35 half is dead in every test. Geometry
here is v2's, unchanged. Only the c/w window and the exits differ.

IMPLEMENTATION — this loads a SECOND, INDEPENDENT instance of engine/stock_credit_v2.py and rebinds
its module-level constants. That keeps one copy of the scan/resolve logic instead of a 400-line
fork that would drift out of sync. v2 itself is untouched at runtime: the two hooks this relies on
(STOCK_CREDIT_MAX_CW, EXCLUDE_SYMBOLS) are no-ops in v2's own instance.

Only scan_signals / resolve_positions / rows_for_ui are exported. build_watchlist and
notify_nearmiss are deliberately NOT re-exported — they write union_watchlist.json, which belongs
to v2 and must not be written twice.
"""
import os
import json
import logging
import importlib.util

from engine import config
from engine.config import DATA_DIR

logger = logging.getLogger(__name__)

_V2_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_credit_v2.py")
_spec = importlib.util.spec_from_file_location("engine._stock_credit_v0_impl", _V2_PATH)
_impl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_impl)

# ── rebind the second instance onto its own book, band and exits ──
_impl.BOOK_PATH = os.path.join(DATA_DIR, "stock_credit_v0_positions.json")
_impl.SNAP_PATH = os.path.join(DATA_DIR, "stock_credit_v0.json")
_impl.logger = logger

_impl.STOCK_CREDIT_ENABLED    = bool(getattr(config, "STOCK_CREDIT_V0_ENABLED", False))
_impl.STOCK_CREDIT_MIN_CW     = float(getattr(config, "STOCK_CREDIT_V0_MIN_CW", 0.35))
_impl.STOCK_CREDIT_MAX_CW     = float(getattr(config, "STOCK_CREDIT_V0_MAX_CW", 0.40))
_impl.STOCK_CREDIT_TAKE_PROFIT = float(getattr(config, "STOCK_CREDIT_V0_TAKE_PROFIT", 0.40))
_impl.STOCK_CREDIT_STOP_MULT  = float(getattr(config, "STOCK_CREDIT_V0_STOP_MULT", 99.0))
_impl.STOCK_CREDIT_MAX_NEW_PER_DAY = int(getattr(config, "STOCK_CREDIT_V0_MAX_NEW_PER_DAY", 3))
_impl.STOCK_CREDIT_MAX_OPEN   = int(getattr(config, "STOCK_CREDIT_V0_MAX_OPEN", 10))
_impl.STOCK_CREDIT_LOTS       = int(getattr(config, "STOCK_CREDIT_V0_LOTS", 1))

# geometry and every other gate stay exactly as v2 has them (short 2-OTM, width 4, DTE >= 10,
# premium >= Rs50, live spread/OI, the Rs40k width x lot exposure cap, re-entry gap).

BAND_LABEL = f"c/w {_impl.STOCK_CREDIT_MIN_CW:.2f}-{_impl.STOCK_CREDIT_MAX_CW:.2f}"
WIN_LABEL  = "77% IS (2019-Sep'24, +ve 4/6 yrs) / 91% OOS (Oct'24-Jul'26, n=43)"


def _open_symbols_in_other_books() -> frozenset:
    """Kept for reference only — v0 no longer defers to the other books (see scan_signals)."""
    syms = set()
    for fn in ("stock_credit_v2_positions.json", "stock_credit_positions.json"):
        try:
            with open(os.path.join(DATA_DIR, fn)) as f:
                for p in json.load(f) or []:
                    if p.get("status") == "OPEN" and p.get("symbol"):
                        syms.add(p["symbol"])
        except Exception:
            continue
    return frozenset(syms)


def scan_signals() -> list:
    """Open v0 spreads. Runs INDEPENDENTLY of v1 and v2 (user instruction 2026-07-31): the three
    books scan in parallel and v0 no longer skips names the others hold.

    v0 and v2 can never collide anyway — same geometry, mutually exclusive c/w bands (v2 takes
    >= 0.40, v0 takes 0.35-0.40), so one stock cannot qualify for both on the same day. v0 and v1
    CAN both fire on one stock: v1 is short-1-OTM/width-3, so its credit/width is higher on the
    same underlying. That gives two same-direction positions on one name, which the cross-book rule
    used to prevent. Accepted deliberately; single-name exposure is bounded by v0's 1 lot,
    max 3 new/day and max 10 open.
    """
    _impl.EXCLUDE_SYMBOLS = frozenset()
    return _impl.scan_signals()


def resolve_positions() -> int:
    return _impl.resolve_positions()


def rows_for_ui(max_closed: int = 30) -> list:
    return _impl.rows_for_ui(max_closed)


def book_path() -> str:
    return _impl.BOOK_PATH
