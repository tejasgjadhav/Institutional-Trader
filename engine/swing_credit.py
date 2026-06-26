"""
Swing Credit Spread — LIVE (parallel, paper-mode forward test). The THIRD strategy.

Distinct from the two intraday option-BUYING strategies (3-Family stocks, ORB+VWAP index):
this one SELLS a defined-risk credit spread AGAINST a daily Donchian breakout on the index and
holds it over several days to harvest theta as the breakout mean-reverts. Multi-day, overnight
carry — NOT squared off at 15:30.

Why FADE: a follow-the-breakout credit spread won only ~40% (index breakouts revert); fading it
wins ~67%. Validated on ~20 months of real expired-option data — see config.SWING_* and
studies/STOCK_OPTIONS_NO_EDGE.md (Part 6). Still a FORWARD-TEST (thin sample, backtest fills).

The signal each day, per index:
  - up-breakout   (close > Donchian-N high) -> SELL a BEAR-CALL spread (short 1-OTM CE, long +3)
  - down-breakout (close < Donchian-N low)  -> SELL a BULL-PUT  spread (short 1-OTM PE, long -3)
  - mid tenor: nearest expiry >= SWING_MIN_DTE days out.
  - hold to expiry; hard stop if cost-to-close >= SWING_STOP_MULT x credit.

State lives in data/swing_positions.json (the book). A display snapshot for the read-only UI is
written to data/swing.json. The engine drives scan_swing_signals() once/day and
resolve_swing_positions() periodically; the GUI only reads the snapshot.
"""
import os
import json
import logging
from datetime import datetime, date, timedelta

from engine.config import (
    IST, DATA_DIR, SWING_CREDIT_ENABLED, SWING_INDICES, SWING_DONCHIAN, SWING_MIN_DTE,
    SWING_SHORT_OFFSET, SWING_WIDTH, SWING_STOP_MULT, SWING_REENTRY_GAP_DAYS, SWING_LOTS,
)
from engine.data_fetcher import fetch_upstox_historical, fetch_upstox_quote, fetch_upstox_ltp
from engine.instruments import to_instrument_key

logger = logging.getLogger(__name__)

BOOK_PATH = os.path.join(DATA_DIR, "swing_positions.json")
SNAP_PATH = os.path.join(DATA_DIR, "swing.json")


# ── persistence ──────────────────────────────────────────────────────────────
def _load_book() -> list:
    try:
        with open(BOOK_PATH) as f:
            return json.load(f) or []
    except Exception:
        return []


def _save_book(book: list) -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = BOOK_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(book, f, default=str, indent=2)
        os.replace(tmp, BOOK_PATH)
    except Exception as e:
        logger.warning(f"swing book save: {e}")


def _save_snapshot() -> None:
    """Write the read-only UI snapshot (rows + summary) from the current book."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        snap = {"ts": datetime.now(IST).isoformat(), "rows": swing_rows_for_ui()}
        tmp = SNAP_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(snap, f, default=str)
        os.replace(tmp, SNAP_PATH)
    except Exception as e:
        logger.warning(f"swing snapshot: {e}")


# ── market helpers ───────────────────────────────────────────────────────────
def _spot(index: str):
    lt = fetch_upstox_ltp(index)
    return lt.get("price") if lt.get("success") and lt.get("price") else None


def _mid(key: str):
    """Live mid of an option leg (bid/ask midpoint; LTP fallback). None if no quote."""
    try:
        q = fetch_upstox_quote(key)
        if q:
            bid, ask = q.get("bid", 0.0) or 0.0, q.get("ask", 0.0) or 0.0
            if bid > 0 and ask > 0:
                return (bid + ask) / 2.0
        lt = fetch_upstox_ltp(key)
        if lt.get("success") and lt.get("price"):
            return float(lt["price"])
    except Exception as e:
        logger.debug(f"swing _mid {key}: {e}")
    return None


def _todays_breakout(index: str):
    """LONG if today's close breaks the Donchian-N high, SHORT if it breaks the low, else None.
    Uses the forming daily candle's last close as the intraday proxy (scan runs near 15:10)."""
    start = (date.today() - timedelta(days=SWING_DONCHIAN * 3 + 20)).isoformat()
    df = fetch_upstox_historical(index, unit="days", interval=1,
                                 from_date=start, to_date=date.today().isoformat())
    if df is None or df.empty or len(df) < SWING_DONCHIAN + 2:
        return None
    df = df.sort_index()
    prior_hi = float(df["High"].rolling(SWING_DONCHIAN).max().shift(1).iloc[-1])
    prior_lo = float(df["Low"].rolling(SWING_DONCHIAN).min().shift(1).iloc[-1])
    c = float(df["Close"].iloc[-1])
    if c > prior_hi:
        return "LONG"
    if c < prior_lo:
        return "SHORT"
    return None


def _pick_legs(index: str, spot: float, opt_type: str):
    """Resolve (short, long, expiry_date) for the credit spread from the LIVE option master:
    nearest expiry >= SWING_MIN_DTE days out, short SWING_SHORT_OFFSET strikes OTM, long
    SWING_WIDTH strikes further OTM. Returns (short_contract, long_contract, expiry_str) or None."""
    from engine.options import _load_index
    uk = to_instrument_key(index)
    if not uk:
        return None
    contracts = [c for c in _load_index().get(uk, []) if c["type"] == opt_type]
    if not contracts:
        return None
    min_day = date.today() + timedelta(days=SWING_MIN_DTE)
    min_ms = int(datetime(min_day.year, min_day.month, min_day.day).timestamp() * 1000)
    future = sorted({c["expiry"] for c in contracts if c["expiry"] >= min_ms})
    if not future:
        return None
    exp = future[0]
    chain = sorted([c for c in contracts if c["expiry"] == exp], key=lambda c: c["strike"])
    if len(chain) < SWING_SHORT_OFFSET + SWING_WIDTH + 2:
        return None
    strikes = [c["strike"] for c in chain]
    atm_i = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot))
    if opt_type == "CE":   # OTM = higher strike
        si, li = atm_i + SWING_SHORT_OFFSET, atm_i + SWING_SHORT_OFFSET + SWING_WIDTH
    else:                  # PE: OTM = lower strike
        si, li = atm_i - SWING_SHORT_OFFSET, atm_i - SWING_SHORT_OFFSET - SWING_WIDTH
    if si < 0 or li < 0 or si >= len(chain) or li >= len(chain):
        return None
    return chain[si], chain[li], str(datetime.fromtimestamp(exp / 1000).date())


# ── the work ─────────────────────────────────────────────────────────────────
def scan_swing_signals() -> list:
    """Once/day: open a new fade credit spread on any index that broke out today (if no open
    position there and re-entry spacing allows). Records to the book. Returns the new positions."""
    if not SWING_CREDIT_ENABLED:
        return []
    book = _load_book()
    today = date.today()
    new = []
    for index in SWING_INDICES:
        try:
            if any(p["index"] == index and p["status"] == "OPEN" for p in book):
                continue   # one open position per index at a time
            entries = [p["entry_date"] for p in book if p["index"] == index]
            if entries:
                last = max(date.fromisoformat(d) for d in entries)
                if (today - last).days < SWING_REENTRY_GAP_DAYS:
                    continue
            bdir = _todays_breakout(index)
            if not bdir:
                continue
            spot = _spot(index)
            if not spot:
                continue
            opt_type = "CE" if bdir == "LONG" else "PE"   # FADE: bear-call up / bull-put down
            legs = _pick_legs(index, spot, opt_type)
            if not legs:
                continue
            short, long, expiry = legs
            sm, lm = _mid(short["key"]), _mid(long["key"])
            if sm is None or lm is None:
                continue
            credit = round(sm - lm, 2)
            if credit <= 0:
                continue
            width_pts = abs(short["strike"] - long["strike"])
            lot = int(short.get("lot", 0) or long.get("lot", 0) or 0)
            num_lots = int(SWING_LOTS.get(index, 1) or 1)   # paper sizing (lots per spread)
            qty = lot * num_lots                              # total options per leg
            side = "BEAR_CALL" if opt_type == "CE" else "BULL_PUT"
            verb = "CE" if opt_type == "CE" else "PE"
            pos = {
                "id": f"{index}-{today.isoformat()}",
                "index": index, "breakout_dir": bdir, "side": side,
                "entry_date": today.isoformat(), "entry_spot": round(spot, 1),
                "short_key": short["key"], "short_strike": int(short["strike"]),
                "long_key": long["key"], "long_strike": int(long["strike"]),
                "width_pts": int(width_pts), "lot": lot, "num_lots": num_lots, "qty": qty,
                "expiry": expiry,
                "credit": credit, "stop_cost": round(credit * SWING_STOP_MULT, 2),
                "max_loss_pts": round(width_pts - credit, 2),
                "capital": round((width_pts - credit) * qty, 0) if qty else None,
                "order_label": (f"SELL {index} {int(short['strike'])} {verb} / "
                                f"BUY {int(long['strike'])} {verb}  {expiry}  "
                                f"({'bear-call' if side=='BEAR_CALL' else 'bull-put'}, credit Rs{credit}"
                                f"{f' x{num_lots} lots' if num_lots != 1 else ''})"),
                "current_cost": credit, "pnl_pts": 0.0, "status": "OPEN",
                "closed_date": None, "exit_cost": None,
            }
            book.append(pos)
            new.append(pos)
            logger.info(f"swing: opened {side} on {index} (fade {bdir}) credit Rs{credit} exp {expiry}")
        except Exception as e:
            logger.warning(f"swing scan {index}: {e}")
    if new:
        _save_book(book)
    _save_snapshot()
    return new


def resolve_swing_positions() -> int:
    """Mark-to-market every OPEN position; close on hard stop (cost >= stop_cost) or at expiry
    (settle at intrinsic). Overnight carry — never force-closed at 15:30. Returns # newly closed."""
    if not SWING_CREDIT_ENABLED:
        return 0
    book = _load_book()
    today = date.today()
    closed = 0
    changed = False
    for p in book:
        if p.get("status") != "OPEN":
            continue
        try:
            exp = date.fromisoformat(p["expiry"])
            # EXPIRY settlement: spread cost = intrinsic of the short, capped at width.
            if today >= exp:
                spot = _spot(p["index"]) or p.get("entry_spot") or 0
                if p["side"] == "BEAR_CALL":
                    intrinsic = max(0.0, spot - p["short_strike"])
                else:  # BULL_PUT
                    intrinsic = max(0.0, p["short_strike"] - spot)
                cost = min(intrinsic, p["width_pts"])
                p["exit_cost"] = round(cost, 2)
                p["current_cost"] = round(cost, 2)
                p["pnl_pts"] = round(p["credit"] - cost, 2)
                p["status"] = "WIN" if p["pnl_pts"] > 0 else "LOSS"
                p["closed_date"] = today.isoformat()
                closed += 1; changed = True
                logger.info(f"swing: {p['index']} {p['side']} expired {p['status']} "
                            f"pnl {p['pnl_pts']:+.1f} pts")
                continue
            # MARK-TO-MARKET: cost to close = buy back short, sell long.
            sm, lm = _mid(p["short_key"]), _mid(p["long_key"])
            if sm is None or lm is None:
                continue
            cost = sm - lm
            p["current_cost"] = round(cost, 2)
            p["pnl_pts"] = round(p["credit"] - cost, 2)
            changed = True
            if cost >= p["stop_cost"]:
                p["exit_cost"] = round(min(cost, p["width_pts"]), 2)
                p["pnl_pts"] = round(p["credit"] - p["exit_cost"], 2)
                p["status"] = "LOSS"
                p["closed_date"] = today.isoformat()
                closed += 1
                logger.info(f"swing: {p['index']} {p['side']} STOPPED pnl {p['pnl_pts']:+.1f} pts")
        except Exception as e:
            logger.warning(f"swing resolve {p.get('id')}: {e}")
    if changed:
        _save_book(book)
    _save_snapshot()
    return closed


def swing_rows_for_ui(max_closed: int = 6) -> list:
    """Display rows for the read-only PM section: OPEN positions first, then recent closed."""
    book = _load_book()
    opens = [p for p in book if p.get("status") == "OPEN"]
    closed = sorted([p for p in book if p.get("status") != "OPEN"],
                    key=lambda p: p.get("closed_date") or "", reverse=True)[:max_closed]
    rows = []
    for p in opens + closed:
        lot = p.get("lot", 0) or 0
        qty = p.get("qty") or (lot * int(p.get("num_lots", 1) or 1))   # total options (lots×lot size)
        pnl_pts = p.get("pnl_pts", 0.0) or 0.0
        cap = p.get("capital") or 0
        pnl_rs = round(pnl_pts * qty, 0) if qty else None
        pnl_pct = round(pnl_pts * qty / cap * 100, 1) if cap else None
        rows.append({
            "index": p["index"], "side": p["side"], "status": p.get("status", "OPEN"),
            "order_label": p.get("order_label", ""),
            "short_strike": p.get("short_strike"), "long_strike": p.get("long_strike"),
            "expiry": p.get("expiry"), "credit": p.get("credit"),
            "current_cost": p.get("current_cost"), "max_loss_pts": p.get("max_loss_pts"),
            "lot": lot, "capital": cap, "entry_date": p.get("entry_date"),
            "pnl_pts": pnl_pts, "pnl_rs": pnl_rs, "pnl_pct": pnl_pct,
        })
    return rows
