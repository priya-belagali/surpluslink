"""NGOs: Priority dispatch offers + open rescue board. Volunteers: Transport missions."""
import os
import urllib.parse

import pandas as pd
import streamlit as st
from sqlalchemy import select

from core import config, safety, ui
from core.db import Listing, Offer, now, session_scope
from core.geo import haversine_km
from core.listings import claim_listing, decline_offer, take_transport

user = ui.start("Find Food", roles=["ngo", "volunteer"], icon="🔎")

is_vol = user.role == "volunteer"
page_title = "🚗 Transport Mission Desk" if is_vol else "🍲 Food Rescue Board"
page_sub = (
    "Pick up claimed food batches and deliver them safely to recipient community kitchens."
    if is_vol
    else "Claim priority food matches or browse open batches available for immediate collection."
)

st.markdown(
    f"""
    <div style="margin-bottom: 24px;">
        <span class="sl-brand-badge">{'Driver Logistics' if is_vol else 'NGO Food Rescue'}</span>
        <h1 style="font-size: 2.1rem; font-weight: 800; color: #0F172A; margin: 4px 0 6px 0;">{page_title}</h1>
        <p style="color: #64748B; font-size: 1rem; margin: 0;">{page_sub}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if not is_vol and not user.verified:
    st.warning("⏳ **Verification Required**: Your NGO account is pending administrative approval. Verified accounts receive exclusive priority alerts and can claim food donations.")
    st.stop()


# ------------------------------------------------------------------------------
# SEARCH & FILTER TOOLBAR
# ------------------------------------------------------------------------------
with st.container(border=True):
    col_search, col_diet, col_sort = st.columns([2, 1, 1])
    search_q = col_search.text_input("🔍 Search Listings", placeholder="Filter by meal name, donor, address...")
    diet_filter = col_diet.selectbox("Dietary Preference", ["All Diets", "🌱 Veg Only", "🍗 Non-Veg Only"])
    sort_by = col_sort.selectbox("Sort Order", ["Most Urgent Pickup", "Distance (Closest First)", "Largest Meal Count"])


# ------------------------------------------------------------------------------
# AUTO-REFRESHING BOARD FRAGMENT
# ------------------------------------------------------------------------------
@st.fragment(run_every=30)
def board() -> None:
    flash = st.session_state.pop("flash", None)
    if flash:
        (st.success if flash[0] else st.error)(flash[1])

    n = now()
    with session_scope() as s:
        if is_vol:
            jobs = s.scalars(select(Listing).where(Listing.status == "claimed", Listing.volunteer_id.is_(None))).all()
            rows = [
                j for j in jobs
                if user.lat is None or haversine_km(user.lat, user.lon, j.lat, j.lon) <= config.VOLUNTEER_RADIUS_KM
            ]
            priority, others = rows, []
        else:
            offered_ids = set(s.scalars(select(Offer.listing_id).where(Offer.ngo_id == user.id, Offer.status == "pending")))
            open_listings = s.scalars(
                select(Listing).where(Listing.status == "open", Listing.pickup_by > n).order_by(Listing.safe_until)
            ).all()
            priority = [l for l in open_listings if l.id in offered_ids]
            others = [l for l in open_listings if l.visible_to_all and l.id not in offered_ids]

    # Apply search and filters
    def matches_filter(item: Listing) -> bool:
        if search_q.strip():
            sq = search_q.strip().lower()
            donor_name = item.donor.display_name.lower()
            if sq not in item.title.lower() and sq not in donor_name and sq not in (item.address or "").lower():
                return False
        if diet_filter == "🌱 Veg Only" and not item.veg:
            return False
        if diet_filter == "🍗 Non-Veg Only" and item.veg:
            return False
        return True

    priority = [item for item in priority if matches_filter(item)]
    others = [item for item in others if matches_filter(item)]

    # Sorting
    def sort_key(item: Listing):
        if sort_by == "Distance (Closest First)":
            return haversine_km(user.lat, user.lon, item.lat, item.lon) if user.lat else 0
        elif sort_by == "Largest Meal Count":
            return -item.quantity_meals
        return item.pickup_by

    priority.sort(key=sort_key)
    others.sort(key=sort_key)

    all_shown = priority + others

    # Map visualization
    if all_shown:
        st.markdown("##### 📍 Geospatial Distribution")
        map_df = pd.DataFrame([
            {
                "lat": l.lat,
                "lon": l.lon,
            }
            for l in all_shown
        ])
        st.map(map_df, zoom=11, size=40)
        st.markdown("<div style='margin-bottom: 18px;'></div>", unsafe_allow_html=True)

    # Priority / Assigned section
    heading = "⭐ Exclusive Priority Offers For You" if not is_vol else "🚗 Urgent Transport Jobs Near You"
    st.markdown(f"### {heading} ({len(priority)})")

    if not priority:
        if is_vol:
            st.info("No unclaimed transport jobs in your area right now. When an NGO without a vehicle claims a donation, it will appear here instantly.")
        else:
            st.info("No exclusive priority offers currently waiting. Explore the community board below or wait for new incoming donor alerts.")
    else:
        for item in priority:
            render_card(item, offered=True)

    # Open to all section (for NGOs)
    if not is_vol:
        st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True)
        st.markdown(f"### 🌍 Open Community Board ({len(others)})")
        st.caption("Listings open to all verified NGOs after priority escalation windows expire.")
        if not others:
            st.info("No open community listings at this moment.")
        else:
            for item in others:
                render_card(item, offered=False)


def render_card(l: Listing, offered: bool) -> None:
    mins_left = safety.minutes_left(l.pickup_by, now())
    urgency_pill = (
        f'<span class="sl-pill sl-pill-urgent">⚡ {safety.format_minutes(mins_left)} left</span>'
        if mins_left < 60
        else f'<span class="sl-pill sl-pill-warning">⏱️ {safety.format_minutes(mins_left)} left</span>'
        if mins_left < 120
        else f'<span class="sl-pill sl-pill-success">🛡️ {safety.format_minutes(mins_left)} left</span>'
    )
    veg_pill = '<span class="sl-pill sl-pill-veg">🌱 Veg</span>' if l.veg else '<span class="sl-pill sl-pill-nonveg">🍗 Non-veg</span>'
    dist_str = f"📍 {haversine_km(user.lat, user.lon, l.lat, l.lon):.1f} km away" if user.lat is not None else ""
    
    maps_query = urllib.parse.quote(f"{l.address}")
    maps_url = f"https://www.google.com/maps/search/?api=1&query={maps_query}"

    with st.container(border=True):
        top_l, top_r = st.columns([3, 1])
        with top_l:
            pills_html = f"""
            <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 8px;">
                {veg_pill}
                {urgency_pill}
                <span class="sl-pill sl-pill-info">🍛 {l.quantity_meals} Meals</span>
                <span style="font-size: 0.8rem; color: #64748B; font-weight: 600;">{dist_str}</span>
            </div>
            <div style="font-size: 1.25rem; font-weight: 800; color: #0F172A; margin-bottom: 4px;">{l.title}</div>
            <div style="font-size: 0.88rem; color: #475569; margin-bottom: 8px;">
                <b>Donor:</b> {l.donor.display_name} &nbsp;·&nbsp; 
                <a href="{maps_url}" target="_blank" style="color: #059669; text-decoration: none; font-weight: 600;">🗺️ {l.address}</a>
            </div>
            """
            st.markdown(pills_html, unsafe_allow_html=True)
            
            if l.description:
                st.markdown(
                    f"""
                    <div style="background: #F8FAFC; border-left: 3px solid #059669; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; color: #334155; margin-bottom: 10px;">
                        <b>Kitchen Note:</b> {l.description}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            if is_vol and l.ngo:
                ngo_maps = urllib.parse.quote(f"{l.ngo.address or l.ngo.display_name}")
                st.markdown(
                    f"""
                    <div style="background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 10px; margin-bottom: 12px; font-size: 0.85rem;">
                        <b>🚗 Destination NGO:</b> {l.ngo.display_name} &nbsp;·&nbsp; 
                        <a href="https://www.google.com/maps/search/?api=1&query={ngo_maps}" target="_blank" style="color: #047857; font-weight: 600;">📍 {l.ngo.address or 'Address upon claim'}</a>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.caption(f"🕒 Cooked at {l.cooked_at:%H:%M} · Pickup required by **{l.pickup_by:%H:%M}** · Safe until **{l.safe_until:%H:%M}**")

        with top_r:
            if l.photo_path and os.path.exists(l.photo_path):
                st.image(l.photo_path, use_container_width=True)
            else:
                st.markdown(
                    """
                    <div style="background: #F1F5F9; border-radius: 12px; height: 100px; display: flex; align-items: center; justify-content: center; color: #94A3B8; font-size: 2.2rem;">
                        🍲
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

        # Action Buttons
        act_col1, act_col2, _ = st.columns([2, 1.5, 4])
        if is_vol:
            if act_col1.button("🚗 Accept Transport Mission", key=f"vol_take_{l.id}", type="primary", use_container_width=True):
                with session_scope() as s:
                    ok, msg = take_transport(s, l.id, user)
                st.session_state["flash"] = (ok, msg)
                st.rerun()
        else:
            if act_col1.button("🤝 Claim This Food", key=f"ngo_claim_{l.id}", type="primary", use_container_width=True):
                with session_scope() as s:
                    ok, msg = claim_listing(s, l.id, user)
                st.session_state["flash"] = (ok, msg)
                st.rerun()
            if offered:
                if act_col2.button("Pass / Decline", key=f"ngo_decl_{l.id}", use_container_width=True):
                    with session_scope() as s:
                        decline_offer(s, l.id, user)
                    st.rerun()


board()
