"""Screen the 0.25-0.30 band, short leg Rs 30-50, per NAME x SIDE in BOTH windows (user, 27-Sep-2026).
Tranche = rows at floor 30 (research/premband25_*_30_rows.json) not present at floor 50
(research/band25_*_rows_all.json, c/w < 0.30). Qualifier: n >= 3, win >= 80% and ROM > +5% in
IS AND OOS. Writes research/premband25_qualifiers.json."""
import json, collections
K = lambda r: (r["sym"], r["day"])
def st(v):
    return dict(n=len(v), win=100 * sum(r["win"] for r in v) / len(v),
                rom=100 * sum(r["net"] for r in v) / sum(r["margin"] for r in v), net=sum(r["net_rs"] for r in v))
inc = {}
for w in ("is", "oos"):
    hi = {K(r) for r in json.load(open(f"research/band25_{w}_rows_all.json")) if r["cw"] < 0.30}
    inc[w] = [r for r in json.load(open(f"research/premband25_{w}_30_rows.json")) if K(r) not in hi]
    s = st(inc[w]); print(f"{w.upper()} tranche: {s['n']} trades · {s['win']:.1f}% · {s['rom']:+.1f}% · net Rs {s['net']:,.0f}")
    for sd in ("BC", "BP"):
        v = [r for r in inc[w] if r["side"] == sd]
        if v: s = st(v); print(f"   {sd}: {s['n']} · {s['win']:.1f}% · {s['rom']:+.1f}% · net Rs {s['net']:,.0f}")
cells = {w: collections.defaultdict(list) for w in inc}
for w in inc:
    for r in inc[w]: cells[w][(r["sym"], r["side"])].append(r)
rows = []
for k in set(cells["is"]) | set(cells["oos"]):
    a = st(cells["is"][k]) if cells["is"].get(k) else None; b = st(cells["oos"][k]) if cells["oos"].get(k) else None
    ok = bool(a and b and a["n"] >= 3 and b["n"] >= 3 and a["win"] >= 80 and b["win"] >= 80 and a["rom"] > 5 and b["rom"] > 5)
    rows.append((ok, k, a, b))
f = lambda s: f"{s['n']}/{s['win']:.0f}%/{s['rom']:+.0f}%" if s else "—"
q = sorted([x for x in rows if x[0]], key=lambda x: -(x[3]["n"]))
print(f"\nQUALIFY IN BOTH WINDOWS: {len(q)}")
for ok, k, a, b in q: print(f"  {k[0]:12s} {k[1]}  IS {f(a):>14s}  OOS {f(b):>14s}  OOS net Rs {b['net']:,.0f}")
if q:
    for w, idx in (("IS", 2), ("OOS", 3)):
        v = [r for ok, k, a, b in q for r in cells[w.lower()][k]]; s = st(v); print(f"pooled qualifiers {w}: {s['n']} · {s['win']:.1f}% · {s['rom']:+.1f}% · net Rs {s['net']:,.0f}")
print("\nIS-strong cells that FAILED out-of-sample (IS n>=5, >=80%, >+5%):")
for ok, k, a, b in sorted(rows, key=lambda x: -(x[2]["n"] if x[2] else 0)):
    if not ok and a and a["n"] >= 5 and a["win"] >= 80 and a["rom"] > 5:
        print(f"  {k[0]:12s} {k[1]}  IS {f(a):>14s}  OOS {f(b):>14s}")
json.dump([{"sym": k[0], "side": k[1], "is": a, "oos": b} for ok, k, a, b in q], open("research/premband25_qualifiers.json", "w"), indent=1)
