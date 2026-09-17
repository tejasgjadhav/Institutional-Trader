"""1-minute OHLCV fetcher (17-Sep-2026) -> research/m1cache/{SYM}_{YYYY-MM}.csv.gz (persistent; the
old /tmp cache was wiped by the weekly cleanup). Upstox v3 public endpoint, no auth, one month per
call, 3 workers, retry with backoff. Idempotent: existing months are skipped."""
import os, sys, time, gzip, urllib.parse, json, concurrent.futures as cf
import requests, pandas as pd
sys.path.insert(0, ".")
from engine.instruments import to_instrument_key
CACHE = "research/m1cache"
IDX = {"NIFTY": "NSE_INDEX|Nifty 50", "BANKNIFTY": "NSE_INDEX|Nifty Bank", "SENSEX": "BSE_INDEX|SENSEX",
       "FINNIFTY": "NSE_INDEX|Nifty Fin Service", "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
       "NEXT50": "NSE_INDEX|Nifty Next 50"}
SYMS = ["NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY", "NEXT50",
        "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK",
        "KOTAKBANK", "ITC", "LT", "BHARTIARTL", "MARUTI", "TATASTEEL", "JSWSTEEL",
        "SUNPHARMA", "HINDUNILVR", "TITAN", "BAJFINANCE", "ADANIENT", "ONGC",
        "NTPC", "POWERGRID", "COALINDIA", "HINDALCO"]
def key_for(sym):
    return IDX.get(sym) or to_instrument_key(sym + ".NS")
def months(start="2022-01", end="2026-09"):
    y, m = map(int, start.split("-")); ye, me = map(int, end.split("-"))
    while (y, m) <= (ye, me):
        yield f"{y:04d}-{m:02d}"; m += 1
        if m == 13: y, m = y + 1, 1
def fetch(sym, ym):
    out = os.path.join(CACHE, f"{sym}_{ym}.csv.gz")
    if os.path.exists(out): return "cached"
    key = key_for(sym)
    if not key: return "nokey"
    y, m = map(int, ym.split("-"))
    last = (pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
    url = f"https://api.upstox.com/v3/historical-candle/{urllib.parse.quote(key, safe='')}/minutes/1/{last}/{ym}-01"
    for a in range(6):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                cs = r.json().get("data", {}).get("candles", [])
                df = pd.DataFrame(cs, columns=["ts", "o", "h", "l", "c", "v", "oi"])
                df["ts"] = pd.to_datetime(df.ts).dt.tz_localize(None)
                df.sort_values("ts")[["ts", "o", "h", "l", "c", "v"]].to_csv(out, index=False, compression="gzip")
                return f"{len(df)}"
            if r.status_code == 429: time.sleep(5 * (a + 1)); continue
            return f"http{r.status_code}"
        except Exception as e:
            time.sleep(3 * (a + 1))
    return "fail"
if __name__ == "__main__":
    jobs = [(s, ym) for s in SYMS for ym in months()]
    print(f"{len(jobs)} symbol-months", flush=True)
    done = 0; bad = 0
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        for (s, ym), res in zip(jobs, ex.map(lambda j: fetch(*j), jobs)):
            done += 1
            if res in ("fail", "nokey") or res.startswith("http"): bad += 1; print(f"  {s} {ym}: {res}", flush=True)
            if done % 100 == 0: print(f"  {done}/{len(jobs)} ({bad} bad)", flush=True)
    print(f"DONE {done} · bad {bad}", flush=True)
