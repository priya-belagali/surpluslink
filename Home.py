"""SurplusLink - Modern Entry & Command Hub: Login, Registration, and Role-Based Dashboards."""
from datetime import datetime
import streamlit as st
from sqlalchemy import select

from core import impact, safety, ui
from core.auth import authenticate, register_user
from core.db import Listing, User, now, session_scope

ui.setup("Home")

user = ui.current_user()

# ==============================================================================
# 1. LOGGED-IN EXPERIENCE (ROLE-TAILORED COMMAND DASHBOARD)
# ==============================================================================
if user:
    ui.sidebar(user)

    # Greeting & Hero Banner
    time_greeting = "Good day"
    curr_hour = now().hour
    if 5 <= curr_hour < 12:
        time_greeting = "Good morning"
    elif 12 <= curr_hour < 17:
        time_greeting = "Good afternoon"
    elif 17 <= curr_hour < 22:
        time_greeting = "Good evening"

    role_titles = {
        "donor": "Food Donor Partner",
        "ngo": "Verified NGO Food Bank",
        "volunteer": "Volunteer Rescue Driver",
        "admin": "Platform Administrator",
    }

    st.markdown(
        f"""
        <div class="sl-hero">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
                <div>
                    <div style="display: inline-block; background: rgba(255, 255, 255, 0.18); backdrop-filter: blur(8px); padding: 4px 12px; border-radius: 9999px; font-size: 0.8rem; font-weight: 700; margin-bottom: 12px; letter-spacing: 0.05em; text-transform: uppercase;">
                        {role_titles.get(user.role, user.role.capitalize())}
                    </div>
                    <h1>{time_greeting}, {user.display_name}! 👋</h1>
                    <p>Welcome to your SurplusLink portal. Monitor live donations, manage pickups, and keep food out of landfills.</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if user.role == "ngo" and not user.verified:
        st.warning("⏳ **Account Pending Verification**: Your NGO registration is being reviewed by administrators. Once approved, you can instantly claim priority food donations.")

    # Platform & User Metrics
    with session_scope() as s:
        open_count = len(s.scalars(select(Listing.id).where(Listing.status == "open")).all())
        in_transit = len(s.scalars(select(Listing.id).where(Listing.status.in_(["claimed", "picked_up"]))).all())
        stats_data = impact.stats(s, user.id if user.role == "donor" else None)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f"""
            <div class="sl-stat-card">
                <div class="sl-stat-val" style="color: #059669;">{open_count}</div>
                <div class="sl-stat-lbl">Open Food Listings</div>
                <div class="sl-stat-sub">🟢 Ready for pickup now</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f"""
            <div class="sl-stat-card">
                <div class="sl-stat-val" style="color: #0284C7;">{in_transit}</div>
                <div class="sl-stat-lbl">Active Rescues</div>
                <div class="sl-stat-sub">🚚 In transit or claimed</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m3:
        meals_lbl = "Your Rescued Meals" if user.role == "donor" else "Total Meals Delivered"
        st.markdown(
            f"""
            <div class="sl-stat-card">
                <div class="sl-stat-val" style="color: #7C3AED;">{stats_data['meals']:,}</div>
                <div class="sl-stat-lbl">{meals_lbl}</div>
                <div class="sl-stat-sub">🍽️ Fed to communities</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            f"""
            <div class="sl-stat-card">
                <div class="sl-stat-val" style="color: #D97706;">{stats_data['co2e_kg']:,.0f} kg</div>
                <div class="sl-stat-lbl">CO₂e Avoided</div>
                <div class="sl-stat-sub">🌱 Greenhouse gas saved</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
    st.subheader("⚡ Quick Action Hub")

    # Role tailored action hubs
    if user.role == "donor":
        a1, a2, a3 = st.columns(3)
        with a1:
            st.markdown(
                """
                <div class="sl-card" style="height: 100%;">
                    <div style="font-size: 1.8rem; margin-bottom: 8px;">➕</div>
                    <div style="font-weight: 700; font-size: 1.15rem; color: #0F172A; margin-bottom: 4px;">Post Surplus Food</div>
                    <p style="color: #64748B; font-size: 0.88rem; margin-bottom: 16px;">Create a new donation with smart safe-until countdowns and notify nearby NGOs immediately.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/1_Post_Food.py", label="Post New Food ➔", icon="➕", use_container_width=True)

        with a2:
            st.markdown(
                """
                <div class="sl-card" style="height: 100%;">
                    <div style="font-size: 1.8rem; margin-bottom: 8px;">📋</div>
                    <div style="font-weight: 700; font-size: 1.15rem; color: #0F172A; margin-bottom: 4px;">Track My Donations</div>
                    <p style="color: #64748B; font-size: 0.88rem; margin-bottom: 16px;">View pickup statuses, assigned NGOs, driver locations, and completed deliveries.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/3_My_Activity.py", label="View Activity ➔", icon="📋", use_container_width=True)

        with a3:
            st.markdown(
                """
                <div class="sl-card" style="height: 100%;">
                    <div style="font-size: 1.8rem; margin-bottom: 8px;">📈</div>
                    <div style="font-weight: 700; font-size: 1.15rem; color: #0F172A; margin-bottom: 4px;">Impact & AI Forecast</div>
                    <p style="color: #64748B; font-size: 0.88rem; margin-bottom: 16px;">Explore environmental metrics, your donation history, and predicted tomorrow surplus.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/4_Impact.py", label="View Analytics ➔", icon="📈", use_container_width=True)

    elif user.role == "ngo":
        a1, a2, a3 = st.columns(3)
        with a1:
            st.markdown(
                """
                <div class="sl-card" style="height: 100%;">
                    <div style="font-size: 1.8rem; margin-bottom: 8px;">🔎</div>
                    <div style="font-weight: 700; font-size: 1.15rem; color: #0F172A; margin-bottom: 4px;">Find Available Food</div>
                    <p style="color: #64748B; font-size: 0.88rem; margin-bottom: 16px;">Review priority offers assigned to your NGO or browse the live open board within your service radius.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/2_Find_Food.py", label="Browse Food ➔", icon="🔎", use_container_width=True)

        with a2:
            st.markdown(
                """
                <div class="sl-card" style="height: 100%;">
                    <div style="font-size: 1.8rem; margin-bottom: 8px;">📋</div>
                    <div style="font-weight: 700; font-size: 1.15rem; color: #0F172A; margin-bottom: 4px;">My Pickups & Claims</div>
                    <p style="color: #64748B; font-size: 0.88rem; margin-bottom: 16px;">Confirm collections, coordinate with volunteer drivers, and log delivered meals.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/3_My_Activity.py", label="My Pickups ➔", icon="📋", use_container_width=True)

        with a3:
            st.markdown(
                """
                <div class="sl-card" style="height: 100%;">
                    <div style="font-size: 1.8rem; margin-bottom: 8px;">📈</div>
                    <div style="font-weight: 700; font-size: 1.15rem; color: #0F172A; margin-bottom: 4px;">Impact & Planning</div>
                    <p style="color: #64748B; font-size: 0.88rem; margin-bottom: 16px;">Track food distribution volume and view predicted regional surplus for tomorrow.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/4_Impact.py", label="View Impact ➔", icon="📈", use_container_width=True)

    elif user.role == "volunteer":
        a1, a2, a3 = st.columns(3)
        with a1:
            st.markdown(
                """
                <div class="sl-card" style="height: 100%;">
                    <div style="font-size: 1.8rem; margin-bottom: 8px;">🚗</div>
                    <div style="font-weight: 700; font-size: 1.15rem; color: #0F172A; margin-bottom: 4px;">Transport Jobs Near Me</div>
                    <p style="color: #64748B; font-size: 0.88rem; margin-bottom: 16px;">Pick up claimed food batches from hotels and deliver them safely to recipient NGOs.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/2_Find_Food.py", label="Find Jobs ➔", icon="🚗", use_container_width=True)

        with a2:
            st.markdown(
                """
                <div class="sl-card" style="height: 100%;">
                    <div style="font-size: 1.8rem; margin-bottom: 8px;">📋</div>
                    <div style="font-weight: 700; font-size: 1.15rem; color: #0F172A; margin-bottom: 4px;">My Active Deliveries</div>
                    <p style="color: #64748B; font-size: 0.88rem; margin-bottom: 16px;">View pickup addresses, contacts, route links, and mark packages as delivered.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/3_My_Activity.py", label="My Jobs ➔", icon="📋", use_container_width=True)

        with a3:
            st.markdown(
                """
                <div class="sl-card" style="height: 100%;">
                    <div style="font-size: 1.8rem; margin-bottom: 8px;">📈</div>
                    <div style="font-weight: 700; font-size: 1.15rem; color: #0F172A; margin-bottom: 4px;">Community Impact</div>
                    <p style="color: #64748B; font-size: 0.88rem; margin-bottom: 16px;">See how your volunteer runs are turning food waste into hunger relief.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/4_Impact.py", label="View Impact ➔", icon="📈", use_container_width=True)

    elif user.role == "admin":
        a1, a2, a3 = st.columns(3)
        with a1:
            st.markdown(
                """
                <div class="sl-card" style="height: 100%;">
                    <div style="font-size: 1.8rem; margin-bottom: 8px;">🛠️</div>
                    <div style="font-weight: 700; font-size: 1.15rem; color: #0F172A; margin-bottom: 4px;">Admin Control Desk</div>
                    <p style="color: #64748B; font-size: 0.88rem; margin-bottom: 16px;">Verify pending NGO applicants, manage users, and inspect recent food flows.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/5_Admin.py", label="Open Admin Desk ➔", icon="🛠️", use_container_width=True)

        with a2:
            st.markdown(
                """
                <div class="sl-card" style="height: 100%;">
                    <div style="font-size: 1.8rem; margin-bottom: 8px;">📈</div>
                    <div style="font-weight: 700; font-size: 1.15rem; color: #0F172A; margin-bottom: 4px;">Platform Analytics</div>
                    <p style="color: #64748B; font-size: 0.88rem; margin-bottom: 16px;">Monitor city-wide rescue volume, emission reductions, and leaderboards.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/4_Impact.py", label="View Platform Stats ➔", icon="📈", use_container_width=True)

        with a3:
            st.markdown(
                """
                <div class="sl-card" style="height: 100%;">
                    <div style="font-size: 1.8rem; margin-bottom: 8px;">🔎</div>
                    <div style="font-weight: 700; font-size: 1.15rem; color: #0F172A; margin-bottom: 4px;">Live Listings Board</div>
                    <p style="color: #64748B; font-size: 0.88rem; margin-bottom: 16px;">Inspect currently open offers and escalation chains in real-time.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/2_Find_Food.py", label="Inspect Listings ➔", icon="🔎", use_container_width=True)

    # Live Feed of Open Listings
    st.markdown("<div style='margin-top: 36px;'></div>", unsafe_allow_html=True)
    st.subheader("🍲 Live Open Listings Preview")
    with session_scope() as s:
        live_open = s.scalars(select(Listing).where(Listing.status == "open", Listing.pickup_by > now()).order_by(Listing.safe_until).limit(3)).all()

    if not live_open:
        st.info("No active open food listings right now. Check back shortly or post a new donation!")
    else:
        f_cols = st.columns(len(live_open))
        for idx, listing in enumerate(live_open):
            with f_cols[idx]:
                mins = safety.minutes_left(listing.pickup_by, now())
                urgency_class = "sl-pill-urgent" if mins < 60 else "sl-pill-warning" if mins < 120 else "sl-pill-success"
                veg_tag = '<span class="sl-pill sl-pill-veg">🌱 Veg</span>' if listing.veg else '<span class="sl-pill sl-pill-nonveg">🍗 Non-Veg</span>'
                
                st.markdown(
                    f"""
                    <div class="sl-card" style="padding: 16px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            {veg_tag}
                            <span class="sl-pill {urgency_class}">⏰ {safety.format_minutes(mins)}</span>
                        </div>
                        <div style="font-weight: 700; font-size: 1.05rem; color: #0F172A; margin-bottom: 4px;">{listing.title}</div>
                        <div style="font-size: 0.82rem; color: #475569; margin-bottom: 8px;">
                            📍 {listing.donor.display_name} · <b>{listing.quantity_meals} meals</b>
                        </div>
                        <div style="font-size: 0.78rem; color: #64748B;">Safe until: <b>{listing.safe_until:%H:%M}</b></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        st.page_link("pages/2_Find_Food.py", label="View all listings on the map ➔", icon="🔎")

    st.stop()


# ==============================================================================
# 2. LOGGED-OUT EXPERIENCE (HERO, DEMO LOGINS, STANDARD LOGIN & REGISTRATION)
# ==============================================================================

st.markdown(
    """
    <div class="sl-hero">
        <div style="display: inline-block; background: rgba(255, 255, 255, 0.18); backdrop-filter: blur(8px); padding: 4px 14px; border-radius: 9999px; font-size: 0.82rem; font-weight: 700; margin-bottom: 14px; letter-spacing: 0.05em; text-transform: uppercase;">
            🌱 Surplus Food Rescue & Redistribution
        </div>
        <h1>SurplusLink</h1>
        <p>A smart, real-time logistics platform connecting hotels, caterers, and canteens with verified NGOs and volunteer drivers to feed communities before safe food goes to waste.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Workflow Explainer
w1, w2, w3 = st.columns(3)
with w1:
    st.markdown(
        """
        <div class="sl-card" style="text-align: center; border-top: 4px solid #059669;">
            <div style="font-size: 2.2rem; margin-bottom: 10px;">🏨</div>
            <div style="font-weight: 700; font-size: 1.05rem; color: #0F172A; margin-bottom: 6px;">1. Post in Seconds</div>
            <p style="color: #64748B; font-size: 0.85rem; line-height: 1.5;">Hotels & caterers post cooked surplus with food-safety timers and one-tap re-post options.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with w2:
    st.markdown(
        """
        <div class="sl-card" style="text-align: center; border-top: 4px solid #0284C7;">
            <div style="font-size: 2.2rem; margin-bottom: 10px;">⚡</div>
            <div style="font-weight: 700; font-size: 1.05rem; color: #0F172A; margin-bottom: 6px;">2. Smart Dispatch</div>
            <p style="color: #64748B; font-size: 0.85rem; line-height: 1.5;">15-minute priority matching offers food to the closest verified NGO with matched meal capacity.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with w3:
    st.markdown(
        """
        <div class="sl-card" style="text-align: center; border-top: 4px solid #D97706;">
            <div style="font-size: 2.2rem; margin-bottom: 10px;">🚗</div>
            <div style="font-weight: 700; font-size: 1.05rem; color: #0F172A; margin-bottom: 6px;">3. Rapid Transport</div>
            <p style="color: #64748B; font-size: 0.85rem; line-height: 1.5;">NGOs claim and volunteer drivers deliver food directly to shelters and communities in need.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)

# 1-Click Demo Login Bar
st.markdown("### ⚡ Quick Demo Access (1-Click Login)")
st.caption("Select any role below to test the platform instantly with pre-seeded demo accounts:")

d_cols = st.columns(4)
for i, acc in enumerate(ui.DEMO_ACCOUNTS):
    with d_cols[i]:
        st.markdown(
            f"""
            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 12px; margin-bottom: 8px;">
                <div style="font-weight: 700; font-size: 0.9rem; color: #0F172A;">{acc['label']}</div>
                <div style="font-size: 0.75rem; color: #64748B;">{acc['desc']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(f"Log in as {acc['role']}", key=f"demo_login_{acc['email']}", use_container_width=True):
            ui.switch_to_demo_user(acc["email"])
            st.rerun()

st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)

# Standard Authentication Tabs
auth_tab1, auth_tab2 = st.tabs(["🔐 Standard Log In", "📝 Create an Account"])

with auth_tab1:
    with st.container(border=True):
        st.markdown("#### Log In to SurplusLink")
        with st.form("standard_login"):
            email_in = st.text_input("Email Address", placeholder="e.g. donor1@demo.com")
            password_in = st.text_input("Password", type="password", placeholder="••••••••")
            submit_login = st.form_submit_button("Sign In to Account", type="primary", use_container_width=True)
            if submit_login:
                with session_scope() as s:
                    u = authenticate(s, email_in, password_in)
                    uid = u.id if u else None
                if uid:
                    st.session_state["user_id"] = uid
                    st.rerun()
                else:
                    st.error("Invalid email or password. For demo accounts, use password 'demo123'.")

with auth_tab2:
    with st.container(border=True):
        st.markdown("#### Register a New Organization or Volunteer Account")
        role_labels = {
            "donor": "🏨 Food Donor (Hotel, Restaurant, Caterer, Canteen)",
            "ngo": "🏢 NGO / Shelter / Food Bank (Recipient & Distribution)",
            "volunteer": "🚗 Volunteer Driver (Food Transport)",
        }
        selected_role = st.radio("Account Type", list(role_labels), format_func=role_labels.get)
        
        c1, c2 = st.columns(2)
        r_name = c1.text_input("Your Full Name", placeholder="e.g. Ramesh Kumar")
        r_org = c2.text_input("Organisation Name" + ("" if selected_role != "volunteer" else " (optional)"),
                              placeholder="e.g. Grand Palace Hotel / Seva Trust")
        r_email = c1.text_input("Email Address", placeholder="name@organization.com", key="reg_email")
        r_phone = c2.text_input("Phone Number", placeholder="+91 98765 43210 (for SMS/WhatsApp alerts)")
        r_pass = c1.text_input("Password (min 6 characters)", type="password", key="reg_pw")
        r_addr = c2.text_input("Operating Street Address", placeholder="e.g. 42 MG Road, Indiranagar")
        
        st.markdown("##### 📍 Location & Hub Coordinates")
        lat, lon = ui.location_input("reg")
        
        capacity, vehicle = 0, False
        if selected_role == "ngo":
            st.markdown("##### 🏢 NGO Operational Details")
            c_ngo1, c_ngo2 = st.columns(2)
            capacity = c_ngo1.number_input("Maximum meal capacity you can absorb at once", min_value=10, value=150, step=10)
            vehicle = c_ngo2.checkbox("We have our own transport vehicle / van for pickups", value=True)
            st.caption("ℹ️ NGOs require admin review before claiming donations to guarantee food hygiene compliance.")
            
        if st.button("Create My Account", type="primary", use_container_width=True):
            try:
                with session_scope() as s:
                    u = register_user(
                        s,
                        email=r_email,
                        password=r_pass,
                        name=r_name,
                        role=selected_role,
                        org_name=r_org.strip() or None,
                        phone=r_phone.strip() or None,
                        address=r_addr.strip() or None,
                        lat=lat,
                        lon=lon,
                        capacity_meals=int(capacity),
                        has_vehicle=vehicle,
                    )
                    uid = u.id
                st.session_state["user_id"] = uid
                st.success("Account created successfully! Welcome to SurplusLink.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
