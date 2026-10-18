"""Donors post surplus food, or repeat their last donation."""
from datetime import datetime, timedelta

import streamlit as st

from core import safety, ui
from core.db import now, session_scope
from core.listings import create_listing, repost_last

user = ui.current_user()
ui.require_role(user, ["donor"])
ui.page_header("Post surplus food", "List what is left. Nearby NGOs are notified as soon as you post.")

with st.container(border=True):
    st.markdown("**Repeat your last donation**")
    st.caption("Uses the same details as your most recent listing and treats the food as cooked just now.")
    if st.button("Repeat last donation"):
        try:
            with session_scope() as s:
                title = repost_last(s, user).title
            st.success(f"Posted \"{title}\". Nearby NGOs are being notified.")
        except ValueError as exc:
            st.error(str(exc))

st.subheader("New donation")

st.markdown("**The food**")
title = st.text_input("What is it?", placeholder="For example: vegetable biryani and raita")
c1, c2, c3 = st.columns(3)
category = c1.selectbox("Food type", list(safety.SAFE_HOURS))
quantity = c2.number_input("Approximate meals", min_value=1, value=50, step=5)
veg = c3.radio("Diet", ["Vegetarian", "Non-vegetarian"], horizontal=True) == "Vegetarian"
description = st.text_area("Notes for the NGO", height=80,
                           placeholder="Packaging, allergens, containers needed")

st.markdown("**Timing**")
t1, t2, t3 = st.columns(3)
st.session_state.setdefault("cooked_time", now().time().replace(second=0, microsecond=0))
cooked_time = t1.time_input("Cooked or prepared at", key="cooked_time")
available_hours = t2.slider("Available for pickup for (hours)", 0.5, 6.0, 2.0, 0.5)
event_type = t3.selectbox("Source", ["Regular service", "Buffet", "Wedding or event", "Conference", "Canteen"])
st.caption(f"{category} is treated as safe for {safety.SAFE_HOURS[category]} hours after cooking. "
           "These are illustrative defaults. Confirm them against FSSAI guidance before relying on them.")

st.markdown("**Pickup location**")
use_saved = st.checkbox("Collect from my registered address", value=bool(user.lat))
if use_saved and user.lat is not None:
    address, lat, lon = user.address or "Registered address", user.lat, user.lon
else:
    address = st.text_input("Pickup address")
    lat, lon = ui.location_input("post")
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
            )
            left = safety.minutes_left(listing.safe_until, now())
        st.success(f"Donation posted. The food stays safe for about {safety.format_minutes(left).replace(' left', '')}. "
                   "Nearby NGOs are being notified.")
    except ValueError as exc:
        st.error(str(exc))
