"""Listing lifecycle: create, claim, decline, transport, pick up, deliver."""
from datetime import datetime, timedelta

from sqlalchemy import select, update

from core import config, matching, safety
from core.db import Listing, Offer, User, now
from core.geo import haversine_km
from core.notify import notify


def create_listing(
    session,
    donor: User,
    *,
    title: str,
    category: str,
    veg: bool,
    quantity_meals: int,
    address: str,
    lat: float,
    lon: float,
    cooked_at: datetime,
    available_hours: float,
    description: str | None = None,
    event_type: str | None = None,
    photo_path: str | None = None,
) -> Listing:
    n = now()
    if not title.strip():
        raise ValueError("Please give the donation a short title.")
    if quantity_meals < 1:
        raise ValueError("Quantity must be at least 1 meal.")
    if cooked_at > n:
        raise ValueError("Cooked time cannot be in the future.")

    safe_until = safety.compute_safe_until(category, cooked_at)
    latest_pickup = safe_until - timedelta(minutes=config.PICKUP_BUFFER_MIN)
    pickup_by = min(n + timedelta(hours=available_hours), latest_pickup)
    if pickup_by < n + timedelta(minutes=config.MIN_PICKUP_WINDOW_MIN):
        raise ValueError(
            "This food has too little safe time left to be collected and distributed. "
            "Please do not donate it."
        )

    listing = Listing(
        donor_id=donor.id, title=title.strip(), category=category, veg=veg,
        quantity_meals=quantity_meals, description=description, event_type=event_type,
        address=address, lat=lat, lon=lon, cooked_at=cooked_at, safe_until=safe_until,
        pickup_by=pickup_by, photo_path=photo_path,
    )
    session.add(listing)
    session.flush()
    session.refresh(listing)
    matching.start_matching(session, listing)
    return listing


def repost_last(session, donor: User) -> Listing:
    """One-tap repeat: same details as the donor's last listing, cooked just now."""
    last = session.scalar(select(Listing).where(Listing.donor_id == donor.id).order_by(Listing.id.desc()))
    if last is None:
        raise ValueError("You have no previous donation to repeat yet.")
    return create_listing(
        session, donor, title=last.title, category=last.category, veg=last.veg,
        quantity_meals=last.quantity_meals, address=last.address, lat=last.lat, lon=last.lon,
        cooked_at=now(), available_hours=2, description=last.description, event_type=last.event_type,
    )


def claim_listing(session, listing_id: int, ngo: User) -> tuple[bool, str]:
    if ngo.role != "ngo" or not ngo.verified:
        return False, "Only verified NGOs can claim food."
    listing = session.get(Listing, listing_id)
    if listing is None:
        return False, "Listing not found."
    has_offer = session.scalar(
        select(Offer.id).where(Offer.listing_id == listing_id, Offer.ngo_id == ngo.id, Offer.status == "pending")
    )
    if not (has_offer or listing.visible_to_all):
        return False, "This listing is currently offered to another NGO."

    n = now()
    # Atomic claim: only one NGO can win, even if two click at the same moment.
    result = session.execute(
        update(Listing)
        .where(Listing.id == listing_id, Listing.status == "open", Listing.pickup_by > n)
        .values(status="claimed", ngo_id=ngo.id, claimed_at=n)
    )
    if result.rowcount != 1:
        return False, "Sorry, this listing was just claimed by someone else or has expired."

    session.execute(
        update(Offer).where(Offer.listing_id == listing_id, Offer.status == "pending", Offer.ngo_id == ngo.id)
        .values(status="accepted")
    )
    session.execute(
        update(Offer).where(Offer.listing_id == listing_id, Offer.status == "pending").values(status="cancelled")
    )
    session.refresh(listing)

    notify(session, listing.donor_id, f"{ngo.display_name} will collect your '{listing.title}'.")
    if not ngo.has_vehicle:
        for v in session.scalars(select(User).where(User.role == "volunteer", User.lat.is_not(None))):
            if haversine_km(listing.lat, listing.lon, v.lat, v.lon) <= config.VOLUNTEER_RADIUS_KM:
                notify(session, v.id, f"Transport needed: {listing.quantity_meals} meals from {listing.donor.display_name}.")
    return True, "Claimed! Arrange pickup before the deadline."


def decline_offer(session, listing_id: int, ngo: User) -> None:
    offer = session.scalar(
        select(Offer).where(Offer.listing_id == listing_id, Offer.ngo_id == ngo.id, Offer.status == "pending")
    )
    if offer is None:
        return
    offer.status = "declined"
    listing = session.get(Listing, listing_id)
    if listing and listing.status == "open":
        matching.offer_next(session, listing)


def take_transport(session, listing_id: int, volunteer: User) -> tuple[bool, str]:
    if volunteer.role != "volunteer":
        return False, "Only volunteers can take transport jobs."
    result = session.execute(
        update(Listing)
        .where(Listing.id == listing_id, Listing.status == "claimed", Listing.volunteer_id.is_(None))
        .values(volunteer_id=volunteer.id)
    )
    if result.rowcount != 1:
        return False, "Another volunteer already took this job."
    listing = session.get(Listing, listing_id)
    session.refresh(listing)
    notify(session, listing.ngo_id, f"{volunteer.name} will transport '{listing.title}'.")
    notify(session, listing.donor_id, f"{volunteer.name} is on the way to collect '{listing.title}'.")
    return True, "Thank you! The job is yours."


def _advance(session, listing_id: int, user: User, from_status: str, to_status: str, stamp: str) -> tuple[bool, str]:
    listing = session.get(Listing, listing_id)
    if listing is None or user.id not in (listing.ngo_id, listing.volunteer_id):
        return False, "You are not assigned to this listing."
    result = session.execute(
        update(Listing).where(Listing.id == listing_id, Listing.status == from_status)
        .values(status=to_status, **{stamp: now()})
    )
    if result.rowcount != 1:
        return False, f"Listing is not in '{from_status}' state."
    session.refresh(listing)
    return True, ""


def mark_picked_up(session, listing_id: int, user: User) -> tuple[bool, str]:
    ok, msg = _advance(session, listing_id, user, "claimed", "picked_up", "picked_up_at")
    if ok:
        listing = session.get(Listing, listing_id)
        notify(session, listing.donor_id, f"'{listing.title}' has been picked up. Thank you!")
    return ok, msg


def mark_delivered(session, listing_id: int, user: User) -> tuple[bool, str]:
    ok, msg = _advance(session, listing_id, user, "picked_up", "delivered", "delivered_at")
    if ok:
        listing = session.get(Listing, listing_id)
        notify(session, listing.donor_id, f"'{listing.title}' reached people in need ({listing.quantity_meals} meals).")
    return ok, msg
