"""Available food (NGOs) and transport jobs (volunteers)."""
import os

import pandas as pd
import streamlit as st
from sqlalchemy import select

from core import config, ui
from core.db import Listing, Offer, now, session_scope
from core.geo import haversine_km
from core.listings import claim_listing, decline_offer, take_transport

user = ui.current_user()
ui.require_role(user, ["ngo", "volunteer"])
is_vol = user.role == "volunteer"

ui.page_header(
    "Transport jobs" if is_vol else "Available food",
    "Food that an NGO has claimed and that still needs a driver." if is_vol else
    "The best-matched NGO is asked first. Claim before the offer expires, or it moves to the next NGO.",
)
ui.verification_notice(user)
if user.role == "ngo" and not user.verified:
    st.stop()


def card(l: Listing, *, priority: bool) -> None:
    dist = haversine_km(user.lat, user.lon, l.lat, l.lon) if user.lat is not None else None
    has_photo = bool(l.photo_path and os.path.exists(l.photo_path))
    with st.container(border=True):
        left, right = st.columns([4, 1]) if has_photo else (st.container(), None)
        with left:
            st.markdown(ui.listing_html(l, distance_km=dist), unsafe_allow_html=True)
            if l.description:
                st.caption(l.description)
            if is_vol:
                st.caption(f"Deliver to {l.ngo.display_name}, {l.ngo.address or 'address on request'}")
            b1, b2, _ = st.columns([1.3, 1, 3])
            if is_vol:
                if b1.button("Take this job", key=f"take{l.id}", type="primary"):
                    with session_scope() as s:
                        ok, msg = take_transport(s, l.id, user)
                    st.session_state["flash"] = (ok, msg)
                    st.rerun()
            else:
                if b1.button("Claim this food", key=f"claim{l.id}", type="primary"):
                    with session_scope() as s:
                        ok, msg = claim_listing(s, l.id, user)
                    st.session_state["flash"] = (ok, msg)
                    st.rerun()
                if priority and b2.button("Decline", key=f"decl{l.id}"):
                    with session_scope() as s:
                        decline_offer(s, l.id, user)
                    st.rerun()
        if right is not None:
            right.image(l.photo_path)


@st.fragment(run_every=30)
def board() -> None:
    """Refreshes every 30 seconds so new offers appear without reloading."""
    flash = st.session_state.pop("flash", None)
    if flash:
        (st.success if flash[0] else st.error)(flash[1])

    n = now()
    with session_scope() as s:
        if is_vol:
            jobs = s.scalars(select(Listing).where(Listing.status == "claimed", Listing.volunteer_id.is_(None))).all()
            priority = [j for j in jobs if user.lat is None or
                        haversine_km(user.lat, user.lon, j.lat, j.lon) <= config.VOLUNTEER_RADIUS_KM]
            others: list[Listing] = []
        else:
            offered = set(s.scalars(select(Offer.listing_id).where(Offer.ngo_id == user.id, Offer.status == "pending")))
            open_ = s.scalars(select(Listing).where(Listing.status == "open", Listing.pickup_by > n)
                              .order_by(Listing.safe_until)).all()
            priority = [l for l in open_ if l.id in offered]
            others = [l for l in open_ if (l.visible_to_all or config.DEMO_MODE) and l.id not in offered]

    shown = priority + others
    if shown:
        with st.expander("Map", expanded=True):
            st.map(pd.DataFrame({"lat": [l.lat for l in shown], "lon": [l.lon for l in shown]}),
                   latitude="lat", longitude="lon", color="#17565E", size=150)

    st.subheader(f"Jobs near you ({len(priority)})" if is_vol else f"Priority offers ({len(priority)})")
    if not priority:
        st.info("Nothing waiting for you right now. This page refreshes on its own.")
    for l in priority:
        card(l, priority=True)

    if not is_vol:
        st.subheader(f"Open to all NGOs ({len(others)})")
        if not others:
            st.info("When the first NGO does not respond in time, a listing moves to the next one and finally to everyone."
                    + (" Demo mode is on, so every open listing shows here immediately." if config.DEMO_MODE else ""))
        for l in others:
            card(l, priority=False)


board()
