"""Cross-check Upstox daily bars against NSE bhavcopy, over the downloaded window.

Bhavcopy is end-of-day, so this reconciles the inputs that are actually comparable:
daily close and daily volume, per symbol per session. Intraday momentum, the ORB
and live option flow cannot be rebuilt from an EOD file, and are reported as
out-of-scope rather than silently skipped.
"""
import os, sys, glob, zipfile, json
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
from engine.data_fetcher import fetch_upstox_historical  # noqa: E402

CM = os.path.join(ROOT, "data", "bhavcopy", "cm")
OUT = os.path.join(ROOT, "studies", "ndte", "xcheck_upstox_vs_bhav.json")
CLOSE_TOL = 0.001          # 0.1% — anything wider is a real disagreement
SIGNAL_DATES = ['2026-06-22','2026-06-23','2026-06-24','2026-06-25','2026-06-29','2026-06-30',
                '2026-07-01','2026-07-02','2026-07-03','2026-07-06','2026-07-07']


def universe():
    import sqlite3
    c = sqlite3.connect(os.path.join(ROOT, "data", "engine.db"))
    t = [r[0] for r in c.execute("select distinct ticker from scan_rows")]
    c.close()
    return sorted(t)


def load_bhav(symbols):
    """Daily close and volume per symbol from the EQ series of every cached bhavcopy."""
    want = {s.replace(".NS", "") for s in symbols}
    rows = []
    for f in sorted(glob.glob(os.path.join(CM, "*.zip"))):
        try:
            z = zipfile.ZipFile(f)
            df = pd.read_csv(z.open(z.namelist()[0]))
        except Exception as e:
            print("  skip", os.path.basename(f), e); continue
        df = df[(df.SctySrs == "EQ") & (df.TckrSymb.isin(want))]
        if df.empty: continue
        rows.append(df[["TradDt", "TckrSymb", "ClsPric", "TtlTradgVol"]])
    if not rows:
        return pd.DataFrame(columns=["date", "sym", "bhav_close", "bhav_vol"])
    out = pd.concat(rows, ignore_index=True)
    out.columns = ["date", "sym", "bhav_close", "bhav_vol"]
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out


def load_upstox(symbols, lo, hi):
    rows = []
    for i, t in enumerate(symbols, 1):
        df = fetch_upstox_historical(t, unit="days", interval=1, from_date=lo, to_date=hi)
        if df.empty:
            print(f"  [{i}/{len(symbols)}] {t}: NO DATA"); continue
        d = df.reset_index()
        d["date"] = pd.to_datetime(d["Timestamp"]).dt.strftime("%Y-%m-%d")
        d["sym"] = t.replace(".NS", "")
        rows.append(d[["date", "sym", "Close", "Volume"]])
        if i % 25 == 0: print(f"  [{i}/{len(symbols)}] fetched", flush=True)
    if not rows:
        return pd.DataFrame(columns=["date", "sym", "ups_close", "ups_vol"])
    out = pd.concat(rows, ignore_index=True)
    out.columns = ["date", "sym", "ups_close", "ups_vol"]
    return out


def main():
    syms = universe()
    print(f"universe: {len(syms)} tickers")

    bhav = load_bhav(syms)
    if bhav.empty:
        print("no bhavcopy rows — nothing to compare"); return
    lo, hi = bhav.date.min(), bhav.date.max()
    print(f"bhavcopy: {len(bhav):,} rows | {bhav.sym.nunique()} symbols | {lo} -> {hi} "
          f"| {bhav.date.nunique()} sessions")

    print("fetching Upstox daily…")
    ups = load_upstox(syms, lo, hi)
    print(f"upstox:   {len(ups):,} rows | {ups.sym.nunique()} symbols")

    m = bhav.merge(ups, on=["date", "sym"], how="outer", indicator=True)
    both = m[m._merge == "both"].copy()
    both["close_diff_pct"] = (both.ups_close - both.bhav_close).abs() / both.bhav_close
    both["vol_diff_pct"] = (both.ups_vol - both.bhav_vol).abs() / both.bhav_vol.replace(0, pd.NA)
    mism = both[both.close_diff_pct > CLOSE_TOL]

    res = {
        "window": {"from": lo, "to": hi, "sessions": int(bhav.date.nunique())},
        "rows": {"bhav_only": int((m._merge == "left_only").sum()),
                 "upstox_only": int((m._merge == "right_only").sum()),
                 "matched": int(len(both))},
        "close": {"within_0.1pct": int((both.close_diff_pct <= CLOSE_TOL).sum()),
                  "mismatched": int(len(mism)),
                  "match_rate_pct": round(100 * (both.close_diff_pct <= CLOSE_TOL).mean(), 4),
                  "max_diff_pct": round(float(both.close_diff_pct.max() * 100), 4),
                  "median_diff_pct": round(float(both.close_diff_pct.median() * 100), 6)},
        "volume": {"median_diff_pct": round(float(both.vol_diff_pct.median() * 100), 4),
                   "over_1pct": int((both.vol_diff_pct > 0.01).sum())},
        "worst": mism.nlargest(15, "close_diff_pct")[
            ["date", "sym", "bhav_close", "ups_close", "close_diff_pct"]].to_dict("records"),
    }

    sig = both[both.date.isin(SIGNAL_DATES)]
    if len(sig):
        res["signal_window"] = {
            "dates": sorted(sig.date.unique().tolist()),
            "matched_rows": int(len(sig)),
            "close_match_rate_pct": round(100 * (sig.close_diff_pct <= CLOSE_TOL).mean(), 4),
            "mismatches": int((sig.close_diff_pct > CLOSE_TOL).sum()),
        }
    res["out_of_scope"] = ["intraday momentum (5-min bars)", "ORB high/low",
                           "live option-chain flow (PCR, OI change)"]

    json.dump(res, open(OUT, "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str)[:2600])
    print("\nwritten:", OUT)


if __name__ == "__main__":
    main()
