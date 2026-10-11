# Dip-buy (C>SMA200, SMA50>SMA200, RSI2<10, C<lower BB20) with signals on adjusted cash,
# P&L on real front-month futures closes from bhavcopy. Exit at first futures close with
# cumulative P&L > 0, 20-day time stop, -8% disaster stop on close. Roll at expiry close.
import pandas as pd, numpy as np
from mr import rsi
COST=0.0010; ROLL=0.0006
P=pd.read_csv("/Users/sayali/files/institutional-trader/studies/monthly_fut/panel.csv.gz",parse_dates=["date","expiry"])
P=P[(P.close>0)&(P.expiry>=P.date)]
D=pd.read_parquet("daily_long.parquet")
out=[]
for sym,x in D.groupby("sym"):
    f=P[P.symbol==sym]
    if f.empty: continue
    fut={d:g.sort_values("expiry")[["expiry","close"]].values for d,g in f.groupby("date")}
    C=x.Close; c=C.values; s200=C.rolling(200).mean().values; s50=C.rolling(50).mean().values
    lb=(C.rolling(20).mean()-2*C.rolling(20).std()).values; r2=rsi(C,2).values
    bad=np.abs(C.pct_change().values)>0.18
    sig=(c>s200)&(s50>s200)&(r2<10)&(c<lb); idx=x.index; i=200
    while i<len(c)-1:
        d=idx[i]
        if not sig[i] or d not in fut: i+=1; continue
        ch=fut[d]; k=0
        if (ch[0][0]-d).days<=2 and len(ch)>1: k=1     # avoid entering a contract that expires in 2 days
        exp,ep=ch[k]; cum=0.0; last=ep; costs=COST; j=i+1; res=None
        while j<len(c):
            dj=idx[j]
            if dj not in fut: j+=1; continue
            row=[r for r in fut[dj] if r[0]==exp]
            if not row: break
            px=row[0][1]
            if abs(px/last-1)>0.18: res=None; break   # unadjusted split/bonus in bhavcopy -> drop trade
            cum=(1+cum)*(px/last)-1; last=px
            hold=j-i
            if cum>0 or cum<=-0.08 or hold>=20 or bad[j]: res=(dj,cum,hold); break
            if dj==exp:   # roll into next contract at the same close
                nxt=[r for r in fut[dj] if r[0]>exp]
                if not nxt: res=(dj,cum,hold); break
                exp,last=nxt[0]; costs+=ROLL
            j+=1
        if res: out.append(dict(sym=sym,ent=d,exit=res[0],g=res[1]-costs,hold=res[2]))
        i=j+1
T=pd.DataFrame(out); T.to_csv("fut_trades.csv",index=False); T["yr"]=T.ent.dt.year
print("All:",len(T),"win",round((T.g>0).mean(),3),"mean",round(T.g.mean(),4),"worst",round(T.g.min(),3),"hold",round(T.hold.mean(),1))
print(T.groupby("yr").g.agg(n="count",win=lambda s:(s>0).mean(),mean="mean",worst="min").round(3).to_string())
