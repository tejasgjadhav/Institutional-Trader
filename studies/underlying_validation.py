"""180/365-day UNDERLYING-PROXY validation of the 3-Family signal.
Same gates as live (alpha-z + >=2/3 families, ORB confirm, market alignment), but the
OUTCOME is the STOCK's own forward move from signal->close (no options). Validates the
signal's directional edge on a full year of price data (the part Upstox actually serves).
"""
import sys, warnings, json
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from datetime import datetime, timedelta
from collections import defaultdict
from engine.config import UNIVERSE, TRADING_START, NO_NEW_TRADES_AFTER
from engine.data_fetcher import fetch_upstox_historical
from engine.signals import compute_all_families, is_orb_confirmed
from engine.backtest120 import _fetch_5min_chunked

def tdays(n):
    days, d = [], datetime.now() - timedelta(days=1)
    while len(days) < n:
        if d.weekday() < 5: days.append(d.date())
        d -= timedelta(days=1)
    return sorted(days)
def bmin(ts): return ts.hour*60 + ts.minute
def hhmm(s): h,m = map(int, s.split(":")); return h*60+m

def collect(n_days):
    days = tdays(n_days)
    a, b = days[0]-timedelta(days=3), days[-1]+timedelta(days=1)
    start_min, cut_min = hhmm(TRADING_START), hhmm(NO_NEW_TRADES_AFTER)
    nifty5 = _fetch_5min_chunked("NIFTY", a, b)
    out = []
    for k, under in enumerate(UNIVERSE):
        if (k+1) % 20 == 0: print(f"  ...{k+1}/{len(UNIVERSE)}", flush=True)
        try:
            daily = fetch_upstox_historical(under, unit="days", interval=1,
                    from_date=(days[0]-timedelta(days=60)).strftime("%Y-%m-%d"),
                    to_date=b.strftime("%Y-%m-%d"))
            five = _fetch_5min_chunked(under, a, b)
        except Exception:
            continue
        if five.empty or daily.empty: continue
        for day in days:
            d5 = five[five.index.date == day]
            if len(d5) < 8: continue
            dfd = daily[daily.index.date < day]
            if len(dfd) < 20: continue
            nday = nifty5[nifty5.index.date == day]
            nopen = float(nday.Open.iloc[0]) if not nday.empty else 0
            for i in range(6, len(d5)):
                ts = d5.index[i]; m = bmin(ts)
                if m < start_min: continue
                if m > cut_min: break
                part = d5.iloc[:i+1]
                try:
                    sig = compute_all_families(under, part, dfd, vix=14.0, nifty_pct=0.0)
                except Exception:
                    break
                if not sig["passes_gate_1"]: continue
                ok, od, vr = is_orb_confirmed(part)
                if not (ok and od == sig["direction"]): continue
                direction = sig["direction"]
                nifty_dir = 0
                if not nday.empty and nopen:
                    ns = nday[nday.index <= ts]
                    if not ns.empty:
                        nc = float(ns.Close.iloc[-1])
                        nifty_dir = 1 if nc > nopen else (-1 if nc < nopen else 0)
                aligned = 1 if ((direction=="LONG" and nifty_dir==1) or
                                (direction=="SHORT" and nifty_dir==-1)) else 0
                entry = float(part.Close.iloc[-1])
                rest = d5.Close[d5.index > ts]
                # signed forward return to EOD, with a 1% adverse stop (live stop cap)
                stop = entry*(0.99) if direction=="LONG" else entry*(1.01)
                exitpx = None
                for px in rest:
                    px = float(px)
                    if (direction=="LONG" and px<=stop) or (direction=="SHORT" and px>=stop):
                        exitpx = stop; break
                if exitpx is None:
                    exitpx = float(rest.iloc[-1]) if len(rest) else entry
                raw = (float(rest.iloc[-1])/entry-1)*100 if len(rest) else 0.0  # pure EOD, no stop
                signed_raw = raw if direction=="LONG" else -raw
                signed_stop = (exitpx/entry-1)*100*(1 if direction=="LONG" else -1)
                out.append({"day": str(day), "under": under, "dir": direction,
                            "aligned": aligned, "ret_eod": round(signed_raw,3),
                            "ret_stop": round(signed_stop,3)})
                break
    return out

def report(name, lst, key="ret_stop"):
    if not lst: print(f"  {name:18}: none"); return
    n=len(lst); w=sum(1 for r in lst if r[key]>0)
    avg=sum(r[key] for r in lst)/n
    print(f"  {name:18}: trades={n:4}  hit={w/n*100:4.0f}%  avg_move={avg:+.3f}%/trade")

for N in (180, 365):
    print(f"\n{'='*64}\n=== {N}-DAY UNDERLYING-PROXY · 3-Family signal directional edge ===")
    rows = collect(N)
    if not rows:
        print("  no data"); continue
    days_span = sorted({r['day'] for r in rows})
    print(f"  span {days_span[0]} .. {days_span[-1]}  ({len(days_span)} trading days)")
    print(" -- exit: ride to close with 1% adverse stop --")
    report("ALL", rows); report("ALIGNED (Gate 3)", [r for r in rows if r['aligned']==1])
    report("NOT aligned", [r for r in rows if r['aligned']==0])
    print(" -- pure EOD (no stop), directional edge only --")
    report("ALL", rows, "ret_eod"); report("ALIGNED (Gate 3)", [r for r in rows if r['aligned']==1], "ret_eod")
    # stability: split into thirds
    cut1, cut2 = days_span[len(days_span)//3], days_span[2*len(days_span)//3]
    for lbl, sub in [("oldest third", [r for r in rows if r['day']<cut1]),
                     ("middle third", [r for r in rows if cut1<=r['day']<cut2]),
                     ("newest third", [r for r in rows if r['day']>=cut2])]:
        report(f"  {lbl}", [r for r in sub if r['aligned']==1], "ret_stop")
    json.dump(rows, open(f"/tmp/uval_{N}.json","w"))
print("\nDONE")
