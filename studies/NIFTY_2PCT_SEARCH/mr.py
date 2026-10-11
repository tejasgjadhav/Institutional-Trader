# Pre-registered trend-filtered mean reversion. Long only. Entry next open (or signal close), exits at close.
import pandas as pd, numpy as np, sys
D=pd.read_parquet("daily_long.parquet")
def rsi(c,n):
    d=c.diff(); u=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean(); v=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return 100-100/(1+u/v)
def trades(x,rule,p,entry="open"):
    o,h,l,c=x.Open.values,x.High.values,x.Low.values,x.Close.values; C=x.Close
    s200=C.rolling(200).mean().values; s5=C.rolling(5).mean().values; s10=C.rolling(10).mean().values
    r2=rsi(C,2).values; m20=C.rolling(20).mean(); sd=C.rolling(20).std(); lb=(m20-2*sd).values
    dn=(C.diff()<0).astype(int); streak=dn.groupby((dn!=dn.shift()).cumsum()).cumsum().where(dn==1,0).values
    bad=(np.abs(C.pct_change().values)>0.18)   # demerger/data-error days
    if rule=="rsi2": sig=(c>s200)&(r2<p)
    elif rule=="streak": sig=(c>s200)&(streak>=p)
    elif rule=="bb": sig=(c>s200)&(c<lb)
    out=[]; i=200; n=len(c)
    while i<n-1:
        if sig[i]:
            e_i=i+1 if entry=="open" else i; ep=o[i+1] if entry=="open" else c[i]
            j=i+1; maxh=10 if rule!="bb" else 15
            while j<n-1:
                ex = (c[j]>s5[j]) if rule in("rsi2","bb") else (c[j]>c[j-1])
                if ex or j-i>=maxh: break
                j+=1
            if not bad[i:j+1].any():
                out.append((x.index[i],x.index[e_i],x.index[j],ep,c[j],r2[i],j-e_i+ (1 if entry=="open" else 0)))
            i=j+1
        else: i+=1
    return pd.DataFrame(out,columns=["sig","ent","exit","ep","xp","rank","hold"])
if __name__=="__main__":
    rows=[]
    for rule,ps in (("rsi2",(5,10,15)),("streak",(3,4)),("bb",(0,))):
        for p in ps:
          for entry in ("open","close"):
            T=[]
            for s,x in D.groupby("sym"):
                t=trades(x.drop(columns="sym"),rule,p,entry); t["sym"]=s; T.append(t)
            T=pd.concat(T); T["g"]=T.xp/T.ep-1
            T.to_parquet(f"tr_{rule}_{p}_{entry}.parquet")
            for per,a,b in (("IS","2010","2019"),("OOS","2020","2026")):
                for grp,q in (("stocks",T[~T.sym.str.startswith("^")]),("index",T[T.sym.str.startswith("^")])):
                    q=q[(q.ent>=a)&(q.ent<=b+"-12-31")]
                    for cost in (0.001,0.003):
                        r=q.g-cost
                        rows.append(dict(rule=f"{rule}{p}",entry=entry,per=per,grp=grp,cost=cost,n=len(r),win=(r>0).mean(),mean=r.mean(),hold=q.hold.mean()))
    R=pd.DataFrame(rows); R.to_csv("mr_summary.csv",index=False)
    pd.set_option("display.width",220)
    v=R.pivot_table(index=["grp","rule","entry","cost"],columns="per",values=["n","win","mean"]).round(4)
    print(v.to_string())
