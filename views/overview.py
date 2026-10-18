"""Role-specific overview: the numbers that matter and the next step."""
import streamlit as st
from sqlalchemy import func, select

from core import config, impact, ui
from core.db import Listing, Offer, User, now, session_scope
from core.geo import haversine_km

user = ui.current_user()
ui.page_header("Overview", f"Signed in as {user.display_name}.")
ui.verification_notice(user)

ACTIVE = ["open", "claimed", "picked_up"]


def donor_view(s):
    stats = impact.stats(s, user.id)
    active = s.scalars(select(Listing).where(Listing.donor_id == user.id, Listing.status.in_(ACTIVE))
                       .order_by(Listing.id.desc())).all()
    c1, c2, c3 = st.columns(3)
    c1.metric("Meals delivered", stats["meals"])
    c2.metric("Active listings", len(active))
    c3.metric("Waiting for an NGO", sum(l.status == "open" for l in active))
    st.subheader("Active listings")
    if not active:
        st.info("You have no active listings. Post surplus food and nearby NGOs are notified straight away.")
    for l in active:
        with st.container(border=True):
            st.markdown(ui.listing_html(l, badge_html=ui.status_badge(l.status), show_donor=False),
                        unsafe_allow_html=True)
    st.page_link("views/post_food.py", label="Post surplus food")


def ngo_view(s):
    n = now()
    offered = set(s.scalars(select(Offer.listing_id).where(Offer.ngo_id == user.id, Offer.status == "pending")))
    open_ = s.scalars(select(Listing).where(Listing.status == "open", Listing.pickup_by > n)).all()
    priority = [l for l in open_ if l.id in offered]
    others = [l for l in open_ if (l.visible_to_all or config.DEMO_MODE) and l.id not in offered]
    active = s.scalar(select(func.count(Listing.id)).where(Listing.ngo_id == user.id,
                                                           Listing.status.in_(["claimed", "picked_up"])))
    c1, c2, c3 = st.columns(3)
    c1.metric("Priority offers for you", len(priority))
    c2.metric("Open to all NGOs", len(others))
    c3.metric("Pickups in progress", active)
    st.page_link("views/find_food.py", label="See available food")
    st.page_link("views/activity.py", label="Manage my pickups")


def volunteer_view(s):
    jobs = s.scalars(select(Listing).where(Listing.status == "claimed", Listing.volunteer_id.is_(None))).all()
    nearby = [j for j in jobs if user.lat is None or
              haversine_km(user.lat, user.lon, j.lat, j.lon) <= config.VOLUNTEER_RADIUS_KM]
    mine = s.scalar(select(func.count(Listing.id)).where(Listing.volunteer_id == user.id,
                                                         Listing.status.in_(["claimed", "picked_up"])))
    c1, c2 = st.columns(2)
    c1.metric("Jobs near you", len(nearby))
    c2.metric("Your jobs in progress", mine)
    st.page_link("views/find_food.py", label="See transport jobs")
    st.page_link("views/activity.py", label="Manage my jobs")


def admin_view(s):
    pending = s.scalar(select(func.count(User.id)).where(User.role == "ngo", User.verified.is_(False)))
    open_now = s.scalar(select(func.count(Listing.id)).where(Listing.status == "open"))
    c1, c2, c3 = st.columns(3)
    c1.metric("NGOs awaiting approval", pending)
    c2.metric("Open listings", open_now)
    c3.metric("Meals delivered", impact.stats(s)["meals"])
    st.page_link("views/admin.py", label="Open administration")


with session_scope() as s:
    {"donor": donor_view, "ngo": ngo_view, "volunteer": volunteer_view, "admin": admin_view}[user.role](s)
