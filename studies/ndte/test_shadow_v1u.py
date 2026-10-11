"""Offline test of the shadow v1u book (11-Oct-2026): it opens paper positions only on union-not-D10
days, writes only its own file, never touches the forward record or live books, skips names a live
book holds, and does nothing when disabled. No network."""
import sys, os, json, shutil, tempfile
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import engine.config as C
import engine.data_utils as DU
import engine.forward_record as FR
import engine.stock_credit_v2 as V2
import engine.shadow_v1u as SH
I = SH._impl
TODAY = date.today()
FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"   got {got!r}, want {want!r}"))
    if not ok:
        FAILED.append(name)


DU.market_is_trading_today = lambda: True
DU.recent_entry_symbols = lambda gap_days=None: frozenset()
calls = []
FR.record_entry = lambda *a, **k: calls.append(a)
REAL_RECORD = FR.record_entry

D10 = {"D10NAME"}                      # live v1 territory
UNION = {"UOK": "LONG", "D10NAME": "LONG", "HELD": "SHORT", "NOBK": None}
SH._d10_breakout = lambda t: "LONG" if t.replace(".NS", "") in D10 else None
V2._todays_breakout = lambda t: ((UNION[t.replace(".NS", "")], 15, 1000.0, "intraday")
                                 if UNION.get(t.replace(".NS", "")) else None)
I._spot = lambda t: 1000.0
def pick(t, spot, opt):
    sym = t.replace(".NS", ""); k0 = 1000.0; k1 = k0 + 30 if opt == "CE" else k0 - 30
    return ({"key": f"{sym}|S", "strike": k0, "lot": 100}, {"key": f"{sym}|L", "strike": k1, "lot": 100},
            (TODAY + timedelta(days=20)).isoformat())
I._pick_legs = pick
I._quote = lambda key: (60.0, 59.5, 60.5, 500) if key.endswith("|S") else (45.0, 44.5, 45.5, 500)  # c/w 0.50
I._save_snapshot = lambda: None
I.STOCK_CREDIT_ENABLED = True

d = tempfile.mkdtemp(prefix="shadowtest_")
SH.DATA_DIR = I.DATA_DIR = d
I.BOOK_PATH = os.path.join(d, "shadow_v1u_positions.json")
live = {"stock_credit_positions.json": [{"symbol": "HELD", "status": "OPEN", "entry_date": "2026-09-01"}],
        "stock_credit_v2_positions.json": [], "stock_credit_v0_positions.json": [],
        "stock_credit_vlc_positions.json": []}
for f, rows in live.items():
    json.dump(rows, open(os.path.join(d, f), "w"))
before = {f: open(os.path.join(d, f), "rb").read() for f in live}
C.UNIVERSE = ["UOK.NS", "D10NAME.NS", "HELD.NS", "NOBK.NS"]

C.SHADOW_V1U_ENABLED = True
new = SH.scan()
check("opens only the union-not-D10 name", sorted(p["symbol"] for p in new), ["UOK"])
check("shadow file holds it", [p["symbol"] for p in json.load(open(I.BOOK_PATH))], ["UOK"])
check("forward record never written", calls, [])
check("forward record function restored", FR.record_entry is REAL_RECORD, True)
check("live book files byte-identical", {f: open(os.path.join(d, f), "rb").read() for f in live}, before)
check("summary reports 1 open", SH.summary()["open"], 1)

C.SHADOW_V1U_ENABLED = False
os.remove(I.BOOK_PATH)
check("disabled: scan returns nothing", SH.scan(), [])
check("disabled: no file written", os.path.exists(I.BOOK_PATH), False)
check("disabled: resolve is a no-op", SH.resolve(), 0)
C.SHADOW_V1U_ENABLED = True

I.scan_signals = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
check("a raising scan is swallowed", SH.scan(), [])
check("forward record restored after a raise", FR.record_entry is REAL_RECORD, True)
shutil.rmtree(d, ignore_errors=True)
print(f"\n{'ALL PASS' if not FAILED else f'{len(FAILED)} FAILED: {FAILED}'}")
sys.exit(1 if FAILED else 0)
