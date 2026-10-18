"""Administration: approve NGOs, review accounts and listings, run housekeeping."""
import pandas as pd
import streamlit as st
from sqlalchemy import select

from core import matching, ui
from core.db import Listing, User, session_scope

user = ui.current_user()
ui.require_role(user, ["admin"])
ui.page_header("Administration", "Approve NGOs and keep an eye on activity.")

with session_scope() as s:
    pending = s.scalars(select(User).where(User.role == "ngo", User.verified.is_(False))).all()
    approved = s.scalars(select(User).where(User.role == "ngo", User.verified.is_(True))).all()
    users = s.scalars(select(User).order_by(User.id)).all()
    listings = s.scalars(select(Listing).order_by(Listing.id.desc()).limit(100)).all()

st.subheader(f"NGOs awaiting approval ({len(pending)})")
st.caption("Check registration documents, such as trust, society or Section 8 registration, before approving.")
if not pending:
    st.info("No NGOs are waiting for approval.")
for u in pending:
    with st.container(border=True):
        st.markdown(f"**{u.display_name}**")
        st.caption(f"{u.email}, {u.phone or 'no phone'}. {u.address or 'No address'}. "
                   f"Capacity {u.capacity_meals} meals. Own vehicle: {'yes' if u.has_vehicle else 'no'}.")
        if st.button("Approve", key=f"v{u.id}", type="primary"):
            with session_scope() as s:
                s.get(User, u.id).verified = True
            st.rerun()

st.subheader(f"Approved NGOs ({len(approved)})")
for u in approved:
    c1, c2 = st.columns([5, 1])
    c1.write(f"{u.display_name} ({u.email})")
    if c2.button("Revoke", key=f"r{u.id}"):
        with session_scope() as s:
            s.get(User, u.id).verified = False
        st.rerun()

st.subheader("Maintenance")
st.caption("Expires listings past their pickup window and passes unanswered offers to the next NGO. "
           "This also runs automatically while the app is in use.")
if st.button("Run expiry and escalation now"):
    with session_scope() as s:
        result = matching.tick(s)
    st.success(f"Done. Expired {result['expired_listings']} listings and escalated {result['escalated']} offers.")

tab_users, tab_listings = st.tabs(["All accounts", "Recent listings"])
with tab_users:
    st.dataframe(pd.DataFrame([{"ID": u.id, "Name": u.display_name, "Email": u.email, "Role": ui.ROLE_LABEL[u.role],
                                "Approved": "Yes" if u.verified else "No"} for u in users]), hide_index=True)
with tab_listings:
    st.dataframe(pd.DataFrame([{"ID": l.id, "Food": l.title, "Meals": l.quantity_meals,
                                "Status": ui.STATUS_LABEL[l.status], "Donor": l.donor.display_name,
                                "NGO": l.ngo.display_name if l.ngo else ""} for l in listings]), hide_index=True)
