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
    temperature_c: float | None = None,
) -> Listing:
    n = now()
    if not title.strip():
        raise ValueError("Please give the donation a short title.")
    if quantity_meals < 1:
        raise ValueError("Quantity must be at least 1 meal.")
    if cooked_at > n:
        raise ValueError("Cooked time cannot be in the future.")
    if temperature_c is not None and not (-30 <= temperature_c <= 120):
        raise ValueError("Please check the temperature: it should be between -30 and 120 degrees C.")

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
        pickup_by=pickup_by, photo_path=photo_path, temperature_c=temperature_c,
    )
    session.add(listing)
    session.flush()
    listing.batch_ref = f"SL-{n:%y%m%d}-{listing.id}"
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
        cooked_at=now(), available_hours=min(2.0, max(0.5, safety.SAFE_HOURS.get(last.category, 3) - 1.0)),
        description=last.description, event_type=last.event_type,
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
    if not (has_offer or listing.visible_to_all or config.DEMO_MODE):
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
        .values(status="accepted", resolved_at=n)
    )
    session.execute(
        update(Offer).where(Offer.listing_id == listing_id, Offer.status == "pending")
        .values(status="cancelled", resolved_at=n)
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
    offer.resolved_at = now()
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


def mark_delivered(session, listing_id: int, user: User, quantity_distributed: int | None = None,
                   area: str | None = None) -> tuple[bool, str]:
    """Confirm delivery. The quantity and area go into the surplus-food record."""
    listing = session.get(Listing, listing_id)
    if listing is None:
        return False, "Listing not found."
    if quantity_distributed is not None and not (0 <= quantity_distributed <= listing.quantity_meals):
        return False, f"Quantity distributed must be between 0 and {listing.quantity_meals}."
    ok, msg = _advance(session, listing_id, user, "picked_up", "delivered", "delivered_at")
    if ok:
        listing = session.get(Listing, listing_id)
        listing.qty_distributed = listing.quantity_meals if quantity_distributed is None else quantity_distributed
        listing.area_distributed = (area or "").strip() or None
        notify(session, listing.donor_id,
               f"'{listing.title}' was distributed: {listing.qty_distributed} meals. The record is ready to download.")
    return ok, msg


def timeline(session, listing: Listing) -> list[tuple[datetime, str]]:
    """Every step of a listing's journey in time order, including each offer in the cascade."""
    events = [(listing.created_at, f"Posted by {listing.donor.display_name}")]
    offers = session.scalars(select(Offer).where(Offer.listing_id == listing.id).order_by(Offer.offered_at, Offer.id)).all()
    for o in offers:
        name = o.ngo.display_name
        events.append((o.offered_at, f"Offered to {name}"))
        if o.status == "expired":
            events.append((o.expires_at, f"{name} did not respond; the offer moved on"))
        elif o.status == "declined":
            events.append((o.resolved_at or o.expires_at, f"{name} declined"))
    if listing.opened_to_all_at:
        events.append((listing.opened_to_all_at, "Every NGO in range has been asked; now open to all"))
    if listing.claimed_at and listing.ngo is not None:
        events.append((listing.claimed_at, f"Claimed by {listing.ngo.display_name}"))
    if listing.picked_up_at:
        who = f" by {listing.volunteer.name}" if listing.volunteer is not None else ""
        events.append((listing.picked_up_at, f"Collected{who}"))
    if listing.delivered_at:
        n = listing.qty_distributed if listing.qty_distributed is not None else listing.quantity_meals
        events.append((listing.delivered_at, f"Delivered: {n} meals distributed"))
    if listing.expired_at:
        events.append((listing.expired_at, "Expired without being claimed"))
    events.sort(key=lambda e: e[0])
    return events
