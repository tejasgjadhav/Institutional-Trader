"""
0DTE Intraday — NIFTY expiry-day CALL credit spread (the 5th strategy, paper forward-test).

At the open of a NIFTY weekly-expiry day: SELL the CE at the strike nearest spot*(1+0.5%),
BUY the CE ~200 pts further out. Hold to same-day settlement — NO intraday stop (that is how
it was backtested; a stop-vs-HIGH model destroyed the edge). Defined risk: max loss =
(width − credit) × qty, ~₹14k/lot.

FLIP-CONDOR HYBRID (paper 2026-07-31): at the same 9:16 scan, the OPPOSITE side (short ~1.0%
OTM, same 200-pt wing) is ALSO sold when its own credit/width >= 0.08 — booked as its own
side-tagged position; margin is shared (condor: one side's wing covers both). Evidence in
studies/PATH_TO_1L.md iteration 2 and config.ZERO_DTE_HYBRID_* comments.

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
    ZERO_DTE_EARLY_CLOSE_FRAC,
    ZERO_DTE_MIN_CREDIT_PCT, ZERO_DTE_FLIP_RET5, ZERO_DTE_ELECTION_BLACKOUT,
    ZERO_DTE_HYBRID_ENABLED, ZERO_DTE_HYBRID_OTM, ZERO_DTE_HYBRID_MIN_CW,
)
from engine.data_fetcher import fetch_upstox_quote, fetch_upstox_ltp, get_cached_ltp, fetch_upstox_historical
from engine.instruments import to_instrument_key

logger = logging.getLogger(__name__)

_bl_warned = None   # last date the empty-blackout warning was logged (once/day)

BOOK_PATH = os.path.join(DATA_DIR, "zero_dte_positions.json")
STATUS_PATH = os.path.join(DATA_DIR, "zero_dte_status.json")


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
        _rv5.ret5 = float((closes[-1] / closes[0] - 1) * 100)   # 5-day return for the FLIP rule
        return rv
    except Exception as e:
        logger.warning(f"zero_dte rv5: {e}")
        return None


def _todays_chain(opt_type="CE"):
    """Contracts of opt_type expiring TODAY, sorted by strike — empty on non-expiry days."""
    from engine.options import _load_index
    uk = to_instrument_key(ZERO_DTE_INDEX)
    if not uk:
        return []
    today = date.today()
    chain = [c for c in _load_index().get(uk, [])
             if c["type"] == opt_type and datetime.fromtimestamp(c["expiry"] / 1000).date() == today]
    return sorted(chain, key=lambda c: c["strike"])


def _todays_ce_chain():
    return _todays_chain("CE")


def _rv5_cached():
    """rv5 computed at most once per day (inputs are prior closes — final before the open)."""
    today = date.today().isoformat()
    if getattr(_rv5_cached, "day", None) == today:
        return _rv5_cached.val
    v = _rv5()
    if v is not None:
        _rv5_cached.day, _rv5_cached.val = today, v
    return v


def write_status() -> None:
    """data/zero_dte_status.json — the pre-market 'signal expected today?' checker the UI shows.
    Verdict is decidable by 9:00 (expiry calendar + rv5 from prior closes); strikes shown are a
    PREVIEW off the latest spot — the real strikes come from the live price at 9:16."""
    if not ZERO_DTE_ENABLED:
        return
    today = date.today()
    st = {"ts": datetime.now(IST).isoformat(), "date": today.isoformat(),
          "rv5_max": ZERO_DTE_RV5_MAX}
    try:
        chain = _todays_ce_chain()
        st["is_expiry_today"] = bool(chain)
        if not chain:
            from engine.options import _load_index
            uk = to_instrument_key(ZERO_DTE_INDEX)
            exps = sorted({datetime.fromtimestamp(c["expiry"] / 1000).date()
                           for c in _load_index().get(uk, []) if c["type"] == "CE"})
            fut = [e for e in exps if e > today]
            st["next_expiry"] = fut[0].isoformat() if fut else None
        rv = _rv5_cached()
        st["rv5"] = round(rv, 3) if rv is not None else None
        ret5 = getattr(_rv5, "ret5", None)
        st["ret5"] = round(ret5, 2) if ret5 is not None else None
        st["flip_side"] = "PE" if (ZERO_DTE_FLIP_RET5 and ret5 is not None and ret5 >= ZERO_DTE_FLIP_RET5) else "CE"
        spot = _spot()
        st["spot"] = spot
        if spot:
            sg = 1 if st.get("flip_side", "CE") == "CE" else -1
            ks = round(spot * (1 + sg * ZERO_DTE_OTM_PCT) / 50) * 50
            st["preview_short"] = ks
            st["preview_wing"] = ks + sg * ZERO_DTE_WIDTH_PTS
        if not st["is_expiry_today"]:
            st["verdict"] = "NO-ENTRY"
        elif rv is not None and ZERO_DTE_RV5_MAX and rv >= ZERO_DTE_RV5_MAX:
            st["verdict"] = "SKIP"
        else:
            st["verdict"] = "EXPECTED"
        st["entered_today"] = any(p["entry_date"] == today.isoformat() for p in _load_book())
    except Exception as e:
        st["error"] = str(e)
    try:
        tmp = STATUS_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(st, f)
        os.replace(tmp, STATUS_PATH)
    except Exception as e:
        logger.warning(f"zero_dte status save: {e}")


SCAN_TRACE = {}   # {index: why it stood down today}, filled by scan_signal()


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
    SCAN_TRACE.clear()
    chain = _todays_ce_chain()
    if not chain:            # not a weekly-expiry day
        return []            # nothing to explain
    # NIFTY IS eligible today, so any exit without a position owes him a reason. This default
    # covers the silent data returns below (no spot, no quote, clamped chain, no lot size).
    SCAN_TRACE[ZERO_DTE_INDEX] = ("the market did not offer a quotable spread. The option chain, the "
                                  "index price or a two-sided quote was unavailable.")
    # ELECTION BLACKOUT (structural, 2026-07-19): scheduled inside-window binary — short premium is
    # the wrong trade against a bimodal outcome. Never triggered in 448 backtested expiries, so the
    # measured cost is Rs0; this is insurance against the ruin mode, not an edge. See config.
    _bl = ZERO_DTE_ELECTION_BLACKOUT or []
    if today.isoformat() in _bl:
        logger.info(f"zero_dte: SKIP — election blackout ({today.isoformat()}): scheduled binary event")
        SCAN_TRACE[ZERO_DTE_INDEX] = "a scheduled binary event falls inside the session, so the election blackout applies."
        return []
    # The blackout is a HAND-MAINTAINED list — there is no news feed behind it. If every entry is in
    # the past the filter is dead code and cannot protect anything, so say so loudly rather than
    # letting a non-functional safety feature look deployed.
    # Warn at most ONCE PER DAY. The next national election is due 2029, so warning on every scan
    # would fire for years and become noise that gets ignored — the opposite of the intent.
    global _bl_warned
    if _bl and not any(d > today.isoformat() for d in _bl) and _bl_warned != today:
        _bl_warned = today
        logger.warning("zero_dte: election blackout has NO FUTURE DATES — filter cannot fire. "
                       "Add ECI counting days + exit-poll sessions to ZERO_DTE_ELECTION_BLACKOUT.")
    rv = _rv5()
    if ZERO_DTE_RV5_MAX and rv is not None and rv >= ZERO_DTE_RV5_MAX:
        logger.info(f"zero_dte: SKIP — calm-regime filter (rv5 {rv:.2f}% >= {ZERO_DTE_RV5_MAX}%)")
        SCAN_TRACE[ZERO_DTE_INDEX] = (f"NIFTY's 5-day realised volatility is {rv:.2f}%, at or above the "
                                      f"{ZERO_DTE_RV5_MAX}% ceiling. This book only sells into a calm week.")
        return []
    # FLIP rule (user-approved): momentum week -> sell the PE side instead of the CE
    ret5 = getattr(_rv5, "ret5", None)
    opt = "PE" if (ZERO_DTE_FLIP_RET5 and ret5 is not None and ret5 >= ZERO_DTE_FLIP_RET5) else "CE"
    sgn = 1 if opt == "CE" else -1
    if opt == "PE":
        chain = _todays_chain("PE")
        if not chain:
            return []
    spot = _spot()
    if not spot:
        return []
    strikes = [c["strike"] for c in chain]
    si = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot * (1 + sgn * ZERO_DTE_OTM_PCT)))
    li = min(range(len(strikes)), key=lambda i: abs(strikes[i] - (strikes[si] + sgn * ZERO_DTE_WIDTH_PTS)))
    short, long = chain[si], chain[li]
    width_pts = abs(long["strike"] - short["strike"])
    if width_pts < ZERO_DTE_WIDTH_PTS * 0.5:     # chain too short / clamped
        return []
    if (sgn == 1 and long["strike"] <= short["strike"]) or (sgn == -1 and long["strike"] >= short["strike"]):
        return []
    sm, lm = _quote(short["key"]), _quote(long["key"])
    if sm is None or lm is None:
        return []
    credit = round(sm - lm, 2)
    if credit <= 0:
        return []
    if ZERO_DTE_MIN_CREDIT_PCT and credit < spot * ZERO_DTE_MIN_CREDIT_PCT / 100:
        logger.info(f"zero_dte: SKIP — thin credit ({credit:.1f} pts < {spot*ZERO_DTE_MIN_CREDIT_PCT/100:.1f} = {ZERO_DTE_MIN_CREDIT_PCT}% of spot) — dead-EV week")
        SCAN_TRACE[ZERO_DTE_INDEX] = (f"the spread paid only {credit:.1f} points against the "
                                      f"{spot*ZERO_DTE_MIN_CREDIT_PCT/100:.1f}-point floor "
                                      f"({ZERO_DTE_MIN_CREDIT_PCT}% of spot). That is too thin to carry the risk to settlement.")
        return []
    lot = int(short.get("lot", 0) or long.get("lot", 0) or 0)
    if lot <= 0:
        return []
    num_lots = int(ZERO_DTE_LOTS or 1)
    qty = lot * num_lots
    pos = {
        "id": f"0DTE-{today.isoformat()}", "symbol": ZERO_DTE_INDEX, "breakout_dir": None,
        "side": "BEAR_CALL" if opt == "CE" else "BULL_PUT", "entry_date": today.isoformat(), "entry_spot": round(spot, 1),
        "short_key": short["key"], "short_strike": int(short["strike"]),
        "long_key": long["key"], "long_strike": int(long["strike"]),
        "width_pts": int(width_pts), "lot": lot, "num_lots": num_lots, "qty": qty,
        "expiry": today.isoformat(), "short_prem": round(sm, 2), "long_prem": round(lm, 2),
        "credit": credit, "credit_width": round(credit / width_pts, 2),
        "stop_cost": None,                      # NO intraday stop — hold to settlement
        "max_loss_pts": round(width_pts - credit, 2),
        "capital": round((width_pts - credit) * qty, 0),
        "order_label": (f"SELL {ZERO_DTE_INDEX} {int(short['strike'])} {opt} / BUY {int(long['strike'])} {opt}"
                        f"  0DTE {today.isoformat()}  ({'bear-call' if opt=='CE' else 'bull-put (FLIP: 5d %+.1f%%)' % (ret5 or 0)}, credit Rs{credit}"
                        f"{f' x{num_lots}' if num_lots != 1 else ''}, settles today 15:40)"),
        "current_cost": credit, "short_cur": round(sm, 2), "long_cur": round(lm, 2),
        "pnl_pts": 0.0, "status": "OPEN",
        "closed_date": None, "exit_cost": None,
    }
    book.append(pos)
    SCAN_TRACE.pop(ZERO_DTE_INDEX, None)      # it fired, so there is nothing to explain
    new = [pos]
    # FLIP-CONDOR HYBRID (user-approved paper 2026-07-31): also sell the OPPOSITE side, short
    # ~ZERO_DTE_HYBRID_OTM OTM with the same wing, ONLY if its own credit/width >= the floor.
    # Own side-tagged position so resolve/telegram/trade-log machinery is reused unchanged.
    # Best-effort: any failure here must never block the primary FLIP entry.
    if ZERO_DTE_HYBRID_ENABLED:
        try:
            hopt = "PE" if opt == "CE" else "CE"
            hsgn = -sgn
            hchain = _todays_chain(hopt)
            hstrikes = [c["strike"] for c in hchain]
            if hstrikes:
                hi = min(range(len(hstrikes)),
                         key=lambda i: abs(hstrikes[i] - spot * (1 + hsgn * ZERO_DTE_HYBRID_OTM)))
                hj = min(range(len(hstrikes)),
                         key=lambda i: abs(hstrikes[i] - (hstrikes[hi] + hsgn * ZERO_DTE_WIDTH_PTS)))
                hshort, hlong = hchain[hi], hchain[hj]
                hw = abs(hlong["strike"] - hshort["strike"])
                geom_ok = (hw >= ZERO_DTE_WIDTH_PTS * 0.5 and
                           ((hsgn == 1 and hlong["strike"] > hshort["strike"]) or
                            (hsgn == -1 and hlong["strike"] < hshort["strike"])))
                hlot = int(hshort.get("lot", 0) or hlong.get("lot", 0) or 0)
                if geom_ok and hlot > 0:
                    hsm, hlm = _quote(hshort["key"]), _quote(hlong["key"])
                    if hsm is not None and hlm is not None:
                        hcredit = round(hsm - hlm, 2)
                        hcw = hcredit / hw if hw else 0.0
                        if hcredit > 0 and hcw >= ZERO_DTE_HYBRID_MIN_CW:
                            hqty = hlot * num_lots
                            hpos = {
                                "id": f"0DTE-{today.isoformat()}-HYB", "symbol": ZERO_DTE_INDEX,
                                "breakout_dir": None, "hybrid": True,
                                "side": "BEAR_CALL" if hopt == "CE" else "BULL_PUT",
                                "entry_date": today.isoformat(), "entry_spot": round(spot, 1),
                                "short_key": hshort["key"], "short_strike": int(hshort["strike"]),
                                "long_key": hlong["key"], "long_strike": int(hlong["strike"]),
                                "width_pts": int(hw), "lot": hlot, "num_lots": num_lots, "qty": hqty,
                                "expiry": today.isoformat(),
                                "short_prem": round(hsm, 2), "long_prem": round(hlm, 2),
                                "credit": hcredit, "credit_width": round(hcw, 2),
                                "stop_cost": None,           # NO intraday stop — hold to settlement
                                "max_loss_pts": round(hw - hcredit, 2),
                                # margin is SHARED with the FLIP side (condor: only one side can
                                # lose; margin = W - total credit). Book 0 here so the UI's
                                # margin-deployed sum does not double-count — the primary's
                                # (W - credit) x qty slightly OVERSTATES the true condor margin,
                                # which is the conservative direction.
                                "capital": 0.0,
                                "order_label": (f"SELL {ZERO_DTE_INDEX} {int(hshort['strike'])} {hopt} / "
                                                f"BUY {int(hlong['strike'])} {hopt}  0DTE {today.isoformat()}"
                                                f"  (HYBRID ADD {'bear-call' if hopt == 'CE' else 'bull-put'},"
                                                f" credit Rs{hcredit}, c/w {hcw:.2f}"
                                                f"{f' x{num_lots}' if num_lots != 1 else ''},"
                                                f" margin shared with FLIP side, settles today 15:40)"),
                                "current_cost": hcredit, "short_cur": round(hsm, 2), "long_cur": round(hlm, 2),
                                "pnl_pts": 0.0, "status": "OPEN",
                                "closed_date": None, "exit_cost": None,
                            }
                            book.append(hpos)
                            new.append(hpos)
                        else:
                            logger.info(f"zero_dte: hybrid add SKIP — c/w {hcw:.3f} < "
                                        f"{ZERO_DTE_HYBRID_MIN_CW} (credit {hcredit:.1f} on {hw:.0f}w)")
        except Exception as e:
            logger.warning(f"zero_dte hybrid add: {e}")
    _save_book(book)
    for p in new:
        logger.info(f"zero_dte: opened {p['order_label']} (spot {spot:.0f})")
    return new


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
                    # EARLY PROFIT CLOSE (user-approved 2026-08-04). Book the win once the spread
                    # has given back most of its credit instead of holding to expiry. A credit
                    # spread only pays FULL credit if both legs expire worthless, so this is a
                    # THRESHOLD not an equality. Removes the tail where a late reversal turns a
                    # winner into a full-width loser. NOT BACKTESTABLE — see config for why.
                    _f = ZERO_DTE_EARLY_CLOSE_FRAC
                    if _f and p["current_cost"] <= p["credit"] * (1 - _f):
                        p["exit_cost"] = p["current_cost"]
                        p["status"] = "WIN" if p["pnl_pts"] > 0 else "LOSS"
                        p["closed_date"] = today.isoformat()
                        closed += 1; changed = True
                        logger.info("zero_dte: EARLY CLOSE %s at %.0f%% of credit "
                                    "(cost %.2f vs credit %.2f) pnl %+.1f",
                                    p["id"], _f * 100, p["current_cost"], p["credit"], p["pnl_pts"])
                        continue
                    # OPTIONAL short-leg stop (default OFF): buy back the spread intraday
                    if ZERO_DTE_STOP_MULT and sm >= ZERO_DTE_STOP_MULT * p["short_prem"]:
                        p["exit_cost"] = p["current_cost"]
                        p["status"] = "WIN" if p["pnl_pts"] > 0 else "LOSS"
                        p["closed_date"] = today.isoformat()
                        closed += 1
                        logger.info(f"zero_dte: STOPPED {p['id']} at {ZERO_DTE_STOP_MULT}x "
                                    f"(short {sm:.1f} vs entry {p['short_prem']:.1f}) pnl {p['pnl_pts']:+.1f}")
                continue
            # BUGFIX 2026-07-21: was `_spot() or entry_spot or 0` — a quote failure settled on the
            # ENTRY spot (09:16 price, not the 15:30 close) or 0 → intrinsic 0 → full credit →
            # FABRICATED WIN. Settlement value is the EXPIRY-DAY daily CLOSE: use it first (correct on
            # T+1 too, where live spot would be the wrong day); fall back to live spot only on expiry
            # day itself when the close candle may not be published yet. Never entry/0.
            spot = None
            try:
                df = fetch_upstox_historical(ZERO_DTE_INDEX, unit="days", interval=1,
                                             from_date=exp.isoformat(), to_date=exp.isoformat())
                if df is not None and not df.empty:
                    spot = float(df["Close"].iloc[-1])
            except Exception as e:
                logger.debug(f"zero_dte settle close-fetch {p.get('id')}: {e}")
            if not spot and today == exp:
                spot = _spot()
            if not spot:
                logger.warning(f"zero_dte: {p['id']} expired but NO SETTLE PRICE — leaving OPEN, will retry")
                continue
            if p.get("side") == "BULL_PUT":
                si = max(0.0, p["short_strike"] - spot)
                li = max(0.0, p["long_strike"] - spot)
            else:
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
