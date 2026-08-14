"""A worked example: a VWAP pullback on a stock, bought as a call.

READ THIS FIRST.

This is a teaching example. It exists so you can watch the machine work from end to end:
a screen runs, a signal appears, an option is chosen, a paper fill is written, the position
is marked to market, and a row lands on the dashboard. That is its whole purpose.

The author does not trade this. It is not his strategy and it is not derived from his
strategy. It has not been backtested on real data. It has not been validated out of sample.
It has no measured win rate, no measured expectancy and no evidence behind it at all. Every
number in its config block was chosen to be readable, not because a test said so.

It is also a well-known setup that many people have tested and most have abandoned. Buying a
short-dated option on an intraday pullback pays theta and spread on every trade. Assume it
loses money until your own test says otherwise.

DEPLOY AT YOUR OWN RISK. It is off by default. If you set EXAMPLE_VWAP_ENABLED to True, run
it, or act on anything it prints, that is your decision and your risk alone. Tejas Jadhav
accepts no responsibility and no liability for any trade you place or any loss you suffer.
This is study code, not investment advice and not a signal service. See DISCLAIMER.md.

THE RULE, IN PLAIN WORDS.

1. Take 5-minute bars of the stock from today's open.
2. Work out VWAP, the volume-weighted average price so far today. VWAP needs traded volume,
   which is why this runs on a stock. A spot index has no volume and no VWAP.
3. Wait for the stock to trade below VWAP by more than EXAMPLE_VWAP_STRETCH percent.
4. Wait for it to turn back up. A turn is EXAMPLE_VWAP_TURN_BARS bars closing higher than
   the one before.
5. Buy one at-the-money call on that stock.
6. Exit at EXAMPLE_VWAP_TARGET_PCT profit on the premium, EXAMPLE_VWAP_STOP_PCT loss on the
   premium, or at EXAMPLE_VWAP_EXIT_AT, whichever comes first.
7. One trade a day at most, and only between EXAMPLE_VWAP_ENTRY_FROM and
   EXAMPLE_VWAP_ENTRY_TO.

That is all of it. Read it, argue with it, test it, and then write something better.

studies/VWAP_EXAMPLE_STRATEGY.md sets out how to test it, and why you should expect it to lose
before you start. The results table in that note is blank because nobody has run it.
"""
import json
import os
import logging
from datetime import datetime, date

from engine import config
from engine.config import IST, DATA_DIR
from engine.data_fetcher import fetch_intraday_5min, get_cached_ltp
from engine.indicators import vwap
from engine.options import get_atm_option, check_option_liquidity
from engine import reader_edition as _reader

log = logging.getLogger(__name__)

BOOK_NAME = "Example VWAP pullback (teaching example, untested)"
BOOK_PATH = os.path.join(DATA_DIR, "example_vwap_positions.json")
SNAP_PATH = os.path.join(DATA_DIR, "example_vwap.json")


# ── the book on disk ────────────────────────────────────────────────────────────────

def _load() -> list:
    try:
        with open(BOOK_PATH) as fh:
            return json.load(fh)
    except Exception:
        return []


def _save(rows: list):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = BOOK_PATH + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(rows, fh, indent=2, default=str)
    os.replace(tmp, BOOK_PATH)


def _write_snapshot(state: str, detail: str = ""):
    """One line for the dashboard, so a quiet day says why it was quiet."""
    os.makedirs(DATA_DIR, exist_ok=True)
    payload = {"book": BOOK_NAME, "state": state, "detail": detail,
               "at": datetime.now(IST).isoformat()}
    try:
        with open(SNAP_PATH, "w") as fh:
            json.dump(payload, fh, indent=2)
    except Exception as e:
        log.warning("example_vwap snapshot: %s", e)


def _in_window(now: datetime) -> bool:
    mins = now.hour * 60 + now.minute
    h1, m1 = map(int, config.EXAMPLE_VWAP_ENTRY_FROM.split(":"))
    h2, m2 = map(int, config.EXAMPLE_VWAP_ENTRY_TO.split(":"))
    return (h1 * 60 + m1) <= mins <= (h2 * 60 + m2)


# ── the screen ──────────────────────────────────────────────────────────────────────

def _signal_now(symbol: str):
    """Return a dict describing the setup if it is present right now, else None."""
    bars = fetch_intraday_5min(symbol, days=1)
    if bars is None or len(bars) < 4:
        return None
    if float(bars["Volume"].sum()) <= 0:
        return None          # no volume means no VWAP. Point this at something that trades.
    v = vwap(bars)
    last_close = float(bars["Close"].iloc[-1])
    last_vwap = v.iloc[-1]
    if last_vwap != last_vwap:          # NaN, no volume yet
        return None
    stretch_pct = (last_vwap - last_close) / last_vwap * 100.0
    if stretch_pct < config.EXAMPLE_VWAP_STRETCH:
        return None
    n = int(config.EXAMPLE_VWAP_TURN_BARS)
    closes = bars["Close"].tail(n + 1).tolist()
    turned = all(closes[i + 1] > closes[i] for i in range(n))
    if not turned:
        return None
    return {"spot": last_close, "vwap": float(last_vwap), "stretch_pct": round(stretch_pct, 3)}


def scan_signals() -> list:
    """Run the screen once. Returns the positions opened, which is zero or one."""
    if not getattr(config, "EXAMPLE_VWAP_ENABLED", False):
        return []
    now = datetime.now(IST)
    if not _in_window(now):
        _write_snapshot("NO SIGNAL", "outside the entry window")
        return []

    rows = _load()
    today = str(now.date())
    todays = [r for r in rows if str(r.get("entry_date")) == today]
    if len(todays) >= int(config.EXAMPLE_VWAP_MAX_PER_DAY):
        _write_snapshot("NO SIGNAL", "already traded today")
        return []

    symbol = config.EXAMPLE_VWAP_SYMBOL
    sig = _signal_now(symbol)
    if not sig:
        _write_snapshot("NO SIGNAL",
                        "not stretched below VWAP, or it has not turned up yet")
        return []

    spot = sig["spot"]
    opt = get_atm_option(symbol, spot, now.date(), "CE")
    if not opt:
        _write_snapshot("NO SIGNAL", "no at-the-money call resolved")
        return []
    ok, why = check_option_liquidity(symbol, spot, "LONG")
    if not ok:
        _write_snapshot("NO SIGNAL", f"option too illiquid to price: {why}")
        return []

    premium = get_cached_ltp(opt["instrument_key"])
    if not premium:
        _write_snapshot("NO SIGNAL", "no premium quote")
        return []

    pos = {
        "book": "example_vwap",
        "entry_date": today,
        "entry_time": now.strftime("%H:%M:%S"),
        "symbol_underlying": symbol,
        "instrument_key": opt["instrument_key"],
        "symbol": opt.get("symbol") or opt.get("tradingsymbol"),
        "strike": opt.get("strike"),
        "expiry": str(opt.get("expiry")),
        "lots": int(config.EXAMPLE_VWAP_LOTS),
        "entry_premium": float(premium),
        "entry_spot": spot,
        "vwap_at_entry": sig["vwap"],
        "stretch_pct": sig["stretch_pct"],
        "outcome": None,
        "exit_premium": None,
        "exit_reason": None,
    }
    rows.append(pos)
    _save(rows)
    _write_snapshot("SIGNAL", f"bought {pos['symbol']} at {premium}")
    log.info("example_vwap: opened %s at %s", pos["symbol"], premium)
    return [pos]


# ── marking and closing ─────────────────────────────────────────────────────────────

def resolve_positions() -> int:
    """Mark open positions and close them on target, stop or the exit time."""
    if not getattr(config, "EXAMPLE_VWAP_ENABLED", False):
        return 0
    rows = _load()
    open_rows = [r for r in rows if r.get("outcome") is None]
    if not open_rows:
        return 0

    now = datetime.now(IST)
    mins = now.hour * 60 + now.minute
    eh, em = map(int, config.EXAMPLE_VWAP_EXIT_AT.split(":"))
    past_exit = mins >= (eh * 60 + em)
    tgt = float(config.EXAMPLE_VWAP_TARGET_PCT)
    stp = float(config.EXAMPLE_VWAP_STOP_PCT)

    closed = 0
    for r in open_rows:
        price = get_cached_ltp(r["instrument_key"])
        if not price:
            continue
        entry = float(r["entry_premium"])
        move_pct = (price - entry) / entry * 100.0 if entry else 0.0
        r["last_premium"] = float(price)
        r["mtm_pct"] = round(move_pct, 2)

        reason = None
        if move_pct >= tgt:
            reason = "target"
        elif move_pct <= -stp:
            reason = "stop"
        elif past_exit:
            reason = "time"
        if not reason:
            continue

        r["outcome"] = "WIN" if move_pct > 0 else "LOSS"
        r["exit_premium"] = float(price)
        r["exit_reason"] = reason
        r["exit_time"] = now.strftime("%H:%M:%S")
        r["pnl_pct"] = round(move_pct, 2)
        closed += 1
        log.info("example_vwap: closed %s on %s at %s (%.1f%%)",
                 r["symbol"], reason, price, move_pct)

    _save(rows)
    return closed


def write_status():
    """Called before the entry window so the dashboard can say what it is waiting for."""
    if not getattr(config, "EXAMPLE_VWAP_ENABLED", False):
        _write_snapshot("OFF", "the example book is switched off in engine/config.py")
        return
    try:
        sig = _signal_now(config.EXAMPLE_VWAP_SYMBOL)
        if sig:
            _write_snapshot("ARMED", f"stretched {sig['stretch_pct']}% below VWAP")
        else:
            _write_snapshot("WAITING", "at or above VWAP, or no volume in the series yet")
    except Exception as e:
        _write_snapshot("WAITING", f"no data yet: {e}")
