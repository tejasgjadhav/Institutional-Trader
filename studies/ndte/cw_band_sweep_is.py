"""IS leg: c/w bands at each book's own geometry, bhavcopy 2019->Sep-2024."""
import sys, json, pickle, warnings, collections, statistics as st
warnings.filterwarnings("ignore"); sys.path.insert(0,"/Users/sayali/files/institutional-trader")
import pandas as pd, numpy as np
from datetime import date, timedelta
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical
MIN_DTE, REENTRY, MIN_PREM = 10, 3, 50.0
BANDS={"0.25-0.30":(0.25,0.30),"0.30-0.35":(0.30,0.35),"0.35-0.40":(0.35,0.40),">=0.40":(0.40,9.0)}
BOOKS={"v2":dict(S=2,W=4,tp=0.50,stop=3.0),"v1":dict(S=1,W=3,tp=0.40,stop=None),
       "v0":dict(S=2,W=4,tp=0.40,stop=None)}
spf=lambda p: min(6.0,max(1.0,60.0/p)) if p>0 else 6.0
print("loading bhavcopy…",flush=True)
frames=pickle.load(open("/tmp/bhav_optstk.pkl","rb"))
big=[]
for d,df in frames:
    df=df.copy(); df["DAY"]=d; big.append(df)
big=pd.concat(big,ignore_index=True); big.columns=[c.strip() for c in big.columns]
big["EXP"]=pd.to_datetime(big["EXPIRY_DT"],format="mixed",dayfirst=True).dt.date.astype(str)
big["STRIKE_PR"]=big["STRIKE_PR"].astype(float); big["CLOSE"]=big["CLOSE"].astype(float)
big["OPTION_TYP"]=big["OPTION_TYP"].astype(str).str.strip(); big["SYMBOL"]=big["SYMBOL"].astype(str).str.strip()
print(f"rows {len(big):,} · symbols {big['SYMBOL'].nunique()}",flush=True)
PX={}
for k,sub in big.groupby(["SYMBOL","EXP","OPTION_TYP"],observed=True):
    c=sub.pivot_table(index="DAY",columns="STRIKE_PR",values="CLOSE",aggfunc="last")
    PX[(str(k[0]),str(k[1]),str(k[2]))]=dict(ks=np.asarray(c.columns,dtype="float64"),
        didx={str(d):i for i,d in enumerate(c.index)},C=c.values.astype("float32"))
del big
exps_by=collections.defaultdict(set)
for (s,e,t) in PX: exps_by[(s,t)].add(e)
rows=[]; n=0
for tk in UNIVERSE:
    sym=tk.replace(".NS","")
    if not any(k[0]==sym for k in PX): continue
    try: u=fetch_upstox_historical(tk,unit="days",interval=1,from_date="2018-11-01",to_date="2024-10-01")
    except Exception: continue
    if u is None or u.empty or len(u)<30: continue
    u=u.sort_index()
    days=[str(i)[:10] for i in u.index]; cl=u["Close"].values; hi=u["High"].values; lo=u["Low"].values
    cb={d:float(c) for d,c in zip(days,cl)}
    last={}
    for i in range(20,len(u)-1):
        d=days[i]; c=float(cl[i]); typ=None
        for dc in (5,10,15,20):
            if c>float(hi[i-dc:i].max()): typ="CE"; break
            if c<float(lo[i-dc:i].min()): typ="PE"; break
        if not typ: continue
        dd=date.fromisoformat(d)
        if last.get(typ) and (dd-last[typ]).days<REENTRY: continue
        fut=sorted(e for e in exps_by.get((sym,typ),()) if date.fromisoformat(e)>=dd+timedelta(days=MIN_DTE))
        if not fut: continue
        exp=fut[0]; P=PX.get((sym,exp,typ))
        if not P or d not in P["didx"]: continue
        last[typ]=dd
        di=P["didx"][d]; ks=P["ks"]
        atm=int(np.argmin(np.abs(ks-c)))
        for bk,cfg in BOOKS.items():
            si=atm+cfg["S"] if typ=="CE" else atm-cfg["S"]
            li=si+cfg["W"] if typ=="CE" else si-cfg["W"]
            if not (0<=si<len(ks) and 0<=li<len(ks)): continue
            se,le=P["C"][di,si],P["C"][di,li]
            if not np.isfinite(se) or not np.isfinite(le) or se<MIN_PREM: continue
            credit=float(se-le); width=float(abs(ks[si]-ks[li]))
            if credit<=0 or credit>=width: continue
            cw=credit/width
            band=next((b for b,(a2,b2) in BANDS.items() if a2<=cw<b2),None)
            if band is None: continue
            path=P["C"][di+1:,si]-P["C"][di+1:,li]; ok=np.isfinite(path); close=None
            if ok.any():
                tp_h=ok&(path<=credit*(1-cfg["tp"]))
                st_h=ok&(path>=credit*cfg["stop"]) if cfg["stop"] else np.zeros(len(path),bool)
                h=tp_h|st_h
                if h.any():
                    j=int(np.argmax(h)); close=max(float(path[j]),0.0) if tp_h[j] else min(float(path[j]),width)
            if close is None:
                es=cb.get(exp) or (cb[max(x for x in cb if x<=exp)] if any(x<=exp for x in cb) else c)
                iS=max(0.0,es-ks[si]) if typ=="CE" else max(0.0,ks[si]-es)
                iL=max(0.0,es-ks[li]) if typ=="CE" else max(0.0,ks[li]-es)
                close=min(max(iS-iL,0.0),width)
            net=(credit-close)-(float(se)*spf(float(se))+float(le)*spf(float(le)))/100.0
            rows.append(dict(book=bk,band=band,yr=dd.year,net=net,margin=width-credit,win=int(net>0)))
    n+=1
    if n%15==0: print(f"  {n} names · {len(rows)} trades",flush=True)
json.dump(rows,open("/tmp/cw_is_rows.json","w"))
print(f"\n=== IS 2019->Sep-2024 · c/w band at each book's OWN geometry ===")
print(f"{'band':<12}{'book':<5}{'n':>6}{'WIN':>8}{'ROM':>9}{'+ve yrs':>9}")
for band in ("0.25-0.30","0.30-0.35","0.35-0.40",">=0.40"):
    for bk in ("v2","v1","v0"):
        s=[x for x in rows if x["band"]==band and x["book"]==bk]
        if len(s)<20: print(f"{band:<12}{bk:<5}{len(s):>6}   (too few)"); continue
        by=collections.defaultdict(list)
        for x in s: by[x["yr"]].append(x["net"])
        pos=sum(1 for v in by.values() if sum(v)>0)
        print(f"{band:<12}{bk:<5}{len(s):>6}{sum(x['win'] for x in s)/len(s)*100:>7.1f}%"
              f"{sum(x['net'] for x in s)/sum(x['margin'] for x in s)*100:>8.1f}%{pos:>6}/{len(by)}")
    print()
print("DONE-CWIS")
