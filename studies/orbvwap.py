"""
Buy-only intraday ORB + VWAP on NIFTY/BANKNIFTY index options.

Faithful to the spec:
  - ORB = first 15 min (3x 5-min bars, 9:15-9:30) on the index FUTURES (real volume).
  - Session VWAP on futures. CALL = close breaks ABOVE ORB high AND holds above VWAP;
    PUT = close breaks BELOW ORB low AND holds below VWAP.
  - Break + RETEST entry: after the break, a later bar pulls back to tag the ORB level
    but CLOSES back on the breakout side (and the right side of VWAP). Enter at that close.
  - Buy ATM or 1-strike ITM index option (not far OTM).
  - Window: first 90 minutes (entries 9:30-10:45). 1 setup per day per index.
  - Exit: -STOP% premium stop, OR futures closes back on the wrong side of VWAP
    (trend break / ORB reclaim fail), OR EOD square-off. Intraday only, no fixed target.
  - "Clean trend" filter optional: VWAP sloping the trade way + price extended from VWAP.
"""
import sys, json, gzip, requests
from datetime import datetime, timedelta
import numpy as np, pandas as pd
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from engine.data_fetcher import fetch_upstox_historical
from engine.backtest120 import _fetch_5min_chunked
from engine.options import get_option_by_offset, fetch_option_premium_5min

URL="https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
def load_futs():
    raw=json.loads(gzip.decompress(requests.get(URL,timeout=60).content))
    futs={}
    for i in raw:
        if i.get("segment")=="NSE_FO" and i.get("instrument_type")=="FUT":
            nm=i.get("name") or ""
            if nm in ("NIFTY","BANKNIFTY"):
                futs.setdefault(nm,[]).append({"key":i["instrument_key"],"expiry":int(i["expiry"])})
    return {k:sorted(v,key=lambda c:c["expiry"]) for k,v in futs.items()}

def tdays(n):
    days,d=[],datetime.now()-timedelta(days=1)
    while len(days)<n:
        if d.weekday()<5: days.append(d.date())
        d-=timedelta(days=1)
    return sorted(days)
def bmin(ts): return ts.hour*60+ts.minute
def vwap_series(df):
    tp=(df.High+df.Low+df.Close)/3
    return (tp*df.Volume).cumsum()/df.Volume.cumsum()

def near_fut_key(futs, nm, day):
    day_ms=int(datetime(day.year,day.month,day.day).timestamp()*1000)
    near=[c for c in futs.get(nm,[]) if c["expiry"]>=day_ms]
    return near[0]["key"] if near else (futs[nm][-1]["key"] if futs.get(nm) else None)

ENTRY_START, ENTRY_END = 9*60+30, 10*60+45   # first 90 min, after ORB
RETEST_BUF = 0.0007   # 0.07% tag tolerance for the retest

_FUT={}; _SPOT={}; _PREM={}
def cfut(nm, fkey, a, b):
    if nm not in _FUT: _FUT[nm]=_fetch_5min_chunked(fkey, a, b)
    return _FUT[nm]
def cspot(nm, a, b):
    if nm not in _SPOT: _SPOT[nm]=_fetch_5min_chunked(nm, a, b)
    return _SPOT[nm]
def cprem(key, day):
    kk=(key,str(day))
    if kk not in _PREM: _PREM[kk]=fetch_option_premium_5min(key, day)
    return _PREM[kk]

ARM=12.0   # 'breathe': arm VWAP exit only after +12% premium
TGT=30.0   # 'target': premium take-profit
def run(n_days=40, strike_off=0, stop_pct=30, clean_filter=False, exit_mode="spec"):
    futs=load_futs(); days=tdays(n_days)
    from_dt=days[0]-timedelta(days=3); to_dt=days[-1]+timedelta(days=1)
    trades=[]
    for nm in ("NIFTY","BANKNIFTY"):
        spot5=cspot(nm, from_dt, to_dt)   # index spot, for strike pick
        fkey=near_fut_key(futs, nm, days[-1])
        fut_all=cfut(nm, fkey, from_dt, to_dt)   # chunked (v3 range cap)
        if fut_all.empty: continue
        for day in days:
            f=fut_all[fut_all.index.date==day]
            if len(f)<10: continue
            sp=spot5[spot5.index.date==day] if not spot5.empty else f
            orb=f.iloc[:3]; orb_hi=float(orb.High.max()); orb_lo=float(orb.Low.min())
            vw=vwap_series(f)
            broke_up=broke_dn=False
            entry=None
            for i in range(3,len(f)):
                ts=f.index[i]; m=bmin(ts)
                if m<ENTRY_START:
                    # still update break state pre-window? window starts 9:30 anyway
                    pass
                if m>ENTRY_END: break
                c=float(f.Close.iloc[i]); lo=float(f.Low.iloc[i]); hi=float(f.High.iloc[i]); v=float(vw.iloc[i])
                # establish break
                if c>orb_hi and c>v: broke_up=True
                if c<orb_lo and c<v: broke_dn=True
                # LONG retest: after break, tag ORB hi from above but close holds above hi & vwap
                day_open=float(f.Open.iloc[0])
                if broke_up and lo<=orb_hi*(1+RETEST_BUF) and c>orb_hi and c>v:
                    if clean_filter:
                        slope=v-float(vw.iloc[max(0,i-3)]); dmove=(c-day_open)/day_open
                        if not (slope>0 and dmove>0.0025): continue   # VWAP rising + >0.25% up on day
                    entry=("LONG",ts,float(sp.Close[sp.index<=ts].iloc[-1]) if not sp.empty and (sp.index<=ts).any() else c); break
                if broke_dn and hi>=orb_lo*(1-RETEST_BUF) and c<orb_lo and c<v:
                    if clean_filter:
                        slope=v-float(vw.iloc[max(0,i-3)]); dmove=(c-day_open)/day_open
                        if not (slope<0 and dmove<-0.0025): continue
                    entry=("SHORT",ts,float(sp.Close[sp.index<=ts].iloc[-1]) if not sp.empty and (sp.index<=ts).any() else c); break
            if not entry: continue
            direction,ets,spot=entry
            typ="CE" if direction=="LONG" else "PE"
            opt=get_option_by_offset(nm,spot,day,typ,strike_off)
            if not opt: continue
            prem=cprem(opt["key"],day)
            if prem.empty: continue
            psub=prem[prem.index<=ets]
            if psub.empty: continue
            entry_prem=float(psub.Close.iloc[-1])
            if entry_prem<=0: continue
            # walk forward on futures bars after entry. exit_mode controls the leash:
            #  spec    = exit on first fut close across VWAP (tight, as written)
            #  buffer  = exit only on close >0.1% across VWAP AND back across ORB level
            #  breathe = ignore VWAP until trade is +ARM% in premium; else -stop% premium
            #  target  = +TGT% premium target OR VWAP loss (buffered), whichever first
            exit_pnl=None; reason=None; armed=False
            ORBlvl=orb_hi if direction=="LONG" else orb_lo
            fafter=f[f.index>ets]
            for j in range(len(fafter)):
                ts=fafter.index[j]; fc=float(fafter.Close.iloc[j]); vv=float(vw[vw.index==ts].iloc[0]) if (vw.index==ts).any() else None
                pr=prem[prem.index<=ts]
                if pr.empty: continue
                pnl=(float(pr.Close.iloc[-1])/entry_prem-1)*100
                if pnl<=-stop_pct: exit_pnl=-stop_pct; reason="STOP"; break
                if exit_mode=="target" and pnl>=TGT: exit_pnl=round(pnl,2); reason="TGT"; break
                if pnl>=ARM: armed=True
                vlost=False
                if vv is not None:
                    if exit_mode=="spec":
                        vlost = (fc<vv) if direction=="LONG" else (fc>vv)
                    elif exit_mode in ("buffer","target"):
                        b=vv*0.001
                        vlost = (fc<vv-b and fc<ORBlvl) if direction=="LONG" else (fc>vv+b and fc>ORBlvl)
                    elif exit_mode=="breathe":
                        vlost = armed and ((fc<vv) if direction=="LONG" else (fc>vv))
                if vlost: exit_pnl=round(pnl,2); reason="VWAP"; break
                if bmin(ts)>=15*60+10: exit_pnl=round(pnl,2); reason="EOD"; break
            if exit_pnl is None:
                last=float(prem.Close.iloc[-1]); exit_pnl=round((last/entry_prem-1)*100,2); reason="EOD"
            trades.append({"day":str(day),"idx":nm,"dir":direction,"pnl":exit_pnl,"reason":reason})
    return trades

def summ(trades):
    n=len(trades)
    if not n: return "no trades"
    g=sum(1 for t in trades if t["pnl"]>0); net=sum(t["pnl"] for t in trades)
    days=sorted({t["day"] for t in trades})
    cut=days[int(len(days)*0.55)] if days else None
    tr=[t for t in trades if t["day"]<cut]; te=[t for t in trades if t["day"]>=cut]
    def wr(L):
        if not L: return "0/-/-"
        gg=sum(1 for t in L if t["pnl"]>0); return f"{len(L)}/{round(gg/len(L)*100)}%/{round(sum(t['pnl'] for t in L)/len(L),2):+}"
    rs={}
    for t in trades: rs[t["reason"]]=rs.get(t["reason"],0)+1
    return f"n={n} win={round(g/n*100)}% net={round(net/n,2):+}/trade | TRAIN {wr(tr)} TEST {wr(te)} | exits={rs}"

print("=== Buy-only ORB+VWAP on index options (40 days, ~27 trading) ===")
print(f"ARM(breathe)=+{ARM}%  TGT(target)=+{TGT}%  premium stop=-30%\n")
for off,lbl in [(0,"ATM"),(-1,"ITM1")]:
    for mode in ["spec","buffer","breathe","target"]:
        for cf in [False,True]:
            t=run(n_days=40,strike_off=off,stop_pct=30,clean_filter=cf,exit_mode=mode)
            print(f"{lbl:4} {mode:8} {'clean' if cf else 'raw  '}: {summ(t)}")
    print()
