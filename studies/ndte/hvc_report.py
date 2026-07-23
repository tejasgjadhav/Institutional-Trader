"""Report tables for the HOURLY-vs-CLOSE entry study from /tmp/hvc/hvc_results.json.
Pure reporting — no fetching. Run after hvc_backtest.py."""
import json, sys
sys.path.insert(0, "/Users/sayali/files/institutional-trader")

RES = json.load(open("/tmp/hvc/hvc_results.json"))
# months in the sample window (Oct'24 -> latest breakout day)
alldays = [r["day"] for cn in ("v2_union", "v1") for v in RES[cn].values() for r in v]
months = len({d[:7] for d in alldays}) or 1

def agg(recs, netk, wink):
    n = len(recs)
    if n == 0: return dict(n=0, win=0.0, netw=0.0)
    win = 100.0 * sum(r[wink] for r in recs) / n
    netw = 100.0 * sum(r[netk] for r in recs) / sum(r["w"] for r in recs)
    return dict(n=n, win=win, netw=netw)

def per_year(recs, netk, wink):
    ys = sorted({r["y"] for r in recs})
    out = []
    for y in ys:
        g = [r for r in recs if r["y"] == y]
        a = agg(g, netk, wink)
        out.append(f"{y}:{a['win']:.0f}%/{a['netw']:+.0f}%w(n{a['n']})")
    return " · ".join(out)

for cn, label in (("v2_union", "v2 UNION (short2 w4 TP50 stop3x, D5-union)"),
                  ("v1", "v1 (short1 w3 TP75 stop2x, D10)")):
    recs = [r for v in RES[cn].values() for r in v]
    close = [r for r in recs if r.get("close_fired")]
    hourly = [r for r in recs if r.get("hourly_fired")]
    intraday = [r for r in hourly if r.get("entry_hour") not in (None, "close")]
    rev = [r for r in intraday if r.get("reverting")]
    held = [r for r in intraday if not r.get("reverting")]
    # extra signals hourly catches that close does NOT (close_fired == 0)
    extra = [r for r in hourly if not r.get("close_fired")]

    print("\n" + "=" * 92)
    print(f"### {label}")
    print(f"window: {months} months (Oct'24->date, single regime) | stocks fired: "
          f"{len({r['sym'] for r in recs})}")
    # intraday-availability: of CLOSE-fired trades, how many had BOTH legs trading intraday
    av = [r for r in close if r.get("short_intra_bars", 0) > 0 and r.get("long_intra_bars", 0) > 0]
    print(f"intraday-DATA availability on CLOSE-fired trades: {len(av)}/{len(close)} "
          f"({100*len(av)/max(len(close),1):.0f}%) have BOTH legs trading intraday "
          f"(rest: far-OTM/high-priced strikes that don't trade sub-day -> hourly can't enter earlier)")
    ac = agg(close, "close_net", "close_win"); ah = agg(hourly, "hourly_net", "hourly_win")
    print(f"\n{'rule':8s} {'n':>4s} {'sig/mo':>7s} {'win%':>6s} {'net %width':>11s}")
    print(f"{'CLOSE':8s} {ac['n']:4d} {ac['n']/months:7.1f} {ac['win']:6.1f} {ac['netw']:+11.1f}")
    print(f"{'HOURLY':8s} {ah['n']:4d} {ah['n']/months:7.1f} {ah['win']:6.1f} {ah['netw']:+11.1f}")
    print(f"\nCLOSE  per-year: {per_year(close, 'close_net', 'close_win')}")
    print(f"HOURLY per-year: {per_year(hourly, 'hourly_net', 'hourly_win')}")

    # extra signals (hourly-only, close skipped these entirely)
    ae = agg(extra, "hourly_net", "hourly_win")
    print(f"\nEXTRA signals HOURLY adds that CLOSE skips (close did NOT fire): n={ae['n']} "
          f"({ae['n']/months:.1f}/mo) win {ae['win']:.0f}% net {ae['netw']:+.1f}%w")

    # FLIP-SIDE: intraday first-touch entries, reverting vs held
    print(f"\n-- FLIP-SIDE: of {len(intraday)} HOURLY intraday first-touch entries --")
    if intraday:
        fr = 100.0 * len(rev) / len(intraday)
        arv = agg(rev, "hourly_net", "hourly_win"); ahd = agg(held, "hourly_net", "hourly_win")
        print(f"   REVERTING spikes (c/w back <0.40 by close): {len(rev)} ({fr:.0f}% of intraday entries)")
        print(f"      reverting : n={arv['n']:3d} win {arv['win']:5.1f}% net {arv['netw']:+.1f}%w")
        print(f"      held      : n={ahd['n']:3d} win {ahd['win']:5.1f}% net {ahd['netw']:+.1f}%w")
    else:
        print("   (no intraday first-touch entries in sample)")

    # entry-hour distribution
    from collections import Counter
    hc = Counter(r.get("entry_hour") for r in hourly)
    print("   entry-hour mix:", dict(sorted(hc.items(), key=lambda kv: str(kv[0]))))

print("\nDONE-REPORT")
