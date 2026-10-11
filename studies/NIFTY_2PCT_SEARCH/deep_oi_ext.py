# Signals on yfinance-adjusted cash; OI = total futures OI across expiries; P&L on real front-month futures.
import pandas as pd, numpy as np, yfinance as yf, warnings, os; warnings.filterwarnings("ignore")
from mr import rsi
COST=0.0010; ROLL=0.0006; SL=0.08
P=pd.read_csv("panel_ext.csv.gz",parse_dates=["date","expiry"])
P=P[(P.close>0)&(P.expiry>=P.date)]
syms=sorted(set(P.symbol)-{"NIFTY","BANKNIFTY","FINNIFTY"})
if not os.path.exists("daily_fo_ext.parquet"):
    d=yf.download([s+".NS" for s in syms]+["^NSEI"],start="2016-06-01",end="2026-10-10",group_by="ticker",auto_adjust=True,progress=False,threads=True)
    pd.concat([d[t][["Open","High","Low","Close"]].dropna().assign(sym=t.replace(".NS","")) for t in d.columns.get_level_values(0).unique()]).rename_axis("date").to_parquet("daily_fo_ext.parquet")
D=pd.read_parquet("daily_fo_ext.parquet")
N=D[D.sym=="^NSEI"].Close; nreg=(N>N.rolling(200).mean())
OI=P.groupby(["symbol","date"]).oi.sum()
out=[]
for sym in syms:
    x=D[D.sym==sym]; f=P[P.symbol==sym]
    if len(x)<300 or f.empty: continue
    fut={d:g.sort_values("expiry")[["expiry","close"]].values for d,g in f.groupby("date")}
    oi=OI.loc[sym].reindex(x.index)
    C=x.Close; c=C.values; s200=C.rolling(200).mean().values; s50=C.rolling(50).mean().values
    m20=C.rolling(20).mean(); sd=C.rolling(20).std(); lb=(m20-2*sd).values; ub=(m20+2*sd).values; r2=rsi(C,2).values
    oi1=(oi/oi.shift(1)-1).values; oi3=(oi/oi.shift(3)-1).values; r3=(C/C.shift(3)-1).values
    vol=C.pct_change().rolling(20).std().values; bad=np.abs(C.pct_change().values)>0.18
    L=(c>s200)&(s50>s200)&(r2<10); S=(c<s200)&(s50<s200)&(r2>90)
    idx=x.index
    for side,sig,band in ((1,L,lb),(-1,S,ub)):
        i=200
        while i<len(c)-1:
            d=idx[i]
            if not sig[i] or d not in fut: i+=1; continue
            ch=fut[d]; k=1 if ((ch[0][0]-d).days<=2 and len(ch)>1) else 0
            exp,last=ch[k]; cum=0.0; costs=COST; j=i+1; res=None
            while j<len(c):
                dj=idx[j]
                if dj not in fut: j+=1; continue
                row=[r for r in fut[dj] if r[0]==exp]
                if not row: break
                px=row[0][1]
                if abs(px/last-1)>0.18: break
                cum=(1+cum)*((px/last) if side>0 else (last/px))-1; last=px
                if cum>0 or cum<=-SL or j-i>=20 or bad[j]: res=(dj,cum,j-i); break
                if dj==exp:
                    nxt=[r for r in fut[dj] if r[0]>exp]
                    if not nxt: res=(dj,cum,j-i); break
                    exp,last=nxt[0]; costs+=ROLL
                j+=1
            if res:
                out.append(dict(sym=sym,side=side,ent=d,exit=res[0],g=res[1]-costs,hold=res[2],bb=bool(side*(band[i]-c[i])>0),
                    oi1=oi1[i],oi3=oi3[i],r3=r3[i],vol=vol[i],nreg=bool(nreg.reindex([d]).iloc[0]) if d in nreg.index else np.nan))
            i=j+1
T=pd.DataFrame(out); T.to_parquet("deep_trades_ext.parquet")
print(len(T), T.groupby("side").g.agg(["count","mean",lambda s:(s>0).mean()]).round(4).to_string())
