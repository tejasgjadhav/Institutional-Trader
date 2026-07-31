"""Re-download NSE F&O bhavcopy 2019->Sep'24 into /tmp/bhav_cache_stk (CLOSE+OI for the ~100-stock
universe), matching the schema stkfade_union.py reads. NSE switched bhavcopy URL format mid-2024:
the legacy `fo{DD}{MON}{YYYY}bhav.csv.zip` 404s for late-2024 dates, so this tries the legacy URL
first and falls back to the new UDiFF `BhavCopy_NSE_FO_0_0_0_{YYYYMMDD}_F_0000.csv.zip`, normalising
both to columns INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,CLOSE,OPEN_INT. Resumable, polite."""
import os, io, zipfile, time, sys
import requests, pandas as pd
from datetime import date, timedelta
import concurrent.futures, threading
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from engine.config import UNIVERSE

CACHE = "/tmp/bhav_cache_stk"; os.makedirs(CACHE, exist_ok=True)
SYMS = {s.replace(".NS", "") for s in UNIVERSE}
MON = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
hdr = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
       "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
COLS = ["INSTRUMENT","SYMBOL","EXPIRY_DT","STRIKE_PR","OPTION_TYP","CLOSE","OPEN_INT"]
LK = threading.Lock(); CTR = {"n": 0, "ok": 0}

def _session():
    s = requests.Session(); s.headers.update(hdr)
    try: s.get("https://www.nseindia.com", timeout=12)
    except Exception: pass
    return s

def _legacy(s, d):
    url = (f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{d.year}/{MON[d.month-1]}/"
           f"fo{d.day:02d}{MON[d.month-1]}{d.year}bhav.csv.zip")
    r = s.get(url, timeout=25)
    if r.status_code == 404: return "404", None
    if r.status_code != 200 or len(r.content) < 1000: return "retry", None
    z = zipfile.ZipFile(io.BytesIO(r.content)); df = pd.read_csv(z.open(z.namelist()[0]))
    df.columns = [c.strip() for c in df.columns]
    for c in ("SYMBOL","OPTION_TYP","INSTRUMENT","EXPIRY_DT"):
        if c in df and df[c].dtype == object: df[c] = df[c].str.strip()
    sub = df[df["SYMBOL"].isin(SYMS)][COLS]
    return "ok", sub

def _udiff(s, d):
    url = (f"https://nsearchives.nseindia.com/content/fo/"
           f"BhavCopy_NSE_FO_0_0_0_{d.strftime('%Y%m%d')}_F_0000.csv.zip")
    r = s.get(url, timeout=25)
    if r.status_code == 404: return "404", None
    if r.status_code != 200 or len(r.content) < 1000: return "retry", None
    z = zipfile.ZipFile(io.BytesIO(r.content)); df = pd.read_csv(z.open(z.namelist()[0]))
    df = df[df["TckrSymb"].isin(SYMS)].copy()
    m = pd.DataFrame({
        "INSTRUMENT": df["FinInstrmTp"],
        "SYMBOL": df["TckrSymb"].str.strip(),
        "EXPIRY_DT": df["XpryDt"],
        "STRIKE_PR": df["StrkPric"],
        "OPTION_TYP": df["OptnTp"].astype(str).str.strip(),
        "CLOSE": df["ClsPric"],
        "OPEN_INT": df["OpnIntrst"],
    })
    return "ok", m

def one(s, d):
    out = os.path.join(CACHE, d.isoformat() + ".csv")
    miss = os.path.join(CACHE, d.isoformat() + ".miss")
    if os.path.exists(out) or os.path.exists(miss): return "cached"
    for attempt in range(3):
        try:
            st, sub = _legacy(s, d)
            if st == "404":
                st2, sub2 = _udiff(s, d)
                if st2 == "404":
                    open(miss, "w").write("404"); return "holiday"
                if st2 == "ok":
                    sub2.to_csv(out, index=False); return f"ok-udiff({len(sub2)})"
            elif st == "ok":
                sub.to_csv(out, index=False); return f"ok({len(sub)})"
        except Exception as e:
            if attempt == 2: return f"err:{str(e)[:40]}"
        time.sleep(2 * (attempt + 1))
    return "fail"

def worker(dates):
    s = _session()
    for d in dates:
        r = one(s, d)
        with LK:
            CTR["n"] += 1
            if r.startswith("ok") or r == "cached": CTR["ok"] += 1
            if CTR["n"] % 100 == 0:
                print(f"  {d} … {CTR['ok']}/{CTR['n']}", flush=True)
        if not r == "cached": time.sleep(0.2)

start = date(2019, 1, 1); end = date(2024, 9, 30)
days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
days = [d for d in days if d.weekday() < 5]
# round-robin split across workers to spread dates
NW = 6
buckets = [days[i::NW] for i in range(NW)]
with concurrent.futures.ThreadPoolExecutor(max_workers=NW) as ex:
    list(ex.map(worker, buckets))
print(f"DONE-BHAVSTK ok={CTR['ok']} tried={CTR['n']}", flush=True)
