"""Download old-format NSE F&O bhavcopy 2018-01-01 -> 2018-12-31: FUTSTK (universe) +
FUTIDX (NIFTY/BANKNIFTY) closes for signal lookback. Resumable, polite."""
import os, io, zipfile, time, sys
import requests, pandas as pd
from datetime import date, timedelta
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from engine.config import UNIVERSE

CACHE = "/Users/sayali/files/institutional-trader/studies/monthly_fut/cache_2018"
os.makedirs(CACHE, exist_ok=True)
SYMS = {s.replace(".NS", "") for s in UNIVERSE} | {"NIFTY", "BANKNIFTY"}
MON = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
hdr = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
       "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
s = requests.Session(); s.headers.update(hdr)
try: s.get("https://www.nseindia.com", timeout=12)
except Exception: pass

KEEP = ["INSTRUMENT", "SYMBOL", "EXPIRY_DT", "OPEN", "HIGH", "LOW", "CLOSE", "SETTLE_PR", "OPEN_INT"]

def one(d):
    out = os.path.join(CACHE, d.isoformat() + ".csv")
    miss = os.path.join(CACHE, d.isoformat() + ".miss")
    if os.path.exists(out) or os.path.exists(miss): return "cached"
    url = (f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{d.year}/{MON[d.month-1]}/"
           f"fo{d.day:02d}{MON[d.month-1]}{d.year}bhav.csv.zip")
    for attempt in range(3):
        try:
            r = s.get(url, timeout=25)
            if r.status_code == 404:
                open(miss, "w").write("404"); return "holiday"
            if r.status_code != 200 or len(r.content) < 1000:
                time.sleep(2 * (attempt + 1)); continue
            z = zipfile.ZipFile(io.BytesIO(r.content)); df = pd.read_csv(z.open(z.namelist()[0]))
            df.columns = [c.strip() for c in df.columns]
            for c in ("SYMBOL", "INSTRUMENT"):
                if df[c].dtype == object: df[c] = df[c].str.strip()
            df = df[df["INSTRUMENT"].isin(["FUTSTK", "FUTIDX"]) & df["SYMBOL"].isin(SYMS)]
            df[KEEP].to_csv(out, index=False)
            return f"ok({len(df)})"
        except Exception as e:
            if attempt == 2: return f"err:{str(e)[:30]}"
            time.sleep(2 * (attempt + 1))
    return "fail"

start = date(2018, 1, 1); end = date(2018, 12, 31); d = start; n = ok = 0
while d <= end:
    if d.weekday() < 5:
        r = one(d); n += 1
        if r.startswith("ok") or r == "cached": ok += 1
        if n % 50 == 0: print(f"  {d} ... {ok}/{n}", flush=True)
        if r != "cached": time.sleep(0.6)
    d += timedelta(days=1)
print(f"DONE 2018: {ok}/{n}")
