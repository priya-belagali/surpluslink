"""Impact reporting based on delivered listings. Constants in config are rough estimates."""
from datetime import timedelta

import pandas as pd
from sqlalchemy import func, select

from core import config
from core.db import Listing, User, now


def stats(session, donor_id: int | None = None) -> dict:
    q = select(func.coalesce(func.sum(Listing.quantity_meals), 0), func.count(Listing.id),
               func.count(func.distinct(Listing.donor_id))).where(Listing.status == "delivered")
    if donor_id:
        q = q.where(Listing.donor_id == donor_id)
    meals, deliveries, donors = session.execute(q).one()
    kg = meals * config.KG_PER_MEAL
    return {"meals": int(meals), "deliveries": deliveries, "donors": donors,
            "kg_food": round(kg, 1), "co2e_kg": round(kg * config.CO2E_KG_PER_KG_FOOD, 1)}


def daily_series(session, days: int = 30, donor_id: int | None = None) -> pd.DataFrame:
    since = now() - timedelta(days=days)
    q = select(Listing.delivered_at, Listing.quantity_meals).where(
        Listing.status == "delivered", Listing.delivered_at >= since)
    if donor_id:
        q = q.where(Listing.donor_id == donor_id)
    rows = session.execute(q).all()
    if not rows:
        return pd.DataFrame({"meals": []})
    df = pd.DataFrame(rows, columns=["when", "meals"])
    df["date"] = pd.to_datetime(df["when"]).dt.date
    return df.groupby("date")[["meals"]].sum()


def leaderboard(session, limit: int = 10) -> list[tuple[str, int]]:
    q = (select(User.org_name, User.name, func.sum(Listing.quantity_meals).label("m"))
         .join(Listing, Listing.donor_id == User.id)
         .where(Listing.status == "delivered")
         .group_by(User.id).order_by(func.sum(Listing.quantity_meals).desc()).limit(limit))
    return [(org or name, int(m)) for org, name, m in session.execute(q).all()]
