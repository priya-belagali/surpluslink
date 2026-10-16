"""Simple surplus forecasting: average of the same weekday, falling back to the overall average.

Deliberately basic. With little history it says so instead of guessing; swap in scikit-learn
once you have months of real data.
"""
from datetime import date

import pandas as pd
from sqlalchemy import select

from core.db import Listing


def forecast_meals(rows: list[tuple], target: date) -> tuple[float | None, int]:
    """rows = [(created_at, quantity_meals)]. Returns (expected_meals or None, days_of_history_used)."""
    if not rows:
        return None, 0
    df = pd.DataFrame(rows, columns=["created_at", "meals"])
    df["date"] = pd.to_datetime(df["created_at"]).dt.normalize()
    daily = df.groupby("date")["meals"].sum()
    same_weekday = daily[daily.index.dayofweek == target.weekday()]
    if len(same_weekday) >= 2:
        return float(same_weekday.mean()), len(same_weekday)
    if len(daily) >= 3:
        return float(daily.mean()), len(daily)
    return None, len(daily)


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
