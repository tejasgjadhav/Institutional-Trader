"""Reproduce the table in studies/THREE_MORE_RULES_TESTED.md.

Run it from the repository root with your own market-data token:
    .venv/bin/python studies/reproduce_three_more_rules.py

Study code. Not investment advice. See DISCLAIMER.md.
"""
import os, sys, json, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from engine.data_fetcher import fetch_upstox_historical
NAMES=["RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS","SBIN.NS","AXISBANK.NS","LT.NS",
       "ITC.NS","BHARTIARTL.NS","MARUTI.NS","SUNPHARMA.NS","TITAN.NS","ASIANPAINT.NS","BAJFINANCE.NS",
       "HINDUNILVR.NS","KOTAKBANK.NS","WIPRO.NS","NTPC.NS","POWERGRID.NS"]
COST=0.10
def daily(t):
    fr=[]; end=dt.date.today()
    for _ in range(8):
        s=end-dt.timedelta(days=360)
        d=fetch_upstox_historical(t,unit="days",interval=1,from_date=s.isoformat(),to_date=end.isoformat())
        if d is not None and len(d): fr.append(d)
        end=s-dt.timedelta(days=1)
    if not fr: return None
    o=pd.concat(fr).sort_index(); return o[~o.index.duplicated(keep="first")]
res={k:[] for k in ("bollinger_revert","high52_breakout","rsi14_oversold")}
for t in NAMES:
    d=daily(t)
    if d is None or len(d)<300: continue
    c=d.Close
    # Bollinger reversion: close below lower band -> buy, exit on touch of the middle band
    mid=c.rolling(20).mean(); sd=c.rolling(20).std(); lo=mid-2*sd
    pos=None
    for i in range(20,len(c)):
        if pos is None and c.iloc[i]<lo.iloc[i]: pos=float(c.iloc[i])
        elif pos is not None and c.iloc[i]>=mid.iloc[i]:
            res["bollinger_revert"].append((float(c.iloc[i])-pos)/pos*100-COST); pos=None
    # 52-week high breakout, exit on a 10% fall from the running peak
    hh=c.rolling(250).max(); pos=None; peak=0
    for i in range(250,len(c)):
        px=float(c.iloc[i])
        if pos is None and px>=hh.iloc[i-1]: pos=px; peak=px
        elif pos is not None:
            peak=max(peak,px)
            if px<=peak*0.90:
                res["high52_breakout"].append((px-pos)/pos*100-COST); pos=None
    # RSI(14) < 30 -> buy, exit RSI > 50
    dd=c.diff(); g=dd.clip(lower=0).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    l=(-dd.clip(upper=0)).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    r=100-100/(1+g/l.replace(0,np.nan)); pos=None
    for i in range(14,len(c)):
        if pos is None and r.iloc[i]<30: pos=float(c.iloc[i])
        elif pos is not None and r.iloc[i]>50:
            res["rsi14_oversold"].append((float(c.iloc[i])-pos)/pos*100-COST); pos=None
    print("done",t,flush=True)
out={}
for k,v in res.items():
    a=np.array(v)
    out[k]=dict(trades=int(len(a)),win_rate_pct=round(float((a>0).mean()*100),1),
        mean_net_pct=round(float(a.mean()),4),median_pct=round(float(np.median(a)),4),
        stdev=round(float(a.std()),3),t_stat=round(float(a.mean()/(a.std()/np.sqrt(len(a)))),2),
        best=round(float(a.max()),2),worst=round(float(a.min()),2)) if len(a)>=30 else {"trades":len(a)}
print(json.dumps(out,indent=1))
json.dump(out,open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "more.json"),"w"),indent=1)
