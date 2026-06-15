import sys, json, gzip, requests
from datetime import datetime, timedelta
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from engine.data_fetcher import fetch_upstox_historical

URL="https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
raw=json.loads(gzip.decompress(requests.get(URL,timeout=60).content))
futs={}
for i in raw:
    if i.get("segment")=="NSE_FO" and i.get("instrument_type")=="FUT":
        nm=i.get("name") or i.get("underlying_symbol") or ""
        if nm in ("NIFTY","BANKNIFTY"):
            futs.setdefault(nm,[]).append({"key":i["instrument_key"],"expiry":int(i["expiry"]),
                "ts":i.get("trading_symbol",""),"lot":i.get("lot_size")})
def tdays(n):
    days,d=[],datetime.now()-timedelta(days=1)
    while len(days)<n:
        if d.weekday()<5: days.append(d.date())
        d-=timedelta(days=1)
    return sorted(days)
days=tdays(8)
for nm in ("NIFTY","BANKNIFTY"):
    cs=sorted(futs.get(nm,[]),key=lambda c:c["expiry"])
    day_ms=int(datetime(days[-1].year,days[-1].month,days[-1].day).timestamp()*1000)
    near=[c for c in cs if c["expiry"]>=day_ms]
    print(f"\n=== {nm} FUT === contracts={len(cs)} near={near[0]['ts'] if near else 'NONE'}")
    if near:
        k=near[0]["key"]
        df=fetch_upstox_historical(k,unit="minutes",interval=5,
            from_date=days[-1].strftime("%Y-%m-%d"),to_date=days[-1].strftime("%Y-%m-%d"))
        print(f"  key={k} bars={len(df)} volsum={df['Volume'].sum() if not df.empty else 'NA'}")
        if not df.empty: print(f"  head vol={list(df['Volume'].head(3))}")
