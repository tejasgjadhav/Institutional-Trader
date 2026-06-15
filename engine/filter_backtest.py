"""
Filter backtest — find ONE extra cutoff that raises win rate on the fixed-gate signals.

Collects each trade-ready signal with rich features (RSI, market alignment, conviction,
volume strength, time) + the option premium outcome at both exits. Then we test each
candidate filter with train/test validation to see which genuinely improves win rate.
"""
import logging
from datetime import datetime, timedelta
import pandas as pd

from engine.config import UNIVERSE, TRADING_START, NO_NEW_TRADES_AFTER, OPTION_STRIKE_OFFSET
from engine.data_fetcher import fetch_upstox_historical
from engine.signals import compute_all_families, is_orb_confirmed
from engine.options import get_option_by_offset, fetch_option_premium_5min
from engine.backtest120 import _fetch_5min_chunked

logger = logging.getLogger(__name__)


def compute_rsi(close: pd.Series, period: int = 14) -> float:
    """Standard RSI of the latest bar."""
    if len(close) < period + 1:
        return 50.0
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    rsi = 100 - 100 / (1 + rs)
    val = rsi.iloc[-1]
    return float(val) if pd.notna(val) else 50.0

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


def collect(n_days=30, cutoff="13:00", progress=None) -> list:
    days=_tdays(n_days)
    from_dt=days[0]-timedelta(days=3); to_dt=days[-1]+timedelta(days=1)
    start_min, cut_min=_hhmm(TRADING_START), _hhmm(cutoff)
    nifty5=_fetch_5min_chunked("NIFTY", from_dt, to_dt)

    out=[]
    for k,under in enumerate(UNIVERSE):
        if progress: progress(k+1,len(UNIVERSE),under)
        daily=fetch_upstox_historical(under,unit="days",interval=1,
              from_date=(days[0]-timedelta(days=40)).strftime("%Y-%m-%d"),to_date=to_dt.strftime("%Y-%m-%d"))
        five=_fetch_5min_chunked(under,from_dt,to_dt)
        if five.empty or daily.empty: continue
        for day in days:
            d5=five[five.index.date==day]
            if len(d5)<7: continue
            dfd=daily[daily.index.date<day]
            if len(dfd)<20: continue
            nday=nifty5[nifty5.index.date==day]; nopen=float(nday.Open.iloc[0]) if not nday.empty else 0
            day_open=float(d5.Open.iloc[0])
            for i in range(6,len(d5)):
                ts=d5.index[i]; m=_bmin(ts)
                if m<start_min: continue
                if m>cut_min: break
                part=d5.iloc[:i+1]
                sig=compute_all_families(under,part,dfd,vix=14.0,nifty_pct=0.0)
                if not sig["passes_gate_1"]: continue
                ok,od,vr=is_orb_confirmed(part)
                if not (ok and od==sig["direction"]): continue
                # features
                rsi=compute_rsi(part["Close"], 14)
                spot=float(part.Close.iloc[-1])
                day_move=(spot-day_open)/day_open*100 if day_open else 0
                nifty_dir=0
                if not nday.empty and nopen:
                    ns=nday[nday.index<=ts]
                    if not ns.empty:
                        nifty_dir=1 if float(ns.Close.iloc[-1])>nopen else (-1 if float(ns.Close.iloc[-1])<nopen else 0)
                direction=sig["direction"]
                # option outcome
                opt=get_option_by_offset(under,spot,day,"CE" if direction=="LONG" else "PE",OPTION_STRIKE_OFFSET)
                if not opt: break
                prem=fetch_option_premium_5min(opt["key"],day)
                if prem.empty: break
                pnl_1020=_outcome(prem,ts,10,20); pnl_155=_outcome(prem,ts,15,5)
                pnl_2to1=_outcome(prem,ts,10,5)   # +10%/-5% = 2:1 reward:risk
                pnl_2010=_outcome(prem,ts,20,10)  # +20%/-10% = 2:1 reward:risk
                if pnl_1020 is None: break
                fam=sig.get("families_detail",{})
                out.append({
                    "day":str(day),"under":under,"dir":direction,"time":m,
                    "alpha_z":round(sig["alpha_z"],3),"abs_alpha":round(abs(sig["alpha_z"]),3),
                    "breadth":sig["breadth"],
                    "trend_z":round(fam.get("TREND",{}).get("z_score",0),3),
                    "flow_z":round(fam.get("FLOW",{}).get("z_score",0),3),
                    "event_z":round(fam.get("EVENT",{}).get("z_score",0),3),
                    "rsi":round(rsi,1),"vol_ratio":round(vr,2),"day_move":round(day_move,2),
                    "nifty_dir":nifty_dir,"aligned":1 if (direction=="LONG" and nifty_dir==1) or (direction=="SHORT" and nifty_dir==-1) else 0,
                    "pnl_1020":pnl_1020,"pnl_155":pnl_155,"pnl_2to1":pnl_2to1,"pnl_2010":pnl_2010,
                    "win_2to1":1 if (pnl_2to1 is not None and pnl_2to1>0) else 0,
                })
                break
    return out
