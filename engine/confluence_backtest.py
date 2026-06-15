"""
Confluence backtest — combine 6 signals, require K to agree, find highest win rate.

Signals (each votes LONG/SHORT/None per 5-min bar):
  1 RS        relative strength vs Nifty
  2 VWAP      above/below VWAP + direction
  3 GAP       opening gap-and-go
  4 MOM       1-hour momentum sign
  5 VOL       volume-surge confirmation
  6 ORB       opening-range breakout

For each stock/day and each threshold K in 2..6, take the first bar where >=K
signals agree on a direction, BUY the OTM+1 option, exit +10%/-20% on premium.
Option premium is fetched once per (stock,day,direction) and reused across K.
Reports win rate vs K — the confluence-vs-win-rate curve.
"""
import logging
from datetime import datetime, timedelta
import pandas as pd

from engine.config import UNIVERSE, TRADING_START, OPTION_STRIKE_OFFSET, PREMIUM_TARGET_PCT, PREMIUM_STOP_PCT
from engine.data_fetcher import fetch_upstox_historical
from engine.options import get_option_by_offset, fetch_option_premium_5min
from engine.backtest120 import _fetch_5min_chunked

logger = logging.getLogger(__name__)

def _tdays(n):
    days, d = [], datetime.now() - timedelta(days=1)
    while len(days) < n:
        if d.weekday() < 5: days.append(d.date())
        d -= timedelta(days=1)
    return sorted(days)
def _bmin(ts): return ts.hour*60+ts.minute
def _hhmm(s): h,m=map(int,s.split(":")); return h*60+m
def _vwap(df):
    tp=(df.High+df.Low+df.Close)/3
    return (tp*df.Volume).cumsum()/df.Volume.cumsum()


def _votes(part, day_open, prev_close, npart, nifty_open, orb_hi, orb_lo, orb_volavg):
    """Return dict signal->('LONG'|'SHORT'|None) for the latest bar."""
    px = float(part.Close.iloc[-1]); v = {}
    # RS
    if npart is not None and len(npart) and day_open>0 and nifty_open>0:
        sret=(px-day_open)/day_open*100; nret=(float(npart.Close.iloc[-1])-nifty_open)/nifty_open*100
        rs=sret-nret
        v["RS"]= "LONG" if (rs>0.5 and sret>0.2) else ("SHORT" if (rs<-0.5 and sret<-0.2) else None)
    else: v["RS"]=None
    # VWAP
    if len(part)>=4:
        vw=float(_vwap(part).iloc[-1]); px3=float(part.Close.iloc[-4])
        v["VWAP"]="LONG" if (px>vw and px>px3) else ("SHORT" if (px<vw and px<px3) else None)
    else: v["VWAP"]=None
    # GAP
    if prev_close>0:
        gap=(day_open-prev_close)/prev_close*100
        v["GAP"]="LONG" if (gap>0.5 and px>day_open) else ("SHORT" if (gap<-0.5 and px<day_open) else None)
    else: v["GAP"]=None
    # MOM (1h = 12 bars)
    if len(part)>=13:
        m=(px-float(part.Close.iloc[-13]))/float(part.Close.iloc[-13])*100
        v["MOM"]="LONG" if m>0.3 else ("SHORT" if m<-0.3 else None)
    else: v["MOM"]=None
    # VOL surge + direction
    curv=float(part.Volume.iloc[-1])
    if orb_volavg>0 and curv>=1.5*orb_volavg and len(part)>=2:
        up = px>float(part.Close.iloc[-2])
        v["VOL"]="LONG" if up else "SHORT"
    else: v["VOL"]=None
    # ORB breakout
    if orb_hi>0:
        v["ORB"]="LONG" if px>orb_hi*1.001 else ("SHORT" if px<orb_lo*0.999 else None)
    else: v["ORB"]=None
    return v


def _sim(prem, ts, ):
    sub=prem[prem.index<=ts]
    if sub.empty: return None
    entry=float(sub.Close.iloc[-1])
    if entry<=0: return None
    tgt,stp=entry*(1+PREMIUM_TARGET_PCT/100), entry*(1-PREMIUM_STOP_PCT/100)
    last=entry
    for b in prem[prem.index>ts].itertuples():
        last=float(b.Close)
        if last<=stp: return ("LOSS", round((stp/entry-1)*100,2))
        if last>=tgt: return ("WIN", round((tgt/entry-1)*100,2))
    return ("FORCED", round((last/entry-1)*100,2))


def run(n_days=20, cutoff="13:00", progress=None) -> dict:
    days=_tdays(n_days)
    from_dt=days[0]-timedelta(days=3); to_dt=days[-1]+timedelta(days=1)
    start_min, cut_min=_hhmm(TRADING_START), _hhmm(cutoff)
    nifty5=_fetch_5min_chunked("NIFTY", from_dt, to_dt)
    Ks=[2,3,4,5,6]
    results={k:[] for k in Ks}

    for idx,under in enumerate(UNIVERSE):
        if progress: progress(idx+1,len(UNIVERSE),under)
        daily=fetch_upstox_historical(under,unit="days",interval=1,
              from_date=(days[0]-timedelta(days=30)).strftime("%Y-%m-%d"),to_date=to_dt.strftime("%Y-%m-%d"))
        five=_fetch_5min_chunked(under,from_dt,to_dt)
        if five.empty or daily.empty: continue
        for day in days:
            d5=five[five.index.date==day]
            if len(d5)<7: continue
            prev=daily[daily.index.date<day]
            if prev.empty: continue
            prev_close=float(prev.Close.iloc[-1]); day_open=float(d5.Open.iloc[0])
            nday=nifty5[nifty5.index.date==day]; nifty_open=float(nday.Open.iloc[0]) if not nday.empty else 0
            orb=d5.iloc[:6]; orb_hi=float(orb.High.max()); orb_lo=float(orb.Low.min()); orb_volavg=float(orb.Volume.mean())

            # first bar reaching each K (per direction), once per stock/day
            firstK={k:None for k in Ks}
            for i in range(6,len(d5)):
                ts=d5.index[i]; m=_bmin(ts)
                if m<start_min: continue
                if m>cut_min: break
                part=d5.iloc[:i+1]; npart=nday[nday.index<=ts] if not nday.empty else None
                vv=_votes(part,day_open,prev_close,npart,nifty_open,orb_hi,orb_lo,orb_volavg)
                longs=sum(1 for x in vv.values() if x=="LONG"); shorts=sum(1 for x in vv.values() if x=="SHORT")
                cnt=max(longs,shorts); direction="LONG" if longs>=shorts else "SHORT"
                for k in Ks:
                    if firstK[k] is None and cnt>=k:
                        firstK[k]=(ts,direction,float(part.Close.iloc[-1]))
            if all(v is None for v in firstK.values()): continue

            # fetch option premium once per direction needed
            prem_cache={}
            for k in Ks:
                if firstK[k] is None: continue
                ts,direction,spot=firstK[k]
                opt_type="CE" if direction=="LONG" else "PE"
                if direction not in prem_cache:
                    opt=get_option_by_offset(under,spot,day,opt_type,OPTION_STRIKE_OFFSET)
                    prem_cache[direction]=fetch_option_premium_5min(opt["key"],day) if opt else pd.DataFrame()
                prem=prem_cache[direction]
                if prem.empty: continue
                out=_sim(prem,ts)
                if out: results[k].append(out)

    summary={}
    for k,lst in results.items():
        n=len(lst)
        if not n: summary[k]={"trades":0,"win":0,"exp":0,"perday":0}; continue
        green=sum(1 for o in lst if o[1]>0); net=sum(o[1] for o in lst)
        summary[k]={"trades":n,"win":round(green/n*100),"exp":round(net/n,2),"perday":round(n/n_days,1)}
    return summary
