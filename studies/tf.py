"""
Timeframe sweep: does a SLOWER candle (10-min, 15-min) raise the win rate by
smoothing out 5-min fakeouts? Resample 5-min -> N-min, scale ORB + momentum to the
same wall-clock (30-min opening range, 60-min momentum), run the IDENTICAL gate,
train/test split. Compare against the 5-min baseline.
"""
import sys, importlib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
sys.path.insert(0, "/Users/sayali/files/institutional-trader")

from engine import config
from engine.data_fetcher import fetch_upstox_historical
from engine.options import get_option_by_offset, fetch_option_premium_5min
from engine.backtest120 import _fetch_5min_chunked
import engine.signals as signals

UNIVERSE = config.UNIVERSE
def _tdays(n):
    days, d = [], datetime.now()-timedelta(days=1)
    while len(days)<n:
        if d.weekday()<5: days.append(d.date())
        d -= timedelta(days=1)
    return sorted(days)
def _bmin(ts): return ts.hour*60+ts.minute
def _hhmm(s): h,m=map(int,s.split(":")); return h*60+m

def _outcome(prem, ts, tgt, stp):
    sub=prem[prem.index<=ts]
    if sub.empty: return None
    e=float(sub.Close.iloc[-1])
    if e<=0: return None
    T=e*(1+tgt/100); S=e*(1-stp/100); last=e
    for v in prem[prem.index>ts].Close:
        last=float(v)
        if last<=S: return -stp
        if last>=T: return tgt
    return round((last/e-1)*100,2)

def resample_tf(d5, factor):
    if factor==1: return d5
    g=np.arange(len(d5))//factor
    agg=d5.groupby(g).agg(Open=('Open','first'),High=('High','max'),
        Low=('Low','min'),Close=('Close','last'),Volume=('Volume','sum'))
    # Label each resampled bar with its CLOSE time (last 5-min sub-bar + 5min), so a
    # candle is only "known" after it completes — entry uses premium AT/AFTER the close,
    # never the favorable move that formed the candle. (Fixes look-ahead.)
    n=len(d5)
    agg.index=pd.DatetimeIndex([d5.index[min(i*factor+factor-1, n-1)]+pd.Timedelta(minutes=5)
                                for i in range(len(agg))])
    return agg

def collect_tf(factor, orb_bars, mom_bars, n_days=30, cutoff="13:00"):
    # patch the timeframe-dependent windows
    signals.ORB_LOOKBACK_MINUTES=orb_bars
    signals.MOMENTUM_BARS=mom_bars
    config.ORB_BARS=orb_bars
    from engine.config import OPTION_STRIKE_OFFSET, TRADING_START
    days=_tdays(n_days)
    from_dt=days[0]-timedelta(days=3); to_dt=days[-1]+timedelta(days=1)
    start_min, cut_min=_hhmm(TRADING_START), _hhmm(cutoff)
    out=[]
    for k,under in enumerate(UNIVERSE):
        if (k+1)%25==0: print(f"  tf{factor} ...{k+1}/{len(UNIVERSE)}", flush=True)
        daily=fetch_upstox_historical(under,unit="days",interval=1,
              from_date=(days[0]-timedelta(days=40)).strftime("%Y-%m-%d"),to_date=to_dt.strftime("%Y-%m-%d"))
        five=_fetch_5min_chunked(under,from_dt,to_dt)
        if five.empty or daily.empty: continue
        for day in days:
            raw=five[five.index.date==day]
            if len(raw)<7*factor: continue
            d5=resample_tf(raw, factor)
            if len(d5)<orb_bars+2: continue
            dfd=daily[daily.index.date<day]
            if len(dfd)<20: continue
            for i in range(orb_bars,len(d5)):
                ts=d5.index[i]; m=_bmin(ts)
                if m<start_min: continue
                if m>cut_min: break
                part=d5.iloc[:i+1]
                sig=signals.compute_all_families(under,part,dfd,vix=14.0,nifty_pct=0.0)
                if not sig["passes_gate_1"]: continue
                ok,od,vr=signals.is_orb_confirmed(part)
                if not (ok and od==sig["direction"]): continue
                spot=float(part.Close.iloc[-1]); direction=sig["direction"]
                opt=get_option_by_offset(under,spot,day,"CE" if direction=="LONG" else "PE",OPTION_STRIKE_OFFSET)
                if not opt: break
                prem=fetch_option_premium_5min(opt["key"],day)
                if prem.empty: break
                rec={"day":str(day),"under":under}
                for nm,(tg,st) in {"p1020":(10,20),"p2010":(20,10),"p155":(15,5),"p105":(10,5)}.items():
                    rec[nm]=_outcome(prem,ts,tg,st)
                if rec["p1020"] is None: break
                out.append(rec); break
    return out

def winrate(rows,key):
    vals=[r[key] for r in rows if r.get(key) is not None]; n=len(vals)
    if not n: return (0,0,0.0)
    g=sum(1 for v in vals if v>0)
    return (n,round(g/n*100),round(sum(vals)/n,2))
def split(rows):
    days=sorted({r["day"] for r in rows}); cut=days[int(len(days)*0.55)]
    return [r for r in rows if r["day"]<cut],[r for r in rows if r["day"]>=cut]
def report(label,rows):
    tr,te=split(rows)
    print(f"\n===== {label} =====  signals={len(rows)} ({len(rows)/30:.1f}/day)")
    print(f"{'exit':<10}{'ALL n/win/net':<24}{'TRAIN win/net':<20}{'TEST win/net'}")
    for nm,key in [("+10/-20","p1020"),("+20/-10","p2010"),("+15/-5","p155"),("+10/-5","p105")]:
        a=winrate(rows,key);t=winrate(tr,key);s=winrate(te,key)
        print(f"{nm:<10}{f'{a[0]}/{a[1]}%/{a[2]:+}':<24}{f'{t[1]}%/{t[2]:+}':<20}{f'{s[1]}%/{s[2]:+}'}")

for factor,orb,mom,name in [(2,3,6,"10-min"),(3,2,4,"15-min")]:
    print(f"\n\n#### {name} candles ####",flush=True)
    rows=collect_tf(factor,orb,mom)
    report(f"{name}  (ORB {orb} bars/30min, MOM {mom} bars/60min)",rows)
