"""ndte36 — does a later 0DTE entry (09:30 / 09:45 / 10:00) avoid losses? (user, 16-Oct-2026)
Same strike rule (0.5% OTM of the spot AT the entry time), all deployed gates, real Upstox 1-min
option prices Oct-2024 -> latest. Exits as live from 16-Oct (hold to settle + Rs5,000 cap) and no cap.

Run: .venv/bin/python studies/ndte/ndte36_late_entry.py [--allow-daytime]
"""
import os, sys, json, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ndte30_time_losscut as M          # noqa: E402
import ndte32_loss_cap as P              # noqa: E402
import ndte34_margin_return as Q         # noqa: E402
import ndte35_open7 as O                 # noqa: E402

TIMES = ["09:16", "09:30", "09:45", "10:00"]
EXITS = {"live: hold + cap5k": (0.0, 5000), "hold, no cap": (0.0, None)}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--allow-daytime", action="store_true")
    a = ap.parse_args(argv); log = lambda s: print(s, flush=True)
    if not M.fetch_window_open(M._ist_now(), a.allow_daytime):
        log("REFUSED"); return 3
    f = M.Fetcher(allow_daytime=a.allow_daytime, log=log, seed_from_cache=True); data = M.Data(f)
    res = {}
    for nm in ("NIFTY", "SENSEX"):
        book = M.BOOKS[nm]
        exps, daily, sdays = M.build_days(data, book, M.START)
        per = {t: [] for t in TIMES}
        for e in exps:
            ctx = M.day_ctx(data, book, e, daily, sdays)
            if ctx["close"] is None or e in M.BLACKOUT:
                continue
            if book["rv5_max"] and ctx["rv5"] is not None and ctx["rv5"] >= book["rv5_max"]:
                continue
            try:
                ctx["chain"] = data.contracts(book, e)
                bars, _ = data.spot_1m(book, e); ctx["spot"] = M.Leg(bars)
                for t in TIMES:
                    pl, _ = M.decide(book, ctx, t, book["otm"], lambda k, _e=e: data.candles(k, _e))
                    if pl:
                        per[t].append((e, pl, ctx["spot"], ctx["close"]))
            except M.FetchFailed:
                data.f.failures.append((f"{nm} {e}", "fetch"))
        res[nm] = {}
        log(f"\n{nm}")
        log(f"  {'entry':6s} {'exit':20s} {'n':>3} {'win':>5} {'losses':>6} {'avg cr':>7} | {'H1 %/mo':>8} {'H2 %/mo':>8} {'all %/mo':>8} | {'total':>8} {'worst':>8} {'sum of losses':>13}")
        for t in TIMES:
            days = per[t]
            avg_cr = sum(sum(p["credit"] for p in pl) for _, pl, _, _ in days) / max(1, len(days))
            for ex, (tp, cap) in EXITS.items():
                st = O.score(days, tp, cap)
                nets = [sum(Q.run_one(p, s, c, tp, cap) for p in pl) for _, pl, s, c in days]
                losses = [x for x in nets if x <= 0]
                al = st["all"]
                res[nm][f"{t} {ex}"] = dict(st, losses=len(losses), loss_sum=round(sum(losses)), avg_credit=round(avg_cr, 2))
                log(f"  {t:6s} {ex:20s} {al['n']:>3} {al['win']:>5} {len(losses):>6} {avg_cr:>7.2f} | {st['h1']['pm']:>7}% {st['h2']['pm']:>7}% {al['pm']:>7}% | {al['total']:>8} {al['worst']:>8} {round(sum(losses)):>13}")
    json.dump(res, open(os.path.join(M.ROOT, "research", "rally_guard", "results36.json"), "w"), indent=1)
    log(f"\nFETCH: {f.n_req} requests, {f.n_hit} cache hits, {f.n_429} 429, {len(f.failures)} failures -> {'CLEAN' if not f.failures else 'NOT CLEAN'}")
    return 0 if not f.failures else 2


if __name__ == "__main__":
    sys.exit(main())
