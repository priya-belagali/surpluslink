"""Donors post surplus food (or repeat their last donation with one tap)."""
from datetime import datetime, timedelta

import streamlit as st

from core import safety, ui
from core.db import now, session_scope
from core.listings import create_listing, repost_last

user = ui.start("Post Food", roles=["donor"], icon="➕")
st.title("➕ Post surplus food")

st.subheader("Quick post")
if st.button("🔁 Repeat my last donation (cooked just now)"):
    try:
        with session_scope() as s:
            listing = repost_last(s, user)
            title = listing.title
        st.success(f"Posted '{title}'. Nearby NGOs are being notified.")
    except ValueError as exc:
        st.error(str(exc))

st.divider()
st.subheader("New donation")
title = st.text_input("What is it? (e.g. Veg biryani and raita)")
c1, c2, c3 = st.columns(3)
category = c1.selectbox("Food type", list(safety.SAFE_HOURS))
quantity = c2.number_input("Approx. number of meals", min_value=1, value=50, step=5)
veg = c3.radio("Type", ["Veg", "Non-veg"], horizontal=True) == "Veg"

c4, c5, c6 = st.columns(3)
cooked_time = c4.time_input("Cooked / prepared at", value=now().time().replace(second=0, microsecond=0))
available_hours = c5.slider("Available for pickup for (hours)", 0.5, 6.0, 2.0, 0.5)
event_type = c6.selectbox("Source", ["Regular service", "Buffet", "Wedding / event", "Conference", "Canteen"])

st.caption(
    f"Safe-hours default for this type: {safety.SAFE_HOURS[category]}h after cooking. "
    "These are illustrative defaults - confirm them against FSSAI guidance."
)

description = st.text_area("Notes for the NGO (packaging, allergens, containers needed…)", height=70)
use_saved = st.checkbox("Pickup from my registered address", value=bool(user.lat))
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
        st.success(f"Posted! Food stays safe for about {safety.format_minutes(left)}. Nearby NGOs are being notified.")
    except ValueError as exc:
        st.error(str(exc))
