"""Intraday 90%-win study on cached Kite 5-min bars (100 F&O stocks, 2019 -> 2026-07).
Entries: mean-reversion VWAP flush (long/short), ORB momentum, 10:00 baseline.
Geometry: small TP x wide SL x forced EOD close 15:20. Conservative intrabar: SL first.
Entry at signal-bar close; evaluation starts NEXT bar (no lookahead).
Aggregates per (family, thr, tp, sl, year) on the fly — memory-light, per-year for free.
Costs reported at 0.10% round trip (retail intraday equity incl. slippage).
"""
import json, os
import numpy as np
from collections import defaultdict

CACHE = "/tmp/k5m"
COST = 0.10
EOD_MIN = 15 * 60 + 20
ENTRY_LO, ENTRY_HI = 9 * 60 + 45, 14 * 60
ORB_BARS = 6
TPS = np.array([0.20, 0.25, 0.30, 0.40, 0.50, 0.75])
SLS = np.array([1.0, 1.5, 2.0, 2.5, 3.0])
MR_THRESHOLDS = [0.75, 1.0, 1.5, 2.0]

# acc[(fam,thr,tp_i,sl_i,year)] = [n, wins_gross, wins_net, sum_gross]
acc = defaultdict(lambda: [0, 0, 0, 0.0])

def record(fam, thr, year, rets):
    """rets: (6,5) gross returns per grid cell"""
    for ti in range(len(TPS)):
        for si in range(len(SLS)):
            r = rets[ti, si]
            a = acc[(fam, thr, ti, si, year)]
            a[0] += 1
            a[1] += 1 if r > 0 else 0
            a[2] += 1 if r - COST > 0 else 0
            a[3] += r

def grid_outcome(entry, side, hi, lo, cl, i):
    """First-touch outcome for the whole TP x SL grid, vectorized. SL first on ties."""
    h, l, c = hi[i + 1:], lo[i + 1:], cl[i + 1:]
    nb = len(h)
    if nb == 0:
        return None
    eod = (c[-1] - entry) / entry * 100 * side
    if side == 1:
        # first bar index reaching each TP / SL level
        t_tp = np.array([np.argmax(h >= entry * (1 + t / 100)) if (h >= entry * (1 + t / 100)).any() else 10**9 for t in TPS])
        t_sl = np.array([np.argmax(l <= entry * (1 - s / 100)) if (l <= entry * (1 - s / 100)).any() else 10**9 for s in SLS])
    else:
        t_tp = np.array([np.argmax(l <= entry * (1 - t / 100)) if (l <= entry * (1 - t / 100)).any() else 10**9 for t in TPS])
        t_sl = np.array([np.argmax(h >= entry * (1 + s / 100)) if (h >= entry * (1 + s / 100)).any() else 10**9 for s in SLS])
    TT = t_tp[:, None]          # (6,1)
    TS = t_sl[None, :]          # (1,5)
    rets = np.where((TS <= TT) & (TS < 10**9), -SLS[None, :],
                    np.where(TT < 10**9, TPS[:, None], eod))
    return rets

def load_days(sym):
    try:
        bars = json.load(open(f"{CACHE}/{sym}.json"))
    except Exception:
        return
    cur, out = None, []
    for b in bars:
        ds = b["date"][:10]
        if ds != cur:
            if out:
                yield cur, out
            cur, out = ds, []
        hh, mm = int(b["date"][11:13]), int(b["date"][14:16])
        out.append((b["open"], b["high"], b["low"], b["close"], b["volume"], hh * 60 + mm))
    if out:
        yield cur, out

def scan_stock(sym):
    for ds, rows in load_days(sym):
        if len(rows) < ORB_BARS + 4:
            continue
        a = np.array(rows, dtype=float)
        m = a[:, 5].astype(int)
        keep = m <= EOD_MIN
        if keep.sum() < ORB_BARS + 4:
            continue
        a, m = a[keep], m[keep]
        o, h, l, c, v = a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4]
        year = int(ds[:4])
        n = len(c)
        tp_price = (h + l + c) / 3
        cv = np.cumsum(v)
        vwap = np.where(cv > 0, np.cumsum(tp_price * v) / np.maximum(cv, 1e-9),
                        np.cumsum(tp_price) / np.arange(1, n + 1))
        dev = (c - vwap) / vwap * 100
        in_win = (m >= ENTRY_LO) & (m <= ENTRY_HI)
        # mean reversion
        for thr in MR_THRESHOLDS:
            for fam, side, cond in (("MR_L", 1, dev <= -thr), ("MR_S", -1, dev >= thr)):
                idx = np.where(cond & in_win)[0]
                if len(idx) == 0 or idx[0] + 1 >= n:
                    continue
                i = int(idx[0])
                r = grid_outcome(c[i], side, h, l, c, i)
                if r is not None:
                    record(fam, thr, year, r)
        # ORB momentum: break of 30-min range + 1.2x volume surge (first only)
        orb_h, orb_l = h[:ORB_BARS].max(), l[:ORB_BARS].min()
        cum_v = np.cumsum(v)
        for i in range(ORB_BARS, n - 1):
            if m[i] > ENTRY_HI:
                break
            if not in_win[i]:
                continue
            avg_v = cum_v[i - 1] / i
            if avg_v <= 0 or v[i] < 1.2 * avg_v:
                continue
            side = 1 if c[i] > orb_h else (-1 if c[i] < orb_l else 0)
            if side == 0:
                continue
            r = grid_outcome(c[i], side, h, l, c, i)
            if r is not None:
                record("ORB", 0.0, year, r)
            break
        # baseline long at 10:00 (every 3rd day)
        if hash(ds) % 3 == 0:
            idx = np.where(m == 600)[0]
            if len(idx) and idx[0] + 1 < n:
                i = int(idx[0])
                r = grid_outcome(c[i], 1, h, l, c, i)
                if r is not None:
                    record("BASE", 0.0, year, r)

def main():
    syms = sorted(f[:-5] for f in os.listdir(CACHE) if f.endswith(".json"))
    for k, s in enumerate(syms):
        scan_stock(s)
        if (k + 1) % 10 == 0:
            print(f"  ...{k+1}/{len(syms)} stocks, {len(acc)} agg cells", flush=True)
    # dump raw accumulators
    here = os.path.dirname(os.path.abspath(__file__))
    json.dump({"|".join(map(str, k)): v for k, v in acc.items()},
              open(os.path.join(here, "intraday90_acc.json"), "w"))
    # aggregate train/test
    def agg(fam, thr, ti, si, years):
        n = w = wn = 0; s = 0.0
        for y in years:
            a = acc.get((fam, thr, ti, si, y))
            if a:
                n += a[0]; w += a[1]; wn += a[2]; s += a[3]
        return n, w, wn, s
    fams = sorted(set((k[0], k[1]) for k in acc))
    print("\n=== TRAIN 2019-23 (gross win >= 88%), with TEST 2024-26 alongside ===")
    hdr = f"{'family':6s} {'thr':4s} {'tp':5s} {'sl':4s} | {'nTR':>6s} {'winTR':>6s} {'netTR':>7s} | {'nTE':>6s} {'winTE':>6s} {'netTE':>7s}"
    print(hdr)
    rows = []
    for fam, thr in fams:
        for ti, tp in enumerate(TPS):
            for si, sl in enumerate(SLS):
                n, w, wn, s = agg(fam, thr, ti, si, range(2019, 2024))
                if n == 0:
                    continue
                win_tr, net_tr = w / n * 100, s / n - COST
                if win_tr < 88:
                    continue
                n2, w2, wn2, s2 = agg(fam, thr, ti, si, range(2024, 2027))
                win_te = w2 / n2 * 100 if n2 else 0
                net_te = s2 / n2 - COST if n2 else 0
                rows.append((net_te, f"{fam:6s} {thr:4.2f} {tp:5.2f} {sl:4.1f} | {n:6d} {win_tr:6.1f} {net_tr:+7.3f} | {n2:6d} {win_te:6.1f} {net_te:+7.3f}"))
    for _, line in sorted(rows, reverse=True):
        print(line)
    print("DONE-I90")

if __name__ == "__main__":
    main()
