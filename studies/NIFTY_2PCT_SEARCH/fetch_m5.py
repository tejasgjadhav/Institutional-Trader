# Upstox 1-min -> 5-min bars (with volume) per symbol, 2022-01 -> 2026-10. Failures listed, never silent.
import sys, os, time, requests, urllib.parse, pandas as pd
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,"/Users/sayali/files/institutional-trader")
from engine.instruments import to_instrument_key
P=pd.read_csv("/Users/sayali/files/institutional-trader/studies/monthly_fut/panel.csv.gz",usecols=["symbol"])
syms=sorted(set(P.symbol)-{"NIFTY","BANKNIFTY","FINNIFTY"})
keys={s:to_instrument_key(s) for s in syms}; keys["NIFTY"]="NSE_INDEX|Nifty 50"
months=pd.date_range("2022-01-01","2026-10-01",freq="MS")
def job(a):
    sym,m=a; e=min(m+pd.offsets.MonthEnd(0),pd.Timestamp("2026-10-09"))
    url=f"https://api.upstox.com/v3/historical-candle/{urllib.parse.quote(keys[sym],safe='')}/minutes/1/{e:%Y-%m-%d}/{m:%Y-%m-%d}"
    for k in range(5):
        try:
            r=requests.get(url,timeout=30,headers={"Accept":"application/json","User-Agent":"Mozilla/5.0"})
            if r.status_code==200: return ("ok",sym,r.json()["data"]["candles"])
            if r.status_code==429: time.sleep(2+2*k); continue
            err=r.status_code
        except Exception as ex: err=repr(ex)[:60]
        time.sleep(1+k)
    return ("fail",sym,f"{m:%Y-%m} {err}")
def agg(c):
    x=pd.DataFrame(c,columns=["ts","o","h","l","c","v","oi"]); x["ts"]=pd.to_datetime(x.ts).dt.tz_localize(None)
    x=x.set_index("ts").sort_index()
    return x.resample("5min",label="left",closed="left").agg({"o":"first","h":"max","l":"min","c":"last","v":"sum"}).dropna()
fails=[]
for sym in list(keys):
    f=f"m5/{sym}.parquet"
    if os.path.exists(f): continue
    with ThreadPoolExecutor(8) as ex: res=list(ex.map(job,[(sym,m) for m in months]))
    bad=[r[2] for r in res if r[0]=="fail"]
    if bad: fails+= [f"{sym} {b}" for b in bad]; continue      # never save a partial symbol
    parts=[agg(r[2]) for r in res if r[2]]
    if parts: pd.concat(parts).sort_index().to_parquet(f)
print("symbols",len(keys),"| saved",len(os.listdir("m5")),"| failures",len(fails),fails[:5])
