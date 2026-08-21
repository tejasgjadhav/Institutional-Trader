# Champion-strategy sweep — can anything but credit spreads print >80% win AND positive net? (2026-07-31)

**Why this study exists.** The user challenged the premise directly: if credit spreads are the only thing that works here, has anything else actually been tried? This sweeps the well-known intraday systems on 5-minute candles to answer whether >80% win with positive net is reachable any other way, so that 'sell premium' is a measured conclusion rather than the only thing anyone looked at.


**User challenge (retail-quant-firm framing):** "Apart from credit spreads is there no way to get
>80% win rate? Did you scan 5-min candles and apply top trading-champion strategies?"

**Answer up front: yes, we scanned them — 7 classic champion families, 227,000+ trades, and NO. An
>80% win rate is trivially easy to manufacture and every manufactured version loses money. Nothing
in this sweep beats the deployed credit books' 85–89% win with positive net after costs. The
>80%-win + positive-net combination on this data remains unique to the gated short-premium
structure.**

## Setup

- **Universe:** NIFTY + BANKNIFTY + 20 liquid F&O large caps (RELIANCE, HDFCBANK, ICICIBANK, SBIN,
  AXISBANK, KOTAKBANK, INFY, TCS, HCLTECH, LT, ITC, BHARTIARTL, MARUTI, TITAN, TATASTEEL,
  JSWSTEEL, BAJFINANCE, SUNPHARMA, HINDUNILVR, ADANIENT).
- **Data:** Upstox daily 2018→2026-07 (2018 = indicator warm-up; trades from 2019). Upstox 5-min
  2022-01→2026-07 (~84,700 bars/symbol). **Honesty note:** Upstox holds no intraday before
  Jan 2022; the Kite 5-min-to-2019 cache from `BUY_STRATEGIES_2019_REALTEST.md` was purged from
  /tmp and no Kite access token exists this session (interactive login required), so the intraday
  families run 2022→2026 (4.6 yrs), the daily families 2019→2026 (7.6 yrs).
- **Split:** daily = train 2019–23 / test 2024–26. Intraday = train 2022–23 / test 2024–26.
- **Costs (charged per round trip):** intraday cash equity **0.05%** (1-tick slippage/side +
  ₹20×2 brokerage + 0.025% sell-side STT + exch/GST/stamp — conservative-realistic for these
  large caps); index intraday via futures **0.03%**; multi-day holds (futures execution, all
  symbols) **0.03%**. All figures below are **NET** of these.
- **No lookahead:** entries at signal-bar close or at the stated stop-trigger level; same-bar
  TP/SL ties resolved SL-first (conservative).
- Scripts: scratchpad `champ_fetch.py` / `champ_bt.py` / `champ_highwin_demo.py` (Upstox cache
  rebuildable via `engine.data_fetcher.fetch_upstox_historical`).

## 0. The >80%-win illusion, demonstrated on this exact data

High win rate is a **geometry dial, not an edge**. Tiny target (0.15%) + wide stop (3.0%) +
EOD close, on 5-min bars 2022→2026:

| Entry | n | Win | Avg win | Avg loss | **Net/trade** | Verdict |
|---|---|---|---|---|---|---|
| **Buy every day at 10:00** (no signal at all) | 24,816 | **83.6%** | +0.10% | −0.89% | **−0.061%** | 83%+ win, loses money, every year 2022–26 |
| VWAP 2σ fade entries, same geometry | 45,648 | **82.2%** | +0.10% | −0.81% | **−0.061%** | identical — the entry doesn't matter |

A signal-free coin toss prints 83.6% win with this geometry and bleeds −0.06%/trade in all five
years. **Any strategy pitched on win rate alone, without expectancy, is selling this illusion.**
That is why every table below shows win% AND expectancy together. (Matches the earlier 2,400-cell
finding in `DAILY_HIGHWIN_SEARCH.md`: 92% win, ~₹0 gross, negative net.)

## 1. Connors RSI-2 mean reversion (daily, long-only, close>200-DMA, exit close>5-SMA, max 10d)

The famous "75–85% win" print. Honest version, net of 0.03%:

| Variant | n | Win | Avg win | Avg loss | Net/tr ALL | Train 19–23 | Test 24–26 |
|---|---|---|---|---|---|---|---|
| RSI2 < 10 | 1,251 | 64.8% | +1.80% | −3.00% | +0.11% | +0.13% | **+0.07%** |
| RSI2 < 5 | 686 | 66.6% | +1.83% | −2.96% | +0.24% | +0.34% | **+0.02%** |

Per-year (RSI2<5): 2019 +0.55 · 2020 −0.59 · 2021 +1.25 · 2022 −0.10 · 2023 −0.26 · 2024 +0.34 ·
2025 +0.56 · **2026 −2.78 (38% win, n=29)**. Negative 4 of 8 years.

**Verdict:** the celebrated win rate does not survive India + costs: 65–67% win, not 80%+, and the
edge collapses from +0.34%/trade in-sample to +0.02% out-of-sample. The loss tail (avg −3%) is 1.6×
the win. Not deployable.

## 2. Larry Williams volatility breakout (open ± 0.5×prev-range)

| Variant | n | Win | Avg win | Avg loss | Net/tr ALL | Train | Test |
|---|---|---|---|---|---|---|---|
| Daily k=0.5 | 35,503 | 46.0% | +0.92% | −0.83% | −0.028% | −0.020% | −0.042% |
| Daily k=1.0 | 13,298 | 45.3% | +0.87% | −0.75% | −0.017% | −0.011% | −0.030% |
| 5-min open-range k=0.5 (2022→) | 18,718 | 46.1% | +0.82% | −0.76% | −0.035% | −0.023% | −0.044% |

**Verdict:** negative everywhere, both eras, both timeframes. Dead.

## 3. Turtle / Donchian FOLLOW (we had only ever tested fades)

| Variant | n | Win | Avg win | Avg loss | Net/tr ALL | Train | Test |
|---|---|---|---|---|---|---|---|
| 20-day entry / 10-day exit | 1,206 | 37.3% | +8.82% | −4.63% | +0.39% | **+0.99%** | **−0.70%** |
| 55/20 (classic Turtle S2) | 588 | 36.1% | +14.86% | −6.39% | +1.27% | **+2.46%** | **−0.98%** |

Per-year (55/20): 2019 −2.79 · **2020 +4.09 · 2021 +15.34** · 2022 −2.66 · 2023 −0.29 ·
2024 +0.39 · 2025 −1.50 · 2026 −2.18. The entire pooled profit is 2020–21 (COVID trend regime).

**Verdict:** the follow direction looks great pooled and FAILS the split — negative 2024–26,
negative 5 of 8 years. Same regime-artifact pattern that killed the index fade. Confirms the house
finding: on this universe the durable money was in fading breakouts (gated short premium), not
following them. And at 36% win it's the opposite of the user's ask anyway.

## 4. VWAP 2σ reversion intraday (5-min, exit at VWAP or EOD, ≤2/day, 2022→)

The classic prop-desk scalp:

| Variant | n | Win | Avg win | Avg loss | Net/tr ALL | Train | Test |
|---|---|---|---|---|---|---|---|
| No stop, exit VWAP/EOD | 32,714 | 63.8% | +0.25% | −0.65% | **−0.074%** | −0.087% | −0.063% |
| Tiny-TP/wide-SL geometry (§0) | 45,648 | 82.2% | +0.10% | −0.81% | **−0.061%** | — | — |

**Verdict:** 64% win, negative expectancy every year 2022–26. The stretch it fades is on average
information, not noise; the EOD losses on trend days (avg −0.65%) are 2.6× the VWAP-touch wins.
Cranking the win% to 82% via geometry just re-lands on §0's illusion. Dead.

## 5. Gap fade / gap-and-go (daily open auction, |gap| ≥ 0.3% / 0.5%)

| Variant | n | Win | Avg win | Avg loss | Net/tr ALL | Train | Test |
|---|---|---|---|---|---|---|---|
| Gap-and-go 0.3% | 23,664 | 43.9% | +1.27% | −1.25% | −0.147% | −0.153% | −0.132% |
| Gap fade → close 0.3% | 23,664 | 53.0% | +1.22% | −1.28% | +0.050% | +0.057% | +0.035% |
| Gap fade → close 0.5% | 15,578 | 53.4% | +1.36% | −1.42% | +0.063% | +0.077% | +0.027% |
| Gap fade → FILL target 0.3% | 23,664 | **70.4%** | +0.66% | −1.48% | **+0.026%** | +0.019% | +0.043% |

Per-year (fade→close 0.5%): +0.02 · +0.12 · +0.07 · +0.05 · +0.11 · +0.05 · +0.06 · **2026 −0.03**.

**Verdict:** gap-and-go loses outright. The gap FADE carries a real but tiny lean — +0.03–0.06%/
trade net at 53% win, positive 7 of 8 years but decaying in test and negative in 2026. Note the
fill-target version: win% jumps to 70%, expectancy *falls* to +0.026% — the same geometry trade-off
as §0, in the wild. At ~₹30–60 per ₹1L notional per trade it cannot pay for its own risk. Not
deployable.

## 6. Inside-bar / NR7 breakout (daily, stop-entry at range break, exit at close)

| Variant | n | Win | Avg win | Avg loss | Net/tr ALL | Train | Test |
|---|---|---|---|---|---|---|---|
| NR7 | 5,259 | 54.1% | +1.03% | −0.74% | +0.217% | +0.262% | **+0.125%** |
| Inside bar | 4,482 | 53.8% | +1.06% | −0.79% | +0.206% | +0.242% | **+0.135%** |

Per-year (NR7): +0.39 · +0.41 · +0.31 · +0.11 · +0.09 · +0.11 · +0.17 · +0.08 — **positive all
8 years, both variants, both split halves.**

**Verdict: the one honest positive surprise of the sweep** — a durable +0.13%/trade net
out-of-sample at ~53% win, positive every year. But (a) it is a 53%-win strategy, nowhere near the
user's 80% bar; (b) edge halves from train to test; (c) +0.13% of notional/trade means ~₹125 per
₹1L cash deployed per trade (~2–3 trades/day across 22 symbols) — real but small, and it would
face the same option-wrapper cost wall as the 3-Family direction edge (+0.107%/trade, which died
−1.0% net inside options — `BUY_STRATEGIES_2019_REALTEST.md`). Worth a future cash/futures
paper-book discussion at most; NOT deployed, per the approval-first rule.

## 7. Supertrend(10,3) flip follow

| Variant | n | Win | Avg win | Avg loss | Net/tr ALL | Train | Test |
|---|---|---|---|---|---|---|---|
| Daily flips (reversal system) | 1,131 | 37.8% | +12.14% | −5.35% | +1.27% | **+2.56%** | **−0.96%** |
| 5-min flips, intraday only (2022→) | 25,822 | 40.9% | +0.55% | −0.43% | −0.030% | −0.025% | −0.034% |

Daily per-year: 2019 −1.41 · **2020 +4.77 · 2021 +10.48** · 2022 −0.00 · 2023 +0.14 · 2024 −1.63 ·
2025 −0.36 · 2026 −0.69.

**Verdict:** the indicator every YouTube "champion" runs. Daily version = Donchian redux: all the
profit is COVID 2020–21, negative in test and in 5 of 8 years. Intraday version is negative both
eras. Dead.

## Ranked summary — everything vs the deployed credit books

| Rank | Strategy | Win | Net/trade | Survives train→test? | >80% win + positive net? |
|---|---|---|---|---|---|
| — | **Deployed: stock fade v2 UNION** | **87%** | positive, t=+13.78, 8/8 yrs | yes | **YES — the benchmark** |
| — | **Deployed: 0DTE NIFTY / SENSEX** | **88–89%** | positive, 7/8 yrs · 3 yrs | yes | **YES** |
| 1 | NR7 / inside-bar breakout | 53–54% | +0.13% OOS, 8/8 yrs | yes (halved) | no — win% nowhere close |
| 2 | Gap fade → close | 53% | +0.03% OOS | yes (thin, 2026 neg) | no |
| 3 | Connors RSI-2 | 65–67% | +0.02–0.07% OOS | barely (−2.8% in 2026) | no |
| 4 | Donchian FOLLOW 55/20 | 36% | −0.98% OOS | **no** (COVID artifact) | no |
| 5 | Supertrend daily | 38% | −0.96% OOS | **no** (COVID artifact) | no |
| 6 | Supertrend 5-min | 41% | −0.03% | negative both | no |
| 7 | LW vol breakout (daily + 5-min) | 45–46% | −0.02 to −0.04% | negative both | no |
| 8 | VWAP 2σ reversion | 64% | −0.07% | negative both | no |
| ✗ | Manufactured 83.6% winner (§0) | **83.6%** | **−0.061%** | negative every year | **the illusion, labelled** |

## Bottom line

1. **Win rate >80% is a dial, not an edge.** We produced 83.6% win on demand with zero signal; it
   loses −0.06%/trade every single year. Anything above 80% must be judged ONLY jointly with
   expectancy.
2. **The champion strategies do not survive India + costs + a train/test split.** The two
   trend-following legends (Turtle, Supertrend) are COVID-regime artifacts (test-period negative);
   the scalps (VWAP, LW) are negative both eras; Connors decays to ~breakeven OOS.
3. **The only honest new positive is NR7/inside-bar at ~53% win, +0.13%/trade OOS** — a small,
   durable directional lean in the same family (and roughly the same size) as the 3-Family
   direction edge, and like it, too small to survive an option-buying wrapper.
4. **Nothing found beats — or approaches — the deployed credit books' 85–89% win with positive
   net.** On all data this repo can test (7.6y daily, 4.6y intraday, 227k+ trades in this sweep
   alone, plus the prior falsification ledger in `NONFADE_INTRADAY_SEARCH.md` /
   `DAILY_HIGHWIN_SEARCH.md`), the >80%-win + positive-net combination exists ONLY in the gated
   short-premium structure: sold options carry a persistent theta/IV rent, and the c/W-style gates
   select the trades where that rent overpays. High win rate everywhere else is either geometry
   (illusion) or regime luck.

*Research only — nothing deployed, no config or engine changes. Data: Upstox V3 historical
(daily 2018→2026-07, 5-min 2022-01→2026-07-30), fetched 2026-07-31.*
