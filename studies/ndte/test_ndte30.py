"""Offline test of the ndte30 simulator. Synthetic minute bars only. Any network call FAILS the test:
requests.Session.request and socket.create_connection are replaced before the study is imported.
Run: .venv/bin/python studies/ndte/test_ndte30.py"""
import os
import sys
import socket
from datetime import datetime

import requests


def _no_net(*a, **k):
    raise AssertionError("NETWORK CALL ATTEMPTED IN OFFLINE TEST")


requests.Session.request = _no_net
socket.create_connection = _no_net

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ndte30_time_losscut as S  # noqa: E402

LOT = 75
CR = 10.0                               # entry credit in the hand-built positions


def approx(a, b, tol=1e-6):
    assert abs(a - b) <= tol, f"{a} != {b}"


def path(points, day="2026-09-01"):
    """points: [(HH:MM, close)] -> Upstox-style candles, open = previous close (first open = close)."""
    out, prev = [], None
    for hm, c in points:
        o = c if prev is None else prev
        out.append([f"{day}T{hm}:00+05:30", o, max(o, c), min(o, c), c, 100, 0])
        prev = c
    return S.norm_candles(out, day)


def pos(short_pts, long_pts, typ="CE", ks=24600.0, kl=24800.0, entry="09:16"):
    ls, ll = S.Leg(path(short_pts)), S.Leg(path(long_pts))
    s0, _, _ = ls.entry_price(entry)
    l0, _, _ = ll.entry_price(entry)
    return dict(typ=typ, ks=ks, kl=kl, width=abs(kl - ks), lot=LOT, leg_s=ls, leg_l=ll, s0=s0, l0=l0,
                credit=round(s0 - l0, 2), entry_hm=entry, hybrid=False, late_legs=0)


def base_cost(p):
    return (p["s0"] + p["l0"]) * S.SLIP_PCT / 100 + S.BROKER * 4 / p["lot"]


def exit_extra(a, b, lot=LOT):
    return (a + b) * S.SLIP_PCT / 100 + S.BROKER * 4 / lot


# ── day 1: winner. short 12 -> 3 -> 1.0, long 2 -> 0.5 -> 0.1; settles OTM ─────────────────
WIN_S = [("09:15", 12.0), ("09:16", 12.0), ("10:30", 6.0), ("12:00", 3.0), ("15:29", 1.0)]
WIN_L = [("09:15", 2.0), ("09:16", 2.0), ("10:30", 1.0), ("12:00", 0.5), ("15:29", 0.1)]
# ── day 2: against early (10:30 spread = 18 -> loss 0.8x credit), recovers, settles OTM ──────
REC_S = [("09:15", 12.0), ("09:16", 12.0), ("10:30", 24.0), ("11:30", 8.0), ("13:00", 4.0), ("15:29", 1.5)]
REC_L = [("09:15", 2.0), ("09:16", 2.0), ("10:30", 6.0), ("11:30", 2.0), ("13:00", 1.0), ("15:29", 0.6)]
# ── day 3: trends against all day, settles beyond the wing (full-width loss) ───────────────
TRD_S = [("09:15", 12.0), ("09:16", 12.0), ("10:30", 30.0), ("13:00", 120.0), ("15:29", 260.0)]
TRD_L = [("09:15", 2.0), ("09:16", 2.0), ("10:30", 5.0), ("13:00", 30.0), ("15:29", 70.0)]


def test_winner_settlement_and_tp():
    p = pos(WIN_S, WIN_L)
    assert p["s0"] == 12.0 and p["l0"] == 2.0 and p["credit"] == CR
    # hold, no TP: spot below the short strike -> intrinsic 0 -> full credit minus base costs
    r = S.simulate(p, settle_close=24500.0, tp_frac=0)
    assert r["kind"] == "SETTLE"
    approx(r["net_pts"], CR - base_cost(p))
    approx(r["net_rs"], (CR - base_cost(p)) * LOT)
    # deployed TP-95: closes when the spread <= 0.5. 15:29 value is 0.9 -> no TP, settles
    r = S.simulate(p, settle_close=24500.0)
    assert r["kind"] == "SETTLE"
    # a TP-60 variant (level 4.0) skips 10:30 (value 5.0) and fires at 12:00 (value 2.5): fill
    # 3*1.01 - 0.5*0.99, and the exit pays the extra costs
    r = S.simulate(p, settle_close=24500.0, tp_frac=0.6)
    assert r["kind"] == "TP" and r["exit_hm"] == "12:00", r
    fill = 3.0 * 1.01 - 0.5 * 0.99
    approx(r["net_pts"], CR - fill - base_cost(p) - exit_extra(3.0, 0.5))
    # a winner is never cut: it is not losing at any T
    for T in S.CUT_TIMES:
        assert S.simulate(p, 24500.0, cut_T=T, cut_L=0.0)["kind"] == "SETTLE"


def test_recovery_day_cut_only_when_losing_more_than_L():
    p = pos(REC_S, REC_L)
    # at 10:30 the spread is 24-6 = 18 -> loss 8 = 0.8x credit
    r = S.simulate(p, 24500.0, cut_T="10:30", cut_L=0.5)
    assert r["kind"] == "CUT" and r["exit_hm"] == "10:30"
    fill = 24.0 * 1.01 - 6.0 * 0.99
    approx(r["net_pts"], CR - fill - base_cost(p) - exit_extra(24.0, 6.0))
    assert r["net_rs"] < 0
    # L=1.0 needs a loss > 10: no cut, trade recovers and settles as a winner
    r = S.simulate(p, 24500.0, cut_T="10:30", cut_L=1.0)
    assert r["kind"] == "SETTLE" and r["net_rs"] > 0
    # L=0 (any loss) at 10:45: the last bars <= 10:45 are the 10:30 bars -> still 18 -> cut at 10:45
    r = S.simulate(p, 24500.0, cut_T="10:45", cut_L=0.0)
    assert r["kind"] == "CUT" and r["exit_hm"] == "10:45"
    # at 12:00 it has recovered (8-2 = 6 < credit): no cut at any L
    for L in S.CUT_LS:
        assert S.simulate(p, 24500.0, cut_T="12:00", cut_L=L)["kind"] == "SETTLE"
    # boundary: a loss of exactly L x credit is NOT cut (strictly more than)
    q = pos(REC_S, REC_L)
    q["credit"] = 9.0                         # 18 - 9 = 9 = exactly 1.0 x 9
    assert S.simulate(q, 24500.0, cut_T="10:30", cut_L=1.0)["kind"] == "SETTLE"


def test_trend_day_full_width_vs_cut():
    p = pos(TRD_S, TRD_L)
    r = S.simulate(p, settle_close=25000.0)   # beyond the wing: cost = width 200
    assert r["kind"] == "SETTLE"
    approx(r["net_pts"], CR - 200.0 - base_cost(p))
    c = S.simulate(p, 25000.0, cut_T="13:00", cut_L=0.0)
    assert c["kind"] == "CUT"
    fill = 120.0 * 1.01 - 30.0 * 0.99
    approx(c["net_pts"], CR - fill - base_cost(p) - exit_extra(120.0, 30.0))
    assert c["net_rs"] > r["net_rs"]           # the cut loses less than full width
    # settlement between the strikes: close 24700 -> cost 100
    approx(S.simulate(p, 24700.0, tp_frac=0)["net_pts"], CR - 100.0 - base_cost(p))


def test_put_settlement():
    p = pos(WIN_S, WIN_L, typ="PE", ks=24400.0, kl=24200.0)
    approx(S.simulate(p, 24300.0, tp_frac=0)["net_pts"], CR - 100.0 - base_cost(p))   # 100 ITM
    approx(S.simulate(p, 24100.0, tp_frac=0)["net_pts"], CR - 200.0 - base_cost(p))   # capped at width
    approx(S.simulate(p, 24500.0, tp_frac=0)["net_pts"], CR - base_cost(p))


def test_timestamp_join_with_missing_bar():
    # the wing has NO 10:30 bar; its last bar <= 10:30 is 10:00 (value 4.0)
    short = [("09:15", 12.0), ("09:16", 12.0), ("10:00", 15.0), ("10:30", 25.0), ("15:29", 1.0)]
    wing = [("09:15", 2.0), ("09:16", 2.0), ("10:00", 4.0), ("11:00", 1.0), ("15:29", 0.1)]
    p = pos(short, wing)
    assert p["leg_s"].close_at("10:30") == 25.0 and p["leg_l"].close_at("10:30") == 4.0
    r = S.simulate(p, 24500.0, cut_T="10:30", cut_L=1.0)       # 25-4 = 21 -> loss 11 > 10 -> cut
    assert r["kind"] == "CUT"
    approx(r["net_pts"], CR - (25.0 * 1.01 - 4.0 * 0.99) - base_cost(p) - exit_extra(25.0, 4.0))
    # a positional join (k-th short bar minus k-th wing bar) would have paired 25.0 with 1.0 (the
    # wing's 11:00 bar): spread 24, a different answer. The timestamp join must not do that.
    assert (p["leg_s"].bars[3][4] - p["leg_l"].bars[3][4]) != (25.0 - 4.0)
    # stale mark flag: a wing last printed > 15 min before T
    wing2 = [("09:15", 2.0), ("09:16", 2.0), ("15:29", 0.1)]
    p2 = pos(short, wing2)
    r2 = S.simulate(p2, 24500.0, cut_T="10:30", cut_L=0.0)
    assert r2["kind"] == "CUT" and r2["stale"] is True
    # a leg with no bar at or before t has no mark
    lone = S.Leg(path([("11:00", 5.0)]))
    assert lone.close_at("10:30") is None and lone.close_at("11:00") == 5.0


def test_entry_price_rules():
    leg = S.Leg(path([("09:15", 10.0), ("09:16", 11.0), ("09:40", 9.0)]))
    assert leg.entry_price("09:16") == (10.0, "exact", "09:16")      # open of 09:16 = prev close
    assert leg.entry_price("09:18") == (11.0, "prior", "09:16")      # 2 min stale close
    assert leg.entry_price("09:35")[1] == "late"                     # first print 5 min later
    assert leg.entry_price("09:25")[1] == "no_print"                 # 9 min stale, 15 min to next
    assert leg.entry_price("09:35", allow_late=False)[1] == "no_print"


def _chain(step, lo, hi, lot):
    ks = [float(k) for k in range(lo, hi + 1, step)]
    return {t: [(k, f"{t}{int(k)}", lot) for k in ks] for t in ("CE", "PE")}


def _flat_prices(table):
    """get_bars stub: key -> one bar at 09:15 and 09:16 at a fixed price."""
    def g(key):
        px = table.get(key, 0.0)
        return path([("09:15", px), ("09:16", px), ("15:29", px)])
    return g


def test_deployed_selection_nifty():
    b = S.BOOKS["NIFTY"]
    spot = S.Leg(path([("09:15", 24400.0), ("09:16", 24400.0), ("09:17", 24410.0)]))
    ch = _chain(50, 23000, 26000, 75)
    prices = {"CE24500": 20.0, "CE24700": 5.0, "PE24150": 9.0, "PE23950": 2.0,
              "PE24300": 20.0, "PE24100": 6.0, "CE24650": 10.0, "CE24850": 1.0}
    ctx = dict(day="2026-09-01", rv5=0.5, ret5=0.2, spot=spot, chain=ch)
    ps, why = S.decide(b, ctx, "09:16", b["otm"], _flat_prices(prices))
    # CE side (ret5 < 1): short nearest 24400*1.005 = 24522 -> 24500; wing 24700. Hybrid PE nearest
    # 24400*0.99 = 24156 -> 24150, wing 23950, credit 7 on 200 = 0.035 < 0.08 -> NOT added.
    assert why == "entered" and len(ps) == 1, (why, ps)
    assert (ps[0]["typ"], ps[0]["ks"], ps[0]["kl"], ps[0]["credit"]) == ("CE", 24500.0, 24700.0, 15.0)
    # rich hybrid side: credit 7 -> 17 (c/w 0.085 >= 0.08) -> added
    prices2 = dict(prices, PE24150=19.0)
    ps, _ = S.decide(b, ctx, "09:16", b["otm"], _flat_prices(prices2))
    assert len(ps) == 2 and ps[1]["hybrid"] and ps[1]["typ"] == "PE" and ps[1]["ks"] == 24150.0
    # FLIP: ret5 >= 1.0 -> PE side, short nearest 24400*0.995 = 24278 -> 24300 (wing 24100)
    ctx_f = dict(ctx, ret5=1.2)
    ps, _ = S.decide(b, ctx_f, "09:16", b["otm"], _flat_prices(prices))
    assert ps[0]["typ"] == "PE" and ps[0]["ks"] == 24300.0 and ps[0]["kl"] == 24100.0
    # rv5 >= 0.9 -> skip; blackout -> skip
    assert S.decide(b, dict(ctx, rv5=0.95), "09:16", 0.005, _flat_prices(prices))[1] == "rv5_skip"
    assert S.decide(b, dict(ctx, day="2024-06-04"), "09:16", 0.005, _flat_prices(prices))[1] == "blackout"
    # thin credit: < 0.02% of 24400 = 4.88 pts
    thin = dict(prices, CE24500=8.0, CE24700=4.0)
    assert S.decide(b, ctx, "09:16", 0.005, _flat_prices(thin))[1] == "thin_credit"
    # restrike at a later entry with a larger distance: spot 09:17 = 24410? entry 09:16 uses its open
    ps, _ = S.decide(b, ctx, "09:16", 0.01, _flat_prices(dict(prices, CE24650=10.0, CE24850=1.0)))
    assert ps[0]["ks"] == 24650.0       # 24400*1.01 = 24644 -> 24650


def test_deployed_selection_sensex():
    b = S.BOOKS["SENSEX"]
    spot = S.Leg(path([("09:15", 75000.0), ("09:16", 75000.0)]))
    ch = _chain(100, 70000, 80000, 20)
    # short nearest 75375 -> 75400 (tie 75300/75400? 75375 is 25 from 75400, 75 from 75300);
    # wing nearest 75400 + 622.5 = 76022.5 -> 76000; width 600
    prices = {"CE75400": 40.0, "CE76000": 10.0}
    ctx = dict(day="2026-09-03", rv5=2.0, ret5=5.0, spot=spot, chain=ch)  # rv5/ret5 must be ignored
    ps, why = S.decide(b, ctx, "09:16", b["otm"], _flat_prices(prices))
    assert why == "entered" and len(ps) == 1
    assert (ps[0]["typ"], ps[0]["ks"], ps[0]["kl"], ps[0]["width"], ps[0]["lot"]) == ("CE", 75400.0, 76000.0, 600.0, 20)
    # c/w floor 0.04: credit 20 on 600 = 0.033 -> skip
    assert S.decide(b, ctx, "09:16", b["otm"], _flat_prices({"CE75400": 30.0, "CE76000": 10.0}))[1] == "low_cw"


def test_weights_and_views():
    days = ["2026-06-01", "2026-07-30", "2026-08-04", "2026-10-01"]
    w = S.recency_weights(days)
    assert w["2026-10-01"] >= 1.0 - 1e-12
    approx(w["2026-07-30"], 0.5 ** (63 / 45.0))
    assert w["2026-08-04"] >= 3 * w["2026-07-30"] - 1e-12 and w["2026-10-01"] >= 3 * w["2026-07-30"] - 1e-12
    v = S.views([("2026-06-01", 100.0, "SETTLE"), ("2026-07-30", -50.0, "CUT"),
                 ("2026-08-04", 30.0, "TP"), ("2026-10-01", -10.0, "SETTLE")], w)
    assert v["post"]["n"] == 2 and v["pre"]["n"] == 2 and v["full"]["n"] == 4
    approx(v["full"]["total"], 70.0)
    approx(v["full"]["avg_loss"], -30.0)
    assert v["full"]["n_cut"] == 1 and v["full"]["n_tp"] == 1
    sw = sum(w.values())
    approx(v["wtd"]["w_mean"], (100 * w["2026-06-01"] - 50 * w["2026-07-30"] + 30 * w["2026-08-04"]
                                - 10 * w["2026-10-01"]) / sw)


def test_spearman_and_pick():
    approx(S.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
    approx(S.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)

    def mk(label, pre, post, worst):
        return dict(label=label, v=dict(full=dict(total=pre + post, worst=worst), pre=dict(total=pre),
                                        post=dict(total=post), wtd=dict(w_total=pre * 0.1 + post)))
    base = mk("base", 100, 10, -500)["v"]
    cells = [mk("base", 100, 10, -500), mk("A", 120, 5, -400), mk("B", 50, 40, -900)]
    pk = S.pick_and_check(cells, base)
    assert pk["recommended"] == "B" and "full-window total below baseline" in pk["flags"]
    assert "full-window worst trade worse than baseline" in pk["flags"]
    assert pk["pre_pick"] == "A" and pk["pre_pick_post_total"] == 5
    assert pk["full_winner"] == "A" and pk["full_winner_post_rank"] == 3


def test_fetch_window_guard_and_cache_only():
    ist = S.C.IST
    wed = lambda h, m: ist.localize(datetime(2026, 10, 7, h, m))
    assert not S.fetch_window_open(wed(10, 0), False)
    assert S.fetch_window_open(wed(10, 0), True)
    assert not S.fetch_window_open(wed(14, 45), True)
    assert not S.fetch_window_open(wed(15, 44), True)
    assert S.fetch_window_open(wed(15, 45), False)
    assert S.fetch_window_open(wed(8, 29), False)
    assert S.fetch_window_open(ist.localize(datetime(2026, 10, 10, 11, 0)), False)   # Saturday
    f = S.Fetcher(cache_only=True)
    try:
        f.get_json("/x", "thing")
        raise AssertionError("cache-only must not return data")
    except S.FetchFailed:
        pass
    assert len(f.failures) == 1 and f.n_req == 0
    # a closed window stops before any request is made
    g = S.Fetcher(allow_daytime=True, now_fn=lambda: wed(14, 50))
    try:
        g.get_json("/x", "thing")
        raise AssertionError("window must be closed")
    except S.WindowClosed:
        pass
    assert g.n_req == 0


# ── end-to-end: the whole driver on a fake data layer (no network, no real cache) ───────────
class _FakeF:
    def __init__(self):
        self.failures, self.n_req, self.n_hit, self.n_429 = [], 0, 0, 0


class _FakeData:
    """Synthetic market: weekday closes drift; each expiry day the index moves linearly from its
    open to its close; option price = intrinsic + time value decaying to 0 at 15:30."""

    def __init__(self, book, exps, fail_day=None):
        import math
        import random
        from datetime import date, timedelta
        self.f, self.book, self.exps, self.fail_day, self.math = _FakeF(), book, exps, fail_day, math
        rnd = random.Random(7)
        lvl = 24000.0 if book["name"] == "NIFTY" else 78000.0
        self.dl, d = {}, date(2026, 4, 1)
        while d <= date(2026, 10, 6):
            if d.weekday() < 5:
                o = lvl
                lvl *= 1 + rnd.uniform(-0.006, 0.0065)
                self.dl[d.isoformat()] = [o, max(o, lvl), min(o, lvl), lvl]
            d += timedelta(days=1)

    def expiries(self, book):
        return self.exps

    def daily(self, book, a, b):
        return {k: v for k, v in self.dl.items() if a <= k <= b}

    def contracts(self, book, e):
        o = self.dl[e][0]
        step = 50 if book["name"] == "NIFTY" else 100
        c0 = int(o * 0.95) // step * step
        ks = [float(k) for k in range(c0, int(o * 1.05), step)]
        lot = 75 if book["name"] == "NIFTY" else 20
        return {t: [(k, f"{t}|{int(k)}|{e}", lot) for k in ks] for t in ("CE", "PE")}

    def _spot(self, e, m):
        o, _, _, c = self.dl[e]
        return o + (c - o) * (m - 555) / (929 - 555)

    def spot_1m(self, book, e):
        return S.norm_candles([[f"{e} {S.m2hm(m)}:00", self._spot(e, m), 0, 0, self._spot(e, m)]
                               for m in range(555, 930)], e), "db"

    def candles(self, key, e):
        if e == self.fail_day:
            self.f.failures.append((f"candles {key} {e}", "simulated failure"))
            raise S.FetchFailed(key)
        t, k, _ = key.split("|")
        k = float(k)
        rows = []
        for m in range(555, 930):
            sp = self._spot(e, m)
            intr = max(0.0, sp - k) if t == "CE" else max(0.0, k - sp)
            tv = 0.012 * sp * self.math.exp(-abs(sp - k) / (0.004 * sp)) * (930 - m) / 375
            px = round(intr + tv, 2)
            if px > 0.05:
                rows.append([f"{e}T{S.m2hm(m)}:00+05:30", px, px, px, px, 1, 0])
        return S.norm_candles(rows, e)


def test_end_to_end_offline(tmp=None):
    import tempfile
    tmp = tempfile.mkdtemp()
    S.OUT_JSON, S.OUT_MD = os.path.join(tmp, "r.json"), os.path.join(tmp, "r.md")
    results, lines = {}, []
    for nm, wd in (("NIFTY", 1), ("SENSEX", 3)):
        book = S.BOOKS[nm]
        from datetime import date, timedelta
        exps, d = [], date(2026, 5, 1)
        while d <= date(2026, 10, 2):
            if d.weekday() == wd:
                exps.append(d.isoformat())
            d += timedelta(days=1)
        data = _FakeData(book, exps, fail_day=exps[3] if nm == "SENSEX" else None)
        R = S.run_book(data, book, "2026-05-01", lines.append)
        A = S.analyse(book, R)
        results[nm] = (book, A, R, dict(n=0))
        assert len(A["cells"]) == len(S.CUT_TIMES) * len(S.CUT_LS) == 147
        assert len(A["ecells"]) == 15
        assert A["base"]["full"]["n"] > 5 and A["base"]["post"]["n"] > 0
        # the deployed entry cell of study B equals study A's baseline (same trades, same exit)
        eb = [c for c in A["ecells"] if c["hm"] == "09:16" and c["d"] == book["otm"]][0]["v"]["full"]
        approx(eb["total"], A["base"]["full"]["total"], 1e-6)
        # L so large it never triggers -> identical to baseline
        far = [c for c in A["cells"] if c["T"] == "15:25" and c["L"] == 3.0][0]["v"]["full"]
        assert far["n_cut"] <= A["base"]["full"]["n"]
        integ = dict(requests=0, cache_hits=0, n_429=0, failures=len(data.f.failures),
                     failure_list=data.f.failures, clean=not data.f.failures)
        S.report(book, A, R, integ, lines.append)
        if nm == "SENSEX":
            assert R["fail_days"] == [] and data.f.failures, "a candle failure must be counted"
            assert R["skips_tl"].get("FETCH_FAILED", 0) >= 1
    S.write_outputs(results, dict(requests=0, cache_hits=0, n_429=0, failures=1, failure_list=[], clean=False))
    import json
    js = json.load(open(S.OUT_JSON))
    assert js["clean"] is False and set(js["books"]) == {"NIFTY", "SENSEX"}
    assert len(js["books"]["NIFTY"]["losscut_grid"]) == 147
    assert "NOT CLEAN" in open(S.OUT_MD).read()
    # the synthetic market has no losing day, so no cut can help: the pick must be the deployed book
    for nm in results:
        assert results[nm][1]["tl_pick"]["recommended"] == "NO CUT (deployed)", results[nm][1]["tl_pick"]
    print("\n".join(lines[:6] + ["   ..."] + [l for l in lines if "RECOMMENDED" in l or "PICK ON" in l]))


def test_request_budget_waits_when_full():
    import time as _t
    f = S.Fetcher(gap=0.1, log=lambda s: None)
    assert f.gap == 0.5                       # never faster than 0.5 s
    slept = []
    f._times = [_t.time() - 10] * f.BUDGET_30M
    f._sleep = lambda s: (slept.append(s), f._times.clear())
    f._budget()
    assert slept and 0 < slept[0] <= 120      # waited (in chunks of at most 2 min) instead of calling
    f._times = [_t.time() - 1900] * f.BUDGET_30M  # older than 30 min -> dropped, no wait
    slept.clear()
    f._budget()
    assert not slept


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"ALL {len(tests)} TESTS PASSED (no network)")
