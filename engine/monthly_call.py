"""
MONTHLY LONG-CALL PULLBACK — signals-only paper forward-test. The 6th strategy.

SAME signal as the monthly futures book (engine/monthly_fut.py): at each expiry-to-expiry cycle
start, if NIFTY > its 200DMA, take the 8 worst 1-month losers among universe stocks still above
their OWN 200DMA, keep the 5 with the highest 20-day vol. But instead of buying the future, BUY
the ~ATM CALL at the cycle's monthly expiry (1 lot each). The TRIGGER is on the UNDERLYING —
exit the call when the stock closes +2% (decaying to +1% after 12 sessions, TP) or −5% (SL);
else hold to expiry. P&L is booked on the CALL premium.

Why calls: premium ≪ futures margin, so return-on-capital is higher. OOS-validated (real Upstox
premiums Oct'24→Jul'26): 5-pick simple config = 67% win, +6-7%/mo on premium. HIGH VARIANCE —
a bought call can lose ~100% of premium in a selloff, so crash months run to −51%. The 8-pick +
extra gates version FAILED OOS (curve-fit), so this is deliberately the plain 5-pick, no gates.
See studies/monthly_fut/MAX_TRADES_OPTIONS.md + opt_oos.py.

Signals-only: the engine surfaces the CALL to BUY on PM DECISIONS; the user places it manually.
State: data/monthly_call_positions.json (book) + data/monthly_call.json (UI snapshot).
"""
import os
import json
import logging
from datetime import datetime, date, timedelta

from engine.config import (
    IST, DATA_DIR, UNIVERSE,
    MONTHLY_CALL_ENABLED, MONTHLY_CALL_LOTS,
    MONTHLY_FUT_POOL, MONTHLY_FUT_TOPN, MONTHLY_FUT_TP, MONTHLY_FUT_TP_LATE,
    MONTHLY_FUT_DECAY_DAY, MONTHLY_FUT_SL, MONTHLY_FUT_MIN_DTE,
)
from engine.data_fetcher import fetch_upstox_ltp, fetch_upstox_quote
from engine.instruments import to_instrument_key
# reuse the futures book's cycle calendar, closes, earnings-skip, regime pick logic
from engine.monthly_fut import (
    _last_thursday, _cycle_expiry, _closes, _earnings_skip_set, IDX_SYMBOLS,
)

logger = logging.getLogger(__name__)

BOOK_PATH = os.path.join(DATA_DIR, "monthly_call_positions.json")
SNAP_PATH = os.path.join(DATA_DIR, "monthly_call.json")


# ── persistence ───────────────────────────────────────────────────────────────
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
        logger.warning(f"monthly_call book save: {e}")


def _save_snapshot(extra: dict = None) -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        snap = {"ts": datetime.now(IST).isoformat(), "rows": call_rows_for_ui()}
        if extra:
            snap.update(extra)
        tmp = SNAP_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(snap, f, default=str)
        os.replace(tmp, SNAP_PATH)
    except Exception as e:
        logger.warning(f"monthly_call snapshot: {e}")


# ── option resolution (ATM call at the cycle expiry) ──────────────────────────
def _atm_call(ticker: str, spot: float, cycle_exp: date):
    """Resolve the ~ATM CALL whose expiry is nearest the cycle expiry. Returns
    (strike, instrument_key, expiry_str) or None."""
    from engine.options import _load_index
    uk = to_instrument_key(ticker)
    if not uk:
        return None
    contracts = [c for c in _load_index().get(uk, []) if c["type"] == "CE"]
    if not contracts:
        return None
    target_ms = int(datetime(cycle_exp.year, cycle_exp.month, cycle_exp.day).timestamp() * 1000)
    exp = min({c["expiry"] for c in contracts}, key=lambda e: abs(e - target_ms))
    chain = sorted([c for c in contracts if c["expiry"] == exp], key=lambda c: c["strike"])
    if not chain:
        return None
    atm = min(chain, key=lambda c: abs(c["strike"] - spot))
    return atm["strike"], atm["key"], str(datetime.fromtimestamp(exp / 1000).date())


def _opt_mid(key: str):
    """Live mid of the call (bid/ask midpoint; LTP fallback). None on quote error."""
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
        logger.debug(f"monthly_call _opt_mid {key}: {e}")
    return None


# ── scan (once per cycle) ─────────────────────────────────────────────────────
def scan_call_signals() -> list:
    """Enter the cycle's 5 pullback long-CALLs near the close of the first trading day after the
    prior monthly expiry (engine calls daily after 15:10; guards make it fire once)."""
    if not MONTHLY_CALL_ENABLED:
        return []
    try:
        from engine.data_utils import market_is_trading_today
        if not market_is_trading_today():
            return []
    except Exception:
        pass
    today = date.today()
    expiry = _cycle_expiry(today)
    cyc = expiry.isoformat()
    if (expiry - today).days < MONTHLY_FUT_MIN_DTE:
        return []
    book = _load_book()
    if any(p.get("cycle") == cyc for p in book):
        return []
    nifty = _closes("NIFTY")
    if nifty is None:
        logger.warning("monthly_call: no NIFTY history — skipping scan today")
        return []
    if float(nifty.iloc[-1]) <= float(nifty.rolling(200, min_periods=150).mean().iloc[-1]):
        book.append({"id": f"CYCLE-{cyc}", "cycle": cyc, "status": "REGIME_OFF",
                     "entry_date": today.isoformat()})
        _save_book(book); _save_snapshot()
        logger.info(f"monthly_call: NIFTY under 200DMA — standing aside for cycle {cyc}")
        return []
    skip, cal_ok = _earnings_skip_set(expiry)
    cand = []
    for u in UNIVERSE:
        sym = u.replace(".NS", "")
        if sym in IDX_SYMBOLS or sym in skip:
            continue
        try:
            s = _closes(sym)
            if s is None or len(s) < 200:
                continue
            px = float(s.iloc[-1])
            ma200 = float(s.rolling(200, min_periods=150).mean().iloc[-1])
            if px <= ma200:
                continue
            mom1 = px / float(s.iloc[-22]) - 1
            vol20 = float(s.pct_change().iloc[-20:].std()) * (252 ** 0.5)
            cand.append((sym, mom1, vol20, px))
        except Exception as e:
            logger.debug(f"monthly_call cand {sym}: {e}")
    cand.sort(key=lambda t: t[1])              # worst 1-month losers first
    pool = cand[:MONTHLY_FUT_POOL]
    pool.sort(key=lambda t: -t[2])             # highest 20d vol first
    picks = pool[:MONTHLY_FUT_TOPN]
    new = []
    for sym, mom1, vol20, px in picks:
        leg = _atm_call(sym, px, expiry)
        if not leg:
            logger.info(f"monthly_call: no ATM call chain for {sym} — skipping")
            continue
        strike, key, opt_exp = leg
        prem = _opt_mid(key)
        if prem is None or prem <= 0:
            logger.info(f"monthly_call: no quote for {sym} {strike}CE — skipping")
            continue
        pos = {
            "id": f"{sym}-{cyc}", "symbol": sym, "cycle": cyc, "expiry": cyc,
            "opt_expiry": opt_exp, "strike": int(strike), "opt_key": key,
            "entry_date": today.isoformat(), "entry_px": round(px, 2),
            "tp_px": round(px * (1 + MONTHLY_FUT_TP), 2),
            "tp_late_px": round(px * (1 + MONTHLY_FUT_TP_LATE), 2),
            "sl_px": round(px * (1 - MONTHLY_FUT_SL), 2),
            "entry_prem": round(prem, 2), "cur_prem": round(prem, 2),
            "lots": int(MONTHLY_CALL_LOTS), "sessions": 0, "last_mark": today.isoformat(),
            "mom1": round(mom1, 4), "vol20": round(vol20, 3),
            "cur_px": round(px, 2), "pnl_pct": 0.0,
            "order_label": (f"BUY {sym} {int(strike)} CE {opt_exp} @ ~Rs{round(prem,1)} "
                            f"(monthly pullback, {MONTHLY_CALL_LOTS} lot) — exit when spot "
                            f"TP {round(px*(1+MONTHLY_FUT_TP),1)} / SL {round(px*(1-MONTHLY_FUT_SL),1)}"),
            "status": "OPEN", "closed_date": None, "exit_prem": None, "reason": None,
        }
        book.append(pos)
        new.append(pos)
        logger.info(f"monthly_call: BUY {sym} {int(strike)}CE @ {prem:.1f} "
                    f"(spot {px:.1f}, vol {vol20:.0%}) cycle {cyc}")
    if not new:
        book.append({"id": f"CYCLE-{cyc}", "cycle": cyc, "status": "NO_CANDIDATES",
                     "entry_date": today.isoformat()})
    _save_book(book)
    _save_snapshot({"earnings_calendar_ok": cal_ok, "earnings_skipped": sorted(skip)})
    return new


# ── resolve (trigger on UNDERLYING, P&L on the CALL premium) ───────────────────
def resolve_call_positions() -> int:
    """Mark every OPEN call; the +2%/−5% TRIGGER is on the underlying (same as the backtest),
    P&L is booked on the option premium. Exit on TP/SL/expiry. Engine calls this periodically."""
    if not MONTHLY_CALL_ENABLED:
        return 0
    book = _load_book()
    today = date.today()
    closed = 0
    changed = False
    for p in book:
        if p.get("status") != "OPEN" or "symbol" not in p:
            continue
        try:
            lt = fetch_upstox_ltp(p["symbol"])
            px = float(lt["price"]) if lt.get("success") and lt.get("price") else None
            prem = _opt_mid(p["opt_key"])
            if prem is not None:
                p["cur_prem"] = round(prem, 2)
                p["pnl_pct"] = round((prem / p["entry_prem"] - 1) * 100, 2)
                changed = True
            if px is None:
                continue
            p["cur_px"] = round(px, 2)
            changed = True
            if p.get("last_mark") != today.isoformat():
                p["last_mark"] = today.isoformat()
                p["sessions"] = int(p.get("sessions", 0)) + 1
            tp_px = p["tp_late_px"] if p["sessions"] > MONTHLY_FUT_DECAY_DAY else p["tp_px"]
            # TIME GATE (added 2026-08-04). This was `today >= expiry` with no clock check, so it
            # settled from 00:00 on expiry day — hours before any price existed. Same defect class
            # that fabricated 0DTE wins in July. Now requires the derivatives close (SETTLE_AFTER).
            from engine.config import SETTLE_AFTER
            _past_settle = datetime.now(IST).strftime("%H:%M") >= SETTLE_AFTER
            _exp = date.fromisoformat(p["expiry"])
            expired = (today > _exp) or (today == _exp and _past_settle)
            reason = ("tp" if px >= tp_px else
                      "sl" if px <= p["sl_px"] else
                      "expiry" if expired else None)
            if reason:
                exit_prem = p.get("cur_prem", p["entry_prem"])
                p["status"] = "WIN" if exit_prem > p["entry_prem"] else "LOSS"
                p["closed_date"] = today.isoformat()
                p["exit_prem"] = exit_prem
                p["reason"] = reason
                closed += 1
                logger.info(f"monthly_call: closed {p['symbol']} {p['status']} "
                            f"(prem {p['pnl_pct']:+.1f}%, {reason})")
        except Exception as e:
            logger.warning(f"monthly_call resolve {p.get('symbol')}: {e}")
    if changed:
        _save_book(book)
        _save_snapshot()
    return closed


# ── UI rows ───────────────────────────────────────────────────────────────────
def call_rows_for_ui(max_closed: int = 6) -> list:
    book = _load_book()
    opens = [p for p in book if p.get("status") == "OPEN" and "symbol" in p]
    closed = sorted([p for p in book if p.get("status") in ("WIN", "LOSS")],
                    key=lambda p: p.get("closed_date") or "", reverse=True)[:max_closed]
    markers = [p for p in book if p.get("status") in ("REGIME_OFF", "NO_CANDIDATES")][-1:]
    rows = []
    for p in opens + closed:
        rows.append({
            "symbol": p["symbol"], "status": p["status"], "order_label": p["order_label"],
            "entry_date": p["entry_date"], "strike": p.get("strike"),
            "entry_prem": p.get("entry_prem"), "cur_prem": p.get("cur_prem"),
            "exit_prem": p.get("exit_prem"), "opt_expiry": p.get("opt_expiry"),
            "entry_px": p.get("entry_px"), "cur_px": p.get("cur_px"),
            "tp_px": p.get("tp_px"), "sl_px": p.get("sl_px"), "expiry": p["expiry"],
            "pnl_pct": p.get("pnl_pct"), "reason": p.get("reason"),
            "sessions": p.get("sessions", 0),
        })
    for p in markers:
        rows.append({"symbol": "—", "status": p["status"], "order_label":
                     ("NIFTY under 200DMA — standing aside this cycle" if p["status"] == "REGIME_OFF"
                      else "no eligible pullback candidates this cycle"),
                     "entry_date": p["entry_date"], "strike": None, "entry_prem": None,
                     "cur_prem": None, "exit_prem": None, "opt_expiry": None, "entry_px": None,
                     "cur_px": None, "tp_px": None, "sl_px": None, "expiry": p["cycle"],
                     "pnl_pct": None, "reason": None, "sessions": 0})
    return rows
