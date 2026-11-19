"""Bridge between the database and the learning routines."""
from sqlalchemy import select

from core.db import Offer
from core.learning import NgoHistory


def ngo_history(session) -> dict[int, NgoHistory]:
    """What each NGO has done with past offers: accepted, declined, or never responded, and how long it took."""
    rows = session.execute(
        select(Offer.ngo_id, Offer.status, Offer.offered_at, Offer.resolved_at)
        .where(Offer.status.in_(["accepted", "declined", "expired"]))
    ).all()
    out: dict[int, NgoHistory] = {}
    for ngo_id, status, offered_at, resolved_at in rows:
        if resolved_at is None:
            continue
        minutes = max((resolved_at - offered_at).total_seconds() / 60, 0.0)
        h = out.setdefault(ngo_id, NgoHistory())
        if status == "accepted":
            h.accepted += 1
            h.accept_minutes += minutes
        elif status == "declined":
            h.declined += 1
            h.fail_minutes += minutes
        else:
            h.expired += 1
            h.fail_minutes += minutes
    return out
