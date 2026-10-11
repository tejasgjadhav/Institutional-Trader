# Upstox v3 1-min candles, month by month. A failed fetch is recorded and never treated as "no data".
import requests, json, os, sys, time, urllib.parse, pandas as pd
from concurrent.futures import ThreadPoolExecutor
KEYS={"JIOFIN":"NSE_EQ|INE758E01017","INFY":"NSE_EQ|INE009A01021","MARUTI":"NSE_EQ|INE585B01010","KOTAKBANK":"NSE_EQ|INE237A01036","EICHERMOT":"NSE_EQ|INE066A01021","SHRIRAMFIN":"NSE_EQ|INE721A01047","BAJAJFINSV":"NSE_EQ|INE918I01026","WIPRO":"NSE_EQ|INE075A01022","TMPV":"NSE_EQ|INE155A01022"}
months=pd.date_range("2022-01-01","2026-10-01",freq="MS")
def job(sym,m):
    f=f"m1/{sym}_{m:%Y%m}.json"
    if os.path.exists(f): return None
    a=m.strftime("%Y-%m-%d"); b=min(m+pd.offsets.MonthEnd(0),pd.Timestamp("2026-10-09")).strftime("%Y-%m-%d")
    url=f"https://api.upstox.com/v3/historical-candle/{urllib.parse.quote(KEYS[sym],safe='')}/minutes/1/{b}/{a}"
    for k in range(4):
        try:
            r=requests.get(url,timeout=30,headers={"Accept":"application/json"})
            if r.status_code==200 and r.json().get("status")=="success":
                json.dump(r.json()["data"]["candles"],open(f,"w")); return None
            if r.status_code==429: time.sleep(2+3*k); continue
            err=f"{r.status_code} {r.text[:120]}"
        except Exception as e: err=repr(e)
        time.sleep(1+k)
    return f"{sym} {m:%Y-%m}: {err}"
with ThreadPoolExecutor(6) as ex: fails=[x for x in ex.map(lambda a:job(*a),[(s,m) for s in KEYS for m in months]) if x]
print("failures:",len(fails)); print("\n".join(fails[:20]))
