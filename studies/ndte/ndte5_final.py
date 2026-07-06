import os, json
import numpy as np, pandas as pd
spots = json.load(open('/tmp/ndte_cache/spot2019.json'))
SLIP = 2.5; BROKER = 20.0
def lot_for(ds): return 75 if ds < '2021-04-01' else (50 if ds < '2024-11-20' else 75)
rows = []
for f in sorted(os.listdir('/tmp/ndte_bhav')):
    if not f.endswith('.csv'): continue
    ds = f[:-4]; sp = spots.get(ds)
    if not sp: continue
    df = pd.read_csv('/tmp/ndte_bhav/' + f)
    legs = {(float(r['STRIKE_PR']), r['OPTION_TYP']): (float(r['OPEN']), float(r['HIGH']), float(r['LOW']), float(r['CLOSE']), float(r['CONTRACTS'])) for _, r in df.iterrows()}
    st = sorted(set(k[0] for k in legs))
    near = lambda x: min(st, key=lambda s: abs(s - x))
    Ks = near(sp[0] * 1.005); Kl = near(Ks + 200)
    vs, vl = legs.get((Ks, 'CE')), legs.get((Kl, 'CE'))
    if not vs or not vl or vs[0] <= 0 or vs[4] < 100: continue
    credit = vs[0] - vl[0]
    if credit <= 0: continue
    lot = lot_for(ds)
    net = (vs[0] - vs[3]) + (vl[3] - vl[0]) - ((vs[0] + vl[0]) * SLIP / 100 + BROKER * 4 / lot)
    m = 200 - credit
    rows.append((ds, net / m * 100, net * 75, credit))
oos = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ndte4_oos.json')))['0.005_200']
rows += [(e, pmv, rpv, None) for e, pmv, rpv in oos]
rows.sort()
pm = np.array([r[1] for r in rows]); rp = np.array([r[2] for r in rows])
print(f'COMBINED 2019-02 -> 2026-06, CE 0.50%OTM W=200 no-stop, n={len(rows)}')
print(f'win {(pm>0).mean()*100:.1f}%  avg {pm.mean():+.2f}%m  med {np.median(pm):+.2f}%m  avg Rs{rp.mean():+.0f}/trade(lot75)')
w = pm[pm > 0]; l = pm[pm <= 0]
print(f'avg win {w.mean():+.1f}%m  avg loss {l.mean():+.1f}%m  worst {pm.min():+.1f}%m  payoff {abs(w.mean()/l.mean()):.2f}')
yr = {}
for r in rows: yr.setdefault(r[0][:4], []).append((r[1], r[2]))
for y in sorted(yr):
    a = np.array(yr[y])
    print(f'{y} n={len(a):2d} win {(a[:,0]>0).mean()*100:5.1f}% avg {a[:,0].mean():+6.2f}%m  Rs{a[:,1].sum():+8.0f}/yr')
streak = mx = 0
for r in rows:
    streak = streak + 1 if r[1] <= 0 else 0
    mx = max(mx, streak)
mo = {}
for r in rows: mo.setdefault(r[0][:7], []).append(r[2])
ms = np.array([sum(v) for v in mo.values()])
print(f'max consecutive losses: {mx} | months neg: {(ms<0).sum()}/{len(ms)} | worst mo Rs{ms.min():+.0f} | median mo Rs{np.median(ms):+.0f}')
crs = [r[3] for r in rows if r[3]]
print(f'median credit {np.median(crs):.1f} pts (of 200 width); margin ~Rs{(200-np.median(crs))*75:,.0f}/lot')
print('DONE-NDTE5')
