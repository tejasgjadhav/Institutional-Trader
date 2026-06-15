import sys
from datetime import datetime, timedelta
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from engine.backtest120 import _fetch_5min_chunked
from engine.options import get_option_by_offset, fetch_option_premium_5min

def tdays(n):
    days, d = [], datetime.now()-timedelta(days=1)
    while len(days)<n:
        if d.weekday()<5: days.append(d.date())
        d -= timedelta(days=1)
    return sorted(days)

days = tdays(8)
for idx in ["NIFTY", "BANKNIFTY"]:
    five = _fetch_5min_chunked(idx, days[0]-timedelta(days=2), days[-1]+timedelta(days=1))
    print(f"\n=== {idx} ===  5min rows={len(five)}")
    if not five.empty:
        last_day = five[five.index.date==days[-1]]
        print(f"  cols={list(five.columns)}")
        print(f"  last day {days[-1]}: {len(last_day)} bars, Volume sum={last_day['Volume'].sum() if 'Volume' in last_day else 'NA'}")
        print(f"  sample Volume head: {list(five['Volume'].head(3)) if 'Volume' in five else 'NA'}")
        spot = float(last_day['Close'].iloc[0]) if not last_day.empty else float(five['Close'].iloc[-1])
        for off,lbl in [(0,"ATM"),(-1,"ITM1")]:
            for typ in ["CE","PE"]:
                opt = get_option_by_offset(idx, spot, days[-1], typ, off)
                if opt:
                    prem = fetch_option_premium_5min(opt["key"], days[-1])
                    print(f"  {lbl} {typ}: strike={opt['strike']} exp={opt['expiry_date']} lot={opt['lot']} premium_bars={len(prem)}")
                else:
                    print(f"  {lbl} {typ}: NO CONTRACT")
