"""One-time compaction of the NSE FO bhavcopy CSV cache into a single parquet.

The CSV loader used by the older studies calls pd.to_datetime() once PER ROW, which costs
~3 s/file -> ~75 min for the 1,500-file cache, every run. Vectorising the date parse and
keeping only the UNIVERSE symbols' option rows cuts that to a few minutes ONCE; afterwards
any study loads /tmp/bhav_stk.parquet in seconds.

Columns kept: SYM, EXP (iso date str), STRIKE, TYP, CLOSE, OI, DAY (iso date str).
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys, glob, time
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from engine.config import UNIVERSE

CACHE = "/tmp/bhav_cache_stk"
OUT = "/tmp/bhav_stk.pkl"
SYMS = {s.replace(".NS", "") for s in UNIVERSE}
USE = ["SYMBOL", "EXPIRY_DT", "STRIKE_PR", "OPTION_TYP", "CLOSE", "OPEN_INT"]

files = sorted(glob.glob(f"{CACHE}/*.csv"))
print(f"compacting {len(files)} files, {len(SYMS)} universe symbols…", flush=True)
parts = []; t0 = time.time()
for i, f in enumerate(files):
    day = os.path.basename(f)[:-4]
    try:
        df = pd.read_csv(f, usecols=lambda c: c.strip() in USE)
    except Exception:
        continue
    df.columns = [c.strip() for c in df.columns]
    if df.empty or "OPTION_TYP" not in df: continue
    df["SYMBOL"] = df["SYMBOL"].astype(str).str.strip()
    df["OPTION_TYP"] = df["OPTION_TYP"].astype(str).str.strip()
    df = df[df["OPTION_TYP"].isin(["CE", "PE"]) & df["SYMBOL"].isin(SYMS)]
    if df.empty: continue
    exp = pd.to_datetime(df["EXPIRY_DT"], errors="coerce")       # vectorised, not per-row
    df = df[exp.notna()].copy(); exp = exp[exp.notna()]
    df["EXP"] = exp.dt.strftime("%Y-%m-%d")
    out = pd.DataFrame({
        "SYM": df["SYMBOL"].astype("category"),
        "EXP": df["EXP"],
        "STRIKE": pd.to_numeric(df["STRIKE_PR"], errors="coerce").astype("float32"),
        "TYP": df["OPTION_TYP"].astype("category"),
        "CLOSE": pd.to_numeric(df["CLOSE"], errors="coerce").astype("float32"),
        "OI": pd.to_numeric(df["OPEN_INT"], errors="coerce").fillna(0).astype("float32"),
        "DAY": day,
    })
    parts.append(out.dropna(subset=["STRIKE", "CLOSE"]))
    if i % 200 == 0:
        print(f"  {i}/{len(files)}  {time.time()-t0:.0f}s  rows so far {sum(len(p) for p in parts):,}", flush=True)

big = pd.concat(parts, ignore_index=True)
big["SYM"] = big["SYM"].astype("category"); big["TYP"] = big["TYP"].astype("category")
big["EXP"] = big["EXP"].astype("category"); big["DAY"] = big["DAY"].astype("category")
big.to_pickle(OUT)
print(f"\nwrote {OUT}: {len(big):,} rows, {big.DAY.nunique()} days "
      f"{min(big.DAY.cat.categories)} -> {max(big.DAY.cat.categories)}, {big.SYM.nunique()} symbols, {time.time()-t0:.0f}s")
print("DONE-PARQUET")
