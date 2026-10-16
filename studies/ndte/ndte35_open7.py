"""ndte35 phase B — the opening 7 minutes on real option prices, Oct-2024 -> latest (prereg35.json).
Phase A (index only, NIFTY 2022-01..2024-07, research/rally_guard/phaseA_open7.py) found the breach rate
rising with the 09:15-09:21 range; the 0.30% cut was chosen there AFTER reading A, so this window is
its out-of-sample test. Variants, each under the live exit (TP 95% + Rs5,000 cap) and TP off + cap:
  E16  enter 09:16 (live)                E22  enter 09:22
  S30  enter 09:22, skip if range >= 0.30%
  W30  enter 09:22, short 1.0% OTM instead of 0.5% when range >= 0.30%
  D25  enter 09:22, skip if the 7-minute drift AWAY from the short <= -0.25% (n=7 in A: watch only)

Run: .venv/bin/python studies/ndte/ndte35_open7.py [--allow-daytime]
"""
import os
import sys
import json
import argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ndte30_time_losscut as M          # noqa: E402
import ndte32_loss_cap as P              # noqa: E402
import ndte34_margin_return as Q         # noqa: E402

EXITS = {"live (TP95+cap5k)": (M.TP_FRAC, 5000), "TP off + cap5k": (0.0, 5000), "TP off, no cap": (0.0, None)}


def window(spot):
    w = [b for b in spot.bars if "09:15" <= b[0] <= "09:21"]
    if len(w) < 5:
        return None, None
    o = w[0][1]
    return 100 * (max(b[2] for b in w) - min(b[3] for b in w)) / o, 100 * (w[-1][4] / o - 1)


def collect(data, book):
    exps, daily, sdays = M.build_days(data, book, M.START)
    out = {k: [] for k in ("E16", "E22", "S30", "W30", "D25")}
    feats = []
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
        except M.FetchFailed:
            data.f.failures.append((f"{book['name']} {e}", "fetch")); continue
        gb = lambda k, _e=e: data.candles(k, _e)
        rng, drift = window(ctx["spot"])
        try:
            p16, _ = M.decide(book, ctx, "09:16", book["otm"], gb)
            p22, _ = M.decide(book, ctx, "09:22", book["otm"], gb)
            pw = M.decide(book, ctx, "09:22", 0.01, gb)[0] if (rng or 0) >= 0.30 else p22
        except M.FetchFailed:
            data.f.failures.append((f"{book['name']} {e} legs", "fetch")); continue
        sg = 1
        if p22:
            sg = 1 if p22[0]["typ"] == "CE" else -1
        d_short = None if drift is None else sg * drift
        feats.append(dict(day=e, rng=rng, drift=d_short))
        rec = lambda pl: (e, pl, ctx["spot"], ctx["close"]) if pl else None
        for k, pl in (("E16", p16), ("E22", p22),
                      ("S30", p22 if (rng is not None and rng < 0.30) else None),
                      ("W30", pw),
                      ("D25", p22 if (d_short is None or d_short > -0.25) else None)):
            r = rec(pl)
            if r:
                out[k].append(r)
    return out, feats


def score(days, tp, cap):
    rows = [(e, sum(Q.run_one(p, s, c, tp, cap) for p in pl), Q.margin(pl)) for e, pl, s, c in days]
    st = {}
    for h, sel in (("h1", [r for r in rows if r[0] < P.HALF]), ("h2", [r for r in rows if r[0] >= P.HALF]), ("all", rows)):
        if not sel:
            st[h] = dict(n=0, pm=0, total=0, worst=0, win=0); continue
        tot = sum(r[1] for r in sel); am = sum(r[2] for r in sel) / len(sel)
        mo = Q.MONTHS.get(h, Q.MONTHS["h1"] + Q.MONTHS["h2"])
        st[h] = dict(n=len(sel), pm=round(100 * tot / mo / am, 1), total=round(tot), worst=round(min(r[1] for r in sel)),
                     win=round(100 * sum(1 for r in sel if r[1] > 0) / len(sel), 1))
    return st


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-daytime", action="store_true")
    ap.add_argument("--cache-only", action="store_true")
    a = ap.parse_args(argv)
    log = lambda s: print(s, flush=True)
    if not a.cache_only and not M.fetch_window_open(M._ist_now(), a.allow_daytime):
        log("REFUSED"); return 3
    f = M.Fetcher(allow_daytime=a.allow_daytime, cache_only=a.cache_only, log=log, seed_from_cache=not a.cache_only)
    data = M.Data(f)
    res = {}
    try:
        for nm in ("NIFTY", "SENSEX"):
            v, feats = collect(data, M.BOOKS[nm])
            res[nm] = {}
            hi = [x for x in feats if (x["rng"] or 0) >= 0.30]
            log(f"\n{nm}: {len(feats)} expiries · opening range >= 0.30% on {len(hi)} of them")
            log(f"  {'variant':6s} {'exit':20s} {'n':>3} | {'H1 %/mo':>8} {'H2 %/mo':>8} {'all %/mo':>8} | {'total':>8} {'worst':>8} {'win':>5}")
            for k, days in v.items():
                for ex, (tp, cap) in EXITS.items():
                    st = score(days, tp, cap)
                    res[nm][f"{k} {ex}"] = st
                    al = st["all"]
                    log(f"  {k:6s} {ex:20s} {al['n']:>3} | {st['h1']['pm']:>7}% {st['h2']['pm']:>7}% {al['pm']:>7}% | {al['total']:>8} {al['worst']:>8} {al['win']:>5}")
    except M.WindowClosed as w:
        log(f"STOPPED at {w}; rerun to resume"); return 3
    json.dump(res, open(os.path.join(M.ROOT, "research", "rally_guard", "results35.json"), "w"), indent=1)
    log(f"\nFETCH: {f.n_req} requests, {f.n_hit} cache hits, {f.n_429} 429, {len(f.failures)} failures -> "
        f"{'CLEAN' if not f.failures else 'NOT CLEAN'}")
    for x in f.failures[:10]:
        log(f"  {x}")
    return 0 if not f.failures else 2


if __name__ == "__main__":
    sys.exit(main())
