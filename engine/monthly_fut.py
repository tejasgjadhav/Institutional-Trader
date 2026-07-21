"""
MONTHLY FUTURES PULLBACK (REV1-v2) — signals-only paper forward-test. The 5th strategy.

The one OOS survivor of the 2026-07 monthly-futures study (studies/monthly_fut/):
at each expiry-to-expiry cycle start, if NIFTY > its 200DMA, take the 8 worst 1-month
losers among universe stocks still above their OWN 200DMA, keep the 5 with the highest
20-day vol, BUY the front-month future (1 lot each). Exit MOC when the close crosses
TP +2% (decaying to +1% after 12 sessions) or SL -5%; else hold to expiry settle.
Backtest (real bhavcopy futures 2018→2026): 75.1% win IS / 75.7% OOS, ~3.9%/mo on
margin capital, worst month ~-20%. See studies/monthly_fut/MONTHLY_FUTURES.md.

EARNINGS-SKIP (live-only rule, untested historically): candidates with a results /
board-meeting date before the cycle expiry are skipped at selection — half of the OOS
losses were single-day news shocks with no technical signature at entry. Fails OPEN
(no calendar -> no skipping) and the snapshot flags whether the calendar loaded.

Signals-only: tracks entries/exits on the UNDERLYING's daily closes (futures P&L ≈
spot + carry; the study measured real futures). The engine never places orders.
State: data/monthly_fut_positions.json (book) + data/monthly_fut.json (UI snapshot).
"""
import os
import json
import logging
import calendar
from datetime import datetime, date, timedelta

import requests

from engine.config import (
    IST, DATA_DIR, UNIVERSE,
    MONTHLY_FUT_ENABLED, MONTHLY_FUT_POOL, MONTHLY_FUT_TOPN, MONTHLY_FUT_TP,
    MONTHLY_FUT_TP_LATE, MONTHLY_FUT_DECAY_DAY, MONTHLY_FUT_SL, MONTHLY_FUT_MIN_DTE,
    MONTHLY_FUT_EARNINGS_SKIP,
)
from engine.data_fetcher import fetch_upstox_historical, fetch_upstox_ltp

logger = logging.getLogger(__name__)

BOOK_PATH = os.path.join(DATA_DIR, "monthly_fut_positions.json")
SNAP_PATH = os.path.join(DATA_DIR, "monthly_fut.json")

IDX_SYMBOLS = ("NIFTY", "BANKNIFTY", "FINNIFTY")


# ── persistence (same pattern as swing_credit) ────────────────────────────────
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
        logger.warning(f"monthly_fut book save: {e}")


def _save_snapshot(extra: dict = None) -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        snap = {"ts": datetime.now(IST).isoformat(), "rows": monthly_rows_for_ui()}
        if extra:
            snap.update(extra)
        tmp = SNAP_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(snap, f, default=str)
        os.replace(tmp, SNAP_PATH)
    except Exception as e:
        logger.warning(f"monthly_fut snapshot: {e}")


# ── cycle calendar ────────────────────────────────────────────────────────────
def _last_thursday(year: int, month: int) -> date:
    d = date(year, month, calendar.monthrange(year, month)[1])
    while d.weekday() != 3:      # Thursday
        d -= timedelta(days=1)
    return d


def _cycle_expiry(today: date) -> date:
    """The front monthly expiry (last Thursday of this month, else next month's)."""
    e = _last_thursday(today.year, today.month)
    if today <= e:
        return e
    y, m = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    return _last_thursday(y, m)


# ── data ──────────────────────────────────────────────────────────────────────
def _closes(symbol: str):
    """Daily Close series for the last ~420 calendar days (needs ≥150 rows for the 200DMA)."""
    start = (date.today() - timedelta(days=420)).isoformat()
    df = fetch_upstox_historical(symbol, unit="days", interval=1,
                                 from_date=start, to_date=date.today().isoformat())
    if df is None or df.empty or len(df) < 150:
        return None
    return df.sort_index()["Close"]


def _earnings_skip_set(expiry: date):
    """Symbols with a results/board-meeting date on or before the cycle expiry, from NSE's
    public event calendar. FAILS OPEN: any error -> empty set (skip nothing) + flag False."""
    if not MONTHLY_FUT_EARNINGS_SKIP:
        return set(), True
    try:
        hdr = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
               "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
        s = requests.Session(); s.headers.update(hdr)
        s.get("https://www.nseindia.com", timeout=10)
        r = s.get("https://www.nseindia.com/api/event-calendar?index=equities", timeout=15)
        events = r.json() if r.status_code == 200 else []
        uni = {u.replace(".NS", "") for u in UNIVERSE}
        skip = set()
        for ev in events or []:
            sym = (ev.get("symbol") or "").strip()
            if sym not in uni:
                continue
            try:
                d = datetime.strptime((ev.get("date") or "")[:11].strip(), "%d-%b-%Y").date()
            except Exception:
                continue
            if d <= expiry:
                skip.add(sym)
        return skip, True
    except Exception as e:
        logger.warning(f"monthly_fut earnings calendar: {e} (failing open — no skips)")
        return set(), False


# ── scan (once per cycle, near the close of an early-cycle day) ───────────────
def scan_monthly_signals() -> list:
    """Enter the cycle's 5 pullback longs at ~the close of the first trading day after the
    prior monthly expiry (engine calls this daily after 15:10; guards make it fire once)."""
    if not MONTHLY_FUT_ENABLED:
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
        return []                     # too deep into the cycle — late entries tested weak
    book = _load_book()
    if any(p.get("cycle") == cyc for p in book):
        return []                     # already entered (or regime-skipped) this cycle
    # regime gate: NIFTY above its 200DMA
    nifty = _closes("NIFTY")
    if nifty is None:
        logger.warning("monthly_fut: no NIFTY history — skipping scan today")
        return []
    if float(nifty.iloc[-1]) <= float(nifty.rolling(200, min_periods=150).mean().iloc[-1]):
        book.append({"id": f"CYCLE-{cyc}", "cycle": cyc, "status": "REGIME_OFF",
                     "entry_date": today.isoformat()})
        _save_book(book); _save_snapshot()
        logger.info(f"monthly_fut: NIFTY under 200DMA — standing aside for cycle {cyc}")
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
            logger.debug(f"monthly_fut cand {sym}: {e}")
    cand.sort(key=lambda t: t[1])                       # worst 1-month losers first
    pool = cand[:MONTHLY_FUT_POOL]
    pool.sort(key=lambda t: -t[2])                      # highest 20d vol first
    picks = pool[:MONTHLY_FUT_TOPN]
    new = []
    mon = expiry.strftime("%b").upper()
    for sym, mom1, vol20, px in picks:
        pos = {
            "id": f"{sym}-{cyc}", "symbol": sym, "cycle": cyc, "expiry": cyc,
            "entry_date": today.isoformat(), "entry_px": round(px, 2),
            "tp_px": round(px * (1 + MONTHLY_FUT_TP), 2),
            "tp_late_px": round(px * (1 + MONTHLY_FUT_TP_LATE), 2),
            "sl_px": round(px * (1 - MONTHLY_FUT_SL), 2),
            "sessions": 0, "last_mark": today.isoformat(),
            "mom1": round(mom1, 4), "vol20": round(vol20, 3),
            "cur_px": round(px, 2), "pnl_pct": 0.0,
            "order_label": (f"BUY {sym} {mon} FUT (1 lot, monthly pullback) — "
                            f"TP {round(px*(1+MONTHLY_FUT_TP),1)} / SL {round(px*(1-MONTHLY_FUT_SL),1)} on close"),
            "status": "OPEN", "closed_date": None, "exit_px": None, "reason": None,
        }
        book.append(pos)
        new.append(pos)
        logger.info(f"monthly_fut: LONG {sym} @ {px:.1f} (mom1 {mom1:+.1%}, vol {vol20:.0%}) cycle {cyc}")
    if not picks:
        book.append({"id": f"CYCLE-{cyc}", "cycle": cyc, "status": "NO_CANDIDATES",
                     "entry_date": today.isoformat()})
    _save_book(book)
    _save_snapshot({"earnings_calendar_ok": cal_ok, "earnings_skipped": sorted(skip)})
    return new


# ── resolve (daily closes; MOC-style like the backtest) ──────────────────────
def resolve_monthly_positions() -> int:
    """Mark every OPEN position; close on TP/SL cross of the (near-close) price or at expiry.
    The engine calls this every MONTHLY_FUT_RESOLVE_INTERVAL; exits mirror the backtest's
    close-based rule when run near 15:25."""
    if not MONTHLY_FUT_ENABLED:
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
            px = lt.get("price") if lt.get("success") else None
            if not px:
                continue
            px = float(px)
            p["cur_px"] = round(px, 2)
            p["pnl_pct"] = round((px / p["entry_px"] - 1) * 100, 2)
            changed = True
            if p.get("last_mark") != today.isoformat():
                p["last_mark"] = today.isoformat()
                p["sessions"] = int(p.get("sessions", 0)) + 1
            tp_px = p["tp_late_px"] if p["sessions"] > MONTHLY_FUT_DECAY_DAY else p["tp_px"]
            # settle at EXPIRY only after the session closes (MOC-style, per this book's own rule),
            # never at 00:00 on expiry day — same guard applied to the other resolvers 2026-07-21.
            from engine.config import IST
            _past_settle = datetime.now(IST).strftime("%H:%M") >= "15:25"
            expired = (today > date.fromisoformat(p["expiry"])) or \
                      (today == date.fromisoformat(p["expiry"]) and _past_settle)
            reason = ("tp" if px >= tp_px else
                      "sl" if px <= p["sl_px"] else
                      "expiry" if expired else None)
            if reason:
                p["status"] = "WIN" if px > p["entry_px"] else "LOSS"
                p["closed_date"] = today.isoformat()
                p["exit_px"] = round(px, 2)
                p["reason"] = reason
                closed += 1
                logger.info(f"monthly_fut: closed {p['symbol']} {p['status']} "
                            f"({p['pnl_pct']:+.2f}%, {reason})")
        except Exception as e:
            logger.warning(f"monthly_fut resolve {p.get('symbol')}: {e}")
    if changed:
        _save_book(book)
        _save_snapshot()
    return closed


# ── UI rows ───────────────────────────────────────────────────────────────────
def monthly_rows_for_ui(max_closed: int = 6) -> list:
    book = _load_book()
    opens = [p for p in book if p.get("status") == "OPEN" and "symbol" in p]
    closed = sorted([p for p in book if p.get("status") in ("WIN", "LOSS")],
                    key=lambda p: p.get("closed_date") or "", reverse=True)[:max_closed]
    markers = [p for p in book if p.get("status") in ("REGIME_OFF", "NO_CANDIDATES")][-1:]
    rows = []
    for p in opens + closed:
        rows.append({
            "symbol": p["symbol"], "status": p["status"], "order_label": p["order_label"],
            "entry_date": p["entry_date"], "entry_px": p["entry_px"], "cur_px": p.get("cur_px"),
            "tp_px": p["tp_px"], "sl_px": p["sl_px"], "expiry": p["expiry"],
            "pnl_pct": p.get("pnl_pct"), "reason": p.get("reason"),
            "sessions": p.get("sessions", 0),
        })
    for p in markers:
        rows.append({"symbol": "—", "status": p["status"], "order_label":
                     ("NIFTY under 200DMA — standing aside this cycle" if p["status"] == "REGIME_OFF"
                      else "no eligible pullback candidates this cycle"),
                     "entry_date": p["entry_date"], "entry_px": None, "cur_px": None,
                     "tp_px": None, "sl_px": None, "expiry": p["cycle"], "pnl_pct": None,
                     "reason": None, "sessions": 0})
    return rows
