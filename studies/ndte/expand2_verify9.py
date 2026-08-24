"""Audit-grade verification of the 9 admission candidates on the CLEAN pass, plus the thin-name
recount (IEX / CONCOR / RBLBANK: did their trade counts rise once fetch drops reached zero?).

Run AFTER research/expansion2/passes.log shows CLEAN. Recomputes every number from the row files
(never trusts a previous table), bootstraps each candidate, and re-states the admission rule verdict
per name. This is the audit the user asked for before any config change.
"""
import json, random, collections, sys
random.seed(17)
NINE = ["PAGEIND","MCX","TVSMOTOR","TIINDIA","SOLARINDS","LTIM","BDL","SHREECEM","AMBER"]
THIN = ["IEX","CONCOR","RBLBANK"]
iss=json.load(open("research/expansion2/is_rows.json"))
oos=json.load(open("research/expansion2/oos_rows.json"))
print(f"rows: IS {len(iss)} · OOS {len(oos)} · overlap "
      f"{len({(x['sym'],x['day']) for x in iss} & {(x['sym'],x['day']) for x in oos})} (must be 0)\n")
def agg(rows,s):
    g=[x for x in rows if x["sym"]==s]
    if not g: return None
    m=sum(x["margin_rs"] for x in g)
    return dict(n=len(g),win=100*sum(x["win"] for x in g)/len(g),
                rs=sum(x["net_rs"] for x in g), rom=100*sum(x["net_rs"] for x in g)/m if m else 0, rows=g)
def boot(g,n=3000):
    if len(g)<5: return None
    out=[]
    for _ in range(n):
        s=[random.choice(g) for _ in g]
        m=sum(x["margin_rs"] for x in s)
        out.append(100*sum(x["net_rs"] for x in s)/m if m else 0)
    out.sort(); return out[int(.05*n)], out[int(.95*n)]
print(f"{'name':<11}{'IS n/win/net':>24}{'OOS n/win/net':>24}{'OOS 90% CI':>20}  verdict")
for s in NINE:
    i,o=agg(iss,s),agg(oos,s)
    il=f"{i['n']}/{i['win']:.0f}%/{i['rs']:+,.0f}" if i else "IS-blind"
    ol=f"{o['n']}/{o['win']:.0f}%/{o['rs']:+,.0f}" if o else "NO OOS TRADES"
    ci=boot(o["rows"]) if o else None
    cis=f"[{ci[0]:+.0f}%,{ci[1]:+.0f}%]" if ci else "-"
    if i and o: v="BOTH WINDOWS +" if (i["rs"]>0 and o["rs"]>0) else "FAILS a window"
    elif o: v="OOS-only (label as such)" if o["rs"]>0 else "OOS NEGATIVE"
    else: v="no data"
    print(f"{s:<11}{il:>24}{ol:>24}{cis:>20}  {v}")
print("\n--- thin-name recount (were pass-2 counts fetch-starved?) ---")
for s in THIN:
    o=agg(oos,s)
    print(f"  {s:<9} OOS: " + (f"n={o['n']} win={o['win']:.0f}% net={o['rs']:+,.0f}" if o else "0 trades") )
