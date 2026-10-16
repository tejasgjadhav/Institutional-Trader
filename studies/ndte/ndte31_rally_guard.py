"""ndte31 — can the SENSEX 0DTE book avoid a full-width loss like 15-Oct-2026? (pre-registered in
research/rally_guard/prereg.json before any result was read)

Reuses the ndte30 data layer, cache (data/ndte30_cache/), fetch budget and token rule unchanged.
  A  narrower wing: same 09:16 short strike, long leg at short + W points
  B  spot stop: deployed wing, buy back at the first 1-min bar <= 15:14 where the index >= short*(1+x)
  C  report only: skip when the prior 4-day return >= 1.5%
NIFTY cross-check for A: deployed FLIP/rv5/hybrid book with a 100 / 150 point wing against 200.

Run: .venv/bin/python studies/ndte/ndte31_rally_guard.py [--allow-daytime] [--cache-only]
"""
import os
import sys
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ndte30_time_losscut as M          # noqa: E402

OUT = os.path.join(M.ROOT, "research", "rally_guard")
SX_WINGS = [200, 300, 400, 500]
NF_WINGS = [100, 150]
STOP_X = [0.0, 0.0025, 0.005]
STOP_LAST = "15:14"                       # the index print freezes in the 15:15 closing auction
HALF = "2025-10-01"


def spot_stop(pos, spot_leg, x, settle_close):
    """Deployed exit, plus: first bar <= 15:14 with index close >= ks*(1+x) -> buy back there."""
    ls, ll = pos["leg_s"], pos["leg_l"]
    trig = pos["ks"] * (1 + x) if pos["typ"] == "CE" else pos["ks"] * (1 - x)
    hit = None
    for b in spot_leg.bars:
        if b[0] < pos["entry_hm"] or b[0] > STOP_LAST:
            continue
        if (pos["typ"] == "CE" and b[4] >= trig) or (pos["typ"] == "PE" and b[4] <= trig):
            hit = b[0]
            break
    base = M.simulate(pos, settle_close)                       # deployed path
    if hit is None or (base["kind"] == "TP" and base["exit_hm"] <= hit):
        return base
    a, c = ls.close_at(hit), ll.close_at(hit)
    if a is None or c is None:
        return base
    lot, credit = pos["lot"], pos["credit"]
    cost0 = (pos["s0"] + pos["l0"]) * M.SLIP_PCT / 100 + M.BROKER * 4 / lot
    fill = a * (1 + M.EXIT_SLIP) - c * (1 - M.EXIT_SLIP)
    extra = (a + c) * M.SLIP_PCT / 100 + M.BROKER * 4 / lot
    net = credit - fill - cost0 - extra
    return dict(net_pts=net, net_rs=net * lot, kind="STOP", exit_hm=hit, stale=False)


def stats(rows):
    if not rows:
        return dict(n=0)
    nets = [r[1] for r in rows]
    w = [x for x in nets if x > 0]
    l = [x for x in nets if x <= 0]
    eq, peak, dd = 0.0, 0.0, 0.0
    for x in nets:
        eq += x; peak = max(peak, eq); dd = min(dd, eq - peak)
    h1 = sum(r[1] for r in rows if r[0] < HALF)
    h2 = sum(r[1] for r in rows if r[0] >= HALF)
    return dict(n=len(nets), win=round(100 * len(w) / len(nets), 1), total=round(sum(nets)),
                avg_win=round(sum(w) / len(w)) if w else 0, avg_loss=round(sum(l) / len(l)) if l else 0,
                worst=round(min(nets)), maxdd=round(dd), h1=round(h1), h2=round(h2),
                full_losses=sum(1 for r in rows if r[3]))


def run(data, book, variants, log):
    exps, daily, sdays = M.build_days(data, book, M.START)
    log(f"[{book['name']}] {len(exps)} expiries {exps[0]} -> {exps[-1]}")
    out = {k: [] for k in variants}
    rally = {}
    for i, e in enumerate(exps, 1):
        ctx = M.day_ctx(data, book, e, daily, sdays)
        if ctx["close"] is None:
            data.f.failures.append((f"official close {book['name']} {e}", "missing"))
            continue
        prior = [daily[d][3] for d in sdays if d < e]
        rally[e] = 100 * (prior[-1] / prior[-5] - 1) if len(prior) >= 5 else None
        if e in M.BLACKOUT or (book["rv5_max"] and ctx["rv5"] is not None and ctx["rv5"] >= book["rv5_max"]):
            continue
        try:
            ctx["chain"] = data.contracts(book, e)
            bars, _ = data.spot_1m(book, e)
            ctx["spot"] = M.Leg(bars)
        except M.FetchFailed:
            continue

        def gb(key, _e=e):
            return data.candles(key, _e)
        for name, (bk, mode, x) in variants.items():
            try:
                pos, _why = M.decide(bk, ctx, M.DEPLOYED_ENTRY, bk["otm"], gb)
            except M.FetchFailed:
                data.f.failures.append((f"{name} {e}", "leg fetch"))
                continue
            for p in pos or []:
                r = spot_stop(p, ctx["spot"], x, ctx["close"]) if mode == "stop" else M.simulate(p, ctx["close"])
                full = r["kind"] == "SETTLE" and M.settle_cost(p["typ"], p["ks"], p["kl"], p["width"], ctx["close"]) >= p["width"] - 1e-9
                out[name].append((e, r["net_rs"], r["kind"], full, p["ks"], p["kl"], p["credit"]))
        if i % 10 == 0:
            log(f"  {i}/{len(exps)} · requests {data.f.n_req} · hits {data.f.n_hit} · failures {len(data.f.failures)}")
    return out, rally


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-daytime", action="store_true")
    ap.add_argument("--cache-only", action="store_true")
    ap.add_argument("--gap", type=float, default=M.Fetcher.MIN_GAP)
    a = ap.parse_args(argv)
    log = lambda s: print(s, flush=True)
    now = M._ist_now()
    if not a.cache_only and not M.fetch_window_open(now, a.allow_daytime):
        log("REFUSED: outside the fetch window"); return 3
    f = M.Fetcher(allow_daytime=a.allow_daytime, cache_only=a.cache_only, gap=a.gap, log=log,
                  seed_from_cache=not a.cache_only)
    data = M.Data(f)
    sx, nf = M.BOOKS["SENSEX"], M.BOOKS["NIFTY"]
    sxv = {"deployed": (sx, "hold", 0)}
    for w in SX_WINGS:
        sxv[f"wing{w}"] = (dict(sx, wing_pts=float(w), wing_pct=None), "hold", 0)
    for x in STOP_X:
        sxv[f"stop+{x * 100:.2f}%"] = (sx, "stop", x)
    nfv = {"deployed": (nf, "hold", 0)}
    for w in NF_WINGS:
        nfv[f"wing{w}"] = (dict(nf, wing_pts=float(w)), "hold", 0)
    try:
        sres, srally = run(data, sx, sxv, log)
        nres, _ = run(data, nf, nfv, log)
    except M.WindowClosed as w:
        log(f"STOPPED at {w}; cache kept, rerun to resume. No results written."); return 3
    except M.FetchFailed as x:
        log(f"ABORTED: {x}"); return 2
    clean = not f.failures
    res = {"clean": clean, "requests": f.n_req, "cache_hits": f.n_hit, "n_429": f.n_429,
           "failures": [list(x) for x in f.failures[:50]], "SENSEX": {}, "NIFTY": {}}
    log(f"\nSENSEX 0DTE, {M.START} -> latest expiry, Rs per lot, after costs")
    hdr = f"{'variant':14s} {'n':>4} {'win%':>6} {'total':>8} {'avgW':>6} {'avgL':>7} {'worst':>8} {'maxDD':>8} {'H1':>8} {'H2':>8} {'fullL':>5}"
    log(hdr)
    for k, rows in sres.items():
        s = stats(rows); res["SENSEX"][k] = s
        log(f"{k:14s} {s['n']:>4} {s['win']:>6} {s['total']:>8} {s['avg_win']:>6} {s['avg_loss']:>7} {s['worst']:>8} {s['maxdd']:>8} {s['h1']:>8} {s['h2']:>8} {s['full_losses']:>5}")
    dep = sres["deployed"]
    kept = [r for r in dep if (srally.get(r[0]) or 0) < 1.5]
    s = stats(kept); res["SENSEX"]["C_skip_r4>=1.5 (report only)"] = s
    log(f"{'C skip r4>=1.5':14s} {s['n']:>4} {s['win']:>6} {s['total']:>8} {s['avg_win']:>6} {s['avg_loss']:>7} {s['worst']:>8} {s['maxdd']:>8} {s['h1']:>8} {s['h2']:>8} {s['full_losses']:>5}  (report only)")
    log("\n15-Oct-2026 under each variant:")
    for k, rows in sres.items():
        for r in rows:
            if r[0] == "2026-10-15":
                log(f"  {k:14s} {r[4]:.0f}/{r[5]:.0f} credit {r[6]:.2f} -> {r[2]} Rs{r[1]:,.0f}")
    log(f"\nNIFTY cross-check (deployed FLIP/rv5/hybrid book)")
    log(hdr)
    for k, rows in nres.items():
        s = stats(rows); res["NIFTY"][k] = s
        log(f"{k:14s} {s['n']:>4} {s['win']:>6} {s['total']:>8} {s['avg_win']:>6} {s['avg_loss']:>7} {s['worst']:>8} {s['maxdd']:>8} {s['h1']:>8} {s['h2']:>8} {s['full_losses']:>5}")
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    json.dump({k: v for k, v in sres.items()}, open(os.path.join(OUT, "sensex_rows.json"), "w"))
    log(f"\nFETCH INTEGRITY: {f.n_req} requests, {f.n_hit} cache hits, {f.n_429} 429, {len(f.failures)} failures -> "
        f"{'CLEAN' if clean else 'NOT CLEAN'}")
    for x in f.failures[:20]:
        log(f"   failed: {x}")
    log("DONE-NDTE31")
    return 0 if clean else 2


if __name__ == "__main__":
    sys.exit(main())
