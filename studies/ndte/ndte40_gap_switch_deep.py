"""ndte40 — deeper checks on the SENSEX gap-up -> put spread switch (user, 16-Oct-2026), before going live.
Option 2: gap >= 0.50% -> put 1.0% below.  Option 3: gap >= 0.25% -> put 0.5% below.
  1 neighbourhood grid (gap 0.20..0.60 x put distance 0.5/0.75/1.0%)
  2 quarter-by-quarter net for live, option 2, option 3
  3 every gap-up day: call result as live vs the put result
Live exits (hold to settle, no cap). Real Upstox 1-min option prices Oct-2024 -> latest.
Run: .venv/bin/python studies/ndte/ndte40_gap_switch_deep.py [--allow-daytime]"""
import os, sys, json, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ndte30_time_losscut as M          # noqa: E402
import ndte34_margin_return as Q         # noqa: E402
import ndte37_open30 as T                # noqa: E402

GAPS = [0.20, 0.25, 0.30, 0.40, 0.50, 0.60]
DISTS = [0.005, 0.0075, 0.01]


def q_of(d):
    return f"{d[:4]}Q{(int(d[5:7]) - 1) // 3 + 1}"


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--allow-daytime", action="store_true")
    a = ap.parse_args(argv); log = lambda s: print(s, flush=True)
    if not M.fetch_window_open(M._ist_now(), a.allow_daytime):
        log("REFUSED"); return 3
    f = M.Fetcher(allow_daytime=a.allow_daytime, log=log, seed_from_cache=True); data = M.Data(f)
    book = M.BOOKS["SENSEX"]
    exps, daily, sdays = M.build_days(data, book, M.START)
    days = []
    try:
        for e in exps:
            ctx = M.day_ctx(data, book, e, daily, sdays)
            if ctx["close"] is None or e in M.BLACKOUT:
                continue
            prev = [daily[d][3] for d in sdays if d < e]
            ctx["chain"] = data.contracts(book, e)
            bars, _ = data.spot_1m(book, e); ctx["spot"] = M.Leg(bars)
            gb = lambda k, _e=e: data.candles(k, _e)
            if not ctx["spot"].bars or not prev:
                continue
            gap = 100 * (ctx["spot"].bars[0][1] / prev[-1] - 1)
            base, _ = M.decide(book, ctx, "09:16", book["otm"], gb)
            puts = {}
            if gap >= min(GAPS):
                for d in DISTS:
                    puts[d] = T.forced(dict(book, otm=d), ctx, "09:16", "PE", gb)
            sp, cl = ctx["spot"], ctx["close"]
            val = lambda pl: sum(Q.run_one(p, sp, cl, 0.0, None) for p in pl) if pl else None
            days.append(dict(day=e, gap=gap, close_move=100 * (cl / sp.bars[0][1] - 1), base=val(base),
                             base_lbl=(f"{base[0]['ks']:.0f}/{base[0]['kl']:.0f} CE cr {base[0]['credit']:.1f}" if base else "no trade"),
                             puts={d: val(p) for d, p in puts.items()},
                             put_lbl={d: (f"{p[0]['ks']:.0f}/{p[0]['kl']:.0f} PE cr {p[0]['credit']:.1f}" if p else "no trade") for d, p in puts.items()}))
    except M.FetchFailed as x:
        log(f"ABORTED fetch {x}"); return 2
    except M.WindowClosed as w:
        log(f"STOPPED {w}"); return 3

    def book_net(g, d, sel=lambda x: True):
        tot = 0.0
        for x in days:
            if not sel(x):
                continue
            v = x["puts"].get(d) if x["gap"] >= g else x["base"]
            tot += v or 0.0
        return round(tot)
    live = book_net(99, 0.005)
    log(f"SENSEX, {len(days)} expiries {days[0]['day']} -> {days[-1]['day']}. Live net (call every day, hold): Rs{live:,}")
    log("\n1. NEIGHBOURHOOD — book net over 2 years (Rs), change vs live in brackets")
    log("   gap \\ put distance " + "".join(f"{d*100:>16.2f}%" for d in DISTS) + "     gap days")
    for g in GAPS:
        cells = "".join(f"{book_net(g, d):>9,} ({book_net(g, d) - live:+6,})" for d in DISTS)
        log(f"   gap >= {g:.2f}%      {cells}     {sum(1 for x in days if x['gap'] >= g):>4}")
    log("\n2. QUARTER BY QUARTER — net Rs")
    qs = sorted({q_of(x["day"]) for x in days})
    log(f"   {'quarter':8s} {'live':>8} {'option 2':>9} {'option 3':>9}   gap days (>=0.25 / >=0.50)")
    for qq in qs:
        s = lambda x, qq=qq: q_of(x["day"]) == qq
        log(f"   {qq:8s} {book_net(99, .005, s):>8,} {book_net(.50, .01, s):>9,} {book_net(.25, .005, s):>9,}   "
            f"{sum(1 for x in days if s(x) and x['gap'] >= .25):>3} / {sum(1 for x in days if s(x) and x['gap'] >= .50)}")
    pos2 = sum(1 for qq in qs if book_net(.50, .01, lambda x, qq=qq: q_of(x['day']) == qq) >= book_net(99, .005, lambda x, qq=qq: q_of(x['day']) == qq))
    pos3 = sum(1 for qq in qs if book_net(.25, .005, lambda x, qq=qq: q_of(x['day']) == qq) >= book_net(99, .005, lambda x, qq=qq: q_of(x['day']) == qq))
    log(f"   quarters where the option is at least as good as live: option 2 {pos2}/{len(qs)}, option 3 {pos3}/{len(qs)}")
    log("\n3. EVERY GAP-UP DAY (gap >= 0.25%) — call as live vs the put")
    log(f"   {'day':10s} {'gap':>6} {'09:15->close':>12} | {'call (live)':>11} | {'put 0.5% (opt 3)':>16} | {'put 1.0% (opt 2 if gap>=.5)':>27}")
    for x in days:
        if x["gap"] < .25:
            continue
        p05, p10 = x["puts"].get(.005), x["puts"].get(.01)
        f_ = lambda v: "—" if v is None else f"{v:,.0f}"
        log(f"   {x['day']:10s} {x['gap']:>5.2f}% {x['close_move']:>11.2f}% | {f_(x['base']):>11} | {f_(p05):>16} | {f_(p10):>20}{'  *' if x['gap'] >= .5 else ''}")
    json.dump(days, open(os.path.join(M.ROOT, "research", "rally_guard", "results40_days.json"), "w"), indent=1, default=str)
    log(f"\nFETCH: {f.n_req} requests, {f.n_hit} cache hits, {f.n_429} 429, {len(f.failures)} failures -> {'CLEAN' if not f.failures else 'NOT CLEAN'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
