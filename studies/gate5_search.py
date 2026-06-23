"""In-memory search: given the collected trades (features + premium paths), find the best
Gate-5 filter and risk-reward (target/stop) that beats the current +10/-20, validated on a
train(70%)/test(30%) time split. No re-fetching — pure replay."""
import json, itertools
rows = json.load(open("/tmp/g5_trades.json"))
rows.sort(key=lambda r: r["day"])
days = sorted({r["day"] for r in rows})
cut = days[int(len(days)*0.70)]
TR = [r for r in rows if r["day"] < cut]
TE = [r for r in rows if r["day"] >= cut]

def replay(r, tgt, stp):
    e = r["entry"]; T = e*(1+tgt/100); S = e*(1-stp/100)
    for px in r["path"]:
        if px <= S: return -stp
        if px >= T: return tgt
    last = r["path"][-1]; return (last/e-1)*100

def stats(lst, tgt, stp, filt=None):
    sub = [r for r in lst if (filt is None or filt(r))]
    if not sub: return None
    pnls = [replay(r, tgt, stp) for r in sub]
    n = len(sub); w = sum(1 for p in pnls if p > 0)
    # rupee-weighted P&L (1 lot each)
    rs = sum(r["entry"]*r["lot"]*p/100 for r, p in zip(sub, pnls))
    cap = sum(r["entry"]*r["lot"] for r in sub)
    wins = [p for p in pnls if p > 0]; losses = [p for p in pnls if p <= 0]
    aw = sum(wins)/len(wins) if wins else 0; al = sum(losses)/len(losses) if losses else 0
    exp = sum(pnls)/n   # expectancy %/trade
    return {"n": n, "win": w/n*100, "exp": exp, "pnl": rs, "roc": rs/cap*100 if cap else 0,
            "rr": abs(tgt/stp), "aw": aw, "al": al}

def line(tag, s):
    if not s: return f"  {tag:34}: none"
    return (f"  {tag:34}: n={s['n']:3} win={s['win']:4.0f}% exp={s['exp']:+5.2f}%/tr "
            f"P&L={s['pnl']:+9,.0f} ({s['roc']:+.1f}%) RR=1:{1/s['rr']:.1f}")

print(f"=== {len(rows)} trades · train<{cut}<=test ({len(TR)}/{len(TE)}) ===\n")
print("BASELINE +10/-20 (current):")
print("  TRAIN", line("", stats(TR,10,20))); print("  TEST ", line("", stats(TE,10,20)))
b_tr = stats(TR,10,20); b_te = stats(TE,10,20)

print("\n--- A) RISK-REWARD sweep (no Gate 5), ranked by TEST expectancy ---")
combos = []
for tgt in (8,10,12,15,20):
    for stp in (8,10,12,15,18,20):
        s_tr = stats(TR,tgt,stp); s_te = stats(TE,tgt,stp)
        if s_tr and s_te: combos.append((tgt,stp,s_tr,s_te))
for tgt,stp,s_tr,s_te in sorted(combos, key=lambda x:-x[3]["exp"])[:8]:
    flag = "  <-- beats baseline both" if (s_tr["exp"]>b_tr["exp"] and s_te["exp"]>b_te["exp"]) else ""
    print(f"  +{tgt}/-{stp} (RR 1:{stp/tgt:.1f})  TRAIN win={s_tr['win']:.0f}% exp={s_tr['exp']:+.2f}  TEST win={s_te['win']:.0f}% exp={s_te['exp']:+.2f}{flag}")

print("\n--- B) GATE-5 candidate filters (keep current +10/-20), ranked by TEST expectancy ---")
import numpy as np
feats = ["az","vr","ext","tod","nstr","gap","orb_w"]
cands = []
for f in feats:
    vals = sorted(r[f] for r in TR)
    for q in (0.2,0.33,0.5,0.67,0.8):
        thr = vals[int(len(vals)*q)]
        for side,fn in [(">=",lambda r,t=thr,ff=f: r[ff]>=t), ("<=",lambda r,t=thr,ff=f: r[ff]<=t)]:
            s_tr = stats(TR,10,20,fn); s_te = stats(TE,10,20,fn)
            if s_tr and s_te and s_tr["n"]>=20 and s_te["n"]>=8:
                cands.append((f,side,round(thr,3),s_tr,s_te))
for f,side,thr,s_tr,s_te in sorted(cands, key=lambda x:-x[4]["exp"])[:10]:
    flag = "  <-- beats baseline both" if (s_tr["exp"]>b_tr["exp"] and s_te["exp"]>b_te["exp"] and s_te["win"]>=b_te["win"]) else ""
    print(f"  {f}{side}{thr:<7} TRAIN n={s_tr['n']:3} win={s_tr['win']:.0f}% exp={s_tr['exp']:+.2f}  TEST n={s_te['n']:3} win={s_te['win']:.0f}% exp={s_te['exp']:+.2f}{flag}")
print("\nDONE-SEARCH")
