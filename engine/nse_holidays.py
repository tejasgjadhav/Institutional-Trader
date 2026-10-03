"""NSE EXCHANGE HOLIDAYS — the official F&O trading-holiday list (user, 4-Oct-2026).

WHY. On Friday 2-Oct-2026 (Mahatma Gandhi Jayanti) the exchange was shut, but the engine sent a
15:31 watchlist and a 15:38 "no signal" message as if it were a trading day. The two open-checks
were clock-only, and the data-based check (data_utils.market_is_trading_today) counted the engine's
own price snapshots as proof of a session, and those are written on holidays too.

WHAT. engine/nse_holidays.json holds NSE's own list, taken from the holiday-master API (segment
FO, the session every live book trades). agent.is_market_open() and data_utils._market_is_open()
return False on these dates, so every scan, digest, 0DTE entry and no-signal message stays quiet.
Shifted expiries need nothing here: both 0DTE books read the expiry date from the contract master.

UPKEEP. NSE publishes next year's list in December. Run, on the Mac or the server:
    python -m engine.nse_holidays --refresh
If the current year is missing from the file, the engine logs one WARNING a day and falls back to
its old clock-and-data behaviour, so a stale file can never stop a real trading day.
"""
import os
import json
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nse_holidays.json")
API = "https://www.nseindia.com/api/holiday-master?type=trading"
_CACHE = {"mtime": None, "dates": set(), "years": set()}
_WARNED = set()


def _load() -> None:
    try:
        mt = os.path.getmtime(PATH)
        if _CACHE["mtime"] == mt:
            return
        d = json.load(open(PATH))
        _CACHE.update(mtime=mt, dates={h["date"] for h in d.get("holidays", [])},
                      years={str(y) for y in d.get("years", [])})
    except Exception as e:
        logger.warning("nse_holidays: cannot read %s (%s), holiday check is off", PATH, e)


def is_exchange_holiday(d: date = None) -> bool:
    """True if NSE's F&O segment is closed on date d (default: today, IST)."""
    if d is None:
        from engine.config import IST
        d = datetime.now(IST).date()
    _load()
    if str(d.year) not in _CACHE["years"]:
        if d not in _WARNED:
            _WARNED.add(d)
            logger.warning("nse_holidays: no NSE holiday list for %s, so holidays are not detected. "
                           "Run: python -m engine.nse_holidays --refresh", d.year)
        return False
    return d.isoformat() in _CACHE["dates"]


def refresh() -> int:
    """Fetch NSE's holiday list (segment FO) and rewrite engine/nse_holidays.json. Returns the count."""
    import requests
    ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")
    s = requests.Session()
    s.headers.update({"User-Agent": ua, "Accept-Language": "en-US"})
    try:
        s.get("https://www.nseindia.com/", timeout=15)          # cookies; a 403 here is normal
    except Exception:
        pass
    r = s.get(API, timeout=20, headers={
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/resources/exchange-communication-holidays"})
    r.raise_for_status()
    rows = []
    for x in r.json().get("FO", []):
        dt = datetime.strptime(x["tradingDate"], "%d-%b-%Y").date()
        rows.append({"date": dt.isoformat(), "day": x.get("weekDay"),
                     "name": str(x.get("description", "")).rstrip("*").strip()})
    if not rows:
        raise RuntimeError("NSE returned no FO holidays; the file was left unchanged")
    out = {"source": API + " (segment FO)", "fetched": date.today().isoformat(),
           "note": "NSE F&O trading holidays. Refresh each December with: "
                   "python -m engine.nse_holidays --refresh",
           "years": sorted({h["date"][:4] for h in rows}), "holidays": rows}
    with open(PATH + ".tmp", "w") as f:
        json.dump(out, f, indent=1)
    os.replace(PATH + ".tmp", PATH)
    return len(rows)


if __name__ == "__main__":
    import sys
    if "--refresh" in sys.argv:
        print(f"saved {refresh()} NSE F&O holidays to {PATH}")
    _load()
    print("years:", sorted(_CACHE["years"]), "· holidays:", len(_CACHE["dates"]))
