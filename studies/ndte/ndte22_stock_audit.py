"""AUDIT of the two STOCK books (v2 UNION, v1) — the 87% of the monthly model never re-measured.

Same adversarial checks applied to BANKNIFTY in ndte20, run against the books that actually carry the
portfolio. Written to FALSIFY, not confirm: each check is one that, if failed, undermines the book.

  1  significance   — is the edge distinguishable from zero? (BANKNIFTY died here: t=+0.10)
  2  outlier drive  — does it survive dropping the best trades? (BANKNIFTY died here: drop 3 -> -Rs8)
  3  per-year       — positive in how many calendar years?
  4  bad prints     — c/W>0.90 stale-print contamination
  5  worst case     — how many months of profit does the worst trade cost?
Units: v2/v1 nets are in POINTS of width; capital = w-credit = w*(1-cw). Reported as % of capital.
"""
import warnings; warnings.filterwarnings("ignore")
import json, os
import numpy as np

def load_v2():
    out = []
    for f in ("/tmp/d5_10_15_20_bhav.json", "/tmp/d5_10_15_20_oct24.json"):
        if os.path.exists(f): out += json.load(open(f)).get("D5", [])
    return out

def load_v1():
    d = json.load(open("studies/stkfade_oos_v1.json"))
    return d.get("A", []) if isinstance(d, dict) else d

def audit(name, rows, has_cw=True):
    print("=" * 104); print(f"{name}   n={len(rows)}"); print("=" * 104)
    if not rows: return print("  no data")
    if has_cw and "cw" in rows[0]:
        bad = [x for x in rows if x["cw"] > 0.90]
        rows = [x for x in rows if x["cw"] <= 0.90]
        print(f"  [4] bad prints: dropped {len(bad)} with c/W>0.90  ->  n={len(rows)}")
        cap = np.array([x["w"] * (1 - x["cw"]) for x in rows])
    else:
        # v1: no cw field; approximate capital using the deployed gate floor (c/W>=0.40 -> cap<=0.60w)
        print("  [4] no c/W field — capital approximated as 0.60 x width (v1 gate floor); % is indicative")
        cap = np.array([x["w"] * 0.60 for x in rows])
    net = np.array([x["net"] for x in rows])
    per = net / cap * 100
    se = per.std(ddof=1) / np.sqrt(len(per))
    t = per.mean() / se
    print(f"  [1] avg {per.mean():+7.2f}% of capital   SE {se:5.2f}   t = {t:+6.2f}   "
          f"95% CI [{per.mean()-1.96*se:+.2f}, {per.mean()+1.96*se:+.2f}]")
    print(f"      -> {'DISTINGUISHABLE from zero' if abs(t) > 1.96 else 'NOT distinguishable from zero'}")
    boot = [np.mean(np.random.choice(net, len(net), replace=True)) for _ in range(5000)]
    print(f"      bootstrap p(mean<=0) = {np.mean(np.array(boot) <= 0):.4f}")
    print(f"      capital-weighted {net.sum()/cap.sum()*100:+.2f}%   win {(net>0).mean()*100:.1f}%   "
          f"avgW {per[per>0].mean():+.1f}%  avgL {per[per<=0].mean():+.1f}%")
    order = np.argsort(net)
    print(f"  [2] outlier dependence (total net, points of width):")
    for lab, idx in (("all", order), ("drop 3 best", order[:-3]), ("drop 5 best", order[:-5]),
                     ("drop 10 best", order[:-10]), ("drop 3 worst", order[3:])):
        print(f"      {lab:13s} n={len(idx):4d}  total {net[idx].sum():+10.1f}")
    if "y" in rows[0]:
        yr = {}
        for x in rows: yr.setdefault(x["y"], []).append(x["net"])
        pos = sum(1 for v in yr.values() if sum(v) > 0)
        print(f"  [3] per calendar year — positive {pos}/{len(yr)}:")
        print("      " + " · ".join(f"{y}:{np.sum(v):+.0f}" for y, v in sorted(yr.items())))
    print(f"  [5] worst trade {net.min():+.1f} pts vs avg {net.mean():+.2f} pts/trade "
          f"= {abs(net.min()/net.mean()):.0f} trades of profit\n")

audit("v2 UNION (stock fade, D5 = deployed)", load_v2())
audit("v1 (stock credit, OOS era only)", load_v1(), has_cw=False)
print("DONE-NDTE22")
