"""Admin Control Desk: NGO Accreditation, User Management, and Matching Housekeeping."""
import pandas as pd
import streamlit as st
from sqlalchemy import select

from core import matching, ui
from core.db import Listing, User, session_scope

user = ui.start("Admin", roles=["admin"], icon="🛠️")
if user.role != "admin":
    st.stop()

st.markdown(
    """
    <div style="margin-bottom: 24px;">
        <span class="sl-brand-badge">Administrative Oversight</span>
        <h1 style="font-size: 2.1rem; font-weight: 800; color: #0F172A; margin: 4px 0 6px 0;">Admin Control Desk</h1>
        <p style="color: #64748B; font-size: 1rem; margin: 0;">Verify NGO credentials, monitor user accounts, inspect food dispatches, and trigger engine housekeeping.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with session_scope() as s:
    pending = s.scalars(select(User).where(User.role == "ngo", User.verified.is_(False))).all()
    verified_ngos = s.scalars(select(User).where(User.role == "ngo", User.verified.is_(True))).all()
    all_users = s.scalars(select(User).order_by(User.id)).all()
    recent_listings = s.scalars(select(Listing).order_by(Listing.id.desc()).limit(150)).all()

# ------------------------------------------------------------------------------
# 1. ADMIN KPI STRIP
# ------------------------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(
        f"""
        <div class="sl-stat-card">
            <div class="sl-stat-val" style="color: {'#DC2626' if len(pending) else '#059669'};">{len(pending)}</div>
            <div class="sl-stat-lbl">Pending NGO Verifications</div>
            <div class="sl-stat-sub">{'⚠️ Requires immediate review' if len(pending) else '✓ All applicants reviewed'}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        f"""
        <div class="sl-stat-card">
            <div class="sl-stat-val" style="color: #059669;">{len(verified_ngos)}</div>
            <div class="sl-stat-lbl">Accredited NGOs</div>
            <div class="sl-stat-sub">🏢 Active recipient food banks</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with k3:
    st.markdown(
        f"""
        <div class="sl-stat-card">
            <div class="sl-stat-val" style="color: #0284C7;">{len(all_users)}</div>
            <div class="sl-stat-lbl">Total Registered Users</div>
            <div class="sl-stat-sub">👥 Donors, NGOs & Drivers</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with k4:
    st.markdown(
        f"""
        <div class="sl-stat-card">
            <div class="sl-stat-val" style="color: #7C3AED;">{len(recent_listings)}</div>
            <div class="sl-stat-lbl">Tracked Food Listings</div>
            <div class="sl-stat-sub">🍲 Processed dispatches</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 2. NGO ACCREDITATION QUEUE
# ------------------------------------------------------------------------------
st.markdown(f"### 📋 NGO Verification Desk ({len(pending)} Pending)")
st.caption("Review NGO legal credentials (e.g. Trust deed, Section 8, 80G/12A, Darpan portal) to ensure hygiene compliance.")

if not pending:
    st.markdown(
        """
        <div style="background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 12px; padding: 16px; color: #166534; font-size: 0.9rem; font-weight: 600;">
            ✓ Great job! All registered NGO applicants have been processed.
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    for u in pending:
        with st.container(border=True):
            col_info, col_acts = st.columns([3, 1])
            with col_info:
                st.markdown(f"#### 🏢 {u.display_name}")
                st.markdown(
                    f"""
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.88rem; color: #334155; margin-bottom: 8px;">
                        <div><b>Email:</b> <a href="mailto:{u.email}">{u.email}</a></div>
                        <div><b>Phone:</b> {u.phone or 'Not provided'}</div>
                        <div><b>Address:</b> {u.address or 'No address'}</div>
                        <div><b>Meal Capacity:</b> 🍱 {u.capacity_meals} meals/batch</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                veh_badge = '<span class="sl-pill sl-pill-success">🚐 Has Own Transport Fleet</span>' if u.has_vehicle else '<span class="sl-pill sl-pill-warning">⏳ Requires Volunteer Drivers</span>'
                st.markdown(veh_badge, unsafe_allow_html=True)

            with col_acts:
                st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)
                if st.button("✅ Approve NGO", key=f"verify_{u.id}", type="primary", use_container_width=True):
                    with session_scope() as s:
                        s.get(User, u.id).verified = True
                    st.success(f"Approved {u.display_name}! They can now claim food donations.")
                    st.rerun()

st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 3. VERIFIED NGOS ROSTER
# ------------------------------------------------------------------------------
with st.expander(f"🏢 Manage Accredited NGOs ({len(verified_ngos)})"):
    for u in verified_ngos:
        c1, c2, c3 = st.columns([3, 2, 1])
        c1.write(f"**{u.display_name}** · {u.email}")
        c2.caption(f"Capacity: {u.capacity_meals} meals · Fleet: {'Yes' if u.has_vehicle else 'No'}")
        if c3.button("Revoke", key=f"revoke_{u.id}", use_container_width=True):
            with session_scope() as s:
                s.get(User, u.id).verified = False
            st.warning(f"Revoked verification for {u.display_name}.")
            st.rerun()


# ------------------------------------------------------------------------------
# 4. SYSTEM HOUSEKEEPING & ESCALATION TRIGGER
# ------------------------------------------------------------------------------
st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
st.markdown("### ⚙️ Dispatch Engine Operations")

with st.container(border=True):
    h_col1, h_col2 = st.columns([3, 1])
    with h_col1:
        st.markdown("#### Real-Time Housekeeping & 15-Minute Escalation")
        st.caption("The engine automatically expires stale uncollected listings and escalates unanswered priority offers to the next closest NGO every 30 seconds. You can also trigger an immediate tick manually below.")
    with h_col2:
        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        if st.button("⚡ Run Engine Tick Now", key="tick_btn", type="primary", use_container_width=True):
            with session_scope() as s:
                res = matching.tick(s)
            st.success(f"Engine executed successfully! Expired Listings: {res['expired_listings']} · Escalated Offers: {res['escalated']}")


# ------------------------------------------------------------------------------
# 5. USER DIRECTORY & RECENT LISTINGS AUDIT
# ------------------------------------------------------------------------------
st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True)
st.markdown("### 🔍 System Audit Explorer")

tab_users, tab_listings = st.tabs(["👥 User Directory", "🍲 Dispatched Listings Monitor"])

with tab_users:
    role_filter = st.selectbox("Filter by Role", ["All Roles", "donor", "ngo", "volunteer", "admin"])
    filtered_users = all_users if role_filter == "All Roles" else [u for u in all_users if u.role == role_filter]
    
    users_df = pd.DataFrame([
        {
            "ID": u.id,
            "Name / Org": u.display_name,
            "Email": u.email,
            "Role": u.role.upper(),
            "Verified": "✓ Yes" if u.verified else "⏳ Pending",
            "Phone": u.phone or "—",
            "Address": u.address or "—",
        }
        for u in filtered_users
    ])
    st.dataframe(users_df, use_container_width=True, hide_index=True)

with tab_listings:
    listings_df = pd.DataFrame([
        {
            "ID": l.id,
            "Food Title": l.title,
            "Category": l.category,
            "Meals": l.quantity_meals,
            "Status": l.status.upper(),
            "Donor": l.donor.display_name,
            "NGO": l.ngo.display_name if l.ngo else "—",
            "Driver": l.volunteer.name if l.volunteer else "—",
            "Safe Until": l.safe_until.strftime("%H:%M"),
        }
        for l in recent_listings
    ])
    st.dataframe(listings_df, use_container_width=True, hide_index=True)
