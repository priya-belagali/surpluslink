"""Small, explainable learning routines.

Nothing here touches the database or Streamlit, so each routine can be tested and simulated on its own.

1. Offer outcomes -> how likely each NGO is to accept, and how long it typically takes (Bayesian smoothing).
2. Daily surplus -> a ridge regression on weekday and trend, with a walk-forward back-test.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

# ---------------------------------------------------------------- NGO behaviour

PRIOR_ACCEPT = (2.0, 2.0)  # Beta(2, 2): with no history we assume about 50 percent, and move slowly
MINUTES_PER_KM = 2.0       # rough urban travel speed (30 km/h), to put waiting time and distance on one scale


@dataclass
class NgoHistory:
    accepted: int = 0
    declined: int = 0
    expired: int = 0           # the NGO never responded before the offer ran out
    accept_minutes: float = 0.0  # total time taken by offers that were accepted
    fail_minutes: float = 0.0    # total time consumed by offers that were declined or expired

    @property
    def total(self) -> int:
        return self.accepted + self.declined + self.expired

    @property
    def failed(self) -> int:
        return self.declined + self.expired


def acceptance_probability(accepted: int, total: int, prior: tuple[float, float] = PRIOR_ACCEPT) -> float:
    """Share of offers accepted, pulled towards 50 percent when there is little evidence."""
    a, b = prior
    return (accepted + a) / (total + a + b)


def smoothed_mean(total_minutes: float, count: int, prior_mean: float, prior_weight: float = 2.0) -> float:
    """Average that starts at prior_mean and moves towards the data as observations arrive."""
    return (total_minutes + prior_mean * prior_weight) / (count + prior_weight)


def expected_wait_minutes(h: NgoHistory, timeout_min: float) -> float:
    """Expected minutes before this NGO resolves an offer (accepts it, or fails and we must move on)."""
    p = acceptance_probability(h.accepted, h.total)
    accept_mean = smoothed_mean(h.accept_minutes, h.accepted, prior_mean=timeout_min / 3)
    fail_mean = smoothed_mean(h.fail_minutes, h.failed, prior_mean=timeout_min)
    return p * accept_mean + (1 - p) * fail_mean


def wait_penalty_km(wait_minutes: float) -> float:
    """Waiting time expressed as extra kilometres, so it can be added to the distance score."""
    return wait_minutes / MINUTES_PER_KM


# ---------------------------------------------------------------- surplus forecast

def daily_totals(rows: list[tuple], as_of: date) -> tuple[list[date], np.ndarray]:
    """Meals per calendar day up to as_of. Days with no donation count as zero, which matters:
    leaving them out makes a donor who gives only now and then look like a steady one."""
    totals: dict[date, float] = {}
    for when, meals in rows:
        d = when.date() if hasattr(when, "date") else when
        if d <= as_of:
            totals[d] = totals.get(d, 0.0) + float(meals)
    if not totals:
        return [], np.array([])
    start = min(totals)
    days = [start + timedelta(days=i) for i in range((as_of - start).days + 1)]
    return days, np.array([totals.get(d, 0.0) for d in days])


def weekday_forecast(rows: list[tuple], target: date, as_of: date | None = None, min_days: int = 14) -> dict | None:
    """Expected meals on `target` from the same weekday in earlier weeks, zero days included.

    The range is the mean plus or minus 1.28 standard deviations of those same-weekday totals (about 80
    percent of days if they are roughly bell-shaped). None when there is less than `min_days` of history.
    """
    as_of = as_of or (target - timedelta(days=1))
    days, y = daily_totals(rows, as_of)
    if len(days) < min_days:
        return None
    same = np.array([v for d, v in zip(days, y) if d.weekday() == target.weekday()])
    sample = same if len(same) >= 2 else y
    mean = float(sample.mean())
    sd = float(sample.std(ddof=1)) if len(sample) > 1 else 0.0
    return {"expected": mean, "low": max(mean - 1.28 * sd, 0.0), "high": mean + 1.28 * sd,
            "days": len(sample), "basis": "same weekday, zero days included" if len(same) >= 2 else "all days", "sigma": sd}


def naive_forecast(rows: list[tuple], as_of: date) -> float | None:
    """The comparison point: tomorrow will look like the overall daily average."""
    days, y = daily_totals(rows, as_of)
    return float(y.mean()) if len(days) else None


def backtest(rows: list[tuple], as_of: date, horizon_days: int = 14, min_train: int = 14) -> dict | None:
    """Walk forward over the last `horizon_days`, predicting each day from earlier data only.

    Returns the average absolute error, in meals per day, of the weekday forecast and of the naive average.
    """
    days, actual = daily_totals(rows, as_of)
    if len(days) < min_train + 7:
        return None
    err_weekday, err_naive = [], []
    for i in range(len(days) - horizon_days, len(days)):
        if i < min_train:
            continue
        prior_end = days[i] - timedelta(days=1)
        model = weekday_forecast(rows, days[i], as_of=prior_end, min_days=min_train)
        naive = naive_forecast(rows, prior_end)
        if model is None or naive is None:
            continue
        err_weekday.append(abs(model["expected"] - actual[i]))
        err_naive.append(abs(naive - actual[i]))
    if len(err_weekday) < 5:
        return None
    w, n = float(np.mean(err_weekday)), float(np.mean(err_naive))
    return {"mae_weekday": w, "mae_naive": n, "days_tested": len(err_weekday),
            "improvement_pct": (1 - w / n) * 100 if n > 0 else 0.0}
