"""LOW-C/W RESCUE — live liquidity probe for the width-1 re-cut.

The backtest gates on OI >= 1 and models cost as a function of premium. The live engine gates on
a real two-sided market (STOCK_CREDIT_MAX_SPREAD_PCT = 6, STOCK_CREDIT_MIN_OI = 100). A width-1
spread buys its wing one strike from the short instead of four, so the question the backtest
cannot answer is whether that adjacent strike actually trades.

This re-prices TODAY's blocked watchlist names at width 1 against live Upstox quotes and reports,
per name: credit/width at width 4 (what blocked it) vs width 1, plus the long leg's bid-ask and OI.

Read-only. Touches no book, no config, writes nothing the engine reads.
"""
import sys, json
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from datetime import date, datetime, timedelta
from engine.stock_credit_v2 import _quote, _spot
from engine.instruments import to_instrument_key
from engine.options import _load_index
from engine.config import (STOCK_CREDIT_MIN_DTE, STOCK_CREDIT_MIN_CW, STOCK_CREDIT_MIN_PREM,
                           STOCK_CREDIT_MAX_SPREAD_PCT, STOCK_CREDIT_MIN_OI)

WL = "/Users/sayali/files/institutional-trader/data/union_watchlist.json"

def chain_for(ticker, opt_type):
    uk = to_instrument_key(ticker)
    if not uk: return None
    contracts = [c for c in _load_index().get(uk, []) if c["type"] == opt_type]
    if not contracts: return None
    min_day = date.today() + timedelta(days=STOCK_CREDIT_MIN_DTE)
    min_ms = int(datetime(min_day.year, min_day.month, min_day.day).timestamp() * 1000)
    future = sorted({c["expiry"] for c in contracts if c["expiry"] >= min_ms})
    if not future: return None
    exp = future[0]
    return sorted([c for c in contracts if c["expiry"] == exp], key=lambda c: c["strike"])

def price(chain, si, li):
    s, l = chain[si], chain[li]
    sm, sb, sa, soi = _quote(s["key"]); lm, lb, la, loi = _quote(l["key"])
    if sm is None or lm is None: return None
    w = abs(s["strike"] - l["strike"]); credit = sm - lm
    if w <= 0 or credit <= 0: return None
    return dict(sk=s["strike"], lk=l["strike"], w=w, credit=credit, cw=credit / w,
                sprem=sm, s_spr=(sa - sb) / sm * 100 if sm and sa > 0 and sb > 0 else None,
                l_spr=(la - lb) / lm * 100 if lm and la > 0 and lb > 0 else None,
                s_oi=soi or 0, l_oi=loi or 0, lot=int(s.get("lot", 0) or 0))

wl = json.load(open(WL))
print(f"watchlist built {wl['ts']} · {wl['breakouts']} breakouts · {wl['passed']} passed\n")
print(f"live gates: c/w>={STOCK_CREDIT_MIN_CW}  prem>=Rs{STOCK_CREDIT_MIN_PREM}  "
      f"spread<={STOCK_CREDIT_MAX_SPREAD_PCT}%  OI>={STOCK_CREDIT_MIN_OI}\n")
print(f"{'sym':<12} {'side':<10} {'--- width 4 (deployed) ---':<28} {'--- width 1 (candidate) ---':<40}")
print(f"{'':<12} {'':<10} {'c/w':>6} {'width':>7} {'gate':>8}   {'c/w':>6} {'width':>7} {'longOI':>8} {'longSpr':>8} {'gate':>8}")

rescued = blocked = noquote = 0
for r in wl.get("rows", []):
    sym = r["sym"]; opt = "CE" if r["dir"] == "LONG" else "PE"
    tk = sym + ".NS"
    ch = chain_for(tk, opt); sp = _spot(tk)
    if not ch or not sp:
        print(f"{sym:<12} {r['side']:<10}  no chain/spot"); noquote += 1; continue
    strikes = [c["strike"] for c in ch]
    atm = min(range(len(strikes)), key=lambda i: abs(strikes[i] - sp))
    def idx(S, W):
        si, li = (atm + S, atm + S + W) if opt == "CE" else (atm - S, atm - S - W)
        return (si, li) if 0 <= si < len(ch) and 0 <= li < len(ch) else None
    i4, i1 = idx(2, 4), idx(2, 1)
    p4 = price(ch, *i4) if i4 else None
    p1 = price(ch, *i1) if i1 else None
    if not p4 or not p1:
        print(f"{sym:<12} {r['side']:<10}  no quote"); noquote += 1; continue
    g4 = "PASS" if p4["cw"] >= STOCK_CREDIT_MIN_CW else "BLOCK"
    ok1 = (p1["cw"] >= STOCK_CREDIT_MIN_CW and p1["sprem"] >= STOCK_CREDIT_MIN_PREM
           and (p1["l_spr"] is None or p1["l_spr"] <= STOCK_CREDIT_MAX_SPREAD_PCT)
           and p1["l_oi"] >= STOCK_CREDIT_MIN_OI)
    g1 = "PASS" if ok1 else "BLOCK"
    if g4 == "BLOCK" and g1 == "PASS": rescued += 1
    elif g4 == "BLOCK": blocked += 1
    ls = f"{p1['l_spr']:.1f}%" if p1["l_spr"] is not None else "n/a"
    print(f"{sym:<12} {r['side']:<10} {p4['cw']:>6.2f} {p4['w']:>7.0f} {g4:>8}   "
          f"{p1['cw']:>6.2f} {p1['w']:>7.0f} {p1['l_oi']:>8.0f} {ls:>8} {g1:>8}")

print(f"\nblocked at width 4 and RESCUED by width 1: {rescued}")
print(f"blocked at both: {blocked}   ·   unquotable: {noquote}")
print("\nNOTE: run during market hours for true two-sided spreads; after the close bid/ask can be stale.")
print("DONE-LIVELIQ")
