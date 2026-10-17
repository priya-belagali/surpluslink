"""Activity & Operations Hub: Order Tracking, Pickup Confirmation, and Distribution History."""
import urllib.parse

import pandas as pd
import streamlit as st
from sqlalchemy import select

from core import ui
from core.db import Listing, session_scope
from core.listings import mark_delivered, mark_picked_up

user = ui.start("My Activity", icon="📋")

st.markdown(
    """
    <div style="margin-bottom: 24px;">
        <span class="sl-brand-badge">Logistics Tracking</span>
        <h1 style="font-size: 2.1rem; font-weight: 800; color: #0F172A; margin: 4px 0 6px 0;">My Activity & Orders</h1>
        <p style="color: #64748B; font-size: 1rem; margin: 0;">Monitor your active food dispatches, update delivery milestones, and review completed distributions.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with session_scope() as s:
    q = select(Listing).order_by(Listing.id.desc())
    if user.role == "donor":
        q = q.where(Listing.donor_id == user.id)
    elif user.role == "ngo":
        q = q.where(Listing.ngo_id == user.id)
    elif user.role == "volunteer":
        q = q.where(Listing.volunteer_id == user.id)
    listings = s.scalars(q.limit(150)).all()

if not listings:
    st.info("📋 You have no recorded food activities yet. Post or claim food to start your rescue journey!")
    st.stop()

# ------------------------------------------------------------------------------
# 1. SUMMARY STATS RIBBON
# ------------------------------------------------------------------------------
active_listings = [l for l in listings if l.status in ("open", "claimed", "picked_up")]
delivered_listings = [l for l in listings if l.status == "delivered"]
total_meals_delivered = sum(l.quantity_meals for l in delivered_listings)

kpi1, kpi2, kpi3 = st.columns(3)
with kpi1:
    st.markdown(
        f"""
        <div class="sl-stat-card">
            <div class="sl-stat-val" style="color: #0284C7;">{len(active_listings)}</div>
            <div class="sl-stat-lbl">Active In-Progress</div>
            <div class="sl-stat-sub">⚡ Requires action or monitoring</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with kpi2:
    st.markdown(
        f"""
        <div class="sl-stat-card">
            <div class="sl-stat-val" style="color: #059669;">{len(delivered_listings)}</div>
            <div class="sl-stat-lbl">Delivered Batches</div>
            <div class="sl-stat-sub">✅ Successfully handed over</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with kpi3:
    st.markdown(
        f"""
        <div class="sl-stat-card">
            <div class="sl-stat-val" style="color: #7C3AED;">{total_meals_delivered:,}</div>
            <div class="sl-stat-lbl">Delivered Meals</div>
            <div class="sl-stat-sub">🍽️ Nourished community members</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 2. STATUS FILTER TABS
# ------------------------------------------------------------------------------
tab_active, tab_delivered, tab_all = st.tabs([
    f"🔥 Active Operations ({len(active_listings)})",
    f"✅ Delivered History ({len(delivered_listings)})",
    f"📑 All Records ({len(listings)})",
])


def render_activity_card(l: Listing) -> None:
    status_map = {
        "open": ("sl-pill-warning", "🟢 Open for Claims"),
        "claimed": ("sl-pill-info", "🟡 Claimed — Awaiting Pickup"),
        "picked_up": ("sl-pill-info", "🚚 In Transit"),
        "delivered": ("sl-pill-success", "✅ Successfully Delivered"),
        "expired": ("sl-pill-role", "⚪ Expired"),
    }
    pill_class, status_label = status_map.get(l.status, ("sl-pill-role", l.status))
    veg_pill = '<span class="sl-pill sl-pill-veg">🌱 Veg</span>' if l.veg else '<span class="sl-pill sl-pill-nonveg">🍗 Non-veg</span>'

    maps_donor = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(l.address)}"
    
    with st.container(border=True):
        st.markdown(ui.render_stepper_html(l.status), unsafe_allow_html=True)

        c_info, c_action = st.columns([3, 1])
        with c_info:
            st.markdown(
                f"""
                <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 6px;">
                    <span class="sl-pill {pill_class}">{status_label}</span>
                    {veg_pill}
                    <span class="sl-pill sl-pill-info">🍛 {l.quantity_meals} Meals</span>
                    <span style="font-size: 0.8rem; color: #64748B;">Category: <b>{l.category}</b></span>
                </div>
                <div style="font-size: 1.25rem; font-weight: 800; color: #0F172A; margin-bottom: 6px;">{l.title}</div>
                """,
                unsafe_allow_html=True,
            )

            # Route & Entity Details
            logistics_cols = st.columns(2)
            with logistics_cols[0]:
                donor_phone = f'<a href="tel:{l.donor.phone}" style="color: #059669;">📞 {l.donor.phone}</a>' if l.donor.phone else 'No phone provided'
                st.markdown(
                    f"""
                    <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px; font-size: 0.84rem;">
                        <div style="font-weight: 700; color: #475569; margin-bottom: 4px;">🏨 PICKUP LOCATION (DONOR)</div>
                        <div style="font-weight: 600; color: #0F172A;">{l.donor.display_name}</div>
                        <div><a href="{maps_donor}" target="_blank" style="color: #0284C7; text-decoration: none;">📍 {l.address}</a></div>
                        <div style="margin-top: 4px; font-size: 0.78rem;">{donor_phone}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with logistics_cols[1]:
                ngo_name = l.ngo.display_name if l.ngo else "Not yet claimed"
                ngo_addr = l.ngo.address or "Address on record" if l.ngo else "—"
                ngo_maps = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(ngo_addr)}" if l.ngo else "#"
                vol_info = f"🚗 <b>Volunteer:</b> {l.volunteer.name}" if l.volunteer else ("🚗 Direct NGO collection" if (l.ngo and l.ngo.has_vehicle) else "⏳ Awaiting volunteer")
                
                st.markdown(
                    f"""
                    <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px; font-size: 0.84rem;">
                        <div style="font-weight: 700; color: #475569; margin-bottom: 4px;">🏢 DELIVERY DESTINATION (NGO)</div>
                        <div style="font-weight: 600; color: #0F172A;">{ngo_name}</div>
                        <div><a href="{ngo_maps}" target="_blank" style="color: #0284C7; text-decoration: none;">📍 {ngo_addr}</a></div>
                        <div style="margin-top: 4px; font-size: 0.78rem;">{vol_info}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Timeline info
            timeline_bits = [f"Posted {l.created_at:%d %b, %H:%M}"]
            if l.claimed_at:
                timeline_bits.append(f"Claimed {l.claimed_at:%H:%M}")
            if l.picked_up_at:
                timeline_bits.append(f"Picked up {l.picked_up_at:%H:%M}")
            if l.delivered_at:
                timeline_bits.append(f"Delivered {l.delivered_at:%H:%M}")
            
            st.markdown(
                f"<div style='font-size: 0.78rem; color: #94A3B8; margin-top: 8px;'>⏱️ {' · '.join(timeline_bits)}</div>",
                unsafe_allow_html=True,
            )

        with c_action:
            # Action buttons for NGO and Volunteers
            if user.role in ("ngo", "volunteer"):
                st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
                if l.status == "claimed":
                    if st.button("🚚 Mark Picked Up", key=f"act_pu_{l.id}", type="primary", use_container_width=True):
                        with session_scope() as s:
                            ok, msg = mark_picked_up(s, l.id, user)
                        if ok:
                            st.success("Updated status to In Transit!")
                            st.rerun()
                        else:
                            st.error(msg)
                elif l.status == "picked_up":
                    if st.button("✅ Mark Delivered", key=f"act_dl_{l.id}", type="primary", use_container_width=True):
                        with session_scope() as s:
                            ok, msg = mark_delivered(s, l.id, user)
                        if ok:
                            st.balloons()
                            st.success("Mission completed! Meals marked as delivered.")
                            st.rerun()
                        else:
                            st.error(msg)


with tab_active:
    if not active_listings:
        st.info("🎉 No pending operations right now! All your food batches are either delivered or fulfilled.")
    else:
        for item in active_listings:
            render_activity_card(item)

with tab_delivered:
    if not delivered_listings:
        st.info("No completed deliveries yet.")
    else:
        for item in delivered_listings:
            render_activity_card(item)

with tab_all:
    for item in listings:
        render_activity_card(item)


# ------------------------------------------------------------------------------
# 3. CSV EXPORT UTILITY
# ------------------------------------------------------------------------------
st.markdown("<div style='margin-top: 36px;'></div>", unsafe_allow_html=True)
with st.expander("📥 Export Activity Log for CSR & Audit Reports"):
    export_df = pd.DataFrame([
        {
            "ID": l.id,
            "Date": l.created_at.strftime("%Y-%m-%d %H:%M"),
            "Title": l.title,
            "Category": l.category,
            "Meals": l.quantity_meals,
            "Status": l.status,
            "Donor": l.donor.display_name,
            "NGO": l.ngo.display_name if l.ngo else "",
            "Volunteer": l.volunteer.name if l.volunteer else "",
            "Address": l.address,
        }
        for l in listings
    ])
    st.dataframe(export_df, use_container_width=True, hide_index=True)
    csv_data = export_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Activity CSV",
        data=csv_data,
        file_name=f"surpluslink_activity_{user.role}_{user.id}.csv",
        mime="text/csv",
    )
