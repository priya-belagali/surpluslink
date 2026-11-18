"""Demo data: clearly labelled sample accounts and eight weeks of history.

Used by seed_demo.py, and by the app itself when SEED_DEMO_ON_EMPTY=true so a freshly deployed
site is not empty. Every demo account uses the password demo123 and has "(demo)" in its name.
"""
import random
from datetime import timedelta

from sqlalchemy import func, select

from core import config
from core.auth import register_user
from core.db import Listing, User, now

DEMO_PASSWORD = "demo123"


def _near(rng, base, km=6.0):
    d = km / 111  # one degree of latitude is about 111 km
    return base[0] + rng.uniform(-d, d), base[1] + rng.uniform(-d, d)


def seed_if_empty(session) -> bool:
    if session.scalar(select(func.count(User.id)).where(User.role == "donor")):
        return False
    seed(session)
    return True


def seed(session) -> None:
    rng = random.Random(7)
    base = config.CITY_PRESETS[config.COVERAGE_CITY]
    city = config.COVERAGE_CITY

    donors = []
    for i, name in enumerate(["Cauvery Banquets (demo)", "Lakeview Caterers (demo)", "Technopark Canteen (demo)"], 1):
        lat, lon = _near(rng, base)
        donors.append(register_user(
            session, email=f"donor{i}@demo.com", password=DEMO_PASSWORD, name=name, role="donor", org_name=name,
            address=f"{name}, {city}", lat=lat, lon=lon, fssai_number=f"DEMO-FSSAI-00{i}"))

    ngos = []
    specs = [("Annapurna Food Bank (demo)", 200, True), ("Hope Kitchen Trust (demo)", 80, False),
             ("Seva Meals Society (demo)", 150, True)]
    for i, (name, capacity, vehicle) in enumerate(specs, 1):
        lat, lon = _near(rng, base)
        u = register_user(session, email=f"ngo{i}@demo.com", password=DEMO_PASSWORD, name=name, role="ngo",
                          org_name=name, address=f"{name}, {city}", lat=lat, lon=lon, capacity_meals=capacity,
                          has_vehicle=vehicle, fssai_number=f"DEMO-FSSAI-10{i}", darpan_id=f"DEMO-DARPAN-0{i}")
        u.verified = True
        ngos.append(u)

    lat, lon = _near(rng, base)
    register_user(session, email="vol1@demo.com", password=DEMO_PASSWORD, name="Ravi (volunteer, demo)",
                  role="volunteer", address=city, lat=lat, lon=lon)

    # Eight weeks of delivered history. Weekends are busier (events and weddings).
    n = now()
    serial = 0
    for day in range(56, 0, -1):
        when = (n - timedelta(days=day)).replace(hour=21, minute=0, second=0, microsecond=0)
        for donor in donors:
            if rng.random() < 0.7:
                serial += 1
                meals = rng.randint(30, 80) + (40 if when.weekday() >= 5 else 0)
                ngo = rng.choice(ngos)
                session.add(Listing(
                    donor_id=donor.id, title="Dinner surplus", category="Cooked meal (rice, curry, etc.)",
                    veg=True, quantity_meals=meals, address=donor.address, lat=donor.lat, lon=donor.lon,
                    cooked_at=when - timedelta(hours=1), safe_until=when + timedelta(hours=3),
                    pickup_by=when + timedelta(hours=2), status="delivered", ngo_id=ngo.id,
                    created_at=when, claimed_at=when + timedelta(minutes=10),
                    picked_up_at=when + timedelta(minutes=40), delivered_at=when + timedelta(hours=1, minutes=15),
                    temperature_c=float(rng.randint(62, 75)), batch_ref=f"SL-{when:%y%m%d}-D{serial}",
                    qty_distributed=meals, area_distributed=f"Community kitchen, {city}"))
