"""ndte34 — raise the 0DTE net % of margin (pre-registered in research/rally_guard/prereg34.json).
Grid: take-profit (95% deployed / 70% / 50% / off) x loss cap (none / 4k / 5k live / 6k / 7k), and on
SENSEX a condor add (sell the put spread too when its own c/w >= 0.08; margin counted once).

Run: .venv/bin/python studies/ndte/ndte34_margin_return.py [--allow-daytime]   (fetches SENSEX put legs)
"""
import os
import sys
import json
import argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ndte30_time_losscut as M          # noqa: E402
import ndte32_loss_cap as P              # noqa: E402

TPS = {"TP95": M.TP_FRAC, "TP70": 0.70, "TP50": 0.50, "TPoff": 0.0}
CAPS = [None, 4000, 5000, 6000, 7000]
MONTHS = {"h1": 12.0, "h2": 12.2}


def run_one(pos, spot, close, tp, cap):
    base = M.simulate(pos, close, tp_frac=tp)
    if cap is None:
        return base["net_rs"]
    hm = P.trigger(("R", cap), pos, spot)
    if hm is None or (base["kind"] == "TP" and base["exit_hm"] <= hm):
        return base["net_rs"]
    a, c = pos["leg_s"].close_at(hm), pos["leg_l"].close_at(hm)
    if a is None or c is None:
        return base["net_rs"]
    lot, credit = pos["lot"], pos["credit"]
    cost0 = (pos["s0"] + pos["l0"]) * M.SLIP_PCT / 100 + M.BROKER * 4 / lot
    net = credit - (a * (1 + M.EXIT_SLIP) - c * (1 - M.EXIT_SLIP)) - cost0 - ((a + c) * M.SLIP_PCT / 100 + M.BROKER * 4 / lot)
    return net * lot


def collect(data, book):
    """[(day, [positions], spot, close)] grouped by expiry day, so a condor's two sides share margin."""
    exps, daily, sdays = M.build_days(data, book, M.START)
    out = []
    for e in exps:
        ctx = M.day_ctx(data, book, e, daily, sdays)
        if ctx["close"] is None or e in M.BLACKOUT:
            continue
        if book["rv5_max"] and ctx["rv5"] is not None and ctx["rv5"] >= book["rv5_max"]:
            continue
        try:
            ctx["chain"] = data.contracts(book, e)
            bars, _ = data.spot_1m(book, e)
            ctx["spot"] = M.Leg(bars)
            pos, _ = M.decide(book, ctx, M.DEPLOYED_ENTRY, book["otm"], lambda k, _e=e: data.candles(k, _e))
        except M.FetchFailed:
            data.f.failures.append((f"{book['name']} {e}", "fetch")); continue
        if pos:
            out.append((e, pos, ctx["spot"], ctx["close"]))
    return out


def margin(pos_list):
    """Max loss of the day's book: one side can lose at expiry, so the larger width minus ALL credit."""
    w = max(p["width"] for p in pos_list)
    lot = pos_list[0]["lot"]
    return (w - sum(p["credit"] for p in pos_list)) * lot


def grid(days, label, log):
    res = {}
    for tpn, tp in TPS.items():
        for cap in CAPS:
            k = f"{tpn} cap {cap or 'none'}"
            rows = []
            for e, pl, spot, close in days:
                net = sum(run_one(p, spot, close, tp, cap) for p in pl)
                rows.append((e, net, margin(pl)))
            st = {}
            for h, sel in (("h1", [r for r in rows if r[0] < P.HALF]), ("h2", [r for r in rows if r[0] >= P.HALF]), ("all", rows)):
                if not sel:
                    continue
                tot = sum(r[1] for r in sel); am = sum(r[2] for r in sel) / len(sel)
                mo = MONTHS.get(h, MONTHS["h1"] + MONTHS["h2"])
                st[h] = dict(n=len(sel), total=round(tot), pm=round(100 * tot / mo / am, 1),
                             win=round(100 * sum(1 for r in sel if r[1] > 0) / len(sel), 1), worst=round(min(r[1] for r in sel)))
            res[k] = st
    log(f"\n{label}: net % of margin a month (H1 | H2 | all), total Rs, worst Rs, win%")
    for k, st in res.items():
        a = st["all"]
        log(f"  {k:18s} {st['h1']['pm']:>6}% | {st['h2']['pm']:>6}% | {a['pm']:>6}%   total {a['total']:>8}  worst {a['worst']:>8}  win {a['win']:>5}")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-daytime", action="store_true")
    ap.add_argument("--cache-only", action="store_true")
    a = ap.parse_args(argv)
    log = lambda s: print(s, flush=True)
    if not a.cache_only and not M.fetch_window_open(M._ist_now(), a.allow_daytime):
        log("REFUSED: outside the fetch window"); return 3
    f = M.Fetcher(allow_daytime=a.allow_daytime, cache_only=a.cache_only, log=log, seed_from_cache=not a.cache_only)
    data = M.Data(f)
    out = {}
    try:
        sx = M.BOOKS["SENSEX"]
        out["SENSEX"] = grid(collect(data, sx), "SENSEX (CE only, as live)", log)
        sxc = dict(sx, hybrid=True, hyb_otm=0.01, hyb_min_cw=0.08)
        out["SENSEX_condor"] = grid(collect(data, sxc), "SENSEX with the put-side add (condor)", log)
        out["NIFTY"] = grid(collect(data, M.BOOKS["NIFTY"]), "NIFTY (as live, incl. its hybrid add)", log)
    except M.WindowClosed as w:
        log(f"STOPPED at {w}; rerun to resume"); return 3
    json.dump(out, open(os.path.join(M.ROOT, "research", "rally_guard", "results34.json"), "w"), indent=1)
    log(f"\nFETCH: {f.n_req} requests, {f.n_hit} cache hits, {f.n_429} 429, {len(f.failures)} failures -> "
        f"{'CLEAN' if not f.failures else 'NOT CLEAN'}")
    for x in f.failures[:10]:
        log(f"  {x}")
    return 0 if not f.failures else 2


if __name__ == "__main__":
    sys.exit(main())
