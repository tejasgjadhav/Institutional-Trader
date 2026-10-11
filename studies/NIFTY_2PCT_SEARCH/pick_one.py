# Each day at the open, rank ~100 F&O stocks; trade the top pick with +2% target / -1% stop, exit at close.
# Daily bars, conservative: if the stop and target both trade the same day, count the stop.
import pandas as pd, numpy as np, warnings; warnings.filterwarnings("ignore")
from sklearn.ensemble import HistGradientBoostingClassifier
D=pd.read_parquet("daily_fo_ext.parquet"); COST=0.001
N=D[D.sym=="^NSEI"]; ngap=(N.Open/N.Close.shift(1)-1).rename("ngap"); nr1=(N.Close/N.Close.shift(1)-1).shift(1).rename("nr1")
F=[]
for s,x in D[D.sym!="^NSEI"].groupby("sym"):
    o,h,l,c=x.Open,x.High,x.Low,x.Close; pc=c.shift(1)
    tr=pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(1)
    f=pd.DataFrame(dict(sym=s,gap=o/pc-1,r1=pc/c.shift(2)-1,r5=pc/c.shift(6)-1,r20=pc/c.shift(21)-1,
        d20=pc/c.rolling(20).mean().shift(1)-1,d200=pc/c.rolling(200).mean().shift(1)-1,atr=(tr.rolling(14).mean()/pc).shift(1),
        prng=((h-l)/pc).shift(1),ploc=((c-l)/(h-l)).shift(1),
        upT=h/o-1>=0.02,upS=l/o-1<=-0.01,dnT=l/o-1<=-0.02,dnS=h/o-1>=0.01,oc=c/o-1),index=x.index)
    F.append(f)
F=pd.concat(F).join(ngap).join(nr1); F["rgap"]=F.gap-F.ngap; F["gap_atr"]=F.gap/F.atr
F=F.replace([np.inf,-np.inf],np.nan).dropna(); F=F[F.index>="2018-01-01"]
F["pnlL"]=np.where(F.upS,-0.01,np.where(F.upT,0.02,F.oc))-COST
F["pnlS"]=np.where(F.dnS,-0.01,np.where(F.dnT,0.02,-F.oc))-COST
F["winL"]=F.upT&~F.upS; F["winS"]=F.dnT&~F.dnS
X=["gap","r1","r5","r20","d20","d200","atr","prng","ploc","ngap","nr1","rgap","gap_atr"]
IS=F[F.index<"2023-01-01"]; OOS=F[F.index>="2023-01-01"].copy()
for side in ("L","S"):
    m=HistGradientBoostingClassifier(max_iter=200,learning_rate=0.05,max_leaf_nodes=15,min_samples_leaf=200).fit(IS[X],IS["win"+side])
    OOS["p"+side]=m.predict_proba(OOS[X])[:,1]
    print(f"\n=== {'LONG' if side=='L' else 'SHORT'}: base rate of a clean 2% win, any stock any day: {OOS['win'+side].mean():.1%}")
    for k in (1,3):
        top=OOS.sort_values("p"+side,ascending=False).groupby(level=0).head(k)
        g=top["pnl"+side]; yr=g.groupby(g.index.year).mean()
        print(f"top-{k} pick/day: n={len(g)} | clean 2% win {top['win'+side].mean():.1%} | stopped {(g<=-0.0109).mean():.1%} | net/trade {g.mean():+.4f} | per-day {g.groupby(level=0).mean().mean():+.4f} | by year {yr.round(4).to_dict()}")
OOS.to_parquet("pick_oos.parquet")
