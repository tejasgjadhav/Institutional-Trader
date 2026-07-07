"""Intraday pairs mean-reversion on /tmp/k5m (100 stocks, 5-min, 2019-2026).
Phase 1: pair selection on DAILY closes 2019-2023 (corr of log returns >= 0.75, top 30 by corr,
same rough sector implied by correlation itself). Phase 2: intraday sim on 5-min for selected
pairs: ratio z vs prior-60-day daily mean/std (no lookahead), enter |z|>=2 in 9:45-14:00
(long cheap / short rich, equal notional), exit z->0 same day or EOD close.
Costs: 0.12% of one-leg notional per round-trip pair trade (4 legs x ~0.03%).
Margin: ~40% of one-leg notional (two futures-style legs) -> return_on_margin = net/0.40.
IS 2019-2023 / OOS 2024-2026.
"""
import os, json
import numpy as np

CACHE = "/tmp/k5m"
COST = 0.12
ENTRY_LO, ENTRY_HI = 9 * 60 + 45, 14 * 60
EOD = 15 * 60 + 20
Z_IN = 2.0

def load(sym):
    bars = json.load(open(f"{CACHE}/{sym}.json"))
    days = {}
    for b in bars:
        days.setdefault(b["date"][:10], []).append(
            (int(b["date"][11:13]) * 60 + int(b["date"][14:16]), b["close"]))
    return days

def main():
    syms = sorted(f[:-5] for f in os.listdir(CACHE) if f.endswith(".json"))
    # phase 1: daily closes
    daily = {}
    for s in syms:
        d = load(s)
        daily[s] = {k: v[-1][1] for k, v in d.items()}
    print("daily built", flush=True)
    dates = sorted(set.intersection(*(set(v) for v in daily.values())))
    is_dates = [d for d in dates if d < "2024-01-01"]
    M = np.array([[daily[s][d] for d in is_dates] for s in syms])
    R = np.diff(np.log(M), axis=1)
    C = np.corrcoef(R)
    cand = []
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            if C[i, j] >= 0.75:
                cand.append((C[i, j], syms[i], syms[j]))
    cand.sort(reverse=True)
    pairs = cand[:30]
    print(f"{len(cand)} candidate pairs, using top {len(pairs)}", flush=True)
    # phase 2
    need = sorted({s for _, a, b in pairs for s in (a, b)})
    intr = {s: load(s) for s in need}
    print("intraday loaded", flush=True)
    res = []
    all_dates = sorted(set(dates) | {d for d in sorted(intr[need[0]]) if d >= "2024-01-01"})
    for corr, A, B in pairs:
        da, db = daily[A], daily[B]
        common = sorted(set(da) & set(db))
        ratio_hist = {}
        for k, d in enumerate(common):
            if k >= 60:
                w = [np.log(da[common[m]] / db[common[m]]) for m in range(k - 60, k)]
                ratio_hist[d] = (np.mean(w), np.std(w))
        for d in common:
            if d not in ratio_hist:
                continue
            mu, sd = ratio_hist[d]
            if sd <= 0:
                continue
            ia, ib = intr[A].get(d), intr[B].get(d)
            if not ia or not ib:
                continue
            pb = {m: c for m, c in ib}
            pos = None
            for m, ca in ia:
                if m > EOD:
                    break
                cb = pb.get(m)
                if cb is None:
                    continue
                z = (np.log(ca / cb) - mu) / sd
                if pos is None:
                    if ENTRY_LO <= m <= ENTRY_HI and abs(z) >= Z_IN:
                        pos = (np.sign(z), ca, cb, m)   # z>0: A rich -> short A long B
                else:
                    sgn, ea, eb, _ = pos
                    if z * sgn <= 0 or m >= EOD - 5:
                        ret = sgn * ((eb and (cb - eb) / eb or 0) - (ca - ea) / ea) * 100
                        net = ret - COST
                        res.append((d, net, net / 0.40))
                        pos = None
                        break
            if pos:  # never exited within loop (no bar past EOD-5) -> close at last common bar
                sgn, ea, eb, _ = pos
                m, ca = ia[-1]
                cb = pb.get(m) or list(pb.values())[-1]
                ret = sgn * ((cb - eb) / eb - (ca - ea) / ea) * 100
                res.append((d, ret - COST, (ret - COST) / 0.40))
    print(f"\n{len(res)} pair-trades")
    for lab, lo, hi in (("IS 2019-23", "2019", "2024"), ("OOS 2024-26", "2024", "2027"), ("ALL", "2019", "2027")):
        sub = [r for r in res if lo <= r[0][:4] < hi]
        if not sub:
            continue
        pm = np.array([r[1] for r in sub]); rm = np.array([r[2] for r in sub])
        days_n = len(set(r[0] for r in sub))
        print(f"{lab:12s} n={len(sub):5d} ({len(sub)/max(days_n,1):.1f}/day) win {(pm>0).mean()*100:5.1f}%  "
              f"avg net {pm.mean():+6.3f}% notional  = {rm.mean():+6.2f}% on margin  worst {pm.min():+6.2f}%")
    print("DONE-PAIRS")

if __name__ == "__main__":
    main()
