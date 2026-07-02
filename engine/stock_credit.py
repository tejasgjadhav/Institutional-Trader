"""
Stock Credit Spread — LIVE (parallel, paper-mode forward test). The FOURTH strategy, and the
high-FREQUENCY one (~16 signals/month vs the index swing's ~3).

Same fade-the-breakout idea as engine/swing_credit.py, but on the full ~100-stock universe and
gated hard: it SELLS a defined-risk credit spread AGAINST a daily Donchian-10 breakout on a stock,
but ONLY when (a) the credit is >= STOCK_CREDIT_MIN_CW of the strike width (rich premium = elevated
post-breakout IV — the edge), (b) the short leg is >= STOCK_CREDIT_MIN_PREM (tradeable), and (c) it
passes a LIVE liquidity gate (two-sided quote, OI, bid-ask). Multi-day, hold to expiry, overnight
carry. Backtest: 65% win, +16-25% net/trade — but FORWARD-TEST only; live mid-cap fills are the
unproven risk. See studies/STOCK_OPTIONS_NO_EDGE.md (Part 8).

State: data/stock_credit_positions.json (book) + data/stock_credit.json (read-only UI snapshot).
"""
import os
import json
import logging
from datetime import datetime, date, timedelta

from engine.config import (
    IST, DATA_DIR, UNIVERSE, STOCK_CREDIT_ENABLED, STOCK_CREDIT_DONCHIAN, STOCK_CREDIT_MIN_DTE,
    STOCK_CREDIT_SHORT_OFFSET, STOCK_CREDIT_WIDTH, STOCK_CREDIT_MIN_CW, STOCK_CREDIT_MIN_PREM,
    STOCK_CREDIT_STOP_MULT, STOCK_CREDIT_REENTRY_GAP_DAYS, STOCK_CREDIT_MAX_SPREAD_PCT,
    STOCK_CREDIT_MIN_OI, STOCK_CREDIT_MAX_NEW_PER_DAY, STOCK_CREDIT_MAX_OPEN, STOCK_CREDIT_LOTS,
)
from engine.data_fetcher import fetch_upstox_historical, fetch_upstox_quote, fetch_upstox_ltp, get_cached_ltp
from engine.instruments import to_instrument_key

logger = logging.getLogger(__name__)

BOOK_PATH = os.path.join(DATA_DIR, "stock_credit_positions.json")
SNAP_PATH = os.path.join(DATA_DIR, "stock_credit.json")


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
        logger.warning(f"stock_credit book save: {e}")


def _save_snapshot() -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        snap = {"ts": datetime.now(IST).isoformat(), "rows": rows_for_ui()}
        tmp = SNAP_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(snap, f, default=str)
        os.replace(tmp, SNAP_PATH)
    except Exception as e:
        logger.warning(f"stock_credit snapshot: {e}")


# ── market helpers ───────────────────────────────────────────────────────────
def _spot(ticker: str):
    p = get_cached_ltp(ticker)
    if p:
        return p
    lt = fetch_upstox_ltp(ticker)
    return lt.get("price") if lt.get("success") and lt.get("price") else None


def _quote(key: str):
    """(mid, bid, ask, oi) for an option leg, or (None, ...)."""
    try:
        q = fetch_upstox_quote(key)
        if q:
            bid, ask, oi = q.get("bid", 0.0) or 0.0, q.get("ask", 0.0) or 0.0, q.get("oi", 0) or 0
            if bid > 0 and ask > 0:
                return (bid + ask) / 2.0, bid, ask, oi
        lt = fetch_upstox_ltp(key)
        if lt.get("success") and lt.get("price"):
            return float(lt["price"]), 0.0, 0.0, 0
    except Exception as e:
        logger.debug(f"stock_credit _quote {key}: {e}")
    return None, 0.0, 0.0, 0


def _todays_breakout(ticker: str):
    start = (date.today() - timedelta(days=STOCK_CREDIT_DONCHIAN * 3 + 25)).isoformat()
    df = fetch_upstox_historical(ticker, unit="days", interval=1,
                                 from_date=start, to_date=date.today().isoformat())
    if df is None or df.empty or len(df) < STOCK_CREDIT_DONCHIAN + 2:
        return None
    df = df.sort_index()
    hi = float(df["High"].rolling(STOCK_CREDIT_DONCHIAN).max().shift(1).iloc[-1])
    lo = float(df["Low"].rolling(STOCK_CREDIT_DONCHIAN).min().shift(1).iloc[-1])
    c = float(df["Close"].iloc[-1])
    if c > hi:
        return "LONG"
    if c < lo:
        return "SHORT"
    return None


def _pick_legs(ticker: str, spot: float, opt_type: str):
    """(short, long, expiry) at the nearest expiry >= MIN_DTE days out, short 1-OTM, long +width."""
    from engine.options import _load_index
    uk = to_instrument_key(ticker)
    if not uk:
        return None
    contracts = [c for c in _load_index().get(uk, []) if c["type"] == opt_type]
    if not contracts:
        return None
    min_day = date.today() + timedelta(days=STOCK_CREDIT_MIN_DTE)
    min_ms = int(datetime(min_day.year, min_day.month, min_day.day).timestamp() * 1000)
    future = sorted({c["expiry"] for c in contracts if c["expiry"] >= min_ms})
    if not future:
        return None
    exp = future[0]
    chain = sorted([c for c in contracts if c["expiry"] == exp], key=lambda c: c["strike"])
    if len(chain) < STOCK_CREDIT_SHORT_OFFSET + STOCK_CREDIT_WIDTH + 2:
        return None
    strikes = [c["strike"] for c in chain]
    atm_i = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot))
    if opt_type == "CE":
        si, li = atm_i + STOCK_CREDIT_SHORT_OFFSET, atm_i + STOCK_CREDIT_SHORT_OFFSET + STOCK_CREDIT_WIDTH
    else:
        si, li = atm_i - STOCK_CREDIT_SHORT_OFFSET, atm_i - STOCK_CREDIT_SHORT_OFFSET - STOCK_CREDIT_WIDTH
    if si < 0 or li < 0 or si >= len(chain) or li >= len(chain):
        return None
    return chain[si], chain[li], str(datetime.fromtimestamp(exp / 1000).date())


# ── the work ─────────────────────────────────────────────────────────────────
def scan_signals() -> list:
    """Once/day: open fade credit spreads on stocks that broke out today AND clear all gates
    (credit/width, premium, liquidity), respecting per-day and total-open caps. Returns new ones."""
    if not STOCK_CREDIT_ENABLED:
        return []
    # SAFETY: only ever create signals on a real trading day (a daily breakout needs today's
    # session). Without this, calling scan_signals() on a weekend/holiday — or in testing — would
    # re-fire the previous session's breakout and pollute the book. The engine also gates by
    # market-open + the 15:10 cutoff, but the function guards itself too.
    try:
        from engine.data_utils import market_is_trading_today
        if not market_is_trading_today():
            return []
    except Exception:
        pass
    book = _load_book()
    today = date.today()
    open_now = [p for p in book if p["status"] == "OPEN"]
    new = []
    for ticker in UNIVERSE:
        if len(open_now) + len(new) >= STOCK_CREDIT_MAX_OPEN:
            break
        if len(new) >= STOCK_CREDIT_MAX_NEW_PER_DAY:
            break
        sym = ticker.replace(".NS", "")
        try:
            if any(p["symbol"] == sym and p["status"] == "OPEN" for p in book):
                continue
            entries = [p["entry_date"] for p in book if p["symbol"] == sym]
            if entries and (today - max(date.fromisoformat(d) for d in entries)).days < STOCK_CREDIT_REENTRY_GAP_DAYS:
                continue
            bdir = _todays_breakout(ticker)
            if not bdir:
                continue
            spot = _spot(ticker)
            if not spot:
                continue
            opt_type = "CE" if bdir == "LONG" else "PE"   # FADE
            legs = _pick_legs(ticker, spot, opt_type)
            if not legs:
                continue
            short, long, expiry = legs
            sm, sbid, sask, soi = _quote(short["key"])
            lm, *_ = _quote(long["key"])
            if sm is None or lm is None:
                continue
            credit = round(sm - lm, 2)
            width_pts = abs(short["strike"] - long["strike"])
            if credit <= 0 or width_pts <= 0:
                continue
            # ── the gates ──
            if credit / width_pts < STOCK_CREDIT_MIN_CW:           # the edge: rich credit vs risk
                continue
            if sm < STOCK_CREDIT_MIN_PREM:                          # tradeable premium
                continue
            if sbid > 0 and sask > 0:                              # live liquidity gate
                spread_pct = (sask - sbid) / sm * 100 if sm else 999
                if spread_pct > STOCK_CREDIT_MAX_SPREAD_PCT or soi < STOCK_CREDIT_MIN_OI:
                    continue
            lot = int(short.get("lot", 0) or long.get("lot", 0) or 0)
            if lot <= 0:                                            # no lot size -> not tradeable
                continue
            num_lots = int(STOCK_CREDIT_LOTS or 1)
            qty = lot * num_lots
            side = "BEAR_CALL" if opt_type == "CE" else "BULL_PUT"
            verb = "CE" if opt_type == "CE" else "PE"
            pos = {
                "id": f"{sym}-{today.isoformat()}", "symbol": sym, "breakout_dir": bdir, "side": side,
                "entry_date": today.isoformat(), "entry_spot": round(spot, 1),
                "short_key": short["key"], "short_strike": int(short["strike"]),
                "long_key": long["key"], "long_strike": int(long["strike"]),
                "width_pts": int(width_pts), "lot": lot, "num_lots": num_lots, "qty": qty,
                "expiry": expiry, "short_prem": round(sm, 2), "long_prem": round(lm, 2),
                "credit": credit, "credit_width": round(credit / width_pts, 2),
                "stop_cost": round(credit * STOCK_CREDIT_STOP_MULT, 2),
                "max_loss_pts": round(width_pts - credit, 2),
                "capital": round((width_pts - credit) * qty, 0) if qty else None,
                "order_label": (f"SELL {sym} {int(short['strike'])} {verb} / BUY {int(long['strike'])} {verb}"
                                f"  {expiry}  ({'bear-call' if side=='BEAR_CALL' else 'bull-put'}, credit Rs{credit}"
                                f"{f' x{num_lots}' if num_lots != 1 else ''})"),
                "current_cost": credit, "short_cur": round(sm, 2), "long_cur": round(lm, 2),
                "pnl_pts": 0.0, "status": "OPEN",
                "closed_date": None, "exit_cost": None,
            }
            book.append(pos); new.append(pos)
            logger.info(f"stock_credit: opened {side} {sym} (fade {bdir}) credit Rs{credit} c/w {pos['credit_width']} exp {expiry}")
        except Exception as e:
            logger.warning(f"stock_credit scan {sym}: {e}")
    if new:
        _save_book(book)
    _save_snapshot()
    return new


def resolve_positions() -> int:
    """Mark-to-market each OPEN spread; close on hard stop (>=2x credit) or at expiry (intrinsic).
    Overnight carry. Returns # newly closed."""
    if not STOCK_CREDIT_ENABLED:
        return 0
    book = _load_book()
    today = date.today()
    closed = 0
    changed = False
    for p in book:
        try:
            exp = date.fromisoformat(p["expiry"])
            expired = today >= exp
            # MTM current leg values for every non-expired position (open or closed) so the UI's
            # 'current' keeps running even after a WIN/LOSS is booked; realized P&L preserved below.
            if not expired:
                sm, *_ = _quote(p["short_key"]); lm, *_ = _quote(p["long_key"])
                if sm is not None and lm is not None:
                    p["short_cur"] = round(sm, 2); p["long_cur"] = round(lm, 2)
                    p["current_cost"] = round(sm - lm, 2); changed = True
            if p.get("status") != "OPEN":
                continue
            if expired:
                spot = _spot(p["symbol"]) or p.get("entry_spot") or 0
                if p["side"] == "BEAR_CALL":
                    si = max(0.0, spot - p["short_strike"]); li = max(0.0, spot - p["long_strike"])
                else:
                    si = max(0.0, p["short_strike"] - spot); li = max(0.0, p["long_strike"] - spot)
                cost = min(max(si - li, 0.0), p["width_pts"])
                p["short_cur"] = round(si, 2); p["long_cur"] = round(li, 2)
                p["exit_cost"] = round(cost, 2); p["current_cost"] = round(cost, 2)
                p["pnl_pts"] = round(p["credit"] - cost, 2)
                p["status"] = "WIN" if p["pnl_pts"] > 0 else "LOSS"
                p["closed_date"] = today.isoformat()
                closed += 1; changed = True
                continue
            cost = p.get("current_cost")
            if cost is None:
                continue
            p["pnl_pts"] = round(p["credit"] - cost, 2)
            if cost >= p["stop_cost"]:
                p["exit_cost"] = round(min(cost, p["width_pts"]), 2)
                p["pnl_pts"] = round(p["credit"] - p["exit_cost"], 2)
                p["status"] = "LOSS"; p["closed_date"] = today.isoformat()
                closed += 1
        except Exception as e:
            logger.warning(f"stock_credit resolve {p.get('id')}: {e}")
    if changed:
        _save_book(book)
    _save_snapshot()
    return closed


def rows_for_ui(max_closed: int = 30) -> list:
    book = _load_book()
    opens = [p for p in book if p.get("status") == "OPEN"]
    closed = sorted([p for p in book if p.get("status") != "OPEN"],
                    key=lambda p: p.get("closed_date") or "", reverse=True)[:max_closed]
    rows = []
    for p in opens + closed:
        qty = p.get("qty") or ((p.get("lot", 0) or 0) * int(p.get("num_lots", 1) or 1))
        pnl_pts = p.get("pnl_pts", 0.0) or 0.0
        cap = p.get("capital") or 0
        rows.append({
            "symbol": p["symbol"], "side": p["side"], "status": p.get("status", "OPEN"),
            "order_label": p.get("order_label", ""),
            "short_strike": p.get("short_strike"), "long_strike": p.get("long_strike"),
            "short_prem": p.get("short_prem"), "long_prem": p.get("long_prem"),
            "short_cur": p.get("short_cur"), "long_cur": p.get("long_cur"),
            "expiry": p.get("expiry"), "credit": p.get("credit"), "credit_width": p.get("credit_width"),
            "stop_cost": p.get("stop_cost"),
            "current_cost": p.get("current_cost"), "exit_cost": p.get("exit_cost"),
            "max_loss_pts": p.get("max_loss_pts"), "lot": p.get("lot", 0), "qty": qty,
            "num_lots": p.get("num_lots", 1), "capital": cap, "entry_date": p.get("entry_date"),
            "pnl_pts": pnl_pts, "pnl_rs": round(pnl_pts * qty, 0) if qty else None,
            "pnl_pct": round(pnl_pts * qty / cap * 100, 1) if cap else None,
        })
    return rows
