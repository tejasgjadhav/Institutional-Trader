"""
0DTE Intraday — NIFTY expiry-day CALL credit spread (the 5th strategy, paper forward-test).

At the open of a NIFTY weekly-expiry day: SELL the CE at the strike nearest spot*(1+0.5%),
BUY the CE ~200 pts further out. Hold to same-day settlement — NO intraday stop (that is how
it was backtested; a stop-vs-HIGH model destroyed the edge). Defined risk: max loss =
(width − credit) × qty, ~₹14k/lot.

Validated on REAL premiums — NSE bhavcopy 2019→Sep'24 (282 expiry days, config family chosen
here) + Upstox expired-instruments Oct'24→Jun'26 (91 days, untouched OOS): combined 373 trades,
85.0% win, +3.20% of margin per trade, net-positive EVERY calendar year 2019→2026. Costs
modeled (2.5% of credit + brokerage). Fills at the opening print are the unproven link — hence
this signals-only forward test. See studies/INTRADAY_85PCT_0DTE_CE_SPREAD.md.

State: data/zero_dte_positions.json (same schema as the other credit books, so the UI's generic
spread-table renderer works unchanged).
"""
import os
import json
import logging
from datetime import datetime, date

from engine.config import (
    IST, DATA_DIR, ZERO_DTE_ENABLED, ZERO_DTE_INDEX, ZERO_DTE_OTM_PCT, ZERO_DTE_WIDTH_PTS,
    ZERO_DTE_LOTS, ZERO_DTE_SETTLE_AFTER, ZERO_DTE_RV5_MAX, ZERO_DTE_STOP_MULT,
)
from engine.data_fetcher import fetch_upstox_quote, fetch_upstox_ltp, get_cached_ltp, fetch_upstox_historical
from engine.instruments import to_instrument_key

logger = logging.getLogger(__name__)

BOOK_PATH = os.path.join(DATA_DIR, "zero_dte_positions.json")


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
        logger.warning(f"zero_dte book save: {e}")


def _spot():
    p = get_cached_ltp(ZERO_DTE_INDEX)
    if p:
        return p
    lt = fetch_upstox_ltp(ZERO_DTE_INDEX)
    return lt.get("price") if lt.get("success") and lt.get("price") else None


def _quote(key: str):
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
        logger.debug(f"zero_dte quote {key}: {e}")
    return None


def _rv5():
    """NIFTY 5-day realized vol (std of last 5 daily log-returns, %), using closes STRICTLY
    before today (no lookahead at 9:16). Caches result on the function. None on data failure."""
    import numpy as np
    try:
        from datetime import timedelta
        df = fetch_upstox_historical(ZERO_DTE_INDEX, unit="days", interval=1,
                                     from_date=(date.today() - timedelta(days=30)).isoformat(),
                                     to_date=date.today().isoformat())
        if df is None or df.empty:
            return None
        df = df.sort_index()
        closes = [float(c) for ix, c in zip(df.index, df["Close"]) if ix.date() < date.today()][-6:]
        if len(closes) < 6:
            return None
        rv = float(np.std(np.diff(np.log(np.array(closes)))) * 100)
        _rv5.last = rv
        return rv
    except Exception as e:
        logger.warning(f"zero_dte rv5: {e}")
        return None


def _todays_ce_chain():
    """CE contracts expiring TODAY, sorted by strike — empty list on non-expiry days."""
    from engine.options import _load_index
    uk = to_instrument_key(ZERO_DTE_INDEX)
    if not uk:
        return []
    today = date.today()
    chain = [c for c in _load_index().get(uk, [])
             if c["type"] == "CE" and datetime.fromtimestamp(c["expiry"] / 1000).date() == today]
    return sorted(chain, key=lambda c: c["strike"])


def scan_signal() -> list:
    """Once per expiry day, right after the open: open THE spread (one trade, one index).
    Returns the new position (in a list) or []."""
    if not ZERO_DTE_ENABLED:
        return []
    try:
        from engine.data_utils import market_is_trading_today
        if not market_is_trading_today():
            return []
    except Exception:
        pass
    today = date.today()
    book = _load_book()
    if any(p["entry_date"] == today.isoformat() for p in book):
        return []
    chain = _todays_ce_chain()
    if not chain:            # not a weekly-expiry day
        return []
    rv = _rv5() if ZERO_DTE_RV5_MAX else None
    if rv is not None and rv >= ZERO_DTE_RV5_MAX:
        logger.info(f"zero_dte: SKIP — calm-regime filter (rv5 {rv:.2f}% >= {ZERO_DTE_RV5_MAX}%)")
        return []
    spot = _spot()
    if not spot:
        return []
    strikes = [c["strike"] for c in chain]
    si = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot * (1 + ZERO_DTE_OTM_PCT)))
    li = min(range(len(strikes)), key=lambda i: abs(strikes[i] - (strikes[si] + ZERO_DTE_WIDTH_PTS)))
    short, long = chain[si], chain[li]
    width_pts = long["strike"] - short["strike"]
    if width_pts < ZERO_DTE_WIDTH_PTS * 0.5:     # chain too short / clamped
        return []
    sm, lm = _quote(short["key"]), _quote(long["key"])
    if sm is None or lm is None:
        return []
    credit = round(sm - lm, 2)
    if credit <= 0:
        return []
    lot = int(short.get("lot", 0) or long.get("lot", 0) or 0)
    if lot <= 0:
        return []
    num_lots = int(ZERO_DTE_LOTS or 1)
    qty = lot * num_lots
    pos = {
        "id": f"0DTE-{today.isoformat()}", "symbol": ZERO_DTE_INDEX, "breakout_dir": None,
        "side": "BEAR_CALL", "entry_date": today.isoformat(), "entry_spot": round(spot, 1),
        "short_key": short["key"], "short_strike": int(short["strike"]),
        "long_key": long["key"], "long_strike": int(long["strike"]),
        "width_pts": int(width_pts), "lot": lot, "num_lots": num_lots, "qty": qty,
        "expiry": today.isoformat(), "short_prem": round(sm, 2), "long_prem": round(lm, 2),
        "credit": credit, "credit_width": round(credit / width_pts, 2),
        "stop_cost": None,                      # NO intraday stop — hold to settlement
        "max_loss_pts": round(width_pts - credit, 2),
        "capital": round((width_pts - credit) * qty, 0),
        "order_label": (f"SELL {ZERO_DTE_INDEX} {int(short['strike'])} CE / BUY {int(long['strike'])} CE"
                        f"  0DTE {today.isoformat()}  (bear-call, credit Rs{credit}"
                        f"{f' x{num_lots}' if num_lots != 1 else ''}, settles today 15:30)"),
        "current_cost": credit, "short_cur": round(sm, 2), "long_cur": round(lm, 2),
        "pnl_pts": 0.0, "status": "OPEN",
        "closed_date": None, "exit_cost": None,
    }
    book.append(pos)
    _save_book(book)
    logger.info(f"zero_dte: opened {pos['order_label']} (spot {spot:.0f})")
    return [pos]


def resolve_positions() -> int:
    """Intraday mark-to-market; after ZERO_DTE_SETTLE_AFTER on/after the expiry day, book the
    trade at intrinsic settlement vs spot. Returns # newly closed."""
    if not ZERO_DTE_ENABLED:
        return 0
    book = _load_book()
    now = datetime.now(IST)
    today = date.today()
    h, m = map(int, ZERO_DTE_SETTLE_AFTER.split(":"))
    past_settle = (now.hour * 60 + now.minute) >= (h * 60 + m)
    closed = 0
    changed = False
    for p in book:
        try:
            if p.get("status") != "OPEN":
                continue
            exp = date.fromisoformat(p["expiry"])
            settle_now = (today > exp) or (today == exp and past_settle)
            if not settle_now:
                sm, lm = _quote(p["short_key"]), _quote(p["long_key"])
                if sm is not None and lm is not None:
                    p["short_cur"] = round(sm, 2); p["long_cur"] = round(lm, 2)
                    p["current_cost"] = round(sm - lm, 2)
                    p["pnl_pts"] = round(p["credit"] - p["current_cost"], 2)
                    changed = True
                    # OPTIONAL short-leg stop (default OFF): buy back the spread intraday
                    if ZERO_DTE_STOP_MULT and sm >= ZERO_DTE_STOP_MULT * p["short_prem"]:
                        p["exit_cost"] = p["current_cost"]
                        p["status"] = "WIN" if p["pnl_pts"] > 0 else "LOSS"
                        p["closed_date"] = today.isoformat()
                        closed += 1
                        logger.info(f"zero_dte: STOPPED {p['id']} at {ZERO_DTE_STOP_MULT}x "
                                    f"(short {sm:.1f} vs entry {p['short_prem']:.1f}) pnl {p['pnl_pts']:+.1f}")
                continue
            spot = _spot() or p.get("entry_spot") or 0
            si = max(0.0, spot - p["short_strike"])
            li = max(0.0, spot - p["long_strike"])
            cost = min(max(si - li, 0.0), p["width_pts"])
            p["short_cur"] = round(si, 2); p["long_cur"] = round(li, 2)
            p["exit_cost"] = round(cost, 2); p["current_cost"] = round(cost, 2)
            p["pnl_pts"] = round(p["credit"] - cost, 2)
            p["status"] = "WIN" if p["pnl_pts"] > 0 else "LOSS"
            p["closed_date"] = today.isoformat()
            closed += 1; changed = True
            logger.info(f"zero_dte: settled {p['id']} pnl {p['pnl_pts']:+.1f} pts ({p['status']})")
        except Exception as e:
            logger.warning(f"zero_dte resolve {p.get('id')}: {e}")
    if changed:
        _save_book(book)
    return closed
