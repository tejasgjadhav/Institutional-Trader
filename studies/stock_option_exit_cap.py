"""Stock options: does REMOVING the +10% cap (let winners ride to EOD) beat the current
+10% target? Same live gates (3-Family + aligned + Gate4 ext<=2.9), -20% stop, 1 lot.
Tests several upper-target levels incl. 'no cap' (ride to EOD). Does NOT touch live config."""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
sys.path.insert(0, "/Users/sayali/files/institutional-trader/studies")
import align_bt as A
from datetime import timedelta
from engine.config import (UNIVERSE, TRADING_START, NO_NEW_TRADES_AFTER,
                           OPTION_STRIKE_OFFSET, PREMIUM_STOP_PCT, MAX_ENTRY_EXTENSION_PCT)

def collect(n_days, targets):
    """For each signal, record the option premium series once, then evaluate every target
    level on it (so all variants see the exact same trades — clean apples-to-apples)."""
    days = A.tdays(n_days)
    a, b = days[0]-timedelta(days=3), days[-1]+timedelta(days=1)
    sm, cm = A.hhmm(TRADING_START), A.hhmm(NO_NEW_TRADES_AFTER)
    nifty5 = A._fetch_5min_chunked("NIFTY", a, b)
    rows = []
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
                nd = 0
                if not nday.empty and nopen:
                    ns = nday[nday.index <= ts]
                    if not ns.empty:
                        nc = float(ns.Close.iloc[-1]); nd = 1 if nc>nopen else (-1 if nc<nopen else 0)
                if not ((direction=="LONG" and nd==1) or (direction=="SHORT" and nd==-1)): continue  # Gate3
                spot = float(part.Close.iloc[-1])
                ext = (spot-d_open)/d_open*100; ext = ext if direction=="LONG" else -ext
                if ext > MAX_ENTRY_EXTENSION_PCT: continue   # Gate4
                opt = A.get_option_by_offset(under, spot, day, "CE" if direction=="LONG" else "PE", OPTION_STRIKE_OFFSET)
                if not opt: break
                prem = A.fetch_option_premium_5min(opt["key"], day)
                if prem.empty: break
                lot = int(opt.get("lot",0) or 0)
                res = {}
                for tg in targets:
                    pnl, entry = A.outcome(prem, ts, tg, PREMIUM_STOP_PCT)
                    res[tg] = (pnl, entry)
                if res.get(targets[0], (None,))[0] is None: break
                rows.append({"under":under,"lot":lot,"res":res})
                break
    return rows

def report(name, rows, tg):
    good = [r for r in rows if r["res"].get(tg) and r["res"][tg][0] is not None]
    if not good: print(f"  {name:26}: none"); return
    n=len(good); w=sum(1 for r in good if r["res"][tg][0]>0)
    rs=sum(r["res"][tg][1]*r["lot"]*r["res"][tg][0]/100 for r in good)
    cap=sum(r["res"][tg][1]*r["lot"] for r in good)
    avgw=[r["res"][tg][0] for r in good if r["res"][tg][0]>0]
    print(f"  {name:26}: trades={n:3} WIN={w/n*100:3.0f}% P&L=Rs{rs:+9,.0f} ({rs/cap*100:+.1f}% on cap) avgWin={sum(avgw)/max(1,len(avgw)):+.1f}%")

TARGETS = [10, 20, 30, 999]   # 999 = no cap, ride to EOD
LBL = {10:"+10% (CURRENT)", 20:"+20% cap", 30:"+30% cap", 999:"NO CAP (ride to EOD)"}
for N in (30, 60):
    print(f"\n=== {N}-DAY · stock options · live gates · -20% stop · 1 lot (GROSS) ===")
    rows = collect(N, TARGETS)
    for tg in TARGETS:
        report(LBL[tg], rows, tg)
print("\nDONE")
