"""MORNING RE-CHECK — 09:30 daily. Does yesterday's stock-credit call STILL hold?

The signal fires at 15:36 on the close and the placement window shuts at 15:40. If the user did not
get the order in, the question the next morning is not "what did we say yesterday" but "does that
exact spread still clear every gate right now". This module answers that and, only when the answer
is yes, sends ONE reminder quoting the SAME strikes.

DELIBERATELY READ-ONLY. It never opens, closes, edits or re-prices a position, never touches the
trade log, and writes nothing except its own de-dup state. The paper books already hold yesterday's
fill at yesterday's price; this is a notification, not a second entry (user, 2026-08-05).

The gates re-run here are the SAME ones the scan used, on live 09:30 quotes:
  1. two-sided market on BOTH legs        (a one-sided book is not tradeable)
  2. short-leg premium >= STOCK_CREDIT_MIN_PREM
  3. short-leg bid-ask <= STOCK_CREDIT_MAX_SPREAD_PCT
  4. short-leg OI >= STOCK_CREDIT_MIN_OI
  5. credit/width still inside the BOOK'S OWN band (v2/v1 >= 0.40, v0 0.35-0.40)
  6. short strike still OTM against live spot

Gate 6 has no counterpart in the scan because the scan runs on a fresh breakout: the strike was
chosen 2 steps OTM moments earlier. Overnight is different — a gap through the short strike turns
the fade into an already-losing trade, and re-issuing that as "still fits" would be wrong.
"""
import os
import json
import html
import logging
from datetime import date, datetime, timedelta

from engine import config
from engine.config import DATA_DIR, IST

logger = logging.getLogger(__name__)

STATE_PATH = os.path.join(DATA_DIR, "recheck_notified.json")


def _v2_tp() -> float:
    """v2's take-profit lives in stock_credit_v2.py (0.50), not config — read it from the module
    that owns it rather than restating the number here. Nothing in this file is a hardcoded
    trading parameter: every threshold, time and level comes from config, the book, or a live
    quote (user standard, 2026-08-05)."""
    from engine import stock_credit_v2
    return float(stock_credit_v2.STOCK_CREDIT_TAKE_PROFIT)

# label -> (positions file, c/w band getter, take-profit getter). The TP differs per book — v2
# books at 50% of credit, v1 and v0 at 40% — so it is read per book, never inferred from the label.
BOOKS = [
    ("Stock Credit v2 UNION", "stock_credit_v2_positions.json",
     lambda: (config.STOCK_CREDIT_MIN_CW, None), lambda: _v2_tp(), "STOCK CREDIT v2 UNION"),
    ("Stock Credit v1", "stock_credit_positions.json",
     lambda: (config.STOCK_CREDIT_MIN_CW, None), lambda: config.STOCK_CREDIT_TAKE_PROFIT,
     "STOCK CREDIT v1"),
    ("Stock Credit v0", "stock_credit_v0_positions.json",
     lambda: (config.STOCK_CREDIT_V0_MIN_CW, config.STOCK_CREDIT_V0_MAX_CW),
     lambda: config.STOCK_CREDIT_V0_TAKE_PROFIT, "STOCK CREDIT v0 (c/w 0.35-0.40)"),
]


def _prev_trading_day() -> str:
    """The last session BEFORE today, holiday-aware.

    Taken from NIFTY's daily bars: a bar exists only for a day the exchange traded, so the most
    recent one dated before today IS the previous trading day. There is no hardcoded holiday
    calendar in this repo on purpose (data_utils.market_is_trading_today infers it the same way),
    and a plain weekday walk-back would call the day after a holiday 'yesterday' and re-check a
    two-day-old call. Falls back to the last weekday only if the feed is unreachable.
    """
    today = date.today()
    try:
        from engine.data_fetcher import fetch_upstox_historical
        df = fetch_upstox_historical("NIFTY", unit="days", interval=1,
                                     from_date=(today - timedelta(days=12)).isoformat(),
                                     to_date=today.isoformat())
        if df is not None and not df.empty:
            days = sorted({ix.date() for ix in df.index if ix.date() < today})
            if days:
                return days[-1].isoformat()
    except Exception as e:
        logger.warning("recheck: daily-bar lookup failed (%s) — falling back to weekday walk", e)
    d = today - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def _last_session(books: list) -> str:
    """Previous trading day, taking the LATEST of three independent witnesses.

    The daily bar alone is not safe: the Upstox feed publishes it late (at 18:15 on 4-Aug it still
    carried no 4-Aug data at all), so at 09:30 it can still be one session behind and would send us
    re-checking a two-day-old call. Two local witnesses close that gap, and both are only ever
    written on a day the engine actually ran a session:
      * the newest entry_date in any book before today — the engine opens positions on trading
        days only, so such a date IS a trading day;
      * the mtime of union_watchlist.json, rebuilt at WATCHLIST_AFTER every session, which is the
        only witness that survives a session that produced NO signal.
    Taking the max is safe in both directions: a witness can only ever be a real session, and if
    the winner turns out to have produced no call the caller sends nothing — which is the wanted
    behaviour anyway.
    """
    today = date.today().isoformat()
    cands = [_prev_trading_day()]
    entries = [p.get("entry_date") for _l, _b, _t, _e, ps in books for p in ps
               if p.get("entry_date") and p["entry_date"] < today]
    if entries:
        cands.append(max(entries))
    try:
        wl = os.path.join(DATA_DIR, "union_watchlist.json")
        if os.path.exists(wl):
            built = date.fromtimestamp(os.path.getmtime(wl)).isoformat()
            if built < today:
                cands.append(built)
    except Exception:
        pass
    return max(cands)


def _check(p: dict, lo: float, hi):
    """Re-run every gate on live quotes. Returns (ok, detail-dict, reason-if-failed)."""
    from engine.stock_credit_v2 import _quote, _spot
    sm, sb, sa, soi = _quote(p["short_key"])
    lm, lb, la, _ = _quote(p["long_key"])
    if sm is None or lm is None:
        return False, {}, "no quote"
    if not (sb > 0 and sa > 0 and lb > 0 and la > 0):
        return False, {}, "one-sided market"
    credit = sm - lm
    width = p["width_pts"]
    if credit <= 0 or credit >= width:
        return False, {}, "credit outside width"
    cw = credit / width
    spread_pct = (sa - sb) / sm * 100 if sm else 99.0
    spot = _spot(p["symbol"])
    d = {"credit": round(credit, 2), "cw": round(cw, 3), "spread": round(spread_pct, 1),
         "oi": soi, "short_prem": round(sm, 2), "spot": spot}
    if sm < config.STOCK_CREDIT_MIN_PREM:
        return False, d, f"short premium ₹{sm:.0f} < ₹{config.STOCK_CREDIT_MIN_PREM:.0f}"
    if spread_pct > config.STOCK_CREDIT_MAX_SPREAD_PCT:
        return False, d, f"bid-ask {spread_pct:.1f}% > {config.STOCK_CREDIT_MAX_SPREAD_PCT:.0f}%"
    if soi < config.STOCK_CREDIT_MIN_OI:
        return False, d, f"no open interest (OI {soi})"
    if cw < lo or (hi is not None and cw >= hi):
        band = f"{lo:.2f}-{hi:.2f}" if hi is not None else f"≥{lo:.2f}"
        return False, d, f"c/w {cw:.2f} outside {band}"
    # INTRINSIC vs TIME VALUE. The c/w gate is a proxy for elevated post-breakout IV, and that is
    # only what it measures while the short strike is OTM. Once spot trades through the strike the
    # extra credit is INTRINSIC — money paid for a move that has already gone against the fade —
    # and c/w climbs toward 1.0 with no edge in it at all. So the message must never quote a rising
    # c/w without also quoting the time value, which is the part the edge actually lives in.
    # (GRASIM, 5-Aug-2026: c/w 0.41 -> 0.486 while time value fell Rs24.85 -> Rs12.58.)
    if spot:
        if p["side"] == "BEAR_CALL":
            intr = max(0.0, spot - p["short_strike"]) - max(0.0, spot - p["long_strike"])
        else:
            intr = max(0.0, p["short_strike"] - spot) - max(0.0, p["long_strike"] - spot)
        intr = max(0.0, intr)
        d["intrinsic"] = round(intr, 2)
        d["time_value"] = round(credit - intr, 2)
        # at entry the strike was OTM by construction, so the entry credit was ALL time value
        d["entry_tv"] = p.get("credit")
        otm = (spot < p["short_strike"]) if p["side"] == "BEAR_CALL" else (spot > p["short_strike"])
        if not otm:
            thru = abs(spot - p["short_strike"])
            why = (f"spot {spot:,.2f} is ₹{thru:,.2f} THROUGH the short strike "
                   f"{p['short_strike']:,.0f}. The higher c/w ({cw:.3f} vs "
                   f"{p.get('credit_width')} at entry) is INTRINSIC, not vol — time value has "
                   f"fallen from ₹{d['entry_tv']} to ₹{d['time_value']}")
            return False, d, why
    ok_why = "every gate still passes on the same strikes"
    if spot:
        side_word = "below" if p["side"] == "BEAR_CALL" else "above"
        ok_why += (f" — spot {spot:,.2f} still {side_word} the short strike "
                   f"{p['short_strike']:,.0f}, so the credit is still time value "
                   f"(₹{d.get('time_value', credit):,.2f} of ₹{credit:,.2f})")
    return True, d, ok_why


def build_message():
    """(text, n_still_valid, dropped) — text is '' when nothing from the last session survives."""
    books = []
    for label, fname, band, tp, eng in BOOKS:
        path = os.path.join(DATA_DIR, fname)
        if not os.path.exists(path):
            continue
        try:
            books.append((label, band, tp, eng, json.load(open(path)) or []))
        except Exception:
            continue
    if not books:
        return "", 0, []
    # ONLY the last trading day counts (user, 2026-08-06). Taking "the most recent entry_date in
    # the book" instead would reach back days: if yesterday produced nothing, it would surface a
    # call from three sessions ago as though it were fresh. No signal that session -> no message.
    day = _last_session(books)

    ok_rows, bad_rows = [], []
    for label, band, tp_get, eng, ps in books:
        lo, hi = band()
        for p in ps:
            if p.get("entry_date") != day or p.get("status") != "OPEN":
                continue
            good, d, why = _check(p, lo, hi)
            (ok_rows if good else bad_rows).append((label, p, d, why, tp_get, eng))
    if not ok_rows and not bad_rows:
        logger.info("recheck: no stock-credit signal on %s (last trading day) — no message", day)
        return "", 0, []

    # the SCHEDULED hour, not the wall clock — a manual run must still read 09:30
    stamp = getattr(config, "SIGNAL_RECHECK_AT", "09:30")
    fmt_d = lambda s: datetime.strptime(s, "%Y-%m-%d").strftime("%d-%b-%Y") if s else "?"
    g = lambda x: ("%g" % x) if isinstance(x, (int, float)) else "?"

    def _head(label, p):
        sym = html.escape(str(p.get("symbol") or ""))
        raw = str(p.get("side") or "")
        side = ("BEAR CALL SPREAD" if raw == "BEAR_CALL"
                else "BULL PUT SPREAD" if raw == "BULL_PUT" else raw)
        verb = "CE" if "CALL" in raw else ("PE" if "PUT" in raw else "")
        return (f"<b>{sym} · {side}</b> ({label})",
                f"SELL {g(p.get('short_strike'))} {verb}  /  BUY {g(p.get('long_strike'))} {verb}"
                f" · expiry {fmt_d(p.get('expiry'))} · lot {p.get('lot') or 0}")

    n = len(ok_rows) + len(bad_rows)
    lines = [
        "🌅 <b>GOOD MORNING</b>",
        f"In case you are buying yesterday's calls — here is where "
        f"{'they stand' if n != 1 else 'it stands'} on a live re-check at <b>{stamp}</b>, "
        f"on the SAME strikes as the {fmt_d(day)} signal.",
        "",
    ]
    # ONE template for every row (user, 2026-08-05). The five lines are identical whichever way
    # the re-check lands; only the VERDICT line and the "Reason:" text change, and both of those
    # come straight from the scan output. Do-not-buys list first so they are read first.
    def _row(verdict, label, p, d, why, tp_get=None):
        h1, h2 = _head(label, p)
        out = [f"{verdict} — {h1}", h2, f"<b>Reason: {html.escape(why)}.</b>"]
        # The "Now:", "Of that credit:" and "Yesterday it was" lines were dropped (user,
        # 2026-08-05) — every number that mattered is already in the Reason line above, so they
        # only repeated it.
        if tp_get:
            w, lot = p.get("width_pts") or 0, p.get("lot") or 0
            if isinstance(w, (int, float)) and lot:
                tp = tp_get()
                out.append(f"🎯 Target: book {tp*100:.0f}% of credit ≈ +₹{tp*d['credit']*lot:,.0f}/lot"
                           f" · Max profit/lot ₹{d['credit']*lot:,.0f}"
                           f" · Max loss/lot ₹{(w-d['credit'])*lot:,.0f}")
        out.append("")
        return out

    for label, p, d, why, _tp, _e in bad_rows:
        lines += _row("⛔ <b>PLEASE DO NOT BUY TODAY</b>", label, p, d, why)
    for label, p, d, why, tp_get, _e in ok_rows:
        lines += _row("✅ <b>YOU CAN BUY TODAY</b>", label, p, d, why, tp_get)
    # Only the standing disclaimer closes this message (user, 2026-08-05). The "Reminder only"
    # note and the "Why this signal" evidence block were dropped as noise — this is a re-check of a
    # call already sent, not a new signal, so the evidence was a repeat of yesterday's message.
    from engine.engine_runner import EngineRunner as _ER
    lines.append(_ER._TG_DISCLAIMER)
    return "\n".join(lines), len(ok_rows), bad_rows


def run(send: bool = True) -> str:
    """Build and (optionally) send. De-duped per signal-date so a restart cannot re-send.

    THE DE-DUPE CHECK COMES FIRST (audit 17-Aug-2026). It used to run AFTER build_message(), which
    re-priced every position from the last session on every engine cycle — every five seconds from
    09:30 to 15:40. With five positions that is roughly 66,000 needless Upstox calls a day, and it
    was the proximate cause of the rate exhaustion that took the feed down at 15:15 on 17-Aug and
    made the engine mistake a network failure for an exchange holiday. Nothing is fetched now until
    we know the message has not already gone out.
    """
    if send:
        try:
            _seen = set(json.load(open(STATE_PATH))) if os.path.exists(STATE_PATH) else set()
        except Exception:
            _seen = set()
        if date.today().isoformat() in _seen:
            return ""                      # already sent today — do not price anything
    text, n, dropped = build_message()
    if not text:
        logger.info("signal_recheck: nothing from the last session still passes "
                    "(%d dropped)", len(dropped))
        return ""
    if send:
        try:
            seen = set(json.load(open(STATE_PATH))) if os.path.exists(STATE_PATH) else set()
        except Exception:
            seen = set()
        key = date.today().isoformat()
        if key in seen:
            logger.info("signal_recheck: already sent today")
            return ""
        from engine.notifications import send_telegram
        if send_telegram(text):
            seen.add(key)
            tmp = STATE_PATH + ".tmp"
            with open(tmp, "w") as f:
                json.dump(sorted(seen), f)
            os.replace(tmp, STATE_PATH)
            logger.info("signal_recheck: reminded on %d still-valid call(s)", n)
    return text


if __name__ == "__main__":
    import sys
    print(run(send="--send" in sys.argv) or "(nothing still passes — no message)")
