"""Reshape the day-partitioned bhav caches into per-symbol CSVs so the backtest can load one
symbol at a time (8 GB RAM can't hold the 32 M-row nested dict). Streaming: one day file in
memory at a time, rows routed to per-symbol append handles. Adds a 'day' column.
  /tmp/bhav_cache_stk    -> /tmp/bysym_stk/{SYM}.csv
  /tmp/bhav_cache_expand -> /tmp/bysym_exp/{SYM}.csv
Idempotent-ish: wipes the out dir first. Run once."""
import os, sys, glob, csv, shutil

def split(cache, outdir):
    if os.path.isdir(outdir): shutil.rmtree(outdir)
    os.makedirs(outdir)
    handles = {}; writers = {}
    cols = ["SYMBOL","EXPIRY_DT","STRIKE_PR","OPTION_TYP","CLOSE","OPEN_INT","day"]
    files = sorted(glob.glob(f"{cache}/*.csv"))
    n = 0
    for f in files:
        day = os.path.basename(f)[:-4]
        with open(f, newline="") as fh:
            r = csv.DictReader(fh)
            if not r.fieldnames or "OPTION_TYP" not in r.fieldnames: continue
            for row in r:
                ot = (row.get("OPTION_TYP") or "").strip()
                if ot not in ("CE", "PE"): continue
                sym = (row.get("SYMBOL") or "").strip()
                if not sym: continue
                w = writers.get(sym)
                if w is None:
                    h = open(os.path.join(outdir, sym + ".csv"), "w", newline="")
                    w = csv.writer(h); w.writerow(cols)
                    handles[sym] = h; writers[sym] = w
                w.writerow([sym, row["EXPIRY_DT"], row["STRIKE_PR"], ot,
                            row["CLOSE"], row["OPEN_INT"], day])
        n += 1
        if n % 300 == 0: print(f"  {outdir}: {n}/{len(files)} days ({len(writers)} syms)", flush=True)
    for h in handles.values(): h.close()
    print(f"DONE {outdir}: {len(writers)} symbols from {n} days", flush=True)

split("/tmp/bhav_cache_stk", "/tmp/bysym_stk")
split("/tmp/bhav_cache_expand", "/tmp/bysym_exp")
print("DONE-SPLIT", flush=True)
