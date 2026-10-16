"""Fill the database with demo accounts and ~8 weeks of history so every screen has data.

Run once:  python seed_demo.py
All demo accounts use the password:  demo123
Re-running is safe: it skips if demo data already exists.
"""
import random
from datetime import timedelta

from sqlalchemy import select

from core import config
from core.auth import register_user
from core.db import Listing, User, init_db, now, session_scope

SEED_CITY = "Bengaluru"  # change to any key in config.CITY_PRESETS
random.seed(7)


def near(base, km=6):
    """A random point within roughly `km` kilometres of base (1 degree is about 111 km)."""
    d = km / 111
    return base[0] + random.uniform(-d, d), base[1] + random.uniform(-d, d)


def main() -> None:
    init_db()
    base = config.CITY_PRESETS[SEED_CITY]
    with session_scope() as s:
        if s.scalar(select(User).where(User.email == "donor1@demo.com")):
            print("Demo data already exists - nothing to do.")
            return

        donors = []
        for i, name in enumerate(["Grand Orchid Hotel", "Spice Route Caterers", "Tech Park Canteen"], 1):
            lat, lon = near(base)
            donors.append(register_user(s, email=f"donor{i}@demo.com", password="demo123", name=name,
                                        role="donor", org_name=name, address=f"{name}, {SEED_CITY}", lat=lat, lon=lon))
        ngos = []
        specs = [("Annapurna Food Bank", 200, True), ("Hope Kitchen Trust", 80, False), ("Seva Meals Society", 150, True)]
        for i, (name, cap, veh) in enumerate(specs, 1):
            lat, lon = near(base)
            u = register_user(s, email=f"ngo{i}@demo.com", password="demo123", name=name, role="ngo", org_name=name,
                              address=f"{name}, {SEED_CITY}", lat=lat, lon=lon, capacity_meals=cap, has_vehicle=veh)
            u.verified = True
            ngos.append(u)
        lat, lon = near(base)
        register_user(s, email="vol1@demo.com", password="demo123", name="Ravi (volunteer)", role="volunteer",
                      address=SEED_CITY, lat=lat, lon=lon)

        # Eight weeks of delivered history: weekends are busier (events/weddings).
        n = now()
        for day in range(56, 0, -1):
            when = (n - timedelta(days=day)).replace(hour=21, minute=0, second=0, microsecond=0)
            for donor in donors:
                if random.random() < 0.7:
                    meals = random.randint(30, 80) + (40 if when.weekday() >= 5 else 0)
                    ngo = random.choice(ngos)
                    s.add(Listing(
                        donor_id=donor.id, title="Dinner surplus", category="Cooked meal (rice, curry, etc.)",
                        veg=True, quantity_meals=meals, address=donor.address, lat=donor.lat, lon=donor.lon,
                        cooked_at=when - timedelta(hours=1), safe_until=when + timedelta(hours=3),
                        pickup_by=when + timedelta(hours=2), status="delivered", ngo_id=ngo.id,
                        created_at=when, claimed_at=when + timedelta(minutes=10),
                        picked_up_at=when + timedelta(minutes=40), delivered_at=when + timedelta(hours=1, minutes=15)))
    print("Demo data created. Log in with donor1@demo.com / ngo1@demo.com / vol1@demo.com, password demo123.")


if __name__ == "__main__":
    main()
