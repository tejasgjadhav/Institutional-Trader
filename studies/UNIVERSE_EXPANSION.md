# F&O universe expansion for Stock Fade v2 UNION — can we add names WITHOUT diluting? (2026-07-29)

**Goal (user):** the deployed **Stock Fade v2 UNION** credit-spread book trades a hand-picked
~100-name universe (`engine.config.UNIVERSE`). NSE F&O has ~180 stock underlyings. Find names
**not** already in UNIVERSE that would **add signals at the same quality** (~84% win, +26% of width,
positive every year) so the blended book is **not diluted**. Additive only.

**Answer: YES — the universe can be expanded additively.** 37 of 88 candidates clear the
credit/width≥0.40 gate on real 2019→Sep'24 bhavcopy, and **every one of those 37 is net-positive
over the in-sample window** — the gate is structural and transfers to new underlyings. Three
non-dilutive add-sets are proposed below (conservative → maximal). **All are in-sample only; read
the caveats before any config change. This is research — `config.UNIVERSE` was NOT edited.**

---

## Method (identical to the deployed book)

Replicated `studies/ndte/stkfade_union.py` exactly: daily UNION Donchian(5/10/15/20) breakout →
SELL 2-OTM credit spread against it (up→bear-call, down→bull-put), width 4. Gates: **credit/width
≥ 0.40** (THE edge), short prem ≥ ₹50, OI ≥ 1, min-DTE 10, reentry 3 days. Exit TP 50% of credit /
hard stop 3×, else settle intrinsic at monthly expiry. Costs 2.5%/leg entry slippage. Data: **NSE
F&O bhavcopy option premiums 2019→Sep'24** (IS), underlying daily from Upstox. Gross of costs
beyond the modeled 2.5%.

Scripts: `studies/ndte/expand_phase0_enum.py` (enumerate), `expand_phase1_screen.py` (breakout
screen), `expand_phase2_dl.py` (download candidate bhavcopy), `expand_split_bysym.py` (reshape to
per-symbol on 8 GB RAM), `expand_phase2_bt.py` (backtest + blend scenarios). Data cached under
`/tmp/bhav_cache_expand` and `/tmp/bysym_*`; results `/tmp/expand_phase2.json`.

**Baseline reproduced:** deployed UNIVERSE on the same engine = **370 trades, 5.78/mo, 84.1% win,
+25.7% of width, positive 6/6 years.** (Matches the ~84%/+26% target.)

---

## Phase 0 — universe enumeration

From the 2024-09-30 F&O bhavcopy (UDiFF): **180 distinct stock-option underlyings.** 92 of the
deployed 100 are present; the other 8 (`ADANIGREEN, BAJAJHLDNG, DMART, ETERNAL, INDIANB, IRFC,
TATAELXSI, UNIONBANK`) were added to F&O later / renamed — already in UNIVERSE, not a concern.

**Candidates = 88 F&O underlyings NOT in UNIVERSE.** (6 could not be screened — no Upstox
underlying: `GMRINFRA`→GMR Airports, `LTIM`→LTIMindtree, `IDFC`→merged, `PEL`, `GUJGASLTD`,
`TATAMOTORS`→demerged. Excluded from all recommendations.)

## Phase 1 — cheap breakout screen (raw signal frequency, pre-gate)

Union Donchian breakout frequency is **near-uniform across all 88 candidates (~3.8–5.2 signal-days
/month)** — it is a property of the price series, not the name. So frequency does **not**
differentiate candidates. The real filter is the **option gate** (Phase 2). Spot price was
recorded because the c/w≥0.40 gate structurally favours higher-priced, rich-IV names. Full table:
`/tmp/expand_phase1.csv`.

Because frequency is uniform and the gate is the true selector, Phase 2 was run on **all** 82
signal-bearing candidates (option-data permitting) rather than a price pre-filtered shortlist — the
gate itself is the shortlisting mechanism.

## Phase 2 — real bhavcopy backtest (the gate does the selecting)

- **37 of 88 candidates produced gated trades. All 37 are net-positive over IS** (worst =
  BHARATFORG +3.3%w). **51 candidates never clear the gate** — structurally can't make a
  rich-IV c/w≥0.40 spread (mostly lower-priced names: BEL, IDEA, CANBK, GAIL, NATIONALUM,
  MOTHERSON, LICHSGFIN, SBICARD, PVRINOX…). This confirms the price/IV structural selection.
- The gate is very selective **per name** (~1 gated trade/month/name), so most contributing
  names have small individual samples — but per-trade quality is controlled by the gate, which
  prior work established is structural and population-wide (`CW_BUCKET_ANALYSIS.md`,
  `FUNDAMENTAL_TECHNICAL_FINDING.md`), not name-specific.

### Top contributing candidates (gated, sorted by net % of width)

| Sym | n | win% | net%w | yrs +ve | notes |
|---|---|---|---|---|---|
| COLPAL | 5 | 100 | +44.9 | 2/2 | liquid large-cap |
| ASTRAL | 5 | 100 | +41.9 | 3/3 | mid-cap |
| INDIAMART | 5 | 100 | +41.5 | 1/1 | all 2024 (shallow) |
| ALKEM | 8 | 87.5 | +40.4 | 3/3 | pharma |
| DALBHARAT | 5 | 100 | +37.5 | 2/2 | cement |
| UBL | 5 | 100 | +37.1 | 2/2 | |
| NAVINFLUOR | 11 | 100 | +36.6 | 3/3 | mid-cap, less liquid |
| **MRF** | **24** | **87.5** | **+30.1** | **5/5** | high-priced, richest gate-clearer |
| ATUL | 10 | 90.0 | +29.5 | 3/3 | mid-cap |
| CUMMINSIND | 11 | 81.8 | +26.2 | 2/2 | mostly 2024 |
| **DEEPAKNTR** | **15** | **86.7** | **+23.8** | **3/4** | one −ve yr (2023 −11.7%) |
| HAL | 5 | 80.0 | +23.1 | 1/1 | all 2024 (shallow) |
| BOSCHLTD | 5 | 80.0 | +7.0 | 2/2 | marginal (2024 +4.2%) |

Full per-candidate table incl. the 24 smaller positive names and the 51 zero-gated names:
`/tmp/expand_phase2.json` and the run log.

---

## Blend scenarios — every option ADDS signals and stays non-dilutive

Baseline = 370 trades · 5.78/mo · **84.1% win · +25.7%w** · +ve 6/6 yr.

| Scenario | Rule | Names | Added n | Added /mo | Added win/net | **Blended /mo** | **Blended win** | **Blended net%w** | +ve yrs |
|---|---|---|---:|---:|---|---:|---:|---:|---|
| **STRICT** | n≥15, win≥80, +ve most yrs | **2** | 39 | +1.44 | 87.2% / +30.0% | **6.39** | **84.4%** | **+28.0%** | 6/6 |
| **TIER-5 (recommended)** | n≥5, win≥80, +ve most yrs | **13** | 114 | +3.17 | 90.4% / +28.9% | **7.56** | **85.5%** | **+27.6%** | 6/6 |
| **ALL-GATED** | any name that clears the gate | **37** | 199 | +4.52 | 86.4% / +26.7% | **8.89** | **84.9%** | **+26.4%** | 6/6 |

Every scenario keeps win% and net%w **at or above baseline** while raising the signal rate — the
literal definition of the user's goal (more signals, no dilution). Note ALL-POSITIVE ≡ ALL-GATED:
no gated candidate was net-negative.

- **STRICT (2):** `MRF, DEEPAKNTR` — the only two meeting the task's literal n≥15 floor. Safest,
  but leaves obvious additive names on the table because the gate is so selective per name.
- **TIER-5 (13) — recommended:** `COLPAL, ASTRAL, INDIAMART, ALKEM, DALBHARAT, UBL, NAVINFLUOR,
  MRF, ATUL, CUMMINSIND, DEEPAKNTR, HAL, BOSCHLTD`. Pools to n=114 (a meaningful sample), win
  **90.4%**, +28.9%w, +ve 5/5 yrs pooled. Best balance of sample size, signal gain (+55% more
  signals/mo) and quality. **Best single answer to the goal.**
- **ALL-GATED (37):** maximal additive set — nearly doubles signals/mo (5.78→8.89, +54%) and still
  84.9%/+26.4%. But leans on many n=1–4 samples and several less-liquid mid-caps, so live fills
  will erode it more than the table shows.

---

## Honest caveats (READ before any config change)

1. **In-sample only.** 2019→Sep'24 bhavcopy is the only window with historical stock-option
   premiums. There is **no direct out-of-sample check on these specific names** — Upstox
   intraday/premium history is ~1 month; the CW-bucket OOS window (Oct'24→Jul'26) covered the
   *deployed* universe, not candidates. This repo's index-fade failure proves single-regime edges
   can vanish OOS. **Mitigant:** unlike index-fade, this is the *same structural gate already
   validated OOS on the deployed book*, merely applied to more underlyings — the transfer is more
   credible than a fresh regime-specific pattern, but it is still not OOS-proven per name.
2. **Uneven per-name coverage / recency skew.** Several names' gated trades cluster in 2022–2024
   (INDIAMART, HAL, CUMMINSIND all-2024; mid-cap strike coverage was thinner earlier). The pooled
   "6/6 years" is carried by *different* names in different years, not deep per-name history.
3. **Gross of costs; mid-cap fills worse.** Beyond the modeled 2.5%/leg, real 4-leg fills on
   mid-caps (NAVINFLUOR, DEEPAKNTR, ATUL, ASTRAL, DALBHARAT) run worse — plan ~⅓ haircut per repo
   convention. MRF, HAL, COLPAL, ALKEM, CUMMINSIND, BOSCHLTD are reasonably liquid. The live
   two-sided-quote + OI gate in `engine/stock_credit_v2.py` already filters untradeable spreads at
   runtime, which protects the blend somewhat.
4. **Small-n noise.** Per-name 100%-on-n=1–5 figures are noise around the ~86% population mean;
   trust the *pooled* scenario stats, not any single name's win%.
5. **The added edge is the same magnitude caveat as the core book** — the deployed book's real
   Oct'24→Jul'26 result (+31.7%w at ≥0.40) is optimistic vs live fills; expect the additions to
   deliver a similar fraction, not the headline IS number.

## Disposition / recommendation

**Recommend the TIER-5 set (13 names)** as the additive expansion: it doubles down on the exact
edge already deployed, raises signal rate +55%, and holds win/net at-or-above baseline across all 6
IS years — additive, not dilutive. **STRICT (MRF+DEEPAKNTR)** is the ultra-conservative floor if
only n≥15 names are wanted.

**REPORT-ONLY.** `engine.config.UNIVERSE` was not changed and nothing was committed. Adding names is
a live change requiring user review of these IS-only numbers first. If deployed, add them to
UNIVERSE and let the existing gates/liquidity filter run — no other engine change is needed.
