"""Admin: verify NGOs, view users and listings, run housekeeping."""
import pandas as pd
import streamlit as st
from sqlalchemy import select

from core import matching, ui
from core.db import Listing, User, session_scope

user = ui.start("Admin", roles=["admin"], icon="🛠️")
if user.role != "admin":
    st.stop()
st.title("🛠️ Admin")

with session_scope() as s:
    pending = s.scalars(select(User).where(User.role == "ngo", User.verified.is_(False))).all()
    verified = s.scalars(select(User).where(User.role == "ngo", User.verified.is_(True))).all()
    users = s.scalars(select(User).order_by(User.id)).all()
    listings = s.scalars(select(Listing).order_by(Listing.id.desc()).limit(100)).all()

st.subheader(f"NGOs awaiting verification ({len(pending)})")
st.caption("Check registration documents (e.g. Section 8 / trust / society registration) before approving.")
for u in pending:
    with st.container(border=True):
        st.markdown(f"**{u.display_name}** · {u.email} · {u.phone or 'no phone'}")
        st.caption(f"{u.address or 'no address'} · capacity {u.capacity_meals} meals · vehicle: {u.has_vehicle}")
        if st.button("Verify", key=f"v{u.id}", type="primary"):
            with session_scope() as s:
                s.get(User, u.id).verified = True
            st.rerun()

st.subheader(f"Verified NGOs ({len(verified)})")
for u in verified:
    c1, c2 = st.columns([4, 1])
    c1.write(f"{u.display_name} · {u.email}")
    if c2.button("Revoke", key=f"r{u.id}"):
        with session_scope() as s:
            s.get(User, u.id).verified = False
        st.rerun()

st.subheader("Housekeeping")
if st.button("Run expiry + escalation now"):
    with session_scope() as s:
        st.success(f"Done: {matching.tick(s)}")

st.subheader("All users")
st.dataframe(pd.DataFrame([{"id": u.id, "name": u.display_name, "email": u.email, "role": u.role,
                            "verified": u.verified} for u in users]), hide_index=True)
st.subheader("Recent listings")
st.dataframe(pd.DataFrame([{"id": l.id, "food": l.title, "meals": l.quantity_meals, "status": l.status,
                            "donor": l.donor.display_name, "ngo": l.ngo.display_name if l.ngo else ""}
                           for l in listings]), hide_index=True)
