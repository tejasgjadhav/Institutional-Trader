import pandas as pd, numpy as np, glob, os, warnings; warnings.filterwarnings("ignore")
C_STK=0.0010; C_IDX=0.0003
def load(s):
    x=pd.read_parquet(f"m5/{s}.parquet"); x=x.between_time("09:15","15:25"); x["d"]=x.index.normalize(); return x
def stats(r,nm):
    r=pd.Series(r).dropna()
    out=[]
    for per,a,b in (("2022-23","2022","2023-12-31"),("2024-26","2024","2026-12-31")):
        q=r[(r.index>=a)&(r.index<=b)]
        out.append(f"{per}: n={len(q):5d} win={(q>0).mean():.0%} net/trade={q.mean():+.4f} t={q.mean()/q.std()*np.sqrt(len(q)):+.2f}")
    yr=r.groupby(r.index.year).mean().round(4).to_dict()
    print(f"{nm:44s} | "+" | ".join(out)+f" | by year {yr}")
# ---------- A: Stocks-in-Play ORB (Zarattini/Barbon/Aziz) ----------
def orb(mins, topn):
    rows=[]
    for f in glob.glob("m5/*.parquet"):
        s=os.path.basename(f)[:-8]
        if s=="NIFTY": continue
        x=load(s); n=mins//5
        dly=x.groupby("d").agg(h=("h","max"),l=("l","min"),c=("c","last"))
        tr=pd.concat([dly.h-dly.l,(dly.h-dly.c.shift()).abs(),(dly.l-dly.c.shift()).abs()],axis=1).max(1)
        atr=tr.rolling(14).mean().shift(1)
        for d,g in x.groupby("d"):
            if len(g)<70 or d not in atr.index or np.isnan(atr[d]): continue
            orr=g.iloc[:n]; rest=g.iloc[n:]
            rows.append(dict(sym=s,d=d,o=orr.o.iloc[0],h=orr.h.max(),l=orr.l.min(),c=orr.c.iloc[-1],v=orr.v.sum(),atr=atr[d],
                             ph=rest.h.values,pl=rest.l.values,po=rest.o.values,pc=rest.c.values))
    D=pd.DataFrame(rows).sort_values(["sym","d"])
    D["rv"]=D.v/D.groupby("sym").v.transform(lambda v:v.rolling(14).mean().shift(1))
    D=D[(D.rv>=1)&(D.c!=D.o)]
    D=D.sort_values("rv",ascending=False).groupby("d").head(topn)
    res={}
    for r in D.itertuples():
        side=1 if r.c>r.o else -1; lvl=r.h if side>0 else r.l; stop_d=0.10*r.atr
        hit=np.nonzero(r.ph>=lvl)[0] if side>0 else np.nonzero(r.pl<=lvl)[0]
        if not len(hit): continue
        i=hit[0]; e=max(lvl,r.po[i]) if side>0 else min(lvl,r.po[i]); st=e-side*stop_d
        pnl=None
        for j in range(i,len(r.pc)):
            if (side>0 and r.pl[j]<=st) or (side<0 and r.ph[j]>=st):
                px=st if j==i else (min(r.po[j],st) if side>0 else max(r.po[j],st)); pnl=side*(px/e-1); break
        if pnl is None: pnl=side*(r.pc[-1]/e-1)
        res.setdefault(r.d,[]).append(pnl-C_STK)
    return pd.Series({d:v for d,l in res.items() for v in l} if False else None) if False else pd.Series([v for d in sorted(res) for v in res[d]],index=[d for d in sorted(res) for _ in res[d]])
# ---------- B: noise-boundary momentum on NIFTY (Zarattini/Aziz/Barbon) ----------
def noise(step):
    x=load("NIFTY"); days=sorted(x.d.unique()); pc=x.groupby("d").c.last().shift(1)
    x["tod"]=x.index.strftime("%H:%M"); op=x.groupby("d").o.transform("first"); x["mv"]=(x.c/op-1).abs()
    piv=x.pivot_table(index="d",columns="tod",values="mv"); sig=piv.rolling(14).mean().shift(1)
    out={}
    dec=[t for t in piv.columns if t>="09:40" and t<="15:10"][::step//5]
    for d,g in x.groupby("d"):
        if d not in sig.index or sig.loc[d].isna().all() or np.isnan(pc.get(d,np.nan)): continue
        o=g.o.iloc[0]; g=g.set_index("tod"); pos=0; e=0; pnl=0; trades=0
        for t in dec:
            if t not in g.index: continue
            px=g.at[t,"c"]; s=sig.at[d,t]; ub=max(o,pc[d])*(1+s); lb=min(o,pc[d])*(1-s)
            want=1 if px>ub else (-1 if px<lb else (pos if (pos>0 and px>ub) or (pos<0 and px<lb) else 0))
            if want!=pos:
                if pos: pnl+=pos*(px/e-1)-C_IDX
                if want: e=px; trades+=1
                pos=want
        if pos: pnl+=pos*(g.c.iloc[-1]/e-1)-C_IDX
        if trades: out[d]=pnl
    return pd.Series(out)
# ---------- C: first-30-min predicts last-30-min (Gao/Han/Li/Zhou) on NIFTY ----------
def gao():
    x=load("NIFTY"); pc=x.groupby("d").c.last().shift(1); out={}
    for d,g in x.groupby("d"):
        g=g.set_index(g.index.strftime("%H:%M"))
        if np.isnan(pc.get(d,np.nan)) or "09:40" not in g.index or "15:00" not in g.index: continue
        r1=g.at["09:40","c"]/pc[d]-1; side=1 if r1>0 else -1
        out[d]=side*(g.c.iloc[-1]/g.at["15:00","o"]-1)-C_IDX
    return pd.Series(out)
if __name__=="__main__":
    stats(gao(),"C  Gao: first 30m -> last 30m, NIFTY")
    stats(noise(30),"B  Noise boundary, NIFTY, 30-min checks")
    stats(noise(15),"B  Noise boundary, NIFTY, 15-min checks")
    for m in (5,15):
        for k in (20,5): stats(orb(m,k),f"A  Stocks-in-Play ORB {m}-min, top {k}")
