"""Donors post surplus food, or repeat their last donation."""
from datetime import datetime, timedelta

import streamlit as st

from core import matching, safety, ui
from core.db import User, now, session_scope
from core.listings import create_listing, repost_last
from core.safety import format_duration
from core import config

user = ui.current_user()
ui.require_role(user, ["donor"])
ui.page_header("Post surplus food", "List what is left. The best-matched NGO is offered it straight away.")


def first_offer_text(s, listing) -> str:
    pending = matching.pending_offer(s, listing.id)
    if pending is not None:
        return f"First offer sent to {pending.ngo.display_name}, who has {format_duration(config.OFFER_TIMEOUT_SEC)} to respond."
    return "No approved NGO is in range, so the listing is open to all NGOs."


with st.container(border=True):
    st.markdown("**Repeat your last donation**")
    st.caption("Same details as your most recent listing, treated as cooked just now.")
    if st.button("Repeat last donation"):
        try:
            with session_scope() as s:
                listing = repost_last(s, user)
                msg = f'Posted "{listing.title}", batch {listing.batch_ref}. {first_offer_text(s, listing)}'
            st.success(msg)
        except ValueError as exc:
            st.error(str(exc))

with st.expander("Details printed on your donation records"):
    fssai = st.text_input("FSSAI licence or registration number", value=user.fssai_number or "", key="own_fssai")
    if st.button("Save details"):
        with session_scope() as s:
            s.get(User, user.id).fssai_number = fssai.strip() or None
        st.success("Saved.")

st.subheader("New donation")
st.markdown("**The food**")
title = st.text_input("What is it?", placeholder="For example: vegetable biryani and raita")
c1, c2, c3 = st.columns(3)
category = c1.selectbox("Food type", list(safety.SAFE_HOURS))
quantity = c2.number_input("Approximate meals", min_value=1, value=50, step=5)
veg = c3.radio("Diet", ["Vegetarian", "Non-vegetarian"], horizontal=True) == "Vegetarian"
description = st.text_area("Notes for the NGO", height=80, placeholder="Packaging, allergens, containers needed")

st.markdown("**Timing and temperature**")
t1, t2, t3, t4 = st.columns(4)
st.session_state.setdefault("cooked_time", now().time().replace(second=0, microsecond=0))
cooked_time = t1.time_input("Cooked or prepared at", key="cooked_time")
available_hours = t2.slider("Available for pickup (hours)", 0.5, 6.0, 2.0, 0.5)
temperature = t3.number_input("Food temperature when packed (degrees C)", min_value=-30.0, max_value=120.0,
                              value=None, step=1.0, placeholder="Optional",
                              help="Part of the donation record. Measure with a food thermometer if you can.")
event_type = t4.selectbox("Source", ["Regular service", "Buffet", "Wedding or event", "Conference", "Canteen"])
st.caption(f"{category}: planning limit of {safety.SAFE_HOURS[category]} hours after cooking. This is a default used by this tool "
           "to schedule pickups. It is not a regulatory limit, so follow your own food safety procedures.")

st.markdown("**Pickup location**")
use_saved = st.checkbox("Collect from my registered address", value=bool(user.lat))
if use_saved and user.lat is not None:
    address, lat, lon = user.address or "Registered address", user.lat, user.lon
else:
    address, lat, lon = ui.location_input("post", label="Pickup address")
photo = st.file_uploader("Photo of the food (optional)", type=["jpg", "jpeg", "png"])

if st.button("Post donation", type="primary"):
    cooked_at = datetime.combine(now().date(), cooked_time)
    if cooked_at > now():
        cooked_at -= timedelta(days=1)
    try:
        with session_scope() as s:
            listing = create_listing(
                s, user, title=title, category=category, veg=veg, quantity_meals=int(quantity),
                address=address, lat=lat, lon=lon, cooked_at=cooked_at, available_hours=available_hours,
                description=description or None, event_type=event_type, photo_path=ui.save_photo(photo),
                temperature_c=temperature,
            )
            left = safety.minutes_left(listing.safe_until, now())
            msg = (f"Donation posted, batch {listing.batch_ref}. About {safety.format_minutes(left).replace(' left', '')} "
                   f"remain against the planning limit. {first_offer_text(s, listing)}")
        st.success(msg)
    except ValueError as exc:
        st.error(str(exc))
