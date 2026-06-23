"""Iteration 2: validate the Gate-5 candidates (orb_w, gap) on the 365-day UNDERLYING
directional data (large sample). Same gates 1-4. Outcome = signed move to close with 1%
stop. Tests whether wider opening range / smaller gap actually separates winners over a year."""
import sys, warnings, json
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from datetime import datetime, timedelta
from engine.config import UNIVERSE, TRADING_START, NO_NEW_TRADES_AFTER, MAX_ENTRY_EXTENSION_PCT
from engine.data_fetcher import fetch_upstox_historical
from engine.signals import compute_all_families, is_orb_confirmed
from engine.backtest120 import _fetch_5min_chunked

def tdays(n):
    d=datetime.now()-timedelta(days=1); o=[]
    while len(o)<n:
        if d.weekday()<5: o.append(d.date())
        d-=timedelta(days=1)
    return sorted(o)
def bmin(ts): return ts.hour*60+ts.minute
def hhmm(s): h,m=map(int,s.split(":")); return h*60+m

def collect(N=365):
    days=tdays(N); a,b=days[0]-timedelta(days=3),days[-1]+timedelta(days=1)
    sm,cm=hhmm(TRADING_START),hhmm(NO_NEW_TRADES_AFTER)
    nifty5=_fetch_5min_chunked("NIFTY",a,b); out=[]
    for k,under in enumerate(UNIVERSE):
        if (k+1)%25==0: print(f"  ...{k+1}/{len(UNIVERSE)}",flush=True)
        try:
            daily=fetch_upstox_historical(under,unit="days",interval=1,
                from_date=(days[0]-timedelta(days=60)).strftime("%Y-%m-%d"),to_date=b.strftime("%Y-%m-%d"))
            five=_fetch_5min_chunked(under,a,b)
        except Exception: continue
        if five.empty or daily.empty: continue
        for day in days:
            d5=five[five.index.date==day]
            if len(d5)<8: continue
            dfd=daily[daily.index.date<day]
            if len(dfd)<20: continue
            prev_close=float(dfd["Close"].iloc[-1])
            nday=nifty5[nifty5.index.date==day]; nopen=float(nday.Open.iloc[0]) if not nday.empty else 0
            d_open=float(d5.Open.iloc[0]); orb_hi=float(d5["High"].iloc[:6].max()); orb_lo=float(d5["Low"].iloc[:6].min())
            for i in range(6,len(d5)):
                ts=d5.index[i]; m=bmin(ts)
                if m<sm: continue
                if m>cm: break
                part=d5.iloc[:i+1]
                try: sig=compute_all_families(under,part,dfd,vix=14.0,nifty_pct=0.0)
                except Exception: break
                if not sig["passes_gate_1"]: continue
                ok,od,vr=is_orb_confirmed(part)
                if not (ok and od==sig["direction"]): continue
                direction=sig["direction"]; nd=0
                if not nday.empty and nopen:
                    ns=nday[nday.index<=ts]
                    if not ns.empty:
                        nc=float(ns.Close.iloc[-1]); nd=1 if nc>nopen else (-1 if nc<nopen else 0)
                if not ((direction=="LONG" and nd==1) or (direction=="SHORT" and nd==-1)): continue
                c=float(part.Close.iloc[-1]); ext=(c-d_open)/d_open*100; ext=ext if direction=="LONG" else -ext
                if ext>MAX_ENTRY_EXTENSION_PCT: continue
                rest=d5.Close[d5.index>ts]
                if len(rest)==0: break
                stop=c*0.99 if direction=="LONG" else c*1.01; ex=None
                for px in rest:
                    px=float(px)
                    if (direction=="LONG" and px<=stop) or (direction=="SHORT" and px>=stop): ex=stop; break
                if ex is None: ex=float(rest.iloc[-1])
                ret=(ex/c-1)*100*(1 if direction=="LONG" else -1)
                out.append({"day":str(day),"ret":round(ret,3),"win":int(ret>0),
                    "orb_w":round((orb_hi-orb_lo)/c*100,3),"gap":round((d_open-prev_close)/prev_close*100,3),
                    "tod":m})
                break
    return out

rows=collect(365)
json.dump(rows,open("/tmp/g5_365.json","w"))
print(f"saved {len(rows)} directional trades")

# analyze the candidates train/test
rows.sort(key=lambda r:r["day"]); days=sorted({r["day"] for r in rows})
cut=days[int(len(days)*0.7)]; TR=[r for r in rows if r["day"]<cut]; TE=[r for r in rows if r["day"]>=cut]
def st(lst,fn=None):
    s=[r for r in lst if fn is None or fn(r)]
    if not s: return None
    n=len(s); w=sum(r["win"] for r in s); a=sum(r["ret"] for r in s)/n
    return n,w/n*100,a
def show(tag,fn=None):
    tr=st(TR,fn); te=st(TE,fn)
    if tr and te: print(f"  {tag:22} TRAIN n={tr[0]:4} hit={tr[1]:3.0f}% avg={tr[2]:+.3f}%  TEST n={te[0]:4} hit={te[1]:3.0f}% avg={te[2]:+.3f}%")
print(f"\n=== 365-day directional check (train<{cut}<=test) ===")
show("BASELINE (all)")
print("-- orb_w (opening-range width) --")
for thr in (0.6,0.8,1.0,1.2): show(f"orb_w>={thr}", lambda r,t=thr: r["orb_w"]>=t)
print("-- gap --")
for thr in (0.3,0.5,0.8): show(f"|gap|<={thr}", lambda r,t=thr: abs(r["gap"])<=t)
print("DONE-365")
