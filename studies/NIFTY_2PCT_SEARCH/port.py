import pandas as pd, numpy as np, sys
D=pd.read_parquet("daily_long.parquet"); D=D[~D.sym.str.startswith("^")]
C=D.pivot_table(index="date",columns="sym",values="Close")
def sim(f,slots,lev,cost=0.001,start="2010-01-01"):
    T=pd.read_parquet(f); T=T[~T.sym.str.startswith("^")&(T.ent>=start)].sort_values("ent")
    eq=1.0; open_=[]; curve={}; taken=[]
    dates=C.index[C.index>=start]
    byent=T.groupby("ent")
    for d in dates:
        # mark to market
        if open_:
            r=0
            for p in open_:
                px=C.at[d,p["sym"]]
                if not np.isnan(px): r+=p["w"]*(px/p["last"]-1); p["last"]=px
            eq*=1+r*lev
        # exits at today's close
        for p in [p for p in open_ if p["exit"]==d]:
            eq*=1-p["w"]*lev*cost; open_.remove(p); taken.append(p)
        # entries at today's close
        if d in byent.groups:
            for _,t in byent.get_group(d).iterrows():
                if len(open_)<slots and t.sym not in [p["sym"] for p in open_]:
                    open_.append(dict(sym=t.sym,exit=t.exit,last=t.ep,w=1/slots,g=t.g))
        curve[d]=eq
    s=pd.Series(curve); r=s.pct_change().dropna(); yrs=len(s)/248
    g=pd.Series([p["g"] for p in taken])
    return dict(file=f.split("tr2_")[1][:-8],slots=slots,lev=lev,trades=len(taken),win=(g>0).mean().round(3),CAGR=round(s.iloc[-1]**(1/yrs)-1,3),
                per_day=round(r.mean(),4),maxDD=round((s/s.cummax()-1).min(),3),worst_day=round(r.min(),3),
                y2020_26=round(s.iloc[-1]/s.loc[:"2019-12-31"].iloc[-1]-1,2) if start<"2020" else None), s
res=[]
for f in ("tr2_F2_profit20_0.08.parquet","tr2_F0_profit20_0.08.parquet","tr2_F2_profit10_0.08.parquet"):
    for slots,lev in ((5,1),(10,1),(5,3),(10,5)):
        r,s=sim(f,slots,lev); res.append(r)
        if f.startswith("tr2_F2_profit20") and slots==5 and lev==3: s.to_csv("curve_F2_5x3.csv")
pd.set_option("display.width",250); print(pd.DataFrame(res).to_string(index=False))
