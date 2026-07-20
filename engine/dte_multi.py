"""
0DTE expiry-day CE credit spreads — SENSEX (BSE weekly, ~Thu) + BANKNIFTY (NSE monthly).
Same validated structure as the NIFTY book (engine/zero_dte.py, deliberately untouched):
at the open of that index's expiry day SELL the CE ~0.5% OTM of spot, BUY the CE ~0.83% of
spot further out, NO stop, settle intrinsic at 15:30. Parameters are exactly the backtested
ones — no extra filters (SENSEX validated unfiltered 88.8%/+7.6%m on 89 expiries Oct'24→Jul'26;
BANKNIFTY structure validated on 273 weeklies 2019-24 + 23 monthlies, deployable only on its
monthly expiry). Books: data/sensex_dte_*.json, data/bnf_dte_*.json (same schema as the other
credit books so the UI's generic renderer works).
"""
import os
import io
import gzip
import json
import logging
from datetime import datetime, date

from engine.config import (IST, DATA_DIR, ZERO_DTE_ELECTION_BLACKOUT, ZERO_DTE_MULTI_MIN_CW,
                           DTE_MULTI_BANKNIFTY_ENABLED)
from engine.data_fetcher import SESSION, UPSTOX_BASE, fetch_upstox_quote, fetch_upstox_ltp, get_cached_ltp
from engine.instruments import to_instrument_key, encode_key

logger = logging.getLogger(__name__)

BSE_MASTER_URL = "https://assets.upstox.com/market-quote/instruments/exchange/BSE.json.gz"
BSE_CACHE = os.path.join(DATA_DIR, "bse_sensex_options.json")

BOOKS = [
    dict(name="SENSEX", src="BSE", spot_key="BSE_INDEX|SENSEX", otm=0.005, wing_pct=0.0083,
         lots=1, book=os.path.join(DATA_DIR, "sensex_dte_positions.json"),
         status=os.path.join(DATA_DIR, "sensex_dte_status.json")),
    dict(name="BANKNIFTY", src="NSE", spot_key=None, otm=0.005, wing_pct=0.0083,
         lots=1, book=os.path.join(DATA_DIR, "bnf_dte_positions.json"),
         status=os.path.join(DATA_DIR, "bnf_dte_status.json")),
]


def _load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f) or default
    except Exception:
        return default


def _save_json(path, obj):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(obj, f, default=str, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        logger.warning(f"dte_multi save {path}: {e}")


def _bse_sensex_options():
    """SENSEX option contracts from the BSE master, cached once per day."""
    c = _load_json(BSE_CACHE, None)
    today = date.today().isoformat()
    if c and c.get("day") == today:
        return c["rows"]
    try:
        r = SESSION.get(BSE_MASTER_URL, timeout=60)
        recs = json.loads(gzip.decompress(r.content))
        rows = [dict(key=x["instrument_key"], strike=float(x["strike_price"]),
                     type=x["instrument_type"], expiry=int(x["expiry"]),
                     lot=int(x.get("lot_size") or 20))
                for x in recs if x.get("underlying_symbol") == "SENSEX"
                and x.get("instrument_type") in ("CE", "PE")]
        _save_json(BSE_CACHE, {"day": today, "rows": rows})
        return rows
    except Exception as e:
        logger.warning(f"dte_multi BSE master: {e}")
        return (c or {}).get("rows", [])


def _chain_today(bk):
    """CE contracts expiring TODAY for this book, sorted by strike."""
    today = date.today()
    if bk["src"] == "BSE":
        rows = _bse_sensex_options()
        ch = [c for c in rows if c["type"] == "CE"
              and datetime.fromtimestamp(c["expiry"] / 1000).date() == today]
    else:
        from engine.options import _load_index
        uk = to_instrument_key(bk["name"])
        ch = [dict(key=c["key"], strike=c["strike"], expiry=c["expiry"],
                   lot=int(c.get("lot") or 30))
              for c in _load_index().get(uk, [])
              if c["type"] == "CE" and datetime.fromtimestamp(c["expiry"] / 1000).date() == today]
    return sorted(ch, key=lambda c: c["strike"])


def _next_expiry(bk):
    today = date.today()
    if bk["src"] == "BSE":
        exps = {datetime.fromtimestamp(c["expiry"] / 1000).date() for c in _bse_sensex_options()
                if c["type"] == "CE"}
    else:
        from engine.options import _load_index
        uk = to_instrument_key(bk["name"])
        exps = {datetime.fromtimestamp(c["expiry"] / 1000).date()
                for c in _load_index().get(uk, []) if c["type"] == "CE"}
    fut = sorted(e for e in exps if e > today)
    return fut[0].isoformat() if fut else None


def _spot(bk):
    if bk["src"] == "NSE":
        p = get_cached_ltp(bk["name"])
        if p:
            return p
        lt = fetch_upstox_ltp(bk["name"])
        return lt.get("price") if lt.get("success") and lt.get("price") else None
    try:
        r = SESSION.get(f"{UPSTOX_BASE}/v2/market-quote/ltp",
                        params={"instrument_key": bk["spot_key"]}, timeout=15)
        d = r.json().get("data", {})
        for v in d.values():
            if v.get("last_price"):
                return float(v["last_price"])
    except Exception as e:
        logger.debug(f"dte_multi spot {bk['name']}: {e}")
    return None


def _quote(key):
    try:
        q = fetch_upstox_quote(key)
        if q:
            bid, ask = q.get("bid", 0.0) or 0.0, q.get("ask", 0.0) or 0.0
            if bid > 0 and ask > 0:
                return (bid + ask) / 2.0
    except Exception:
        pass
    try:
        r = SESSION.get(f"{UPSTOX_BASE}/v2/market-quote/ltp",
                        params={"instrument_key": key}, timeout=15)
        for v in r.json().get("data", {}).values():
            if v.get("last_price"):
                return float(v["last_price"])
    except Exception as e:
        logger.debug(f"dte_multi quote {key}: {e}")
    return None


def _scan_book(bk):
    today = date.today()
    book = _load_json(bk["book"], [])
    if any(p["entry_date"] == today.isoformat() for p in book):
        return []
    # ELECTION BLACKOUT (structural, 2026-07-19) — see config. Scheduled inside-window binary;
    # short premium is the wrong trade against a bimodal outcome. Rs0 measured historical cost.
    if today.isoformat() in (ZERO_DTE_ELECTION_BLACKOUT or []):
        logger.info(f"dte_multi[{bk['name']}]: SKIP — election blackout ({today.isoformat()})")
        return []
    chain = _chain_today(bk)
    if not chain:
        return []
    spot = _spot(bk)
    if not spot:
        return []
    strikes = [c["strike"] for c in chain]
    si = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot * (1 + bk["otm"])))
    wing_t = strikes[si] + spot * bk["wing_pct"]
    li = min(range(len(strikes)), key=lambda i: abs(strikes[i] - wing_t))
    short, long = chain[si], chain[li]
    width = long["strike"] - short["strike"]
    if width < spot * bk["wing_pct"] * 0.5:
        return []
    sm, lm = _quote(short["key"]), _quote(long["key"])
    if sm is None or lm is None:
        return []
    credit = round(sm - lm, 2)
    if credit <= 0:
        return []
    # MINIMUM CREDIT/WIDTH (structural, 2026-07-19) — SENSEX/BANKNIFTY only; NIFTY unchanged.
    # Below this the spread is negative-EV by arithmetic: near-zero credit against a full
    # settlement tail. The c/W<0.04 bucket had the HIGHEST win rate (91.7%) and still LOST money.
    # 0.04 is the structural boundary of that dead bucket, NOT the sweep's argmax. See config.
    if ZERO_DTE_MULTI_MIN_CW and credit / width < ZERO_DTE_MULTI_MIN_CW:
        logger.info(f"dte_multi[{bk['name']}]: SKIP — credit/width {credit/width:.3f} < "
                    f"{ZERO_DTE_MULTI_MIN_CW} (uncompensated tail risk)")
        return []
    lot = int(short.get("lot") or 0)
    if lot <= 0:
        return []
    qty = lot * int(bk["lots"])
    pos = {
        "id": f"{bk['name']}-0DTE-{today.isoformat()}", "symbol": bk["name"], "breakout_dir": None,
        "side": "BEAR_CALL", "entry_date": today.isoformat(), "entry_spot": round(spot, 1),
        "short_key": short["key"], "short_strike": int(short["strike"]),
        "long_key": long["key"], "long_strike": int(long["strike"]),
        "width_pts": int(width), "lot": lot, "num_lots": int(bk["lots"]), "qty": qty,
        "expiry": today.isoformat(), "short_prem": round(sm, 2), "long_prem": round(lm, 2),
        "credit": credit, "credit_width": round(credit / width, 3),
        "stop_cost": None, "max_loss_pts": round(width - credit, 2),
        "capital": round((width - credit) * qty, 0),
        "order_label": (f"SELL {bk['name']} {int(short['strike'])} CE / BUY {int(long['strike'])} CE"
                        f"  0DTE {today.isoformat()}  (bear-call, credit Rs{credit}, settles today 15:30)"),
        "current_cost": credit, "short_cur": round(sm, 2), "long_cur": round(lm, 2),
        "pnl_pts": 0.0, "status": "OPEN", "closed_date": None, "exit_cost": None,
    }
    book.append(pos)
    _save_json(bk["book"], book)
    logger.info(f"dte_multi: opened {pos['order_label']} (spot {spot:.0f})")
    return [pos]


def _resolve_book(bk, past_settle):
    book = _load_json(bk["book"], [])
    today = date.today()
    closed = changed = 0
    for p in book:
        try:
            if p.get("status") != "OPEN":
                continue
            exp = date.fromisoformat(p["expiry"])
            if (today > exp) or (today == exp and past_settle):
                spot = _spot(bk) or p.get("entry_spot") or 0
                si = max(0.0, spot - p["short_strike"]); li = max(0.0, spot - p["long_strike"])
                cost = min(max(si - li, 0.0), p["width_pts"])
                p["short_cur"] = round(si, 2); p["long_cur"] = round(li, 2)
                p["exit_cost"] = round(cost, 2); p["current_cost"] = round(cost, 2)
                p["pnl_pts"] = round(p["credit"] - cost, 2)
                p["status"] = "WIN" if p["pnl_pts"] > 0 else "LOSS"
                p["closed_date"] = today.isoformat()
                closed += 1; changed += 1
                logger.info(f"dte_multi: settled {p['id']} pnl {p['pnl_pts']:+.1f} ({p['status']})")
            else:
                sm, lm = _quote(p["short_key"]), _quote(p["long_key"])
                if sm is not None and lm is not None:
                    p["short_cur"] = round(sm, 2); p["long_cur"] = round(lm, 2)
                    p["current_cost"] = round(sm - lm, 2)
                    p["pnl_pts"] = round(p["credit"] - p["current_cost"], 2)
                    changed += 1
        except Exception as e:
            logger.warning(f"dte_multi resolve {p.get('id')}: {e}")
    if changed:
        _save_json(bk["book"], book)
    return closed


def _write_status(bk):
    today = date.today()
    st = {"ts": datetime.now(IST).isoformat(), "date": today.isoformat(), "rv5_max": None}
    try:
        chain = _chain_today(bk)
        st["is_expiry_today"] = bool(chain)
        if not chain:
            st["next_expiry"] = _next_expiry(bk)
        spot = _spot(bk)
        st["spot"] = spot
        if spot:
            step = 100 if bk["name"] in ("SENSEX", "BANKNIFTY") else 50
            ks = round(spot * (1 + bk["otm"]) / step) * step
            st["preview_short"] = ks
            st["preview_wing"] = ks + round(spot * bk["wing_pct"] / step) * step
        st["verdict"] = "EXPECTED" if st["is_expiry_today"] else "NO-ENTRY"
        st["entered_today"] = any(p["entry_date"] == today.isoformat()
                                  for p in _load_json(bk["book"], []))
    except Exception as e:
        st["error"] = str(e)
    _save_json(bk["status"], st)


def scan_signals() -> list:
    """Returns the NEW position dicts (was a bare count — the Telegram formatter needs the
    legs/premiums). Truthiness unchanged for the single engine_runner caller."""
    new = []
    for bk in BOOKS:
        # BANKNIFTY REJECTED 2026-07-19 — edge indistinguishable from zero (t=+0.10), entire profit
        # was 3 trades, worst day = ~102 months of profit. See studies/BANKNIFTY_0DTE_REJECTION.md.
        # Resolution still runs below so any already-open position settles normally.
        if bk["name"] == "BANKNIFTY" and not DTE_MULTI_BANKNIFTY_ENABLED:
            continue
        try:
            new.extend(_scan_book(bk) or [])
        except Exception as e:
            logger.warning(f"dte_multi scan {bk['name']}: {e}")
    return new


def resolve_positions(past_settle: bool) -> int:
    n = 0
    for bk in BOOKS:
        try:
            n += _resolve_book(bk, past_settle)
            _write_status(bk)
        except Exception as e:
            logger.warning(f"dte_multi resolve {bk['name']}: {e}")
    return n
