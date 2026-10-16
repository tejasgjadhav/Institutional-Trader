"""ndte39 — switch side on a gap open (user, 16-Oct-2026; prereg research/rally_guard/prereg39.json).
Gap up >= g: sell the PUT spread with the short d below the 09:16 spot (deployed wing); gap down <= -g
(mirror): sell the CALL spread d above. Other days unchanged. Live exits (hold to settle, no cap).
Real Upstox 1-min option prices Oct-2024 -> latest. Run: .venv/bin/python studies/ndte/ndte39_gap_switch.py [--allow-daytime]"""
import os, sys, json, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ndte30_time_losscut as M          # noqa: E402
import ndte34_margin_return as Q         # noqa: E402
import ndte37_open30 as T                # noqa: E402
import ndte32_loss_cap as P              # noqa: E402

GAPS = [0.25, 0.50, 0.75]
DISTS = [0.005, 0.01]


def forced(book, ctx, hm, typ, otm, gb):
    b = dict(book, otm=otm)
    return T.forced(b, ctx, hm, typ, gb)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--allow-daytime", action="store_true")
    a = ap.parse_args(argv); log = lambda s: print(s, flush=True)
    if not M.fetch_window_open(M._ist_now(), a.allow_daytime):
        log("REFUSED"); return 3
    f = M.Fetcher(allow_daytime=a.allow_daytime, log=log, seed_from_cache=True); data = M.Data(f)
    out = {}
    try:
        for nm in ("NIFTY", "SENSEX"):
            book = M.BOOKS[nm]
            exps, daily, sdays = M.build_days(data, book, M.START)
            rows = {}
            gapdays = []
            for e in exps:
                ctx = M.day_ctx(data, book, e, daily, sdays)
                if ctx["close"] is None or e in M.BLACKOUT:
                    continue
                if book["rv5_max"] and ctx["rv5"] is not None and ctx["rv5"] >= book["rv5_max"]:
                    continue
                prev = [daily[d][3] for d in sdays if d < e]
                try:
                    ctx["chain"] = data.contracts(book, e)
                    bars, _ = data.spot_1m(book, e); ctx["spot"] = M.Leg(bars)
                    gb = lambda k, _e=e: data.candles(k, _e)
                    o915 = ctx["spot"].bars[0][1] if ctx["spot"].bars and ctx["spot"].bars[0][0] <= "09:16" else None
                    if not o915 or not prev:
                        continue
                    gap = 100 * (o915 / prev[-1] - 1)
                    base, _ = M.decide(book, ctx, "09:16", book["otm"], gb)
                    alt = {}
                    for g in GAPS:
                        for d in DISTS:
                            if gap >= g:
                                alt[("UP", g, d)] = forced(book, ctx, "09:16", "PE", d, gb)
                            elif gap <= -g:
                                alt[("DN", g, d)] = forced(book, ctx, "09:16", "CE", d, gb)
                except M.FetchFailed:
                    data.f.failures.append((f"{nm} {e}", "fetch")); continue
                sp, cl = ctx["spot"], ctx["close"]
                val = lambda pl: (sum(Q.run_one(p, sp, cl, 0.0, None) for p in pl), Q.margin(pl)) if pl else (None, 1)
                b_ = val(base)
                gapdays.append((e, gap, b_[0]))
                rows.setdefault(("live", 0, 0), []).append((e, *b_))
                for side in ("UP", "DN"):
                    for g in GAPS:
                        for d in DISTS:
                            k = (side, g, d)
                            r = val(alt[k]) if k in alt else b_
                            rows.setdefault(k, []).append((e, *r))
            st = {k: T.summarise(v) for k, v in rows.items()}
            L = st[("live", 0, 0)]
            log(f"\n{nm}: live 09:16 hold, no cap: trades {L['all']['n']}, net H1 {L['h1']['total']} / H2 {L['h2']['total']} / all {L['all']['total']}, worst {L['all']['worst']}")
            for side in ("UP", "DN"):
                for g in GAPS:
                    gd = [x for x in gapdays if (x[1] >= g if side == "UP" else x[1] <= -g)]
                    base_on = sum(x[2] for x in gd if x[2] is not None)
                    for d in DISTS:
                        s = st[(side, g, d)]
                        sw = [r for r in rows[(side, g, d)] if r[0] in {x[0] for x in gd}]
                        sw_net = sum(r[1] for r in sw if r[1] is not None)
                        log(f"  gap {'UP' if side == 'UP' else 'DOWN'} {'>=' if side == 'UP' else '<= -'}{g:.2f}% -> {'PUT' if side == 'UP' else 'CALL'} {d*100:.1f}% : {len(gd):2d} gap days, "
                            f"their net {round(base_on):>7} as now vs {round(sw_net):>7} switched · book net H1 {s['h1']['total']:>7} H2 {s['h2']['total']:>7} all {s['all']['total']:>7} worst {s['all']['worst']:>7}")
            out[nm] = {"|".join(map(str, k)): v for k, v in st.items()}
    except M.WindowClosed as w:
        log(f"STOPPED at {w}; rerun"); return 3
    json.dump(out, open(os.path.join(M.ROOT, "research", "rally_guard", "results39.json"), "w"), indent=1)
    log(f"\nFETCH: {f.n_req} requests, {f.n_hit} cache hits, {f.n_429} 429, {len(f.failures)} failures -> {'CLEAN' if not f.failures else 'NOT CLEAN'}")
    return 0 if not f.failures else 2


if __name__ == "__main__":
    sys.exit(main())
