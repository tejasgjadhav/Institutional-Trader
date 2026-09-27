"""Per-SIDE screen across all 208 NSE F&O underlyings on the deployed gates (run 5 harness, per-book
floor) — user, 27-Sep-2026: 'devise a strategy per BC and BP for all 208; we rejected companies that
failed even one side'. Side = breakout direction on the entry day (breakout_days). Pooled across the
deployed books on each name-side (one book fires per breakout). Outputs research/side_screen_208.json."""
import sys, json, collections, importlib.util
sys.path.insert(0, "."); sys.argv = ["side_screen", "OOS"]
spec = importlib.util.spec_from_file_location("dbt", "studies/ndte/deployed_backtest.py")
H = importlib.util.module_from_spec(spec); spec.loader.exec_module(H)
from engine.data_fetcher import fetch_upstox_historical
from engine.config import UNIVERSE
L = lambda p: json.load(open(p))
U = {t.replace(".NS", "") for t in UNIVERSE}; OUTS = set(L("research/expansion2/outsiders.json"))
P8 = {"HCLTECH", "SBILIFE", "OFSS", "TCS", "TECHM", "HDFCBANK", "DMART", "JINDALSTEL"}
IS = L("research/deployed_bt_is_rows_run5.json") + L("research/expansion2/is_rows.json") + L("research/pruned8_is_rows.json")
OOS = L("research/deployed_bt_oos_rows_run5.json") + L("research/expansion2/oos_rows.json") + L("research/pruned8_oos_rows.json")
def dedup(rows):
    seen, out = set(), []
    for r in rows:
        k = (r["book"], r["sym"], r["day"])
        if k not in seen: seen.add(k); out.append(r)
    return out
IS, OOS = dedup(IS), dedup(OOS)
names = sorted({r["sym"] for r in IS + OOS})
side = {}
for s in names:
    try: u = fetch_upstox_historical(s + ".NS", unit="days", interval=1, from_date="2018-11-01", to_date=None)
    except Exception: u = None
    if u is None or u.empty: continue
    for d, c, typ, d10 in H.breakout_days(u.sort_index()): side[(s, d)] = "BC" if typ == "CE" else "BP"
for r in IS + OOS: r["side"] = side.get((r["sym"], r["day"]))
miss = sum(1 for r in IS + OOS if not r["side"]); print(f"rows {len(IS)} IS / {len(OOS)} OOS · side unresolved {miss}")
def st(v):
    if not v: return None
    return dict(n=len(v), win=sum(r["win"] for r in v) / len(v), rom=sum(r["net"] for r in v) / sum(r["margin"] for r in v), net=sum(r["net_rs"] for r in v))
cell = {w: collections.defaultdict(list) for w in ("is", "oos")}
for w, rows in (("is", IS), ("oos", OOS)):
    for r in rows:
        if r["side"]: cell[w][(r["sym"], r["side"])].append(r)
good = lambda s: s and s["n"] >= 3 and s["win"] >= 0.80 and s["rom"] > 0.05
MO = 23
grp = lambda s: "universe" if s in U else "pruned-8" if s in P8 else "outsider" if s in OUTS else "other"
res = []
for k in sorted(set(cell["is"]) | set(cell["oos"])):
    a, b = st(cell["is"].get(k)), st(cell["oos"].get(k))
    res.append(dict(sym=k[0], side=k[1], group=grp(k[0]), is_=a, oos=b, both=bool(good(a) and good(b)), is_only_pick=bool(good(a))))
def pool(sel, w):
    v = [r for x in sel for r in cell[w].get((x["sym"], x["side"]), [])]
    s = st(v); return s
def line(lbl, sel):
    a, b = pool(sel, "is"), pool(sel, "oos")
    f = lambda s: f"{s['n']:4d} tr · {100*s['win']:5.1f}% · ROM {100*s['rom']:+5.1f}% · ₹{s['net']:>10,.0f}" if s else "—"
    print(f"{lbl:58s} IS {f(a)} | OOS {f(b)}" + (f" · {b['n']/MO:.1f}/mo · ₹{b['net']/MO:,.0f}/mo" if b else ""))
print("\n== baselines ==")
line("current universe, both sides, as deployed", [x for x in res if x["group"] == "universe"])
line("all 208, both sides", res)
print("\n== YOUR RULE: sides passing >=80% win and ROM > +5% on >=3 trades in BOTH windows ==")
both = [x for x in res if x["both"]]
for g in ("universe", "outsider", "pruned-8"):
    line(f"  passing sides · {g} ({sum(1 for x in both if x['group']==g)} name-sides)", [x for x in both if x["group"] == g])
line(f"  passing sides · ALL ({len(both)} name-sides)", both)
print("\n== HONEST TEST: pick sides on IN-SAMPLE only, then look at their OUT-OF-SAMPLE ==")
pick = [x for x in res if x["is_only_pick"]]
line(f"  IS-picked sides ({len(pick)})", pick)
line(f"  IS-picked sides NOT in the universe today ({sum(1 for x in pick if x['group']!='universe')})", [x for x in pick if x["group"] != "universe"])
line(f"  sides NOT picked by IS ({sum(1 for x in res if not x['is_only_pick'])})", [x for x in res if not x["is_only_pick"]])
json.dump([{**{k: v for k, v in x.items() if k not in ('is_', 'oos')}, "is": x["is_"], "oos": x["oos"]} for x in res], open("research/side_screen_208.json", "w"))
print(f"\npassing both windows, not in the universe today: {sorted((x['sym'], x['side']) for x in both if x['group']!='universe')}")
