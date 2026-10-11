import sys, os, json, time, requests, urllib.parse, pandas as pd
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,"/Users/sayali/files/institutional-trader")
from engine.instruments import to_instrument_key
O=pd.read_parquet("pick_oos.parquet")
P=[]
for side in ("L","S"):
    t=O.sort_values("p"+side,ascending=False).groupby(level=0).head(3)[["sym","p"+side]].rename(columns={"p"+side:"p"})
    t["side"]=side; t["rank"]=t.groupby(level=0).p.rank(ascending=False,method="first"); P.append(t)
P=pd.concat(P).rename_axis("date").reset_index(); P.to_csv("picks.csv",index=False)
need={(r.sym,r.date.strftime("%Y-%m")) for r in P.itertuples()}
days={}
for r in P.itertuples(): days.setdefault(r.sym,set()).add(r.date.normalize())
keys={s:to_instrument_key(s) for s in days}
def job(a):
    sym,ym=a; m=pd.Timestamp(ym+"-01"); e=min(m+pd.offsets.MonthEnd(0),pd.Timestamp("2026-10-09"))
    url=f"https://api.upstox.com/v3/historical-candle/{urllib.parse.quote(keys[sym],safe='')}/minutes/1/{e:%Y-%m-%d}/{m:%Y-%m-%d}"
    for k in range(5):
        try:
            r=requests.get(url,timeout=30,headers={"Accept":"application/json","User-Agent":"Mozilla/5.0"})
            if r.status_code==200:
                x=pd.DataFrame(r.json()["data"]["candles"],columns=["ts","o","h","l","c","v","oi"])
                x["ts"]=pd.to_datetime(x.ts).dt.tz_localize(None); x=x[x.ts.dt.normalize().isin(days[sym])]; x["sym"]=sym
                return ("ok",x)
            if r.status_code==429: time.sleep(2+2*k); continue
            err=r.status_code
        except Exception as ex: err=repr(ex)[:60]
        time.sleep(1+k)
    return ("fail",f"{sym} {ym} {err}")
with ThreadPoolExecutor(8) as ex: res=list(ex.map(job,sorted(need)))
fails=[r[1] for r in res if r[0]=="fail"]; X=pd.concat([r[1] for r in res if r[0]=="ok"])
X.drop(columns=["oi"]).to_parquet("picks_m1.parquet")
got=X.groupby("sym").ts.apply(lambda s:s.dt.normalize().nunique()).sum()
print("requests",len(need),"| failures",len(fails),fails[:5],"| pick-days needed",sum(len(v) for v in days.values()),"| got",got)
