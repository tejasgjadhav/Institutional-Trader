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
# NSE trading calendar, needed to map post-close events to the NEXT session. Merge both eras:
# spot2019_NIFTY.json (2019->Sep'24, written by ndte14) + spot_NIFTY.json (Oct'24->date, ndte13).
SPOTS = ["/tmp/ndte_ev/spot2019_NIFTY.json", "/tmp/ndte_ev/spot_NIFTY.json"]

# --- SAME-DAY impact (intraday announcement) -------------------------------
# SCHEDULED RBI MPC decision days = the AVOIDABLE set (published calendar, knowable in advance).
RBI_MPC = [
    # --- 2019 -> Sep'24 (bhavcopy era) ---
    "2019-02-07", "2019-04-04", "2019-06-06", "2019-08-07", "2019-10-04", "2019-12-05",
    "2020-02-06", "2020-08-06", "2020-10-09", "2020-12-04",
    "2021-02-05", "2021-04-07", "2021-06-04", "2021-08-06", "2021-10-08", "2021-12-08",
    "2022-02-10", "2022-04-08", "2022-06-08", "2022-08-05", "2022-09-30", "2022-12-07",
    "2023-02-08", "2023-04-06", "2023-06-08", "2023-08-10", "2023-10-06", "2023-12-08",
    "2024-02-08", "2024-04-05", "2024-06-07", "2024-08-08",
    # --- Oct'24 -> date (Upstox era) ---
    "2024-10-09", "2024-12-06", "2025-02-07", "2025-04-09", "2025-06-06",
    "2025-08-06",   # RESCHEDULED (was 08-07)
    "2025-10-01", "2025-12-05", "2026-02-06", "2026-04-08", "2026-06-05"]

# NOT knowable in advance -> can NEVER be part of an "avoid" rule. Tracked only so we can
# measure what they did. Including these in the avoidable set would be hindsight cheating.
RBI_OFFCYCLE = ["2020-03-27", "2020-05-22", "2022-05-04",      # off-cycle MPC (COVID/surprise hike)
                "2020-04-17", "2021-05-05"]                    # unscheduled Governor statements

BUDGET = ["2019-02-01", "2019-07-05",   # interim + full (post-election year)
          "2020-02-01",                 # SATURDAY special session
          "2021-02-01", "2022-02-01", "2023-02-01",
          "2024-02-01", "2024-07-23",   # interim + full (post-election year)
          "2025-02-01", "2026-02-01"]   # both weekend special sessions

# --- NEXT-DAY impact (post-close release) ----------------------------------
FOMC = ["2019-01-30", "2019-03-20", "2019-05-01", "2019-06-19", "2019-07-31", "2019-09-18",
        "2019-10-30", "2019-12-11",
        "2020-01-29", "2020-04-29", "2020-06-10", "2020-07-29", "2020-09-16", "2020-11-05",
        "2020-12-16",   # note: the scheduled 2020-03-18 meeting was CANCELLED
        "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28", "2021-09-22",
        "2021-11-03", "2021-12-15",
        "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27", "2022-09-21",
        "2022-11-02", "2022-12-14",
        "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26", "2023-09-20",
        "2023-11-01", "2023-12-13",
        "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18",
        "2024-11-07", "2024-12-18", "2025-01-29", "2025-03-19", "2025-05-07",
        "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
        "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17"]

# Emergency Fed actions — NOT knowable in advance, excluded from the avoidable set.
FOMC_UNSCHEDULED = ["2019-10-11", "2020-03-03", "2020-03-15", "2020-03-23"]
CPI = ["2024-10-14", "2024-11-12", "2024-12-12", "2025-01-13", "2025-02-12",
       "2025-03-12", "2025-04-14", "2025-05-12", "2025-06-12", "2025-07-14",
       "2025-08-12", "2025-09-12", "2025-10-13", "2025-11-12", "2025-12-12",
       "2026-01-12", "2026-02-12", "2026-03-12", "2026-04-13", "2026-05-12",
       "2026-06-12", "2026-07-13"]              # mostly INFERRED — kept separate

# --- judgment-call extras (kept separate, not in the headline set) ---------
ELECTION_SAMEDAY = ["2019-05-23",   # Lok Sabha counting day
                    "2024-06-04",   # Lok Sabha counting day (Nifty -5.9%)
                    "2025-11-14"]   # Bihar assembly result day
ELECTION_NEXTDAY = ["2024-11-05"]   # US presidential election

def main():
    have = [p for p in SPOTS if os.path.exists(p)]
    if not have:
        sys.exit(f"missing {SPOTS} — run ndte13_events.py / ndte14_events_2019.py first "
                 "(they cache the NSE trading calendar)")
    tset = set()
    for p in have: tset |= set(json.load(open(p)).keys())
    tdays = sorted(tset)
    print(f"trading calendar: {len(tdays)} days ({tdays[0]} -> {tdays[-1]}) from {len(have)} file(s)")

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
        # NOT avoidable — surprise announcements, tracked for measurement only
        UNAVOIDABLE=sorted(set(RBI_OFFCYCLE) | set(spill(FOMC_UNSCHEDULED))),
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
