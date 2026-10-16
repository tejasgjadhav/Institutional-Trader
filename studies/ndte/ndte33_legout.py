"""ndte33 — leg-out variant of the 0DTE loss cap (user, 16-Oct-2026): when the open loss reaches the
cap, buy back ONLY the sold option, keep the bought option and sell it at the close (two exits tested:
the 15:29 bar close with slippage, and intrinsic settlement). Cache only. Compared with closing both legs.

Run: .venv/bin/python studies/ndte/ndte33_legout.py
"""
import os
import sys
import json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ndte30_time_losscut as M          # noqa: E402
import ndte32_loss_cap as P              # noqa: E402

CAPS = (3500, 5000, 7000)


def legout(pos, spot, close, cap, long_exit):
    base = M.simulate(pos, close)
    hm = P.trigger(("R", cap), pos, spot)
    if hm is None or (base["kind"] == "TP" and base["exit_hm"] <= hm):
        return base, None
    ls, ll = pos["leg_s"], pos["leg_l"]
    a = ls.close_at(hm)
    if a is None:
        return base, None
    lot, credit = pos["lot"], pos["credit"]
    cost0 = (pos["s0"] + pos["l0"]) * M.SLIP_PCT / 100 + M.BROKER * 4 / lot
    short_buy = a * (1 + M.EXIT_SLIP) + a * M.SLIP_PCT / 100 + M.BROKER * 2 / lot
    if long_exit == "bar":
        c = ll.close_at(M.LAST_BAR) or 0.0
        long_sell = c * (1 - M.EXIT_SLIP) - c * M.SLIP_PCT / 100 - M.BROKER * 2 / lot
    else:
        c = max(0.0, close - pos["kl"]) if pos["typ"] == "CE" else max(0.0, pos["kl"] - close)
        long_sell = c
    net = pos["s0"] - pos["l0"] - cost0 - short_buy + long_sell
    long_at_hm = ll.close_at(hm) or 0.0
    return dict(net_rs=net * lot, kind="LEGOUT", exit_hm=hm), (long_sell - long_at_hm * (1 - M.EXIT_SLIP)) * lot


def main():
    f = M.Fetcher(cache_only=True, log=print)
    data = M.Data(f)
    out = {}
    for nm in ("SENSEX", "NIFTY"):
        days = P.collect(data, M.BOOKS[nm], print)
        print(f"\n{nm}  (Rs per lot after costs; H1 Oct-24..Sep-25, H2 Oct-25 on)")
        print(f"{'variant':34s} {'n':>3} {'win':>5} {'total':>8} {'worst':>8} {'maxDD':>8} {'H1':>8} {'H2':>8} {'exits':>5}  long-leg gain vs closing both")
        rowsets = {"deployed (hold)": [(e, M.simulate(p, c)["net_rs"], "", None) for e, p, s, c in days]}
        for cap in CAPS:
            rowsets[f"cap Rs{cap}: close both"] = [(e, *(lambda r: (r["net_rs"], r["kind"]))(P.evaluate(p, s, c, ("R", cap))), None) for e, p, s, c in days]
            for le in ("bar", "settle"):
                rs = []
                for e, p, s, c in days:
                    r, gain = legout(p, s, c, cap, le)
                    rs.append((e, r["net_rs"], r["kind"], gain))
                rowsets[f"cap Rs{cap}: leg out, long to {le}"] = rs
        out[nm] = {}
        for k, rows in rowsets.items():
            st = P.stats([(r[0], r[1], "EXIT" if r[2] in ("EXIT", "LEGOUT") else r[2]) for r in rows])
            h1 = sum(r[1] for r in rows if r[0] < P.HALF); h2 = sum(r[1] for r in rows if r[0] >= P.HALF)
            gains = [r[3] for r in rows if r[3] is not None]
            gtxt = f"{len(gains)} exits: +{sum(1 for g in gains if g > 0)} / -{sum(1 for g in gains if g <= 0)}, net Rs{sum(gains):,.0f}" if gains else ""
            print(f"{k:34s} {st['n']:>3} {st['win']:>5} {st['total']:>8} {st['worst']:>8} {st['maxdd']:>8} {round(h1):>8} {round(h2):>8} {st['exits']:>5}  {gtxt}")
            out[nm][k] = dict(st, h1=round(h1), h2=round(h2))
    json.dump(out, open(os.path.join(M.ROOT, "research", "rally_guard", "results33.json"), "w"), indent=1)
    print(f"\nFETCH: {f.n_req} requests, {f.n_hit} cache hits, {len(f.failures)} failures")


if __name__ == "__main__":
    main()
