"""Simple surplus forecasting: average of the same weekday, falling back to the overall average.

Deliberately basic. With little history it says so instead of guessing; swap in scikit-learn
once you have months of real data.
"""
from datetime import date

import pandas as pd
from sqlalchemy import select

from core.db import Listing


def forecast_detail(rows: list[tuple], target: date) -> dict:
    """Expected meals for `target` with a low-to-high range.

    Uses the same weekday in past weeks when there are at least two such days, otherwise the
    overall daily average. Returns expected=None when there is too little history.
    """
    empty = {"expected": None, "low": None, "high": None, "days": 0, "basis": None}
    if not rows:
        return empty
    df = pd.DataFrame(rows, columns=["created_at", "meals"])
    df["date"] = pd.to_datetime(df["created_at"]).dt.normalize()
    daily = df.groupby("date")["meals"].sum()
    same_weekday = daily[daily.index.dayofweek == target.weekday()]
    if len(same_weekday) >= 2:
        sample, basis = same_weekday, "same weekday"
    elif len(daily) >= 3:
        sample, basis = daily, "all days"
    else:
        return {**empty, "days": len(daily)}
    return {"expected": float(sample.mean()), "low": float(sample.min()), "high": float(sample.max()),
            "days": len(sample), "basis": basis}


def forecast_meals(rows: list[tuple], target: date) -> tuple[float | None, int]:
    """rows = [(created_at, quantity_meals)]. Returns (expected_meals or None, days_of_history_used)."""
    d = forecast_detail(rows, target)
    return d["expected"], d["days"]


def donor_forecast_detail(session, donor_id: int, target: date) -> dict:
    rows = session.execute(
        select(Listing.created_at, Listing.quantity_meals).where(Listing.donor_id == donor_id)).all()
    return forecast_detail([tuple(r) for r in rows], target)


def donor_forecast(session, donor_id: int, target: date) -> tuple[float | None, int]:
    rows = session.execute(
        select(Listing.created_at, Listing.quantity_meals).where(Listing.donor_id == donor_id)).all()
    return forecast_meals([tuple(r) for r in rows], target)


def platform_forecast(session, target: date) -> tuple[float, int]:
    """Total expected meals tomorrow across donors with enough history, and how many donors counted."""
    donor_ids = session.scalars(select(Listing.donor_id).distinct()).all()
    total, counted = 0.0, 0
    for donor_id in donor_ids:
        expected, _ = donor_forecast(session, donor_id, target)
        if expected is not None:
            total += expected
            counted += 1
    return round(total), counted
