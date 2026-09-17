"""Before/after for run 4 vs run 3, per book: n / win / ROM / Rs, median cohort, and exactly
which (sym, day) rows the run-4 guards removed or added. Usage: run4_compare.py IS|OOS"""
import sys, json, collections
win = (sys.argv[1] if len(sys.argv) > 1 else "IS").lower()
r3 = json.load(open(f"research/deployed_bt_{win}_rows.json"))
r4 = json.load(open(f"research/run4_{win}_rows.json"))
def st(g):
    n = len(g); w = 100*sum(x["win"] for x in g)/n if n else 0
    rom = 100*sum(x["net"] for x in g)/sum(x["margin"] for x in g) if n else 0
    return n, w, rom, sum(x["net_rs"] for x in g)
print(f"=== RUN 3 -> RUN 4 · {win.upper()} ===")
print(f"{'book':<5}{'run3 n/win/ROM/Rs':>34}   {'run4 n/win/ROM/Rs':>34}   removed  added")
for bk in ("v2", "v1", "v0"):
    a = [x for x in r3 if x["book"] == bk]; b = [x for x in r4 if x["book"] == bk]
    ka = {(x["sym"], x["day"]) for x in a}; kb = {(x["sym"], x["day"]) for x in b}
    n3, w3, m3, s3 = st(a); n4, w4, m4, s4 = st(b)
    print(f"{bk:<5}{n3:>6}/{w3:5.1f}%/{m3:6.1f}%/{s3:+11,.0f}   {n4:>6}/{w4:5.1f}%/{m4:6.1f}%/{s4:+11,.0f}   {len(ka-kb):>7}  {len(kb-ka):>5}")
    rem = [x for x in a if (x["sym"], x["day"]) not in kb]
    if rem:
        n, w, rom, rs = st(rem)
        print(f"      removed rows: {n} @ win {w:.1f}% ROM {rom:.1f}% Rs{rs:+,.0f}  e.g. " +
              ", ".join(f"{x['sym']} {x['day']}" for x in rem[:5]))
print("\nmedian cohort (0.40-0.50):")
for bk in ("v2", "v1", "v0"):
    a = [x for x in r3 if x["book"] == bk and 0.40 <= x["cw"] < 0.50]
    b = [x for x in r4 if x["book"] == bk and 0.40 <= x["cw"] < 0.50]
    n3, w3, m3, _ = st(a); n4, w4, m4, _ = st(b)
    print(f"  {bk}: run3 {n3}/{w3:.1f}%/{m3:.1f}%  ->  run4 {n4}/{w4:.1f}%/{m4:.1f}%")
