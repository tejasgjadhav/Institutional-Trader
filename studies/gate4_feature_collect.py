"""Re-run 365d aligned signals, capturing signal-TIME features, to hunt for a Gate 4
that separates winners from losers. Saves /tmp/g4_365.json."""
import sys, warnings, json
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from datetime import datetime, timedelta
from engine.config import UNIVERSE, TRADING_START, NO_NEW_TRADES_AFTER
from engine.data_fetcher import fetch_upstox_historical
from engine.signals import compute_all_families, is_orb_confirmed
from engine.backtest120 import _fetch_5min_chunked

def tdays(n):
    days, d = [], datetime.now()-timedelta(days=1)
    while len(days)<n:
        if d.weekday()<5: days.append(d.date())
        d-=timedelta(days=1)
    return sorted(days)
def bmin(ts): return ts.hour*60+ts.minute
def hhmm(s): h,m=map(int,s.split(":")); return h*60+m

def collect(n_days):
    days=tdays(n_days); a,b=days[0]-timedelta(days=3),days[-1]+timedelta(days=1)
    sm,cm=hhmm(TRADING_START),hhmm(NO_NEW_TRADES_AFTER)
    nifty5=_fetch_5min_chunked("NIFTY",a,b); out=[]
    for k,under in enumerate(UNIVERSE):
        if (k+1)%20==0: print(f"  ...{k+1}/{len(UNIVERSE)}",flush=True)
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
            nday=nifty5[nifty5.index.date==day]
            nopen=float(nday.Open.iloc[0]) if not nday.empty else 0
            d_open=float(d5.Open.iloc[0])
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
                direction=sig["direction"]
                nifty_dir=0
                if not nday.empty and nopen:
                    ns=nday[nday.index<=ts]
                    if not ns.empty:
                        nc=float(ns.Close.iloc[-1]); nifty_dir=1 if nc>nopen else (-1 if nc<nopen else 0)
                aligned=1 if ((direction=="LONG" and nifty_dir==1) or (direction=="SHORT" and nifty_dir==-1)) else 0
                if not aligned: break  # only study aligned (Gate 3 already on)
                c=float(part.Close.iloc[-1])
                rest=d5.Close[d5.index>ts]
                stop=c*0.99 if direction=="LONG" else c*1.01
                ex=None
                for px in rest:
                    px=float(px)
                    if (direction=="LONG" and px<=stop) or (direction=="SHORT" and px>=stop): ex=stop; break
                if ex is None: ex=float(rest.iloc[-1]) if len(rest) else c
                ret=(ex/c-1)*100*(1 if direction=="LONG" else -1)
                nstr=abs((nc-nopen)/nopen*100) if (not nday.empty and nopen) else 0
                out.append({"day":str(day),"under":under,"dir":direction,"ret":round(ret,3),
                    "win":int(ret>0),
                    "az":round(abs(sig.get("alpha_z",0)),3),
                    "breadth":int(sig.get("breadth",0)),
                    "trend":round(sig.get("trend_z",0),3) if sig.get("trend_z") is not None else None,
                    "flow":round(sig.get("flow_z",0),3) if sig.get("flow_z") is not None else None,
                    "event":round(sig.get("event_z",0),3) if sig.get("event_z") is not None else None,
                    "vr":round(float(vr),2),
                    "tod":m,
                    "ext":round((c-d_open)/d_open*100,3),  # % from day open at signal
                    "nstr":round(nstr,3)})  # nifty strength at signal (abs %)
                break
    return out

rows=collect(365)
json.dump(rows,open("/tmp/g4_365.json","w"))
print(f"saved {len(rows)} aligned trades with features")
print("sample:",rows[0] if rows else None)
