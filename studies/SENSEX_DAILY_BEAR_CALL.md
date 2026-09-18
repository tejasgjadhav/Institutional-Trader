# SENSEX weekly — DAILY bear call spread, same-day close (user question, 18-Sep-2026)

**Question.** Every trading day at 09:16, sell the SENSEX weekly CE nearest 0.5% above spot and buy the
CE nearest 0.83% above (the deployed 0DTE geometry), close both at 15:29. Non-expiry days are the new
signals (Fri→Wed under the Thursday regime); expiry day is already the deployed 0DTE book. 1 lot,
₹200/day costs (two round trips), win = net > 0. Prices: 1-minute expired-contract candles
(09:16 bar close in, 15:29 bar close out); spot: SENSEX 1-min bars. Script studies/sensex_daily_short.py;
report studies/sensex_daily_report.py; rows research/sensex_daily/.

## Two-month sample first (13-Jul → 16-Sep-2026, 9 weeks, 47 days, lot 20)

| | days | win | gross | net | ₹/month | avg/day | worst | maxDD |
|---|---|---|---|---|---|---|---|---|
| **non-expiry days (the new signals)** | 39 | **46.2%** | +2,820 | **−4,980** | **−1,660** | −128 | −1,651 | −5,422 |
| expiry day (= 0DTE book) | 8 | 87.5% | +4,541 | +2,941 | +980 | +368 | −231 | −231 |

By weekday (non-expiry): **Wed (1-DTE) 70% / +₹1,716 · Tue 70% / −₹8 · Mon 22% / −₹2,320 · Fri 11% / −₹4,527.**
Months: Jul −4,071 · Aug −1,558 · Sep +649.

**Read.** Even GROSS the non-expiry days earn ~₹72/day (₹2,820 over 39) — one session of theta on a
1–6-DTE contract is small — and ₹200/day of costs turns it negative. The loss concentrates on Friday
and Monday (early in the week, most DTE, least decay, full gap/drift exposure). Wednesday, the
1-DTE day, behaves like the 0DTE book's cousin. Nine weeks is far too few to conclude; the full
Oct-2024 → Sep-2026 run (102 weeks) is queued for 15:45 and decides.

Cost note: ₹200/day is brokerage+charges+a tick on two legs; at ₹100/day the non-expiry line is
still −₹1,080 net over the sample. The structural problem is gross theta, not the cost assumption.
