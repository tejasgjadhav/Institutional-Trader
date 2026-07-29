"""Three NEW analyses on the validated v2 UNION stock credit-spread fade, reusing the exact
gate + fade logic of studies/ndte/stkfade_union.py (IS, NSE bhavcopy 2019->Sep'24, /tmp/bhav_cache_stk)
and studies/ndte/stkfade_oos_v1.py (OOS, real Upstox expired-option premiums Oct'24->date):

  1. PUT (bull-put, down-break) vs CALL (bear-call, up-break) split — n/win/net/avgWin/avgLoss, IS & OOS.
  2. STOP-LOSS sweep {2.0, 2.5, 3.0-deployed, 3.5, no-stop} — n/win/net/worst-loss/net-after-1/3-haircut.
  3. TIMING — (a) win% by day-of-week of entry; (b) entry-at-close vs entry-at-next-open.

Deployed v2 config held fixed everywhere except the swept parameter: UNION Donchian(5,10,15,20),
SELL against the break (up->bear-call short 2-OTM CE +4 wide; down->bull-put short 2-OTM PE -4),
gates credit/width>=0.40, short prem>=Rs50, OI>=1, min-DTE 10, reentry 3d, TP 50% of credit, stop 3x.

SLIPPAGE CONVENTION (both IS & OOS, for apples-to-apples comparability): 2.5% per-leg entry
slippage (spf) charged on entry only + Rs20x4/lot is negligible at width scale and omitted here as in
stkfade_union.py. Base net therefore matches the validated v2 sim exactly. The analysis-2 haircut
column subtracts an EXTRA 1/3 of round-trip (entry+exit) slippage to stress "fills 1/3 worse".

Writes per-trade records to /tmp/stkfade_pcs_is.json + /tmp/stkfade_pcs_oos.json and the report to
studies/SWING_PUTCALL_STOP_ANALYSIS.md. NOTE: 'next-open' is proxied by the NEXT trading day's option
CLOSE (bhavcopy/expired-candle have no intraday option OPEN historically) and is re-gated at the
delayed credit, so its n differs from entry-at-close. Everything is GROSS of taxes; single OOS regime.
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys, glob, json, collections, time, threading, concurrent.futures
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import date, datetime, timedelta
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical, UPSTOX_BASE
from engine.instruments import encode_key
from engine.expired_options import get_expiries, get_contracts, _get_json as _gj

CACHE = "/tmp/bhav_cache_stk"
MIN_DTE, REENTRY, MIN_CW, MIN_PREM, MIN_OI = 10, 3, 0.40, 50.0, 1
DCS = (5, 10, 15, 20); SHORT, WIDTH, TP, STOP = 2, 4, 0.50, 3.0
OOS_START = date(2024, 10, 1)
def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0
def expiso(x): return pd.to_datetime(x).date()

# ---------------------------------------------------------------- IS collector (bhav cache)
def collect_is():
    print("loading bhav cache…", flush=True)
    prem = collections.defaultdict(dict); oi = collections.defaultdict(dict)
    strikes = collections.defaultdict(set); bdays = set()
    for f in sorted(glob.glob(f"{CACHE}/*.csv")):
        d = os.path.basename(f)[:-4]
        try: df = pd.read_csv(f)
        except Exception: continue
        if df.empty or "OPTION_TYP" not in df: continue
        df = df[df["OPTION_TYP"].isin(["CE", "PE"])]
        bdays.add(d)
        for r in df.itertuples(index=False):
            try: e = expiso(r.EXPIRY_DT).isoformat()
            except Exception: continue
            k = (r.SYMBOL, e, float(r.STRIKE_PR), r.OPTION_TYP)
            prem[k][d] = float(r.CLOSE); oi[k][d] = float(r.OPEN_INT)
            strikes[(r.SYMBOL, e, r.OPTION_TYP)].add(float(r.STRIKE_PR))
    bdays = sorted(bdays); bset = set(bdays)
    print(f"  {len(bdays)} bhav days ({bdays[0]}..{bdays[-1]})", flush=True)

    print("underlyings + union breakouts…", flush=True)
    sig_union = {}; close_by_sym = {}
    for sym0 in UNIVERSE:
        sym = sym0.replace(".NS", "")
        u = fetch_upstox_historical(sym0, unit="days", interval=1, from_date="2018-06-01", to_date=max(bdays))
        if u is None or u.empty or len(u) < 40: continue
        u = u.sort_index()
        close_by_sym[sym] = {ix.date().isoformat(): float(u["Close"].loc[ix]) for ix in u.index}
        for dc in DCS:
            hi = u["High"].rolling(dc).max().shift(1); lo = u["Low"].rolling(dc).min().shift(1)
            for i in range(max(dc, 20), len(u) - 1):
                day = u.index[i].date(); ds = day.isoformat()
                if ds not in bset: continue
                c = float(u["Close"].iloc[i])
                typ = "CE" if c > float(hi.iloc[i]) else ("PE" if c < float(lo.iloc[i]) else None)
                if not typ: continue
                kk = (day, sym)
                if kk not in sig_union: sig_union[kk] = (typ, c)
    sig = sorted((d, s, t, c) for (d, s), (t, c) in sig_union.items())
    print(f"  union signals {len(sig)}", flush=True)

    exps_by = {}
    for (sym, e, t) in strikes: exps_by.setdefault((sym, t), set()).add(e)

    recs = []; last = {}
    for (day, sym, typ, c) in sig:
        kk = (sym, typ)
        if last.get(kk) and (day - last[kk]).days < REENTRY: continue
        fut = sorted(e for e in exps_by.get(kk, ()) if date.fromisoformat(e) >= day + timedelta(days=MIN_DTE))
        if not fut: continue
        exp = fut[0]; ks = sorted(strikes.get((sym, exp, typ), []))
        if len(ks) < SHORT + WIDTH + 2: continue
        atm = min(range(len(ks)), key=lambda j: abs(ks[j] - c))
        si, li = (atm + SHORT, atm + SHORT + WIDTH) if typ == "CE" else (atm - SHORT, atm - SHORT - WIDTH)
        if si < 0 or li < 0 or si >= len(ks) or li >= len(ks): continue
        sk, lk = ks[si], ks[li]; ds = day.isoformat()
        se = prem.get((sym, exp, sk, typ), {}).get(ds); le = prem.get((sym, exp, lk, typ), {}).get(ds)
        soi = oi.get((sym, exp, sk, typ), {}).get(ds, 0)
        if se is None or le is None or se < MIN_PREM or soi < MIN_OI: continue
        credit = se - le; w = abs(sk - lk)
        if credit <= 0 or credit >= w or credit / w < MIN_CW: continue
        last[kk] = day
        path = []
        for dd in (x for x in bdays if ds < x <= exp):
            a = prem.get((sym, exp, sk, typ), {}).get(dd); b = prem.get((sym, exp, lk, typ), {}).get(dd)
            if a is None or b is None: continue
            path.append((a, b))
        cb = close_by_sym.get(sym, {})
        espot = cb.get(exp) or (cb[max(x for x in cb if x <= exp)] if any(x <= exp for x in cb) else c)
        intr = max(0.0, espot - sk) if typ == "CE" else max(0.0, sk - espot)
        intl = max(0.0, espot - lk) if typ == "CE" else max(0.0, lk - espot)
        settle = min(max(intr - intl, 0.0), w)
        recs.append(dict(day=ds, dow=day.weekday(), side=typ, w=w, credit=credit,
                         se=se, le=le, path=path, settle=settle))
    print(f"  IS trades captured {len(recs)}", flush=True)
    json.dump(recs, open("/tmp/stkfade_pcs_is.json", "w"))
    return recs

# ---------------------------------------------------------------- OOS collector (Upstox expired options)
def leg_series(key, d0, to):
    j = _gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}")
    if j.get("status") == "success":
        c = j.get("data", {}).get("candles", [])
        if c:
            df = pd.DataFrame(c, columns=["ts", "O", "H", "L", "C", "V", "OI"]); df["ts"] = pd.to_datetime(df["ts"])
            return df.set_index("ts").sort_index()["C"]
    return None

def collect_oos():
    print("OOS: Upstox expired-option premiums Oct'24->date…", flush=True)
    recs = []; EXPC = {}; CHC = {}; LK = threading.Lock(); DONE = [0]
    def do_stock(sym0):
        sym = sym0.replace(".NS", "")
        try:
            u = fetch_upstox_historical(sym0, unit="days", interval=1, from_date="2024-06-01", to_date=date.today().isoformat())
            if u is None or u.empty or len(u) < 30:
                with LK: DONE[0] += 1
                return
            u = u.sort_index()
            cb = {ix.date().isoformat(): float(u["Close"].loc[ix]) for ix in u.index}
            rolls = {dc: (u["High"].rolling(dc).max().shift(1), u["Low"].rolling(dc).min().shift(1)) for dc in DCS}
            last = {}
            for i in range(max(DCS) + 1, len(u) - 1):
                day = u.index[i].date()
                if day < OOS_START: continue
                c = float(u["Close"].iloc[i]); typ = None
                for dc in DCS:
                    hi, lo = rolls[dc]
                    if c > float(hi.iloc[i]): typ = "CE"; break
                    if c < float(lo.iloc[i]): typ = "PE"; break
                if typ is None: continue
                if last.get(typ) and (day - last[typ]).days < REENTRY: continue
                try:
                    if sym not in EXPC: EXPC[sym] = get_expiries(sym)
                    exps = [e for e in EXPC[sym] if e >= (day + timedelta(days=MIN_DTE)).isoformat()]
                    if not exps: continue
                    exp = exps[0]; ck = (sym, exp, typ)
                    if ck not in CHC:
                        CHC[ck] = sorted([ct for ct in get_contracts(sym, exp) if ct["instrument_type"] == typ],
                                         key=lambda ct: float(ct["strike_price"]))
                    chain = CHC[ck]
                except Exception: continue
                ks = [float(ct["strike_price"]) for ct in chain]
                if len(ks) < SHORT + WIDTH + 2: continue
                atm = min(range(len(ks)), key=lambda j: abs(ks[j] - c))
                si, li = (atm + SHORT, atm + SHORT + WIDTH) if typ == "CE" else (atm - SHORT, atm - SHORT - WIDTH)
                if si < 0 or li < 0 or si >= len(ks) or li >= len(ks): continue
                sct, lct = chain[si], chain[li]; sk, lk = ks[si], ks[li]
                to = min(datetime.fromisoformat(exp).date(), day + timedelta(days=45)).isoformat()
                sp = leg_series(sct["instrument_key"], day.isoformat(), to)
                lp = leg_series(lct["instrument_key"], day.isoformat(), to)
                if sp is None or lp is None: continue
                common = sp.index.intersection(lp.index)
                if len(common) < 1: continue
                sp = sp.loc[common].sort_index(); lp = lp.loc[common].sort_index()
                se = float(sp.iloc[0]); le = float(lp.iloc[0]); credit = se - le; w = abs(sk - lk)
                if se < MIN_PREM or credit <= 0 or credit >= w or credit / w < MIN_CW: continue
                last[typ] = day
                path = [(float(sp.iloc[t]), float(lp.iloc[t])) for t in range(1, len(common))]
                espot = cb.get(exp) or (cb[max(x for x in cb if x <= exp)] if any(x <= exp for x in cb) else c)
                intr = max(0.0, espot - sk) if typ == "CE" else max(0.0, sk - espot)
                intl = max(0.0, espot - lk) if typ == "CE" else max(0.0, lk - espot)
                settle = min(max(intr - intl, 0.0), w)
                with LK:
                    recs.append(dict(day=day.isoformat(), dow=day.weekday(), side=typ, w=w, credit=credit,
                                     se=se, le=le, path=path, settle=settle))
        except Exception as e:
            with LK: print(f"  !! {sym}: {str(e)[:50]}", flush=True)
        with LK:
            DONE[0] += 1
            if DONE[0] % 20 == 0:
                print(f"  …{DONE[0]}/100 stocks, {len(recs)} OOS trades", flush=True)
                json.dump(recs, open("/tmp/stkfade_pcs_oos.json", "w"))
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(do_stock, UNIVERSE))
    print(f"  OOS trades captured {len(recs)}", flush=True)
    json.dump(recs, open("/tmp/stkfade_pcs_oos.json", "w"))
    return recs

# ---------------------------------------------------------------- evaluator
def evaluate(rec, tp=TP, stop=STOP, entry_idx=0):
    """Return dict(net, netpc, win, exit_slip, entry_slip) for a config. entry_idx=0 -> enter at
    breakout close; entry_idx=1 -> enter at next trading day's close (re-gated by caller)."""
    p = rec["path"]; w = rec["w"]
    if entry_idx == 0:
        se, le, credit = rec["se"], rec["le"], rec["credit"]; walk = p
    else:
        if len(p) < 1: return None
        se, le = p[0]; credit = se - le; walk = p[1:]
    entry_slip = (se * spf(se) + le * spf(le)) / 100.0
    close = None; exit_slip = 0.0
    for (a, b) in walk:
        cost = a - b
        if tp > 0 and cost <= credit * (1 - tp):
            close = max(cost, 0.0); exit_slip = (a * spf(a) + b * spf(b)) / 100.0; break
        if stop is not None and cost >= credit * stop:
            close = min(cost, w); exit_slip = (a * spf(a) + b * spf(b)) / 100.0; break
    if close is None:
        close = rec["settle"]  # intrinsic settlement, no exit trade -> no exit slippage
    net = (credit - close) - entry_slip
    return dict(net=net, netpc=net / w * 100, win=int(net > 0), entry_slip=entry_slip, exit_slip=exit_slip)

def summarize(recs, evals):
    """recs and evals aligned; evals may contain None (excluded). Returns dict of stats using width."""
    pairs = [(rc, ev) for rc, ev in zip(recs, evals) if ev is not None]
    n = len(pairs)
    if n == 0: return dict(n=0, win=0.0, netw=0.0, avgw=0.0, avgl=0.0, worst=0.0)
    sw = sum(rc["w"] for rc, _ in pairs)
    win = sum(ev["win"] for _, ev in pairs) / n * 100
    netw = sum(ev["net"] for _, ev in pairs) / sw * 100
    wins = [ev["netpc"] for _, ev in pairs if ev["win"]]
    loss = [ev["netpc"] for _, ev in pairs if not ev["win"]]
    avgw = sum(wins) / len(wins) if wins else 0.0
    avgl = sum(loss) / len(loss) if loss else 0.0
    worst = min(ev["netpc"] for _, ev in pairs)
    return dict(n=n, win=win, netw=netw, avgw=avgw, avgl=avgl, worst=worst)

# ---------------------------------------------------------------- three analyses
def analysis_putcall(recs):
    """Deployed config (TP0.5, stop3). Split CE(bear-call/up) vs PE(bull-put/down)."""
    rows = {"CE": [], "PE": []}
    for rc in recs:
        ev = evaluate(rc)
        rows[rc["side"]].append((rc, ev))
    out = {}
    for side in ("CE", "PE"):
        rl = rows[side]
        out[side] = summarize([rc for rc, _ in rl], [ev for _, ev in rl])
    return out

STOPS = [("2.0x", 2.0), ("2.5x", 2.5), ("3.0x (deployed)", 3.0), ("3.5x", 3.5), ("no-stop", None)]
def analysis_stopsweep(recs):
    out = []
    for lab, st in STOPS:
        evals = [evaluate(rc, tp=TP, stop=st) for rc in recs]
        s = summarize(recs, evals)
        # 1/3 slippage haircut: subtract 1/3 of round-trip (entry+exit) slippage from each net
        pairs = [(rc, ev) for rc, ev in zip(recs, evals) if ev is not None]
        sw = sum(rc["w"] for rc, _ in pairs) or 1.0
        net_hc = sum(ev["net"] - (ev["entry_slip"] + ev["exit_slip"]) / 3.0 for _, ev in pairs)
        s["netw_hc"] = net_hc / sw * 100
        s["label"] = lab
        out.append(s)
    return out

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]
def analysis_dow(recs):
    out = []
    for d in range(5):
        sub = [rc for rc in recs if rc["dow"] == d]
        evals = [evaluate(rc) for rc in sub]
        s = summarize(sub, evals); s["label"] = DOW[d]
        out.append(s)
    return out

def analysis_timing(recs):
    """entry-at-close (deployed) vs entry-at-next-open (proxied by next trading day close, re-gated)."""
    ev_close = [evaluate(rc, entry_idx=0) for rc in recs]
    close_s = summarize(recs, ev_close)
    ev_open = []
    for rc in recs:
        if len(rc["path"]) < 1: ev_open.append(None); continue
        a1, b1 = rc["path"][0]; credit2 = a1 - b1; w = rc["w"]
        if a1 < MIN_PREM or credit2 <= 0 or credit2 >= w or credit2 / w < MIN_CW:
            ev_open.append(None); continue      # trade would not qualify if delayed one day
        ev_open.append(evaluate(rc, entry_idx=1))
    open_s = summarize(recs, ev_open)
    return close_s, open_s

# ---------------------------------------------------------------- report
def fmt(s):
    if s.get("n", 0) == 0: return f"{'n=0':>8s}"
    return s
def row_pcs(lab, s):
    if s["n"] == 0: return f"| {lab} | 0 | – | – | – | – |"
    return f"| {lab} | {s['n']} | {s['win']:.1f}% | {s['netw']:+.1f}% | {s['avgw']:+.1f}% | {s['avgl']:+.1f}% |"
def row_stop(s):
    if s["n"] == 0: return f"| {s['label']} | 0 | – | – | – | – |"
    return (f"| {s['label']} | {s['n']} | {s['win']:.1f}% | {s['netw']:+.1f}% | "
            f"{s['worst']:+.1f}% | {s['netw_hc']:+.1f}% |")
def row_dow(s):
    if s["n"] == 0: return f"| {s['label']} | 0 | – | – |"
    return f"| {s['label']} | {s['n']} | {s['win']:.1f}% | {s['netw']:+.1f}% |"

def build_report(IS, OOS):
    L = []
    A = L.append
    A("# Stock Fade v2 UNION — Put/Call, Stop-Loss & Timing analysis\n")
    A("Extends the validated v2 UNION credit-spread fade (see `studies/ndte/stkfade_union.py`, "
      "`STOCK_OPTIONS_NO_EDGE.md` Part 10). Strategy held fixed except the swept parameter: UNION "
      "Donchian(5/10/15/20) daily breakout → SELL a credit spread AGAINST it (up→bear-call short "
      "2-OTM CE +4 wide; down→bull-put short 2-OTM PE −4), gates credit/width≥0.40, short prem≥₹50, "
      "OI≥1, min-DTE 10, reentry 3d, TP 50% of credit, hard stop 3× credit, else settle intrinsic at "
      "monthly expiry.\n")
    A(f"- **IS** = NSE bhavcopy 2019→Sep 2024 (close-only sim), **n={len(IS)} trades**.\n"
      f"- **OOS** = real Upstox expired-option premiums Oct 2024→{date.today().isoformat()} "
      f"(single regime), **n={len(OOS)} trades**.\n"
      "- Net = % of spread width; 2.5%/leg **entry** slippage charged (matches the validated v2 sim); "
      "GROSS of taxes. Small ₹20×4/lot commission omitted as in the base sim.\n")
    A("---\n")

    # 1 put/call
    A("## 1. PUT (bull-put / down-break) vs CALL (bear-call / up-break)\n")
    pc_is = analysis_putcall(IS); pc_oos = analysis_putcall(OOS)
    for lab, dat in (("In-sample 2019→Sep'24", pc_is), ("Out-of-sample Oct'24→date", pc_oos)):
        A(f"**{lab}**\n")
        A("| side | n | win% | net %width | avg win %w | avg loss %w |")
        A("|---|--:|--:|--:|--:|--:|")
        A(row_pcs("CALL (bear-call, up-break)", dat["CE"]))
        A(row_pcs("PUT  (bull-put, down-break)", dat["PE"]))
        A("")
    A("")

    # 2 stop sweep
    A("## 2. Stop-loss sweep (rest of v2 fixed)\n")
    for lab, recs in (("In-sample 2019→Sep'24", IS), ("Out-of-sample Oct'24→date", OOS)):
        A(f"**{lab}**\n")
        A("| stop | n | win% | net %width | worst single loss %w | net after ⅓ slip haircut |")
        A("|---|--:|--:|--:|--:|--:|")
        for s in analysis_stopsweep(recs): A(row_stop(s))
        A("")
    A("_Haircut = base net minus one-third of modeled round-trip (entry+exit) slippage, i.e. assumes "
      "real fills are ~⅓ worse than the 2.5%/leg model._\n")

    # 3 timing
    A("## 3. Timing\n")
    A("### 3a. Win% by day-of-week of the breakout/entry\n")
    for lab, recs in (("In-sample 2019→Sep'24", IS), ("Out-of-sample Oct'24→date", OOS)):
        A(f"**{lab}**\n")
        A("| entry DOW | n | win% | net %width |")
        A("|---|--:|--:|--:|")
        for s in analysis_dow(recs): A(row_dow(s))
        A("")
    A("### 3b. Entry-at-close vs entry-at-next-open\n")
    A("_'Next-open' proxied by the NEXT trading day's option CLOSE (historical intraday option opens "
      "don't exist in bhavcopy/expired-candle data) and RE-GATED at the delayed credit, so its n is "
      "lower — trades that no longer clear credit/width≥0.40 a day later are dropped._\n")
    for lab, recs in (("In-sample 2019→Sep'24", IS), ("Out-of-sample Oct'24→date", OOS)):
        cs, os_ = analysis_timing(recs)
        A(f"**{lab}**\n")
        A("| entry | n | win% | net %width |")
        A("|---|--:|--:|--:|")
        A(row_dow({**cs, "label": "at breakout close (deployed)"}))
        A(row_dow({**os_, "label": "wait one session (next close)"}))
        A("")

    A("---\n")
    A("### Caveats\n")
    A("- OOS is a **single ~21-month regime** (Oct'24→now); IS-vs-OOS agreement is the real test of "
      "stability, not either number alone.\n")
    A("- Close-only IS sim: TP/stop touches are detected on **daily option closes**, so intraday stop "
      "hits are understated (real stops trigger a bit more often, slightly fattening the loss tail).\n")
    A("- All figures GROSS of taxes/STT; entry-slippage only in the base column (exit slippage enters "
      "only via the analysis-2 haircut).\n")
    return "\n".join(L)

def keyline(tag, s):
    if s["n"] == 0: return f"{tag}: n=0"
    return f"{tag}: n={s['n']} win {s['win']:.1f}% net {s['netw']:+.1f}%w"

def main():
    IS = collect_is()
    OOS = collect_oos()
    md = build_report(IS, OOS)
    outp = "/Users/sayali/files/institutional-trader/studies/SWING_PUTCALL_STOP_ANALYSIS.md"
    open(outp, "w").write(md)
    print("\n" + "=" * 70)
    print(f"WROTE {outp}")
    print("=" * 70)
    # concise summary
    pc_is = analysis_putcall(IS); pc_oos = analysis_putcall(OOS)
    print("\n[1] PUT vs CALL (deployed TP0.5/stop3):")
    print("   IS  " + keyline("CALL", pc_is["CE"]) + " | " + keyline("PUT", pc_is["PE"]))
    print("   OOS " + keyline("CALL", pc_oos["CE"]) + " | " + keyline("PUT", pc_oos["PE"]))
    print("\n[2] Stop sweep (net %width | after 1/3 haircut | worst):")
    for lab, recs in (("IS ", IS), ("OOS", OOS)):
        for s in analysis_stopsweep(recs):
            if s["n"] == 0: continue
            print(f"   {lab} {s['label']:16s} n={s['n']:4d} win {s['win']:4.1f}% net {s['netw']:+6.1f}%w  "
                  f"hc {s['netw_hc']:+6.1f}%w  worst {s['worst']:+6.1f}%")
        print()
    print("[3a] Day-of-week (net %width):")
    for lab, recs in (("IS ", IS), ("OOS", OOS)):
        cells = " ".join(f"{s['label']}:{s['win']:.0f}%/{s['netw']:+.0f}%" for s in analysis_dow(recs) if s["n"])
        print(f"   {lab} {cells}")
    print("[3b] Close vs next-open:")
    for lab, recs in (("IS ", IS), ("OOS", OOS)):
        cs, os_ = analysis_timing(recs)
        print(f"   {lab} close: {keyline('', cs).strip()} || next-open: {keyline('', os_).strip()}")
    print("\nDONE-PUTCALL-STOP")

if __name__ == "__main__":
    main()
