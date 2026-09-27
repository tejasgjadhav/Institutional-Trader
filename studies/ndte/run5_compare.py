"""Run 5 vs run 4, per book, on the PUBLISHED basis (median cohort 0.40-0.50 for v2/v1, own band
0.35-0.40 for v0; ROM in points; years under MIN_YR_N are stubs). Rs/mo = cohort net_rs / months."""
import json, collections, sys
sys.path.insert(0, "studies/ndte")
MIN_YR_N = 5
MONTHS = {"is": 69.0, "oos": None}
def summ(rows, bk, months):
    lo, hi = (0.35, 0.40) if bk == "v0" else (0.40, 0.50)
    g = [x for x in rows if x["book"] == bk and lo <= x["cw"] < hi]
    if not g: return None
    by = collections.defaultdict(list)
    for x in g: by[x["yr"]].append(x["net_rs"])
    full = {y: v for y, v in by.items() if len(v) >= MIN_YR_N}
    return dict(n=len(g), win=100*sum(x["win"] for x in g)/len(g), rom=100*sum(x["net"] for x in g)/sum(x["margin"] for x in g),
                rs_tr=sum(x["net_rs"] for x in g)/len(g), rs_mo=sum(x["net_rs"] for x in g)/months, per_mo=len(g)/months,
                pos=sum(1 for v in full.values() if sum(v) > 0), full=len(full))
def months_of(rows):
    ds = sorted(x["day"] for x in rows); y0, m0 = int(ds[0][:4]), int(ds[0][5:7]); y1, m1 = int(ds[-1][:4]), int(ds[-1][5:7])
    return (y1 - y0) * 12 + (m1 - m0) + 1
out = {}
for w in ("is", "oos"):
    r4 = json.load(open(f"research/deployed_bt_{w}_rows_run4.json")); r5 = json.load(open(f"research/deployed_bt_{w}_rows.json"))
    mo = months_of(r4)
    print(f"\n=== {w.upper()} ({mo} months) · published basis ===")
    print(f"{'book':5s} {'run 4':>44s} | {'run 5':>44s}")
    for bk in ("v2", "v1", "v0"):
        a, b = summ(r4, bk, mo), summ(r5, bk, mo); out[(w, bk)] = b
        f = lambda s: f"{s['n']:4d} · {s['win']:5.1f}% · {s['rom']:+5.1f}% · ₹{s['rs_mo']:>7,.0f}/mo · {s['per_mo']:.1f}/mo · {s['pos']}/{s['full']}" if s else "—"
        print(f"{bk:5s} {f(a):>44s} | {f(b):>44s}")
json.dump({f"{w}_{bk}": v for (w, bk), v in out.items()}, open("research/run5_summary.json", "w"), indent=1)
