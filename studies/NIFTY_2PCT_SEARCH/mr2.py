import pandas as pd, numpy as np
from mr import rsi
D=pd.read_parquet("daily_long.parquet")
def run(x,filt,exitr,maxh,cat=None,entry="close",rth=10):
    o,h,l,c=(x[k].values for k in ("Open","High","Low","Close")); C=x.Close
    s200=C.rolling(200).mean().values; s50=C.rolling(50).mean().values; s5=C.rolling(5).mean().values
    r2=rsi(C,2).values; lb=(C.rolling(20).mean()-2*C.rolling(20).std()).values
    bad=np.abs(C.pct_change().values)>0.18
    base=(c>s200)&(r2<rth)
    sig={"F0":base,"F1":base&(s50>s200),"F2":base&(s50>s200)&(c<lb)}[filt]
    out=[];i=200;n=len(c)
    while i<n-1:
        if not sig[i]: i+=1; continue
        e=i+1 if entry=="open" else i; ep=o[i+1] if entry=="open" else c[i]; j=i+1; xp=None
        while j<n:
            if cat is not None and l[j]<=ep*(1-cat): xp=min(o[j],ep*(1-cat)); break
            if (exitr=="profit" and c[j]>ep) or (exitr=="sma5" and c[j]>s5[j]) or j-e>=maxh: xp=c[j]; break
            j+=1
        if xp is None: break
        if not bad[i:j+1].any(): out.append((x.index[i],x.index[j],ep,xp,j-e))
        i=j+1
    return pd.DataFrame(out,columns=["ent","exit","ep","xp","hold"])
rows=[]
for filt in ("F0","F1","F2"):
  for exitr,maxh in (("sma5",10),("profit",10),("profit",20)):
    for cat in (None,0.08):
      T=pd.concat([run(x,filt,exitr,maxh,cat).assign(sym=s) for s,x in D.groupby("sym")])
      T["g"]=T.xp/T.ep-1-0.001; T.to_parquet(f"tr2_{filt}_{exitr}{maxh}_{cat}.parquet")
      for per,a,b in (("IS","2010","2019-12-31"),("OOS","2020","2026-12-31")):
        for grp in ("stocks","index"):
          q=T[(T.ent>=a)&(T.ent<=b)&(T.sym.str.startswith("^")==(grp=="index"))]
          rows.append(dict(grp=grp,filt=filt,exit=f"{exitr}{maxh}",cat=cat,per=per,n=len(q),win=(q.g>0).mean(),mean=q.g.mean(),worst=q.g.min(),hold=q.hold.mean()))
R=pd.DataFrame(rows); pd.set_option("display.width",250)
print(R.pivot_table(index=["grp","filt","exit","cat"],columns="per",values=["n","win","mean","worst","hold"],dropna=False).round(3).to_string())
