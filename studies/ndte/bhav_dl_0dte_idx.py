"""Download NSE F&O bhavcopy 2019-02 -> Sep'24, keeping the SAME-DAY-EXPIRY (0DTE) index option
rows with full OHLC for NIFTY + BANKNIFTY -> /tmp/ndte_bhav_idx/{date}.csv

Why scan every weekday instead of just Thursdays (as bhav_expiry_dl.py / bhav_bnf_dl.py did):
the weekly expiry WEEKDAY changed several times in this period (BANKNIFTY moved Thu->Wed in
Sep'23; NIFTY later moved to Tue), so a hardcoded weekday silently drops expiries. We simply
keep any row whose EXPIRY_DT == that trading date, which is expiry-weekday-agnostic and correct
by construction. Days with no same-day-expiry rows are marked .noexp and skipped cheaply.

Resumable, polite, retry/backoff. Feeds ndte14_events_2019.py.
"""
import os, io, zipfile, time
import requests, pandas as pd
from datetime import date, timedelta

CACHE = "/tmp/ndte_bhav_idx"; os.makedirs(CACHE, exist_ok=True)
MON = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
SYMS = {"NIFTY", "BANKNIFTY"}
COLS = ["SYMBOL","EXPIRY_DT","STRIKE_PR","OPTION_TYP","OPEN","HIGH","LOW","CLOSE","CONTRACTS","OPEN_INT"]
hdr = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
       "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
s = requests.Session(); s.headers.update(hdr)
try: s.get("https://www.nseindia.com", timeout=12)
except Exception: pass

def expiry_str(d):
    return f"{d.day:02d}-{MON[d.month-1].capitalize()}-{d.year}".upper()

def one(d):
    out = os.path.join(CACHE, d.isoformat() + ".csv")
    miss = os.path.join(CACHE, d.isoformat() + ".noexp")
    if os.path.exists(out) or os.path.exists(miss): return "cached"
    url = (f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{d.year}/{MON[d.month-1]}/"
           f"fo{d.day:02d}{MON[d.month-1]}{d.year}bhav.csv.zip")
    for attempt in range(4):
        try:
            r = s.get(url, timeout=30)
            if r.status_code == 404:
                open(miss, "w").write("holiday"); return "holiday"
            if r.status_code != 200 or len(r.content) < 1000:
                time.sleep(2 * (attempt + 1)); continue
            z = zipfile.ZipFile(io.BytesIO(r.content)); df = pd.read_csv(z.open(z.namelist()[0]))
            df.columns = [c.strip() for c in df.columns]
            for c in ("SYMBOL", "OPTION_TYP", "INSTRUMENT", "EXPIRY_DT"):
                if c in df and df[c].dtype == object: df[c] = df[c].str.strip()
            sub = df[(df["INSTRUMENT"] == "OPTIDX") & (df["SYMBOL"].isin(SYMS)) &
                     (df["OPTION_TYP"].isin(["CE", "PE"])) &
                     (df["EXPIRY_DT"].str.upper() == expiry_str(d))][COLS]
            if sub.empty:
                open(miss, "w").write("noexp"); return "noexp"
            sub.to_csv(out, index=False)
            return f"ok({len(sub)})"
        except Exception as e:
            if attempt == 3: return f"err:{str(e)[:30]}"
            time.sleep(2 * (attempt + 1))
    return "fail"

d = date(2019, 1, 1); end = date(2024, 9, 30); n = ok = 0
while d <= end:
    if d.weekday() < 5:
        r = one(d); n += 1
        if r.startswith("ok"): ok += 1
        if n % 100 == 0: print(f"  {d} … {ok} expiry-days / {n} scanned", flush=True)
        if r != "cached": time.sleep(0.4)
    d += timedelta(days=1)
print(f"DONE-BHAVIDX expiry_days={ok} scanned={n}", flush=True)
