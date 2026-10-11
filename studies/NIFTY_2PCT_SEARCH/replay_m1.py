import json, glob, pandas as pd, numpy as np, yfinance as yf, warnings; warnings.filterwarnings("ignore")
PAIRS=[("JIOFIN","trend_short"),("JIOFIN","gapdn_go"),("BAJAJFINSV","trend_short"),("INFY","gapdn_go"),("MARUTI","gapdn_go"),
       ("KOTAKBANK","gapdn_go"),("EICHERMOT","gapdn_go"),("SHRIRAMFIN","gapdn_go"),("WIPRO","gapdn_go"),("TMPV","highvol_long"),("KOTAKBANK","highvol_long")]
GEOS=[(t,s) for t in (0.02,0.03) for s in (0.01,0.015,0.02)]; COST=0.0010
def m1(sym):
    rows=[r for f in sorted(glob.glob(f"m1/{sym}_*.json")) for r in json.load(open(f))]
    x=pd.DataFrame(rows,columns=["ts","o","h","l","c","v","oi"]); x["ts"]=pd.to_datetime(x.ts).dt.tz_localize(None)
    return x.sort_values("ts").drop_duplicates("ts").set_index("ts")
syms=sorted({p[0] for p in PAIRS})
D=yf.download([s+".NS" for s in syms],start="2021-09-01",end="2026-10-10",group_by="ticker",auto_adjust=True,progress=False)
res=[]
for sym,rule in PAIRS:
    d=D[sym+".NS"].dropna(); o,h,l,c=d.Open,d.High,d.Low,d.Close; pc=c.shift(1)
    ma20=c.rolling(20).mean().shift(1); ma50=c.rolling(50).mean().shift(1); r1=pc/c.shift(2)-1
    atr=pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(1).rolling(14).mean().shift(1)/pc
    sig={"trend_short":(pc<ma20)&(ma20<ma50)&(r1<0),"gapdn_go":(o/pc-1<-0.005)&(pc<ma20),"highvol_long":(atr>0.02)&(pc>ma20)}[rule]
    side=1 if rule=="highvol_long" else -1
    days=set(sig[sig.fillna(False)].index.normalize())
    x=m1(sym); x["day"]=x.index.normalize()
    for day,b in x[x.day.isin(days)].groupby("day"):
        b=b.between_time("09:16","15:15")
        if len(b)<300: continue
        ent=b.o.iloc[0]; body=b.iloc[:-1]; exit_px=b.o.iloc[-1]   # 15:15 bar open
        fav=(body.h/ent-1) if side>0 else (1-body.l/ent); adv=(1-body.l/ent) if side>0 else (body.h/ent-1)
        for t,s in GEOS:
            hit_s=np.argmax(adv.values>=s) if (adv.values>=s).any() else 10**9
            hit_t=np.argmax(fav.values>=t) if (fav.values>=t).any() else 10**9
            if hit_s<=hit_t and hit_s<10**9: p=-s
            elif hit_t<10**9: p=t
            else: p=side*(exit_px/ent-1)
            res.append(dict(sym=sym,rule=rule,day=day,tgt=t,stp=s,ret=p-COST))
R=pd.DataFrame(res); R["yr"]=R.day.dt.year; R.to_csv("m1_trades.csv",index=False)
pd.set_option("display.width",220)
y=R[(R.tgt==0.02)&(R.stp==0.015)].groupby(["sym","rule","yr"]).ret.agg(["count","mean"]).unstack("yr")
print("Net per trade on the stock, target 2% / stop 1.5% (count, mean):\n",y.round(4).to_string())
a=R.groupby(["sym","rule","tgt","stp"]).ret.mean().groupby(["sym","rule"]).agg(["min","max"])
a["pre26_mean"]=R[R.yr<2026].groupby(["sym","rule"]).ret.mean(); a["pre26_n"]=R[(R.yr<2026)&(R.tgt==.02)&(R.stp==.015)].groupby(["sym","rule"]).size()
a["y26_mean"]=R[R.yr==2026].groupby(["sym","rule"]).ret.mean()
print("\nAcross all 6 geometries:\n",a.round(4).to_string())
