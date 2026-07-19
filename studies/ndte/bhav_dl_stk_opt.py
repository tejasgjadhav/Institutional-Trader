"""Re-download NSE F&O bhavcopy 2019->Sep'24, caching the ~100-stock OPTION rows with FULL OHLC
(OPEN/HIGH/LOW/CLOSE + OPEN_INT) to /tmp/bhav_cache_stk. Unlike bhav_dl_stk.py (which kept only
CLOSE, adequate for close-only sims), this keeps the daily LOW/HIGH so the Donchian-fade study can
detect intraday TP-50 / stop touches on daily OHLC. Resumable, polite, retry/backoff, checkpoints.
Mirrors bhav_expiry_dl.py's OHLC pattern for the full ~100-stock universe (INSTRUMENT==OPTSTK)."""
import os, io, zipfile, time, sys
import requests, pandas as pd
from datetime import date, timedelta
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from engine.config import UNIVERSE

CACHE = "/tmp/bhav_cache_stk"; os.makedirs(CACHE, exist_ok=True)
SYMS = {s.replace(".NS", "") for s in UNIVERSE}
MON = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
COLS = ["INSTRUMENT","SYMBOL","EXPIRY_DT","STRIKE_PR","OPTION_TYP","OPEN","HIGH","LOW","CLOSE","OPEN_INT"]
hdr = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
       "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
s = requests.Session(); s.headers.update(hdr)
try: s.get("https://www.nseindia.com", timeout=12)
except Exception: pass

def one(d):
    out = os.path.join(CACHE, d.isoformat() + ".csv")
    miss = os.path.join(CACHE, d.isoformat() + ".miss")
    if os.path.exists(out) or os.path.exists(miss): return "cached"
    url = (f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{d.year}/{MON[d.month-1]}/"
           f"fo{d.day:02d}{MON[d.month-1]}{d.year}bhav.csv.zip")
    for attempt in range(4):
        try:
            r = s.get(url, timeout=30)
            if r.status_code == 404:
                open(miss, "w").write("404"); return "holiday"
            if r.status_code != 200 or len(r.content) < 1000:
                time.sleep(2 * (attempt + 1)); continue
            z = zipfile.ZipFile(io.BytesIO(r.content)); df = pd.read_csv(z.open(z.namelist()[0]))
            df.columns = [c.strip() for c in df.columns]
            for c in ("SYMBOL", "OPTION_TYP", "INSTRUMENT", "EXPIRY_DT"):
                if c in df and df[c].dtype == object: df[c] = df[c].str.strip()
            sub = df[(df["SYMBOL"].isin(SYMS)) & (df["INSTRUMENT"] == "OPTSTK") &
                     (df["OPTION_TYP"].isin(["CE", "PE"]))][COLS]
            sub.to_csv(out, index=False)
            return f"ok({len(sub)})"
        except Exception as e:
            if attempt == 3: return f"err:{str(e)[:30]}"
            time.sleep(2 * (attempt + 1))
    return "fail"

start = date(2019, 1, 1); end = date(2024, 9, 30); d = start; n = ok = 0
while d <= end:
    if d.weekday() < 5:
        r = one(d); n += 1
        if r.startswith("ok") or r == "cached": ok += 1
        if n % 100 == 0: print(f"  {d} … {ok}/{n}", flush=True)
        if r != "cached": time.sleep(0.5)
    d += timedelta(days=1)
print(f"DONE-BHAVSTKOPT ok={ok} tried={n}", flush=True)
