"""Bhavcopy downloader, UDiFF endpoint. Same shape as bhav_dl_stk.py, new URL.

The legacy /content/historical/... paths 404 since Jul-2024. NSE serves UDiFF now.
Writes to data/bhavcopy/{cm,fo}/ in the repo, not /tmp, so a reboot cannot eat it.
"""
import os, sys, time, datetime as dt
import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SEG = sys.argv[1] if len(sys.argv) > 1 else "cm"          # cm | fo
START = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else dt.date(2024, 9, 1)
END = dt.date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else dt.date.today()
CACHE = os.path.join(ROOT, "data", "bhavcopy", SEG)
os.makedirs(CACHE, exist_ok=True)

hdr = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124 Safari/537.36",
       "Accept": "*/*", "Referer": "https://www.nseindia.com/"}
s = requests.Session(); s.headers.update(hdr)
try: s.get("https://www.nseindia.com", timeout=15)
except Exception: pass

def url_for(d):
    return (f"https://nsearchives.nseindia.com/content/{SEG}/"
            f"BhavCopy_NSE_{SEG.upper()}_0_0_0_{d:%Y%m%d}_F_0000.csv.zip")

def grab(d):
    out = os.path.join(CACHE, d.isoformat() + ".csv.zip")
    miss = os.path.join(CACHE, d.isoformat() + ".miss")
    if os.path.exists(out) or os.path.exists(miss):
        return None                                        # already settled
    for attempt in range(3):
        try:
            r = s.get(url_for(d), timeout=30)
            if r.status_code == 200 and r.content[:2] == b"PK":
                with open(out, "wb") as f: f.write(r.content)
                return True
            if r.status_code == 404:
                open(miss, "w").close()                    # holiday or no file
                return False
        except Exception:
            pass
        time.sleep(1.5 * (attempt + 1))
        try: s.get("https://www.nseindia.com", timeout=15)
        except Exception: pass
    open(miss, "w").close()
    return False

d, n, ok, skip = START, 0, 0, 0
while d <= END:
    if d.weekday() < 5:                                    # weekdays only
        n += 1
        r = grab(d)
        if r is None: skip += 1
        elif r: ok += 1
        if n % 25 == 0:
            print(f"{SEG} {d} tried={n} ok={ok} cached={skip}", flush=True)
    d += dt.timedelta(days=1)
print(f"DONE-{SEG.upper()} tried={n} downloaded={ok} already-cached={skip} "
      f"files={len([x for x in os.listdir(CACHE) if x.endswith('.zip')])}", flush=True)
