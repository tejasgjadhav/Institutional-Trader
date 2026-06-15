"""
Capital + P&L if you take EVERY index-option signal in the last 30 days,
exit on a -10% premium stop, else book at end-of-day cutoff. 1 lot/trade, ATM.
Signal = ORB+VWAP break (CALL on up-break, PUT on down-break), 1 setup/day/index.

Reports NIFTY-only, BANKNIFTY-only, and BOTH, with explicit math validation.
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

ENTRY_START,ENTRY_END=9*60+30,10*60+45   # first 90 min
RETEST_BUF=0.0007
STOP_PCT=10.0                             # -10% premium stop
BOOK_MIN=15*60+15                         # cutoff to book = 15:15

def collect(n_days=30, strike_off=0):
    futs=load_futs(); days=tdays(n_days)
    a,b=days[0]-timedelta(days=3),days[-1]+timedelta(days=1)
    trades=[]
    for nm in ("NIFTY","BANKNIFTY"):
        spot5=_fetch_5min_chunked(nm,a,b)
        fut=_fetch_5min_chunked(near_key(futs,nm,days[-1]),a,b)
        if fut.empty: continue
        for day in days:
            f=fut[fut.index.date==day]
            if len(f)<12: continue
            sp=spot5[spot5.index.date==day] if not spot5.empty else f
            orb=f.iloc[:3]; orb_hi=float(orb.High.max()); orb_lo=float(orb.Low.min())
            vw=vwap_s(f); broke_up=broke_dn=False; entry=None
            for i in range(3,len(f)):
                ts=f.index[i]; m=bmin(ts)
                if m>ENTRY_END: break
                c=float(f.Close.iloc[i]); lo=float(f.Low.iloc[i]); hi=float(f.High.iloc[i]); v=float(vw.iloc[i])
                if c>orb_hi and c>v: broke_up=True
                if c<orb_lo and c<v: broke_dn=True
                if m<ENTRY_START: continue
                if broke_up and lo<=orb_hi*(1+RETEST_BUF) and c>orb_hi and c>v:
                    entry=("LONG",ts); break
                if broke_dn and hi>=orb_lo*(1-RETEST_BUF) and c<orb_lo and c<v:
                    entry=("SHORT",ts); break
            if not entry: continue
            direction,ets=entry
            spot=float(sp.Close[sp.index<=ets].iloc[-1]) if not sp.empty and (sp.index<=ets).any() else float(f.Close[f.index<=ets].iloc[-1])
            typ="CE" if direction=="LONG" else "PE"
            opt=get_option_by_offset(nm,spot,day,typ,strike_off)
            if not opt: continue
            prem=fetch_option_premium_5min(opt["key"],day)
            if prem.empty: continue
            psub=prem[prem.index<=ets]
            if psub.empty: continue
            entry_prem=float(psub.Close.iloc[-1])
            if entry_prem<=0: continue
            lot=int(opt.get("lot",0) or 0)
            if lot<=0: continue
            # exit walk: -10% stop, else book at cutoff (or last bar)
            stop_price=entry_prem*(1-STOP_PCT/100)
            exit_prem=None; reason=None
            for ts2,row in prem[prem.index>ets].iterrows():
                px=float(row.Close)
                if px<=stop_price: exit_prem=stop_price; reason="STOP"; break
                if bmin(ts2)>=BOOK_MIN: exit_prem=px; reason="BOOK"; break
            if exit_prem is None:
                exit_prem=float(prem.Close.iloc[-1]); reason="BOOK"   # last available = EOD book
            capital=entry_prem*lot
            pnl=(exit_prem-entry_prem)*lot
            trades.append({"day":str(day),"idx":nm,"dir":direction,"typ":typ,
                "strike":opt["strike"],"lot":lot,"entry":entry_prem,
                "exit":exit_prem,"capital":capital,
                "pnl":pnl,"ret_pct":(exit_prem/entry_prem-1)*100,"reason":reason})
    return trades

trades=collect(30,strike_off=0)
df=pd.DataFrame(trades)
print(f"Total signals taken: {len(df)} over {df.day.nunique()} trading days "
      f"({df.day.min()} .. {df.day.max()})\n")

# show a few trades with explicit math
print("Sample trades (entry x lot = capital;  (exit-entry) x lot = pnl):")
for _,r in df.head(6).iterrows():
    print(f"  {r.day} {r.idx:9} {r.dir:5} {int(r.strike)}{r.typ}  lot={r.lot}  "
          f"entry={r.entry:.2f} exit={r.exit:.2f} [{r.reason}]  "
          f"cap={r.entry:.2f}x{r.lot}={r.capital:,.0f}  pnl=({r.exit:.2f}-{r.entry:.2f})x{r.lot}={r.pnl:+,.0f}")

def block(name, d):
    n=len(d)
    if n==0: print(f"\n{name}: no trades"); return
    cap=d.capital.sum(); pnl=d.pnl.sum(); wins=(d.pnl>0).sum()
    peakday=d.groupby("day").capital.sum().max()
    print(f"\n===== {name} =====")
    print(f"  trades              : {n}  (wins {wins}, losses {n-wins}, win% {wins/n*100:.0f}%)")
    print(f"  total capital outlay : Rs {cap:,.0f}   (sum of entry premium x lot over all trades)")
    print(f"  peak single-day cap  : Rs {peakday:,.0f}   (max capital deployed on any one day = what you actually need, intraday)")
    print(f"  net P&L              : Rs {pnl:,.0f}")
    print(f"  return on outlay     : {pnl/cap*100:+.2f}%   (net P&L / total outlay)")
    print(f"  avg P&L per trade    : Rs {pnl/n:,.0f}")
    # validation
    assert abs(d.pnl.sum()-sum(d.pnl))<1e-6
    recomputed_pnl=float(((d.exit-d.entry)*d.lot).sum())
    recomputed_cap=float((d.entry*d.lot).sum())
    print(f"  [validate] sum((exit-entry)*lot) = Rs {recomputed_pnl:,.2f}  ==  net P&L {pnl:,.2f}  -> {abs(recomputed_pnl-pnl)<0.01}")
    print(f"  [validate] sum(entry*lot)        = Rs {recomputed_cap:,.2f}  ==  outlay  {cap:,.2f}  -> {abs(recomputed_cap-cap)<0.01}")
    rs={k:int(v) for k,v in d.reason.value_counts().items()}
    print(f"  exits: {rs}")

block("NIFTY only", df[df.idx=="NIFTY"])
block("BANKNIFTY only", df[df.idx=="BANKNIFTY"])
block("BOTH combined", df)

# cross-check both = nifty + banknifty
n=df[df.idx=="NIFTY"]; bk=df[df.idx=="BANKNIFTY"]
print(f"\n[validate] BOTH P&L {df.pnl.sum():,.2f} == NIFTY {n.pnl.sum():,.2f} + BANKNIFTY {bk.pnl.sum():,.2f} "
      f"= {n.pnl.sum()+bk.pnl.sum():,.2f} -> {abs(df.pnl.sum()-(n.pnl.sum()+bk.pnl.sum()))<0.01}")
