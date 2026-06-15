"""NIFTY only, 60 days, ORB+VWAP break entry, ATM 1 lot. Exit: +25% target / -15% stop,
else book at EOD. Report capital invested, net P&L (Rs and %), with math validation."""
import sys, json, gzip, requests
from datetime import datetime, timedelta
import numpy as np, pandas as pd
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from engine.backtest120 import _fetch_5min_chunked
from engine.options import get_option_by_offset, fetch_option_premium_5min

URL="https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
def near_key(day):
    raw=json.loads(gzip.decompress(requests.get(URL,timeout=60).content))
    fs=[{"key":i["instrument_key"],"expiry":int(i["expiry"])} for i in raw
        if i.get("segment")=="NSE_FO" and i.get("instrument_type")=="FUT" and (i.get("name") or "")=="NIFTY"]
    fs=sorted(fs,key=lambda c:c["expiry"]); dm=int(datetime(day.year,day.month,day.day).timestamp()*1000)
    nr=[c for c in fs if c["expiry"]>=dm]; return nr[0]["key"] if nr else fs[-1]["key"]
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
TARGET,STOP=25.0,15.0

days=tdays(60); a,b=days[0]-timedelta(days=3),days[-1]+timedelta(days=1)
spot5=_fetch_5min_chunked("NIFTY",a,b); fut=_fetch_5min_chunked(near_key(days[-1]),a,b)
trades=[]
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
    opt=get_option_by_offset("NIFTY",spot,day,typ,0)
    if not opt: continue
    prem=fetch_option_premium_5min(opt["key"],day)
    if prem.empty: continue
    psub=prem[prem.index<=ets]
    if psub.empty: continue
    ep=float(psub.Close.iloc[-1]); lot=int(opt.get("lot",0) or 0)
    if ep<=0 or lot<=0: continue
    tgt,stp=ep*(1+TARGET/100),ep*(1-STOP/100); exitp=None; reason=None
    for ts2,row in prem[prem.index>ets].iterrows():
        px=float(row.Close)
        if px<=stp: exitp=stp; reason="STOP"; break
        if px>=tgt: exitp=tgt; reason="TARGET"; break
    if exitp is None: exitp=float(prem.Close.iloc[-1]); reason="BOOK"
    trades.append({"day":str(day),"dir":direction,"strike":opt["strike"],"typ":typ,"lot":lot,
        "entry":ep,"exit":exitp,"cap":ep*lot,"pnl":(exitp-ep)*lot,"reason":reason})

df=pd.DataFrame(trades)
print(f"NIFTY | 60 days requested -> {df.day.nunique()} trading days with a signal "
      f"({df.day.min()} .. {df.day.max()})")
print(f"Policy: +{TARGET:.0f}% target / -{STOP:.0f}% stop, ATM, 1 lot (lot={df.lot.iloc[0]})\n")
n=len(df); wins=(df.pnl>0).sum(); cap=df.cap.sum(); pnl=df.pnl.sum()
peak=df.groupby("day").cap.sum().max()
print(f"  trades                 : {n}  (wins {wins}, losses {n-wins}, win% {wins/n*100:.0f}%)")
print(f"  TOTAL capital invested : Rs {cap:,.0f}   (sum of entry premium x lot, all trades)")
print(f"  peak single-day capital: Rs {peak:,.0f}   (intraday -> this is what you actually need)")
print(f"  NET P&L                : Rs {pnl:,.0f}")
print(f"  % on total invested    : {pnl/cap*100:+.2f}%")
print(f"  % on peak capital      : {pnl/peak*100:+.2f}%   (since capital recycles daily)")
print(f"  avg P&L per trade      : Rs {pnl/n:,.0f}")
print(f"  exits                  : {dict(df.reason.value_counts())}")
# validation
print(f"\n  [validate] sum(entry*lot)        = Rs {(df.entry*df.lot).sum():,.2f} == invested {cap:,.2f} -> {abs((df.entry*df.lot).sum()-cap)<0.01}")
print(f"  [validate] sum((exit-entry)*lot) = Rs {((df.exit-df.entry)*df.lot).sum():,.2f} == P&L {pnl:,.2f} -> {abs(((df.exit-df.entry)*df.lot).sum()-pnl)<0.01}")
print("\n  per-trade:")
for _,r in df.iterrows():
    print(f"   {r.day} {r.dir:5} {int(r.strike)}{r.typ} entry={r.entry:7.2f} exit={r.exit:7.2f} [{r.reason:6}] "
          f"cap={r.cap:8,.0f} pnl={r.pnl:+8,.0f}")
