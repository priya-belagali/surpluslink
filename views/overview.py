"""Role-specific overview: the numbers that matter, and for donors the live journey of each listing."""
from datetime import timedelta

import streamlit as st
from sqlalchemy import func, select

from core import config, forecast, impact, matching, ui
from core.db import Listing, Offer, User, now, session_scope
from core.geo import haversine_km
from core.listings import timeline

user = ui.current_user()
ui.page_header("Overview", f"{user.display_name}, {ui.ROLE_LABEL[user.role].lower()}")
ui.verification_notice(user)

ACTIVE = ["open", "claimed", "picked_up"]


@st.fragment(run_every=5)
def live_listings() -> None:
    """Refreshes every 5 seconds and moves the cascade along, so offers can be watched passing from NGO to NGO."""
    ui.run_tick()
    at = now()
    with session_scope() as s:
        active = s.scalars(select(Listing).where(Listing.donor_id == user.id, Listing.status.in_(ACTIVE))
                           .order_by(Listing.id.desc())).all()
        blocks = [(l, timeline(s, l), matching.pending_offer(s, l.id) if l.status == "open" else None,
                   matching.rank_details(s, l) if l.status == "open" else None) for l in active]
    if not blocks:
        st.info("You have no active listings.")
    for l, events, pending, ranking in blocks:
        with st.container(border=True):
            st.markdown(ui.listing_html(l, show_status=True, show_donor=False, at=at), unsafe_allow_html=True)
            st.markdown(ui.timeline_html(events, pending, at), unsafe_allow_html=True)
            if ranking:
                with st.expander("Why NGOs are asked in this order"):
                    st.dataframe(ui.rank_table(ranking), hide_index=True)
                    st.caption(ui.RANK_NOTE)


def donor_view(s):
    stats = impact.stats(s, user.id)
    active = s.scalars(select(Listing).where(Listing.donor_id == user.id, Listing.status.in_(ACTIVE))).all()
    ui.figures([("Meals delivered", stats["meals"]), ("Active listings", len(active)),
                ("Waiting for an NGO", sum(l.status == "open" for l in active))])
    st.subheader("Listings in progress")
    live_listings()
    st.page_link("views/post_food.py", label="Post surplus food")

    st.subheader("Tomorrow")
    tomorrow = (now() + timedelta(days=1)).date()
    f = forecast.donor_forecast_detail(s, user.id, tomorrow)
    if f["expected"] is None:
        st.caption("There is not enough history for a forecast yet.")
        return
    expected = round(f["expected"])
    how = (f"The range covers about 80 percent of the same-weekday totals in {f['days']} earlier weeks, counting days with no surplus."
           if f["basis"].startswith("same weekday") else f"Based on {f['days']} days of history only, so treat it as rough.")
    st.markdown(f"Expected surplus on {tomorrow:%A}: about **{expected} meals**, likely between {round(f['low'])} and "
                f"{round(f['high'])}. {how}")
    if st.button("Alert the nearest NGOs in advance"):
        with session_scope() as s2:
            names = matching.heads_up(s2, user, expected, f"on {tomorrow:%A}")
        if names:
            st.success("Heads-up sent to " + ", ".join(names) + ".")
        else:
            st.warning("No approved NGO with a saved location is in range.")


def ngo_view(s):
    n = now()
    offered = set(s.scalars(select(Offer.listing_id).where(Offer.ngo_id == user.id, Offer.status == "pending")))
    open_ = s.scalars(select(Listing).where(Listing.status == "open", Listing.pickup_by > n)).all()
    priority = [l for l in open_ if l.id in offered]
    others = [l for l in open_ if (l.visible_to_all or config.DEMO_MODE) and l.id not in offered]
    active = s.scalar(select(func.count(Listing.id)).where(Listing.ngo_id == user.id,
                                                           Listing.status.in_(["claimed", "picked_up"])))
    ui.figures([("Offers waiting for you", len(priority)), ("Open to all NGOs", len(others)), ("Pickups in progress", active)])
    st.page_link("views/find_food.py", label="Available food")
    st.page_link("views/activity.py", label="My pickups")


def volunteer_view(s):
    jobs = s.scalars(select(Listing).where(Listing.status == "claimed", Listing.volunteer_id.is_(None))).all()
    nearby = [j for j in jobs if user.lat is None or
              haversine_km(user.lat, user.lon, j.lat, j.lon) <= config.VOLUNTEER_RADIUS_KM]
    mine = s.scalar(select(func.count(Listing.id)).where(Listing.volunteer_id == user.id,
                                                         Listing.status.in_(["claimed", "picked_up"])))
    ui.figures([("Jobs near you", len(nearby)), ("Your jobs in progress", mine)])
    st.page_link("views/find_food.py", label="Transport jobs")
    st.page_link("views/activity.py", label="My jobs")


def admin_view(s):
    pending = s.scalar(select(func.count(User.id)).where(User.role == "ngo", User.verified.is_(False)))
    open_now = s.scalar(select(func.count(Listing.id)).where(Listing.status == "open"))
    stats = impact.stats(s)
    ui.figures([("NGOs awaiting approval", pending), ("Open listings", open_now),
                ("Meals delivered", stats["meals"]), ("Records available", stats["deliveries"])])
    st.page_link("views/admin.py", label="Administration")


with session_scope() as s:
    {"donor": donor_view, "ngo": ngo_view, "volunteer": volunteer_view, "admin": admin_view}[user.role](s)
