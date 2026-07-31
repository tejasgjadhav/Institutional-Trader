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
