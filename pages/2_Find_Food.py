"""NGOs: priority offers + open board. Volunteers: transport jobs."""
import os

import pandas as pd
import streamlit as st
from sqlalchemy import select

from core import config, safety, ui
from core.db import Listing, Offer, now, session_scope
from core.geo import haversine_km
from core.listings import claim_listing, decline_offer, take_transport

user = ui.start("Find Food", roles=["ngo", "volunteer"], icon="🔎")
st.title("🔎 Find food" if user.role != "volunteer" else "🚗 Transport jobs")

# Auto-refresh every 30 s so new offers appear without a manual reload.
@st.fragment(run_every=30)
def board() -> None:
    flash = st.session_state.pop("flash", None)
    if flash:
        (st.success if flash[0] else st.error)(flash[1])
    n = now()
    with session_scope() as s:
        if user.role == "volunteer":
            jobs = s.scalars(select(Listing).where(Listing.status == "claimed", Listing.volunteer_id.is_(None))).all()
            offered_ids: set[int] = set()
            rows = [j for j in jobs if user.lat is None or
                    haversine_km(user.lat, user.lon, j.lat, j.lon) <= config.VOLUNTEER_RADIUS_KM]
            priority, others = rows, []
        else:
            if not user.verified:
                st.warning("Your NGO account is awaiting admin verification.")
                return
            offered_ids = set(s.scalars(select(Offer.listing_id).where(Offer.ngo_id == user.id, Offer.status == "pending")))
            open_ = s.scalars(select(Listing).where(Listing.status == "open", Listing.pickup_by > n)
                              .order_by(Listing.safe_until)).all()
            priority = [l for l in open_ if l.id in offered_ids]
            others = [l for l in open_ if l.visible_to_all and l.id not in offered_ids]

    shown = priority + others
    if shown:
        st.map(pd.DataFrame({"lat": [l.lat for l in shown], "lon": [l.lon for l in shown]}), size=60)

    heading = "Priority for you" if user.role == "ngo" else "Jobs near you"
    st.subheader(f"⭐ {heading} ({len(priority)})")
    if not priority:
        st.caption("Nothing right now. This page refreshes automatically.")
    for l in priority:
        card(l, offered=True)
    if user.role == "ngo":
        st.subheader(f"🌍 Open to all NGOs ({len(others)})")
        if not others:
            st.caption("Listings appear here when the priority NGOs don't respond in time.")
        for l in others:
            card(l, offered=False)


def card(l: Listing, offered: bool) -> None:
    with st.container(border=True):
        left, right = st.columns([3, 1])
        dist = f"{haversine_km(user.lat, user.lon, l.lat, l.lon):.1f} km away · " if user.lat is not None else ""
        deadline = safety.format_minutes(safety.minutes_left(l.pickup_by, now()))
        left.markdown(f"**{l.title}** — {l.quantity_meals} meals · {'🥦 Veg' if l.veg else '🍗 Non-veg'}")
        left.caption(f"{l.donor.display_name} · {l.address} · {dist}pickup {deadline} · safe until {l.safe_until:%H:%M}")
        if l.description:
            left.write(l.description)
        if user.role == "volunteer":
            left.caption(f"Deliver to: {l.ngo.display_name} — {l.ngo.address or 'address on request'}")
        if l.photo_path and os.path.exists(l.photo_path):
            right.image(l.photo_path)
        b1, b2, _ = left.columns([1, 1, 3])
        if user.role == "volunteer":
            if b1.button("I'll transport this", key=f"take{l.id}", type="primary"):
                with session_scope() as s:
                    ok, msg = take_transport(s, l.id, user)
                st.session_state["flash"] = (ok, msg)
                st.rerun()
        else:
            if b1.button("Claim", key=f"claim{l.id}", type="primary"):
                with session_scope() as s:
                    ok, msg = claim_listing(s, l.id, user)
                st.session_state["flash"] = (ok, msg)
                st.rerun()
            if offered and b2.button("Decline", key=f"decl{l.id}"):
                with session_scope() as s:
                    decline_offer(s, l.id, user)
                st.rerun()


board()
