import pandas as pd, numpy as np
df=pd.read_csv("ohlc.csv",parse_dates=["date"])
IS=("2026-01-01","2026-06-30"); OOS=("2026-07-01","2026-10-09")
C_INTRA=0.0010; C_SWING=0.0025   # round-trip cost+slippage
out=[]; opp=[]
for s,x in df.groupby("sym"):
    if s=="^NSEI": continue
    x=x.set_index("date").sort_index()
    o,h,l,c=x.Open,x.High,x.Low,x.Close
    pc=c.shift(1); r1=pc/c.shift(2)-1
    ma20=c.rolling(20).mean().shift(1); ma50=c.rolling(50).mean().shift(1)
    atr=(pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(1)).rolling(14).mean().shift(1)/pc
    hi20=h.rolling(20).max().shift(1); lo20=l.rolling(20).min().shift(1)
    y=x.loc["2026"]
    opp.append(dict(sym=s,up2=((y.High/y.Open-1)>=.02).mean(),dn2=((y.Low/y.Open-1)<=-.02).mean(),
                    absret=(y.Close/y.Close.shift(1)-1).abs().mean(),ytd=y.Close.iloc[-1]/y.Close.iloc[0]-1))
    def intraday(sig,side,tgt,stp):
        # stop-first when both touched (conservative on daily bars)
        if side>0: fav=h/o-1; adv=1-l/o; cl=c/o-1
        else: fav=1-l/o; adv=h/o-1; cl=1-c/o
        pnl=np.where(adv>=stp,-stp,np.where(fav>=tgt,tgt,cl))-C_INTRA
        return pd.Series(np.where(sig,pnl,np.nan),index=x.index)
    rules={
     "trend_long":(pc>ma20)&(ma20>ma50)&(r1>0),
     "trend_short":(pc<ma20)&(ma20<ma50)&(r1<0),
     "gapup_go":(o/pc-1>0.005)&(pc>ma20),
     "gapdn_go":(o/pc-1<-0.005)&(pc<ma20),
     "gapdn_fade":(o/pc-1<-0.015),
     "brk20_long":(pc>=hi20*0.995),
     "highvol_long":(atr>0.02)&(pc>ma20),
    }
    for name,sig in rules.items():
        side=-1 if ("short" in name or "dn_go" in name) else 1
        for tgt in (0.02,0.03):
            for stp in (0.01,0.015,0.02):
                p=intraday(sig.fillna(False),side,tgt,stp)
                for per,(a,b) in (("IS",IS),("OOS",OOS)):
                    q=p.loc[a:b].dropna()
                    out.append(dict(sym=s,rule=name,tgt=tgt,stp=stp,per=per,n=len(q),
                        mean=q.mean() if len(q) else np.nan,win=(q>0).mean() if len(q) else np.nan,
                        hit2=(q>=0.02-C_INTRA-1e-9).mean() if len(q) else np.nan,
                        days=len(x.loc[a:b])))
    # swing: Donchian 20 breakout, exit on 10-day low or 2*ATR stop, long only (cash)
    pos=0; entry=0; stop=0; tr=[]
    lo10=l.rolling(10).min().shift(1)
    for i in range(60,len(x)):
        d=x.index[i]
        if pos==0 and c.iloc[i-1]>hi20.iloc[i-1]:
            pos=1; entry=o.iloc[i]; stop=entry*(1-2*atr.iloc[i]); ed=d
        elif pos==1:
            ex=None
            if l.iloc[i]<=stop: ex=min(o.iloc[i],stop)
            elif c.iloc[i]<lo10.iloc[i]: ex=c.iloc[i]
            if ex: tr.append(dict(sym=s,entry=ed,exit=d,ret=ex/entry-1-C_SWING,hold=(d-ed).days)); pos=0
    pd.DataFrame(tr).to_csv(f"swing_{s}.csv",index=False) if tr else None
R=pd.DataFrame(out); R.to_csv("intraday_grid.csv",index=False)
pd.DataFrame(opp).sort_values("up2",ascending=False).to_csv("opportunity.csv",index=False)
