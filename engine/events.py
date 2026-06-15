"""
EVENT family data — real NSE corporate announcements, scraped and scored.

Pulls NSE's public corporate-announcements feed, matches announcements to our
universe, and scores each stock's news into a sentiment in [-1, +1] using a
keyword model. Results are cached to data/event_scores.json.

Schedule (driven by the agent): a full scrape at ~9 AM, then refreshed every
hour from 9 AM to 1 PM, so the EVENT z-score updates through the morning
without slowing the 5-min signal scan.
"""
import os
import json
import logging
from datetime import datetime, timedelta
import requests

from engine.config import DATA_DIR, IST, UNIVERSE

logger = logging.getLogger(__name__)

CACHE_PATH = os.path.join(DATA_DIR, "event_scores.json")

# ── keyword sentiment model ───────────────────────────────────────────────────
BULLISH = [
    "order", "bags", "wins", "won", "awarded", "contract", "bonus", "dividend",
    "buyback", "acquisition", "acquire", "merger", "expansion", "expand", "profit",
    "stake", "approval", "approved", "launch", "partnership", "agreement", "tie-up",
    "investment", "fund rais", "fundrais", "capex", "new plant", "capacity",
    "record date", "interim dividend", "strong", "growth", "upgrade", "rating upgrade",
    "highest ever", "milestone", "commission", "allotment of equity", "preferential",
]
BEARISH = [
    "resignation", "resigns", "resigned", "fraud", "investigation", "probe", "penalty",
    "default", "downgrade", "rating downgrade", "loss", "decline", "litigation", "lawsuit",
    "insolvency", "nclt", "pledge", "lay off", "layoff", "shut", "recall", "ban", "fine",
    "scam", "embezzle", "delay", "deferred", "cyber", "breach", "qualified opinion",
    "going concern", "auditor resign", "suspension", "show cause", "demand notice",
]


def _score_text(text: str) -> int:
    """+1 bullish, -1 bearish, 0 neutral for one announcement."""
    t = (text or "").lower()
    pos = sum(1 for k in BULLISH if k in t)
    neg = sum(1 for k in BEARISH if k in t)
    if pos > neg:
        return 1
    if neg > pos:
        return -1
    return 0


# ── NSE scraper ───────────────────────────────────────────────────────────────
_NSE_HOME = "https://www.nseindia.com"
_NSE_ANN = "https://www.nseindia.com/api/corporate-announcements?index=equities"
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
}


def _scrape_nse_announcements(hours_back: int = 18) -> list:
    """
    Scrape NSE corporate announcements. NSE needs a session cookie first
    (hit the homepage), then the API. Returns a list of {symbol, text, when}.
    """
    try:
        s = requests.Session()
        s.headers.update(_HEADERS)
        s.get(_NSE_HOME, timeout=10)                # seed cookies
        r = s.get(_NSE_ANN, timeout=15)
        r.raise_for_status()
        data = r.json()
        rows = data if isinstance(data, list) else data.get("data", data.get("rows", []))
        cutoff = datetime.now() - timedelta(hours=hours_back)
        out = []
        for a in rows:
            sym = a.get("symbol")
            text = " ".join(str(a.get(k, "")) for k in ("desc", "attchmntText", "sm_name", "smIndustry"))
            when = a.get("an_dt") or a.get("sort_date") or ""
            if sym:
                out.append({"symbol": sym, "text": text, "when": when})
        logger.info(f"NSE announcements scraped: {len(out)} rows")
        return out
    except Exception as e:
        logger.warning(f"NSE announcement scrape failed: {e}")
        return []


# ── refresh + cache ───────────────────────────────────────────────────────────

def refresh_event_scores() -> dict:
    """
    Scrape, score per universe stock, cache to disk. Returns {symbol: score}.
    A failed scrape keeps the previous cache (no data loss).
    """
    universe_syms = {t.replace(".NS", "") for t in UNIVERSE}
    anns = _scrape_nse_announcements()
    if not anns:
        # keep yesterday's/last cache if present
        return _load_cache().get("scores", {})

    # aggregate per symbol: net sentiment clipped to [-1, +1]
    agg = {}
    for a in anns:
        sym = a["symbol"]
        if sym not in universe_syms:
            continue
        agg.setdefault(sym, []).append(_score_text(a["text"]))
    scores = {}
    for sym, lst in agg.items():
        net = sum(lst)
        scores[sym] = max(-1, min(1, net))   # clip

    cache = {
        "refreshed_at": datetime.now(IST).isoformat(),
        "date": str(datetime.now(IST).date()),
        "scores": scores,
        "n_announcements": len(anns),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)
    logger.info(f"Event scores refreshed: {len(scores)} stocks with events "
                f"(of {len(anns)} announcements)")
    return scores


def _load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def get_event_score(ticker: str) -> tuple:
    """
    (sentiment, has_event) for a stock from the cached scrape.
      sentiment in [-1, +1]; has_event True if any matched announcement.
    Indices (NIFTY/BANKNIFTY) have no single-stock events -> (0, False).
    """
    sym = ticker.replace(".NS", "")
    scores = _load_cache().get("scores", {})
    if sym in scores:
        return float(scores[sym]), True
    return 0.0, False


def cache_age_minutes() -> float:
    c = _load_cache()
    ts = c.get("refreshed_at")
    if not ts:
        return 9e9
    try:
        return (datetime.now(IST) - datetime.fromisoformat(ts)).total_seconds() / 60
    except Exception:
        return 9e9


def cache_status() -> dict:
    c = _load_cache()
    return {
        "refreshed_at": c.get("refreshed_at", "never"),
        "stocks_with_events": len(c.get("scores", {})),
        "announcements": c.get("n_announcements", 0),
        "age_min": round(cache_age_minutes(), 1),
    }


if __name__ == "__main__":
    print("Refreshing event scores from NSE...")
    sc = refresh_event_scores()
    print("Status:", cache_status())
    print("Stocks with events:", {k: v for k, v in list(sc.items())[:20]})
