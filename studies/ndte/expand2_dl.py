"""Download bhavcopy 2019->Sep-2024 for the 103 OUTSIDER F&O names (universe expansion study 2).

Why a re-download: the July expansion study cached its candidate data under /tmp, which a reboot
destroyed, and its backtest predates the six harness corrections anyway. Same resumable pattern as
build_is_pickle.py, different symbol set and cache dir. NSE archives only - no Upstox contention.
"""
import os, io, sys, json, time, zipfile, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd, requests
from datetime import date, timedelta

ROOT = "/Users/sayali/files/institutional-trader"
DAYS = os.path.join(ROOT, "research/cache/bhav_days_expand")
OUT  = os.path.join(ROOT, "research/expansion2/bhav_outsiders.pkl")
START, END = date(2019, 1, 1), date(2024, 9, 30)
KEEP = {"SYMBOL", "EXPIRY_DT", "STRIKE_PR", "OPTION_TYP", "CLOSE", "OPEN_INT"}
SYMS = set(json.load(open(os.path.join(ROOT, "research/expansion2/outsiders.json"))))
os.makedirs(DAYS, exist_ok=True)

def url_for(d):
    s = d.strftime("%Y%m%d")
    return [f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{s}_F_0000.csv.zip",
            f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{d.strftime('%Y')}/"
            f"{d.strftime('%b').upper()}/fo{d.strftime('%d%b%Y').upper()}bhav.csv.zip"]

def parse(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        df = pd.read_csv(z.open(z.namelist()[0]))
    df.columns = [c.strip().upper() for c in df.columns]
    ren = {"TCKRSYMB":"SYMBOL","XPRYDT":"EXPIRY_DT","STRKPRICE":"STRIKE_PR","STRKPRIC":"STRIKE_PR",
           "OPTNTP":"OPTION_TYP","CLSPRIC":"CLOSE","OPNINTRST":"OPEN_INT","FININSTRMTP":"INSTRUMENT"}
    df = df.rename(columns={k:v for k,v in ren.items() if k in df.columns})
    if "INSTRUMENT" not in df.columns: return None
    t = df["INSTRUMENT"].astype(str).str.upper()
    df = df[t.str.startswith("OPTSTK") | (t == "STO")]      # STO = post-July-2024 code
    if df.empty or not KEEP.issubset(df.columns): return None
    df = df[df["SYMBOL"].astype(str).str.strip().isin(SYMS)]
    return df[list(KEEP)] if not df.empty else None

sess = requests.Session(); sess.headers.update({"User-Agent":"Mozilla/5.0","Accept":"*/*"})
try: sess.get("https://www.nseindia.com", timeout=8)
except Exception: pass
d, got, skipped = START, 0, 0
while d <= END:
    if d.weekday() >= 5: d += timedelta(days=1); continue
    path = os.path.join(DAYS, d.isoformat()+".pkl")
    if os.path.exists(path): got += 1; d += timedelta(days=1); continue
    df = None
    for u in url_for(d):
        try:
            r = sess.get(u, timeout=25)
            if r.status_code == 200 and r.content[:2] == b"PK":
                df = parse(r.content); break
        except Exception: time.sleep(1.5)
    if df is not None and not df.empty: df.to_pickle(path); got += 1
    else: skipped += 1
    if (got+skipped) % 50 == 0: print(f"  {d} · {got} cached · {skipped} missing", flush=True)
    time.sleep(0.25); d += timedelta(days=1)
print(f"download complete: {got} days, {skipped} unavailable", flush=True)
frames = []
for f in sorted(os.listdir(DAYS)):
    if f.endswith(".pkl"):
        try: frames.append((f[:-4], pd.read_pickle(os.path.join(DAYS,f))))
        except Exception as e: print(f"  skip {f}: {e}", flush=True)
pd.to_pickle(frames, OUT)
print(f"DONE-PICKLE {len(frames)} sessions -> {OUT} ({os.path.getsize(OUT)/1e9:.2f} GB)")
