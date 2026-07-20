"""FINAL untested items from the Fable design pass (2026-07-19).

Closes the remaining gaps in the 0DTE event-avoidance series:
  A2  INDIA VIX  — Fable's #2 candidate, genuinely untested. Earlier work used rv5 (REALIZED vol),
                   which Fable classified as A7, the redundancy control — a different signal from an
                   IMPLIED-vol spike. Tested both as a LEVEL and as a d/d SPIKE.
  A4  ELECTIONS  — counting days + exit-poll reaction sessions (Fable: adopt on structural grounds,
                   statistically untestable). Measured here so the cost of the overlay is known.
  Half-sizing    — Fable: "skip" is a blunt instrument. Every flagged rule is reported BOTH as a full
                   skip AND as a 0.5x haircut, which keeps crush-collection upside while trimming tail.
  Ex-worst-day   — Fable: with tail-driven P&L a single day can flip a filter's sign. Every headline
                   is re-reported with the single worst trade removed.
  Era split      — every rule must hold in BOTH eras independently or it is a regime artifact.

NO LOOKAHEAD: entry is ~09:16, so the last KNOWN VIX close is the PRIOR session's. vix_level uses
close[t-1]; vix_spike uses close[t-1] vs close[t-2]. Never today's close.

A3 (US overnight) is NOT tested standalone: the Indian opening gap already prices the US move, and
that gap was tested in ndte15 (failed). Fable's own prior was that standalone A3 is subsumed.
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys, json, time
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np
from engine.data_fetcher import SESSION, UPSTOX_BASE
from engine.instruments import encode_key

HERE = os.path.dirname(os.path.abspath(__file__))
C = "/tmp/ndte_ev"; os.makedirs(C, exist_ok=True)

def india_vix():
    cf = f"{C}/india_vix.json"
    if os.path.exists(cf): return json.load(open(cf))
    out = {}
    for _ in range(4):
        r = SESSION.get(f"{UPSTOX_BASE}/v2/historical-candle/"
                        f"{encode_key('NSE_INDEX|India VIX')}/day/2026-07-19/2019-01-01", timeout=30)
        if r.status_code == 200:
            for ts, o, h, l, c, *_ in r.json().get("data", {}).get("candles", []):
                out[ts[:10]] = c
            break
        time.sleep(3)
    if out: json.dump(out, open(cf, "w"))
    return out

VIX = india_vix()
vdays = sorted(VIX)
print(f"India VIX: {len(vdays)} days ({vdays[0]} -> {vdays[-1]})")

rows = []
for fn in ("ndte14_trades_2019.json", "ndte13_trades.json"):
    p = os.path.join(HERE, fn)
    if os.path.exists(p): rows += json.load(open(p))
rows = [r for r in rows if r["traded"]]

# spot for gap (interaction test)
SPOTF = {"NIFTY": ["spot2019_NIFTY.json", "spot_NIFTY.json"],
         "BANKNIFTY": ["spot2019_BANKNIFTY.json", "spot_BANKNIFTY.json"],
         "SENSEX": ["spot_SENSEX.json"]}
spots = {}
for b, fs in SPOTF.items():
    m = {}
    for f in fs:
        p = os.path.join(C, f)
        if os.path.exists(p): m.update(json.load(open(p)))
    spots[b] = m

def enrich(r):
    d = r["date"]
    import bisect
    i = bisect.bisect_left(vdays, d)
    if i < 2: return None
    r = dict(r)
    r["vix_level"] = VIX[vdays[i - 1]]                                  # prior close — known at 09:16
    r["vix_spike"] = (VIX[vdays[i - 1]] / VIX[vdays[i - 2]] - 1) * 100  # prior d/d change
    s = spots.get(r["book"], {}); sd = sorted(s)
    if d in s:
        j = sd.index(d)
        if j >= 1 and s[sd[j - 1]][3]:
            r["gap"] = abs(s[d][0] / s[sd[j - 1]][3] - 1) * 100
    return r

rows = [x for x in (enrich(r) for r in rows) if x]
rows.sort(key=lambda r: r["date"])
print(f"{len(rows)} trades with VIX context ({rows[0]['date']} -> {rows[-1]['date']})\n")

def tot(sel):  return sum(r["rs"] for r in sel)
def win(sel):  return np.mean([r["pm"] > 0 for r in sel]) * 100 if sel else float("nan")
def avg(sel):  return np.mean([r["pm"] for r in sel]) if sel else float("nan")

def report(label, flag, sel):
    """full-skip AND half-size, with era split and ex-worst-day."""
    base = tot(sel)
    fl = [r for r in sel if flag(r)]; ke = [r for r in sel if not flag(r)]
    if len(fl) < 3:
        print(f"  {label:38s} flagged n={len(fl)} — too few to evaluate"); return
    skip = tot(ke)
    half = tot(ke) + 0.5 * tot(fl)
    print(f"  {label:38s} flagged n={len(fl):3d} ({win(fl):5.1f}% win, {avg(fl):+7.2f}%m)")
    print(f"      base Rs{base:+11,.0f} | SKIP Rs{skip:+11,.0f} ({skip-base:+9,.0f}) "
          f"| HALF Rs{half:+11,.0f} ({half-base:+9,.0f})")
    # ex-worst-day
    w = min(sel, key=lambda r: r["rs"])
    s2 = [r for r in sel if r is not w]
    f2 = [r for r in s2 if flag(r)]; k2 = [r for r in s2 if not flag(r)]
    print(f"      ex-worst-day ({w['date']} {w['book']} Rs{w['rs']:+,.0f}): "
          f"base Rs{tot(s2):+,.0f} -> SKIP Rs{tot(k2):+,.0f} ({tot(k2)-tot(s2):+,.0f})")
    # era split — the decider
    verdicts = []
    for elab, lo, hi in (("A", "2019-01-01", "2024-09-30"), ("B", "2024-10-01", "2026-12-31")):
        e = [r for r in sel if lo <= r["date"] <= hi]
        if not e: continue
        ek = [r for r in e if not flag(r)]; ef = [r for r in e if flag(r)]
        d = tot(ek) - tot(e)
        verdicts.append(d > 0)
        print(f"      ERA {elab}: base Rs{tot(e):+9,.0f} -> SKIP Rs{tot(ek):+9,.0f} ({d:+8,.0f}) "
              f"[flagged n={len(ef)}] {'HELPS' if d > 0 else 'costs'}")
    print(f"      >>> {'CONSISTENT ACROSS ERAS' if len(set(verdicts))==1 and verdicts and verdicts[0] else 'FAILS ERA SPLIT / costs money'}\n")

print("=" * 100); print("A2 — INDIA VIX (Fable's #2, previously untested)"); print("=" * 100)
for lo in (15, 18, 20, 25):
    report(f"skip vix_level >= {lo}", lambda r, t=lo: r["vix_level"] >= t, rows)
for sp in (5, 10, 15, 20):
    report(f"skip vix_spike >= +{sp}%", lambda r, t=sp: r["vix_spike"] >= t, rows)
report("skip vix_spike>=10 AND level>=15",
       lambda r: r["vix_spike"] >= 10 and r["vix_level"] >= 15, rows)
report("skip vix_spike>=10 OR gap>=0.75",
       lambda r: r["vix_spike"] >= 10 or r.get("gap", 0) >= 0.75, rows)

print("=" * 100); print("PER BOOK — vix_spike >= +10% (the pre-registered threshold)"); print("=" * 100)
for b in ("NIFTY", "SENSEX", "BANKNIFTY"):
    sel = [r for r in rows if r["book"] == b]
    if sel: report(f"{b}: skip vix_spike >= +10%", lambda r: r["vix_spike"] >= 10, sel)

print("=" * 100); print("A4 — ELECTIONS (counting days + exit-poll reaction sessions)"); print("=" * 100)
ELECTION = {"2019-05-20", "2019-05-23", "2024-06-03", "2024-06-04",
            "2024-11-06", "2025-11-14", "2021-05-02", "2022-03-10", "2023-12-04"}
hit = [r for r in rows if r["date"] in ELECTION]
print(f"  expiries coinciding with ANY election/exit-poll session: {len(hit)}")
for r in hit: print(f"    {r['date']} {r['book']:10s} {r['pm']:+7.2f}%m Rs{r['rs']:+,.0f}")
if not hit:
    print("  ZERO overlap in the full 2019->date sample. The overlay has never once triggered,")
    print("  so its historical cost is EXACTLY Rs0 — it is free insurance, not a tested edge.")
print("\nDONE-NDTE17")
