"""30/60-day OPTION backtest: Gate 3 (aligned) vs Gate 3+Gate 4 (don't chase).
Real option premiums, +10%/-20% live exit, 1 lot. Reports win% and rupee P&L."""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
sys.path.insert(0, "/Users/sayali/files/institutional-trader/studies")
import align_bt as A
from datetime import timedelta
from engine.config import (UNIVERSE, TRADING_START, NO_NEW_TRADES_AFTER,
                           OPTION_STRIKE_OFFSET, PREMIUM_TARGET_PCT, PREMIUM_STOP_PCT,
                           MAX_ENTRY_EXTENSION_PCT)

def collect(n_days, ext_cap):
    days = A.tdays(n_days)
    a, b = days[0]-timedelta(days=3), days[-1]+timedelta(days=1)
    sm, cm = A.hhmm(TRADING_START), A.hhmm(NO_NEW_TRADES_AFTER)
    nifty5 = A._fetch_5min_chunked("NIFTY", a, b)
    out = []
    for k, under in enumerate(UNIVERSE):
        if (k+1) % 25 == 0: print(f"   ...{k+1}/{len(UNIVERSE)}", flush=True)
        try:
            daily = A.fetch_upstox_historical(under, unit="days", interval=1,
                from_date=(days[0]-timedelta(days=40)).strftime("%Y-%m-%d"), to_date=b.strftime("%Y-%m-%d"))
            five = A._fetch_5min_chunked(under, a, b)
        except Exception: continue
        if five.empty or daily.empty: continue
        for day in days:
            d5 = five[five.index.date == day]
            if len(d5) < 7: continue
            dfd = daily[daily.index.date < day]
            if len(dfd) < 20: continue
            nday = nifty5[nifty5.index.date == day]
            nopen = float(nday.Open.iloc[0]) if not nday.empty else 0
            d_open = float(d5.Open.iloc[0])
            for i in range(6, len(d5)):
                ts = d5.index[i]; m = A.bmin(ts)
                if m < sm: continue
                if m > cm: break
                part = d5.iloc[:i+1]
                sig = A.compute_all_families(under, part, dfd, vix=14.0, nifty_pct=0.0)
                if not sig["passes_gate_1"]: continue
                ok, od, vr = A.is_orb_confirmed(part)
                if not (ok and od == sig["direction"]): continue
                direction = sig["direction"]
                nifty_dir = 0
                if not nday.empty and nopen:
                    ns = nday[nday.index <= ts]
                    if not ns.empty:
                        nc = float(ns.Close.iloc[-1]); nifty_dir = 1 if nc>nopen else (-1 if nc<nopen else 0)
                aligned = (direction=="LONG" and nifty_dir==1) or (direction=="SHORT" and nifty_dir==-1)
                if not aligned: continue                         # Gate 3: reject & keep scanning
                spot = float(part.Close.iloc[-1])
                ext = (spot - d_open)/d_open*100
                ext_dir = ext if direction=="LONG" else -ext
                if ext_cap is not None and ext_dir > ext_cap: continue   # Gate 4
                opt = A.get_option_by_offset(under, spot, day, "CE" if direction=="LONG" else "PE", OPTION_STRIKE_OFFSET)
                if not opt: break
                prem = A.fetch_option_premium_5min(opt["key"], day)
                if prem.empty: break
                pnl, entry = A.outcome(prem, ts, PREMIUM_TARGET_PCT, PREMIUM_STOP_PCT)
                if pnl is None: break
                lot = int(opt.get("lot", 0) or 0)
                out.append({"day": str(day), "under": under, "pnl_pct": pnl, "entry": entry, "lot": lot})
                break
    return out

def report(name, lst):
    if not lst: print(f"  {name:28}: no trades"); return
    n=len(lst); w=sum(1 for r in lst if r["pnl_pct"]>0)
    rs=sum(r["entry"]*r["lot"]*r["pnl_pct"]/100 for r in lst)
    cap=sum(r["entry"]*r["lot"] for r in lst)
    print(f"  {name:28}: trades={n:3} WIN={w/n*100:3.0f}%  P&L=Rs{rs:+9,.0f}  (on Rs{cap:,.0f} = {rs/cap*100:+.1f}%)")

for N in (30, 60):
    print(f"\n=== {N}-DAY · stock options · +10%/-20% · 1 lot (GROSS) ===")
    g3 = collect(N, ext_cap=None)
    g4 = collect(N, ext_cap=MAX_ENTRY_EXTENSION_PCT)
    report("Gate 3 (aligned)", g3)
    report(f"Gate 3+4 (ext<={MAX_ENTRY_EXTENSION_PCT})", g4)
print("\nDONE")
