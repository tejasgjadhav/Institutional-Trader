"""ndte30 — two studies on the DEPLOYED 0DTE index books (NIFTY Tue, SENSEX Thu), real Upstox
expired-instrument 1-minute option candles, Oct'24 -> latest expiry.

STUDY A  TIME-CONDITIONAL LOSS CUT (T x L). Deployed entry (09:16, deployed strike rule, all gates).
         At clock time T, if the open spread is losing by MORE than L x entry credit (mark = last 1-min
         close <= T of each leg, legs joined BY TIMESTAMP), buy it back at T; else hold to the
         deployed exit (95% take-profit, then intrinsic settlement vs the official index close).
         T = 10:30..15:15 every 15 min + 15:25.  L in {0, .25, .5, 1, 1.5, 2, 3}.  L=0 = any loss.
         After 15:15 the index print is frozen in the closing auction; the cut is decided on the
         OPTION spread value only, which is how it is always decided here.
STUDY B  ENTRY TIME x STRIKE DISTANCE. Entry 09:16/09:30/09:45/10:00/10:15, short strike d in
         {0.5, 0.75, 1.0}% OTM of the index AT the entry time (restrike), deployed wing, FLIP side,
         hybrid add (NIFTY), every deployed gate, deployed exit.

Deployed rules replicated (engine/zero_dte.py, engine/dte_multi.py, engine/config.py, read 7-Oct-2026):
  NIFTY : skip ZERO_DTE_ELECTION_BLACKOUT days; skip if rv5 >= 0.9 (std of the last 5 daily log
          returns, closes strictly before the day, ddof=0); FLIP: ret5 = last prior close / close 5
          sessions earlier - 1 >= +1.0% -> sell PE spread, else CE. Short = listed strike nearest
          spot*(1 +/- 0.5%), wing = strike nearest short +/- 200; skip if width < 100 or geometry
          wrong; skip if credit <= 0 or credit < 0.02% of spot. HYBRID ADD: opposite side, short
          nearest spot*(1 -/+ 1.0%), same 200 wing, added only if its own credit/width >= 0.08.
  SENSEX: skip blackout days; CE only, no rv5, no FLIP; short nearest spot*1.005, wing nearest
          short + 0.83% of spot; skip if width < half of that; skip credit <= 0 or credit/width < 0.04.
  Both  : entry once at 09:16; EARLY PROFIT CLOSE when spread cost <= 5% of credit
          (ZERO_DTE_EARLY_CLOSE_FRAC 0.95); otherwise intrinsic vs the expiry-day daily close.
GAPS vs the live engine (cannot be closed offline):
  * entry premiums are the 09:16 1-min bar OPEN (traded print), the engine uses the bid/ask MID;
  * spot at entry is the index 1-min bar open at the entry minute, the engine uses the live LTP;
  * the engine checks take-profit every 120 s on mid quotes, here every 1-min bar close;
  * WIN here = net Rs > 0 after costs; the engine's WIN flag is gross pnl_pts > 0.

Costs (as ndte7): 2.5% of entry premiums (s0+l0) + Rs20 x 4 legs per lot. Any EARLY exit (loss cut
or take-profit) pays the same again on its exit premiums (2.5% of exit s+l + Rs20 x 4 per lot) and
fills at short*1.01 - long*0.99. Rs are per lot, lot from the contract data.

Views on every table (user, 7-Oct-2026): POST-CAS (expiries >= 2026-08-03, the closing-auction
regime), RECENCY-WEIGHTED full window (45-calendar-day half-life back from the latest expiry, every
post-CAS trade weighted >= 3x the heaviest pre-CAS trade), FULL unweighted. Recommendation is picked
on the recency-weighted total; out-of-sample check = pick on PRE-CAS, test on POST-CAS.

TOKEN RULE: the Upstox token is shared with the live engine. Default: refuses to fetch between
08:30 and 15:45 IST on weekdays. --allow-daytime (user-authorised 7-Oct-2026) allows fetching until
14:45 IST and stops cleanly there, cache kept; rerun the same command after 15:45 to resume.
Calls are spaced 2 s apart by default (--gap, never below 0.5 s) and capped at 1000 per rolling
30 minutes (Upstox's per-user cap is 2000, shared with the engine); HTTP 429 waits 60 s and retries. Every failed fetch is COUNTED (FETCH
INTEGRITY line) and never treated as "no trade". --cache-only never touches the network.

Run (after 15:45, or with the daytime flag):  .venv/bin/python studies/ndte/ndte30_time_losscut.py
Cache: data/ndte30_cache/   Outputs: studies/ndte/ndte30_results.json, studies/ndte/ndte30_summary.md
Offline test: .venv/bin/python studies/ndte/test_ndte30.py
"""
import os
import sys
import json
import time
import bisect
import sqlite3
import argparse
from datetime import datetime, date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from engine import config as C                         # local only: reads .env, no network
from engine.dte_multi import BOOKS as _DM_BOOKS         # creates a requests.Session, no network

CACHE = os.path.join(ROOT, "data", "ndte30_cache")
DB = os.path.join(ROOT, "data", "market_history.db")
OUT_JSON = os.path.join(HERE, "ndte30_results.json")
OUT_MD = os.path.join(HERE, "ndte30_summary.md")

START = "2024-10-01"
CAS_START = "2026-08-03"
HALF_LIFE_DAYS = 45.0
POST_MIN_MULT = 3.0

SLIP_PCT = 2.5
BROKER = 20.0
EXIT_SLIP = 0.01
TP_FRAC = C.ZERO_DTE_EARLY_CLOSE_FRAC
LAST_BAR = "15:29"            # options trade to 15:30; the last 1-min bar starts 15:29
PRIOR_MAX_MIN = 5             # entry may use the close of a leg's bar at most 5 min before entry
LATE_MAX_MIN = 9              # ... or the open of its first bar at most 9 min after (counted)
STALE_MIN = 15                # a cut mark older than this on either leg is counted as stale

CUT_TIMES = [f"{m // 60:02d}:{m % 60:02d}" for m in range(10 * 60 + 30, 15 * 60 + 16, 15)] + ["15:25"]
CUT_LS = [0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0]
ENTRY_TIMES = ["09:16", "09:30", "09:45", "10:00", "10:15"]
DISTS = [0.005, 0.0075, 0.01]
DEPLOYED_ENTRY = C.ZERO_DTE_SCAN_AFTER                  # "09:16"

_sx = [b for b in _DM_BOOKS if b["name"] == "SENSEX"][0]
BOOKS = {
    "NIFTY": dict(name="NIFTY", key="NSE_INDEX|Nifty 50", idx_sym="NIFTY",
                  otm=C.ZERO_DTE_OTM_PCT, wing_pts=float(C.ZERO_DTE_WIDTH_PTS), wing_pct=None,
                  rv5_max=C.ZERO_DTE_RV5_MAX, min_credit_pct=C.ZERO_DTE_MIN_CREDIT_PCT,
                  flip_ret5=C.ZERO_DTE_FLIP_RET5, min_cw=0.0,
                  hybrid=C.ZERO_DTE_HYBRID_ENABLED, hyb_otm=C.ZERO_DTE_HYBRID_OTM,
                  hyb_min_cw=C.ZERO_DTE_HYBRID_MIN_CW),
    "SENSEX": dict(name="SENSEX", key=_sx["spot_key"], idx_sym="SENSEX",
                   otm=_sx["otm"], wing_pts=None, wing_pct=_sx["wing_pct"],
                   rv5_max=0.0, min_credit_pct=0.0, flip_ret5=0.0, min_cw=C.ZERO_DTE_MULTI_MIN_CW,
                   hybrid=False, hyb_otm=0.0, hyb_min_cw=0.0),
}
BLACKOUT = set(C.ZERO_DTE_ELECTION_BLACKOUT or [])


# ════════════════════════════ pure core (no I/O) ════════════════════════════
def hm2m(hm):
    return int(hm[:2]) * 60 + int(hm[3:5])


def m2hm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def norm_candles(cs, day):
    """Upstox / idx_1m rows [ts, o, h, l, c, ...] -> sorted [(HH:MM, o, h, l, c)] for `day` only,
    bars from 15:30 on dropped. Duplicate minutes keep the last row."""
    out = {}
    for c in cs or []:
        ts = str(c[0])
        if ts[:10] != day:
            continue
        hm = ts[11:16]
        if hm > LAST_BAR:
            continue
        out[hm] = (hm, float(c[1]), float(c[2]), float(c[3]), float(c[4]))
    return [out[k] for k in sorted(out)]


class Leg:
    """1-minute bars of one contract (or the index) on one day, searchable by clock time."""

    def __init__(self, bars):
        self.bars = list(bars)
        self.hms = [b[0] for b in self.bars]

    def last_at(self, hm):
        """The last bar whose minute is <= hm (bar-start timestamps), or None."""
        i = bisect.bisect_right(self.hms, hm) - 1
        return self.bars[i] if i >= 0 else None

    def close_at(self, hm):
        b = self.last_at(hm)
        return b[4] if b else None

    def entry_price(self, hm, allow_late=True):
        """Price at the instant hm:00 -> (price, kind, minute) or (None, 'no_print', None).
        exact = open of the hm bar; prior = close of the last bar within PRIOR_MAX_MIN before hm;
        late = open of the first bar within LATE_MAX_MIN after hm (the leg did not print at hm)."""
        i = bisect.bisect_left(self.hms, hm)
        if i < len(self.hms) and self.hms[i] == hm:
            return self.bars[i][1], "exact", hm
        if i > 0 and hm2m(hm) - hm2m(self.hms[i - 1]) <= PRIOR_MAX_MIN:
            return self.bars[i - 1][4], "prior", self.hms[i - 1]
        if allow_late and i < len(self.hms) and hm2m(self.hms[i]) - hm2m(hm) <= LATE_MAX_MIN:
            return self.bars[i][1], "late", self.hms[i]
        return None, "no_print", None


def nearest(strikes, x):
    """Engine rule: min over the SORTED chain by |strike - x|; a tie keeps the lower strike."""
    return min(strikes, key=lambda k: abs(k - x))


def rv5_ret5(prior_closes):
    """(rv5 %, ret5 %) from closes strictly before the day, exactly as zero_dte._rv5."""
    import numpy as np
    cl = [float(c) for c in prior_closes][-6:]
    if len(cl) < 6:
        return None, None
    rv = float(np.std(np.diff(np.log(np.array(cl)))) * 100)
    return rv, float((cl[-1] / cl[0] - 1) * 100)


def pick_vertical(book, side_chain, typ, spot, otm):
    """Deployed strike rule for one vertical. side_chain = sorted [(strike, key, lot)] of one type.
    Returns (dict, None) or (None, reason)."""
    if not side_chain:
        return None, "no_chain"
    strikes = [c[0] for c in side_chain]
    sgn = 1 if typ == "CE" else -1
    ks = nearest(strikes, spot * (1 + sgn * otm))
    if book["wing_pts"]:
        kl = nearest(strikes, ks + sgn * book["wing_pts"])
        min_w = book["wing_pts"] * 0.5
    else:
        kl = nearest(strikes, ks + sgn * spot * book["wing_pct"])
        min_w = spot * book["wing_pct"] * 0.5
    width = abs(kl - ks)
    if width < min_w:
        return None, "clamped_chain"
    if (sgn == 1 and kl <= ks) or (sgn == -1 and kl >= ks):
        return None, "bad_geometry"
    by = {c[0]: c for c in side_chain}
    lot = int(by[ks][2] or by[kl][2] or 0)
    return dict(typ=typ, ks=ks, kl=kl, key_s=by[ks][1], key_l=by[kl][1], lot=lot, width=width), None


def _open_leg(v, entry_hm, get_bars):
    """Fetch both legs of vertical v and price them at entry. Returns (pos-ish dict, None) or
    (None, reason). get_bars may raise (fetch failure) - the caller counts that."""
    ls, ll = Leg(get_bars(v["key_s"])), Leg(get_bars(v["key_l"]))
    s0, ks_kind, _ = ls.entry_price(entry_hm)
    l0, kl_kind, _ = ll.entry_price(entry_hm)
    if s0 is None or l0 is None:
        return None, "no_print"
    late = (ks_kind == "late") + (kl_kind == "late")
    return dict(v, leg_s=ls, leg_l=ll, s0=s0, l0=l0, credit=round(s0 - l0, 2), late_legs=late,
                entry_hm=entry_hm), None


def decide(book, ctx, entry_hm, otm, get_bars, flip=True, hybrid=True, credit_gates=True):
    """The deployed scan for one book on one expiry day at entry_hm with short distance otm.
    ctx: day, rv5, ret5, spot (Leg of index bars), chain {CE:[...], PE:[...]}.
    Returns (positions, reason). positions may hold 2 entries (NIFTY FLIP side + hybrid add)."""
    day = ctx["day"]
    if day in BLACKOUT:
        return [], "blackout"
    rv, ret5 = ctx.get("rv5"), ctx.get("ret5")
    if book["rv5_max"] and rv is not None and rv >= book["rv5_max"]:
        return [], "rv5_skip"
    typ = "PE" if (flip and book["flip_ret5"] and ret5 is not None and ret5 >= book["flip_ret5"]) else "CE"
    spot, _, _ = ctx["spot"].entry_price(entry_hm, allow_late=False)
    if not spot:
        return [], "no_spot"
    v, why = pick_vertical(book, ctx["chain"].get(typ), typ, spot, otm)
    if v is None:
        return [], why
    p, why = _open_leg(v, entry_hm, get_bars)
    if p is None:
        return [], why
    if p["credit"] <= 0:
        return [], "no_credit"
    if credit_gates and book["min_credit_pct"] and p["credit"] < spot * book["min_credit_pct"] / 100:
        return [], "thin_credit"
    if credit_gates and book["min_cw"] and p["credit"] / p["width"] < book["min_cw"]:
        return [], "low_cw"
    if p["lot"] <= 0:
        return [], "no_lot"
    p.update(day=day, spot=spot, hybrid=False)
    out = [p]
    if hybrid and book["hybrid"]:
        htyp = "PE" if typ == "CE" else "CE"
        hv, _ = pick_vertical(book, ctx["chain"].get(htyp), htyp, spot, book["hyb_otm"])
        if hv is not None and hv["lot"] > 0:
            hp, _ = _open_leg(hv, entry_hm, get_bars)
            if hp is not None and hp["credit"] > 0 and hp["credit"] / hp["width"] >= book["hyb_min_cw"]:
                hp.update(day=day, spot=spot, hybrid=True)
                out.append(hp)
    return out, "entered"


def settle_cost(typ, ks, kl, width, close):
    if typ == "CE":
        si, li = max(0.0, close - ks), max(0.0, close - kl)
    else:
        si, li = max(0.0, ks - close), max(0.0, kl - close)
    return min(max(si - li, 0.0), width)


def simulate(pos, settle_close, tp_frac=TP_FRAC, cut_T=None, cut_L=None):
    """One position through the exit rule. Returns dict(net_pts, net_rs, kind, exit_hm, stale).
    kind: SETTLE | TP | CUT. Marks join the legs BY TIMESTAMP: the value at minute m is the close
    of each leg's last bar <= m, and both legs must have one."""
    ls, ll = pos["leg_s"], pos["leg_l"]
    credit, lot = pos["credit"], pos["lot"]
    base = (pos["s0"] + pos["l0"]) * SLIP_PCT / 100 + BROKER * 4 / lot
    tp_level = credit * (1 - tp_frac) if tp_frac else None

    def mark(hm):
        a, b = ls.close_at(hm), ll.close_at(hm)
        return None if a is None or b is None else (a, b)

    def early(hm, kind, a, b, stale=False):
        fill = a * (1 + EXIT_SLIP) - b * (1 - EXIT_SLIP)
        extra = (a + b) * SLIP_PCT / 100 + BROKER * 4 / lot
        net = credit - fill - base - extra
        return dict(net_pts=net, net_rs=net * lot, kind=kind, exit_hm=hm, stale=stale)

    def cut_check():
        v = mark(cut_T)
        if v is None:
            return None
        if (v[0] - v[1]) - credit > cut_L * credit:
            bs, bl = ls.last_at(cut_T), ll.last_at(cut_T)
            stale = max(hm2m(cut_T) - hm2m(bs[0]), hm2m(cut_T) - hm2m(bl[0])) > STALE_MIN
            return early(cut_T, "CUT", v[0], v[1], stale)
        return None

    timeline = sorted(set(h for h in ls.hms + ll.hms if pos["entry_hm"] <= h <= LAST_BAR))
    checked = cut_T is None
    for hm in timeline:
        if not checked and hm > cut_T:
            checked = True
            r = cut_check()
            if r:
                return r
        v = mark(hm)
        if tp_level is not None and v is not None and (v[0] - v[1]) <= tp_level:
            return early(hm, "TP", v[0], v[1])
        if not checked and hm == cut_T:
            checked = True
            r = cut_check()
            if r:
                return r
    if not checked:
        r = cut_check()
        if r:
            return r
    cost = settle_cost(pos["typ"], pos["ks"], pos["kl"], pos["width"], settle_close)
    net = credit - cost - base
    return dict(net_pts=net, net_rs=net * lot, kind="SETTLE", exit_hm="close", stale=False)


def recency_weights(days):
    """{day: weight}. 45-day half-life back from the latest day; every post-CAS day weighted at least
    POST_MIN_MULT x the heaviest pre-CAS day."""
    if not days:
        return {}
    latest = date.fromisoformat(max(days))
    dec = {d: 0.5 ** ((latest - date.fromisoformat(d)).days / HALF_LIFE_DAYS) for d in days}
    pre = [w for d, w in dec.items() if d < CAS_START]
    floor = POST_MIN_MULT * max(pre) if pre else 0.0
    return {d: (max(w, floor) if d >= CAS_START else w) for d, w in dec.items()}


def stats(trades, wmap=None):
    """trades: [(day, net_rs, kind)]. Unweighted stats, plus weighted ones when wmap is given."""
    n = len(trades)
    if not n:
        return dict(n=0)
    nets = [t[1] for t in trades]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x <= 0]
    s = dict(n=n, win_pct=100.0 * len(wins) / n,
             avg_win=sum(wins) / len(wins) if wins else 0.0,
             avg_loss=sum(losses) / len(losses) if losses else 0.0,
             total=sum(nets), mean=sum(nets) / n, worst=min(nets),
             n_cut=sum(1 for t in trades if t[2] == "CUT"),
             n_tp=sum(1 for t in trades if t[2] == "TP"))
    if wmap:
        ws = [wmap[t[0]] for t in trades]
        sw = sum(ws)
        s["w_win_pct"] = 100.0 * sum(w for w, x in zip(ws, nets) if x > 0) / sw
        s["w_mean"] = sum(w * x for w, x in zip(ws, nets)) / sw
        s["w_total"] = sum(w * x for w, x in zip(ws, nets))
    return s


def views(trades, wmap):
    post = [t for t in trades if t[0] >= CAS_START]
    pre = [t for t in trades if t[0] < CAS_START]
    return dict(full=stats(trades), post=stats(post), pre=stats(pre), wtd=stats(trades, wmap))


def _ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2.0 + 1
        i = j + 1
    return r


def spearman(a, b):
    if len(a) < 3:
        return None
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else None


def pick_and_check(cells, base):
    """cells: [{label, v: views}] with the deployed cell FIRST (it wins ties), base: its views. Recommendation by recency-weighted
    total; flags vs baseline; pick-on-pre / test-on-post; post rank of the full-window winner."""
    def g(c, view, k):
        return (c["v"].get(view) or {}).get(k, 0.0) or 0.0
    rec = max(cells, key=lambda c: g(c, "wtd", "w_total"))
    best_post = max(cells, key=lambda c: g(c, "post", "total"))
    full_win = max(cells, key=lambda c: g(c, "full", "total"))
    pre_pick = max(cells, key=lambda c: g(c, "pre", "total"))
    post_rank = 1 + sum(1 for c in cells if g(c, "post", "total") > g(full_win, "post", "total"))
    flags = []
    if g(rec, "full", "total") < (base["full"].get("total") or 0):
        flags.append("full-window total below baseline")
    if g(rec, "full", "worst") < (base["full"].get("worst") or 0):
        flags.append("full-window worst trade worse than baseline")
    return dict(
        recommended=rec["label"], recommended_views=rec["v"], flags=flags,
        best_post=best_post["label"], best_post_total=g(best_post, "post", "total"),
        pre_pick=pre_pick["label"], pre_pick_post_total=g(pre_pick, "post", "total"),
        baseline_post_total=base["post"].get("total", 0.0),
        full_winner=full_win["label"], full_winner_post_rank=post_rank, n_cells=len(cells),
        spearman_pre_vs_post=spearman([g(c, "pre", "total") for c in cells],
                                      [g(c, "post", "total") for c in cells]))


# ════════════════════════════ data layer (network) ════════════════════════════
class WindowClosed(Exception):
    pass


class FetchFailed(Exception):
    pass


class TokenInvalid(Exception):
    pass


def fetch_window_open(now, allow_daytime):
    """True when an Upstox call is allowed at IST time `now`. Weekends always; weekdays outside
    08:30-15:45; with allow_daytime, also 08:30-14:45."""
    if now.weekday() >= 5:
        return True
    hm = now.strftime("%H:%M")
    if hm < "08:30" or hm >= "15:45":
        return True
    return bool(allow_daytime) and hm < "14:45"


def _ist_now():
    return datetime.now(C.IST)


def _atomic_dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


class Fetcher:
    """Upstox caps a user at 2000 requests per 30 minutes (plus 500/min). The live engine shares the
    token, so this study keeps ITSELF under BUDGET_30M per rolling 30 minutes and spaces calls MIN_GAP
    apart. Run 1 (7-Oct-2026 09:05) used a 0.5 s gap, sent ~2,150 requests in 18 minutes, and stalled
    on the 30-minute cap; that is why the budget exists. On start the budget is seeded with the cache
    files written in the last 30 minutes, so a restart cannot burst either."""
    MIN_GAP = 2.0
    BUDGET_30M = 1000

    def __init__(self, allow_daytime=False, cache_only=False, now_fn=_ist_now, gap=None, log=print,
                 seed_from_cache=False):
        self.allow_daytime, self.cache_only, self.now_fn, self.log = allow_daytime, cache_only, now_fn, log
        self.gap = max(0.5, float(gap)) if gap else self.MIN_GAP
        self.n_req = self.n_hit = self.n_429 = 0
        self.failures = []            # (what, why)
        self._last = 0.0
        self._failed_keys = set()
        self._times = []
        if seed_from_cache and os.path.isdir(CACHE):
            cut = time.time() - 1800
            for dp, _, fs in os.walk(CACHE):
                for fn in fs:
                    try:
                        t = os.path.getmtime(os.path.join(dp, fn))
                    except OSError:
                        continue
                    if t > cut:
                        self._times.append(t)
            self._times.sort()
            if self._times:
                self.log(f"  budget seeded with {len(self._times)} requests from the last 30 min (cache mtimes)")

    def _budget(self):
        while True:
            now = time.time()
            self._times = [t for t in self._times if now - t < 1800]
            if len(self._times) < self.BUDGET_30M:
                return
            # wait until enough of the oldest requests age out to bring the count back under budget
            wait = 1800 - (now - self._times[len(self._times) - self.BUDGET_30M]) + 1
            self.log(f"  {self.now_fn():%H:%M:%S} 30-min budget full ({len(self._times)}/{self.BUDGET_30M}); "
                     f"waiting {wait:.0f}s")
            self._sleep(min(wait, 120))

    def fail(self, what, why):
        if what not in self._failed_keys:
            self._failed_keys.add(what)
            self.failures.append((what, why))
        raise FetchFailed(f"{what}: {why}")

    def _check_window(self):
        if not fetch_window_open(self.now_fn(), self.allow_daytime):
            raise WindowClosed(self.now_fn().strftime("%H:%M IST"))

    def _sleep(self, s):
        end = time.time() + s
        while time.time() < end:
            self._check_window()
            time.sleep(min(5.0, max(0.0, end - time.time())))

    def get_json(self, path, what, params=None):
        """GET UPSTOX_BASE+path -> json with status success. Raises FetchFailed / WindowClosed /
        TokenInvalid. Never returns a failure as data."""
        if self.cache_only:
            self.fail(what, "cache-only miss")
        from engine.data_fetcher import SESSION, UPSTOX_BASE
        errs = n429 = 0
        while True:
            self._check_window()
            self._budget()
            gap = time.time() - self._last
            if gap < self.gap:
                time.sleep(self.gap - gap)
            self._last = time.time()
            self._times.append(self._last)
            try:
                r = SESSION.get(UPSTOX_BASE + path, params=params, timeout=30)
            except Exception as e:
                errs += 1
                if errs >= 4:
                    self.fail(what, f"network: {type(e).__name__}")
                self._sleep(5)
                continue
            self.n_req += 1
            if r.status_code == 429:
                self.n_429 += 1
                n429 += 1
                if n429 > 30:
                    self.fail(what, "HTTP 429 thirty times")
                self.log(f"  {self.now_fn():%H:%M:%S} HTTP 429 on {what} (#{n429}); waiting 60s")
                self._sleep(60)
                continue
            if r.status_code == 401:
                raise TokenInvalid("HTTP 401 - Upstox token rejected; refresh .env and rerun")
            if r.status_code != 200:
                errs += 1
                if errs >= 4:
                    self.fail(what, f"HTTP {r.status_code}")
                self._sleep(5)
                continue
            try:
                j = r.json()
            except Exception:
                j = {}
            if j.get("status") != "success":
                errs += 1
                if errs >= 4:
                    self.fail(what, f"status {j.get('status')}")
                self._sleep(5)
                continue
            return j

    def cached(self, path, what, fetch_fn):
        if os.path.exists(path):
            self.n_hit += 1
            with open(path) as f:
                return json.load(f)
        if what in self._failed_keys:
            raise FetchFailed(what)
        v = fetch_fn()
        _atomic_dump(path, v)
        return v


def _enc(key):
    return key.replace("|", "%7C")


class Data:
    """All market data for the study. Option candles and contracts come from Upstox expired
    instruments, cached under data/ndte30_cache/. Index 1-min from data/market_history.db idx_1m
    first. Official closes from Upstox daily candles."""

    def __init__(self, fetcher):
        self.f = fetcher
        self._db = None

    def expiries(self, book):
        today = date.today().isoformat()
        p = os.path.join(CACHE, f"expiries_{book['name']}_{today}.json")

        def fx():
            j = self.f.get_json("/v2/expired-instruments/expiries", f"expiries {book['name']}",
                                params={"instrument_key": book["key"]})
            out = sorted(j.get("data") or [])
            if not out:
                self.f.fail(f"expiries {book['name']}", "empty list")
            return out
        return self.f.cached(p, f"expiries {book['name']}", fx)

    def daily(self, book, start, end):
        """{YYYY-MM-DD: [o, h, l, c]} official daily candles, fetched per calendar year."""
        p = os.path.join(CACHE, f"daily_{book['name']}_{start}_{end}.json")

        def fx():
            out = {}
            y0, y1 = int(start[:4]), int(end[:4])
            for y in range(y0, y1 + 1):
                a, b = max(start, f"{y}-01-01"), min(end, f"{y}-12-31")
                j = self.f.get_json(f"/v2/historical-candle/{_enc(book['key'])}/day/{b}/{a}",
                                    f"daily {book['name']} {y}")
                for c in j.get("data", {}).get("candles", []) or []:
                    out[c[0][:10]] = [float(c[1]), float(c[2]), float(c[3]), float(c[4])]
            if len(out) < 100:
                self.f.fail(f"daily {book['name']}", f"only {len(out)} daily candles")
            return out
        return self.f.cached(p, f"daily {book['name']}", fx)

    def contracts(self, book, e):
        """{CE: sorted [(strike, key, lot)], PE: [...]}"""
        p = os.path.join(CACHE, "contracts", f"{book['name']}_{e}.json")

        def fx():
            j = self.f.get_json("/v2/expired-instruments/option/contract", f"contracts {book['name']} {e}",
                                params={"instrument_key": book["key"], "expiry_date": e})
            out = j.get("data") or []
            if not out:
                self.f.fail(f"contracts {book['name']} {e}", "empty contract list")
            return out
        raw = self.f.cached(p, f"contracts {book['name']} {e}", fx)
        ch = {"CE": [], "PE": []}
        for c in raw:
            t = c.get("instrument_type")
            if t in ch:
                ch[t].append((float(c["strike_price"]), c["instrument_key"], int(c.get("lot_size") or 0)))
        for t in ch:
            ch[t].sort()
        return ch

    def candles(self, key, day):
        """Sorted 1-min bars for an expired contract on day. [] = fetched, no trades (legit)."""
        p = os.path.join(CACHE, "candles", day, key.replace("|", "_").replace(" ", "_") + ".json")

        def fx():
            j = self.f.get_json(f"/v2/expired-instruments/historical-candle/{_enc(key)}/1minute/{day}/{day}",
                                f"candles {key} {day}")
            return j.get("data", {}).get("candles", []) or []
        return norm_candles(self.f.cached(p, f"candles {key} {day}", fx), day)

    def _idx_db(self, sym, day):
        if not os.path.exists(DB):
            return []
        if self._db is None:
            self._db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        return self._db.execute("SELECT ts,o,h,l,c FROM idx_1m WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts",
                                (sym, day + " 09:00:00", day + " 15:31:00")).fetchall()

    def spot_1m(self, book, day):
        rows = self._idx_db(book["idx_sym"], day)
        bars = norm_candles(rows, day)
        if len(bars) >= 300:
            return bars, "db"
        p = os.path.join(CACHE, "spot1m", f"{book['name']}_{day}.json")

        def fx():
            j = self.f.get_json(f"/v3/historical-candle/{_enc(book['key'])}/minutes/1/{day}/{day}",
                                f"spot1m {book['name']} {day}")
            cs = j.get("data", {}).get("candles", []) or []
            if not cs:
                self.f.fail(f"spot1m {book['name']} {day}", "no index bars")
            return cs
        return norm_candles(self.f.cached(p, f"spot1m {book['name']} {day}", fx), day), "upstox"


# ════════════════════════════ study driver ════════════════════════════
def build_days(data, book, start):
    """Per expiry: ctx dict, or a skip reason. Fetch failures are re-raised to the caller's counter."""
    today = date.today().isoformat()
    exps = [e for e in data.expiries(book) if start <= e < today]
    d0 = (date.fromisoformat(start) - timedelta(days=45)).isoformat()
    yday = (date.today() - timedelta(days=1)).isoformat()
    daily = data.daily(book, d0, yday)
    sdays = sorted(daily)
    return exps, daily, sdays


def day_ctx(data, book, e, daily, sdays):
    prior = [daily[d][3] for d in sdays if d < e]
    rv, ret5 = rv5_ret5(prior)
    ctx = dict(day=e, rv5=rv, ret5=ret5, close=(daily.get(e) or [None] * 4)[3])
    return ctx


def run_book(data, book, start, log):
    exps, daily, sdays = build_days(data, book, start)
    log(f"[{book['name']}] {len(exps)} expiries {exps[0] if exps else '-'} -> {exps[-1] if exps else '-'}")
    skips_tl, skips_entry = {}, {}
    tl_positions = {}              # day -> positions at the deployed entry
    entry_positions = {}           # (hm, d) -> {day: positions}
    repro = {}                     # day -> [pos] (ndte7-style CE-only reproduction)
    days_ok = []
    fail_days = []
    for i, e in enumerate(exps, 1):
        ctx = day_ctx(data, book, e, daily, sdays)
        if ctx["close"] is None:
            data.f.failures.append((f"official close {book['name']} {e}", "missing from daily candles"))
            fail_days.append(e)
            continue
        cheap_skip = None
        if e in BLACKOUT:
            cheap_skip = "blackout"
        elif book["rv5_max"] and ctx["rv5"] is not None and ctx["rv5"] >= book["rv5_max"]:
            cheap_skip = "rv5_skip"
        if cheap_skip:
            days_ok.append(e)
            skips_tl[cheap_skip] = skips_tl.get(cheap_skip, 0) + 1
            for hm in ENTRY_TIMES:
                for d in DISTS:
                    k = f"{hm} d={d * 100:.2f}%"
                    skips_entry.setdefault(k, {}).setdefault(cheap_skip, 0)
                    skips_entry[k][cheap_skip] += 1
            continue
        try:
            ctx["chain"] = data.contracts(book, e)
            bars, _src = data.spot_1m(book, e)
            ctx["spot"] = Leg(bars)
        except FetchFailed:
            fail_days.append(e)
            continue
        days_ok.append(e)

        def get_bars(key, _e=e):
            return data.candles(key, _e)

        def run_cell(hm, d, **kw):
            try:
                return decide(book, ctx, hm, d, get_bars, **kw)
            except FetchFailed:
                return None, "FETCH_FAILED"

        pos, why = run_cell(DEPLOYED_ENTRY, book["otm"])
        skips_tl[why] = skips_tl.get(why, 0) + 1
        if pos:
            tl_positions[e] = pos
        for hm in ENTRY_TIMES:
            for d in DISTS:
                k = f"{hm} d={d * 100:.2f}%"
                p2, why2 = run_cell(hm, d)
                skips_entry.setdefault(k, {}).setdefault(why2, 0)
                skips_entry[k][why2] += 1
                if p2:
                    entry_positions.setdefault((hm, d), {})[e] = p2
        if book["name"] == "NIFTY" and e <= "2026-06-30":
            p3, _ = run_cell(DEPLOYED_ENTRY, book["otm"], flip=False, hybrid=False, credit_gates=False)
            if p3:
                repro[e] = p3
        if i % 10 == 0:
            log(f"  [{book['name']}] {i}/{len(exps)} days · requests {data.f.n_req} · cache hits "
                f"{data.f.n_hit} · 429s {data.f.n_429} · failures {len(data.f.failures)}")
    return dict(exps=exps, daily=daily, days_ok=days_ok, fail_days=fail_days, skips_tl=skips_tl,
                skips_entry=skips_entry, tl=tl_positions, entry=entry_positions, repro=repro)


def _trades(pos_by_day, daily, **kw):
    out = []
    for e in sorted(pos_by_day):
        for p in pos_by_day[e]:
            r = simulate(p, daily[e][3], **kw)
            out.append((e, r["net_rs"], r["kind"], r, p))
    return out


def _tk(trs):
    return [(t[0], t[1], t[2]) for t in trs]


def analyse(book, R):
    wmap = recency_weights(R["days_ok"])
    daily = R["daily"]
    base_tr = _trades(R["tl"], daily)
    hold_tr = _trades(R["tl"], daily, tp_frac=0)
    base_v = views(_tk(base_tr), wmap)
    hold_v = views(_tk(hold_tr), wmap)
    # ---- STUDY A: T x L ----
    cells = []
    for T in CUT_TIMES:
        for L in CUT_LS:
            tr = _trades(R["tl"], daily, cut_T=T, cut_L=L)
            v = views(_tk(tr), wmap)
            v["n_stale_cut"] = sum(1 for t in tr if t[2] == "CUT" and t[3]["stale"])
            cells.append(dict(label=f"T={T} L={L:g}", T=T, L=L, v=v))
    # the deployed no-cut book competes too and is listed FIRST, so it wins every tie (max() keeps the
    # first maximum): a cut that never fires must not be reported as a recommendation
    tl_pick = pick_and_check([dict(label="NO CUT (deployed)", T=None, L=None, v=base_v)] + cells, base_v)
    # ---- STUDY B: entry time x distance ----
    ecells = []
    for hm in ENTRY_TIMES:
        for d in DISTS:
            tr = _trades(R["entry"].get((hm, d), {}), daily)
            ecells.append(dict(label=f"{hm} d={d * 100:.2f}%", hm=hm, d=d, v=views(_tk(tr), wmap),
                               skips=R["skips_entry"].get(f"{hm} d={d * 100:.2f}%", {})))
    ebase = [c for c in ecells if c["hm"] == DEPLOYED_ENTRY and abs(c["d"] - book["otm"]) < 1e-9][0]["v"]
    e_pick = pick_and_check(ecells, ebase)
    repro_v = None
    if R["repro"]:
        rt = _trades(R["repro"], daily, tp_frac=0)
        repro_v = stats([(t[0], t[3]["net_pts"] * 75, t[2]) for t in rt])
    return dict(wmap=wmap, base=base_v, hold=hold_v, cells=cells, tl_pick=tl_pick, ecells=ecells,
                e_pick=e_pick, base_trades=base_tr, repro=repro_v)


def live_audit(book, R):
    """Compare simulated deployed-entry strikes with the live forward book's (Mac copy)."""
    f = {"NIFTY": "zero_dte_positions.json", "SENSEX": "sensex_dte_positions.json"}[book["name"]]
    try:
        with open(os.path.join(ROOT, "data", f)) as fh:
            live = json.load(fh) or []
    except Exception:
        return dict(n=0, note="no live book file")
    rows, match = [], 0
    for lp in live:
        e = lp.get("entry_date")
        sims = R["tl"].get(e)
        if sims is None:
            rows.append(dict(day=e, live=f"{lp['side']} {lp['short_strike']}/{lp['long_strike']}",
                             sim="no trade", match=False))
            continue
        want_h = bool(lp.get("hybrid"))
        sp = [p for p in sims if p["hybrid"] == want_h]
        if not sp:
            rows.append(dict(day=e, live=f"{lp['side']} {lp['short_strike']}", sim="side absent", match=False))
            continue
        p = sp[0]
        side = "BEAR_CALL" if p["typ"] == "CE" else "BULL_PUT"
        ok = side == lp["side"] and int(p["ks"]) == int(lp["short_strike"]) and int(p["kl"]) == int(lp["long_strike"])
        match += ok
        rows.append(dict(day=e, live=f"{lp['side']} {lp['short_strike']}/{lp['long_strike']} cr {lp['credit']}",
                         sim=f"{side} {int(p['ks'])}/{int(p['kl'])} cr {p['credit']:.2f}", match=ok))
    return dict(n=len(live), matched=match, rows=rows)


# ════════════════════════════ reporting ════════════════════════════
def _f(x, w=8, p=0):
    return f"{x:+{w},.{p}f}" if isinstance(x, (int, float)) else f"{'-':>{w}s}"


def fmt_views(v):
    po, wt, fu = v["post"], v["wtd"], v["full"]
    a = (f"{po.get('n', 0):3d} {po.get('win_pct', 0):5.1f} {_f(po.get('total'))} {_f(po.get('worst'))}"
         if po.get("n") else f"{0:3d} {'-':>5s} {'-':>8s} {'-':>8s}")
    b = f"{wt.get('w_win_pct', 0):5.1f} {_f(wt.get('w_mean'), 7)}" if wt.get("n") else f"{'-':>5s} {'-':>7s}"
    c = (f"{fu.get('n', 0):3d} {fu.get('win_pct', 0):5.1f} {_f(fu.get('avg_win'), 7)} {_f(fu.get('avg_loss'), 8)} "
         f"{_f(fu.get('total'), 9)} {_f(fu.get('worst'))}" if fu.get("n") else "  0")
    return f"{a} | {b} | {c}"


HDR = (f"{'POST-CAS: n  win%   total    worst':36s} | {'WTD: win%  mean':15s} | "
       f"FULL: n  win%  avg win avg loss     total    worst")


def report(book, A, R, integ, log):
    nm = book["name"]
    log(f"\n{'=' * 110}\n{nm} — {len(R['days_ok'])} expiries with an official close, "
        f"{len(R['fail_days'])} expiry days lost to fetch failures")
    log(f"  deployed-entry outcomes: {R['skips_tl']}")
    npost = A["base"]["post"].get("n", 0)
    log(f"  POST-CAS window (>= {CAS_START}): {npost} trades — directional evidence, not proof")
    log(f"\n  {'row':22s} {HDR}")
    log(f"  {'HOLD (no TP, ref)':22s} {fmt_views(A['hold'])}")
    log(f"  {'BASELINE (deployed)':22s} {fmt_views(A['base'])}   cut/tp {A['base']['full'].get('n_cut', 0)}/"
        f"{A['base']['full'].get('n_tp', 0)}")
    if A["repro"]:
        r = A["repro"]
        log(f"  REPRO ndte7 (CE-only, no FLIP/hybrid/gates/TP, <=2026-06-30, x75): n={r['n']} win {r['win_pct']:.1f}% "
            f"total Rs{r['total']:+,.0f} worst Rs{r['worst']:+,.0f}  [published: n=73 90.4% +Rs49,527 worst -11,703]")
    log(f"\n  STUDY A — loss cut at T if losing > L x credit   (Rs per lot)")
    log(f"  {'T     L':22s} {HDR}  cut stale")
    for c in A["cells"]:
        log(f"  {c['label']:22s} {fmt_views(c['v'])}  {c['v']['full'].get('n_cut', 0):3d} {c['v']['n_stale_cut']:3d}")
    _pick_lines(A["tl_pick"], log)
    log(f"\n  STUDY B — entry time x short distance (deployed exit)   (Rs per lot)")
    log(f"  {'entry  d':22s} {HDR}")
    for c in A["ecells"]:
        log(f"  {c['label']:22s} {fmt_views(c['v'])}")
    _pick_lines(A["e_pick"], log)


def _pick_lines(pk, log):
    rv = pk["recommended_views"]
    log(f"  >> RECOMMENDED (max recency-weighted total): {pk['recommended']}  "
        f"wtd mean Rs{rv['wtd'].get('w_mean', 0):+,.0f}/trade, post-CAS total Rs{rv['post'].get('total', 0):+,.0f}, "
        f"full total Rs{rv['full'].get('total', 0):+,.0f}, full worst Rs{rv['full'].get('worst', 0):+,.0f}")
    log(f"     FLAGS: {', '.join(pk['flags']) if pk['flags'] else 'none'}")
    log(f"     best post-CAS cell: {pk['best_post']} (Rs{pk['best_post_total']:+,.0f})")
    log(f"     PICK ON PRE-CAS -> {pk['pre_pick']}: post-CAS Rs{pk['pre_pick_post_total']:+,.0f} vs baseline post-CAS "
        f"Rs{pk['baseline_post_total']:+,.0f}")
    sp = pk["spearman_pre_vs_post"]
    log(f"     full-window winner {pk['full_winner']} ranks {pk['full_winner_post_rank']}/{pk['n_cells']} post-CAS; "
        f"Spearman(pre, post) over cells = {sp if sp is None else round(sp, 3)}")


def _jsonable_views(v):
    return {k: v[k] for k in v}


def write_outputs(results, integ):
    js = dict(generated=datetime.now(C.IST).isoformat(timespec="seconds"), clean=integ["clean"],
              integrity=integ, cas_start=CAS_START, half_life_days=HALF_LIFE_DAYS,
              post_min_mult=POST_MIN_MULT, cut_times=CUT_TIMES, cut_ls=CUT_LS,
              entry_times=ENTRY_TIMES, dists=DISTS, books={})
    md = [f"# ndte30 results ({js['generated']})", "",
          f"FETCH INTEGRITY: {'CLEAN' if integ['clean'] else 'NOT CLEAN - do not publish'} "
          f"({integ['requests']} requests, {integ['failures']} failures, {integ['n_429']} HTTP 429).", ""]
    for nm, (book, A, R, audit) in results.items():
        js["books"][nm] = dict(
            config={k: v for k, v in book.items()}, expiries=len(R["days_ok"]), fail_days=R["fail_days"],
            skips_deployed_entry=R["skips_tl"], baseline=A["base"], hold=A["hold"], repro_ndte7=A["repro"],
            losscut_grid=[dict(T=c["T"], L=c["L"], views=_jsonable_views(c["v"])) for c in A["cells"]],
            losscut_pick={k: v for k, v in A["tl_pick"].items()},
            entry_grid=[dict(entry=c["hm"], d=c["d"], views=c["v"], skips=c["skips"]) for c in A["ecells"]],
            entry_pick={k: v for k, v in A["e_pick"].items()},
            baseline_trades=[dict(day=t[0], hybrid=t[4]["hybrid"], typ=t[4]["typ"], ks=t[4]["ks"],
                                  kl=t[4]["kl"], credit=t[4]["credit"], lot=t[4]["lot"],
                                  late_legs=t[4]["late_legs"], exit=t[2], exit_hm=t[3]["exit_hm"],
                                  net_rs=round(t[1], 2), weight=round(A["wmap"][t[0]], 4))
                             for t in A["base_trades"]],
            live_audit=audit)
        b, tp, ep = A["base"], A["tl_pick"], A["e_pick"]
        md += [f"## {nm}", "",
               f"Expiries {len(R['days_ok'])}; post-CAS trades {b['post'].get('n', 0)} (directional evidence only).",
               f"Live-book strike audit: {audit.get('matched', 0)}/{audit.get('n', 0)} live positions matched.", "",
               "| row | post-CAS n / win% / total Rs | weighted win% / mean Rs | full n / win% / total Rs / worst Rs |",
               "|---|---|---|---|"]
        for lbl, v in (("Baseline (deployed)", b), (f"Loss cut pick {tp['recommended']}", tp["recommended_views"]),
                       ("Entry baseline", [c for c in A["ecells"] if c["hm"] == DEPLOYED_ENTRY
                                           and abs(c["d"] - book["otm"]) < 1e-9][0]["v"]),
                       (f"Entry pick {ep['recommended']}", ep["recommended_views"])):
            po, wt, fu = v["post"], v["wtd"], v["full"]
            md.append(f"| {lbl} | {po.get('n', 0)} / {po.get('win_pct', 0):.1f} / {po.get('total', 0):+,.0f} | "
                      f"{wt.get('w_win_pct', 0):.1f} / {wt.get('w_mean', 0):+,.0f} | {fu.get('n', 0)} / "
                      f"{fu.get('win_pct', 0):.1f} / {fu.get('total', 0):+,.0f} / {fu.get('worst', 0):+,.0f} |")
        for nmx, pk in (("Loss cut", tp), ("Entry", ep)):
            md += ["", f"{nmx}: flags = {', '.join(pk['flags']) or 'none'}. Pick on pre-CAS = {pk['pre_pick']}, "
                       f"its post-CAS total Rs{pk['pre_pick_post_total']:+,.0f} vs baseline Rs{pk['baseline_post_total']:+,.0f}. "
                       f"Full-window winner {pk['full_winner']} ranks {pk['full_winner_post_rank']}/{pk['n_cells']} "
                       f"post-CAS."]
        md.append("")
    _atomic_dump(OUT_JSON, js)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(md) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--allow-daytime", action="store_true",
                    help="user-authorised: fetch during the weekday day, but stop at 14:45 IST")
    ap.add_argument("--cache-only", action="store_true", help="never call Upstox; a cache miss is a failure")
    ap.add_argument("--books", default="NIFTY,SENSEX")
    ap.add_argument("--start", default=START)
    ap.add_argument("--gap", type=float, default=Fetcher.MIN_GAP, help="seconds between Upstox calls (>= 0.5)")
    a = ap.parse_args(argv)

    def log(s):
        print(s, flush=True)

    now = _ist_now()
    if not a.cache_only and not fetch_window_open(now, a.allow_daytime):
        log(f"REFUSED at {now:%a %H:%M} IST: the Upstox token is shared with the live engine. Fetching is "
            f"allowed outside 08:30-15:45 on weekdays (with --allow-daytime: until 14:45). Nothing fetched.")
        return 3
    f = Fetcher(allow_daytime=a.allow_daytime, cache_only=a.cache_only, gap=a.gap, log=log,
                seed_from_cache=not a.cache_only)
    data = Data(f)
    log(f"ndte30 start {now:%Y-%m-%d %H:%M} IST · books {a.books} · from {a.start} · "
        f"{'CACHE-ONLY' if a.cache_only else 'network allowed' + (' until 14:45' if a.allow_daytime else '')}")
    results = {}
    try:
        for nm in [x.strip().upper() for x in a.books.split(",") if x.strip()]:
            book = BOOKS[nm]
            R = run_book(data, book, a.start, log)
            A = analyse(book, R)
            results[nm] = (book, A, R, live_audit(book, R))
    except WindowClosed as w:
        log(f"\nSTOPPED at {w}: the fetch window closed. Cache kept in {CACHE} "
            f"({f.n_req} requests this run). Rerun the same command after 15:45 IST to resume. No results written.")
        return 3
    except TokenInvalid as t:
        log(f"\nABORTED: {t}. No results written.")
        return 4
    except FetchFailed as x:
        log(f"\nABORTED: a book-level fetch failed ({x}). No results written.")
        log(f"FETCH INTEGRITY: {f.n_req} requests, {len(f.failures)} failures: {f.failures[:10]}")
        return 2
    integ = dict(requests=f.n_req, cache_hits=f.n_hit, n_429=f.n_429, failures=len(f.failures),
                 failure_list=[list(x) for x in f.failures], clean=not f.failures)
    for nm, (book, A, R, audit) in results.items():
        report(book, A, R, integ, log)
        log(f"\n  live-book strike audit {nm}: {audit.get('matched', 0)}/{audit.get('n', 0)} matched")
        for r in audit.get("rows", []):
            if not r["match"]:
                log(f"     MISMATCH {r['day']}: live {r['live']} | sim {r['sim']}")
    write_outputs(results, integ)
    log(f"\nFETCH INTEGRITY: {f.n_req} requests, {f.n_hit} cache hits, {f.n_429} HTTP 429, "
        f"{len(f.failures)} failures -> {'CLEAN' if integ['clean'] else 'NOT CLEAN - DO NOT PUBLISH, rerun to retry'}")
    for x in f.failures[:30]:
        log(f"   failed: {x[0]} ({x[1]})")
    log(f"wrote {OUT_JSON} and {OUT_MD}\nDONE-NDTE30")
    return 0 if integ["clean"] else 2


if __name__ == "__main__":
    sys.exit(main())
