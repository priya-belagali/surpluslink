"""Each role's own listings: journey, delivery details, and the downloadable record."""
import streamlit as st
from sqlalchemy import select

from core import matching, ui
from core.db import Listing, session_scope
from core.listings import mark_delivered, mark_picked_up, timeline
from core.records import schedule2_pdf

user = ui.current_user()
ui.require_role(user, ["donor", "ngo", "volunteer"])

TITLES = {
    "donor": ("My donations", "Everything you have posted, the journey of each listing, and its record."),
    "ngo": ("My pickups", "Food you have claimed. Update each one as it moves, then confirm delivery."),
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
    mine = s.scalars(q.limit(40)).all()
    journeys = {l.id: (timeline(s, l), matching.pending_offer(s, l.id) if l.status == "open" else None) for l in mine}

if not mine:
    st.info({"donor": "You have not posted anything yet.",
             "ngo": "Food you claim will appear here.",
             "volunteer": "Jobs you take will appear here."}.get(user.role, "Nothing to show yet."))
    st.stop()


def record_button(l: Listing) -> None:
    if l.ngo_id:
        st.download_button("Download record (PDF)", data=schedule2_pdf(l), file_name=f"record-{l.batch_ref or l.id}.pdf",
                           mime="application/pdf", key=f"rec{l.id}")


for l in mine:
    events, pending = journeys[l.id]
    with st.container(border=True):
        st.markdown(ui.listing_html(l, show_status=True, show_donor=(user.role != "donor")), unsafe_allow_html=True)
        if user.role != "donor":
            st.caption(f"Pickup contact: {l.donor.phone}" if l.donor.phone else "No phone number on file for this donor.")
        with st.expander("Journey"):
            st.markdown(ui.timeline_html(events, pending), unsafe_allow_html=True)

        if user.role in ("ngo", "volunteer"):
            if l.status == "claimed" and st.button("Mark as collected", key=f"pu{l.id}", type="primary"):
                with session_scope() as s:
                    ok, msg = mark_picked_up(s, l.id, user)
                if ok:
                    st.rerun()
                st.error(msg)
            if l.status == "picked_up":
                st.markdown("**Delivery details for the record**")
                d1, d2 = st.columns([1, 2])
                qty = d1.number_input("Meals distributed", min_value=0, max_value=l.quantity_meals,
                                      value=l.quantity_meals, key=f"qty{l.id}")
                area = d2.text_input("Area where food is distributed", key=f"area{l.id}",
                                     placeholder="Locality or institution")
                if st.button("Confirm delivery", key=f"dl{l.id}", type="primary"):
                    with session_scope() as s:
                        ok, msg = mark_delivered(s, l.id, user, quantity_distributed=int(qty), area=area)
                    if ok:
                        st.rerun()
                    st.error(msg)
        record_button(l)
