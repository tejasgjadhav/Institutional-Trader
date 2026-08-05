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
from datetime import date, datetime

from engine import config
from engine.config import DATA_DIR, IST

logger = logging.getLogger(__name__)

STATE_PATH = os.path.join(DATA_DIR, "recheck_notified.json")

# label -> (positions file, c/w band getter, take-profit getter). The TP differs per book — v2
# books at 50% of credit, v1 and v0 at 40% — so it is read per book, never inferred from the label.
BOOKS = [
    ("Stock Credit v2 UNION", "stock_credit_v2_positions.json",
     lambda: (config.STOCK_CREDIT_MIN_CW, None), lambda: 0.50),
    ("Stock Credit v1", "stock_credit_positions.json",
     lambda: (config.STOCK_CREDIT_MIN_CW, None), lambda: config.STOCK_CREDIT_TAKE_PROFIT),
    ("Stock Credit v0", "stock_credit_v0_positions.json",
     lambda: (config.STOCK_CREDIT_V0_MIN_CW, config.STOCK_CREDIT_V0_MAX_CW),
     lambda: config.STOCK_CREDIT_V0_TAKE_PROFIT),
]


def _prev_entry_date(books: list) -> str:
    """The most recent entry_date across the three books that is BEFORE today — i.e. the last
    session that actually produced a call. Using 'yesterday' literally would miss Monday, when
    yesterday is Sunday."""
    today = date.today().isoformat()
    dates = [p.get("entry_date") for _lbl, _f, ps in books for p in ps
             if p.get("entry_date") and p["entry_date"] < today]
    return max(dates) if dates else ""


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
        return False, d, f"OI {soi} < {config.STOCK_CREDIT_MIN_OI}"
    if cw < lo or (hi is not None and cw >= hi):
        band = f"{lo:.2f}-{hi:.2f}" if hi is not None else f"≥{lo:.2f}"
        return False, d, f"c/w {cw:.2f} outside {band}"
    if spot:
        otm = (spot < p["short_strike"]) if p["side"] == "BEAR_CALL" else (spot > p["short_strike"])
        if not otm:
            return False, d, f"spot {spot:,.0f} through the short strike {p['short_strike']:,.0f}"
    return True, d, ""


def build_message():
    """(text, n_still_valid, dropped) — text is '' when nothing from the last session survives."""
    books = []
    for label, fname, band, tp in BOOKS:
        path = os.path.join(DATA_DIR, fname)
        if not os.path.exists(path):
            continue
        try:
            books.append((label, band, tp, json.load(open(path)) or []))
        except Exception:
            continue
    if not books:
        return "", 0, []
    day = _prev_entry_date([(l, None, ps) for l, _b, _t, ps in books])
    if not day:
        return "", 0, []

    ok_rows, bad_rows = [], []
    for label, band, tp_get, ps in books:
        lo, hi = band()
        for p in ps:
            if p.get("entry_date") != day or p.get("status") != "OPEN":
                continue
            good, d, why = _check(p, lo, hi)
            (ok_rows if good else bad_rows).append((label, p, d, why, tp_get))
    if not ok_rows and not bad_rows:
        return "", 0, []

    stamp = datetime.now(IST).strftime("%H:%M")
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
    # ---- the ones you should NOT buy today, and why ----
    for label, p, d, why, _tp in bad_rows:
        h1, h2 = _head(label, p)
        lines += [f"⛔ <b>PLEASE DO NOT BUY TODAY</b> — {h1}", h2,
                  f"<b>Reason: {html.escape(why)}.</b>"]
        if d.get("cw") is not None:
            lines.append(f"Now: credit ₹{d['credit']} (c/w {d['cw']}) · premium ₹{d['short_prem']:.0f}"
                         f" · bid-ask {d['spread']}% · OI {int(d['oi']):,}"
                         + (f" · spot {d['spot']:,.0f}" if d.get("spot") else ""))
        lines.append(f"<i>Yesterday it was credit ₹{p.get('credit')} (c/w {p.get('credit_width')}) — "
                     f"that entry no longer exists at these levels.</i>")
        lines.append("")
    # ---- the ones that still fit ----
    for label, p, d, _why, tp_get in ok_rows:
        h1, h2 = _head(label, p)
        w = p.get("width_pts") or 0
        lot = p.get("lot") or 0
        lines += [f"✅ <b>STILL FITS — you can go ahead</b> — {h1}", h2,
                  f"Credit yesterday ₹{p.get('credit')} (c/w {p.get('credit_width')}) · "
                  f"now ₹{d['credit']} (c/w {d['cw']})",
                  f"Every gate passes: premium ₹{d['short_prem']:.0f} · bid-ask {d['spread']}% · "
                  f"OI {int(d['oi']):,}"
                  + (f" · spot {d['spot']:,.0f}, short strike still OTM" if d.get("spot") else "")]
        if isinstance(w, (int, float)) and lot:
            tp = tp_get()
            lines += [f"🎯 Target: book {tp*100:.0f}% of credit ≈ +₹{tp*d['credit']*lot:,.0f}/lot",
                      f"Max profit/lot ₹{d['credit']*lot:,.0f} · "
                      f"Max loss/lot ₹{(w-d['credit'])*lot:,.0f}"]
        lines.append("")
    lines += [
        "<i>Reminder only. The paper book already holds yesterday's fill at yesterday's price — "
        "nothing here is written to the trade log or any book, and the tracked result will follow "
        "the original signal either way.</i>",
        "⚠️ Tejas Jadhav is NOT a SEBI-registered research analyst/investment advisor. "
        "Educational signals · invest at your own risk · consult a SEBI-registered advisor.",
    ]
    return "\n".join(lines), len(ok_rows), bad_rows


def run(send: bool = True) -> str:
    """Build and (optionally) send. De-duped per signal-date so a restart cannot re-send."""
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
