"""Build studies/ndte/event_calendar.json from researched scheduled-event dates (2026-07-19).

Why a builder and not a hand-written json: some events land AFTER the 15:30 Indian close, so
their impact hits the NEXT Indian trading day. That mapping needs the real NSE trading calendar,
which we already have as the cached spot series from ndte13_events.py.

SAME-DAY events (announced during the session, so a 0DTE position is exposed intraday):
  RBI MPC   decision ~10:00 IST
  BUDGET    FM speech ~11:00 IST
NEXT-DAY events (released after the 15:30 close -> the following session wears it):
  FOMC      statement 14:00 ET ~= 23:30 IST
  CPI       MOSPI 16:00 IST

CONFIDENCE (see ZERO_DTE_EVENT_DAYS.md): RBI/BUDGET/FOMC are verified against primary sources
(rbi.org.in, federalreserve.gov, NSE circular). CPI is mostly INFERRED from MOSPI's "12th or next
working day" rule with only 3 dates verified — it is therefore reported SEPARATELY and never
folded into the headline verdict. OTHER (elections) is a judgment call, also kept separate.

Known gotchas baked in:
  - 2025-08-06 MPC was RESCHEDULED from 05-07 Aug to 04-06 Aug; decision day is the 6th, not 7th.
  - Both Budget days fell on a WEEKEND (2025-02-01 Sat, 2026-02-01 Sun) with special live
    sessions — they are real sessions but will rarely coincide with a weekly expiry.
"""
import os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
SPOT = "/tmp/ndte_ev/spot_NIFTY.json"

# --- SAME-DAY impact (intraday announcement) -------------------------------
RBI_MPC = ["2024-10-09", "2024-12-06", "2025-02-07", "2025-04-09", "2025-06-06",
           "2025-08-06",   # RESCHEDULED (was 08-07)
           "2025-10-01", "2025-12-05", "2026-02-06", "2026-04-08", "2026-06-05"]
BUDGET = ["2025-02-01", "2026-02-01"]           # both weekend special sessions

# --- NEXT-DAY impact (post-close release) ----------------------------------
FOMC = ["2024-11-07", "2024-12-18", "2025-01-29", "2025-03-19", "2025-05-07",
        "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
        "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17"]
CPI = ["2024-10-14", "2024-11-12", "2024-12-12", "2025-01-13", "2025-02-12",
       "2025-03-12", "2025-04-14", "2025-05-12", "2025-06-12", "2025-07-14",
       "2025-08-12", "2025-09-12", "2025-10-13", "2025-11-12", "2025-12-12",
       "2026-01-12", "2026-02-12", "2026-03-12", "2026-04-13", "2026-05-12",
       "2026-06-12", "2026-07-13"]              # mostly INFERRED — kept separate

# --- judgment-call extras (kept separate, not in the headline set) ---------
ELECTION_SAMEDAY = ["2025-11-14"]               # Bihar assembly result day
ELECTION_NEXTDAY = ["2024-11-05"]               # US presidential election

def main():
    if not os.path.exists(SPOT):
        sys.exit(f"missing {SPOT} — run ndte13_events.py first (it caches the NSE calendar)")
    tdays = sorted(json.load(open(SPOT)).keys())

    def nxt(d):
        for t in tdays:
            if t > d: return t
        return None
    def spill(lst):
        return sorted({x for x in (nxt(d) for d in lst) if x})

    cal = dict(
        RBI_MPC=sorted(RBI_MPC),
        BUDGET=sorted(BUDGET),
        FOMC_RAW=sorted(FOMC), FOMC_SPILLOVER=spill(FOMC),
        CPI_RAW=sorted(CPI), CPI_SPILLOVER=spill(CPI),
        ELECTION=sorted(ELECTION_SAMEDAY + spill(ELECTION_NEXTDAY)),
    )
    out = os.path.join(HERE, "event_calendar.json")
    json.dump(cal, open(out, "w"), indent=1)
    print(f"wrote {out}")
    for k, v in cal.items():
        print(f"  {k:16s} {len(v):3d}  {v[:3]}{' …' if len(v) > 3 else ''}")
    core = set(cal["RBI_MPC"]) | set(cal["BUDGET"]) | set(cal["FOMC_SPILLOVER"])
    print(f"  CORE (RBI+Budget+FOMC) in-window: "
          f"{len([d for d in core if '2024-10-01' <= d <= '2026-07-19'])}")

if __name__ == "__main__":
    main()
