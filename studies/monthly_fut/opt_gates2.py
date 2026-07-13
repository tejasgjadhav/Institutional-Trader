"""8-pick + momentum gate + TIGHTER stop to cap the -50% crash month. Also test a mid-month
PORTFOLIO stop (cut whole book if down >X% intra-cycle). IS bhav 2019->Sep24."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "studies/monthly_fut")
from bt import load, near_month, build_features, cycles, asof
from opt_bt2 import day_opts, call_close, spf
from opt_maxtrades import picks

def mom_gate(nif, d):
    s = nif[nif.index <= d]
    if len(s) < 210: return False
    px=float(s.iloc[-1]); ma200=float(s.rolling(200).mean().iloc[-1])
    if px<=ma200: return False
    return px/float(s.iloc[-22])-1 > -0.02

def trade_ret_sl(sym, entry_d, exp, eday, by_sym, sl):
    g = by_sym.get(sym)
    if g is None or entry_d not in g.index: return None
    e=float(g.loc[entry_d]["close"]); r0=g.loc[entry_d]
    res=call_close(eday, sym, exp, e)
    if not res or res[1] is None or res[1]<=0: return None
    K,prem0,_=res
    path=g.loc[(g.index>entry_d)&(g.index<=exp)]; path=path[path["expiry"]==r0["expiry"]]
    if path.empty: return None
    rets=(path["close"]/e-1); xp=None
    for i,(d2,rr) in enumerate(rets.items()):
        tp=0.01 if i+1>12 else 0.02
        if rr>=tp or rr<=-sl:
            dd=day_opts(pd.Timestamp(d2).date()); r2=call_close(dd,sym,exp,K) if dd is not None else None
            xp=r2[1] if (r2 and r2[1] and r2[1]>0) else max(0.0,float(path.loc[d2]["close"])-K); break
    if xp is None:
        last=path.iloc[-1]; se=float(last["settle"] if np.isfinite(last["settle"]) and last["settle"]>0 else last["close"])
        xp=max(0.0,se-K)
    return (xp-prem0-(prem0+xp)*spf(prem0))/prem0

def run(sl, npick=8):
    p=load(); nm=near_month(p)
    cont={s:g.set_index("date")["close"] for s,g in nm.groupby("symbol")}
    feats,reg=build_features(cont,cont["NIFTY"]); cyc=cycles(nm)
    by_sym={s:g.set_index("date") for s,g in nm.groupby("symbol")}
    nif=cont["NIFTY"]; months=[]; win=[]
    for entry_d,exp in cyc:
        entry_d=pd.Timestamp(entry_d)
        if entry_d.year>=2024: continue
        if not mom_gate(nif,entry_d): continue
        eday=day_opts(entry_d.date())
        if eday is None: continue
        rs=[trade_ret_sl(sym,entry_d,exp,eday,by_sym,sl) for sym in picks(feats,reg,entry_d,npick)]
        rs=[x for x in rs if x is not None]
        if rs: months.append(np.mean(rs)); win+=rs
    m=np.array(months); w=np.array(win); eq=np.cumprod(1+m); dd=(eq/np.maximum.accumulate(eq)-1).min()
    print(f"mom-gate + SL{sl*100:.0f}%: trades={len(w)} win={(w>0).mean()*100:.0f}% mo={m.mean()*100:.1f}% "
          f"worst={m.min()*100:.0f}% DD={dd*100:.0f}% mo<-15%={(m<-0.15).sum()} Rs/mo={m.mean()*200000:,.0f}")

for sl in (0.05,0.04,0.03,0.025):
    run(sl)
