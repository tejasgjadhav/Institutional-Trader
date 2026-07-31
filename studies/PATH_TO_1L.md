# PATH TO ₹1L/MONTH — iteration 1 (2026-07-31)

**User goal:** a realistic path to ≥₹1,00,000/month profit on ₹5L margin, F&O and cash both open.
**Scope of this study:** (1) lot-scaling capital curve from the measured live books, (2) triage of
unexplored strategy families, (3) one quick backtest (0DTE iron condor, run today on 282 real-premium
expiries). Research only — nothing deployed, nothing is investment advice; these are the paper system's
own modeled numbers, and **live fills are still the unproven link.**

---

## 1. Lot-scaling capital curve (from the measured books)

Per-book inputs (all measured, 1 lot, model = backtest net of modeled slippage + brokerage):

| Book | ₹/mo model | sig/mo | margin/trade | concurrent | avg loss | worst single loss |
|---|--:|--:|--:|--:|--:|--:|
| v2 UNION (TP-50) | ₹20,000 | ~7.6 | ~₹10.5k | ~2–3 | −₹7,922 | −₹21.6k (capped) |
| v1 (TP-40/no-stop) | ₹13,000 | ~11 | ~₹7k | ~2–3 | ~−55%w ≈ −₹3.7k | ~−60%w ≈ −₹4.5k |
| 0DTE NIFTY FLIP | ₹1,771 | ~3.2 | ₹13.6k | 1, same-day | −₹4,038 | −₹13.0k |
| 0DTE SENSEX CE | ₹3,153 | ~4.1 | ₹11.5k | 1, same-day | −₹4,549 | −₹9.0k |
| **TOTAL** | **₹37,924** | **~26** | | | | |

- **Peak concurrent margin per lot-set:** v2 (3 × 10.5k) + v1 (3 × 7k) + one 0DTE day (13.6k) ≈ **₹66k
  theoretical**; **plan ₹1L** (MTM excursions before TP/stop, spread widening, expiry delivery-margin
  spikes on ITM stock shorts); the conservative CLAUDE.md bookend is ₹2–2.5L.
- **Worst-week cluster (1 lot-set), everything correlated short-premium in a crash week:** v2 streak-4
  (measured max) × −7.9k = −₹32k, v1 2–3 losses ≈ −₹9k, both 0DTE full-loss ≈ −₹22k → **≈ −₹60–70k**.
  Worst *measured* single-book month: v2 −₹26.4k.
- v1 loss shape re-measured today from its 242 OOS per-trade paths (`/tmp/v1_oos_exits.json`): TP-40
  exit → 86.4% win, avg loss −55.2%w, worst −59.9%w, max 2 consecutive (that era).

### The scaling table

| Lot-sets | Model ₹/mo | Sober (50%) ₹/mo | Peak margin (theor → plan) | Crash-week cluster | Funds on ₹5L? |
|--:|--:|--:|--:|--:|---|
| 1 | ₹37.9k | ₹19.0k | ₹0.7L → ₹1L | −₹0.6–0.7L | Yes, ₹4L spare |
| 2 | ₹75.8k | ₹37.9k | ₹1.3L → ₹2L | −₹1.2–1.4L | Yes |
| **3** | **₹113.8k** | ₹56.9k | ₹2.0L → ₹3L | **−₹1.9–2.1L** | Yes — tight, ₹2L buffer |
| 4 | ₹151.7k | ₹75.8k | ₹2.6L → ₹4L | −₹2.5–2.8L | Borderline: only at theoretical margins; a crash week + margin spike can force liquidation |
| 6 | ₹227.5k | ₹113.8k | ₹4L → ₹6L | −₹3.8–4.2L | **No** — planning margin exceeds ₹5L |

**Where ₹1L/mo becomes plausible:** at **3 lot-sets IF live ≈ model.** At the sober-50% rate it needs
6 lot-sets, which ₹5L cannot fund — the sober-case ceiling on ₹5L is **~₹75–95k/mo at 4–5 lot-sets,
fully deployed.** So on ₹5L, ₹1L/mo is a *good-regime model-rate outcome*, not a sober-case one.

**The drawdown you are accepting at 3 lots:** a clustered crash week ≈ **−₹2L (40% of capital)**;
a v2-style bad month ×3 ≈ −₹80k; plan on a −₹1.5–2L peak-to-trough episode sometime in year 1.
If that episode is not acceptable, ₹1L/mo on ₹5L is not on — the honest alternative is ~₹50–70k/mo
at 2–3 lots with half the tail.

### Gate timeline (LIVE ≥60% of model over 20–30 trades, then step a lot)

- Pooled books fire ~26 signals/mo at 1 lot-set → a 20–30-trade gate fills in **~1–1.2 months per step**
  (a v2-only gate needs 3–4 months at 7.6/mo — gate on the pooled book, judge v2 separately).
- First data point already exists: **July 2026 live paper month = 21 trades, +₹2,166/trade, +₹45,488**
  at 1 lot ≈ 120% of model (UI profit-calc table). One month, paper marks not real fills — favorable
  but not proof.
- Stepwise: M1 finish the 30-trade gate @1 → M2–3 run 2 lots and re-gate (the second lot fills worse,
  especially v2's 4-leg mid-cap spreads — this is where model-rate usually dies) → M4+ run 3 lots.
- **Earliest credible sustained ₹1L month ≈ month 4–6**, and only if each gate passes at ≥60% of model.
  If live settles at the 50% haircut, the ₹5L ceiling is ₹75–95k/mo — then the path needs either the
  best new book (Section 2) or more capital.

---

## 2. Unexplored strategy families — data-feasibility triage

| Pri | Family | Mechanism (why it might work) | Sig/mo | Backtestable free? | Verdict today |
|---|---|---|--:|---|---|
| P1 | **Expiry-day iron condor** (add put spread to proven 0DTE) | margin sharing: 2 credits vs 1 on the same one-sided max loss; theta collapses both sides | same 7–9 expiry days | **Y — tested today** (§3) | Beats CE-always, **loses to deployed FLIP**; iteration 2 = FLIP-condor hybrid + OOS + SENSEX |
| P2 | **NIFTY calendar / diagonal** (sell weekly, buy next-weekly/monthly) | near-expiry theta decays faster than far; short-vol without naked gamma | ~4 | **Y — cached now**: `/tmp/bhav_nifty_opt` full chain incl. all expiries, 2018-12→2024-09 (daily CLOSE only → close-to-close sim, fine for multi-day) | The only untouched defined-risk theta family with data in hand — run in iteration 2 |
| P3 | **Futures pairs, multi-day** (stock/index futures spreads, daily closes) | cointegration mean-reversion | 2–5 per pair | **Y — cached**: FUTSTK closes 2019→Sep'24 for the 113 universe (`/tmp/bhav_cache_stk`); FUTIDX = trivial re-download | Weak prior: *intraday* pairs already failed (45% win, −0.14%/tr, 3,670 trades, `DAILY_HIGHWIN_SEARCH.md`); multi-day untested but margin-heavy (~₹2–3L/pair) — collides with the ₹5L cap |
| P4 | **Cash momentum / mean-reversion** (daily bars) | cross-sectional momentum persists in India; unlevered, uncorrelated with short-premium | monthly rebal | Y — daily bars 2019→ (Kite/Upstox/bhavcopy) | Cannot reach the goal: ~12–18%/yr unlevered ≈ ₹5–7.5k/mo per ₹5L and it competes for the same capital. Diversifier only |
| — | **Covered-call-style** on liquid stocks | harvest call IV against delivery | ~4 per name | Y (bhavcopy) | **Drop at ₹5L** — needs lot-notional delivery ₹5–15L per name; the synthetic version (short put) ≈ the credit books already running |

Also on the record (explored, not deployed, single-era): daily-entered CE spread on the nearest weekly
**held to settlement** — 78.8% win, +7.25%m, ≈ +₹2.2L/21mo ≈ ₹10.5k/mo at 1 lot (`DAILY_HIGHWIN_SEARCH.md`).
The biggest known ₹/mo lever outside the live books, but 21-month single-era evidence only, no 2019-24
extension possible from the bhav cache. If any book is added for money (not diversification), this one
earns the OOS-era scrutiny first.

---

## 3. Quick test — 0DTE NIFTY iron condor (run 2026-07-31)

**Setup:** `studies/ndte/ndte23_ic.py`, identical conventions to the validated `ndte3` harness
(re-downloaded NSE expiry-day bhavcopy → `/tmp/ndte_bhav`, 282 expiries 2019-02→Jul'24; entry OPEN,
settle CLOSE, no stop, short-leg CONTRACTS ≥100, costs 2.5% of gross credit + ₹20×legs×2/lot;
condor margin = W − total credit, one-sided). **Faithfulness: the deployed CE d=0.5% W=200 baseline
reproduces its documented numbers exactly — 282 trades, 84.4% win, +3.17%m.**

| Config (W=200) | n | Win | Avg %m | Total ₹ (1 lot) | ₹/mo | Neg years |
|---|--:|--:|--:|--:|--:|---|
| CE 0.50 (deployed base) | 282 | 84.4% | +3.17% | +₹81,735 | ₹1,257 | 0/6 |
| PE-only 0.50 | 282 | 78.0% | +0.90% | +₹11,157 | — | 3/6 |
| PE-only 0.75 | 279 | 83.9% | +1.31% | +₹29,775 | — | 1/6 |
| IC CE0.50 + PE0.50 | 282 | 70.9% | +4.94% | +₹92,891 | ₹1,429 | 1/6 (2019) |
| **IC CE0.50 + PE0.75** | **279** | **75.3%** | **+4.92%** | **+₹107,907** | **₹1,660** | **0/6** |
| IC CE0.50 + PE1.50 | 272 | 82.0% | +4.53% | +₹85,973 | ₹1,323 | 0/6 |

**Findings, honestly:**
1. **The condor works as a structure**: +32% more money than CE-always on the same margin and the same
   days (margin sharing does what it should), positive all 6 years, worst trade unchanged (−₹13.0k vs
   −₹12.4k). The put side alone is weak (+0.9–1.3%m, negative years) — exactly as documented — but the
   condor's shared margin still monetizes it.
2. **It does NOT beat the deployed FLIP.** Same IS window: FLIP = 85.8% win / +3.82%m / **+₹137,523**
   (`FLIP_SIDE_CREDIT_FADE.md`) vs best condor 75.3% / +4.92%m / +₹107,907. Momentum-gated side
   selection extracts more than selling both sides, at a much higher win rate. **Do not deploy the
   condor over FLIP on NIFTY.**
3. The realistic uplift if it did deploy is small anyway: +₹400/mo per lot IS. This family cannot move
   the ₹1L needle by itself.
4. **Iteration-2 follow-ups that ARE worth running:** (a) FLIP-condor hybrid — momentum-selected near
   side + far-OTM spread on the other side (never tested); (b) condor on **SENSEX**, where FLIP failed
   to transfer and the book runs CE-only (+7.6%m) — needs the Upstox-era PE legs (slow fetch, ~hours);
   (c) OOS Oct'24→now for whatever survives. No stop-sweep — the no-stop finding is settled.

---

## 4. Verdict — the fastest credible route

1. **Scaling the proven books is the path; new books are garnish.** The whole triage produced nothing
   that plausibly adds more than ~₹10k/mo per lot, while each lot-step of the existing portfolio adds
   ~₹38k/mo at model rate. The binding question is only: **does live ≈ model?**
2. **The route:** finish the 30-trade live gate at 1 lot (July's +₹45,488/21 trades is one favorable
   month) → 2 lots ~month 2 → 3 lots ~month 4 → **₹1L/mo becomes a realistic model-rate month around
   month 4–6**, on ~₹3L planning margin inside the ₹5L, accepting a possible −₹1.5–2L episode.
3. **If live comes in at the sober 50%, ₹5L caps out at ~₹75–95k/mo** — then add the best-evidenced
   extra book (daily hold-to-expiry CE, after OOS-era scrutiny) or add capital; do not force 6 lots.
4. Iteration 2 backlog, in order: calendar/diagonal backtest (data cached), FLIP-condor hybrid,
   SENSEX condor, daily hold-to-expiry re-scrutiny. Skip: covered calls, cash momentum (as ₹-engines),
   intraday pairs (already dead).

*Repro:* `studies/ndte/ndte23_ic.py` (data: `studies/ndte/bhav_expiry_dl.py` → `/tmp/ndte_bhav`,
spot cache `/tmp/ndte_cache/spot2019.json`). /tmp caches are wiped on reboot — both are resumable.

---

# Iteration 2 (2026-07-31) — FLIP-condor hybrid + SENSEX condor

## 5. FLIP-CONDOR HYBRID on NIFTY 0DTE — PROMISING (IS + OOS)

**Idea:** keep the deployed FLIP side exactly as-is (ret5 ≥ +1% → PE, else CE; short 0.5% OTM,
W=200), and ADD the opposite-side spread only when that side's own credit/width clears a floor.
Margin is shared (both wings W=200, only one side can lose at settlement → margin = W − total
credit), so any positive added-side EV lifts return-on-margin on the same capital.

**Reproduction gate (`studies/ndte/ndte24_flipcondor.py`):** on the same 282 expiries
(2019-02→Jul'24, `/tmp/ndte_bhav`), the FLIP baseline reproduces **n=282, 85.8% win, +3.82%m —
exactly** under intrinsic settlement (the flip study's convention). The documented ₹137,523 does
NOT reproduce in rupees: the original scratchpad (deleted) used a different lot-size bookkeeping —
era lots give **+₹103,818**, flat-75 gives +₹144,363, which bracket it. Every comparison below is
same-machinery (era lots, intrinsic settle), so the verdict does not hinge on that bookkeeping.

### IS — same 282 expiries, 1 lot, net of 2.5% slippage + brokerage

| Config | n (2-side) | Win | Avg %m | Total ₹ | Worst | Per-year ₹ (19/20/21/22/23/24) |
|---|--:|--:|--:|--:|--:|---|
| FLIP (deployed baseline) | 282 (0) | 85.8% | +3.82% | +₹103,818 | −₹12,975 | −4k/+23k/+13k/+26k/+19k/+27k |
| HYB add d=0.75 cw≥0.07 | 282 (89) | 84.4% | +6.19% | **+₹159,575** | −₹12,975 | +2k/+46k/+33k/+25k/+22k/+31k |
| **HYB add d=1.00 cw≥0.08** | 282 (39) | **86.5%** | +5.81% | **+₹148,045** | −₹12,975 | +1k/+49k/+17k/+31k/+20k/+31k |

Not a fit cell: the whole swept neighborhood (add d ∈ {0.75, 1.00, 1.25} × floor ∈ {0.05…0.10},
15 cells) lands at +₹127k–₹167k, i.e. **every cell beats FLIP's +₹104k**; win% ranges 82.6–86.5%.
Symmetric no-floor condors (add d=0.50) are the worst of the family — the floor and the wider
added side are what convert iteration-1's "condor loses to FLIP" into a win. Worst trade is
unchanged (it is FLIP's own worst day; the added side cannot add a new max-loss — one side's
wing covers both). 2019, FLIP's one negative year, turns positive in both headline cells.

### OOS — Oct'24→Jul'26, real Upstox expired premiums, cells frozen before the run

`studies/ndte/ndte26_flipcondor_oos.py`, 95 expiries (`/tmp/ndte_nifty_oos`):

| Config | n (2-side) | Win | Avg %m | Total ₹ | Worst |
|---|--:|--:|--:|--:|--:|
| FLIP (deployed baseline) | 95 (0) | 91.6% | +5.92% | +₹64,323 | −₹11,629 |
| HYB d=0.75 cw≥0.07 [frozen] | 95 (33) | 89.5% | +10.24% | +₹85,797 | −₹11,629 |
| **HYB d=1.00 cw≥0.08 [frozen]** | 94 (11) | **91.5%** | +9.18% | +₹82,225 | −₹11,629 |

All 8 OOS neighbor cells also beat FLIP (+₹79k–96k at 88.4–91.6% win). One expiry (2026-02-03)
is excluded by the margin≤0 guard — its 1%-OTM added side shows a stale 189.9-credit open print
(junk data that would have flattered the hybrid; exclusion is the conservative call).

**Verdict: PROMISING — needs user approval + paper forward-test, NOT deploy.**
- The d=1.00 cw≥0.08 cell matches FLIP's win rate (86.5% IS / 91.5% OOS vs 85.8/91.6), beats it
  on money in BOTH eras (+43% IS, +28% OOS), same worst-case, positive all 6 IS years — and it
  only fires the second side on ~12–14% of expiries (39/282 IS, 11/94 OOS), when the far side is
  paid ≥16 pts on 200. Mechanically it is the stock-book lesson again: rich credit IS the gate.
- Honest size of the prize at 1 lot: **≈ +₹800–1,000/month over FLIP** (OOS era). Real, not
  transformative — it does not move the ₹1L needle alone; it raises the 0DTE NIFTY book's rate
  from ~₹1.8k to ~₹2.6–2.8k/mo on the same margin.
- Caveats: the floor value is swept (selection risk is real even with a robust neighborhood);
  bhav OPEN fills on both legs are optimistic for a 4-leg entry; the added side fires rarely
  OOS (11–33 trades), so the OOS uplift rests on a thin add-count even though the full-book n=95.

## 6. SENSEX 0DTE condor — REJECT (fails the win-rate bar on a thin, one-regime sample)

`studies/ndte/ndte25_sensex_condor.py`, cache `/tmp/ndte_sensex` rebuilt (was wiped);
baselines reproduce exactly (CE-only 89 exp **88.8% / +7.57%m / +₹67,248**, worst −₹8,963;
sensex_flip's CE/PE/FLIP figures all match the 2026-07-08 study). Deployed CE side + PE side
gated by its own c/w floor, real premiums Oct'24→Jul'26:

| Config | n (2-side) | Win | Avg %m | Total ₹ | Worst | 24/25/26 ₹ |
|---|--:|--:|--:|--:|--:|---|
| CE-only (deployed) | 89 (0) | **88.8%** | +7.57% | +₹67,248 | −₹8,963 | −4k/+34k/+37k |
| IC +PE 0.50 (symmetric, best floor) | 89 (62–83) | 73–75% | +10.5% | +₹63–65k | −₹12,499 | worse everywhere |
| IC +PE 0.75 cw≥0.06 (best cell) | 89 (57) | 85.4% | +13.39% | +₹96,879 | −₹9,531 | −3k/+37k/+63k |

The best cell adds +₹30k over 22 months but: win% drops 88.8→85.4 (fails "same-or-better"),
the worst trade deepens (−₹9.0k→−₹9.5k), the 2024 stub — the only adverse stretch in the sample —
gets worse in every variant (75%→58–67% win), and the uplift is concentrated in 2026's hot regime
(its 100%-win 2026 line on 26 trades is exactly what floor-selection on 89 expiries produces).
**89 expiries, 22 months, one regime — same reason SENSEX FLIP was rejected. Keep SENSEX CE-only.**
Revisit only if the NIFTY hybrid passes its paper test AND the SENSEX book has ≥150 expiries.

## 7. Iteration-2 verdict

1. **The FLIP-condor hybrid (add d=1.00, cw≥0.08) is the first iteration-2 candidate to clear the
   bar**: more money than FLIP in-sample AND out-of-sample at the same win rate and the same
   worst-case, on shared margin. Status: awaiting user approval → paper forward-test at 1 lot.
2. **SENSEX condor: rejected** on the win-rate bar and sample thinness.
3. Prize honesty: ≈ +₹0.8–1k/mo at 1 lot. The ₹1L path remains lot-scaling of the proven books
   (Section 1); this is a rate improvement on one of them, not a new engine.
4. Still open from the backlog: calendar/diagonal backtest (`/tmp/bhav_nifty_opt` cached, wiped on
   reboot — re-download via `studies/ndte/bhav_dl_0dte_idx.py` era scripts), daily hold-to-expiry
   CE re-scrutiny.

*Repro:* `studies/ndte/ndte24_flipcondor.py` (IS), `ndte26_flipcondor_oos.py` (OOS, cache
`/tmp/ndte_nifty_oos`), `ndte25_sensex_condor.py` (SENSEX, cache `/tmp/ndte_sensex`). All /tmp
caches are resumable; scripts refetch what a reboot wipes.
