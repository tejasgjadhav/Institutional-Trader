"""Reproduce the three simple rules' published result.

This is the script that produced the table in studies/THREE_SIMPLE_RULES_TESTED.md. Run it and you should land
close to the published numbers. If you do not, one of us has a bug, and finding out which is
worth more than tuning a parameter.

It needs an Upstox market-data token in .env. Run it from the repository root:
    .venv/bin/python studies/reproduce_daily_rules_result.py

Study code. Not investment advice. See DISCLAIMER.md.
"""
import os, sys, json, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from engine.data_fetcher import fetch_upstox_historical

NAMES=["RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS","SBIN.NS","AXISBANK.NS",
       "LT.NS","ITC.NS","BHARTIARTL.NS","MARUTI.NS","SUNPHARMA.NS","TITAN.NS","ASIANPAINT.NS",
       "BAJFINANCE.NS","HINDUNILVR.NS","KOTAKBANK.NS","WIPRO.NS","NTPC.NS","POWERGRID.NS"]
COST=0.10   # percent round trip, realistic Indian cash equity

def daily(t):
    frames=[]; end=dt.date.today()
    for _ in range(8):
        start=end-dt.timedelta(days=360)
        d=fetch_upstox_historical(t,unit="days",interval=1,from_date=start.isoformat(),to_date=end.isoformat())
        if d is not None and len(d): frames.append(d)
        end=start-dt.timedelta(days=1)
    if not frames: return None
    o=pd.concat(frames).sort_index(); return o[~o.index.duplicated(keep="first")]

def rsi(s,n=2):
    d=s.diff(); g=d.clip(lower=0).ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    l=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    return 100-100/(1+g/l.replace(0,np.nan))

res={k:[] for k in ("sma_cross","rsi2","gap_fill")}
span={}
for t in NAMES:
    d=daily(t)
    if d is None or len(d)<300: print("skip",t); continue
    c=d.Close; span[t]=(str(d.index.min().date()),str(d.index.max().date()))
    # 1 SMA 20/50 crossover, long only, exit on cross back
    f,s=c.rolling(20).mean(),c.rolling(50).mean()
    up=(f>s)&(f.shift(1)<=s.shift(1)); dn=(f<s)&(f.shift(1)>=s.shift(1))
    pos=None
    for i in range(len(c)):
        if pos is None and up.iloc[i]: pos=float(c.iloc[i])
        elif pos is not None and dn.iloc[i]:
            res["sma_cross"].append((float(c.iloc[i])-pos)/pos*100-COST); pos=None
    # 2 RSI(2) < 10 with price above 200-day MA; exit when close > prior high
    r=rsi(c); ma200=c.rolling(200).mean(); pos=None
    for i in range(200,len(c)):
        if pos is None and r.iloc[i]<10 and c.iloc[i]>ma200.iloc[i]: pos=float(c.iloc[i])
        elif pos is not None and c.iloc[i]>float(d.High.iloc[i-1]):
            res["rsi2"].append((float(c.iloc[i])-pos)/pos*100-COST); pos=None
    # 3 gap fill: open <= prev close * 0.99, buy open, exit same-day close
    for i in range(1,len(c)):
        po=float(c.iloc[i-1]); op=float(d.Open.iloc[i])
        if op<=po*0.99:
            res["gap_fill"].append((float(c.iloc[i])-op)/op*100-COST)
    print("done",t,flush=True)

out={}
for k,v in res.items():
    a=np.array(v)
    if len(a)<30: out[k]={"trades":len(a)}; continue
    out[k]=dict(trades=int(len(a)), win_rate_pct=round(float((a>0).mean()*100),1),
                mean_net_pct=round(float(a.mean()),4), median_pct=round(float(np.median(a)),4),
                stdev=round(float(a.std()),3), t_stat=round(float(a.mean()/(a.std()/np.sqrt(len(a)))),2),
                best=round(float(a.max()),2), worst=round(float(a.min()),2))
out["_meta"]=dict(names=len(span), cost_pct_round_trip=COST,
                  window=[min(v[0] for v in span.values()), max(v[1] for v in span.values())])
print(json.dumps(out,indent=1))
json.dump(out,open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "simple.json"),"w"),indent=1)
