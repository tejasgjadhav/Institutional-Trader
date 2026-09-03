"""Band study 0.30-0.40 (user, 27-Aug-2026): which NAMES clear >=80% win AND net ROM > +5%
per side since 2018, one band below/around the deployed gates? v0 geometry (S=2,W=4,TP-40,
no stop), band widened to (0.30, 0.40). Study only - nothing deploys from here without OOS."""
import sys, json
sys.path.insert(0, "."); sys.path.insert(0, "studies/ndte")
import deployed_backtest as H
H.BOOKS = {"b30": dict(S=2, W=4, tp=0.40, stop=None, band=(0.30, 0.40))}
H.OUT = "research/band30_is_rows.json"

# OOS restricted to the IS qualifiers' names only (36 unique) - full-universe OOS would burn
# hours of throttled Upstox for names already disqualified in sample.
if len(sys.argv) > 1 and sys.argv[1] == "OOS":
    qs = {"HEROMOTOCO", "M&M", "RELIANCE", "TITAN"}  # OOS top-up: corrected-ROM qualifiers missed by run 1
    H.UNIVERSE = [tk for tk in H.UNIVERSE if tk.replace(".NS", "") in qs]
    print(f"OOS restricted to {len(H.UNIVERSE)} qualifier names")
if __name__ == "__main__":
    rows = H.run_is() if (len(sys.argv) > 1 and sys.argv[1] == "IS") else H.run_oos()
    H.OUT = "research/band30_is_rows.json" if sys.argv[1] == "IS" else "research/band30_oos_topup_rows.json"
    json.dump(rows, open(H.OUT, "w"))
    print(f"saved {len(rows)} rows -> {H.OUT}")
