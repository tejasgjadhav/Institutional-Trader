"""
Historical NSE events — for backtesting the EVENT family.

Fetches NSE corporate announcements over a date range and maps each to the
trading day on which it would have been actionable (no lookahead): news before
11:00 AM counts for that day; later news counts for the next day. Scored with
the same keyword model as the live scraper.

Used ONLY by backtests — the live system uses engine.events.
"""
import logging
from datetime import datetime, timedelta
import requests

from engine.config import UNIVERSE
from engine.events import _score_text  # reuse the live keyword model

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
}
_HOME = "https://www.nseindia.com"
_API = "https://www.nseindia.com/api/corporate-announcements"

NEWS_CUTOFF_HOUR = 11  # news after this counts for the NEXT trading day


def _session():
    s = requests.Session(); s.headers.update(_HEADERS)
    s.get(_HOME, timeout=10)
    return s


def _fetch_range(s, d_from, d_to) -> list:
    params = {"index": "equities",
              "from_date": d_from.strftime("%d-%m-%Y"),
              "to_date": d_to.strftime("%d-%m-%Y")}
    try:
        r = s.get(_API, params=params, timeout=25)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else data.get("data", data.get("rows", []))
    except Exception as e:
        logger.warning(f"NSE history fetch {d_from}..{d_to} failed: {e}")
        return []


def _parse_dt(s: str):
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except Exception:
            continue
    return None


def _effective_trading_day(dt: datetime):
    """News known before 11:00 -> same day; otherwise next calendar day."""
    if dt.hour < NEWS_CUTOFF_HOUR:
        return dt.date()
    return (dt + timedelta(days=1)).date()


def fetch_event_scores(from_date, to_date, progress=None) -> dict:
    """
    Returns {(date_iso, symbol): score in [-1,+1]} for the universe over the range.
    Chunks the range into ~10-day windows so NSE returns complete data.
    """
    universe = {t.replace(".NS", "") for t in UNIVERSE}
    s = _session()
    # fetch a couple of days before from_date so prior-evening news maps in
    start = from_date - timedelta(days=2)
    raw = []
    cur = start
    while cur <= to_date:
        end = min(cur + timedelta(days=9), to_date)
        chunk = _fetch_range(s, cur, end)
        raw.extend(chunk)
        if progress:
            progress(cur, end, len(chunk))
        cur = end + timedelta(days=1)

    # aggregate per (effective day, symbol)
    agg = {}
    for a in raw:
        sym = a.get("symbol")
        if sym not in universe:
            continue
        dt = _parse_dt(str(a.get("an_dt") or a.get("sort_date") or ""))
        if not dt:
            continue
        day = _effective_trading_day(dt).isoformat()
        text = " ".join(str(a.get(k, "")) for k in ("desc", "attchmntText", "sm_name", "smIndustry"))
        agg.setdefault((day, sym), []).append(_score_text(text))

    scores = {}
    for key, lst in agg.items():
        scores[key] = max(-1, min(1, sum(lst)))
    logger.info(f"Historical event scores: {len(scores)} (day,stock) entries from {len(raw)} announcements")
    return scores
