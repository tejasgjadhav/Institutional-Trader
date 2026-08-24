"""Regression tests for the harness of record. Runs in seconds, touches no network.

WHY THIS EXISTS. Between 14-Aug and 21-Aug 2026 this repo found nine defects in its own backtest
code: legs joined by position, a corporate-action scale error, an ungated exit walk, a phantom stop,
open interest leaking between books, a fetch failure indistinguishable from an untraded contract, a
missing __main__ guard, a non-atomic cache write, and a shared cache with two incompatible formats.
Every one printed a plausible number instead of crashing, so each was found only by the NEXT audit.

The user's objection on 21-Aug was the correct one: the measurement was never done once, it was
COPIED five times, and each copy inherited its parent's bugs. This file is the answer. It locks the
behaviour that took a week to establish, so a future edit that changes the answer fails loudly here
instead of quietly publishing a new number.

Run:  .venv/bin/python studies/ndte/test_harness.py
"""
import sys, json, os
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
sys.argv = ["test_harness", "OOS"]          # importing must NOT start a backtest
import importlib.util

# HARNESS_PATH lets this suite run against a MUTATED copy, which is how the tests themselves are
# verified: reintroduce a fixed bug, confirm the suite goes red. A test that cannot fail is decoration.
_spec = importlib.util.spec_from_file_location(
    "dbt", os.environ.get("HARNESS_PATH",
                          os.path.join(os.path.dirname(__file__), "deployed_backtest.py")))
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)                  # the __main__ guard makes this safe

FAILED = []
def check(name, got, want):
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"   got {got!r}, want {want!r}"))
    if not ok: FAILED.append(name)

# A 15-strike ladder so BOTH geometries sit on it: v1 sells atm+1 width 3, v2/v0 sell atm+2 width 4.
KS = [float(x) for x in range(900, 1200, 20)]
ATM = 5
H.LOTMAP["TEST"] = 100

def run(px, d10=True, open_until=None, exp="2026-02-26", cb=None):
    rows = []
    fired, exits = H.eval_books("2026-01-05", "TEST", "CE", KS, ATM, px, cb or {exp: 1000.0},
                                exp, 1000.0, d10, rows, open_until or {})
    return rows, fired, exits

# price sets: (se, le) -> credit. v1 width 60, v2/v0 width 80.
V1_FIRES = (60.0, 20.0)     # credit 40 / 60 = 0.667  -> v1 band
V2_FIRES = (60.0, 20.0)     # credit 40 / 80 = 0.500  -> v2 band
V0_FIRES = (50.0, 20.0)     # credit 30 / 80 = 0.375  -> v0 band only
def maker(v1px, v2px, walk=(), oi1=(777.0, 777.0), oi2=(222.0, 222.0)):
    def px(si, li):
        return (v1px[0], v1px[1], list(walk), oi1) if si == ATM + 1 else \
               (v2px[0], v2px[1], list(walk), oi2)
    return px

print("=== live hierarchy ===")
r,_,_ = run(maker(V1_FIRES, V2_FIRES))
check("v1 defers to v2 on the same day", sorted(x["book"] for x in r), ["v2"])
r,_,_ = run(maker(V1_FIRES, V0_FIRES))
check("v1 beats v0 on the same stock",   sorted(x["book"] for x in r), ["v1"])
r,_,_ = run(maker(V1_FIRES, V0_FIRES), d10=False)
check("v1 needs a Donchian-10 breakout", sorted(x["book"] for x in r), ["v0"])
r,_,_ = run(maker(V1_FIRES, V2_FIRES), open_until={"v2": "2026-01-31"})
check("v1 stands down while v2 holds it", sorted(x["book"] for x in r), [])

print("=== gates ===")
r,_,_ = run(maker((40.0, 10.0), (40.0, 10.0)))      # se 40 < MIN_PREM 50
check("premium floor rejects se < 50",   len(r), 0)
r,_,_ = run(maker(V1_FIRES, V2_FIRES, oi1=(0.0, 0.0), oi2=(0.0, 0.0)))
check("open-interest floor rejects OI 0", len(r), 0)

print("=== open interest is attributed to the book that sold it (the 20-Aug leak) ===")
r,_,_ = run(maker(V1_FIRES, V0_FIRES))               # v1 wins; v0's px still ran after it
check("v1 records ITS OWN legs' OI", [x["oi_units"] for x in r], [777.0])

print("=== exits ===")
# v2 tp=0.50: credit 40, closes when cost <= 20
r,_,_ = run(maker(V1_FIRES, V2_FIRES, walk=[("2026-01-20", 30.0, 15.0)]))
check("take-profit fires on the walk", [x["day"] for x in r], ["2026-01-05"])
check("TP trade books a win",          [x["win"] for x in r], [1])
# held to expiry, settled off the legs themselves
r,_,_ = run(maker(V1_FIRES, V2_FIRES, walk=[("2026-02-26", 90.0, 10.0)]))
check("expiry settles off its own legs (loss capped by width)", [x["win"] for x in r], [0])

print("=== data-integrity semantics ===")
import engine.expired_options as EO
H.LEGC.clear(); _orig = EO._get_json
EO._get_json = lambda *a, **k: {}
check("leg() returns None on fetch failure", H.leg("K1", "2026-01-01", "2026-02-01"), None)
EO._get_json = lambda *a, **k: {"status": "success", "data": {"candles": []}}
check("leg() returns {} on empty success",   H.leg("K2", "2026-01-01", "2026-02-01"), {})
EO._get_json = _orig

import pandas as pd
cl = [100.0]*30 + [130.0]
u = pd.DataFrame({"Close": cl, "High": cl, "Low": cl},
                 index=pd.to_datetime(pd.date_range("2026-01-01", periods=31)))
check("the final bar can produce a signal",
      str(u.index[-1])[:10] in [d for d,_,_,_ in H.breakout_days(u)], True)

print("=== GOLDEN FILE: in-sample answer is locked ===")
# GOLD updated 24-Aug-2026: the 20-Aug values (v2 217/+27.2) predate three deliberate changes -
# the split-name rupee-scale fix (points now converted at each day's own price scale), the
# universe prune to 114 (the eight removed names' trades left the basis), and rupee reweighting
# that follows from both. Counts moved 217->200 etc. because the pruned names are gone.
GOLD = {"v2": (200, 23.2), "v1": (335, 12.5), "v0": (217, 15.7)}   # median cohort, 24-Aug-2026
try:
    rows = json.load(open("research/deployed_bt_is_rows.json"))
    for bk, (n_want, rom_want) in GOLD.items():
        lo, hi = (0.35, 0.40) if bk == "v0" else (0.40, 0.50)
        g = [x for x in rows if x["book"] == bk and lo <= x["cw"] < hi]
        mrs = sum(x["margin_rs"] for x in g)
        rom = round(sum(x["net_rs"] for x in g) / mrs * 100, 1) if mrs else 0.0
        check(f"IS {bk}: n", len(g), n_want)
        check(f"IS {bk}: ROM-Rs", rom, rom_want)
except FileNotFoundError:
    print("  SKIP  research/deployed_bt_is_rows.json not present")

print()
if FAILED:
    print(f"{len(FAILED)} FAILED: {FAILED}"); sys.exit(1)
print("all checks passed")
