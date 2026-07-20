"""HEAVYWEIGHT EARNINGS + MARKET-SHOCK overlap test for the three 0DTE books, 2019 -> date.

Completes the user's ask: beyond RBI/Budget/FOMC, do INDEX-HEAVYWEIGHT RESULTS days (RELIANCE,
HDFCBANK, ICICIBANK, ...) or known market-shock days justify standing aside?

Two things make this test honest:

1. EX-ANTE PROVEN, not assumed. Results dates come from NSE's board-meeting API, which also carries
   the advance-intimation timestamp. Minimum lead time across all 367 rows is 3 days (median 14) —
   so every date was genuinely knowable before the morning in question. Nothing is inferred from
   price action.

2. RELEASE-WINDOW SPLIT (the distinction that decides the answer). A result is only a risk to a
   position we already hold if it lands INSIDE the 09:16->15:30 window:
     INTRADAY        (09:15-15:30)  -> binary lands while we are short gamma. THE risk case.
     POST_CLOSE / NON_TRADING_DAY   -> already public before the next open; that session sells the
                                       exhale (the FOMC mechanism). Expected GOOD, not bad.
   Only 51 of 367 releases were INTRADAY; 223 were post-close and 88 fell on non-trading days
   (HDFCBANK/ICICIBANK habitually report on Saturdays).

INDEX RELEVANCE: BANKNIFTY is ~half HDFCBANK+ICICIBANK, so bank results are a plausible mover there.
NIFTY/SENSEX top weights are ~9-13%, so a 4% single-stock move is only ~0.4% of index — at or below
the pain threshold of a 0.5%-OTM spread. Tested per book so that arithmetic is checked, not assumed.

MARKET SHOCKS are reported DESCRIPTIVELY ONLY. A shock list compiled today is selected for having
moved the market (survivorship-of-the-scary) and is inadmissible as a trading rule — see
ZERO_DTE_PREOPEN_SIGNALS.md. It is shown here to audit what the strategy actually did on those days.
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nse_results_dates import RESULTS_DATES
from india_market_shocks import MARKET_SHOCK_EVENTS

BANKS = {"HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK"}
RELEVANT = {"BANKNIFTY": BANKS, "NIFTY": None, "SENSEX": None}   # None = all 12 heavyweights

rows = []
for fn in ("ndte14_trades_2019.json", "ndte13_trades.json"):
    p = os.path.join(HERE, fn)
    if os.path.exists(p): rows += json.load(open(p))
rows = [r for r in rows if r["traded"]]
rows.sort(key=lambda r: r["date"])
print(f"{len(rows)} deployed-filter trades ({rows[0]['date']} -> {rows[-1]['date']})")

good = [r for r in RESULTS_DATES if not r["superseded"]]
def dateset(book, sessions, use_first_tradable):
    keep = RELEVANT[book]
    out = set()
    for r in good:
        if keep is not None and r["symbol"] not in keep: continue
        if r["session"] not in sessions: continue
        d = r["first_tradable"] if use_first_tradable else r["date"]
        if d: out.add(d)
    return out

def stats(sel):
    if not sel: return None
    pm = np.array([r["pm"] for r in sel]); rs = np.array([r["rs"] for r in sel])
    return dict(n=len(sel), win=(pm > 0).mean() * 100, avg=pm.mean(), tot=rs.sum(), worst=rs.min())
def line(lab, s):
    if s is None: return f"    {lab:34s} n=   0   —"
    return (f"    {lab:34s} n={s['n']:4d}  win {s['win']:5.1f}%  avg {s['avg']:+6.2f}%m  "
            f"tot Rs{s['tot']:+10,.0f}  worst Rs{s['worst']:+9,.0f}")

def compare(book, sel, label, dates):
    ev  = [r for r in sel if r["date"] in dates]
    nev = [r for r in sel if r["date"] not in dates]
    base, se, sn = stats(sel), stats(ev), stats(nev)
    print(f"\n  -- {label} --")
    if not se:
        print(f"    NO OVERLAP — not one expiry in {len(sel)} coincided with this category.")
        return
    print(line("EX-EVENT (avoidance)", sn)); print(line("EVENT-ONLY (skipped)", se))
    d = sn["tot"] - base["tot"]
    print(f"       -> win {base['win']:.1f}% -> {sn['win']:.1f}% ({sn['win']-base['win']:+.1f}pp) | "
          f"Rs{base['tot']:+,.0f} -> Rs{sn['tot']:+,.0f} ({d:+,.0f}) | "
          f"{'AVOIDING HELPS' if d > 0 else 'AVOIDING COSTS MONEY'}"
          f"{'  [n<10: NOISE]' if se['n'] < 10 else ''}")

for book in ("NIFTY", "SENSEX", "BANKNIFTY"):
    sel = [r for r in rows if r["book"] == book]
    if not sel: continue
    who = "bank heavyweights" if RELEVANT[book] else "all 12 heavyweights"
    print(f"\n{'='*104}\n{book}  (n={len(sel)}, relevance set = {who})\n{'='*104}")
    print(line("ALL (baseline)", stats(sel)))
    compare(book, sel, "RISK CASE: result released INTRADAY that day (inside 09:16-15:30 window)",
            dateset(book, {"INTRADAY"}, False))
    compare(book, sel, "EXHALE CASE: result already public (post-close / non-trading day) -> first session after",
            dateset(book, {"POST_CLOSE", "NON_TRADING_DAY"}, True))
    compare(book, sel, "ANY results involvement (either case)",
            dateset(book, {"INTRADAY"}, False) | dateset(book, {"POST_CLOSE", "NON_TRADING_DAY"}, True))

print(f"\n{'='*104}\nPOOLED — all books\n{'='*104}")
allsel = rows
print(line("ALL (baseline)", stats(allsel)))
intr = set().union(*(dateset(b, {"INTRADAY"}, False) for b in RELEVANT))
exha = set().union(*(dateset(b, {"POST_CLOSE", "NON_TRADING_DAY"}, True) for b in RELEVANT))
compare("POOLED", allsel, "RISK CASE: any heavyweight result INTRADAY", intr)
compare("POOLED", allsel, "EXHALE CASE: session after a heavyweight result", exha)

print(f"\n{'='*104}\nDESCRIPTIVE ONLY — what the books did on known market-shock days\n"
      f"(NOT a proposed filter: a shock list compiled today is selected for having moved the market)\n{'='*104}")
for cls in ("PRE_OPEN_OBSERVABLE", "INTRADAY_SURPRISE"):
    ds = {s["date"] for s in MARKET_SHOCK_EVENTS if s["classification"] == cls}
    sel = [r for r in rows if r["date"] in ds]
    print(line(cls, stats(sel)))
    for r in sorted(sel, key=lambda r: r["pm"])[:6]:
        note = next((s["description"][:58] for s in MARKET_SHOCK_EVENTS if s["date"] == r["date"]), "")
        print(f"        {r['date']} {r['book']:10s} {r['pm']:+8.2f}%m Rs{r['rs']:+8,.0f}  {note}")
print("\nDONE-NDTE16")
