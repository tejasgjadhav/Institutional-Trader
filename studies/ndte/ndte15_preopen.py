"""PRE-OPEN OBSERVABLE SIGNALS — the avoidable-vs-unavoidable test that needs no news feed.

Motivation: the previous study rejected a *calendar* event filter (RBI/Budget/FOMC). But the user's
real question is broader — "what factors known before 09:15 should make us stand aside?" Most of
those factors (overnight Wall Street move, a weekend geopolitical escalation, a crude spike, an
Asian-market gap) are UNPREDICTABLE as events yet FULLY OBSERVABLE at the open. And they all
express themselves in one number the market computes for us: **the overnight gap**.

That makes the gap a strictly better instrument than any news list: it is the market's own
weighted summary of every overnight input, it needs no news API, and it is available for the whole
2019->2026 history. If "bad news before the open" hurts this book, a gap filter must show it.

NO LOOKAHEAD: these books enter at ~09:16, after the 09:15 open prints. So the open — and hence
the gap — is genuinely known before entry. Same for rv5 / prior-day move, which use only closed bars.

Signals tested (all pre-09:16 observable):
  GAP    |open / prev_close - 1| * 100      overnight news, in one number
  RV5    5-day realized vol of closes       regime vol (deployed on NIFTY, NOT on SENSEX/BNF)
  PREV   |prev_close / prev_prev_close - 1| yesterday's move
For each, sweep thresholds and report: trade-all baseline vs "skip when signal >= threshold".
Verdict is decided on TOTAL Rs (skipping trades always changes win%; only Rs says if it paid).
"""
import warnings; warnings.filterwarnings("ignore")
import os, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
C = "/tmp/ndte_ev"

rows = []
for fn in ("ndte14_trades_2019.json", "ndte13_trades.json"):
    p = os.path.join(HERE, fn)
    if os.path.exists(p): rows += json.load(open(p))
rows = [r for r in rows if r["traded"]]

# spot series per book, both eras merged
SPOTF = {
    "NIFTY":     ["spot2019_NIFTY.json", "spot_NIFTY.json"],
    "BANKNIFTY": ["spot2019_BANKNIFTY.json", "spot_BANKNIFTY.json"],
    "SENSEX":    ["spot_SENSEX.json"],
}
spots = {}
for b, files in SPOTF.items():
    m = {}
    for f in files:
        p = os.path.join(C, f)
        if os.path.exists(p): m.update(json.load(open(p)))
    spots[b] = m

def enrich(r):
    s = spots.get(r["book"], {})
    days = sorted(s)
    d = r["date"]
    if d not in s: return None
    i = days.index(d)
    if i < 2: return None
    o = s[d][0]; pc = s[days[i - 1]][3]; ppc = s[days[i - 2]][3]
    if not pc or not ppc: return None
    r = dict(r)
    r["gap"] = abs(o / pc - 1) * 100
    r["gap_signed"] = (o / pc - 1) * 100
    r["prev"] = abs(pc / ppc - 1) * 100
    return r

rows = [x for x in (enrich(r) for r in rows) if x]
rows.sort(key=lambda r: r["date"])
print(f"{len(rows)} trades with pre-open signals ({rows[0]['date']} -> {rows[-1]['date']})")

def stats(sel):
    if not sel: return None
    pm = np.array([r["pm"] for r in sel]); rs = np.array([r["rs"] for r in sel])
    return dict(n=len(sel), win=(pm > 0).mean() * 100, avg=pm.mean(), tot=rs.sum(), worst=rs.min())

def sweep(name, sel, key, thresholds):
    base = stats(sel)
    if not base: return
    print(f"\n  signal: {key.upper()}   (baseline n={base['n']}  win {base['win']:.1f}%  "
          f"avg {base['avg']:+.2f}%m  tot Rs{base['tot']:+,.0f})")
    print(f"    {'skip if >=':>11s} {'kept':>5s} {'skipped':>7s} {'win%':>6s} {'avg%m':>7s} "
          f"{'tot Rs':>11s} {'vs base':>10s} {'skipped-subset':>22s}")
    for t in thresholds:
        keep = [r for r in sel if r[key] < t]
        drop = [r for r in sel if r[key] >= t]
        sk, sd = stats(keep), stats(drop)
        if not sk or not sd or sd["n"] < 3: continue
        d = sk["tot"] - base["tot"]
        flag = "HELPS" if d > 0 else "costs"
        print(f"    {t:>11.2f} {sk['n']:>5d} {sd['n']:>7d} {sk['win']:>6.1f} {sk['avg']:>+7.2f} "
              f"{sk['tot']:>+11,.0f} {d:>+10,.0f} {flag:>6s}  "
              f"[{sd['win']:.0f}% {sd['avg']:+.1f}%m Rs{sd['tot']:+,.0f}]")

GRID = dict(gap=[0.25, 0.4, 0.5, 0.6, 0.75, 1.0, 1.25, 1.5],
            rv5=[0.5, 0.6, 0.7, 0.8, 0.9, 1.1, 1.3],
            prev=[0.5, 0.75, 1.0, 1.25, 1.5, 2.0])

for b in sorted({r["book"] for r in rows}):
    sel = [r for r in rows if r["book"] == b]
    print(f"\n{'='*118}\n{b}  (2019 -> date, deployed-filter trades, n={len(sel)})\n{'='*118}")
    for key, th in GRID.items():
        if key == "rv5" and b == "NIFTY":
            print(f"\n  signal: RV5 — already deployed on NIFTY (rv5<0.9); sweeping shows the residual only")
        sub = [r for r in sel if r.get(key) is not None]
        sweep(b, sub, key, th)

print(f"\n{'='*118}\nPOOLED — ALL BOOKS 2019 -> date\n{'='*118}")
for key, th in GRID.items():
    sweep("POOLED", [r for r in rows if r.get(key) is not None], key, th)

# does a big gap actually predict a loss? direct diagnostic, no thresholds
print(f"\n{'='*118}\nDIAGNOSTIC — outcome by gap bucket (is 'bad overnight news' actually bad for us?)\n{'='*118}")
buckets = [(0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.0), (1.0, 99)]
print(f"  {'gap %':>12s} {'n':>5s} {'win%':>6s} {'avg %m':>8s} {'tot Rs':>11s} {'worst Rs':>10s}")
for lo, hi in buckets:
    sel = [r for r in rows if lo <= r["gap"] < hi]
    s = stats(sel)
    if not s: continue
    print(f"  {lo:>5.2f}-{hi if hi<99 else 9.99:<6.2f} {s['n']:>5d} {s['win']:>6.1f} {s['avg']:>+8.2f} "
          f"{s['tot']:>+11,.0f} {s['worst']:>+10,.0f}")
print(f"\n  by SIGNED gap (down-gap = risk-off overnight news):")
for lo, hi, lab in [(-99, -0.75, "gap DOWN >0.75%"), (-0.75, -0.25, "gap down 0.25-0.75%"),
                    (-0.25, 0.25, "flat +-0.25%"), (0.25, 0.75, "gap up 0.25-0.75%"),
                    (0.75, 99, "gap UP >0.75%")]:
    sel = [r for r in rows if lo <= r["gap_signed"] < hi]
    s = stats(sel)
    if not s: continue
    print(f"  {lab:>22s} n={s['n']:>4d} win {s['win']:>5.1f}%  avg {s['avg']:+6.2f}%m  "
          f"tot Rs{s['tot']:+,.0f}  worst Rs{s['worst']:+,.0f}")

# ---------------------------------------------------------------------------
# ROBUSTNESS. The two candidate rules above were found by SWEEPING thresholds on
# the whole sample — that is in-sample optimisation and is exactly how this repo's
# index-fade "6 positive years" result died. So: do they survive an ERA SPLIT?
# A rule that only works in one era is a regime artifact, not an edge.
# ---------------------------------------------------------------------------
print(f"\n{'='*118}\nROBUSTNESS — do the candidate rules hold in BOTH eras independently?\n{'='*118}")
CANDS = [
    ("skip rv5 >= 1.10",        lambda r: r["rv5"] is not None and r["rv5"] >= 1.10),
    ("skip rv5 >= 1.30",        lambda r: r["rv5"] is not None and r["rv5"] >= 1.30),
    ("skip gap_UP >= 0.75%",    lambda r: r["gap_signed"] >= 0.75),
    ("skip |gap| >= 0.75%",     lambda r: r["gap"] >= 0.75),
    ("skip gap_UP>=0.75 OR rv5>=1.10",
     lambda r: r["gap_signed"] >= 0.75 or (r["rv5"] is not None and r["rv5"] >= 1.10)),
]
ERAS = [("ERA A 2019->Jul'24", "2019-01-01", "2024-09-30"),
        ("ERA B Oct'24->date", "2024-10-01", "2026-12-31")]
for lab, fn in CANDS:
    print(f"\n  {lab}")
    for elab, lo, hi in ERAS:
        sel = [r for r in rows if lo <= r["date"] <= hi]
        base = stats(sel); keep = stats([r for r in sel if not fn(r)]); drop = stats([r for r in sel if fn(r)])
        if not base or not keep: continue
        d = keep["tot"] - base["tot"]
        print(f"    {elab:20s} base n={base['n']:3d} Rs{base['tot']:+9,.0f} -> keep n={keep['n']:3d} "
              f"Rs{keep['tot']:+9,.0f} ({d:+8,.0f}) {'HELPS' if d>0 else 'costs'}"
              + (f"   [skipped n={drop['n']}, {drop['win']:.0f}% win, {drop['avg']:+.1f}%m]" if drop else ""))

print(f"\n{'='*118}\nSIGNED-GAP BUCKETS BY ERA — is the 'up-gap is the danger' asymmetry real in both?\n{'='*118}")
for elab, lo, hi in ERAS:
    print(f"\n  {elab}")
    for glo, ghi, gl in [(-99, -0.75, "gap DOWN >0.75%"), (-0.75, -0.25, "gap down .25-.75"),
                         (-0.25, 0.25, "flat"), (0.25, 0.75, "gap up .25-.75"),
                         (0.75, 99, "gap UP >0.75%")]:
        s = stats([r for r in rows if lo <= r["date"] <= hi and glo <= r["gap_signed"] < ghi])
        if not s: continue
        print(f"    {gl:>18s} n={s['n']:>4d} win {s['win']:>5.1f}%  avg {s['avg']:+7.2f}%m  Rs{s['tot']:+9,.0f}")

print("\nDONE-NDTE15")
