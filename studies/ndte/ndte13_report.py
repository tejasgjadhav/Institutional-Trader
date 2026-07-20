"""0DTE EVENT-DAY AVOIDANCE — analysis (pairs with ndte13_events.py).
Reads the collected per-expiry outcomes (ndte13_trades.json) + the scheduled-event calendar
(event_calendar.json) and answers: if we had SKIPPED expiries that landed on a known-in-advance
macro event, what happens to win% and net return vs trading every expiry?

Reported per book and pooled, for each event definition:
  ALL         — baseline, every expiry passing the deployed filters
  EX-EVENT    — the avoidance strategy (skip event expiries)
  EVENT-ONLY  — the subset you'd be giving up (this is what avoidance actually costs/saves)

The decisive number is TOTAL Rs, not win%: skipping trades mechanically changes win% but you
only profit from avoidance if the skipped subset was genuinely NEGATIVE. Small-n is called out
explicitly — ~6 RBI decisions/yr means event subsets are tiny and mostly noise.
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "ndte13_trades.json")))
cal = json.load(open(os.path.join(HERE, "event_calendar.json")))

# event-date sets. FOMC/CPI release after the 15:30 IST close -> impact = NEXT trading day.
CORE = {
    "RBI MPC":        set(cal.get("RBI_MPC", [])),
    "Budget":         set(cal.get("BUDGET", [])),
    "FOMC spillover": set(cal.get("FOMC_SPILLOVER", [])),
}
SETS = dict(CORE)
SETS["ANY CORE (RBI+Budget+FOMC)"] = set().union(*CORE.values())
# supplementary — lower confidence, reported but NEVER folded into the headline verdict
SETS["CPI spillover [INFERRED]"] = set(cal.get("CPI_SPILLOVER", []))
SETS["Election [judgment]"]      = set(cal.get("ELECTION", []))
SETS["EVERYTHING (incl. weak)"]  = set().union(*SETS.values())
ANY_KEY = "ANY CORE (RBI+Budget+FOMC)"

def stats(sel):
    if not sel: return None
    pm = np.array([r["pm"] for r in sel]); rs = np.array([r["rs"] for r in sel])
    return dict(n=len(sel), win=(pm > 0).mean() * 100, avg=pm.mean(),
                tot=rs.sum(), worst=rs.min())

def line(lab, s):
    if s is None: return f"  {lab:26s}  n=  0   —"
    return (f"  {lab:26s}  n={s['n']:3d}  win {s['win']:5.1f}%  avg {s['avg']:+6.2f}%m  "
            f"tot Rs{s['tot']:+10,.0f}  worst Rs{s['worst']:+9,.0f}")

def analyse(name, sel):
    print(f"\n{'='*100}\n{name}  (deployed-filter trades only)\n{'='*100}")
    base = stats(sel)
    print(line("ALL (baseline)", base))
    if base is None: return
    for ename, dates in SETS.items():
        ev  = [r for r in sel if r["date"] in dates]
        nev = [r for r in sel if r["date"] not in dates]
        se, sn = stats(ev), stats(nev)
        print(f"\n  -- avoid: {ename} --")
        print(line("EX-EVENT (avoidance)", sn))
        print(line("EVENT-ONLY (skipped)", se))
        if se and sn:
            d_win = sn["win"] - base["win"]; d_tot = sn["tot"] - base["tot"]
            verdict = ("AVOIDING HELPS" if d_tot > 0 else "AVOIDING COSTS MONEY")
            print(f"     -> win {base['win']:.1f}% -> {sn['win']:.1f}% ({d_win:+.1f}pp) | "
                  f"total Rs{base['tot']:+,.0f} -> Rs{sn['tot']:+,.0f} ({d_tot:+,.0f}) | {verdict}"
                  f"{'  [n<10: NOISE]' if se['n'] < 10 else ''}")

books = sorted({r["book"] for r in rows})
for b in books:
    analyse(b, [r for r in rows if r["book"] == b and r["traded"]])
analyse("POOLED (all three books)", [r for r in rows if r["traded"]])

# per-event-date detail — so the user can eyeball the actual event trades
print(f"\n{'='*100}\nEVENT-DAY TRADE DETAIL (every expiry that fell on a scheduled event)\n{'='*100}")
anyd = SETS[ANY_KEY]
det = sorted([r for r in rows if r["traded"] and r["date"] in anyd], key=lambda r: r["date"])
if not det:
    print("  none")
else:
    print(f"  {'date':11s} {'book':10s} {'side':4s} {'%margin':>8s} {'Rs':>9s}  which event")
    for r in det:
        which = ", ".join(k for k, v in CORE.items() if r["date"] in v)
        print(f"  {r['date']:11s} {r['book']:10s} {r['side']:4s} {r['pm']:+8.2f} {r['rs']:+9,.0f}  {which}")
print("\nDONE-NDTE13R")
