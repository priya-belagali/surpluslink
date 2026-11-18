"""Smart matching: rank NGOs, offer to the best one, escalate if nobody answers."""
from datetime import timedelta
from types import SimpleNamespace

from sqlalchemy import select, update

from core import config
from core.db import Listing, Offer, User, now
from core.geo import haversine_km
from core.notify import notify
from core.safety import format_duration


def rank_ngos(session, listing) -> list[tuple[User, float, float]]:
    """Return [(ngo, score, distance_km)] best first. Lower score is better.

    `listing` only needs .lat, .lon and .quantity_meals, so a plain object works for forecasts.
    """
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
            score += 15  # cannot absorb the whole batch: strongly deprioritise
        if ngo.has_vehicle:
            score -= 4  # can collect without waiting for a volunteer
        ranked.append((ngo, round(score, 2), round(dist, 1)))
    ranked.sort(key=lambda r: r[1])
    return ranked


def pending_offer(session, listing_id: int) -> Offer | None:
    return session.scalar(
        select(Offer).where(Offer.listing_id == listing_id, Offer.status == "pending").order_by(Offer.id.desc())
    )


def offer_next(session, listing: Listing) -> bool:
    """Offer the listing to the next-best NGO not yet asked. If none remain, open it to everyone."""
    already = set(session.scalars(select(Offer.ngo_id).where(Offer.listing_id == listing.id)))
    for ngo, _score, dist in rank_ngos(session, listing):
        if ngo.id in already:
            continue
        expires = now() + timedelta(seconds=config.OFFER_TIMEOUT_SEC)
        session.add(Offer(listing_id=listing.id, ngo_id=ngo.id, expires_at=expires))
        notify(
            session,
            ngo.id,
            f"Offer: {listing.quantity_meals} meals ({listing.title}) from {listing.donor.display_name}, "
            f"{dist} km away. Respond in the app within {format_duration(config.OFFER_TIMEOUT_SEC)}.",
        )
        return True

    listing.visible_to_all = True
    listing.opened_to_all_at = now()
    for ngo, _s, _d in rank_ngos(session, listing):
        notify(session, ngo.id, f"Open to all NGOs: {listing.quantity_meals} meals ({listing.title}).")
    return False


def start_matching(session, listing: Listing) -> None:
    offer_next(session, listing)


def heads_up(session, donor: User, expected_meals: int, when_text: str, limit: int = 3) -> list[str]:
    """Tell the nearest NGOs to expect surplus from this donor. Returns the NGO names alerted."""
    if donor.lat is None or expected_meals < 1:
        return []
    probe = SimpleNamespace(lat=donor.lat, lon=donor.lon, quantity_meals=expected_meals)
    names = []
    for ngo, _score, dist in rank_ngos(session, probe)[:limit]:
        notify(session, ngo.id,
               f"Heads-up: {donor.display_name} expects about {expected_meals} meals of surplus {when_text}, "
               f"{dist} km from you. No action is needed yet.")
        names.append(ngo.display_name)
    return names


def tick(session) -> dict:
    """Housekeeping: expire stale listings and escalate unanswered offers. Safe to call often."""
    n = now()
    expired_listings = escalated = 0

    stale = session.scalars(
        select(Listing).where(Listing.status == "open", (Listing.pickup_by <= n) | (Listing.safe_until <= n))
    ).all()
    for listing in stale:
        listing.status = "expired"
        listing.expired_at = n
        session.execute(
            update(Offer).where(Offer.listing_id == listing.id, Offer.status == "pending")
            .values(status="cancelled", resolved_at=n)
        )
        notify(session, listing.donor_id, f"Your listing '{listing.title}' expired without being collected.")
        expired_listings += 1

    timed_out = session.scalars(select(Offer).where(Offer.status == "pending", Offer.expires_at <= n)).all()
    for offer in timed_out:
        offer.status = "expired"
        offer.resolved_at = n
        listing = session.get(Listing, offer.listing_id)
        if listing and listing.status == "open":
            offer_next(session, listing)
            escalated += 1

    session.flush()
    return {"expired_listings": expired_listings, "escalated": escalated}
