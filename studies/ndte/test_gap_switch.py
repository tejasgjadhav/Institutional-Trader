"""Offline test of the SENSEX gap-up switch (16-Oct-2026). No network: chain, quotes, gap and book are
replaced. Checks: small gap -> bear call as before; gap >= 0.50% -> bull put 1% below with the right
wing; a thin put -> no trade and no fallback; switch off -> call; put settlement intrinsic."""
import sys, os
from datetime import date, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import engine.dte_multi as D

FAILED = []
def check(name, got, want):
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"   got {got!r}, want {want!r}"))
    if not ok:
        FAILED.append(name)

BK = dict(D.BOOKS[0])
SPOT = 74000.0
exp_ms = int(datetime.combine(date.today(), datetime.min.time()).timestamp() * 1000) + 15 * 3600 * 1000
chain = {t: [dict(key=f"{t}{k}", strike=float(k), lot=20, type=t, expiry=exp_ms) for k in range(70000, 78001, 100)] for t in ("CE", "PE")}
D._chain_today = lambda bk, opt_type="CE": chain[opt_type]
D._spot = lambda bk: SPOT
store = {"b": []}
D._load_json = lambda path, default=None: store["b"] if path == BK["book"] else default
D._save_json = lambda path, obj: store.update(b=obj) if path == BK["book"] else None
PR = {}
def quote(key):
    k = float(key[2:]); t = key[:2]
    dist = (k - SPOT) if t == "CE" else (SPOT - k)        # distance out of the money
    return PR.get(key, max(1.0, 200.0 - dist * 0.15))
D._quote = quote
D.SENSEX_GAP_PUT_OTM = 0.01          # fixed geometry for the checks below; live value checked at the end

def scan(gap, switch=0.50):
    D.SENSEX_GAP_SWITCH_PCT = switch
    D._gap_pct = lambda bk: gap
    store["b"] = []
    return D._scan_book(BK)

p = scan(0.20)
check("gap 0.20%: bear call as before", (p[0]["side"], p[0]["short_strike"], p[0]["long_strike"]), ("BEAR_CALL", 74400, 75000))
p = scan(0.60)
check("gap 0.60%: bull put 1% below", (p[0]["side"], p[0]["short_strike"]), ("BULL_PUT", 73300))
check("put wing 0.83% further below, width positive", (p[0]["long_strike"], p[0]["width_pts"]), (72700, 600))
check("tagged as the gap rule", (p[0]["rule"], p[0]["gap_pct"]), ("gap_switch", 0.6))
check("order label says PE", "SELL SENSEX 73300 PE / BUY 72700 PE" in p[0]["order_label"], True)
PR.update({"PE73300": 20.0, "PE72700": 19.5})              # credit 0.5 on 600 -> c/w 0.0008
p = scan(0.60)
check("thin put: no trade, no fallback to the call", p, [])
check("thin put: reason names the gap rule", "gap-up rule" in D.SCAN_TRACE.get("SENSEX", ""), True)
PR.clear()
p = scan(0.60, switch=0.0)
check("switch off: bear call", p[0]["side"], "BEAR_CALL")

# settlement of a bull put
pos = dict(id="T", symbol="SENSEX", side="BULL_PUT", status="OPEN", expiry=date.today().isoformat(),
           entry_date=date.today().isoformat(), short_strike=73300, long_strike=72700, width_pts=600,
           credit=40.0, lot=20, qty=20, short_key="s", long_key="l")
for close, want in ((74000.0, 40.0), (73100.0, -160.0), (72000.0, -560.0)):
    store["b"] = [dict(pos)]
    D._expiry_close = lambda bk, exp, c=close: c
    D._resolve_book(BK, past_settle=True)
    check(f"put settles at close {close:.0f}: pnl {want:+.0f} pts", store["b"][0]["pnl_pts"], want)
import engine.config as C
D.SENSEX_GAP_PUT_OTM = C.SENSEX_GAP_PUT_OTM
p = scan(0.30, switch=C.SENSEX_GAP_SWITCH_PCT)
check(f"LIVE config ({C.SENSEX_GAP_SWITCH_PCT}% gap, put {C.SENSEX_GAP_PUT_OTM:.1%}): gap 0.30% -> put 73600/73000", (p[0]["side"], p[0]["short_strike"], p[0]["long_strike"]), ("BULL_PUT", 73600, 73000))
p = scan(0.20, switch=C.SENSEX_GAP_SWITCH_PCT)
check("LIVE config: gap 0.20% stays a bear call", p[0]["side"], "BEAR_CALL")
print(f"\n{'ALL PASS' if not FAILED else f'{len(FAILED)} FAILED: {FAILED}'}")
sys.exit(1 if FAILED else 0)
