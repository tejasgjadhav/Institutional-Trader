"""IS forensics: how much of the v2/v1 bhavcopy edge rides on OI=0 marks / impossible triggers,
and what exit-side costs do to it. No API calls - pickle only."""
import sys, json, pickle, warnings, collections
warnings.filterwarnings("ignore"); sys.path.insert(0,"/Users/sayali/files/institutional-trader")
import pandas as pd, numpy as np
from datetime import date, timedelta
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical
MIN_DTE,REENTRY,MIN_PREM=10,3,50.0
BOOKS={"v2":dict(S=2,W=4,tp=0.50,stop=3.0),"v1":dict(S=1,W=3,tp=0.40,stop=None)}
spf=lambda p: min(6.0,max(1.0,60.0/p)) if p>0 else 6.0
frames=pickle.load(open("/tmp/bhav_optstk.pkl","rb"))
big=[]
for d,df in frames:
    df=df.copy(); df["DAY"]=d; big.append(df)
big=pd.concat(big,ignore_index=True); big.columns=[c.strip() for c in big.columns]
big["EXP"]=pd.to_datetime(big["EXPIRY_DT"],format="mixed",dayfirst=True).dt.date.astype(str)
for col in ("STRIKE_PR","CLOSE","OPEN_INT"): big[col]=big[col].astype(float)
big["OPTION_TYP"]=big["OPTION_TYP"].astype(str).str.strip(); big["SYMBOL"]=big["SYMBOL"].astype(str).str.strip()
PX={}
for k,sub in big.groupby(["SYMBOL","EXP","OPTION_TYP"],observed=True):
    c=sub.pivot_table(index="DAY",columns="STRIKE_PR",values="CLOSE",aggfunc="last")
    o=sub.pivot_table(index="DAY",columns="STRIKE_PR",values="OPEN_INT",aggfunc="last").reindex(index=c.index,columns=c.columns)
    PX[(str(k[0]),str(k[1]),str(k[2]))]=dict(ks=np.asarray(c.columns,dtype="float64"),
        didx={str(d):i for i,d in enumerate(c.index)},C=c.values.astype("float32"),O=o.values.astype("float32"))
del big
exps_by=collections.defaultdict(set)
for (s,e,t) in PX: exps_by[(s,t)].add(e)
res=collections.defaultdict(lambda: dict(n=0,net0=0.0,netx=0.0,mg=0.0,win0=0,winx=0,
                                          exit_oi0=0,imposs=0,gate=0))
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
        dd_=date.fromisoformat(d)
        if last.get(typ) and (dd_-last[typ]).days<REENTRY: continue
        fut=sorted(e for e in exps_by.get((sym,typ),()) if date.fromisoformat(e)>=dd_+timedelta(days=MIN_DTE))
        if not fut: continue
        exp=fut[0]; P=PX.get((sym,exp,typ))
        if not P or d not in P["didx"]: continue
        last[typ]=dd_
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
            if credit/width<0.40: continue          # DEPLOYED band only
            R=res[bk]; R["n"]+=1; R["mg"]+=width-credit
            path=P["C"][di+1:,si]-P["C"][di+1:,li]
            oiS,oiL=P["O"][di+1:,si],P["O"][di+1:,li]
            ok=np.isfinite(path)
            j=None; kind=None
            for t in range(len(path)):
                if not ok[t]: continue
                if path[t]<=credit*(1-cfg["tp"]): j,kind=t,"tp"; break
                if cfg["stop"] and path[t]>=credit*cfg["stop"]: j,kind=t,"stop"; break
            ec=(se*spf(se)+le*spf(le))/100.0
            if j is None:
                es=cb.get(exp) or (cb[max(x for x in cb if x<=exp)] if any(x<=exp for x in cb) else c)
                iS=max(0.0,es-ks[si]) if typ=="CE" else max(0.0,ks[si]-es)
                iL=max(0.0,es-ks[li]) if typ=="CE" else max(0.0,ks[li]-es)
                close=min(max(iS-iL,0.0),width); xc=0.0
            else:
                close=max(float(path[j]),0.0) if kind=="tp" else min(float(path[j]),width)
                spx,lpx=float(P["C"][di+1+j,si]),float(P["C"][di+1+j,li])
                xc=(abs(spx)*spf(abs(spx))+abs(lpx)*spf(abs(lpx)))/100.0 if np.isfinite(spx) and np.isfinite(lpx) else 0.0
                if (np.isfinite(oiS[j]) and oiS[j]==0) or (np.isfinite(oiL[j]) and oiL[j]==0): R["exit_oi0"]+=1
                if kind=="stop" and float(path[j])>width: R["imposs"]+=1
            n0=(credit-close)-ec; nx=(credit-close)-ec-xc
            R["net0"]+=n0; R["netx"]+=nx; R["win0"]+=int(n0>0); R["winx"]+=int(nx>0)
print("=== IS >=0.40 (deployed band) forensics: entry-only vs +exit costs; artifact counts ===")
for bk,R in res.items():
    if not R["n"]: continue
    print(f"{bk}: n={R['n']}  WIN {R['win0']/R['n']*100:.1f}% -> {R['winx']/R['n']*100:.1f}% with exit costs"
          f"  ROM {R['net0']/R['mg']*100:+.1f}% -> {R['netx']/R['mg']*100:+.1f}%"
          f"  exits on OI=0 leg: {R['exit_oi0']} ({R['exit_oi0']/R['n']*100:.0f}%)  impossible stop marks: {R['imposs']}")
print("DONE-FORENSICS")
