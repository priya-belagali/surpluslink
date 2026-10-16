"""Each role's own listings, jobs and status updates."""
import pandas as pd
import streamlit as st
from sqlalchemy import or_, select

from core import ui
from core.db import Listing, session_scope
from core.listings import mark_delivered, mark_picked_up

user = ui.start("My Activity", icon="📋")
st.title("📋 My activity")

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
    st.info("Nothing here yet.")
    st.stop()

ICON = {"open": "🟢 open", "claimed": "🟡 claimed", "picked_up": "🚚 picked up",
        "delivered": "✅ delivered", "expired": "⚪ expired"}

if user.role == "donor":
    st.dataframe(pd.DataFrame([{
        "Posted": l.created_at.strftime("%d %b %H:%M"), "Food": l.title, "Meals": l.quantity_meals,
        "Status": ICON[l.status], "NGO": l.ngo.display_name if l.ngo else "—",
        "Volunteer": l.volunteer.name if l.volunteer else "—"} for l in mine]),
        hide_index=True)
    st.stop()

# NGOs and volunteers: show action buttons for in-progress items.
for l in mine:
    with st.container(border=True):
        st.markdown(f"**{l.title}** — {l.quantity_meals} meals · {ICON[l.status]}")
        st.caption(f"From {l.donor.display_name}, {l.address} ({l.donor.phone or 'no phone'})")
        if l.status == "claimed" and st.button("Mark picked up", key=f"pu{l.id}", type="primary"):
            with session_scope() as s:
                ok, msg = mark_picked_up(s, l.id, user)
            st.rerun() if ok else st.error(msg)
        if l.status == "picked_up" and st.button("Mark delivered", key=f"dl{l.id}", type="primary"):
            with session_scope() as s:
                ok, msg = mark_delivered(s, l.id, user)
            st.rerun() if ok else st.error(msg)
