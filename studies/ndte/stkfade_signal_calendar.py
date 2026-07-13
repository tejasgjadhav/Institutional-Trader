"""When do v2 UNION fade signals fire? Calendar distribution (goal-loop 2026-07-13).
FAST: replays UNION Donchian(5,10,15,20) breakouts across the ~100-stock universe over the OOS
window (2024-10-01 -> today) using ONLY daily underlying candles (no option fetches). For each
breakout records day-of-month, ISO weekday, week-of-month, and days-since-the-last-monthly-expiry
(last Thursday of month) — the latter is the credit-richness proxy: the c/w>=0.40 gate favours
high-DTE spreads, which occur just AFTER monthly expiry. Reentry gate (3d/side) applied so counts
match live cadence. This is the BREAKOUT distribution (pre-premium-gate); passing signals skew
further toward the post-expiry weeks because of the credit gate. Out: prints histograms.
"""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import date, timedelta
from collections import Counter
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical
import concurrent.futures, threading

START = date(2024, 10, 1); UNION_DCS = (5, 10, 15, 20); REENTRY = 3
LK = threading.Lock()
dom = Counter(); wd = Counter(); wom = Counter(); dse = Counter(); total = [0]

def last_thursday(y, m):
    d = date(y, m, 28)
    while d.month == m:
        nd = d + timedelta(days=1)
        if nd.month != m: break
        d = nd
    # d = last day of month; walk back to Thursday (weekday 3)
    while d.weekday() != 3:
        d -= timedelta(days=1)
    return d

def days_since_expiry(day):
    # nearest monthly expiry <= day
    exp = last_thursday(day.year, day.month)
    if day < exp:
        pm = day.replace(day=1) - timedelta(days=1)
        exp = last_thursday(pm.year, pm.month)
    return (day - exp).days

def do_stock(sym0):
    u = fetch_upstox_historical(sym0, unit="days", interval=1, from_date="2024-06-01", to_date=date.today().isoformat())
    if u is None or u.empty or len(u) < 30: return
    u = u.sort_index()
    rolls = {dc: (u["High"].rolling(dc).max().shift(1), u["Low"].rolling(dc).min().shift(1)) for dc in UNION_DCS}
    last = {}
    for i in range(max(UNION_DCS) + 1, len(u)):
        day = u.index[i].date()
        if day < START: continue
        c = float(u["Close"].iloc[i]); typ = None
        for dc in UNION_DCS:
            hi, lo = rolls[dc]
            if c > float(hi.iloc[i]): typ = "CE"; break
            if c < float(lo.iloc[i]): typ = "PE"; break
        if typ is None: continue
        if last.get(typ) and (day - last[typ]).days < REENTRY: continue
        last[typ] = day
        with LK:
            total[0] += 1
            dom[day.day] += 1
            wd[day.weekday()] += 1
            wom[(day.day - 1) // 7 + 1] += 1
            dse[days_since_expiry(day)] += 1

with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(do_stock, UNIVERSE))

n = total[0]
print(f"\n=== {n} UNION breakout-signals, {len(UNIVERSE)} stocks, Oct'24->{date.today()} ===")
wk_start = last_thursday(2020, 1)  # unused; just for clarity

print("\n-- by WEEK-OF-MONTH (calendar) --")
for w in sorted(wom):
    bar = "█" * round(wom[w] / n * 100)
    print(f"  week {w}: {wom[w]:4d} ({wom[w]/n*100:4.1f}%) {bar}")

print("\n-- by WEEKDAY --")
names = ["Mon", "Tue", "Wed", "Thu", "Fri"]
for d in range(5):
    if d in wd:
        print(f"  {names[d]}: {wd[d]:4d} ({wd[d]/n*100:4.1f}%) {'█'*round(wd[d]/n*100)}")

print("\n-- by DAYS-SINCE-MONTHLY-EXPIRY (credit-richness proxy; 0-7 = fresh far-DTE = richest credit) --")
buckets = [(0,6,"0-6d  (week after expiry — richest)"), (7,13,"7-13d"), (14,20,"14-20d"), (21,34,"21-34d (near expiry — thin credit)")]
for lo, hi, lab in buckets:
    cnt = sum(v for k, v in dse.items() if lo <= k <= hi)
    print(f"  {lab:38s} {cnt:4d} ({cnt/n*100:4.1f}%) {'█'*round(cnt/n*100)}")

print("\n-- by DAY-OF-MONTH (top 10) --")
for d, cnt in sorted(dom.items(), key=lambda x: -x[1])[:10]:
    print(f"  {d:2d}th: {cnt:3d} ({cnt/n*100:.1f}%)")
print("DONE-CAL")
