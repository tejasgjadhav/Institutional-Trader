# Recommendation after the 2026-07-19 audit session — validate, don't modify

**Question asked:** any change in strategy?

**Answer: no geometry or gate change is warranted.** Every modification tested this session was
rejected on the data. What the session actually exposed is a **validation gap, not a strategy gap** —
and that is where the next effort should go.

---

## 1. Everything tested, and why nothing changed

| Proposed change | Result | Verdict |
|---|---|---|
| Skip RBI / Budget / FOMC days | −₹33.1k, both eras agree | ✗ rejected |
| Skip on large overnight gap | sign **inverts** between eras | ✗ regime artifact |
| Skip on India VIX level / spike | −₹123.7k / −₹17.2k; flagged days were the **best** (92.9% win) | ✗ rejected |
| Skip heavyweight earnings days | −₹14.1k NIFTY, −₹7.0k SENSEX | ✗ rejected |
| Skip geopolitical shock days | those 7 expiries went **7/7, +21.4%m** | ✗ rejected |
| Longer Donchian window (D10/15/20) | D5 wins on total edge/mo | ✗ keep D5 |
| Extend NIFTY's rv5<0.9 to SENSEX/BNF | costs money at every threshold | ✗ rejected |

Two things *were* deployed, both **risk exclusions rather than edges**: the election blackout
(₹0 measured cost, never triggered) and a minimum credit/width of 0.04 on SENSEX/BANKNIFTY. Plus
BANKNIFTY itself was rejected.

**The mechanism behind all the rejections:** this is a short-volatility book. It is *paid for visible
fear*. Filters that key on ex-ante-visible stress remove exactly the trades where the market overpays.

---

## 2. The actual problem — 87% of the claimed P&L is unverified

| Book | ₹/mo | Basis |
|---|---|---|
| ★ Stock fade v2 UNION | ~₹20,000 | **prior study · not re-measured** |
| Stock credit v1 | ~₹12,000 | **prior study · not re-measured · no per-trade file exists** |
| 0DTE SENSEX | ₹3,153 | measured this session |
| 0DTE NIFTY | ₹1,771 | measured this session |
| **Total** | **₹36,924** | **₹32,000 of it (87%) unverified** |

That would be tolerable if the unverified numbers were usually right. **They are not.** Every stale
figure checked this session came in optimistic:

| Claimed | Measured | Error |
|---|---|---|
| BANKNIFTY 91% win / ₹1,500 per month | 78.6% / **₹141** | **~10× overstated** |
| NIFTY 0DTE ₹2,500 per month | ₹1,771 | −29% |
| SENSEX 0DTE ₹3,200 per month | ₹3,153 | ✓ accurate |

Two of three were overstated, one by an order of magnitude. There is no reason to assume the two
stock books — carrying 87% of the total — are the exception.

**Independent corroboration:** v2's own measured figures imply **≈97% per month on deployed capital**
(~₹22.4k profit against ~₹23.1k average tied up, from +52.3% per trade over a 12.1-day hold). That is
not a credible live return. It does not mean v2 has no edge; it means the *magnitude* is inflated, and
it matches the repo's long-standing "the backtest is OPTIMISTIC — keep lots at 1" warning.

---

## 3. Recommendations, in priority order

**① Audit the two stock books the same way the 0DTE books were audited. (highest value by far)**
Specifically, produce for v2 and v1 what now exists for 0DTE: a persisted per-trade file, win rate by
calendar year, return on capital per lot in rupees, avg win vs avg loss, measured holding period, and
an adversarial audit (bad prints, outlier dependence, survivorship, liquidity floors on *both* legs).
v1 currently has **no per-trade file at all**, which is why its cells read "—" rather than carrying
numbers. Until this lands, ₹32,000 of the monthly model is an assertion.

**② Reconsider the plan-on haircut.** The UI plans on 80% of model. Applying a 20% haircut to numbers
that may themselves be 2–3× too high is not conservative. Until the stock audit lands, **~50% of model
is the more defensible planning figure** (≈₹18.5k rather than ≈₹29.5k at 1 lot). *Not changed in the
engine or UI — a planning assumption needs your sign-off.*

**③ Do not resize, do not add books, do not add filters.** Nothing in this session's evidence supports
any of them. Keep lots at 1.

**④ Optional, low priority — capital efficiency observation.** On a per-day-of-capital basis the 0DTE
books match or beat the leader (SENSEX +7.6%/day, NIFTY +4.7%/day, v2 +4.3%/day), but 0DTE capital sits
idle ~90% of the month. NIFTY and SENSEX expire on different days, so a single capital pool already
serves both. There is no obvious way to deploy 0DTE more often without adding indices — and the one
index tried (BANKNIFTY) was just rejected. Filed as an observation, **not** a recommendation.

---

## 4. What would change this verdict

- The stock audit showing v2/v1 hold up → the ₹36,924 becomes trustworthy and sizing can be discussed.
- The stock audit showing them inflated like BANKNIFTY → the portfolio is much smaller than believed,
  and the priority becomes deciding what is actually worth running.

Either way the next action is the same, and it is measurement rather than modification.

Scripts from this session: `ndte13`–`ndte21` in `studies/ndte/`. Studies: `ZERO_DTE_EVENT_DAYS.md`,
`ZERO_DTE_PREOPEN_SIGNALS.md`, `ZERO_DTE_EARNINGS_SHOCKS.md`, `BANKNIFTY_0DTE_REJECTION.md`,
`DONCHIAN_5_10_15_20.md`.
