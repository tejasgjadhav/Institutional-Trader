"""T-1 EVE book (17-Sep-2026): sell the index bear call at the close of the session BEFORE expiry.

studies/T1_CLOSE_ENTRY.md is the evidence. Same structure as the deployed 0DTE books (SELL a CE
~0.5% OTM / BUY a CE further out), entered one session EARLIER so it collects the overnight gap and
the whole expiry day. BEAR CALL only - the study found the put side negative everywhere, which makes
this a short-delta bet dressed as a credit spread. That is why it is ADVISORY: every fill carries
advisory=True, lands on its own forward-record line, and never touches the headline P&L.

Reuses engine/dte_multi.py's data helpers (chain, spot, quote, expiry close, json I/O) so there is
one copy of that logic. Positions: data/t1_eve_positions.json.
"""
import os
import logging
from datetime import date, datetime, timedelta

from engine import config
from engine.config import DATA_DIR, IST, ZERO_DTE_MULTI_MIN_CW
from engine import dte_multi as D
from engine.instruments import to_instrument_key

logger = logging.getLogger(__name__)
BOOK_PATH = os.path.join(DATA_DIR, "t1_eve_positions.json")

BOOKS = [
    dict(name="SENSEX", src="BSE", spot_key="BSE_INDEX|SENSEX"),
    dict(name="BANKNIFTY", src="NSE", spot_key="NSE_INDEX|Nifty Bank"),   # audit: None never settled
]
BOOKS = [b for b in BOOKS if b["name"] in getattr(config, "T1_EVE_BOOKS", ())]


def _expiries(bk):
    if bk["src"] == "BSE":
        rows = D._bse_sensex_options()
        return sorted({datetime.fromtimestamp(c["expiry"] / 1000).date() for c in rows if c["type"] == "CE"})
    from engine.options import _load_index
    uk = to_instrument_key(bk["name"])
    return sorted({datetime.fromtimestamp(c["expiry"] / 1000).date()
                   for c in _load_index().get(uk, []) if c["type"] == "CE"})


def eve_expiry(bk, today=None):
    """The expiry date if TODAY is its eve (next calendar day, so a holiday eve is simply missed
    rather than guessed), else None."""
    today = today or date.today()
    exps = [e for e in _expiries(bk) if e > today]
    if exps and exps[0] == today + timedelta(days=1):
        return exps[0]
    return None


def _chain_for(bk, exp):
    if bk["src"] == "BSE":
        rows = D._bse_sensex_options()
        ch = [c for c in rows if c["type"] == "CE" and datetime.fromtimestamp(c["expiry"] / 1000).date() == exp]
    else:
        from engine.options import _load_index
        uk = to_instrument_key(bk["name"])
        ch = [dict(key=c["key"], strike=c["strike"], expiry=c["expiry"], lot=int(c.get("lot") or 0))
              for c in _load_index().get(uk, [])
              if c["type"] == "CE" and datetime.fromtimestamp(c["expiry"] / 1000).date() == exp]
    return sorted(ch, key=lambda c: c["strike"])


def _pick(bk, exp, spot):
    chain = _chain_for(bk, exp)
    if len(chain) < 10:
        return None
    strikes = [c["strike"] for c in chain]
    si = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot * (1 + config.T1_EVE_OTM)))
    li = si + int(config.T1_EVE_WING_STEPS)
    if li >= len(chain):
        return None
    return chain[si], chain[li]


def scan_signals():
    """Once per eve day per book, inside the entry window. Returns the new positions."""
    if not getattr(config, "T1_EVE_ENABLED", False):
        return []
    today = date.today()
    book = D._load_json(BOOK_PATH, [])
    new = []
    for bk in BOOKS:
        try:
            if any(p["symbol"] == bk["name"] and p["entry_date"] == today.isoformat() for p in book):
                continue
            exp = eve_expiry(bk, today)
            if not exp:
                continue
            spot = D._spot(bk)
            if not spot:
                logger.warning(f"t1_eve[{bk['name']}]: eve of {exp} but no spot - skipped"); continue
            legs = _pick(bk, exp, spot)
            if not legs:
                logger.warning(f"t1_eve[{bk['name']}]: eve of {exp} but no usable chain - skipped"); continue
            short, long = legs
            sm, lm = D._quote(short["key"]), D._quote(long["key"])
            if sm is None or lm is None:
                logger.warning(f"t1_eve[{bk['name']}]: no quote on a leg - skipped"); continue
            credit = round(sm - lm, 2); width = long["strike"] - short["strike"]
            if credit <= 0 or width <= 0:
                continue
            if ZERO_DTE_MULTI_MIN_CW and credit / width < ZERO_DTE_MULTI_MIN_CW:
                logger.info(f"t1_eve[{bk['name']}]: SKIP credit/width {credit/width:.3f} < {ZERO_DTE_MULTI_MIN_CW}")
                continue
            lot = int(short.get("lot") or 0)
            if lot <= 0:
                continue
            pos = {
                "id": f"{bk['name']}-T1EVE-{today.isoformat()}", "symbol": bk["name"], "breakout_dir": None,
                "side": "BEAR_CALL", "entry_date": today.isoformat(), "entry_spot": round(spot, 1),
                "short_key": short["key"], "short_strike": int(short["strike"]),
                "long_key": long["key"], "long_strike": int(long["strike"]),
                "width_pts": int(width), "lot": lot, "num_lots": 1, "qty": lot,
                "expiry": exp.isoformat(), "short_prem": round(sm, 2), "long_prem": round(lm, 2),
                "credit": credit, "credit_width": round(credit / width, 3),
                "stop_cost": None, "max_loss_pts": round(width - credit, 2),
                "capital": round((width - credit) * lot, 0), "advisory": True,
                "order_label": (f"SELL {bk['name']} {int(short['strike'])} CE / BUY {int(long['strike'])} CE"
                                f"  T-1 EVE, expiry {exp.isoformat()}  (bear-call, credit Rs{credit}, "
                                f"held to settlement {exp.isoformat()} 15:40)"),
                "current_cost": credit, "short_cur": round(sm, 2), "long_cur": round(lm, 2),
                "pnl_pts": 0.0, "status": "OPEN", "closed_date": None, "exit_cost": None,
            }
            book.append(pos); new.append(pos)
            logger.info(f"t1_eve: opened {pos['order_label']} (spot {spot:.0f})")
        except Exception as e:
            logger.warning(f"t1_eve scan {bk['name']}: {e}")
    if new:
        D._save_json(BOOK_PATH, book)
        try:
            from engine import forward_record
            for p in new:
                forward_record.record_entry("t1eve", p)
        except Exception as e:
            logger.debug(f"t1_eve forward record: {e}")
    return new


def resolve_positions(past_settle):
    """Mark to market; settle on the expiry-day close (held to settlement, no early close - as the
    study measured it). Same settlement rule as dte_multi: never on entry spot or 0."""
    book = D._load_json(BOOK_PATH, [])
    today = date.today(); closed = changed = 0
    for p in book:
        try:
            if p.get("status") != "OPEN":
                continue
            bk = next((b for b in BOOKS if b["name"] == p["symbol"]), None)
            if bk is None:
                continue
            exp = date.fromisoformat(p["expiry"])
            if (today > exp) or (today == exp and past_settle):
                spot = D._expiry_close(bk, exp) or (D._spot(bk) if today == exp else None)
                if not spot:
                    logger.warning(f"t1_eve: {p['id']} expired but NO SETTLE PRICE - leaving OPEN"); continue
                si = max(0.0, spot - p["short_strike"]); li = max(0.0, spot - p["long_strike"])
                cost = min(max(si - li, 0.0), p["width_pts"])
                p["short_cur"] = round(si, 2); p["long_cur"] = round(li, 2)
                p["exit_cost"] = round(cost, 2); p["current_cost"] = round(cost, 2)
                p["pnl_pts"] = round(p["credit"] - cost, 2)
                p["status"] = "WIN" if p["pnl_pts"] > 0 else "LOSS"; p["closed_date"] = today.isoformat()
                closed += 1; changed += 1
                logger.info(f"t1_eve: settled {p['id']} pnl {p['pnl_pts']:+.1f} ({p['status']})")
            else:
                sm, lm = D._quote(p["short_key"]), D._quote(p["long_key"])
                if sm is not None and lm is not None:
                    p["short_cur"] = round(sm, 2); p["long_cur"] = round(lm, 2)
                    p["current_cost"] = round(sm - lm, 2)
                    p["pnl_pts"] = round(p["credit"] - p["current_cost"], 2)
                    p["mtm_ts"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M"); changed += 1
        except Exception as e:
            logger.warning(f"t1_eve resolve {p.get('id')}: {e}")
    if changed:
        D._save_json(BOOK_PATH, book)
    return closed
