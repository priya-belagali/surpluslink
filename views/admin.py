"""Administration: approve NGOs, review accounts and listings, run housekeeping, test alerts."""
import pandas as pd
import streamlit as st
from sqlalchemy import select

from core import matching, notify, places, ui
from core.db import Listing, User, session_scope

user = ui.current_user()
ui.require_role(user, ["admin"])
ui.page_header("Administration", "Approve NGOs and look after the platform.")

with session_scope() as s:
    pending = s.scalars(select(User).where(User.role == "ngo", User.verified.is_(False))).all()
    approved = s.scalars(select(User).where(User.role == "ngo", User.verified.is_(True))).all()
    users = s.scalars(select(User).order_by(User.id)).all()
    listings = s.scalars(select(Listing).order_by(Listing.id.desc()).limit(100)).all()

st.subheader(f"NGOs awaiting approval ({len(pending)})")
st.caption("An NGO Darpan ID is self-declared, so treat it as something to check, not as proof. "
           "Look up the ID on the NGO Darpan portal and compare the name, and check the FSSAI registration and the "
           "organisation's registration documents before approving.")
if not pending:
    st.info("No NGOs are waiting for approval.")
for u in pending:
    with st.container(border=True):
        st.markdown(f"**{u.display_name}**")
        st.caption(f"{u.email}, {u.phone or 'no phone'}. {u.address or 'No address'}. Capacity {u.capacity_meals} meals. "
                   f"Own vehicle: {'yes' if u.has_vehicle else 'no'}.")
        st.markdown(f"FSSAI registration: **{u.fssai_number or 'not given'}**. NGO Darpan ID: **{u.darpan_id or 'not given'}**.")
        checked = st.checkbox("I have checked this NGO's registration details", key=f"chk{u.id}")
        if st.button("Approve", key=f"v{u.id}", type="primary", disabled=not checked):
            with session_scope() as s:
                s.get(User, u.id).verified = True
            st.rerun()

st.subheader(f"Approved NGOs ({len(approved)})")
for u in approved:
    c1, c2 = st.columns([5, 1])
    c1.write(f"{u.display_name} ({u.email})  FSSAI: {u.fssai_number or '-'}  Darpan: {u.darpan_id or '-'}")
    if c2.button("Revoke", key=f"r{u.id}"):
        with session_scope() as s:
            s.get(User, u.id).verified = False
        st.rerun()

st.subheader("Tools")
t1, t2, t3 = st.tabs(["Housekeeping", "Test an alert", "Coverage data"])
with t1:
    st.caption("Expires listings past their pickup window and passes unanswered offers to the next NGO. "
               "This also runs automatically while the app is open.")
    if st.button("Run housekeeping now"):
        with session_scope() as s:
            result = matching.tick(s)
        st.success(f"Expired {result['expired_listings']} listings and escalated {result['escalated']} offers.")
with t2:
    st.caption("Sends one message through Twilio. With the WhatsApp sandbox, the phone must first join the sandbox "
               "by sending the join code shown in your Twilio console.")
    phone = st.text_input("Phone number with country code", placeholder="+91...")
    if st.button("Send test message"):
        ok, detail = notify.send_test(phone)
        (st.success if ok else st.warning)(detail)
with t3:
    data = places.load()
    st.caption("Kitchens and venues from OpenStreetMap, used by the Coverage page. "
               + (f"Last fetched {data['fetched_at']}, {len(data['places'])} places." if data else "Nothing fetched yet."))
    if st.button("Fetch coverage data now"):
        with st.spinner("Contacting the public Overpass servers. This can take up to a minute."):
            try:
                count = places.refresh()
                st.success(f"Saved {count} places.")
            except RuntimeError as exc:
                st.error(str(exc))

tab_users, tab_listings = st.tabs(["All accounts", "Recent listings"])
with tab_users:
    st.dataframe(pd.DataFrame([{"ID": u.id, "Name": u.display_name, "Email": u.email, "Role": ui.ROLE_LABEL[u.role],
                                "Approved": "Yes" if u.verified else "No"} for u in users]), hide_index=True)
with tab_listings:
    st.dataframe(pd.DataFrame([{"ID": l.id, "Batch": l.batch_ref or "", "Food": l.title, "Meals": l.quantity_meals,
                                "Status": ui.STATUS_LABEL[l.status], "Donor": l.donor.display_name,
                                "NGO": l.ngo.display_name if l.ngo else ""} for l in listings]), hide_index=True)
