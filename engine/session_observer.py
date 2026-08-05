"""SESSION OBSERVER — records what actually happens in the 15:15–15:40 window, every trading day.

WHY THIS EXISTS. The 15:36 retiming was justified on numbers that a third-party audit could not
stand behind (5-Aug-2026): the "2–4% spreads" figure had no artifact in the repo at all — no script,
no data file, no log — and the "17/18 two-sided" sample was priced off a stale watchlist. Two open
questions were left, and neither can be answered from history because intraday option premiums are
not retrievable for past sessions (`studies/DATA_AVAILABILITY_LIMITS.md`):

  Q1  Is the 15:36–15:40 window actually TRADEABLE? From 15:15 the underlying stops trading
      continuously (auction to 15:35), so a market maker cannot delta-hedge in the stock. There is
      a STRUCTURAL reason to expect wide quotes, not merely an untested one. If the spread eats the
      edge, the retiming fails on execution no matter how faithful the signal is.
  Q2  Does the daily bar the scanner reads actually carry TODAY's close by 15:36? The scan takes
      `df["Close"].iloc[-1]` with no freshness check, so a late feed means it silently reads
      YESTERDAY's close against a one-day-shifted Donchian band. Evidence it may already be
      happening: union_watchlist.json built 4-Aug 14:45 held exactly the 46 breakouts of 3-Aug's
      close. If so, the retiming changed nothing at all.

So this records rather than argues. Every sample carries the daily-bar date (Q2) alongside the
book (Q1), and after enough sessions `write_study()` turns the pile into a studies/ document.

DELIBERATELY READ-ONLY. It opens nothing, closes nothing, writes no book, no trade-log row and no
signal. It cannot affect a trade. Its only output is data/session_obs/YYYY-MM-DD.jsonl and the
study file it generates.
"""
import os
import json
import logging
from datetime import date, datetime, timedelta

from engine import config
from engine.config import DATA_DIR, IST

logger = logging.getLogger(__name__)

OBS_DIR = os.path.join(DATA_DIR, "session_obs")
# `targets` is resolved ONCE per session and held. It used to be rebuilt every sample, which
# broke the measurement two ways (found 5-Aug): when spot moved the ATM shifted and the series
# silently switched to a DIFFERENT contract, and the 15:17 watchlist rebuild made names vanish
# mid-window. Neither is a market event; both are the instrument changing under the measurement.
_state = {"day": None, "done": set(), "targets": None}


def _mins(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def _batch_quotes(keys: list) -> dict:
    """{instrument_key: {bid, ask, ltp, oi, volume}} in ONE call per 25 keys.

    The quotes response is keyed by TRADING SYMBOL, not by instrument key, so the mapping back is
    via each entry's instrument_token. Falls back to per-key fetches if that field is missing —
    losing the observation would be worse than spending the calls.
    """
    from engine.data_fetcher import SESSION, UPSTOX_BASE, UPSTOX_ANALYTICS_TOKEN, fetch_upstox_quote
    out = {}
    if not (UPSTOX_ANALYTICS_TOKEN and keys):
        return out
    for i in range(0, len(keys), 25):
        chunk = keys[i:i + 25]
        try:
            r = SESSION.get(f"{UPSTOX_BASE}/v2/market-quote/quotes",
                            params={"instrument_key": ",".join(chunk)}, timeout=8)
            r.raise_for_status()
            got = set()
            for q in (r.json().get("data", {}) or {}).values():
                tok = q.get("instrument_token")
                if not tok:
                    continue
                depth = q.get("depth", {}) or {}
                buy, sell = depth.get("buy") or [], depth.get("sell") or []
                out[tok] = {
                    "bid": float(buy[0]["price"]) if buy and buy[0].get("price") else 0.0,
                    "ask": float(sell[0]["price"]) if sell and sell[0].get("price") else 0.0,
                    "bid_qty": int(buy[0].get("quantity") or 0) if buy else 0,
                    "ask_qty": int(sell[0].get("quantity") or 0) if sell else 0,
                    "ltp": q.get("last_price"), "oi": q.get("oi") or 0,
                    "volume": q.get("volume") or 0,
                }
                got.add(tok)
            for k in chunk:                       # anything the batch did not map
                if k not in got:
                    v = fetch_upstox_quote(k)
                    if v:
                        out[k] = {"bid": v.get("bid", 0.0), "ask": v.get("ask", 0.0),
                                  "bid_qty": 0, "ask_qty": 0, "ltp": v.get("ltp"),
                                  "oi": v.get("oi", 0), "volume": v.get("volume", 0)}
        except Exception as e:
            logger.warning("session_observer batch quote failed: %s", e)
    return out


def _daily_bar_probe(ticker: str = "RELIANCE") -> dict:
    """Q2 — what the scanner's own price lookup returns RIGHT NOW.

    Mirrors `stock_credit_v2._todays_breakout`: fetch daily bars to today, take the last one. The
    date of that bar is the whole question. `stale=True` means the scan is reading a previous
    session's close.
    """
    try:
        from engine.data_fetcher import fetch_upstox_historical
        today = date.today()
        df = fetch_upstox_historical(ticker + ".NS", unit="days", interval=1,
                                     from_date=(today - timedelta(days=7)).isoformat(),
                                     to_date=today.isoformat())
        if df is None or df.empty:
            return {"bar_date": None, "stale": True, "note": "no daily bars at all"}
        last = df.index[-1].date()
        return {"bar_date": last.isoformat(), "close": round(float(df["Close"].iloc[-1]), 2),
                "stale": last != today}
    except Exception as e:
        return {"bar_date": None, "stale": None, "note": f"probe failed: {e}"}


def _targets() -> list:
    """Names to watch: today's breakout candidates from the union watchlist, at v2 geometry.

    These are exactly the names that could fire at 15:36, so their book is the book that matters.
    Legs are re-resolved live rather than taken from the watchlist file, because that file may
    itself have been built on a stale bar — the defect under investigation must not be inherited
    by the instrument that measures it.
    """
    from engine.stock_credit_v2 import _pick_legs, _spot
    out = []
    try:
        raw = json.load(open(os.path.join(DATA_DIR, "union_watchlist.json")))
        wl = raw if isinstance(raw, list) else (raw.get("rows") or [])
    except Exception:
        return out
    cap = int(getattr(config, "SESSION_OBS_MAX_NAMES", 25))
    for row in wl[:cap]:
        sym = row.get("sym")
        side = row.get("side") or ""
        if not sym:
            continue
        try:
            spot = _spot(sym)
            if not spot:
                continue
            legs = _pick_legs(sym, spot, "CE" if "CALL" in side else "PE")
            if not legs:
                continue
            short, long_, exp = legs
            out.append({"sym": sym, "side": side, "spot": round(spot, 2), "expiry": exp,
                        "short_key": short["key"], "short_strike": short["strike"],
                        "long_key": long_["key"], "long_strike": long_["strike"]})
        except Exception:
            continue
    return out


def sample(tag: str) -> int:
    """Take ONE snapshot of the whole candidate book and append it. Returns rows written."""
    if _state.get("targets") is None:
        _state["targets"] = _targets()
    targets = _state["targets"]
    if not targets:
        logger.info("session_observer[%s]: no watchlist candidates to observe", tag)
        return 0
    keys = [t["short_key"] for t in targets] + [t["long_key"] for t in targets]
    q = _batch_quotes(keys)
    now = datetime.now(IST)
    rows = []
    for t in targets:
        s, l = q.get(t["short_key"]), q.get(t["long_key"])
        if not s or not l:
            continue
        smid = (s["bid"] + s["ask"]) / 2 if s["bid"] > 0 and s["ask"] > 0 else (s["ltp"] or 0)
        lmid = (l["bid"] + l["ask"]) / 2 if l["bid"] > 0 and l["ask"] > 0 else (l["ltp"] or 0)
        credit = (smid or 0) - (lmid or 0)
        width = abs(t["short_strike"] - t["long_strike"])
        rows.append({
            "ts": now.isoformat(timespec="seconds"), "tag": tag, "sym": t["sym"],
            "side": t["side"], "spot": t["spot"], "expiry": t["expiry"],
            "short_strike": t["short_strike"], "long_strike": t["long_strike"],
            "short_bid": s["bid"], "short_ask": s["ask"], "short_mid": round(smid or 0, 2),
            "short_oi": s["oi"], "short_vol": s["volume"],
            "short_bidqty": s["bid_qty"], "short_askqty": s["ask_qty"],
            "long_bid": l["bid"], "long_ask": l["ask"], "long_mid": round(lmid or 0, 2),
            "long_oi": l["oi"],
            "two_sided": bool(s["bid"] > 0 and s["ask"] > 0 and l["bid"] > 0 and l["ask"] > 0),
            "short_spread_pct": round((s["ask"] - s["bid"]) / smid * 100, 2) if smid else None,
            "long_spread_pct": round((l["ask"] - l["bid"]) / lmid * 100, 2) if lmid else None,
            "credit": round(credit, 2), "width": width,
            "cw": round(credit / width, 3) if width else None,
        })
    if not rows:
        return 0
    os.makedirs(OBS_DIR, exist_ok=True)
    path = os.path.join(OBS_DIR, f"{date.today().isoformat()}.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps({"ts": now.isoformat(timespec="seconds"), "tag": tag,
                            "daily_bar": _daily_bar_probe(), "rows": rows}) + "\n")
    logger.info("session_observer[%s]: %d names recorded", tag, len(rows))
    return len(rows)


def observe(now) -> None:
    """Called every engine cycle. Samples the baseline once, then every interval 15:15→15:40."""
    try:
        if not getattr(config, "SESSION_OBSERVER_ENABLED", False):
            return
        if now.weekday() >= 5:
            return
        from engine.data_utils import market_is_trading_today
        if not market_is_trading_today():
            return
        today = date.today().isoformat()
        if _state["day"] != today:
            _state.update(day=today, done=set(), targets=None)
        m = now.hour * 60 + now.minute
        base = _mins(getattr(config, "SESSION_OBS_BASELINE", "14:45"))
        lo = _mins(getattr(config, "SESSION_OBS_FROM", "15:15"))
        hi = _mins(getattr(config, "SESSION_OBS_TO", "15:40"))
        step = max(1, int(getattr(config, "SESSION_OBS_INTERVAL_SEC", 60)) // 60)
        if m == base and "baseline" not in _state["done"]:
            if sample("baseline"):                 # mid-session control: continuous, tight book
                _state["done"].add("baseline")
            return
        if lo <= m <= hi and (m - lo) % step == 0:
            slot = f"w{m}"
            if slot not in _state["done"]:
                if sample(now.strftime("%H:%M")):
                    _state["done"].add(slot)   # only on success — a transient quote failure retries
    except Exception as e:
        logger.warning("session_observer: %s", e)


# ── study generation ─────────────────────────────────────────────────────────
def write_study(path: str = None) -> str:
    """Aggregate every recorded session into studies/SESSION_WINDOW_OBSERVATIONS.md.

    Reports only what was measured. Where a session is missing or thin it says so rather than
    interpolating — the whole point of this file is to replace numbers that had no artifact behind
    them.
    """
    import statistics as st
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "studies", "SESSION_WINDOW_OBSERVATIONS.md")
    if not os.path.isdir(OBS_DIR):
        return ""
    files = sorted(f for f in os.listdir(OBS_DIR) if f.endswith(".jsonl"))
    if not files:
        return ""
    by_tag, stale_log, sessions = {}, [], []
    for fn in files:
        day = fn[:-6]
        sessions.append(day)
        for line in open(os.path.join(OBS_DIR, fn)):
            try:
                rec = json.loads(line)
            except Exception:
                continue
            db = rec.get("daily_bar") or {}
            stale_log.append((day, rec.get("tag"), db.get("bar_date"), db.get("stale")))
            for r in rec["rows"]:
                t = by_tag.setdefault(rec.get("tag"), {"spread": [], "two": 0, "n": 0,
                                                       "oi": [], "cw": []})
                t["n"] += 1
                t["two"] += 1 if r.get("two_sided") else 0
                if r.get("short_spread_pct") is not None:
                    t["spread"].append(r["short_spread_pct"])
                if r.get("short_oi"):
                    t["oi"].append(r["short_oi"])
                if r.get("cw") is not None:
                    t["cw"].append(r["cw"])
    med = lambda v: round(st.median(v), 2) if v else None
    L = ["# Session-window observations — what the 15:15–15:40 book actually looks like", "",
         f"Auto-generated by `engine/session_observer.py`. Sessions recorded: **{len(sessions)}** "
         f"({sessions[0]} → {sessions[-1]}).", "",
         "This file exists because the 15:36 retiming was argued on a spread figure with no artifact "
         "behind it. Everything below is measured, or is marked as not measured.", "",
         "## Liquidity through the window", "",
         "| sample | obs | two-sided | median short bid-ask | median short OI | median c/w |",
         "|---|---|---|---|---|---|"]
    for tag in sorted(by_tag, key=lambda x: (x != "baseline", x)):
        t = by_tag[tag]
        L.append(f"| {tag} | {t['n']} | {t['two']}/{t['n']} | "
                 f"{med(t['spread'])}% | {med(t['oi'])} | {med(t['cw'])} |")
    stale_bad = [s for s in stale_log if s[3] is True]
    L += ["", "## Q2 — is the scanner reading TODAY's close?", "",
          f"Samples where the last daily bar was NOT today: **{len(stale_bad)} of {len(stale_log)}**.", ""]
    if stale_bad:
        L += ["Sessions/times where the bar was stale (the scan would read a previous close):", ""]
        for day, tag, bar, _ in stale_bad[:40]:
            L.append(f"- {day} {tag} → last bar {bar}")
        L.append("")
    L += ["## How to read this", "",
          "`baseline` is the 14:45 control — continuous session, underlying hedgeable. Compare every "
          "15:xx row against it. The structural expectation is that quotes widen after 15:15, because "
          "the underlying stops trading continuously and a market maker cannot delta-hedge; whether "
          "that is true, and by how much, is what this table settles.", ""]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")
    return path


if __name__ == "__main__":
    import sys
    if "--study" in sys.argv:
        print("wrote", write_study())
    else:
        print("daily-bar probe:", _daily_bar_probe())
        print("rows:", sample(sys.argv[1] if len(sys.argv) > 1 else "manual"))
