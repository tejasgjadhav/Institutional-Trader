"""Rebuild the in-sample bhavcopy option pickle into research/, where a reboot cannot delete it.

WHY THIS EXISTS. The 1.6 GB OPTSTK pickle that every in-sample backtest depends on lived in /tmp
and was destroyed twice — once by a machine restart on 17-Aug-2026, taking the Upstox leg cache with
it and costing hours of throttled refetching. Research inputs now live in research/, which is
gitignored but survives reboots.

WHAT IT PRODUCES. research/bhav_optstk.pkl — a list of (date, DataFrame) with the OPTSTK rows for
every name in UNIVERSE, carrying SYMBOL, EXPIRY_DT, STRIKE_PR, OPTION_TYP, CLOSE and OPEN_INT.
OPEN_INT is the column that matters most: an exchange CLOSE on a contract that never traded is a
theoretical settlement price, not a fillable quote, and the harness needs OI to exclude those.

Resumable. Each day is cached as its own pickle under research/cache/bhav_days/ (pyarrow is not installed here), so an interrupted
run picks up where it stopped instead of starting over.
"""
import os
import io
import sys
import time
import zipfile
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")

import pandas as pd
import requests
from datetime import date, timedelta

from engine.config import UNIVERSE

ROOT = "/Users/sayali/files/institutional-trader"
DAYS = os.path.join(ROOT, "research/cache/bhav_days")
OUT = os.path.join(ROOT, "research/bhav_optstk.pkl")
START, END = date(2019, 1, 1), date(2024, 9, 30)
KEEP = {"SYMBOL", "EXPIRY_DT", "STRIKE_PR", "OPTION_TYP", "CLOSE", "OPEN_INT"}
SYMS = {t.replace(".NS", "") for t in UNIVERSE}
HDRS = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}

os.makedirs(DAYS, exist_ok=True)


def url_for(d):
    """NSE changed the bhavcopy path in July 2024; try the new layout first, then the old."""
    s = d.strftime("%Y%m%d")
    return [
        f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{s}_F_0000.csv.zip",
        f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{d.strftime('%Y')}/"
        f"{d.strftime('%b').upper()}/fo{d.strftime('%d%b%Y').upper()}bhav.csv.zip",
    ]


def parse(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        df = pd.read_csv(z.open(z.namelist()[0]))
    df.columns = [c.strip().upper() for c in df.columns]
    ren = {"TCKRSYMB": "SYMBOL", "XPRYDT": "EXPIRY_DT", "STRKPRICE": "STRIKE_PR",
           "STRKPRIC": "STRIKE_PR", "OPTNTP": "OPTION_TYP", "CLSPRIC": "CLOSE",
           "OPNINTRST": "OPEN_INT", "FININSTRMTP": "INSTRUMENT"}
    df = df.rename(columns={k: v for k, v in ren.items() if k in df.columns})
    if "INSTRUMENT" not in df.columns:
        return None
    # NSE's July-2024 format renamed the instrument codes: a stock option is "STO", not "OPTSTK".
    # Accepting only OPTSTK silently dropped every 2024 session — the download succeeded, the parse
    # returned nothing, and the run reported them as "unavailable" (found 17-Aug-2026).
    _t = df["INSTRUMENT"].astype(str).str.upper()
    df = df[_t.str.startswith("OPTSTK") | (_t == "STO")]
    if df.empty or not KEEP.issubset(df.columns):
        return None
    df = df[df["SYMBOL"].astype(str).str.strip().isin(SYMS)]
    return df[list(KEEP)] if not df.empty else None


sess = requests.Session()
sess.headers.update(HDRS)
try:
    sess.get("https://www.nseindia.com", timeout=8)
except Exception:
    pass

d, got, skipped = START, 0, 0
while d <= END:
    if d.weekday() >= 5:
        d += timedelta(days=1)
        continue
    path = os.path.join(DAYS, d.isoformat() + ".pkl")
    if os.path.exists(path):
        got += 1
        d += timedelta(days=1)
        continue
    df = None
    for u in url_for(d):
        try:
            r = sess.get(u, timeout=25)
            if r.status_code == 200 and r.content[:2] == b"PK":
                df = parse(r.content)
                break
        except Exception:
            time.sleep(1.5)
    if df is not None and not df.empty:
        df.to_pickle(path)
        got += 1
    else:
        skipped += 1
    if (got + skipped) % 50 == 0:
        print(f"  {d} · {got} days cached · {skipped} missing", flush=True)
    time.sleep(0.25)
    d += timedelta(days=1)

print(f"download complete: {got} days cached, {skipped} unavailable", flush=True)

frames = []
for f in sorted(os.listdir(DAYS)):
    if not f.endswith(".pkl"):
        continue
    try:
        frames.append((f[:-4], pd.read_pickle(os.path.join(DAYS, f))))
    except Exception as e:
        print(f"  skip {f}: {e}", flush=True)

pd.to_pickle(frames, OUT)
size = os.path.getsize(OUT) / 1e9
print(f"DONE-PICKLE {len(frames)} sessions -> {OUT} ({size:.2f} GB)")
