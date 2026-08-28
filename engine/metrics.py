"""Scoring a set of trades honestly.

Every function here takes a sequence of per-trade returns, in percent, net of costs. They are
deliberately plain: a win rate on its own is not a result, so the summary always reports the
sample size, the spread of outcomes and a t-statistic beside it.

studies/SAMPLE_SIZE.md says what a given number of trades can and cannot settle.
studies/A_RANDOM_BASELINE.md says what to compare against.

Study code. Not investment advice. See DISCLAIMER.md.
"""
import math
import random
import statistics as st


def summarise(returns) -> dict:
    """Headline numbers for a set of per-trade returns, in percent."""
    r = [float(x) for x in returns]
    n = len(r)
    if n == 0:
        return {"trades": 0}
    mean = st.fmean(r)
    sd = st.pstdev(r) if n < 2 else st.stdev(r)
    t = mean / (sd / math.sqrt(n)) if sd > 0 else float("nan")
    wins = [x for x in r if x > 0]
    losses = [x for x in r if x <= 0]
    return {
        "trades": n,
        "win_rate_pct": round(len(wins) / n * 100, 1),
        "mean_pct": round(mean, 4),
        "median_pct": round(st.median(r), 4),
        "stdev_pct": round(sd, 3),
        "t_stat": round(t, 2),
        "avg_win_pct": round(st.fmean(wins), 3) if wins else 0.0,
        "avg_loss_pct": round(st.fmean(losses), 3) if losses else 0.0,
        "best_pct": round(max(r), 2),
        "worst_pct": round(min(r), 2),
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) else None,
    }


def max_drawdown_pct(returns) -> float:
    """Worst peak-to-trough fall of the cumulative curve, in percent."""
    equity, peak, worst = 0.0, 0.0, 0.0
    for x in returns:
        equity += float(x)
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return round(worst, 2)


def longest_losing_run(returns) -> int:
    """The longest streak of losing trades. Decide before going live whether you can sit through it."""
    run = best = 0
    for x in returns:
        run = run + 1 if float(x) <= 0 else 0
        best = max(best, run)
    return best


def bootstrap_mean_ci(returns, iterations: int = 2000, level: float = 0.95, seed: int = 7):
    """A confidence interval for the mean, by resampling. Check whether it contains zero."""
    r = [float(x) for x in returns]
    if len(r) < 10:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(iterations):
        means.append(st.fmean(rng.choices(r, k=len(r))))
    means.sort()
    lo = means[int((1 - level) / 2 * iterations)]
    hi = means[int((1 + level) / 2 * iterations) - 1]
    return (round(lo, 4), round(hi, 4))


def report(returns, label: str = "strategy") -> str:
    """One readable block. Print this rather than quoting a win rate on its own."""
    s = summarise(returns)
    if not s.get("trades"):
        return f"{label}: no trades"
    ci = bootstrap_mean_ci(returns)
    lines = [
        f"{label}",
        f"  trades {s['trades']}   win rate {s['win_rate_pct']}%",
        f"  mean {s['mean_pct']}%   median {s['median_pct']}%   sd {s['stdev_pct']}%   t {s['t_stat']}",
        f"  avg win {s['avg_win_pct']}%   avg loss {s['avg_loss_pct']}%   profit factor {s['profit_factor']}",
        f"  best {s['best_pct']}%   worst {s['worst_pct']}%   max drawdown {max_drawdown_pct(returns)}%",
        f"  longest losing run {longest_losing_run(returns)} trades",
    ]
    if ci:
        lines.append(f"  95% interval for the mean {ci[0]}% to {ci[1]}%"
                     f"{'   (contains zero)' if ci[0] <= 0 <= ci[1] else ''}")
    return "\n".join(lines)
