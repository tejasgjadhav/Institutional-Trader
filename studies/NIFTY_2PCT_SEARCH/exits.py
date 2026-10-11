import pandas as pd, numpy as np, itertools
from multiprocessing import Pool
COST=0.001
TG=[0.01,0.015,0.02,0.03,None]; ST=[0.005,0.0075,0.01,0.015,0.02]; TR=[None,0.0075,0.01]; BE=[False,True]; TM=["11:00","13:00","15:15"]
CFG=list(itertools.product(TG,ST,TR,BE,TM))
def prep():
    P=pd.read_csv("picks.csv",parse_dates=["date"]); X=pd.read_parquet("picks_m1.parquet")
    X=X.set_index("ts").sort_index(); out=[]
    for (sym,d),g in X.groupby(["sym",X.index.normalize()]):
        g=g.between_time("09:16","15:15")
        if len(g)<300: continue
        for r in P[(P.sym==sym)&(P.date==d)].itertuples():
            out.append((r.date,r.sym,r.side,int(r.rank),g.o.values,g.h.values,g.l.values,g.index.strftime("%H:%M").values))
    return out
def run(p):
    date,sym,side,rank,o,h,l,tm=p; e=o[0]
    if side=="L": fav=h/e-1; adv=l/e-1; op=o/e-1
    else: fav=1-l/e; adv=1-h/e; op=1-o/e
    runmax=np.maximum.accumulate(np.r_[0,fav[:-1]])    # best favourable excursion before this bar
    res=[]
    for tg,st,tr,be,T in CFG:
        tidx=np.searchsorted(tm,T); stop=np.full(len(o),-st)
        if tr is not None: stop=np.maximum(stop,runmax-tr)
        if be: stop=np.where(runmax>=0.01,np.maximum(stop,0.0),stop)
        hs=np.nonzero(adv[:tidx]<=stop[:tidx])[0]; ht=np.nonzero(fav[:tidx]>=tg)[0] if tg else np.array([],int)
        i_s=hs[0] if len(hs) else 10**9; i_t=ht[0] if len(ht) else 10**9
        if i_s<=i_t and i_s<10**9: pnl=min(op[i_s],stop[i_s])
        elif i_t<10**9: pnl=tg
        else: pnl=op[min(tidx,len(o)-1)]
        res.append(pnl-COST)
    return (date,sym,side,rank,res)
if __name__=="__main__":
    data=prep()
    with Pool(4) as pool: R=pool.map(run,data,chunksize=50)
    M=pd.DataFrame([r[4] for r in R],columns=[str(c) for c in CFG])
    meta=pd.DataFrame([r[:4] for r in R],columns=["date","sym","side","rank"]); pd.concat([meta,M],axis=1).to_parquet("exit_grid.parquet")
    print("trades",len(meta))
