"""OPEN RECORDER (user-approved 16-Oct-2026): on a 0DTE expiry day, record the live quotes of the
index and of every option strike within OPEN_RECORDER_BAND of spot, both CE and PE, from 09:15 to
09:25 every OPEN_RECORDER_EVERY_S seconds. Upstox keeps traded 1-min candles, but not the bid/ask,
so this is the only way to measure what a real 09:16 or 09:22 fill would have cost.

Read-only: it never opens, closes or changes a position, and every call is guarded so it can never
disturb the engine. One batched quote call per book per tick. Output, one JSON line per tick:
    data/open_record/<YYYY-MM-DD>_<BOOK>.jsonl
"""
import os
import json
import time
import logging
from datetime import datetime, date

from engine import config
from engine.config import IST, DATA_DIR

logger = logging.getLogger(__name__)
OUT_DIR = os.path.join(DATA_DIR, "open_record")
_last = {}


def _hm(s):
    return int(s[:2]) * 60 + int(s[3:5])


def _nifty_rows():
    from engine import zero_dte
    rows = [dict(key=c["key"], strike=c["strike"], type=t) for t in ("CE", "PE") for c in zero_dte._todays_chain(t)]
    return rows, zero_dte._spot, "NSE_INDEX|Nifty 50"


def _sensex_rows():
    from engine import dte_multi
    today = date.today()
    rows = [dict(key=c["key"], strike=c["strike"], type=c["type"]) for c in dte_multi._bse_sensex_options()
            if c["type"] in ("CE", "PE") and datetime.fromtimestamp(c["expiry"] / 1000).date() == today]
    return rows, None, "BSE_INDEX|SENSEX"


def _quotes(keys):
    from engine.data_fetcher import _upstox_get, UPSTOX_BASE
    r = _upstox_get(f"{UPSTOX_BASE}/v2/market-quote/quotes", params={"instrument_key": ",".join(keys)}, timeout=10)
    r.raise_for_status()
    out = {}
    for v in (r.json().get("data") or {}).values():
        d = v.get("depth") or {}
        b, s = (d.get("buy") or [{}])[0], (d.get("sell") or [{}])[0]
        out[v.get("instrument_token")] = dict(ltp=v.get("last_price"), bid=b.get("price"), bid_qty=b.get("quantity"),
                                             ask=s.get("price"), ask_qty=s.get("quantity"), oi=v.get("oi"),
                                             vol=v.get("volume"), ts=v.get("timestamp"))
    return out


def tick(now=None):
    """Call every engine cycle. Does nothing outside the window, on non-expiry days, or when disabled."""
    if not getattr(config, "OPEN_RECORDER_ENABLED", False):
        return
    now = now or datetime.now(IST)
    m = now.hour * 60 + now.minute
    if now.weekday() >= 5 or not (_hm(config.OPEN_RECORDER_FROM) <= m <= _hm(config.OPEN_RECORDER_TO)):
        return
    for book, fn in (("NIFTY", _nifty_rows), ("SENSEX", _sensex_rows)):
        if time.time() - _last.get(book, 0) < config.OPEN_RECORDER_EVERY_S:
            continue
        _last[book] = time.time()
        try:
            rows, _, idx_key = fn()
            if not rows:
                continue                                    # not this index's expiry day
            q0 = _quotes([idx_key])
            spot = (q0.get(idx_key) or {}).get("ltp")
            if not spot:
                continue
            band = config.OPEN_RECORDER_BAND
            near = [r for r in rows if abs(r["strike"] / spot - 1) <= band]
            q = _quotes([idx_key] + [r["key"] for r in near])
            rec = {"t": now.strftime("%H:%M:%S"), "spot": spot,
                   "rows": [dict(r, **(q.get(r["key"]) or {})) for r in near]}
            os.makedirs(OUT_DIR, exist_ok=True)
            with open(os.path.join(OUT_DIR, f"{now.date().isoformat()}_{book}.jsonl"), "a") as f:
                f.write(json.dumps(rec) + "\n")
        except Exception as e:
            logger.warning(f"open_recorder {book}: {e}")
