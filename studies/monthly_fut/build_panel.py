"""Merge the four bhavcopy caches into one futures panel:
date, symbol, expiry, open, high, low, close, settle, oi  ->  panel.csv.gz
Sources (later overrides earlier on date+symbol+expiry):
  1. /tmp/bhav_cache_stk        old fmt, FUTSTK only, CLOSE+OI          2019-01 -> ~2024-06
  2. cache_2018                 old fmt, FUTSTK+FUTIDX, OHLC+SETTLE+OI  2018
  3. cache_idx                  old fmt, FUTIDX, OHLC+SETTLE+OI         2019-01 -> 2024-06
  4. cache_new                  UDiFF, STF+IDF, OHLC+SETTLE+OI          2024-07 -> now
"""
import os, glob
import pandas as pd

BASE = "/Users/sayali/files/institutional-trader/studies/monthly_fut"
frames = []

def load_dir(path, parser):
    out = []
    for f in sorted(glob.glob(os.path.join(path, "*.csv"))):
        d = os.path.basename(f)[:-4]
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        if df.empty: continue
        r = parser(df)
        if r is None or r.empty: continue
        r.insert(0, "date", d)
        out.append(r)
    return out

def parse_old_stk(df):
    df = df[df["INSTRUMENT"] == "FUTSTK"]
    if df.empty: return None
    r = df[["SYMBOL", "EXPIRY_DT", "CLOSE", "OPEN_INT"]].copy()
    r.columns = ["symbol", "expiry", "close", "oi"]
    for c in ("open", "high", "low", "settle"): r[c] = float("nan")
    return r

def parse_old_full(df):
    if "INSTRUMENT" in df.columns:
        df = df[df["INSTRUMENT"].isin(["FUTSTK", "FUTIDX"])]
    r = df[["SYMBOL", "EXPIRY_DT", "OPEN", "HIGH", "LOW", "CLOSE", "SETTLE_PR", "OPEN_INT"]].copy()
    r.columns = ["symbol", "expiry", "open", "high", "low", "close", "settle", "oi"]
    return r

def parse_new(df):
    df = df[df["FinInstrmTp"].isin(["STF", "IDF"])]
    r = df[["TckrSymb", "XpryDt", "OpnPric", "HghPric", "LwPric", "ClsPric", "SttlmPric", "OpnIntrst"]].copy()
    r.columns = ["symbol", "expiry", "open", "high", "low", "close", "settle", "oi"]
    return r

print("loading old stk cache ...", flush=True)
frames += load_dir("/tmp/bhav_cache_stk", parse_old_stk)
print("loading 2018 ...", flush=True)
frames += load_dir(f"{BASE}/cache_2018", parse_old_full)
print("loading idx ...", flush=True)
frames += load_dir(f"{BASE}/cache_idx", parse_old_full)
print("loading new ...", flush=True)
frames += load_dir(f"{BASE}/cache_new", parse_new)

panel = pd.concat(frames, ignore_index=True)
panel["date"] = pd.to_datetime(panel["date"])
panel["expiry"] = pd.to_datetime(panel["expiry"], format="mixed", dayfirst=True)
# later sources override earlier (richer columns / corrected data)
panel = panel.drop_duplicates(subset=["date", "symbol", "expiry"], keep="last")
panel = panel.sort_values(["symbol", "date", "expiry"]).reset_index(drop=True)
panel.to_csv(f"{BASE}/panel.csv.gz", index=False, compression="gzip")
print(f"panel: {len(panel)} rows, {panel['symbol'].nunique()} symbols, "
      f"{panel['date'].min().date()} -> {panel['date'].max().date()}")
print(panel.groupby(panel["date"].dt.year).size())
