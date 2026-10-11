"""SHADOW BOOK v1u (user-approved 11-Oct-2026): paper-only, no Telegram, no effect on the live books.

WHAT. v1's geometry and gates (1-OTM, width 3, c/w >= 0.40, short >= Rs30 or the bull-put sub-floor,
TP-40, no stop) applied on UNION breakout days that are NOT Donchian-10 breakouts, i.e. the days the
live v1 never looks at. Research (research/run6/goal_compact.txt, addition A1) found it about +10% ROM
in both windows at +3-4 trades a month, but it failed the pre-registered next-session-entry check, so
it is measured on real 15:36 prices here before anyone trades it.

HOW. A separate module instance of engine/stock_credit.py (the same pattern stock_credit_v0.py uses)
with its own book file, its breakout function replaced, rejection logging off, and the forward record
write suppressed for the duration of its own scan. It runs after the live books and skips any name a
live book holds open; the live cross-book re-entry gap still applies because stock_credit reads the live
book files. data/shadow_v1u_positions.json is read by nothing else: not the cross-book gap, the digest,
Telegram, the forward record or the viewer. Every call is guarded, so it can never disturb trading.

    python -m engine.shadow_v1u --summary
"""
import os
import json
import logging
import importlib.util

from engine import config
from engine.config import DATA_DIR

logger = logging.getLogger(__name__)

_V1_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_credit.py")
_spec = importlib.util.spec_from_file_location("engine._shadow_v1u_impl", _V1_PATH)
_impl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_impl)

_impl.BOOK_PATH = os.path.join(DATA_DIR, "shadow_v1u_positions.json")
_impl.SNAP_PATH = os.path.join(DATA_DIR, "shadow_v1u.json")
_impl.RECORD_REJECTIONS = False
_impl.logger = logger

_LIVE_FILES = ("stock_credit_positions.json", "stock_credit_v2_positions.json",
               "stock_credit_v0_positions.json", "stock_credit_vlc_positions.json")
_d10_breakout = _impl._todays_breakout


def _union_not_d10(ticker):
    """Direction of a union (D5/10/15/20) breakout that v1's own D10 rule does NOT see, else None."""
    if _d10_breakout(ticker):
        return None
    from engine import stock_credit_v2
    b = stock_credit_v2._todays_breakout(ticker)
    return b[0] if b else None


_impl._todays_breakout = _union_not_d10


def _live_open_symbols() -> set:
    out = set()
    for f in _LIVE_FILES:
        try:
            for p in json.load(open(os.path.join(DATA_DIR, f))) or []:
                if p.get("status") == "OPEN":
                    out.add(p.get("symbol"))
        except Exception:
            pass
    return out


def scan() -> list:
    """Run the shadow scan once; returns the new shadow positions. Never raises."""
    if not getattr(config, "SHADOW_V1U_ENABLED", False):
        return []
    try:
        from engine import forward_record as _fr
        held = _live_open_symbols()
        _impl.UNIVERSE = [t for t in config.UNIVERSE if t.replace(".NS", "") not in held]
        _saved = _fr.record_entry
        _fr.record_entry = lambda *a, **k: None          # shadow trades never enter the forward record
        try:
            new = _impl.scan_signals() or []
        finally:
            _fr.record_entry = _saved
        n_open = sum(1 for p in _load() if p.get("status") == "OPEN")
        logger.info("shadow v1u: %d new (%s), %d open", len(new),
                    ", ".join(p.get("symbol", "?") for p in new) or "none", n_open)
        return new
    except Exception as e:
        logger.warning("shadow v1u scan: %s", e)
        return []


def resolve() -> int:
    """Mark and close shadow positions with v1's own exits. Never raises."""
    if not getattr(config, "SHADOW_V1U_ENABLED", False):
        return 0
    try:
        return _impl.resolve_positions() or 0
    except Exception as e:
        logger.warning("shadow v1u resolve: %s", e)
        return 0


def _load() -> list:
    try:
        return json.load(open(_impl.BOOK_PATH)) or []
    except Exception:
        return []


def summary() -> dict:
    rows = _load()
    closed = [p for p in rows if p.get("status") != "OPEN"]
    pnl = [float(p.get("pnl_rs") or p.get("realized_pnl") or 0) for p in closed]
    wins = sum(1 for x in pnl if x > 0)
    return {"open": len(rows) - len(closed), "closed": len(closed),
            "win_pct": round(100 * wins / len(closed), 1) if closed else None,
            "pnl_rs": round(sum(pnl), 0)}


if __name__ == "__main__":
    print(summary())
