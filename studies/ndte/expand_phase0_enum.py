"""PHASE 0 — enumerate the full NSE F&O stock-option universe.
Download one recent full F&O bhavcopy day (unfiltered), list all distinct SYMBOL where the
instrument is a stock option (legacy INSTRUMENT=='OPTSTK' / UDiFF FinInstrmTp=='STO'), then
subtract the deployed engine UNIVERSE. Prints candidate count + list. Tries several recent
trading days until one downloads. Writes the candidate list to /tmp/expand_candidates.txt."""
import os, io, zipfile, time, sys
import requests, pandas as pd
from datetime import date, timedelta
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from engine.config import UNIVERSE

UNIV = {s.replace(".NS", "") for s in UNIVERSE}
MON = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
hdr = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
       "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}

def session():
    s = requests.Session(); s.headers.update(hdr)
    try: s.get("https://www.nseindia.com", timeout=12)
    except Exception: pass
    return s

def legacy(s, d):
    url = (f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{d.year}/{MON[d.month-1]}/"
           f"fo{d.day:02d}{MON[d.month-1]}{d.year}bhav.csv.zip")
    r = s.get(url, timeout=25)
    if r.status_code != 200 or len(r.content) < 1000: return None
    z = zipfile.ZipFile(io.BytesIO(r.content)); df = pd.read_csv(z.open(z.namelist()[0]))
    df.columns = [c.strip() for c in df.columns]
    for c in ("SYMBOL","INSTRUMENT"):
        if df[c].dtype == object: df[c] = df[c].str.strip()
    return set(df[df["INSTRUMENT"] == "OPTSTK"]["SYMBOL"].unique())

def udiff(s, d):
    url = (f"https://nsearchives.nseindia.com/content/fo/"
           f"BhavCopy_NSE_FO_0_0_0_{d.strftime('%Y%m%d')}_F_0000.csv.zip")
    r = s.get(url, timeout=25)
    if r.status_code != 200 or len(r.content) < 1000: return None
    z = zipfile.ZipFile(io.BytesIO(r.content)); df = pd.read_csv(z.open(z.namelist()[0]))
    sto = df[df["FinInstrmTp"].astype(str).str.strip() == "STO"]
    return set(sto["TckrSymb"].astype(str).str.strip().unique())

s = session()
allsyms = None; used = None
# walk back from Sep-30-2024 (end of the option-backtest window) over trading days
d = date(2024, 9, 30)
tried = 0
while tried < 15 and allsyms is None:
    if d.weekday() < 5:
        tried += 1
        for fn in (legacy, udiff):
            try:
                res = fn(s, d)
                if res:
                    allsyms = res; used = (d, fn.__name__); break
            except Exception as e:
                print(f"  {d} {fn.__name__} err {str(e)[:40]}", flush=True)
        if allsyms is None:
            print(f"  {d}: no data (holiday?)", flush=True)
    d -= timedelta(days=1)

if allsyms is None:
    print("FAILED: could not download any bhavcopy day", flush=True); sys.exit(1)

allsyms = {x for x in allsyms if isinstance(x, str) and x}
cands = sorted(allsyms - UNIV)
in_univ_not_fo = sorted(UNIV - allsyms)
print(f"\nbhavcopy day used: {used[0]} via {used[1]}", flush=True)
print(f"total distinct stock-option underlyings: {len(allsyms)}", flush=True)
print(f"UNIVERSE size: {len(UNIV)}  (of which in this bhav day: {len(UNIV & allsyms)})", flush=True)
print(f"UNIVERSE names NOT in this F&O day (delisted/renamed?): {in_univ_not_fo}", flush=True)
print(f"\nCANDIDATES (F&O underlyings NOT in UNIVERSE): {len(cands)}", flush=True)
print(cands, flush=True)
open("/tmp/expand_candidates.txt", "w").write("\n".join(cands))
print("\nDONE-PHASE0", flush=True)
