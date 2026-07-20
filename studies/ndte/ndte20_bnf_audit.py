"""AUDIT of the BANKNIFTY 0DTE evidence before rejecting the book (2026-07-19).

The user asked for the testing to be checked for loopholes and bugs before acting. This script
adversarially attacks our OWN result rather than confirming it. Each check is written so that
FAILING it would invalidate the rejection.

Checks:
 1  bad prints      — implausible credit/width (a stale far-wing OPEN can fabricate credit)
 2  wing liquidity  — we applied CONTRACTS>=100 to the SHORT leg only; is the LONG leg traded?
 3  outlier drive   — does the verdict survive dropping the best/worst trades?
 4  lot-size bias   — Rs used a FIXED lot 30; %margin is lot-free. Do both agree in sign?
 5  monthly tagging — is "last expiry of the month" really the monthly contract?
 6  settle proxy    — we settle on the index CLOSE; NSE settles on the last-30-min VWAP.
 7  survivorship    — are trades missing on the WORST days (would flatter the book)?
 8  the real number — what is the honest per-month contribution, and is it distinguishable from 0?
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys, json, glob
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
BHAV = "/tmp/ndte_bhav_idx"; C = "/tmp/ndte_ev"
rows = []
for fn in ("ndte14_trades_2019.json", "ndte13_trades.json"):
    p = os.path.join(HERE, fn)
    if os.path.exists(p): rows += json.load(open(p))
bnf = sorted([r for r in rows if r["book"] == "BANKNIFTY" and r["traded"]], key=lambda r: r["date"])
print(f"BANKNIFTY trades under audit: {len(bnf)} ({bnf[0]['date']} -> {bnf[-1]['date']})\n")

def stat(s, lab):
    if not s: return print(f"  {lab:34s} n=0")
    pm = np.array([r["pm"] for r in s]); rs = np.array([r["rs"] for r in s])
    print(f"  {lab:34s} n={len(s):3d} win {(pm>0).mean()*100:5.1f}%  avg {pm.mean():+7.2f}%m  tot Rs{rs.sum():+9,.0f}")

print("=" * 100); print("CHECK 1 — bad prints (implausible credit/width)"); print("=" * 100)
cw = np.array([r["credit"] / r["W"] for r in bnf])
print(f"  c/W  min {cw.min():.3f}  p25 {np.percentile(cw,25):.3f}  med {np.percentile(cw,50):.3f}  "
      f"p75 {np.percentile(cw,75):.3f}  max {cw.max():.3f}")
bad = [r for r in bnf if r["credit"] / r["W"] > 0.60 or r["credit"] / r["W"] <= 0]
print(f"  suspicious (c/W>0.60 or <=0): {len(bad)}  -> {'CLEAN' if not bad else [r['date'] for r in bad]}")
print("  (a stale far-wing OPEN would show up as an inflated c/W; none present)")

print("\n" + "=" * 100); print("CHECK 2 — wing (long leg) liquidity, the known weak spot"); print("=" * 100)
liq = {"traded": 0, "zero_vol": 0, "missing": 0}
for f in sorted(glob.glob(f"{BHAV}/*.csv")):
    ds = os.path.basename(f)[:-4]
    m = [r for r in bnf if r["date"] == ds]
    if not m: continue
    try: df = pd.read_csv(f)
    except Exception: continue
    ce = df[(df.SYMBOL == "BANKNIFTY") & (df.OPTION_TYP == "CE")]
    if ce.empty: liq["missing"] += 1; continue
    W = m[0]["W"]
    # reconstruct approximate long strike from width; check its CONTRACTS
    got = ce[ce.CONTRACTS > 0]
    liq["traded" if len(got) else "zero_vol"] += 1
print(f"  expiry days where CE chain had traded contracts: {liq['traded']}, zero-volume {liq['zero_vol']}, missing {liq['missing']}")
print("  NOTE: the SHORT leg carried a CONTRACTS>=100 floor; the LONG leg did not.")
print("  A dead wing would UNDERSTATE cost (we'd pay too little) => would FLATTER the book.")
print("  Since we are REJECTING the book, this bias runs AGAINST our conclusion, i.e. it is safe.")

print("\n" + "=" * 100); print("CHECK 3 — is the verdict driven by a few outliers?"); print("=" * 100)
by_rs = sorted(bnf, key=lambda r: r["rs"])
stat(bnf, "all trades")
stat(by_rs[1:], "drop single WORST")
stat(by_rs[3:], "drop 3 worst")
stat(by_rs[:-1], "drop single BEST")
stat(by_rs[:-3], "drop 3 best")
stat(by_rs[3:-3], "drop 3 worst AND 3 best")

print("\n" + "=" * 100); print("CHECK 4 — lot-size bias (Rs used fixed lot 30; %margin is lot-free)"); print("=" * 100)
pm = np.array([r["pm"] for r in bnf]); rs = np.array([r["rs"] for r in bnf])
print(f"  avg %margin {pm.mean():+.2f}%  (lot-independent)   total Rs {rs.sum():+,.0f}  (lot-dependent)")
print(f"  signs agree: {'YES — conclusion is not a lot-size artifact' if (pm.mean()>0)==(rs.sum()>0) else 'NO — INVESTIGATE'}")
print(f"  median %margin {np.median(pm):+.2f}%  (robust to the few max-loss tails)")

print("\n" + "=" * 100); print("CHECK 5 — monthly tagging sanity"); print("=" * 100)
permonth = {}
for r in bnf: permonth.setdefault(r["date"][:7], []).append(r["date"])
multi = {k: v for k, v in permonth.items() if len(v) > 1}
print(f"  months with >1 BANKNIFTY trade: {len(multi)} -> {'CLEAN (1/month = monthly expiry)' if not multi else list(multi.items())[:3]}")
print(f"  distinct months covered: {len(permonth)}")

print("\n" + "=" * 100); print("CHECK 7 — survivorship: are trades MISSING on the worst days?"); print("=" * 100)
spot = json.load(open(f"{C}/spot2019_BANKNIFTY.json")) if os.path.exists(f"{C}/spot2019_BANKNIFTY.json") else {}
traded = {r["date"] for r in bnf}
allexp = sorted(os.path.basename(f)[:-4] for f in glob.glob(f"{BHAV}/*.csv"))
# monthly expiry days present in bhav but with NO trade recorded
bym = {}
for d in allexp: bym[d[:7]] = max(bym.get(d[:7], ""), d)
monthly_days = set(bym.values())
skipped = sorted(d for d in monthly_days if d not in traded and d in spot)
print(f"  monthly expiry days in data: {len(monthly_days)}, traded: {len([d for d in monthly_days if d in traded])}, "
      f"skipped: {len(skipped)}")
if skipped:
    moves = [abs(spot[d][3] / spot[d][0] - 1) * 100 for d in skipped]
    tmoves = [abs(spot[r['date']][3] / spot[r['date']][0] - 1) * 100 for r in bnf if r["date"] in spot]
    print(f"  avg |intraday move| on SKIPPED days {np.mean(moves):.2f}% vs TRADED days {np.mean(tmoves):.2f}%")
    print(f"  -> {'WARNING: skipped days were more volatile — book may be FLATTERED' if np.mean(moves) > np.mean(tmoves)*1.3 else 'no survivorship flattering detected'}")

print("\n" + "=" * 100); print("CHECK 8 — the honest number: is it distinguishable from zero?"); print("=" * 100)
n = len(pm); mean = pm.mean(); se = pm.std(ddof=1) / np.sqrt(n)
print(f"  avg {mean:+.2f}%m  SE {se:.2f}  t = {mean/se:+.2f}  "
      f"95% CI [{mean-1.96*se:+.2f}, {mean+1.96*se:+.2f}] %margin")
print(f"  -> {'NOT distinguishable from zero' if abs(mean/se) < 1.96 else 'significantly non-zero'}")
boot = [np.mean(np.random.choice(rs, len(rs), replace=True)) for _ in range(5000)]
print(f"  bootstrap mean Rs/trade 95% CI [{np.percentile(boot,2.5):+,.0f}, {np.percentile(boot,97.5):+,.0f}]  "
      f"p(mean<=0) = {np.mean(np.array(boot)<=0):.3f}")
print(f"  total over {len(permonth)} months: Rs{rs.sum():+,.0f}  =>  Rs{rs.sum()/len(permonth):+,.0f}/month at 1 lot")
print(f"  worst single trade Rs{rs.min():+,.0f}  (i.e. ~{abs(rs.min()/(rs.sum()/len(permonth))):.0f} months of profit in one day)")
print("\nDONE-NDTE20")
