"""Take-profit sweep report (user, 27-Sep-2026): all 208 F&O names, both sides, deployed gates,
every book's TP set to 20/30/40/50/60% of credit or held to expiry. Baseline = today's mixed TPs
(v2 50%, v1/v0 40%). Full band, 1 lot. Writes research/tpsweep/report.json."""
import json, os, collections, sys
sys.path.insert(0, ".")
from engine.config import UNIVERSE
U = {t.replace(".NS", "") for t in UNIVERSE}
L = lambda p: json.load(open(p)) if os.path.exists(p) else []
MO = {"is": 69, "oos": 23}
def dedup(rows):
    seen, out = set(), []
    for r in rows:
        k = (r["book"], r["sym"], r["day"])
        if k not in seen: seen.add(k); out.append(r)
    return out
def st(v, w):
    if not v: return None
    by = collections.defaultdict(float)
    for r in v: by[r["yr"]] += r["net_rs"]
    return dict(n=len(v), pm=len(v) / MO[w], win=sum(r["win"] for r in v) / len(v),
                rom=sum(r["net"] for r in v) / sum(r["margin"] for r in v), net=sum(r["net_rs"] for r in v),
                rs_mo=sum(r["net_rs"] for r in v) / MO[w], neg_yrs=sum(1 for y in by.values() if y < 0), yrs=len(by))
sets = {"baseline (v2 50 / v1,v0 40)": {"is": L("research/deployed_bt_is_rows_run5.json") + L("research/expansion2/is_rows.json") + L("research/pruned8_is_rows.json"),
                                        "oos": L("research/deployed_bt_oos_rows_run5.json") + L("research/expansion2/oos_rows.json") + L("research/pruned8_oos_rows.json")}}
for tp in (20, 30, 40, 50, 60, 99):
    lbl = f"TP {tp}%" if tp != 99 else "hold to expiry"
    sets[lbl] = {w: sum((L(f"research/tpsweep/tp{tp}_{s}_{w}.json") for s in ("main", "outs", "p8")), []) for w in ("is", "oos")}
rep = []
print(f"{'setting':30s} {'scope':9s} | {'IS /mo':>6s} {'win':>6s} {'ROM':>7s} {'₹/mo':>9s} | {'OOS /mo':>7s} {'win':>6s} {'ROM':>7s} {'₹/mo':>9s} {'neg yrs':>7s}")
for lbl, d in sets.items():
    for scope, f in (("all 208", lambda r: True), ("universe", lambda r: r["sym"] in U)):
        a = st([r for r in dedup(d["is"]) if f(r)], "is"); b = st([r for r in dedup(d["oos"]) if f(r)], "oos")
        if not a or not b:
            print(f"{lbl:30s} {scope:9s} | (not run yet)"); continue
        rep.append(dict(setting=lbl, scope=scope, is_=a, oos=b))
        print(f"{lbl:30s} {scope:9s} | {a['pm']:6.1f} {100*a['win']:5.1f}% {100*a['rom']:+6.1f}% {a['rs_mo']:>9,.0f} | {b['pm']:7.1f} {100*b['win']:5.1f}% {100*b['rom']:+6.1f}% {b['rs_mo']:>9,.0f} {b['neg_yrs']:>3d}/{b['yrs']}")
json.dump(rep, open("research/tpsweep/report.json", "w"), indent=1, default=str)
