"""NIFTY, MAY signals: compare expiry (weekly/shortest, 30-JUN monthly, 28-JUL next)
x moneyness (ITM/ATM/OTM) at +25%/-15%. Reports net Rs, win%, return%, avg DTE per cell."""
import sys, json, gzip, requests
from datetime import datetime, timedelta, date
import numpy as np, pandas as pd
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from engine.backtest120 import _fetch_5min_chunked
from engine.options import _load_index, fetch_option_premium_5min
from engine.instruments import to_instrument_key

URL="https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
def fut_key():
    raw=json.loads(gzip.decompress(requests.get(URL,timeout=60).content))
    fs=sorted([{"key":i["instrument_key"],"e":int(i["expiry"])} for i in raw
        if i.get("segment")=="NSE_FO" and i.get("instrument_type")=="FUT" and (i.get("name") or "")=="NIFTY"],key=lambda c:c["e"])
    return fs[0]["key"]
def tdays(n):
    days,dd=[],datetime.now()-timedelta(days=1)
    while len(days)<n:
        if dd.weekday()<5: days.append(dd.date())
        dd-=timedelta(days=1)
    return sorted(days)
def bmin(ts): return ts.hour*60+ts.minute
def vwap_s(df):
    tp=(df.High+df.Low+df.Close)/3; return (tp*df.Volume).cumsum()/df.Volume.cumsum()
ENTRY_START,ENTRY_END=9*60+30,10*60+45; RETEST_BUF=0.0007
TGT,STP=25.0,15.0

und=to_instrument_key("NIFTY"); IDX=_load_index()
def chain(typ, exp_ms): return sorted([c for c in IDX.get(und,[]) if c["type"]==typ and c["expiry"]==exp_ms],key=lambda x:x["strike"])
def exps(typ): return sorted({c["expiry"] for c in IDX.get(und,[]) if c["type"]==typ})
def monthlies(typ):
    bym={}
    for c in IDX.get(und,[]):
        if c["type"]!=typ: continue
        d=datetime.fromtimestamp(c["expiry"]/1000).date(); bym[(d.year,d.month)]=max(bym.get((d.year,d.month),0),c["expiry"])
    return sorted(bym.values())
def pick(typ, exp_ms, spot, offset):
    ch=chain(typ,exp_ms)
    if not ch: return None
    ai=min(range(len(ch)),key=lambda i:abs(ch[i]["strike"]-spot))
    idx=ai+offset if typ=="CE" else ai-offset
    idx=max(0,min(len(ch)-1,idx)); return ch[idx]
_PC={}
def prem(key,day):
    k=(key,str(day))
    if k not in _PC: _PC[k]=fetch_option_premium_5min(key,day)
    return _PC[k]
def outcome(p, ets):
    sub=p[p.index<=ets]
    if sub.empty: return None
    ep=float(sub.Close.iloc[-1])
    if ep<=0: return None
    last=ep
    for v in p.Close[p.index>ets]:
        last=float(v)
        if last<=ep*(1-STP/100): return ep,-STP
        if last>=ep*(1+TGT/100): return ep,TGT
    return ep,(last/ep-1)*100

days=[d for d in tdays(60) if date(2026,5,1)<=d<=date(2026,5,31)]
a,b=days[0]-timedelta(days=3),days[-1]+timedelta(days=1)
spot5=_fetch_5min_chunked("NIFTY",a,b); fut=_fetch_5min_chunked(fut_key(),a,b)
MON=monthlies("CE");
def near_month(day, k=0):
    dm=int(datetime(day.year,day.month,day.day).timestamp()*1000)
    f=[e for e in MON if e>=dm]; return f[k] if len(f)>k else None

# collect May entries
entries=[]
for day in days:
    f=fut[fut.index.date==day]
    if len(f)<12: continue
    sp=spot5[spot5.index.date==day] if not spot5.empty else f
    orb=f.iloc[:3]; oh=float(orb.High.max()); ol=float(orb.Low.min())
    vw=vwap_s(f); bu=bd=False; entry=None
    for i in range(3,len(f)):
        ts=f.index[i]; m=bmin(ts)
        if m>ENTRY_END: break
        c=float(f.Close.iloc[i]); lo=float(f.Low.iloc[i]); hi=float(f.High.iloc[i]); v=float(vw.iloc[i])
        if c>oh and c>v: bu=True
        if c<ol and c<v: bd=True
        if m<ENTRY_START: continue
        if bu and lo<=oh*(1+RETEST_BUF) and c>oh and c>v: entry=("LONG",ts); break
        if bd and hi>=ol*(1-RETEST_BUF) and c<ol and c<v: entry=("SHORT",ts); break
    if not entry: continue
    direction,ets=entry
    spot=float(sp.Close[sp.index<=ets].iloc[-1]) if not sp.empty and (sp.index<=ets).any() else float(f.Close[f.index<=ets].iloc[-1])
    entries.append((day,ets,direction,spot))
print(f"NIFTY May entries: {len(entries)} ({days[0]} .. {days[-1]})")

ALL_EXP={"CE":exps("CE"),"PE":exps("PE")}
def weekly_exp(typ, day):
    dm=int(datetime(day.year,day.month,day.day).timestamp()*1000)
    return [e for e in ALL_EXP[typ] if e>=dm]   # ordered; we try in order for data

OFF={"ITM":-1,"ATM":0,"OTM":1}; EXPDEF=["weekly","monthly(30-JUN)","next(28-JUL)"]
cells={(e,o):{"pnl":0.0,"cap":0.0,"win":0,"n":0,"dte":[]} for e in EXPDEF for o in OFF}
for (day,ets,direction,spot) in entries:
    typ="CE" if direction=="LONG" else "PE"
    # determine the three target expiries
    m0=near_month(day,0); m1=near_month(day,1)
    for elabel in EXPDEF:
        if elabel.startswith("monthly"): exp_ms=m0
        elif elabel.startswith("next"): exp_ms=m1
        else: exp_ms=None  # weekly: pick shortest with data below
        for oname,off in OFF.items():
            if elabel=="weekly":
                chosen=None
                for e in weekly_exp(typ,day):
                    if e in (m0,m1): continue  # keep weekly distinct from the monthly cols
                    o=pick(typ,e,spot,off)
                    if not o: continue
                    p=prem(o["key"],day)
                    if not p.empty and not p[p.index<=ets].empty:
                        chosen=(e,o,p); break
                if not chosen: continue
                e,o,p=chosen
            else:
                if not exp_ms: continue
                o=pick(typ,exp_ms,spot,off)
                if not o: continue
                p=prem(o["key"],day); e=exp_ms
                if p.empty or p[p.index<=ets].empty: continue
            r=outcome(p,ets)
            if not r: continue
            ep,pct=r; lot=int(o.get("lot",65) or 65); cap=ep*lot
            c=cells[(elabel,oname)]; c["pnl"]+=cap*pct/100; c["cap"]+=cap
            c["win"]+= 1 if pct>0 else 0; c["n"]+=1
            c["dte"].append((datetime.fromtimestamp(e/1000).date()-day).days)

print(f"\n=== NIFTY May @ +{TGT:.0f}%/-{STP:.0f}%  [net Rs | win% | return% | n | avgDTE] ===")
print(f"{'EXPIRY':16} | {'ITM':>26} | {'ATM':>26} | {'OTM':>26}")
for e in EXPDEF:
    row=f"{e:16} |"
    for o in ["ITM","ATM","OTM"]:
        c=cells[(e,o)]
        if c["n"]==0: row+=f" {'--':>26} |"; continue
        dte=int(np.mean(c['dte'])) if c['dte'] else 0
        row+=f" Rs{c['pnl']:+7,.0f} {c['win']/c['n']*100:3.0f}% {c['pnl']/c['cap']*100:+5.1f}% n{c['n']:2} {dte}d |"
    print(row)
