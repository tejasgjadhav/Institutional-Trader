"""CREDIT FLOOR — the one new test Fable authorised after deciding the event series (2026-07-19).

Logic: the series' closing finding is that this book is PAID FOR VISIBLE FEAR — every filter keying
on ex-ante-visible stress (gap, VIX, spike, shocks) removed exactly the trades where the market
overpaid. The mirror image is the open question: if rich premium is where the edge lives, is CHEAP
premium where it dies? A credit floor is ex-ante knowable at 09:16, economically coherent, and this
repo already has precedent — the stock book's credit/width >= 0.40 gate IS its edge.

Partial precedent in the 0DTE engine too: NIFTY already runs ZERO_DTE_MIN_CREDIT_PCT = 0.02 (credit
>= 0.02% of spot). SENSEX and BANKNIFTY run NO credit gate at all. So this sweeps a credit floor per
book, expressed two ways, era-split as always.

  c/W        credit / width           (comparable to the stock book's c/w gate)
  c/margin   credit / (width-credit)  (return-on-capital framing)

House rule unchanged: a rule must help in BOTH eras independently or it is a regime artifact.
"""
import warnings; warnings.filterwarnings("ignore")
import os, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
rows = []
for fn in ("ndte14_trades_2019.json", "ndte13_trades.json"):
    p = os.path.join(HERE, fn)
    if os.path.exists(p): rows += json.load(open(p))
rows = [r for r in rows if r["traded"] and r.get("W")]
for r in rows:
    r["cw"] = r["credit"] / r["W"]
    m = r["W"] - r["credit"]
    r["cm"] = r["credit"] / m if m > 0 else 0.0
rows.sort(key=lambda r: r["date"])
print(f"{len(rows)} trades ({rows[0]['date']} -> {rows[-1]['date']})\n")

def tot(s): return sum(r["rs"] for r in s)
def win(s): return np.mean([r["pm"] > 0 for r in s]) * 100 if s else float("nan")
def avg(s): return np.mean([r["pm"] for r in s]) if s else float("nan")

def sweep(label, sel, key, ths):
    base = tot(sel)
    print(f"\n  {label}  (baseline n={len(sel)} win {win(sel):.1f}% avg {avg(sel):+.2f}%m Rs{base:+,.0f})")
    print(f"    {'skip if <':>9s} {'kept':>5s} {'skipped':>7s} {'skipped win/avg':>18s} "
          f"{'kept Rs':>11s} {'vs base':>10s}  {'ERA A':>10s} {'ERA B':>10s}  verdict")
    for t in ths:
        keep = [r for r in sel if r[key] >= t]; drop = [r for r in sel if r[key] < t]
        if len(drop) < 3 or not keep: continue
        d = tot(keep) - base
        # Era verdict. NOTE: an era with NO trades (SENSEX has zero Era-A trades — BSE weeklies
        # only launched 2023) must count as NOT-CONFIRMED, never as a silent pass. An earlier
        # version skipped zero-valued eras and mislabelled SENSEX single-era results as
        # "BOTH ERAS HELP"; that was wrong and is corrected here.
        eras, present = [], []
        for lo, hi in (("2019-01-01", "2024-09-30"), ("2024-10-01", "2026-12-31")):
            e = [r for r in sel if lo <= r["date"] <= hi]
            present.append(len(e) > 0)
            ek = [r for r in e if r[key] >= t]
            eras.append(tot(ek) - tot(e) if e else 0.0)
        ok = all(present) and all(x > 0 for x in eras)
        verdict = ("BOTH ERAS HELP" if ok else
                   ("single-era only" if not all(present) else "fails"))
        print(f"    {t:>9.3f} {len(keep):>5d} {len(drop):>7d} {win(drop):>8.1f}%/{avg(drop):>+7.2f}%m "
              f"{tot(keep):>+11,.0f} {d:>+10,.0f}  {eras[0]:>+10,.0f} {eras[1]:>+10,.0f}  "
              f"{verdict}")

for b in ("NIFTY", "SENSEX", "BANKNIFTY"):
    sel = [r for r in rows if r["book"] == b]
    if not sel: continue
    print("=" * 118); print(f"{b}"); print("=" * 118)
    sweep(f"{b} — credit/WIDTH floor", sel, "cw", [0.02, 0.04, 0.06, 0.08, 0.10, 0.14, 0.18, 0.25])
    sweep(f"{b} — credit/MARGIN floor", sel, "cm", [0.02, 0.04, 0.06, 0.08, 0.12, 0.16, 0.25])

print("\n" + "=" * 118); print("POOLED"); print("=" * 118)
sweep("POOLED — credit/WIDTH floor", rows, "cw", [0.02, 0.04, 0.06, 0.08, 0.10, 0.14, 0.18, 0.25])

print(f"\n{'='*118}\nDIAGNOSTIC — outcome by credit/width bucket (is cheap premium where it dies?)\n{'='*118}")
print(f"  {'c/W bucket':>14s} {'n':>5s} {'win%':>6s} {'avg %m':>8s} {'tot Rs':>11s}")
for lo, hi in [(0, .04), (.04, .08), (.08, .12), (.12, .18), (.18, 9)]:
    s = [r for r in rows if lo <= r["cw"] < hi]
    if not s: continue
    print(f"  {lo:>6.2f}-{hi if hi<9 else 1.0:<7.2f} {len(s):>5d} {win(s):>6.1f} {avg(s):>+8.2f} {tot(s):>+11,.0f}")
print("\nDONE-NDTE18")
