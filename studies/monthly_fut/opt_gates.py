"""8-pick long-call monthly book + MARKET-LEVEL loss-minimizing gates (the tail is crash months).
Gates tested at CYCLE ENTRY (all use NIFTY only, no lookahead):
  base    : NIFTY>200DMA (existing regime gate)
  +50dma  : also NIFTY>50DMA (stronger uptrend)
  +slope  : also NIFTY 200DMA rising vs 21d ago
  +mom    : also NIFTY 1-mo return > -2% (don't buy calls into a falling market)
  +lowvol : also NIFTY 20d realized vol < 22% ann. (skip high-vol/crash-prone regimes)
  ALL     : 50dma + slope + mom>-2% + vol<22%
IS bhav premiums 2019->Sep24. 8 picks, equal-weight Rs2L, early-exit +2%/-5%.
"""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "studies/monthly_fut")
from bt import load, near_month, build_features, cycles, asof
from opt_bt2 import day_opts, call_close, spf
from opt_maxtrades import picks, trade_ret

def gate_ok(nif, d, which):
    s = nif[nif.index <= d]
    if len(s) < 210: return False
    px = float(s.iloc[-1])
    ma200 = float(s.rolling(200).mean().iloc[-1])
    if px <= ma200: return False                        # base regime gate
    ma50 = float(s.rolling(50).mean().iloc[-1])
    ma200_prev = float(s.rolling(200).mean().iloc[-22])
    mom1 = px/float(s.iloc[-22]) - 1
    vol20 = float(s.pct_change().iloc[-20:].std())*(252**0.5)
    if which=="base":   return True
    if which=="+50dma": return px > ma50
    if which=="+slope": return ma200 > ma200_prev
    if which=="+mom":   return mom1 > -0.02
    if which=="+lowvol":return vol20 < 0.22
    if which=="ALL":    return (px>ma50) and (ma200>ma200_prev) and (mom1>-0.02) and (vol20<0.22)
    return True

def run(which, npick=8):
    p = load(); nm = near_month(p)
    cont = {s: g.set_index("date")["close"] for s,g in nm.groupby("symbol")}
    feats, reg = build_features(cont, cont["NIFTY"]); cyc = cycles(nm)
    by_sym = {s: g.set_index("date") for s,g in nm.groupby("symbol")}
    nif = cont["NIFTY"]; months=[]; win=[]; skipped=0
    for entry_d, exp in cyc:
        entry_d = pd.Timestamp(entry_d)
        if entry_d.year >= 2024: continue
        if not gate_ok(nif, entry_d, which): skipped+=1; continue
        eday = day_opts(entry_d.date())
        if eday is None: continue
        rs=[]
        for sym in picks(feats, reg, entry_d, npick):
            t = trade_ret(sym, entry_d, exp, eday, by_sym)
            if t: rs.append(t[0])
        if not rs: continue
        months.append(np.mean(rs)); win+=rs
    m=np.array(months); w=np.array(win)
    eq=np.cumprod(1+m); dd=(eq/np.maximum.accumulate(eq)-1).min()
    neg=(m<-0.15).sum()
    print(f"{which:8s} trades={len(w):4d} months={len(m):2d} skip={skipped:2d} win={(w>0).mean()*100:4.0f}% "
          f"mo={m.mean()*100:5.1f}% worst={m.min()*100:6.0f}% DD={dd*100:5.0f}% mo<-15%={neg} "
          f"Rs/mo={m.mean()*200000:7,.0f}")

for w in ("base","+50dma","+slope","+mom","+lowvol","ALL"):
    run(w)
