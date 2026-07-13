"""Trade-by-trade ledger of the deployed 5-pick monthly long-call book, LAST 6 CYCLES, 1 lot each.
Real Upstox premiums. Emits: date, symbol, strike, lot, entry prem, exit prem, reason, Rs P&L,
cumulative. This is the BACKTEST record (the live book hasn't fired yet)."""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader"); sys.path.insert(0, "studies/monthly_fut")
import numpy as np, pandas as pd
from datetime import datetime, timedelta
from bt import load, near_month, build_features, cycles, asof
from opt_bt2 import sel
from engine.instruments import encode_key
from engine.expired_options import get_expiries, get_contracts, _get_json as _gj
from engine.data_fetcher import UPSTOX_BASE

def spf(p): return (min(6.0,max(1.0,60.0/p))/100.0) if p>0 else 0.06
def oser(key,d0,to):
    j=_gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}")
    if j.get("status")=="success":
        c=j.get("data",{}).get("candles",[])
        if c:
            df=pd.DataFrame(c,columns=["ts","O","H","L","C","V","OI"]); df["ts"]=pd.to_datetime(df["ts"]).dt.tz_localize(None)
            return df.set_index("ts").sort_index()["C"]
    return None

p=load(); nm=near_month(p); cont={s:g.set_index("date")["close"] for s,g in nm.groupby("symbol")}
feats,reg=build_features(cont,cont["NIFTY"]); cyc=cycles(nm); by_sym={s:g.set_index("date") for s,g in nm.groupby("symbol")}
# last 6 cycles with entry >= 2026-01-01
cyc6=[(e,x) for e,x in cyc if pd.Timestamp(e)>=pd.Timestamp("2026-01-01")][:6]
EXP={}; CH={}; rows=[]
for entry_d,exp in cyc6:
    entry_d=pd.Timestamp(entry_d)
    # regime gate
    s=cont["NIFTY"][cont["NIFTY"].index<=entry_d]
    regime = len(s)>=200 and float(s.iloc[-1])>float(s.rolling(200).mean().iloc[-1])
    if not regime:
        rows.append(dict(cycle=exp.date(), entry=entry_d.date(), sym="— REGIME OFF (NIFTY<200DMA) —",
                         strike="",lot="",eprem="",xprem="",reason="stand aside",pnl=0)); continue
    for sym in sel(feats,reg,entry_d):
        g=by_sym.get(sym)
        if g is None or entry_d not in g.index: continue
        e=float(g.loc[entry_d]["close"]); r0=g.loc[entry_d]
        try:
            if sym not in EXP: EXP[sym]=get_expiries(sym)
            cand=[x for x in EXP[sym] if x>=exp.date().isoformat()]; oexp=cand[0] if cand else None
            if not oexp: continue
            if (sym,oexp) not in CH: CH[(sym,oexp)]=sorted([c for c in get_contracts(sym,oexp) if c["instrument_type"]=="CE"],key=lambda c:float(c["strike_price"]))
            chain=CH[(sym,oexp)]
        except Exception: continue
        if not chain: continue
        ks=[float(c["strike_price"]) for c in chain]; ai=min(range(len(ks)),key=lambda i:abs(ks[i]-e))
        K=ks[ai]; key=chain[ai]["instrument_key"]; lot=int(chain[ai].get("lot_size") or 0)
        to=min(datetime.fromisoformat(oexp).date(),entry_d.date()+timedelta(days=45)).isoformat()
        ser=oser(key,entry_d.date().isoformat(),to)
        if ser is None or ser.empty: continue
        eprem=float(ser.iloc[0])
        if eprem<=0: continue
        path=g.loc[(g.index>entry_d)&(g.index<=exp)]; path=path[path["expiry"]==r0["expiry"]]
        if path.empty: continue
        rets=(path["close"]/e-1); xprem=None; reason="expiry"; xdate=path.index[-1].date()
        for i,(d2,rr) in enumerate(rets.items()):
            tp=0.01 if i+1>12 else 0.02
            if rr>=tp or rr<=-0.05:
                v=ser[ser.index.normalize()==pd.Timestamp(d2).normalize()]
                xprem=float(v.iloc[-1]) if len(v) else max(0.0,float(path.loc[d2]["close"])-K)
                reason="TP +2%" if rr>=tp else "SL -5%"; xdate=pd.Timestamp(d2).date(); break
        if xprem is None:
            last=path.iloc[-1]; se=float(last["settle"] if np.isfinite(last["settle"]) and last["settle"]>0 else last["close"]); xprem=max(0.0,se-K)
        cost=(eprem+xprem)*spf(eprem)
        pnl=(xprem-eprem-cost)*lot
        rows.append(dict(cycle=exp.date(),entry=entry_d.date(),sym=sym,strike=int(K),lot=lot,
                         eprem=round(eprem,1),xprem=round(xprem,1),reason=reason,xdate=xdate,pnl=round(pnl)))
df=pd.DataFrame(rows)
real=df[df["lot"]!=""]
df["cum"]=df["pnl"].cumsum()
print("="*104)
print(f"{'ENTRY':11} {'STOCK':13} {'CALL':9} {'lot':>4} {'BUY@':>7} {'EXIT@':>7} {'EXIT':9} {'P&L Rs':>9} {'CUM Rs':>10}")
print("="*104)
cur=None
for r in df.itertuples():
    if r.cycle!=cur: print(f"-- cycle {r.cycle} " + "-"*88); cur=r.cycle
    if r.lot=="":
        print(f"{str(r.entry):11} {r.sym}"); continue
    print(f"{str(r.entry):11} {r.sym:13} {r.strike:>6}CE {r.lot:>4} {r.eprem:>7} {r.xprem:>7} {r.reason:9} {r.pnl:>9,} {r.cum:>10,}")
print("="*104)
w=real[real["pnl"]>0]; l=real[real["pnl"]<0]
tot=real["pnl"].sum()
print(f"TRADES {len(real)} | WINS {len(w)} ({len(w)/max(len(real),1)*100:.0f}%) | LOSSES {len(l)} | "
      f"NET P&L Rs{tot:,.0f} | {'IN PROFIT' if tot>0 else 'IN LOSS'}")
print(f"avg win Rs{w['pnl'].mean():,.0f} | avg loss Rs{l['pnl'].mean():,.0f} | best Rs{real['pnl'].max():,.0f} | worst Rs{real['pnl'].min():,.0f}")
df.to_csv("studies/monthly_fut/call_ledger_6mo.csv",index=False)
print("DONE-LEDGER")
