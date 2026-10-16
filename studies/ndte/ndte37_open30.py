"""ndte37 — the 09:15-09:45 window (user, 16-Oct-2026; prereg research/rally_guard/prereg37.json).
Real Upstox 1-min option prices Oct-2024 -> latest, NIFTY and SENSEX, live exits (hold to settle +
Rs5,000 cap). Goal (user): the most NET profit; skipping days is fine.
  L16   live: enter 09:16                     E45  enter 09:45, deployed side
  G1    09:45, skip if range30 >= 0.50%       F1   09:45, side from drift30 (up >= .30 -> PE, down <= -.30 -> CE)
  G1F1  both                                  X1   09:16 entry, exit at 09:45 if range30 >= 0.50%
  X2    09:16 entry, exit at 09:45 if drift30 toward the short >= +0.30%

Run: .venv/bin/python studies/ndte/ndte37_open30.py [--allow-daytime]
"""
import os, sys, json, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ndte30_time_losscut as M          # noqa: E402
import ndte32_loss_cap as P              # noqa: E402
import ndte34_margin_return as Q         # noqa: E402

CAP = 5000


def feats(spot):
    w = [b for b in spot.bars if "09:15" <= b[0] <= "09:44"]
    if len(w) < 20:
        return None, None
    o = w[0][1]
    return 100 * (max(b[2] for b in w) - min(b[3] for b in w)) / o, 100 * (w[-1][4] / o - 1)


def forced(book, ctx, hm, typ, gb):
    """One vertical on a FORCED side at hm, with the deployed gates (no hybrid add)."""
    spot, _, _ = ctx["spot"].entry_price(hm, allow_late=False)
    if not spot:
        return None
    v, _ = M.pick_vertical(book, ctx["chain"].get(typ), typ, spot, book["otm"])
    if v is None:
        return None
    p, _ = M._open_leg(v, hm, gb)
    if p is None or p["credit"] <= 0 or p["lot"] <= 0:
        return None
    if book["min_credit_pct"] and p["credit"] < spot * book["min_credit_pct"] / 100:
        return None
    if book["min_cw"] and p["credit"] / p["width"] < book["min_cw"]:
        return None
    p.update(day=ctx["day"], spot=spot, hybrid=False)
    return [p]


def net_live(p, spot, close):
    return Q.run_one(p, spot, close, 0.0, CAP)


def net_exit_at(p, spot, close, hm="09:45"):
    """09:16 position closed at hm unless the cap fired first."""
    t = P.trigger(("R", CAP), p, spot)
    if t is not None and t < hm:
        return Q.run_one(p, spot, close, 0.0, CAP)
    a, c = p["leg_s"].close_at(hm), p["leg_l"].close_at(hm)
    if a is None or c is None:
        return Q.run_one(p, spot, close, 0.0, CAP)
    lot = p["lot"]
    cost0 = (p["s0"] + p["l0"]) * M.SLIP_PCT / 100 + M.BROKER * 4 / lot
    net = p["credit"] - (a * (1 + M.EXIT_SLIP) - c * (1 - M.EXIT_SLIP)) - cost0 - ((a + c) * M.SLIP_PCT / 100 + M.BROKER * 4 / lot)
    return net * lot


def summarise(rows):
    """rows: [(day, net or None if no trade, margin)]"""
    tr = [r for r in rows if r[1] is not None]
    st = {}
    for h, sel in (("h1", [r for r in tr if r[0] < P.HALF]), ("h2", [r for r in tr if r[0] >= P.HALF]), ("all", tr)):
        if not sel:
            st[h] = dict(n=0, total=0, pm=0, worst=0, win=0, losses=0); continue
        tot = sum(r[1] for r in sel); am = sum(r[2] for r in sel) / len(sel)
        mo = Q.MONTHS.get(h, Q.MONTHS["h1"] + Q.MONTHS["h2"])
        st[h] = dict(n=len(sel), total=round(tot), pm=round(100 * tot / mo / am, 1), worst=round(min(r[1] for r in sel)),
                     win=round(100 * sum(1 for r in sel if r[1] > 0) / len(sel), 1), losses=sum(1 for r in sel if r[1] <= 0))
    return st


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--allow-daytime", action="store_true")
    a = ap.parse_args(argv); log = lambda s: print(s, flush=True)
    if not M.fetch_window_open(M._ist_now(), a.allow_daytime):
        log("REFUSED"); return 3
    f = M.Fetcher(allow_daytime=a.allow_daytime, log=log, seed_from_cache=True); data = M.Data(f)
    res = {}
    try:
        for nm in ("NIFTY", "SENSEX"):
            book = M.BOOKS[nm]
            exps, daily, sdays = M.build_days(data, book, M.START)
            V = {k: [] for k in ("L16", "E45", "G1", "F1", "G1F1", "X1", "X2")}
            nflip = nskip = 0
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
                    rng, drift = feats(ctx["spot"])
                    if rng is None:
                        continue
                    p16, _ = M.decide(book, ctx, "09:16", book["otm"], gb)
                    p45, _ = M.decide(book, ctx, "09:45", book["otm"], gb)
                    dside = p45[0]["typ"] if p45 else ("PE" if (book["flip_ret5"] and (ctx["ret5"] or 0) >= book["flip_ret5"]) else "CE")
                    fside = "PE" if drift >= 0.30 else ("CE" if drift <= -0.30 else dside)
                    pf = p45 if fside == dside else forced(book, ctx, "09:45", fside, gb)
                    nflip += fside != dside; nskip += rng >= 0.50
                except M.FetchFailed:
                    data.f.failures.append((f"{nm} {e}", "fetch")); continue
                sp, cl = ctx["spot"], ctx["close"]
                live = lambda pl: (sum(net_live(p, sp, cl) for p in pl), Q.margin(pl)) if pl else (None, 1)
                for k, pl in (("L16", p16), ("E45", p45), ("G1", p45 if rng < 0.50 else None), ("F1", pf),
                              ("G1F1", pf if rng < 0.50 else None)):
                    n_, m_ = live(pl); V[k].append((e, n_, m_))
                if p16:
                    sg = 1 if p16[0]["typ"] == "CE" else -1
                    x1 = rng >= 0.50; x2 = sg * drift >= 0.30
                    for k, flag in (("X1", x1), ("X2", x2)):
                        n_ = sum((net_exit_at(p, sp, cl) if flag else net_live(p, sp, cl)) for p in p16)
                        V[k].append((e, n_, Q.margin(p16)))
            res[nm] = {k: summarise(v) for k, v in V.items()}
            log(f"\n{nm}: side changed by the half-hour on {nflip} days; range30 >= 0.50% on {nskip} days")
            log(f"  {'rule':5s} {'trades':>6} {'win':>5} {'losses':>6} | {'H1 net':>8} {'H2 net':>8} {'ALL net':>8} | {'H1 %/mo':>7} {'H2 %/mo':>7} {'all %/mo':>8} {'worst':>7}")
            for k, st in res[nm].items():
                al = st["all"]
                log(f"  {k:5s} {al['n']:>6} {al['win']:>5} {al['losses']:>6} | {st['h1']['total']:>8} {st['h2']['total']:>8} {al['total']:>8} | {st['h1']['pm']:>6}% {st['h2']['pm']:>6}% {al['pm']:>7}% {al['worst']:>7}")
    except M.WindowClosed as w:
        log(f"STOPPED at {w}; rerun"); return 3
    json.dump(res, open(os.path.join(M.ROOT, "research", "rally_guard", "results37.json"), "w"), indent=1)
    log(f"\nFETCH: {f.n_req} requests, {f.n_hit} cache hits, {f.n_429} 429, {len(f.failures)} failures -> {'CLEAN' if not f.failures else 'NOT CLEAN'}")
    for x in f.failures[:10]:
        log(f"  {x}")
    return 0 if not f.failures else 2


if __name__ == "__main__":
    sys.exit(main())
