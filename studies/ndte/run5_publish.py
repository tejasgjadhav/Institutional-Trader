"""Every published number for v2/v1/v0 from the run-5 row files, on the published basis:
median cohort (v2/v1 c/w 0.40-0.50, v0 its own band 0.35-0.40), ROM in points, years with < 5 trades
are stubs, Rs/month = cohort net_rs / months in the window. Writes research/run5_publish.json."""
import json, collections
MIN_YR_N = 5
def months_of(rows):
    ds = sorted(x["day"] for x in rows); y0, m0 = int(ds[0][:4]), int(ds[0][5:7]); y1, m1 = int(ds[-1][:4]), int(ds[-1][5:7])
    return (y1 - y0) * 12 + (m1 - m0) + 1, ds[0], ds[-1]
out = {}
for w in ("is", "oos"):
    import sys as _s
    _p = (_s.argv[1] if (w == "oos" and len(_s.argv) > 1) else f"research/deployed_bt_{w}_rows.json")
    rows = json.load(open(_p)); mo, d0, d1 = months_of(rows); out[w + "_src"] = _p
    out[w] = {"months": mo, "first": d0, "last": d1}
    for bk in ("v2", "v1", "v0"):
        lo, hi = (0.35, 0.40) if bk == "v0" else (0.40, 0.50)
        g = [x for x in rows if x["book"] == bk and lo <= x["cw"] < hi]
        W = [x["net_rs"] for x in g if x["win"]]; L = [x["net_rs"] for x in g if not x["win"]]
        by = collections.defaultdict(list)
        for x in g: by[x["yr"]].append(x["net_rs"])
        full = {y: v for y, v in by.items() if len(v) >= MIN_YR_N}
        n = len(g); wr = len(W) / n
        aw = sum(W) / len(W) if W else 0.0; al = -sum(L) / len(L) if L else 0.0
        out[w][bk] = dict(n=n, per_mo=round(n / mo, 1), win=round(100 * wr, 1),
                          rom=round(100 * sum(x["net"] for x in g) / sum(x["margin"] for x in g), 1),
                          avg_win=round(aw), avg_loss=round(al), exp=round(wr * aw - (1 - wr) * al),
                          rs_tr=round(sum(x["net_rs"] for x in g) / n), rs_mo=round(sum(x["net_rs"] for x in g) / mo),
                          pos=sum(1 for v in full.values() if sum(v) > 0), full=len(full))
json.dump(out, open("research/run5_publish.json", "w"), indent=1)
for w in ("is", "oos"):
    print(f"{w.upper()} {out[w]['months']} months {out[w]['first']} -> {out[w]['last']}")
    for bk in ("v2", "v1", "v0"):
        s = out[w][bk]; print(f"  {bk}: n={s['n']} ({s['per_mo']}/mo) win {s['win']}% ROM {s['rom']:+}% avgW ₹{s['avg_win']:,} avgL ₹{s['avg_loss']:,} exp ₹{s['exp']:,} ₹/tr {s['rs_tr']:,} ₹/mo {s['rs_mo']:,} +yrs {s['pos']}/{s['full']}")
