"""Run with:  pytest   (uses a throwaway SQLite file, never your real data)."""
import os
import tempfile
from datetime import timedelta

# Must be set BEFORE importing anything from core.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["OFFER_TIMEOUT_MIN"] = "15"

import pytest  # noqa: E402

from core import forecast, geocode, impact, listings, matching, notify, places, records, safety  # noqa: E402
from core.auth import authenticate, register_user  # noqa: E402
from core.db import Base, Listing, Offer, User, engine, init_db, now, session_scope  # noqa: E402
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


# ---------------- cascade, record, alerts, parsing ----------------

def test_cascade_is_visible_in_the_timeline():
    with session_scope() as s:
        donor, near, far = make_world(s)
        near_id = near.id
        lid = post(s, donor).id
        s.query(Offer).update({Offer.expires_at: now() - timedelta(seconds=1)})
    with session_scope() as s:
        matching.tick(s)
        texts = [txt for _, txt in listings.timeline(s, s.get(Listing, lid))]
        assert any("Offered to Near NGO" in x for x in texts)
        assert any("Near NGO did not respond" in x for x in texts)
        assert any("Offered to Far NGO" in x for x in texts)
        first = s.query(Offer).filter_by(ngo_id=near_id).one()
        assert first.status == "expired" and first.resolved_at is not None
        assert matching.pending_offer(s, lid).ngo.display_name == "Far NGO"


def test_delivery_completes_the_schedule_2_record():
    with session_scope() as s:
        donor, near, far = make_world(s)
        donor.fssai_number, near.darpan_id = "DONOR-LIC-1", "DARPAN-1"
        lid = post(s, donor, quantity_meals=40, temperature_c=68.0).id
        assert listings.claim_listing(s, lid, near)[0]
        assert listings.mark_picked_up(s, lid, near)[0]
        ok, _ = listings.mark_delivered(s, lid, near, quantity_distributed=35, area="Ward 5")
        assert ok
        listing = s.get(Listing, lid)
        rows = dict(records.schedule2_rows(listing))
        assert len(rows) == 12
        assert rows["Temperature of food"] == "68.0 degrees C"
        assert rows["Quantity distributed by surplus food distribution organisation"] == "35 meals"
        assert rows["Area where food is distributed"] == "Ward 5"
        assert rows["Batch number of food product (item)"].startswith("SL-")
        assert "DONOR-LIC-1" in rows["Name and address of the food donor organisation"]
        assert "DARPAN-1" in rows["Name and address of the surplus food distribution organisation"]
        assert records.schedule2_pdf(listing).startswith(b"%PDF")


def test_cannot_distribute_more_than_was_donated():
    with session_scope() as s:
        donor, near, far = make_world(s)
        lid = post(s, donor, quantity_meals=10).id
        listings.claim_listing(s, lid, near)
        listings.mark_picked_up(s, lid, near)
        ok, msg = listings.mark_delivered(s, lid, near, quantity_distributed=999)
        assert ok is False and "between 0 and 10" in msg


def test_heads_up_goes_to_the_nearest_ngos_first():
    with session_scope() as s:
        donor, near, far = make_world(s)
        names = matching.heads_up(s, donor, 60, "tomorrow")
        assert names[0] == "Near NGO" and "Far NGO" in names


def test_repeat_donation_availability_follows_the_food_type(monkeypatch):
    monkeypatch.setitem(safety.SAFE_HOURS, "Dairy-based dishes", 2)  # pretend this type keeps for only 2 hours
    with session_scope() as s:
        donor, near, far = make_world(s)
        post(s, donor, category="Dairy-based dishes")
        again = listings.repost_last(s, donor)
        assert (again.pickup_by - now()).total_seconds() <= 1 * 3600 + 5  # not the fixed 2 hours any more


def test_timeout_can_be_set_in_seconds():
    from core import config
    assert config.OFFER_TIMEOUT_SEC == 15 * 60  # default comes from OFFER_TIMEOUT_MIN
    assert safety.format_duration(90) == "90 seconds" and safety.format_duration(900) == "15 minutes"


def test_geocode_parser_and_phone_format():
    assert geocode.parse_result([{"lat": "12.30", "lon": "76.64", "display_name": "Mysuru"}]) == \
        {"lat": 12.3, "lon": 76.64, "name": "Mysuru"}
    assert geocode.parse_result([]) is None and geocode.parse_result([{"lat": "x"}]) is None
    assert notify.normalize_phone("98450 12345") == "+919845012345"
    assert notify.normalize_phone("+1 (415) 555-0100") == "+14155550100"


def test_places_parser_classifies_and_uses_centres():
    data = {"elements": [
        {"type": "node", "lat": 12.30, "lon": 76.64, "tags": {"amenity": "restaurant", "name": "A"}},
        {"type": "way", "center": {"lat": 12.31, "lon": 76.65}, "tags": {"tourism": "hotel", "name": "B"}},
        {"type": "node", "tags": {"amenity": "canteen"}},  # no coordinates: skipped
    ]}
    out = places.parse_elements(data)
    assert [p["kind"] for p in out] == ["Restaurant or cafe", "Hotel or lodging"]
    assert "around:8000,12.2958,76.6394" in places.build_query(12.2958, 76.6394, 8)


def test_forecast_gives_a_range():
    today = now()
    rows = [(today - timedelta(days=7 * k), 100 + 20 * k) for k in range(1, 4)]
    d = forecast.forecast_detail(rows, today.date())
    assert d["expected"] == 140 and d["days"] == 3 and d["basis"].startswith("same weekday")
    assert round(d["low"], 1) == 114.4 and round(d["high"], 1) == 165.6


# ---------------- learning from offers

def test_adaptive_ranking_demotes_an_ngo_that_ignores_offers():
    with session_scope() as s:
        donor, near, far = make_world(s)
        twin = register_user(s, email="twin@x.com", password="secret1", name="Twin NGO", role="ngo",
                             lat=near.lat, lon=near.lon, capacity_meals=100, has_vehicle=True)
        twin.verified = True
        s.flush()
        listing = post(s, donor)
        for k in range(6):  # "Near NGO" never answered six earlier offers
            start = now() - timedelta(hours=k + 2)
            s.add(Offer(listing_id=listing.id, ngo_id=near.id, status="expired", offered_at=start,
                        expires_at=start + timedelta(minutes=15), resolved_at=start + timedelta(minutes=15)))
        s.flush()
        ranking = matching.rank_details(s, listing)
        assert [r["ngo"].display_name for r in ranking][:2] == ["Twin NGO", "Near NGO"]
        assert ranking[1]["penalty"] > ranking[0]["penalty"] and ranking[1]["p_accept"] < 0.5


def test_offer_outcomes_are_counted_per_ngo():
    from core import intelligence
    with session_scope() as s:
        donor, near, far = make_world(s)
        listing = post(s, donor)
        base = now() - timedelta(hours=1)
        s.add(Offer(listing_id=listing.id, ngo_id=far.id, status="accepted", offered_at=base,
                    expires_at=base + timedelta(minutes=15), resolved_at=base + timedelta(minutes=3)))
        s.add(Offer(listing_id=listing.id, ngo_id=far.id, status="declined", offered_at=base,
                    expires_at=base + timedelta(minutes=15), resolved_at=base + timedelta(minutes=5)))
        s.flush()
        h = intelligence.ngo_history(s)[far.id]
        assert (h.accepted, h.declined, h.expired) == (1, 1, 0) and h.accept_minutes == 3 and h.fail_minutes == 5


def test_demo_data_gives_matching_something_to_learn_from():
    from core import demo, intelligence, learning
    with session_scope() as s:
        demo.seed(s)
        names = {u.id: u.name for u in s.query(User).filter_by(role="ngo")}
        hist = intelligence.ngo_history(s)
        chance = {names[i]: learning.acceptance_probability(h.accepted, h.total) for i, h in hist.items()}
        assert chance["Annapurna Food Bank (demo)"] > chance["Hope Kitchen Trust (demo)"]
        assert demo.seed_if_empty(s) is False  # a second call changes nothing
