"""Loss-avoidance study for the 0DTE CE spread (d=0.5% W=200 no-stop).
Features known at 9:16 (no lookahead) from spot/VIX daily + chain. Winner/loser forensics,
then single- and two-feature filter sweep. IS = bhav 2019->Jul'24 (recomputed); OOS = ndte4 rows.
A filter passes only if it improves BOTH IS and OOS net%m without gutting frequency.
"""
import os, json
import numpy as np
import pandas as pd

SLIP = 2.5; BROKER = 20.0
spots = json.load(open('/tmp/ndte_cache/spot2019.json'))
vix = json.load(open('/tmp/ndte_cache/vix2019.json'))
sdays = sorted(spots)

def lot_for(ds): return 75 if ds < '2021-04-01' else (50 if ds < '2024-11-20' else 75)

def features(ds):
    """All computed from data BEFORE 9:16 of ds."""
    i = sdays.index(ds)
    if i < 21: return None
    o = spots[ds][0]
    prev = [spots[sdays[j]] for j in range(i - 21, i)]   # prior 21 days OHLC
    pc = prev[-1][3]; ph = prev[-1][1]; pl = prev[-1][2]
    closes = np.array([p[3] for p in prev])
    f = {}
    f['gap'] = (o - pc) / pc * 100                        # signed overnight gap
    f['prev_ret'] = (pc - prev[-2][3]) / prev[-2][3] * 100
    f['ret5'] = (pc - prev[-6][3]) / prev[-6][3] * 100
    f['open_vs_phigh'] = (o - ph) / ph * 100              # >0 = opening above prior high
    f['prev_range'] = (ph - pl) / pc * 100
    f['atr5'] = np.mean([(p[1] - p[2]) / p[3] * 100 for p in prev[-5:]])
    f['ext20'] = (o - closes.mean()) / closes.mean() * 100  # extension vs 20d SMA
    f['rv5'] = np.std(np.diff(np.log(closes[-6:]))) * 100
    up = 0
    for j in range(len(prev) - 1, 0, -1):
        if prev[j][3] > prev[j - 1][3]: up += 1
        else: break
    f['up_streak'] = up
    v = vix.get(ds) or vix.get(sdays[i - 1])
    pv = vix.get(sdays[i - 1])
    f['vix'] = v[0] if v else np.nan                      # VIX open today (known 9:16)
    f['vix_chg'] = (v[0] - pv[3]) / pv[3] * 100 if (v and pv) else np.nan
    return f

# ── IS trades from bhav ──────────────────────────────────────────────────────
rows = []
for fn in sorted(os.listdir('/tmp/ndte_bhav')):
    if not fn.endswith('.csv'): continue
    ds = fn[:-4]
    if ds not in spots: continue
    df = pd.read_csv('/tmp/ndte_bhav/' + fn)
    ce = df[df.OPTION_TYP == 'CE'].set_index('STRIKE_PR')
    st = sorted(ce.index)
    if len(st) < 10: continue
    o = spots[ds][0]
    near = lambda x: min(st, key=lambda k: abs(k - x))
    Ks = near(o * 1.005); Kl = near(Ks + 200)
    if abs(Kl - Ks) < 100: continue
    try: vs, vl = ce.loc[Ks], ce.loc[Kl]
    except Exception: continue
    if vs.OPEN <= 0 or vs.CONTRACTS < 100: continue
    credit = vs.OPEN - vl.OPEN
    if credit <= 0: continue
    lot = lot_for(ds)
    net = (vs.OPEN - vs.CLOSE) + (vl.CLOSE - vl.OPEN) - ((vs.OPEN + vl.OPEN) * SLIP / 100 + BROKER * 4 / lot)
    m = 200 - credit
    f = features(ds)
    if not f: continue
    f.update(dict(ds=ds, pm=net / m * 100, rp=net * lot, era='IS', cw=credit / 200))
    rows.append(f)

# ── OOS trades from ndte4 ────────────────────────────────────────────────────
oos = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ndte4_oos.json')))['0.005_200']
for ds, pm, rp in oos:
    f = features(ds)
    if not f: continue
    f.update(dict(ds=ds, pm=pm, rp=rp, era='OOS', cw=np.nan))
    rows.append(f)

D = pd.DataFrame(rows).set_index('ds').sort_index()
print(f"{len(D)} trades ({(D.era=='IS').sum()} IS + {(D.era=='OOS').sum()} OOS)")

# ── forensics: winners vs losers vs BIG losers ───────────────────────────────
FEATS = ['gap', 'prev_ret', 'ret5', 'open_vs_phigh', 'prev_range', 'atr5', 'ext20', 'rv5', 'up_streak', 'vix', 'vix_chg', 'cw']
W = D[D.pm > 0]; L = D[D.pm <= 0]; BL = D[D.pm <= -50]
print(f"\n=== feature medians: {len(W)} winners | {len(L)} losers | {len(BL)} big losers (<=-50%m) ===")
for f in FEATS:
    print(f"{f:14s}  win {W[f].median():+7.2f}   loss {L[f].median():+7.2f}   BIG loss {BL[f].median():+7.2f}")

# ── filter sweep ─────────────────────────────────────────────────────────────
def ev(sub, era):
    s = sub[sub.era == era]
    if len(s) == 0: return None
    return len(s), (s.pm > 0).mean() * 100, s.pm.mean(), s.rp.sum()

def show(name, mask):
    keep = D[mask]
    a = ev(keep, 'IS'); b = ev(keep, 'OOS')
    if not a or not b or a[0] < 150 or b[0] < 50: return None
    y25 = keep[(keep.era == 'OOS') & (keep.index.str.startswith('2025'))]
    base25 = D[(D.era == 'OOS') & (D.index.str.startswith('2025'))]
    line = (f"{name:34s} | IS n={a[0]:3d} win {a[1]:4.1f} avg {a[2]:+5.2f} | "
            f"OOS n={b[0]:2d} win {b[1]:4.1f} avg {b[2]:+5.2f} ₹{b[3]:+8.0f} | "
            f"2025: {len(y25)}tr ₹{y25.rp.sum():+7.0f} (base {len(base25)}tr ₹{base25.rp.sum():+7.0f})")
    return (b[2], a[2], line)

results = [show('BASE (no filter)', D.pm.notna())]
GRID = {
    'gap<': [0.2, 0.3, 0.5], 'gap>': [-0.3, -0.5],            # skip big gap-ups / take only gap-downs?
    'prev_ret<': [0.5, 1.0], 'ret5<': [1.5, 2.5],
    'open_vs_phigh<': [0.0, 0.3], 'ext20<': [1.0, 2.0],
    'up_streak<': [3, 4], 'atr5>': [0.6, 0.8], 'atr5<': [1.2, 1.6],
    'vix<': [15, 18, 22], 'vix>': [12, 14], 'vix_chg<': [3, 6],
    'prev_range<': [1.0, 1.5], 'rv5<': [0.9, 1.3],
}
def mk(f, op, t):
    return (D[f] < t) if op == '<' else (D[f] > t)
for k, ts in GRID.items():
    f, op = k[:-1], k[-1]
    for t in ts:
        r = show(f"{f}{op}{t}", mk(f, op, t))
        if r: results.append(r)
# two-feature combos of the most mechanism-plausible pairs
COMBOS = [('gap', '<', 0.3, 'up_streak', '<', 4), ('gap', '<', 0.3, 'ext20', '<', 2.0),
          ('gap', '<', 0.3, 'vix<', None, 22), ('open_vs_phigh', '<', 0.3, 'up_streak', '<', 4),
          ('gap', '<', 0.5, 'prev_ret', '<', 1.0)]
for a1, o1, t1, a2, o2, t2 in COMBOS:
    if a2 == 'vix<':
        m = mk(a1, o1, t1) & mk('vix', '<', t2); nm = f"{a1}{o1}{t1} & vix<{t2}"
    else:
        m = mk(a1, o1, t1) & mk(a2, o2, t2); nm = f"{a1}{o1}{t1} & {a2}{o2}{t2}"
    r = show(nm, m)
    if r: results.append(r)

print("\n=== filters ranked by OOS avg %m (must also beat base IS) ===")
base_is = results[0][1]
print(results[0][2])
for oosavg, isavg, line in sorted([r for r in results[1:] if r], key=lambda r: -r[0])[:18]:
    mark = ' ✓' if isavg > base_is else '  '
    print(line + mark)
print("DONE-NDTE6")
