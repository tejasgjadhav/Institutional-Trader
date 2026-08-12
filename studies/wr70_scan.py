"""WR70 SCAN — search entry gates in-sample, judge them out-of-sample.

Reads the matrices built by wr70_search.py and asks one question per cell:

    does this (feature bucket, side, stop, target-ratio) beat the 1/(1+ratio) baseline by
    enough to clear 3bps of cost AND deliver >=70% win rate AND >=3%/month at 7x?

Quintile edges are fitted on IN-SAMPLE data only, then applied unchanged to OUT-OF-SAMPLE, so
the OOS numbers were never searched over. IS is used to pick candidates; OOS is the verdict.
Bonferroni is applied to the IS scan; a survivor must ALSO hold up OOS, which is the far
harder test and the one that actually matters.
"""
import os, itertools
import numpy as np
import pandas as pd
from datetime import date

OUT = "/tmp/wr70"
COST = 3.0
LEV = 7.0
IS_END = date(2024, 12, 31)
MIN_N = 400

from wr70_search import STOPS, RATIOS, FEATS

F = pd.read_pickle(os.path.join(OUT, "F.pkl"))
A = np.load(os.path.join(OUT, "A.npz"))["arr"]          # (n, 2, S, R)
assert len(F) == len(A), (len(F), A.shape)

F["is_is"] = pd.to_datetime(F.date).dt.date <= IS_END
mask_is = F.is_is.to_numpy()
n_months_is = len(pd.period_range(F.date.min(), pd.Timestamp("2024-12-31"), freq="M"))
n_months_oos = len(pd.period_range("2025-01-01", F.date.max(), freq="M"))
n_syms = F.sym.nunique()
SIDES = ["long", "short"]


def cell(sel, si, ri, k):
    """Stats for a selection of entries at one geometry. k = side index."""
    r = A[sel, k, si, ri]
    r = r[~np.isnan(r)]
    n = len(r)
    if n < MIN_N:
        return None
    net = r.mean() - COST
    win = (r > 0).mean()
    base = 1.0 / (1.0 + RATIOS[ri])
    se = np.sqrt(base * (1 - base) / n)
    z = (win - base) / se
    sd = r.std()
    t = net / (sd / np.sqrt(n)) if sd > 0 else 0.0
    return dict(n=n, win=win * 100, base=base * 100, excess=(win - base) * 100,
                z=z, net=net, t=t, sd=sd)


def monthly_pct(net_bps, n_trades, months):
    """Equal-weight across instruments: return per instrument per month, levered."""
    per_inst_per_month = n_trades / n_syms / months
    return net_bps * per_inst_per_month * LEV / 100.0


# ── build gate definitions: feature quintile buckets fitted on IS only ────────
gates = {}
for f in FEATS:
    v = F[f].to_numpy(dtype=float)
    ok = ~np.isnan(v)
    if ok.sum() < 5000:
        continue
    qs = np.nanquantile(v[mask_is & ok], [0.2, 0.4, 0.6, 0.8])
    if len(set(np.round(qs, 8))) < 4:
        continue
    for b in range(5):
        lo = -np.inf if b == 0 else qs[b - 1]
        hi = np.inf if b == 4 else qs[b]
        gates[f"{f}|Q{b+1}"] = ok & (v > lo) & (v <= hi)

n_tests = len(gates) * len(SIDES) * len(STOPS) * len(RATIOS)
z_bonf = 4.06 if n_tests > 5000 else 3.9
try:
    from scipy.stats import norm
    z_bonf = norm.ppf(1 - 0.05 / (2 * n_tests))
except Exception:
    pass

print(f"entries {len(F):,}  instruments {n_syms}  IS months {n_months_is}  OOS months {n_months_oos}")
print(f"gates {len(gates)}  x sides 2 x stops {len(STOPS)} x ratios {len(RATIOS)} "
      f"= {n_tests:,} tests   Bonferroni z = {z_bonf:.2f}\n")

# ── in-sample scan ────────────────────────────────────────────────────────────
rows = []
for gname, gm in gates.items():
    sel_is = gm & mask_is
    if sel_is.sum() < MIN_N:
        continue
    for k, si, ri in itertools.product(range(2), range(len(STOPS)), range(len(RATIOS))):
        s = cell(sel_is, si, ri, k)
        if s is None:
            continue
        s.update(gate=gname, side=SIDES[k], stop=STOPS[si], ratio=RATIOS[ri],
                 si=si, ri=ri, kside=k,
                 pct_mo=monthly_pct(s["net"], s["n"], n_months_is))
        rows.append(s)
IS = pd.DataFrame(rows)
IS.to_csv(os.path.join(OUT, "is_scan.csv"), index=False)

print("=" * 108)
print("IN-SAMPLE 2022-2024 — top cells by net expectancy (search space, NOT a result)")
print("=" * 108)
cols = ["gate", "side", "stop", "ratio", "n", "win", "base", "excess", "z", "net", "pct_mo"]
print(IS.sort_values("net", ascending=False).head(12)[cols]
      .to_string(index=False, float_format=lambda v: f"{v:8.2f}"))

# ── candidate selection on IS, then the OOS verdict ──────────────────────────
cand = IS[(IS.net > 0) & (IS.z > z_bonf) & (IS.win >= 70) & (IS.pct_mo >= 3.0)]
print(f"\nIS candidates meeting the FULL spec (win>=70%, net>0, z>{z_bonf:.2f}, "
      f">=3%/mo): {len(cand)}")
if not len(cand):
    relaxed = IS[(IS.net > 0) & (IS.z > z_bonf) & (IS.win >= 70)]
    print(f"  relaxed (drop the 3%/mo hurdle): {len(relaxed)}")
    cand = relaxed.sort_values("net", ascending=False).head(25)
    if not len(cand):
        relaxed2 = IS[(IS.net > 0) & (IS.z > z_bonf)]
        print(f"  relaxed further (drop the 70% hurdle too): {len(relaxed2)}")
        cand = relaxed2.sort_values("net", ascending=False).head(25)

if len(cand):
    print("\n" + "=" * 108)
    print("OUT-OF-SAMPLE 2025-2026 — the verdict. These edges were never fitted to this data.")
    print("=" * 108)
    out = []
    for _, r in cand.iterrows():
        sel_oos = gates[r.gate] & (~mask_is)
        s = cell(sel_oos, int(r.si), int(r.ri), int(r.kside))
        if s is None:
            continue
        s.update(gate=r.gate, side=r.side, stop=r.stop, ratio=r.ratio,
                 is_net=r.net, is_win=r.win,
                 pct_mo=monthly_pct(s["net"], s["n"], n_months_oos))
        out.append(s)
    O = pd.DataFrame(out).sort_values("net", ascending=False)
    O.to_csv(os.path.join(OUT, "oos_scan.csv"), index=False)
    print(O[["gate", "side", "stop", "ratio", "n", "win", "base", "excess", "z",
             "is_net", "net", "t", "pct_mo"]]
          .to_string(index=False, float_format=lambda v: f"{v:8.2f}"))
    surv = O[(O.net > 0) & (O.win >= 70) & (O.pct_mo >= 3.0)]
    print(f"\nSURVIVORS meeting the full spec OUT OF SAMPLE: {len(surv)}/{len(O)}")
    print(f"  merely net-positive OOS: {(O.net > 0).sum()}/{len(O)}  "
          f"(coin-flip expectation if all edges are fake: ~{len(O)/2:.0f})")
    print(f"  IS->OOS net correlation: {O.is_net.corr(O.net):+.3f} "
          f"(a real effect persists; noise gives ~0)")
