"""Run with:  pytest   (uses a throwaway SQLite file, never your real data)."""
import os
import tempfile
from datetime import timedelta

# Must be set BEFORE importing anything from core.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["OFFER_TIMEOUT_MIN"] = "15"

import pytest  # noqa: E402

from core import forecast, impact, listings, matching, safety  # noqa: E402
from core.auth import authenticate, register_user  # noqa: E402
from core.db import Base, Listing, Offer, engine, init_db, now, session_scope  # noqa: E402
from core.geo import haversine_km  # noqa: E402

BASE = (12.97, 77.59)


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    init_db()


def make_world(s):
    donor = register_user(s, email="d@x.com", password="secret1", name="Hotel", role="donor",
                          address="a", lat=BASE[0], lon=BASE[1])
    near = register_user(s, email="n1@x.com", password="secret1", name="Near NGO", role="ngo",
                         lat=BASE[0] + 0.01, lon=BASE[1], capacity_meals=100, has_vehicle=True)
    far = register_user(s, email="n2@x.com", password="secret1", name="Far NGO", role="ngo",
                        lat=BASE[0] + 0.1, lon=BASE[1], capacity_meals=100)
    near.verified = far.verified = True
    s.flush()
    return donor, near, far


def post(s, donor, **kw):
    args = dict(title="Biryani", category="Cooked meal (rice, curry, etc.)", veg=True, quantity_meals=50,
                address="a", lat=BASE[0], lon=BASE[1], cooked_at=now() - timedelta(minutes=20), available_hours=2)
    args.update(kw)
    return listings.create_listing(s, donor, **args)


def test_auth():
    with session_scope() as s:
        register_user(s, email="A@x.com", password="secret1", name="A", role="donor")
        assert authenticate(s, "a@x.com", "secret1") is not None
        assert authenticate(s, "a@x.com", "wrong") is None
        with pytest.raises(ValueError):
            register_user(s, email="a@x.com", password="secret1", name="A", role="donor")


def test_ngo_needs_verification():
    with session_scope() as s:
        ngo = register_user(s, email="n@x.com", password="secret1", name="N", role="ngo")
        assert ngo.verified is False


def test_nearest_ngo_is_offered_first():
    with session_scope() as s:
        donor, near, far = make_world(s)
        listing = post(s, donor)
        offer = s.query(Offer).filter_by(listing_id=listing.id).one()
        assert offer.ngo_id == near.id


def test_only_one_claim_wins():
    with session_scope() as s:
        donor, near, far = make_world(s)
        listing = post(s, donor)
        lid = listing.id
        listing.visible_to_all = True
        assert listings.claim_listing(s, lid, near)[0] is True
        assert listings.claim_listing(s, lid, far)[0] is False


def test_escalation_after_timeout_then_open_to_all():
    with session_scope() as s:
        donor, near, far = make_world(s)
        near_id, far_id = near.id, far.id
        lid = post(s, donor).id
        s.query(Offer).update({Offer.expires_at: now() - timedelta(minutes=1)})
    with session_scope() as s:
        matching.tick(s)
        assert {o.ngo_id for o in s.query(Offer).all()} == {near_id, far_id}  # second NGO now asked
        s.query(Offer).filter_by(status="pending").update({Offer.expires_at: now() - timedelta(minutes=1)})
    with session_scope() as s:
        matching.tick(s)
        assert s.get(Listing, lid).visible_to_all is True


def test_unsafe_food_is_rejected():
    with session_scope() as s:
        donor, *_ = make_world(s)
        with pytest.raises(ValueError):
            post(s, donor, cooked_at=now() - timedelta(hours=3, minutes=50))  # 4h food, nearly spoiled


def test_full_lifecycle_and_impact():
    with session_scope() as s:
        donor, near, far = make_world(s)
        lid = post(s, donor, quantity_meals=40).id
        assert listings.claim_listing(s, lid, near)[0]
        assert listings.mark_delivered(s, lid, near)[0] is False  # must be picked up first
        assert listings.mark_picked_up(s, lid, near)[0]
        assert listings.mark_delivered(s, lid, near)[0]
        stats = impact.stats(s)
        assert stats["meals"] == 40 and stats["deliveries"] == 1


def test_expiry_housekeeping():
    with session_scope() as s:
        donor, *_ = make_world(s)
        lid = post(s, donor).id
        s.get(Listing, lid).pickup_by = now() - timedelta(minutes=1)
    with session_scope() as s:
        assert matching.tick(s)["expired_listings"] == 1
        assert s.get(Listing, lid).status == "expired"


def test_forecast_and_safety_and_geo():
    today = now()
    rows = [(today - timedelta(days=7 * k), 100) for k in range(1, 4)]
    expected, n = forecast.forecast_meals(rows, today.date())
    assert expected == 100 and n == 3
    assert forecast.forecast_meals([], today.date()) == (None, 0)
    assert safety.format_minutes(75) == "1h 15m left" and safety.format_minutes(0) == "expired"
    assert 110 < haversine_km(0, 0, 1, 0) < 112
