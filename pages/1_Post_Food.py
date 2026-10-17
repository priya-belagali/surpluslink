"""Donors post surplus food with live food-safety intelligence and one-tap re-post."""
from datetime import datetime, timedelta

import streamlit as st
from sqlalchemy import select

from core import config, safety, ui
from core.db import Listing, now, session_scope
from core.listings import create_listing, repost_last

user = ui.start("Post Food", roles=["donor"], icon="➕")

st.markdown(
    """
    <div style="margin-bottom: 24px;">
        <span class="sl-brand-badge">Donor Dispatch Hub</span>
        <h1 style="font-size: 2.1rem; font-weight: 800; color: #0F172A; margin: 4px 0 6px 0;">Post Surplus Food</h1>
        <p style="color: #64748B; font-size: 1rem; margin: 0;">Publish excess cooked meals with real-time food-safety tracking. Nearby verified NGOs will be alerted instantly.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------------------
# 1. ONE-TAP REPEAT DONATION (IF PREVIOUS LISTING EXISTS)
# ------------------------------------------------------------------------------
with session_scope() as s:
    last_listing = s.scalar(select(Listing).where(Listing.donor_id == user.id).order_by(Listing.id.desc()))

if last_listing:
    with st.container(border=True):
        col_rep1, col_rep2 = st.columns([3, 1])
        with col_rep1:
            st.markdown(f"#### 🔁 Quick Re-Post: '{last_listing.title}'")
            st.caption(f"Same setup: **{last_listing.quantity_meals} meals** · {'🌱 Veg' if last_listing.veg else '🍗 Non-veg'} · {last_listing.category} · Pickup from {last_listing.address}")
        with col_rep2:
            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
            if st.button("Repeat Donation (Cooked Now)", key="repost_btn", type="primary", use_container_width=True):
                try:
                    with session_scope() as s:
                        listing = repost_last(s, user)
                        title_res = listing.title
                    st.success(f"🎉 Successfully posted '{title_res}'! Dispatching alerts to nearby food banks.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

st.markdown("<div style='margin-top: 18px;'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 2. QUICK PRESET CHIPS
# ------------------------------------------------------------------------------
st.markdown("##### ⚡ Quick Food Templates")
st.caption("Click a preset to quickly fill common meal types:")
p1, p2, p3, p4 = st.columns(4)

if "post_form" not in st.session_state:
    st.session_state["post_form"] = {
        "title": "Vegetable Biryani with Raita & Salan",
        "category": "Cooked meal (rice, curry, etc.)",
        "veg": "Veg",
        "quantity": 50,
        "event_type": "Regular service",
    }

if p1.button("🍚 Biryani & Curries (50 meals)", use_container_width=True):
    st.session_state["post_form"]["title"] = "Veg Biryani & Mirchi Ka Salan"
    st.session_state["post_form"]["category"] = "Cooked meal (rice, curry, etc.)"
    st.session_state["post_form"]["veg"] = "Veg"
    st.session_state["post_form"]["quantity"] = 50
    st.session_state["post_form"]["event_type"] = "Buffet"
    st.rerun()

if p2.button("🍛 Thali / Dal & Sabzi (80 meals)", use_container_width=True):
    st.session_state["post_form"]["title"] = "Dal Tadka, Mix Veg Sabzi & Steamed Rice"
    st.session_state["post_form"]["category"] = "Cooked meal (rice, curry, etc.)"
    st.session_state["post_form"]["veg"] = "Veg"
    st.session_state["post_form"]["quantity"] = 80
    st.session_state["post_form"]["event_type"] = "Regular service"
    st.rerun()

if p3.button("🥪 Sandwiches & Snacks (30 meals)", use_container_width=True):
    st.session_state["post_form"]["title"] = "Assorted Grilled Sandwiches & Samosas"
    st.session_state["post_form"]["category"] = "Bakery / snacks"
    st.session_state["post_form"]["veg"] = "Veg"
    st.session_state["post_form"]["quantity"] = 30
    st.session_state["post_form"]["event_type"] = "Conference"
    st.rerun()

if p4.button("🥐 Bakery Breads & Rolls (40 items)", use_container_width=True):
    st.session_state["post_form"]["title"] = "Fresh Dinner Rolls, Breads & Muffins"
    st.session_state["post_form"]["category"] = "Bakery / snacks"
    st.session_state["post_form"]["veg"] = "Veg"
    st.session_state["post_form"]["quantity"] = 40
    st.session_state["post_form"]["event_type"] = "Regular service"
    st.rerun()

st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 3. COMPREHENSIVE NEW DONATION BUILDER
# ------------------------------------------------------------------------------
st.markdown("### 📝 New Surplus Donation Details")

col_left, col_right = st.columns([3, 2], gap="large")

with col_left:
    with st.container(border=True):
        st.markdown("#### 1. Food Specifications")
        title_val = st.text_input(
            "Meal / Dish Name",
            value=st.session_state["post_form"]["title"],
            placeholder="e.g. Steamed Rice, Paneer Butter Masala, Chapati",
        )
        
        c1, c2, c3 = st.columns(3)
        cat_list = list(safety.SAFE_HOURS.keys())
        default_cat_idx = cat_list.index(st.session_state["post_form"]["category"]) if st.session_state["post_form"]["category"] in cat_list else 0
        category_val = c1.selectbox("Food Category", cat_list, index=default_cat_idx)
        
        quantity_val = c2.number_input(
            "Quantity (Approx. Meals)",
            min_value=1,
            value=int(st.session_state["post_form"]["quantity"]),
            step=5,
        )
        
        veg_options = ["Veg", "Non-veg"]
        default_veg_idx = 0 if st.session_state["post_form"]["veg"] == "Veg" else 1
        veg_choice = c3.radio("Dietary Type", veg_options, index=default_veg_idx, horizontal=True)
        is_veg = veg_choice == "Veg"

        c4, c5 = st.columns(2)
        event_types = ["Regular service", "Buffet", "Wedding / event", "Conference", "Canteen", "Bakery surplus"]
        default_ev_idx = event_types.index(st.session_state["post_form"]["event_type"]) if st.session_state["post_form"]["event_type"] in event_types else 0
        event_val = c4.selectbox("Source Event / Kitchen", event_types, index=default_ev_idx)
        
        photo_upload = c5.file_uploader("Attach Photo (Optional)", type=["jpg", "jpeg", "png"])

        description_val = st.text_area(
            "Packaging & Allergen Notes for the NGO",
            placeholder="e.g. Packed in stainless steel containers. Bring clean vessels. Contains dairy. No peanuts.",
            height=75,
        )

    with st.container(border=True):
        st.markdown("#### 2. Pickup Location")
        use_saved = st.checkbox("Pickup from my registered address", value=bool(user.lat))
        if use_saved and user.lat is not None:
            address_val = user.address or "Registered address"
            lat_val, lon_val = user.lat, user.lon
            st.success(f"📍 Using registered location: **{address_val}** (`{lat_val:.4f}, {lon_val:.4f}`)")
        else:
            address_val = st.text_input("Pickup Street Address", placeholder="e.g. 100 Feet Road, Indiranagar, Bengaluru")
            lat_val, lon_val = ui.location_input("post")

with col_right:
    with st.container(border=True):
        st.markdown("#### 3. Freshness & Safety Calculator")
        st.caption("FSSAI guidelines emphasize prompt consumption of hot cooked food within safe thermal windows.")

        cooked_time = st.time_input(
            "Time Food Was Cooked / Prepared",
            value=now().time().replace(second=0, microsecond=0),
            help="When the food finished cooking or left the heat.",
        )
        
        available_hours = st.slider(
            "Available for Pickup Window (Hours)",
            min_value=0.5,
            max_value=6.0,
            value=2.0,
            step=0.5,
            help="How long your premises will remain open for the collection team.",
        )

        # Dynamic safety math
        n_now = now()
        cooked_at_dt = datetime.combine(n_now.date(), cooked_time)
        if cooked_at_dt > n_now:
            cooked_at_dt -= timedelta(days=1)

        safe_until_dt = safety.compute_safe_until(category_val, cooked_at_dt)
        latest_pickup_dt = safe_until_dt - timedelta(minutes=config.PICKUP_BUFFER_MIN)
        pickup_by_dt = min(n_now + timedelta(hours=available_hours), latest_pickup_dt)
        mins_remaining = safety.minutes_left(pickup_by_dt, n_now)

        if mins_remaining < config.MIN_PICKUP_WINDOW_MIN:
            safety_badge = '<span class="sl-pill sl-pill-urgent">❌ Window Too Short</span>'
            status_desc = "Food cooked too long ago. Too little safe time left for transport & distribution."
        elif mins_remaining < 60:
            safety_badge = '<span class="sl-pill sl-pill-urgent">⚡ Urgent Window</span>'
            status_desc = "Pickup must occur rapidly. High priority dispatch will be triggered."
        elif mins_remaining < 120:
            safety_badge = '<span class="sl-pill sl-pill-warning">⏱️ Moderate Window</span>'
            status_desc = "Standard pickup window. Sufficient time for nearby vehicle pickup."
        else:
            safety_badge = '<span class="sl-pill sl-pill-success">🛡️ High Freshness</span>'
            status_desc = "Ample time for collection, distribution, and community consumption."

        st.markdown(
            f"""
            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 16px; margin: 12px 0;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <span style="font-size: 0.82rem; font-weight: 700; color: #475569; text-transform: uppercase;">Safety Status</span>
                    {safety_badge}
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85rem; margin-bottom: 10px;">
                    <div>🕒 <b>Cooked:</b> {cooked_at_dt:%H:%M}</div>
                    <div>🛡️ <b>Safe Until:</b> {safe_until_dt:%H:%M}</div>
                    <div>🚨 <b>Pickup By:</b> {pickup_by_dt:%H:%M}</div>
                    <div>⏳ <b>Remaining:</b> {safety.format_minutes(mins_remaining)}</div>
                </div>
                <div style="font-size: 0.78rem; color: #64748B; border-top: 1px dashed #CBD5E1; padding-top: 8px;">
                    {status_desc}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div style="font-size: 0.8rem; color: #64748B; margin-bottom: 16px;">
                💡 <b>FSSAI Baseline:</b> <i>{category_val}</i> has a maximum safe guideline of <b>{safety.SAFE_HOURS[category_val]} hours</b> post-cooking.
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Submit Action
        if st.button("🚀 Publish Donation to Network", type="primary", use_container_width=True):
            try:
                with session_scope() as s:
                    listing = create_listing(
                        s,
                        user,
                        title=title_val,
                        category=category_val,
                        veg=is_veg,
                        quantity_meals=int(quantity_val),
                        address=address_val,
                        lat=lat_val,
                        lon=lon_val,
                        cooked_at=cooked_at_dt,
                        available_hours=available_hours,
                        description=description_val or None,
                        event_type=event_val,
                        photo_path=ui.save_photo(photo_upload),
                    )
                    left_mins = safety.minutes_left(listing.safe_until, now())
                
                st.balloons()
                st.success(
                    f"🎉 **Donation Live!** Posted '{title_val}' ({quantity_val} meals). "
                    f"Food remains safe for {safety.format_minutes(left_mins)}. "
                    "The nearest matching NGO has been dispatched an exclusive 15-minute offer."
                )
            except ValueError as exc:
                st.error(f"⚠️ {str(exc)}")
