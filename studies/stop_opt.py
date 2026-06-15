"""
Stop-loss optimization. Collect each index-option signal's forward premium PATH once,
then simulate many exit policies in-memory: stop-only, target+stop matrix,
breakeven-after-cushion, and trailing stop. Find which are NET POSITIVE (Rs) on
NIFTY/BANKNIFTY/both over the last 30 days. 1 lot/trade, ATM, ORB+VWAP break entry.
"""
import sys, json, gzip, requests
from datetime import datetime, timedelta
import numpy as np, pandas as pd
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from engine.backtest120 import _fetch_5min_chunked
from engine.options import get_option_by_offset, fetch_option_premium_5min

URL="https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
def load_futs():
    raw=json.loads(gzip.decompress(requests.get(URL,timeout=60).content)); f={}
    for i in raw:
        if i.get("segment")=="NSE_FO" and i.get("instrument_type")=="FUT" and (i.get("name") or "") in ("NIFTY","BANKNIFTY"):
            f.setdefault(i["name"],[]).append({"key":i["instrument_key"],"expiry":int(i["expiry"])})
    return {k:sorted(v,key=lambda c:c["expiry"]) for k,v in f.items()}
def tdays(n):
    days,dd=[],datetime.now()-timedelta(days=1)
    while len(days)<n:
        if dd.weekday()<5: days.append(dd.date())
        dd-=timedelta(days=1)
    return sorted(days)
def bmin(ts): return ts.hour*60+ts.minute
def vwap_s(df):
    tp=(df.High+df.Low+df.Close)/3; return (tp*df.Volume).cumsum()/df.Volume.cumsum()
def near_key(futs,nm,day):
    dm=int(datetime(day.year,day.month,day.day).timestamp()*1000)
    nr=[c for c in futs.get(nm,[]) if c["expiry"]>=dm]
    return nr[0]["key"] if nr else None
ENTRY_START,ENTRY_END=9*60+30,10*60+45; RETEST_BUF=0.0007

def collect(n_days=30):
    futs=load_futs(); days=tdays(n_days); a,b=days[0]-timedelta(days=3),days[-1]+timedelta(days=1)
    out=[]
    for nm in ("NIFTY","BANKNIFTY"):
        spot5=_fetch_5min_chunked(nm,a,b); fut=_fetch_5min_chunked(near_key(futs,nm,days[-1]),a,b)
        if fut.empty: continue
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
            typ="CE" if direction=="LONG" else "PE"
            opt=get_option_by_offset(nm,spot,day,typ,0)
            if not opt: continue
            prem=fetch_option_premium_5min(opt["key"],day)
            if prem.empty: continue
            psub=prem[prem.index<=ets]
            if psub.empty: continue
            ep=float(psub.Close.iloc[-1]); lot=int(opt.get("lot",0) or 0)
            if ep<=0 or lot<=0: continue
            path=[(bmin(ts),float(px)) for ts,px in prem.Close[prem.index>ets].items()]
            out.append({"idx":nm,"entry":ep,"lot":lot,"path":path})
    return out

def sim(t, stop=None, target=None, be_after=None, trail=None):
    """Return exit premium given a policy. stop/target/be_after/trail in %."""
    ep=t["entry"]; armed=False; peak=ep; be=False
    for m,px in t["path"]:
        if target and px>=ep*(1+target/100): return ep*(1+target/100)
        if px>peak: peak=px
        if be_after and px>=ep*(1+be_after/100): be=True
        # breakeven stop: once cushion reached, exit if back to entry
        if be and px<=ep: return ep
        if trail and px>=ep*(1+trail/100): armed=True
        if armed and px<=peak*(1-trail/100): return peak*(1-trail/100)
        if stop and px<=ep*(1-stop/100): return ep*(1-stop/100)
    return t["path"][-1][1] if t["path"] else ep   # book at EOD

def agg(trades, **pol):
    rows=[]
    for t in trades:
        ex=sim(t,**pol); rows.append({"idx":t["idx"],"cap":t["entry"]*t["lot"],"pnl":(ex-t["entry"])*t["lot"]})
    d=pd.DataFrame(rows)
    def one(s):
        if not len(s): return (0,0,0,0)
        return (len(s),(s.pnl>0).mean()*100,s.pnl.sum(),s.pnl.sum()/s.cap.sum()*100)
    return one(d), one(d[d.idx=="NIFTY"]), one(d[d.idx=="BANKNIFTY"])

print("collecting signal paths...",flush=True)
T=collect(30)
print(f"signals={len(T)} (NIFTY {sum(t['idx']=='NIFTY' for t in T)}, BANKNIFTY {sum(t['idx']=='BANKNIFTY' for t in T)})\n")

def line(label,pol):
    b,n,bk=agg(T,**pol)
    def f(x): return f"{x[0]:>2} {x[1]:>3.0f}% Rs{x[2]:>+8,.0f} ({x[3]:>+5.1f}%)"
    print(f"{label:30} | BOTH {f(b)} | NIFTY {f(n)} | BNF {f(bk)}")

print("== A. STOP-ONLY (book winners at EOD, no target) ==  [n win% netRs (ret%)]")
for s in [10,15,20,25,30,40,None]:
    line(f"stop={s if s else 'none(hold EOD)'}", dict(stop=s))
print("\n== B. TARGET + STOP (asymmetric: cap loss, book profit at target) ==")
for tg in [20,25,30]:
    for s in [15,20,25,30]:
        line(f"target=+{tg}  stop=-{s}", dict(stop=s,target=tg))
print("\n== C. BREAKEVEN-AFTER-CUSHION (move stop to entry once +X%) ==")
for be in [10,15,20]:
    for s in [25,30]:
        line(f"init stop=-{s}, BE-stop after +{be}%", dict(stop=s,be_after=be))
print("\n== D. TRAILING STOP (arm at +X%, trail X% from peak) ==")
for tr in [12,15,20,25]:
    line(f"trail {tr}% (arm +{tr}%)", dict(trail=tr))
