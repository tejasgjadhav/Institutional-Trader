"""ndte38 — entry x 09:45 filter x exit combinations, scored on NET (user goal 16-Oct-2026).
prereg: research/rally_guard/prereg38.json. Reuses ndte37 helpers and the ndte30 cache.
Run: .venv/bin/python studies/ndte/ndte38_combos.py [--allow-daytime]"""
import os, sys, json, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ndte30_time_losscut as M          # noqa: E402
import ndte32_loss_cap as P              # noqa: E402
import ndte34_margin_return as Q         # noqa: E402
import ndte37_open30 as T                # noqa: E402

ENTRIES = ["09:16", "09:30", "09:45"]
FILTERS = ["none", "skip30", "side30", "both"]
EXITS = ["hold", "cap5k", "cap7k", "cap10k", "x45rng", "x45drift"]


def net_exit(p, spot, close, ex, rng, drift):
    if ex == "hold":
        return Q.run_one(p, spot, close, 0.0, None)
    if ex.startswith("cap"):
        return Q.run_one(p, spot, close, 0.0, {"cap5k": 5000, "cap7k": 7000, "cap10k": 10000}[ex])
    sg = 1 if p["typ"] == "CE" else -1
    flag = rng >= 0.50 if ex == "x45rng" else sg * drift >= 0.30
    if not flag:
        return Q.run_one(p, spot, close, 0.0, None)
    a, c = p["leg_s"].close_at("09:45"), p["leg_l"].close_at("09:45")
    if a is None or c is None:
        return Q.run_one(p, spot, close, 0.0, None)
    lot = p["lot"]
    cost0 = (p["s0"] + p["l0"]) * M.SLIP_PCT / 100 + M.BROKER * 4 / lot
    return (p["credit"] - (a * (1 + M.EXIT_SLIP) - c * (1 - M.EXIT_SLIP)) - cost0 - ((a + c) * M.SLIP_PCT / 100 + M.BROKER * 4 / lot)) * lot


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--allow-daytime", action="store_true")
    a = ap.parse_args(argv); log = lambda s: print(s, flush=True)
    if not M.fetch_window_open(M._ist_now(), a.allow_daytime):
        log("REFUSED"); return 3
    f = M.Fetcher(allow_daytime=a.allow_daytime, log=log, seed_from_cache=True); data = M.Data(f)
    out = {}
    for nm in ("NIFTY", "SENSEX"):
        book = M.BOOKS[nm]
        exps, daily, sdays = M.build_days(data, book, M.START)
        rows = {}
        for e in exps:
            ctx = M.day_ctx(data, book, e, daily, sdays)
            if ctx["close"] is None or e in M.BLACKOUT:
                continue
            if book["rv5_max"] and ctx["rv5"] is not None and ctx["rv5"] >= book["rv5_max"]:
                continue
            try:
                ctx["chain"] = data.contracts(book, e)
                bars, _ = data.spot_1m(book, e); ctx["spot"] = M.Leg(bars)
                gb = lambda k, _e=e: data.candles(k, _e)
                rng, drift = T.feats(ctx["spot"])
                if rng is None:
                    continue
                pos = {t: M.decide(book, ctx, t, book["otm"], gb)[0] for t in ENTRIES}
                d45 = pos["09:45"][0]["typ"] if pos["09:45"] else ("PE" if (book["flip_ret5"] and (ctx["ret5"] or 0) >= book["flip_ret5"]) else "CE")
                fs = "PE" if drift >= 0.30 else ("CE" if drift <= -0.30 else d45)
                side45 = pos["09:45"] if fs == d45 else T.forced(book, ctx, "09:45", fs, gb)
            except M.FetchFailed:
                data.f.failures.append((f"{nm} {e}", "fetch")); continue
            for t in ENTRIES:
                for flt in FILTERS:
                    if t != "09:45" and flt != "none":
                        continue
                    pl = pos[t]
                    if flt in ("side30", "both"):
                        pl = side45
                    if flt in ("skip30", "both") and rng >= 0.50:
                        pl = None
                    for ex in EXITS:
                        if t == "09:45" and ex.startswith("x45"):
                            continue
                        k = (t, flt, ex)
                        n_ = sum(net_exit(p, ctx["spot"], ctx["close"], ex, rng, drift) for p in pl) if pl else None
                        rows.setdefault(k, []).append((e, n_, Q.margin(pl) if pl else 1))
        st = {k: T.summarise(v) for k, v in rows.items()}
        base_h2 = st[("09:16", "none", "hold")]["h2"]["total"]; live_h2 = st[("09:16", "none", "cap5k")]["h2"]["total"]
        rank = sorted(st.items(), key=lambda kv: -kv[1]["h1"]["total"])
        log(f"\n{nm}: {len(st)} combinations. Baselines: 09:16+hold H1/H2/all {st[('09:16','none','hold')]['h1']['total']}/{base_h2}/{st[('09:16','none','hold')]['all']['total']} · "
            f"LIVE 09:16+cap5k {st[('09:16','none','cap5k')]['h1']['total']}/{live_h2}/{st[('09:16','none','cap5k')]['all']['total']}")
        log(f"  top 8 by H1 net:   {'entry':5s} {'filter':7s} {'exit':8s} | {'trades':>6} {'win':>5} | {'H1 net':>7} {'H2 net':>7} {'ALL net':>8} {'worst':>7}")
        for k, s in rank[:8]:
            log(f"                     {k[0]:5s} {k[1]:7s} {k[2]:8s} | {s['all']['n']:>6} {s['all']['win']:>5} | {s['h1']['total']:>7} {s['h2']['total']:>7} {s['all']['total']:>8} {s['all']['worst']:>7}")
        pk, ps = rank[0]
        ok = ps["h2"]["total"] >= base_h2 and ps["h2"]["total"] >= live_h2
        log(f"  PICK {pk}: H2 {ps['h2']['total']} vs 09:16+hold {base_h2} and live {live_h2} -> {'PASS' if ok else 'FAIL'}")
        top_all = sorted(st.items(), key=lambda kv: -kv[1]["all"]["total"])[:5]
        log("  (for reference, best on the WHOLE window, not a selection): " + "; ".join(f"{k} {s['all']['total']}" for k, s in top_all))
        out[nm] = {"|".join(k): v for k, v in st.items()}
        out[nm + "_pick"] = dict(pick=list(pk), passed=ok)
    json.dump(out, open(os.path.join(M.ROOT, "research", "rally_guard", "results38.json"), "w"), indent=1)
    log(f"\nFETCH: {f.n_req} requests, {f.n_hit} cache hits, {len(f.failures)} failures -> {'CLEAN' if not f.failures else 'NOT CLEAN'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
