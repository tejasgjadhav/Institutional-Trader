"""Download NSE F&O bhavcopy 2019->Sep'24, caching ALL-DAY NIFTY index-option rows
(INSTRUMENT==OPTIDX, SYMBOL==NIFTY, every expiry/strike, CLOSE+CONTRACTS) to
/tmp/bhav_nifty_opt — the multi-day-path data the index-fade optimization grid needs
(bhav_expiry_dl.py kept expiry-day rows only). Legacy URL first, UDiFF fallback
(NSE switched format Jul'24). Resumable, polite, threaded — pattern from
expand_phase2_dl.py / bhav_dl_stk_opt.py."""
import os, io, zipfile, time
import requests, pandas as pd
from datetime import date, timedelta
import concurrent.futures, threading

CACHE = "/tmp/bhav_nifty_opt"; os.makedirs(CACHE, exist_ok=True)
MON = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
hdr = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
       "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
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
    for c in ("SYMBOL", "OPTION_TYP", "INSTRUMENT", "EXPIRY_DT"):
        if c in df and df[c].dtype == object: df[c] = df[c].str.strip()
    sub = df[(df["INSTRUMENT"] == "OPTIDX") & (df["SYMBOL"] == "NIFTY") &
             (df["OPTION_TYP"].isin(["CE", "PE"]))]
    m = pd.DataFrame({"EXPIRY": pd.to_datetime(sub["EXPIRY_DT"], format="%d-%b-%Y").dt.date.astype(str),
                      "STRIKE": sub["STRIKE_PR"].astype(float), "TYP": sub["OPTION_TYP"],
                      "CLOSE": sub["CLOSE"].astype(float), "VOL": sub["CONTRACTS"]})
    return "ok", m

def _udiff(s, d):
    url = (f"https://nsearchives.nseindia.com/content/fo/"
           f"BhavCopy_NSE_FO_0_0_0_{d.strftime('%Y%m%d')}_F_0000.csv.zip")
    r = s.get(url, timeout=25)
    if r.status_code == 404: return "404", None
    if r.status_code != 200 or len(r.content) < 1000: return "retry", None
    z = zipfile.ZipFile(io.BytesIO(r.content)); df = pd.read_csv(z.open(z.namelist()[0]))
    df = df[(df["TckrSymb"].astype(str).str.strip() == "NIFTY") &
            (df["OptnTp"].astype(str).str.strip().isin(["CE", "PE"]))]
    m = pd.DataFrame({"EXPIRY": pd.to_datetime(df["XpryDt"]).dt.date.astype(str),
                      "STRIKE": df["StrkPric"].astype(float),
                      "TYP": df["OptnTp"].astype(str).str.strip(),
                      "CLOSE": df["ClsPric"].astype(float), "VOL": df["TtlTradgVol"]})
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
                if st2 == "404": open(miss, "w").write("404"); return "holiday"
                if st2 == "ok": sub2.to_csv(out, index=False); return f"ok-udiff({len(sub2)})"
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
            if CTR["n"] % 100 == 0: print(f"  {d} … {CTR['ok']}/{CTR['n']}", flush=True)
        if r != "cached": time.sleep(0.2)

start = date(2018, 12, 1); end = date(2024, 9, 30)   # Dec'18 lead-in for Donchian-20 warmup
days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
days = [d for d in days if d.weekday() < 5]
NW = 6
buckets = [days[i::NW] for i in range(NW)]
print(f"downloading {len(days)} weekdays of NIFTY OPTIDX -> {CACHE}", flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=NW) as ex:
    list(ex.map(worker, buckets))
print(f"DONE-NIFTYOPT-DL ok={CTR['ok']} tried={CTR['n']}", flush=True)
