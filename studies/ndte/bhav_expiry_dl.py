"""Download NSE F&O bhavcopy for NIFTY WEEKLY EXPIRY DAYS only, 2019-02 -> Sep 2024, keeping
full OHLC of same-day-expiry NIFTY options (the 0DTE rows). Thursdays + Wednesday fallback
(holiday-shifted expiries). Resumable -> /tmp/ndte_bhav/{date}.csv"""
import os, io, zipfile, time
import requests, pandas as pd
from datetime import date, timedelta

CACHE = "/tmp/ndte_bhav"; os.makedirs(CACHE, exist_ok=True)
MON = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
hdr = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
       "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
s = requests.Session(); s.headers.update(hdr)
try: s.get("https://www.nseindia.com", timeout=12)
except Exception: pass

def expiry_str(d):
    return f"{d.day:02d}-{MON[d.month-1].capitalize()}-{d.year}"

def one(d):
    out = os.path.join(CACHE, d.isoformat() + ".csv")
    miss = os.path.join(CACHE, d.isoformat() + ".miss")
    if os.path.exists(out): return "cached"
    if os.path.exists(miss): return "miss"
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
            for c in ("SYMBOL", "OPTION_TYP", "INSTRUMENT", "EXPIRY_DT"):
                if c in df and df[c].dtype == object: df[c] = df[c].str.strip()
            sub = df[(df["SYMBOL"] == "NIFTY") & (df["INSTRUMENT"] == "OPTIDX") &
                     (df["EXPIRY_DT"].str.upper() == expiry_str(d).upper())]
            if sub.empty:                      # not an expiry day
                open(miss, "w").write("noexp"); return "noexp"
            cols = ["EXPIRY_DT","STRIKE_PR","OPTION_TYP","OPEN","HIGH","LOW","CLOSE","SETTLE_PR","CONTRACTS","OPEN_INT"]
            sub[cols].to_csv(out, index=False)
            return f"ok({len(sub)})"
        except Exception as e:
            if attempt == 2: return f"err:{str(e)[:40]}"
            time.sleep(2 * (attempt + 1))
    return "fail"

d = date(2019, 2, 11); end = date(2024, 9, 30)
n = ok = 0
while d <= end:
    if d.weekday() == 3:                      # Thursday
        r = one(d); n += 1
        got = r.startswith("ok") or r == "cached"
        if not got:                           # holiday-shifted expiry -> Wednesday
            r2 = one(d - timedelta(days=1))
            got = r2.startswith("ok") or r2 == "cached"
        if got: ok += 1
        if n % 25 == 0: print(f"  {d} … {ok}/{n} expiry days", flush=True)
        time.sleep(0.6)
    d += timedelta(days=1)
print(f"DONE-BHAVEXP ok={ok} tried={n}", flush=True)
