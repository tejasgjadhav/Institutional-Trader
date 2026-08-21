"""The FORWARD PAPER RECORD — the only genuinely out-of-sample instrument this system has.

WHY THIS FILE. On 21-Aug-2026 the user asked why the measurement kept being re-run instead of done
once. Part of the answer is that the backtest was copied rather than fixed. The other part is that
the forward record had almost nothing in it, so the backtest was the only thing with data.

That is a fact worth showing rather than remembering. Every live trade entered BEFORE the 6-Aug-2026
stale-bar fix was fired off the PREVIOUS session's breakout - a T-1 signal, a different strategy that
no backtest describes. Pooling those with the real ones flatters the record and answers the wrong
question. This script splits them and reports only what the deployed strategy has actually done.

Run:  .venv/bin/python studies/ndte/forward_record.py
"""
import json, os, sys, collections
from datetime import date

sys.path.insert(0, "/Users/sayali/files/institutional-trader")
ROOT = "/Users/sayali/files/institutional-trader"
FIX = "2026-08-06"          # the stale-bar fix; entries before this are T-1 signals
BOOKS = [("v2", "stock_credit_v2_positions.json"),
         ("v1", "stock_credit_positions.json"),
         ("v0", "stock_credit_v0_positions.json")]

def pnl(p):
    v = p.get("pnl_rs")
    if v is None:
        v = (p.get("pnl_pts") or 0) * (p.get("qty") or p.get("lot") or 0)
    return float(v)

era = {"pre": collections.defaultdict(list), "post": collections.defaultdict(list)}
openp = collections.defaultdict(list)
for bk, fn in BOOKS:
    path = os.path.join(ROOT, "data", fn)
    if not os.path.exists(path):
        continue
    for p in json.load(open(path)):
        if p.get("status") == "OPEN":
            openp[bk].append(p); continue
        era["post" if (p.get("entry_date") or "") >= FIX else "pre"][bk].append(p)

def block(title, d, note):
    print(f"\n=== {title} ===")
    print(f"{note}\n")
    print(f"{'book':<5}{'closed':>8}{'win':>7}{'net Rs':>12}{'best':>10}{'worst':>10}")
    tot = n = w = 0.0, 0, 0
    T = [0.0, 0, 0]
    for bk, _ in BOOKS:
        g = d.get(bk, [])
        if not g:
            print(f"{bk:<5}{0:>8}{'-':>7}{'-':>12}"); continue
        v = [pnl(p) for p in g]
        T[0] += sum(v); T[1] += len(v); T[2] += sum(1 for x in v if x > 0)
        print(f"{bk:<5}{len(v):>8}{sum(1 for x in v if x>0)/len(v)*100:>6.0f}%"
              f"{sum(v):>+12,.0f}{max(v):>+10,.0f}{min(v):>+10,.0f}")
    if T[1]:
        print(f"{'ALL':<5}{T[1]:>8}{T[2]/T[1]*100:>6.0f}%{T[0]:>+12,.0f}")
    return T

print("FORWARD PAPER RECORD  ·  generated", date.today().isoformat())
post = block("THE DEPLOYED STRATEGY", era["post"],
             f"Entered on or after {FIX}. This is the ONLY record that tests what is deployed.")
pre = block("BEFORE THE STALE-BAR FIX — NOT THIS STRATEGY", era["pre"],
            "Entered before " + FIX + ", off the PREVIOUS session's breakout (T-1 signals).\n"
            "No backtest describes this. Shown for completeness; never pool it with the block above.")

print("\n=== STILL OPEN ===")
for bk, _ in BOOKS:
    for p in openp.get(bk, []):
        print(f"  {bk:<3} {p.get('symbol','?'):<12} entry {p.get('entry_date')}  "
              f"credit {p.get('credit')}  now {p.get('current_cost')}  "
              f"pnl_pts {p.get('pnl_pts')}  stop_cost={p.get('stop_cost')}")

n = post[1]
print(f"\nVERDICT: the deployed strategy has {n} closed trade(s).")
if n < 30:
    print(f"That is far too few to conclude anything. At roughly 8 v1 signals a month, a sample")
    print(f"worth trusting is months away. Until then the backtest is the best available estimate")
    print(f"and its ceiling is about 8/10 — no further sweep raises that.")
