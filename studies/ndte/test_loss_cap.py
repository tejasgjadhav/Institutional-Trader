"""Offline test of the 0DTE loss cap (16-Oct-2026) on both books. No network: quotes, book files and
Telegram are replaced. Checks: under the cap stays open; at the cap closes as LOSS with exit_reason and
one EXIT alert; cap 0 disables it; the take-profit still wins first."""
import sys, os
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import engine.notifications as N
import engine.zero_dte as Z
import engine.dte_multi as D

FAILED = []
SENT = []
N.send_telegram = lambda msg, *a, **k: SENT.append(msg) or True
TODAY = date.today().isoformat()


def check(name, got, want):
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"   got {got!r}, want {want!r}"))
    if not ok:
        FAILED.append(name)


def pos(credit=73.8, lot=20, sym="SENSEX", side="BEAR_CALL"):
    return {"id": f"T-{sym}", "symbol": sym, "side": side, "status": "OPEN", "expiry": "2099-01-01",
            "entry_date": TODAY, "short_key": "S", "long_key": "L", "short_strike": 73400, "long_strike": 74000,
            "width_pts": 600, "lot": lot, "num_lots": 1, "qty": lot, "credit": credit, "short_prem": 88.35}


def run_sensex(cost, cap=5000.0):
    D.ZERO_DTE_LOSS_CAP_RS = cap
    store = {"b": [pos()]}
    D._load_json = lambda path, default=None: store["b"]
    D._save_json = lambda path, obj: store.update(b=obj)
    D._quote = lambda k: cost + 10.0 if k == "S" else 10.0
    SENT.clear()
    n = D._resolve_book({"book": "x", "name": "SENSEX"}, past_settle=False)
    return n, store["b"][0], list(SENT)


def run_nifty(cost, cap=5000.0):
    Z.ZERO_DTE_LOSS_CAP_RS = cap
    store = {"b": [pos(credit=19.5, lot=65, sym="NIFTY")]}
    Z._load_book = lambda: store["b"]
    Z._save_book = lambda b: store.update(b=b)
    Z._quote = lambda k: cost + 5.0 if k == "S" else 5.0
    Z.ZERO_DTE_ENABLED = True
    SENT.clear()
    n = Z.resolve_positions()
    return n, store["b"][0], list(SENT)


print("SENSEX book (lot 20, credit 73.8 -> cap at a spread cost of 323.8)")
n, p, s = run_sensex(300.0)
check("loss Rs4,524 stays open", p["status"], "OPEN")
check("no alert under the cap", len(s), 0)
n, p, s = run_sensex(330.0)
check("loss Rs5,124 closes", (n, p["status"], p.get("exit_reason")), (1, "LOSS", "loss_cap"))
check("exit cost recorded", p.get("exit_cost"), 330.0)
check("one EXIT alert", len(s), 1)
check("alert names the buy-back", "BUY BACK 73400 CE / SELL 74000 CE" in (s[0] if s else ""), True)
n, p, s = run_sensex(330.0, cap=0.0)
check("cap 0 disables it", p["status"], "OPEN")
D.ZERO_DTE_EARLY_CLOSE_FRAC = 0.95
n, p, s = run_sensex(2.0)
D.ZERO_DTE_EARLY_CLOSE_FRAC = 0.0
check("take-profit still wins first when switched on", (p["status"], p.get("exit_reason")), ("WIN", None))

n, p, s = run_sensex(2.0)
check("early close off (16-Oct): a cheap spread stays open to settle", p["status"], "OPEN")

print("NIFTY book (lot 65, credit 19.5 -> cap at a spread cost of 96.4)")
n, p, s = run_nifty(90.0)
check("loss Rs4,583 stays open", p["status"], "OPEN")
n, p, s = run_nifty(100.0)
check("loss Rs5,233 closes", (p["status"], p.get("exit_reason")), ("LOSS", "loss_cap"))
check("one EXIT alert", len(s), 1)

print(f"\n{'ALL PASS' if not FAILED else f'{len(FAILED)} FAILED: {FAILED}'}")
sys.exit(1 if FAILED else 0)
