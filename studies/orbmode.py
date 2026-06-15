"""
Head-to-head: opening-range volume benchmark (strict, the OLD structure) vs the
rolling benchmark (current), over 30 days, with train/test split. Reports win rate
and net/trade at +10/-20, +20/-10, +15/-5, +10/-5.
"""
import sys, importlib
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from engine import config

def winrate(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    n = len(vals)
    if not n: return (0, 0, 0.0)
    g = sum(1 for v in vals if v > 0)
    return (n, round(g/n*100), round(sum(vals)/n, 2))

def split(rows):
    days = sorted({r["day"] for r in rows})
    cut = days[int(len(days)*0.55)]
    return [r for r in rows if r["day"] < cut], [r for r in rows if r["day"] >= cut]

def report(label, rows):
    tr, te = split(rows)
    print(f"\n===== {label} =====  signals={len(rows)}  ({len(rows)/30:.1f}/day)")
    print(f"{'exit':<12}{'ALL n/win%/net':<26}{'TRAIN n/win%/net':<26}{'TEST n/win%/net'}")
    for name, key in [("+10/-20","pnl_1020"),("+20/-10","pnl_2010"),("+15/-5","pnl_155"),("+10/-5","pnl_2to1")]:
        a = winrate(rows, key); t = winrate(tr, key); s = winrate(te, key)
        print(f"{name:<12}{f'{a[0]}/{a[1]}%/{a[2]:+}':<26}{f'{t[0]}/{t[1]}%/{t[2]:+}':<26}{f'{s[0]}/{s[1]}%/{s[2]:+}'}")

def prog(i, n, u):
    if i % 20 == 0 or i == n: print(f"  ...{i}/{n}", flush=True)

for mode in ["opening", "rolling"]:
    config.VOLUME_BENCHMARK_MODE = mode
    import engine.filter_backtest as fb
    importlib.reload(fb)
    print(f"\n\n#### COLLECTING mode={mode} ####", flush=True)
    rows = fb.collect(n_days=30, cutoff="13:00", progress=prog)
    report(f"VOLUME_BENCHMARK = {mode}", rows)
