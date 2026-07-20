"""0DTE EVENT-DAY AVOIDANCE — FULL-HISTORY analysis, 2019 -> date.
Merges the two eras (ndte14_trades_2019.json = bhavcopy 2019->Sep'24, ndte13_trades.json =
Upstox Oct'24->date) and re-runs the avoid-vs-trade-all comparison over the whole sample.

Core discipline: an "avoid the event" rule can only skip what was KNOWABLE IN ADVANCE. Off-cycle
RBI announcements (COVID-era, the May'22 surprise hike) and emergency Fed actions are therefore
NOT in the avoidable set — they are measured separately, because pretending we could have dodged
them would be hindsight cheating and would flatter the filter.

Reports, per book / era / pooled:
  ALL         baseline, every expiry passing the deployed filters
  EX-EVENT    the avoidance strategy
  EVENT-ONLY  the subset given up (this is what avoidance actually costs or saves)
"""
import warnings; warnings.filterwarnings("ignore")
import os, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
rows = []
for fn in ("ndte14_trades_2019.json", "ndte13_trades.json"):
    p = os.path.join(HERE, fn)
    if os.path.exists(p): rows += json.load(open(p))
    else: print(f"  (missing {fn})")
cal = json.load(open(os.path.join(HERE, "event_calendar.json")))
rows = [r for r in rows if r["traded"]]
rows.sort(key=lambda r: r["date"])

CORE = {
    "RBI MPC (scheduled)": set(cal.get("RBI_MPC", [])),
    "Budget":              set(cal.get("BUDGET", [])),
    "FOMC spillover":      set(cal.get("FOMC_SPILLOVER", [])),
}
SETS = dict(CORE)
SETS["ANY CORE (avoidable)"] = set().union(*CORE.values())
SETS["CPI spillover [INFERRED]"] = set(cal.get("CPI_SPILLOVER", []))
SETS["Election [judgment]"]      = set(cal.get("ELECTION", []))
SETS["EVERYTHING (incl. weak)"]  = set().union(*SETS.values())
UNAVOID = set(cal.get("UNAVOIDABLE", []))

def stats(sel):
    if not sel: return None
    pm = np.array([r["pm"] for r in sel]); rs = np.array([r["rs"] for r in sel])
    return dict(n=len(sel), win=(pm > 0).mean() * 100, avg=pm.mean(), tot=rs.sum(), worst=rs.min())

def line(lab, s):
    if s is None: return f"  {lab:28s}  n=  0   —"
    return (f"  {lab:28s}  n={s['n']:4d}  win {s['win']:5.1f}%  avg {s['avg']:+6.2f}%m  "
            f"tot Rs{s['tot']:+11,.0f}  worst Rs{s['worst']:+9,.0f}")

def analyse(name, sel):
    print(f"\n{'='*104}\n{name}\n{'='*104}")
    base = stats(sel)
    print(line("ALL (baseline)", base))
    if base is None: return
    for ename, dates in SETS.items():
        ev  = [r for r in sel if r["date"] in dates]
        nev = [r for r in sel if r["date"] not in dates]
        se, sn = stats(ev), stats(nev)
        if not se: continue
        print(f"\n  -- avoid: {ename} --")
        print(line("EX-EVENT (avoidance)", sn)); print(line("EVENT-ONLY (skipped)", se))
        d_win = sn["win"] - base["win"]; d_tot = sn["tot"] - base["tot"]
        print(f"     -> win {base['win']:.1f}% -> {sn['win']:.1f}% ({d_win:+.1f}pp) | "
              f"Rs{base['tot']:+,.0f} -> Rs{sn['tot']:+,.0f} ({d_tot:+,.0f}) | "
              f"{'AVOIDING HELPS' if d_tot > 0 else 'AVOIDING COSTS MONEY'}"
              f"{'  [n<10: NOISE]' if se['n'] < 10 else ''}")

for b in sorted({r["book"] for r in rows}):
    analyse(f"{b}  (2019 -> date, deployed-filter trades)", [r for r in rows if r["book"] == b])
analyse("POOLED — ALL BOOKS, 2019 -> date", rows)

# era split, so a single-regime artefact can't hide inside the pooled number
for lab, lo, hi in (("ERA A · bhavcopy 2019 -> Sep'24", "2019-01-01", "2024-09-30"),
                    ("ERA B · Upstox Oct'24 -> date",  "2024-10-01", "2026-12-31")):
    analyse(f"POOLED — {lab}", [r for r in rows if lo <= r["date"] <= hi])

# what the unavoidable surprises did — measured, never 'avoided'
print(f"\n{'='*104}\nUNAVOIDABLE SURPRISES (off-cycle RBI / emergency Fed) — could NOT have been skipped\n{'='*104}")
su = [r for r in rows if r["date"] in UNAVOID]
print(line("surprise-day trades", stats(su)))
for r in sorted(su, key=lambda r: r["date"]):
    print(f"    {r['date']}  {r['book']:10s} {r['side']}  {r['pm']:+8.2f}%m  Rs{r['rs']:+9,.0f}")

print(f"\n{'='*104}\nWORST 12 TRADES 2019->date — were the disasters on event days?\n{'='*104}")
for r in sorted(rows, key=lambda r: r["pm"])[:12]:
    tags = [k for k, v in CORE.items() if r["date"] in v] or (["UNAVOIDABLE-SURPRISE"] if r["date"] in UNAVOID else [])
    print(f"  {r['date']}  {r['book']:10s} {r['side']}  {r['pm']:+8.2f}%m  Rs{r['rs']:+9,.0f}   "
          f"{', '.join(tags) if tags else 'ordinary day'}")
print("\nDONE-NDTE14R")
