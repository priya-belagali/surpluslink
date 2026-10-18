"""Each role's own listings and jobs, with status updates for NGOs and volunteers."""
import pandas as pd
import streamlit as st
from sqlalchemy import select

from core import ui
from core.db import Listing, session_scope
from core.listings import mark_delivered, mark_picked_up

user = ui.current_user()
ui.require_role(user, ["donor", "ngo", "volunteer"])

TITLES = {
    "donor": ("My donations", "Everything you have posted and where it stands."),
    "ngo": ("My pickups", "Food you have claimed. Update the status as it moves."),
    "volunteer": ("My jobs", "Transport jobs you have taken."),
    "admin": ("Activity", "Recent listings."),
}
ui.page_header(*TITLES[user.role])

with session_scope() as s:
    q = select(Listing).order_by(Listing.id.desc())
    if user.role == "donor":
        q = q.where(Listing.donor_id == user.id)
    elif user.role == "ngo":
        q = q.where(Listing.ngo_id == user.id)
    elif user.role == "volunteer":
        q = q.where(Listing.volunteer_id == user.id)
    mine = s.scalars(q.limit(100)).all()

if not mine:
    st.info({"donor": "You have not posted anything yet. Use Post surplus food to add your first donation.",
             "ngo": "Food you claim will appear here.",
             "volunteer": "Jobs you take will appear here."}.get(user.role, "Nothing to show yet."))
    st.stop()

if user.role == "donor":
    st.dataframe(pd.DataFrame([{
        "Posted": l.created_at.strftime("%d %b, %H:%M"),
        "Food": l.title,
        "Meals": l.quantity_meals,
        "Status": ui.STATUS_LABEL[l.status],
        "NGO": l.ngo.display_name if l.ngo else "",
        "Volunteer": l.volunteer.name if l.volunteer else "",
    } for l in mine]), hide_index=True)
    st.stop()

for l in mine:
    with st.container(border=True):
        st.markdown(ui.listing_html(l, badge_html=ui.status_badge(l.status)), unsafe_allow_html=True)
        st.caption(f"Pickup contact: {l.donor.phone}" if l.donor.phone else "No phone number on file for this donor.")
        if l.status == "claimed" and st.button("Mark as collected", key=f"pu{l.id}", type="primary"):
            with session_scope() as s:
                ok, msg = mark_picked_up(s, l.id, user)
            if ok:
                st.rerun()
            st.error(msg)
        if l.status == "picked_up" and st.button("Mark as delivered", key=f"dl{l.id}", type="primary"):
            with session_scope() as s:
                ok, msg = mark_delivered(s, l.id, user)
            if ok:
                st.rerun()
            st.error(msg)
