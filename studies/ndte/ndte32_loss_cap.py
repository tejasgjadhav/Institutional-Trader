"""ndte32 — cap the worst 0DTE loss with an intraday exit rule (pre-registered in
research/rally_guard/prereg32.json before any result was read). Cache only by default.

Rules (each one decides a buy-back minute; a take-profit that comes first still wins):
  R  rupee cap     : open loss >= Rs X per lot at any 1-min mark
  V  velocity      : index up >= v% from the entry spot at any minute <= T (mirror for a bull put)
  K  confirmed     : index closed beyond short*(1+x) for M consecutive minutes (<= 15:14)
  G  time-gated    : index beyond short*(1+x) before T
Selection on H1 (Oct-24..Sep-25) only, then tested on H2 and on NIFTY.

Run: .venv/bin/python studies/ndte/ndte32_loss_cap.py [--network --allow-daytime]
"""
import os
import sys
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ndte30_time_losscut as M          # noqa: E402

OUT = os.path.join(M.ROOT, "research", "rally_guard")
HALF = "2025-10-01"
SPOT_LAST = "15:14"


def rules():
    g = {"deployed": None}
    for X in (2500, 3500, 5000):
        g[f"R cap Rs{X}"] = ("R", X)
    for v in (0.005, 0.0075, 0.01):
        for T in ("10:30", "11:30", "13:00"):
            g[f"V +{v*100:.2f}% by {T}"] = ("V", v, T)
    for x in (0.0, 0.0025, 0.005):
        for m in (5, 15, 30):
            g[f"K short+{x*100:.2f}% x{m}m"] = ("K", x, m)
    for x in (0.0, 0.0025, 0.005):
        for T in ("11:00", "12:30", "14:00"):
            g[f"G short+{x*100:.2f}% <{T}"] = ("G", x, T)
    return g


def beyond(typ, px, lvl):
    return px >= lvl if typ == "CE" else px <= lvl


def trigger(rule, pos, spot):
    kind = rule[0]
    typ, ks, e = pos["typ"], pos["ks"], pos["entry_hm"]
    sg = 1 if typ == "CE" else -1
    if kind == "R":
        ls, ll = pos["leg_s"], pos["leg_l"]
        for hm in sorted(set(ls.hms + ll.hms)):
            if hm < e or hm > M.LAST_BAR:
                continue
            a, b = ls.close_at(hm), ll.close_at(hm)
            if a is not None and b is not None and ((a - b) - pos["credit"]) * pos["lot"] >= rule[1]:
                return hm
        return None
    bars = [b for b in spot.bars if e <= b[0] <= SPOT_LAST]
    if kind == "V":
        lvl = pos["spot"] * (1 + sg * rule[1])
        return next((b[0] for b in bars if b[0] <= rule[2] and beyond(typ, b[4], lvl)), None)
    lvl = ks * (1 + sg * rule[1])
    if kind == "G":
        return next((b[0] for b in bars if b[0] < rule[2] and beyond(typ, b[4], lvl)), None)
    run = 0
    for b in bars:                                            # K
        run = run + 1 if beyond(typ, b[4], lvl) else 0
        if run >= rule[2]:
            return b[0]
    return None


def evaluate(pos, spot, close, rule):
    base = M.simulate(pos, close)
    if rule is None:
        return base
    hm = trigger(rule, pos, spot)
    if hm is None or (base["kind"] == "TP" and base["exit_hm"] <= hm):
        return base
    ls, ll = pos["leg_s"], pos["leg_l"]
    a, c = ls.close_at(hm), ll.close_at(hm)
    if a is None or c is None:
        return base
    lot, credit = pos["lot"], pos["credit"]
    cost0 = (pos["s0"] + pos["l0"]) * M.SLIP_PCT / 100 + M.BROKER * 4 / lot
    fill = a * (1 + M.EXIT_SLIP) - c * (1 - M.EXIT_SLIP)
    extra = (a + c) * M.SLIP_PCT / 100 + M.BROKER * 4 / lot
    net = credit - fill - cost0 - extra
    return dict(net_rs=net * lot, kind="EXIT", exit_hm=hm)


def stats(rows):
    if not rows:
        return dict(n=0, win=0, total=0, worst=0, avg_loss=0, maxdd=0, exits=0)
    nets = [r[1] for r in rows]
    l = [x for x in nets if x <= 0]
    eq = peak = dd = 0.0
    for x in nets:
        eq += x; peak = max(peak, eq); dd = min(dd, eq - peak)
    return dict(n=len(nets), win=round(100 * (len(nets) - len(l)) / len(nets), 1), total=round(sum(nets)),
                worst=round(min(nets)), avg_loss=round(sum(l) / len(l)) if l else 0, maxdd=round(dd),
                exits=sum(1 for r in rows if r[2] == "EXIT"))


def collect(data, book, log):
    """Deployed positions per expiry with their index path. Cache-only friendly."""
    exps, daily, sdays = M.build_days(data, book, M.START)
    days = []
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
        for p in pos or []:
            days.append((e, p, ctx["spot"], ctx["close"]))
    log(f"[{book['name']}] {len(days)} positions, {days[0][0]} -> {days[-1][0]}")
    return days


def table(days, grid):
    out = {}
    for name, rule in grid.items():
        rows = []
        for e, p, spot, close in days:
            r = evaluate(p, spot, close, rule)
            rows.append((e, r["net_rs"], r["kind"]))
        out[name] = dict(all=stats(rows), h1=stats([r for r in rows if r[0] < HALF]),
                         h2=stats([r for r in rows if r[0] >= HALF]), rows=rows)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", action="store_true")
    ap.add_argument("--allow-daytime", action="store_true")
    a = ap.parse_args(argv)
    log = lambda s: print(s, flush=True)
    f = M.Fetcher(allow_daytime=a.allow_daytime, cache_only=not a.network, log=log)
    data = M.Data(f)
    grid = rules()
    res = {}
    for nm in ("SENSEX", "NIFTY"):
        days = collect(data, M.BOOKS[nm], log)
        res[nm] = table(days, grid)
    sx, dep = res["SENSEX"], res["SENSEX"]["deployed"]
    log(f"\nSENSEX, Rs per lot after costs. H1 = Oct-24..Sep-25 (selection), H2 = Oct-25 on (test)")
    log(f"{'rule':26s} | {'H1 n':>4} {'win':>5} {'total':>7} {'worst':>7} | {'H2 n':>4} {'win':>5} {'total':>7} {'worst':>7} | {'ALL total':>9} {'worst':>7} {'avgL':>6} {'maxDD':>7} {'exits':>5}")
    for k, v in sx.items():
        h1, h2, al = v["h1"], v["h2"], v["all"]
        log(f"{k:26s} | {h1['n']:>4} {h1['win']:>5} {h1['total']:>7} {h1['worst']:>7} | {h2['n']:>4} {h2['win']:>5} {h2['total']:>7} {h2['worst']:>7} | {al['total']:>9} {al['worst']:>7} {al['avg_loss']:>6} {al['maxdd']:>7} {al['exits']:>5}")
    d1 = dep["h1"]
    ok = [(k, v) for k, v in sx.items() if k != "deployed" and v["h1"]["total"] >= 0.8 * d1["total"] and v["h1"]["win"] >= 85]
    ok.sort(key=lambda kv: (-kv[1]["h1"]["worst"], -kv[1]["h1"]["total"]))
    log(f"\nH1-eligible rules (total >= 80% of deployed H1 {d1['total']}, win >= 85%): {len(ok)}")
    pick = ok[0][0] if ok else None
    verdict = {"pick": pick}
    if pick:
        p = sx[pick]
        d2 = dep["h2"]
        h2ok = p["h2"]["total"] >= 0.8 * d2["total"] and p["h2"]["worst"] > -6000 and p["h2"]["win"] >= 85
        nd, npk = res["NIFTY"]["deployed"]["all"], res["NIFTY"][pick]["all"]
        nok = npk["worst"] > nd["worst"] and npk["total"] >= 0.75 * nd["total"]
        verdict.update(h2_pass=h2ok, nifty_pass=nok, nifty_dep=nd, nifty_pick=npk)
        log(f"PICK on H1: {pick}  (H1 worst {p['h1']['worst']} vs deployed {d1['worst']})")
        log(f"  H2 test: total {p['h2']['total']} vs deployed {d2['total']} (need >= {round(0.8 * d2['total'])}), "
            f"worst {p['h2']['worst']} (need > -6000), win {p['h2']['win']} -> {'PASS' if h2ok else 'FAIL'}")
        log(f"  NIFTY: total {npk['total']} vs {nd['total']}, worst {npk['worst']} vs {nd['worst']} -> {'PASS' if nok else 'FAIL'}")
    log(f"\nNIFTY cross-check, all rules (ALL window)")
    for k, v in res["NIFTY"].items():
        al = v["all"]
        log(f"  {k:26s} n {al['n']:>3} win {al['win']:>5} total {al['total']:>7} worst {al['worst']:>7} exits {al['exits']:>3}")
    os.makedirs(OUT, exist_ok=True)
    json.dump({"verdict": verdict, "SENSEX": {k: {x: v[x] for x in ("all", "h1", "h2")} for k, v in sx.items()},
               "NIFTY": {k: {x: v[x] for x in ("all", "h1", "h2")} for k, v in res["NIFTY"].items()}},
              open(os.path.join(OUT, "results32.json"), "w"), indent=1, default=str)
    log(f"\nFETCH: {f.n_req} requests, {f.n_hit} cache hits, {len(f.failures)} failures -> {'CLEAN' if not f.failures else 'NOT CLEAN'}")
    for x in f.failures[:10]:
        log(f"  {x}")
    return 0 if not f.failures else 2


if __name__ == "__main__":
    sys.exit(main())
