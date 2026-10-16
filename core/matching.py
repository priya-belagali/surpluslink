"""Smart matching: rank NGOs, offer to the best one first, escalate if nobody responds."""
from datetime import timedelta

from sqlalchemy import select, update

from core import config
from core.db import Listing, Offer, User, now
from core.geo import haversine_km
from core.notify import notify


def rank_ngos(session, listing: Listing) -> list[tuple[User, float, float]]:
    """Return [(ngo, score, distance_km)] best first. Lower score is better."""
    ngos = session.scalars(
        select(User).where(User.role == "ngo", User.verified.is_(True), User.lat.is_not(None))
    ).all()
    ranked = []
    for ngo in ngos:
        dist = haversine_km(listing.lat, listing.lon, ngo.lat, ngo.lon)
        if dist > config.MAX_MATCH_RADIUS_KM:
            continue
        score = dist
        if ngo.capacity_meals < listing.quantity_meals:
            score += 15  # can't absorb the whole batch: strongly deprioritise
        if ngo.has_vehicle:
            score -= 4  # can collect without waiting for a volunteer
        ranked.append((ngo, round(score, 2), round(dist, 1)))
    ranked.sort(key=lambda r: r[1])
    return ranked


def offer_next(session, listing: Listing) -> bool:
    """Offer the listing to the next-best NGO not yet asked. If none remain, open it to everyone."""
    already = set(session.scalars(select(Offer.ngo_id).where(Offer.listing_id == listing.id)))
    for ngo, _score, dist in rank_ngos(session, listing):
        if ngo.id in already:
            continue
        expires = now() + timedelta(minutes=config.OFFER_TIMEOUT_MIN)
        session.add(Offer(listing_id=listing.id, ngo_id=ngo.id, expires_at=expires))
        notify(
            session,
            ngo.id,
            f"Priority offer: {listing.quantity_meals} meals ({listing.title}) from "
            f"{listing.donor.display_name}, {dist} km away. Respond within {config.OFFER_TIMEOUT_MIN} min.",
        )
        return True

    listing.visible_to_all = True
    for ngo, _s, _d in rank_ngos(session, listing):
        notify(session, ngo.id, f"Now open to all NGOs: {listing.quantity_meals} meals ({listing.title}).")
    return False


def start_matching(session, listing: Listing) -> None:
    offer_next(session, listing)


def tick(session) -> dict:
    """Housekeeping: expire stale listings and escalate unanswered offers. Safe to call often."""
    n = now()
    expired_listings = escalated = 0

    stale = session.scalars(
        select(Listing).where(Listing.status == "open", (Listing.pickup_by <= n) | (Listing.safe_until <= n))
    ).all()
    for listing in stale:
        listing.status = "expired"
        session.execute(
            update(Offer).where(Offer.listing_id == listing.id, Offer.status == "pending").values(status="cancelled")
        )
        notify(session, listing.donor_id, f"Your listing '{listing.title}' expired without being collected.")
        expired_listings += 1

    timed_out = session.scalars(
        select(Offer).where(Offer.status == "pending", Offer.expires_at <= n)
    ).all()
    for offer in timed_out:
        offer.status = "expired"
        listing = session.get(Listing, offer.listing_id)
        if listing and listing.status == "open":
            offer_next(session, listing)
            escalated += 1

    session.flush()
    return {"expired_listings": expired_listings, "escalated": escalated}
