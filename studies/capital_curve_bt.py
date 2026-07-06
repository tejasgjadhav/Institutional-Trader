"""
Capital-curve backtest for the VALIDATED index fade credit spread (swing_credit logic),
replayed on real expired-option premiums. Answers the question the per-trade studies never did:
**what monthly return on a FIXED capital base, and what max drawdown?**

Objective spec: studies/OBJECTIVE_SPEC.md
  - capital base sensitivity: Rs1L / 2L / 3L
  - 1 lot/spread, NIFTY+FINNIFTY, hold-to-expiry, 2x-credit stop, Donchian-10 fade, mid tenor >=10 DTE
  - report: monthly return on capital, MAX DRAWDOWN (vs 15% cap), win rate, worst month, gap to 5%/mo

NOT a re-optimization. Config is frozen at the deployed swing_credit values. We only translate the
already-validated per-trade edge into an equity curve on a real capital base.

Run:  .venv/bin/python -m studies.capital_curve_bt
"""
import sys
from datetime import date, timedelta
import pandas as pd

from engine.data_fetcher import fetch_upstox_historical
from engine import expired_options as eo

# ── frozen deployed config (engine/config.py SWING_*) ────────────────────────
DONCHIAN   = 10
MIN_DTE    = 10
SHORT_OFF  = 1
WIDTH      = 3        # strike steps
STOP_MULT  = 2.0
REENTRY_GAP= 3        # days between entries on same index
INDICES    = ["NIFTY", "FINNIFTY"]
START      = "2024-11-15"   # leave Donchian warmup before this
END        = "2026-06-18"
CAP_BASES  = [100_000, 200_000, 300_000]
DD_CAP_PCT = 15.0
TARGET_MO  = 5.0

_dcache = {}   # key -> {date_iso: close}  daily premium cache


def daily_underlying(index):
    df = fetch_upstox_historical(index, unit="days", interval=1,
                                 from_date="2024-10-01", to_date=END)
    if df is None or df.empty:
        return None
    return df.sort_index()


def leg_daily_series(key, frm_iso, to_iso):
    """Daily premium closes for an expired option leg over [frm, to]. One API call. Returns
    {date_iso: close}. Cached per key+window."""
    ck = (key, frm_iso, to_iso)
    if ck in _dcache:
        return _dcache[ck]
    url = (f"{eo.UPSTOX_BASE}/v2/expired-instruments/historical-candle/"
           f"{eo.encode_key(key)}/day/{to_iso}/{frm_iso}")
    j = eo._get_json(url)
    out = {}
    if j.get("status") == "success":
        for c in j.get("data", {}).get("candles", []) or []:
            # [ts, o, h, l, close, vol, oi]
            out[str(pd.to_datetime(c[0]).date())] = float(c[4])
    _dcache[ck] = out
    return out


def pick_legs(index, spot, d, opt_type):
    """Nearest expiry >= d+MIN_DTE, short SHORT_OFF OTM, long +WIDTH further OTM."""
    exps = [e for e in eo.get_expiries(index)
            if date.fromisoformat(e) >= d + timedelta(days=MIN_DTE)]
    if not exps:
        return None
    exp = exps[0]
    chain = [c for c in eo.get_contracts(index, exp) if c.get("instrument_type") == opt_type]
    if not chain:
        return None
    chain = sorted(chain, key=lambda c: float(c.get("strike_price", 0)))
    strikes = [float(c.get("strike_price", 0)) for c in chain]
    atm = min(range(len(strikes)), key=lambda j: abs(strikes[j] - spot))
    if opt_type == "CE":
        si, li = atm + SHORT_OFF, atm + SHORT_OFF + WIDTH
    else:
        si, li = atm - SHORT_OFF, atm - SHORT_OFF - WIDTH
    if si < 0 or li < 0 or si >= len(chain) or li >= len(chain):
        return None
    s, l = chain[si], chain[li]
    lot = int(s.get("lot_size") or l.get("lot_size") or 0)
    if lot <= 0:
        return None
    return dict(short_key=s["instrument_key"], short_strike=float(s["strike_price"]),
                long_key=l["instrument_key"], long_strike=float(l["strike_price"]),
                expiry=exp, lot=lot, width=abs(float(s["strike_price"]) - float(l["strike_price"])))


def replay_index(index, udf):
    """Walk the daily underlying; on each fresh Donchian breakout open one fade spread, hold to
    stop or expiry. One open position per index at a time + re-entry gap. Returns list of trades."""
    udf = udf.copy()
    udf["pri_hi"] = udf["High"].rolling(DONCHIAN).max().shift(1)
    udf["pri_lo"] = udf["Low"].rolling(DONCHIAN).min().shift(1)
    dates = [ts.date() for ts in udf.index]
    closes = list(udf["Close"]); his = list(udf["pri_hi"]); los = list(udf["pri_lo"])
    trades = []
    block_until = None
    for i, d in enumerate(dates):
        if str(d) < START or pd.isna(his[i]):
            continue
        if block_until and d < block_until:
            continue
        c = closes[i]
        bdir = "LONG" if c > his[i] else ("SHORT" if c < los[i] else None)
        if not bdir:
            continue
        opt_type = "CE" if bdir == "LONG" else "PE"   # FADE
        legs = pick_legs(index, c, d, opt_type)
        if not legs:
            continue
        exp = date.fromisoformat(legs["expiry"])
        sser = leg_daily_series(legs["short_key"], d.isoformat(), exp.isoformat())
        lser = leg_daily_series(legs["long_key"], d.isoformat(), exp.isoformat())
        sp, lp = sser.get(str(d)), lser.get(str(d))
        if sp is None or lp is None:
            continue
        credit = round(sp - lp, 2)
        if credit <= 0:
            continue
        stop_cost = credit * STOP_MULT
        # hold: walk trading days from entry to expiry
        hold_dates = [dd for dd in dates if d < dd <= exp]
        status, exit_cost, close_d = None, None, None
        for dd in hold_dates:
            sc, lc = sser.get(str(dd)), lser.get(str(dd))
            if dd >= exp:   # settle at intrinsic on the underlying
                spot_exp = closes[dates.index(dd)]
                if opt_type == "CE":
                    intr = max(0.0, spot_exp - legs["short_strike"])
                else:
                    intr = max(0.0, legs["short_strike"] - spot_exp)
                exit_cost = min(intr, legs["width"]); close_d = dd
                status = "WIN" if credit - exit_cost > 0 else "LOSS"
                break
            if sc is None or lc is None:
                continue
            cost = sc - lc
            if cost >= stop_cost:
                exit_cost = min(cost, legs["width"]); close_d = dd
                status = "LOSS"
                break
        if status is None:   # no data to expiry -> settle intrinsic at expiry close
            spot_exp = closes[dates.index(exp)] if exp in dates else c
            intr = (max(0.0, spot_exp - legs["short_strike"]) if opt_type == "CE"
                    else max(0.0, legs["short_strike"] - spot_exp))
            exit_cost = min(intr, legs["width"]); close_d = exp
            status = "WIN" if credit - exit_cost > 0 else "LOSS"
        pnl_pts = round(credit - exit_cost, 2)
        margin = (legs["width"] - credit) * legs["lot"]   # defined-risk capital at stake (Rs)
        trades.append(dict(index=index, entry=d, close=close_d, dir=bdir, status=status,
                           credit=credit, exit_cost=round(exit_cost, 2), width=legs["width"],
                           lot=legs["lot"], pnl_pts=pnl_pts, pnl_rs=round(pnl_pts * legs["lot"], 0),
                           margin=round(margin, 0), expiry=legs["expiry"]))
        block_until = close_d + timedelta(days=REENTRY_GAP)
        print(f"  {index} {d} {bdir:5} {status:4} credit {credit:6.1f} "
              f"exit {exit_cost:6.1f} pnl Rs{pnl_pts*legs['lot']:+8.0f} (margin {margin:.0f})",
              file=sys.stderr)
    return trades


def equity_stats(trades, cap_base):
    """Sequential equity curve on a fixed base (1 lot, positions effectively non-overlapping per
    index; both indices share the base). Returns monthly-return + drawdown stats."""
    if not trades:
        return None
    tr = sorted(trades, key=lambda t: t["close"])
    eq = cap_base
    peak = cap_base
    max_dd = 0.0
    curve = []
    for t in tr:
        eq += t["pnl_rs"]
        peak = max(peak, eq)
        dd = (peak - eq) / cap_base * 100
        max_dd = max(max_dd, dd)
        curve.append((t["close"], eq))
    net = eq - cap_base
    months = (tr[-1]["close"] - tr[0]["entry"]).days / 30.4375
    months = max(months, 1.0)
    # monthly P&L buckets
    mon = {}
    for t in tr:
        k = f"{t['close'].year}-{t['close'].month:02d}"
        mon[k] = mon.get(k, 0) + t["pnl_rs"]
    monthly_pct = [v / cap_base * 100 for v in mon.values()]
    wins = sum(1 for t in tr if t["status"] == "WIN")
    gp = sum(t["pnl_rs"] for t in tr if t["pnl_rs"] > 0)
    gl = -sum(t["pnl_rs"] for t in tr if t["pnl_rs"] < 0)
    return dict(
        n=len(tr), wins=wins, win_rate=wins / len(tr) * 100,
        pf=(gp / gl if gl else float("inf")),
        net_rs=net, months=months,
        ret_per_mo_pct=net / cap_base * 100 / months,
        max_dd_pct=max_dd,
        worst_month_pct=min(monthly_pct) if monthly_pct else 0,
        best_month_pct=max(monthly_pct) if monthly_pct else 0,
        n_months=len(mon),
        avg_margin=sum(t["margin"] for t in tr) / len(tr),
    )


def main():
    all_trades = []
    for idx in INDICES:
        udf = daily_underlying(idx)
        if udf is None:
            print(f"!! no underlying data for {idx}", file=sys.stderr)
            continue
        print(f"\n=== replay {idx} ===", file=sys.stderr)
        all_trades += replay_index(idx, udf)

    print("\n" + "=" * 70)
    print(f"INDEX FADE CREDIT SPREAD — capital-curve backtest")
    print(f"window {START} -> {END} | NIFTY+FINNIFTY | 1 lot | hold-to-expiry | 2x stop")
    print("=" * 70)
    if not all_trades:
        print("NO TRADES — check API access / window.")
        return
    n = len(all_trades)
    wins = sum(1 for t in all_trades if t["status"] == "WIN")
    net = sum(t["pnl_rs"] for t in all_trades)
    print(f"\ntrades: {n}  |  win rate: {wins/n*100:.1f}%  |  net P&L: Rs{net:,.0f} "
          f"(1 lot, GROSS of bid-ask)")
    print(f"avg margin/trade: Rs{sum(t['margin'] for t in all_trades)/n:,.0f}\n")
    print(f"{'capital':>10} {'ret/mo':>8} {'max DD':>8} {'worst mo':>9} {'best mo':>8} "
          f"{'win%':>6} {'PF':>5}  verdict")
    print("-" * 78)
    for cap in CAP_BASES:
        s = equity_stats(all_trades, cap)
        dd_ok = s["max_dd_pct"] <= DD_CAP_PCT
        tgt_ok = s["ret_per_mo_pct"] >= TARGET_MO
        verdict = ("PASS" if (dd_ok and tgt_ok) else
                   f"{'DD OK' if dd_ok else 'DD BREACH'} / {'5%+' if tgt_ok else 'below 5%'}")
        print(f"{cap:>10,} {s['ret_per_mo_pct']:>7.2f}% {s['max_dd_pct']:>7.1f}% "
              f"{s['worst_month_pct']:>8.1f}% {s['best_month_pct']:>7.1f}% "
              f"{s['win_rate']:>5.1f}% {s['pf']:>5.2f}  {verdict}")
    s = equity_stats(all_trades, CAP_BASES[1])
    print(f"\nspan: {s['n_months']} months, {s['months']:.1f} elapsed | "
          f"~{n/s['months']:.1f} trades/mo")
    print("NOTE: GROSS of bid-ask. Index spreads are India's tightest, but live fills shave more.")
    print("NOTE: defined-risk; the per-trade margin is what's actually at stake, not the full base.")


if __name__ == "__main__":
    main()
