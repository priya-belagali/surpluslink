"""Shared Streamlit helpers: page setup, design system, login gate, sidebar, notifications, and location widget."""
from datetime import datetime
import html
import time
import uuid

import streamlit as st
from sqlalchemy import select, update

from core import config, matching
from core.db import Notification, User, init_db, session_scope

APP_NAME = "SurplusLink"
_last_tick = {"t": 0.0}

DEMO_ACCOUNTS = [
    {"label": "🏨 Grand Orchid Hotel", "email": "donor1@demo.com", "role": "Donor", "desc": "Large hotel surplus"},
    {"label": "🏢 Annapurna Food Bank", "email": "ngo1@demo.com", "role": "NGO", "desc": "Verified NGO (200 meals capacity)"},
    {"label": "🚗 Ravi (Volunteer)", "email": "vol1@demo.com", "role": "Volunteer", "desc": "On-demand delivery driver"},
    {"label": "🛡️ Platform Admin", "email": config.ADMIN_EMAIL, "role": "Admin", "desc": "Verification & oversight"},
]


@st.cache_resource
def _boot() -> bool:
    init_db()
    return True


def _maybe_tick() -> None:
    """Run housekeeping at most every 30 s. worker.py does the same if you run it separately."""
    if time.time() - _last_tick["t"] > 30:
        _last_tick["t"] = time.time()
        with session_scope() as s:
            matching.tick(s)


def inject_custom_css() -> None:
    """Inject modern, clean, responsive SaaS styling for SurplusLink."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

        /* Global typography & base styling */
        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            color: #0F172A;
        }

        /* Top header brand styling */
        .sl-brand-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: linear-gradient(135deg, rgba(5, 150, 105, 0.08) 0%, rgba(16, 185, 129, 0.16) 100%);
            border: 1px solid rgba(5, 150, 105, 0.25);
            padding: 5px 14px;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 600;
            color: #065F46;
            margin-bottom: 8px;
        }

        /* Hero banner card */
        .sl-hero {
            background: linear-gradient(135deg, #064E3B 0%, #065F46 45%, #047857 100%);
            border-radius: 20px;
            padding: 36px 36px;
            color: #FFFFFF;
            margin-bottom: 28px;
            box-shadow: 0 10px 30px -5px rgba(6, 78, 59, 0.25);
            position: relative;
            overflow: hidden;
        }

        .sl-hero h1 {
            color: #FFFFFF !important;
            font-weight: 800;
            font-size: 2.25rem;
            margin: 0 0 10px 0;
            letter-spacing: -0.02em;
        }

        .sl-hero p {
            color: #D1FAE5;
            font-size: 1.08rem;
            margin: 0;
            max-width: 720px;
            line-height: 1.6;
        }

        /* Sleek Card Container */
        .sl-card {
            background: #FFFFFF;
            border-radius: 16px;
            border: 1px solid #E2E8F0;
            box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.05);
            padding: 22px;
            margin-bottom: 18px;
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .sl-card:hover {
            border-color: #CBD5E1;
            box-shadow: 0 8px 30px -4px rgba(15, 23, 42, 0.09);
        }

        /* Stat / Metric Card */
        .sl-stat-card {
            background: #FFFFFF;
            border-radius: 16px;
            border: 1px solid #E2E8F0;
            padding: 18px 20px;
            box-shadow: 0 2px 12px -2px rgba(15, 23, 42, 0.04);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .sl-stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px -4px rgba(15, 23, 42, 0.08);
        }

        .sl-stat-val {
            font-size: 1.85rem;
            font-weight: 800;
            color: #0F172A;
            line-height: 1.2;
            letter-spacing: -0.02em;
        }

        .sl-stat-lbl {
            font-size: 0.85rem;
            font-weight: 600;
            color: #64748B;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 4px;
        }

        .sl-stat-sub {
            font-size: 0.8rem;
            color: #059669;
            font-weight: 500;
            margin-top: 6px;
        }

        /* Badges & Pills */
        .sl-pill {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 600;
            line-height: 1;
        }

        .sl-pill-veg {
            background-color: #ECFDF5;
            color: #047857;
            border: 1px solid #A7F3D0;
        }

        .sl-pill-nonveg {
            background-color: #FFF1F2;
            color: #BE123C;
            border: 1px solid #FECDD3;
        }

        .sl-pill-urgent {
            background-color: #FEF2F2;
            color: #DC2626;
            border: 1px solid #FCA5A5;
            animation: pulse-border 1.8s infinite;
        }

        .sl-pill-warning {
            background-color: #FFFBEB;
            color: #B45309;
            border: 1px solid #FDE68A;
        }

        .sl-pill-success {
            background-color: #F0FDF4;
            color: #15803D;
            border: 1px solid #BBF7D0;
        }

        .sl-pill-info {
            background-color: #F0F9FF;
            color: #0369A1;
            border: 1px solid #BAE6FD;
        }

        .sl-pill-role {
            background-color: #F8FAFC;
            color: #475569;
            border: 1px solid #E2E8F0;
            font-size: 0.75rem;
        }

        @keyframes pulse-border {
            0% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.4); }
            70% { box-shadow: 0 0 0 6px rgba(220, 38, 38, 0); }
            100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); }
        }

        /* Order / Job Lifecycle Stepper */
        .sl-stepper {
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: relative;
            margin: 16px 0;
            padding: 0 10px;
        }

        .sl-stepper::before {
            content: '';
            position: absolute;
            top: 14px;
            left: 24px;
            right: 24px;
            height: 3px;
            background: #E2E8F0;
            z-index: 1;
        }

        .sl-step {
            position: relative;
            z-index: 2;
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
        }

        .sl-step-circle {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            background: #F1F5F9;
            border: 2px solid #CBD5E1;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8rem;
            font-weight: 700;
            color: #64748B;
            transition: all 0.2s ease;
        }

        .sl-step-active .sl-step-circle {
            background: #059669;
            border-color: #059669;
            color: #FFFFFF;
            box-shadow: 0 0 0 4px rgba(5, 150, 105, 0.2);
        }

        .sl-step-done .sl-step-circle {
            background: #10B981;
            border-color: #10B981;
            color: #FFFFFF;
        }

        .sl-step-label {
            font-size: 0.75rem;
            font-weight: 600;
            color: #64748B;
            margin-top: 6px;
        }

        .sl-step-active .sl-step-label {
            color: #065F46;
            font-weight: 700;
        }

        /* Profile card in sidebar */
        .sl-user-card {
            background: linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%);
            border: 1px solid #E2E8F0;
            border-radius: 14px;
            padding: 14px 16px;
            margin-bottom: 14px;
        }

        .sl-user-avatar {
            width: 38px;
            height: 38px;
            border-radius: 50%;
            background: #059669;
            color: #FFFFFF;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 1rem;
            margin-right: 10px;
            vertical-align: middle;
        }

        /* Quick Action Cards */
        .sl-action-tile {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 14px;
            padding: 18px;
            box-shadow: 0 2px 10px -2px rgba(15, 23, 42, 0.04);
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .sl-action-tile:hover {
            border-color: #059669;
        }

        /* Streamlit Button enhancements */
        button[kind="primary"] {
            background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
            border: none !important;
            box-shadow: 0 4px 12px rgba(5, 150, 105, 0.25) !important;
            font-weight: 600 !important;
            border-radius: 10px !important;
            transition: all 0.2s ease !important;
        }

        button[kind="primary"]:hover {
            transform: translateY(-1px) !important;
            box-shadow: 0 6px 18px rgba(5, 150, 105, 0.35) !important;
        }

        button[kind="secondary"] {
            border-radius: 10px !important;
            font-weight: 500 !important;
            border: 1px solid #CBD5E1 !important;
        }

        button[kind="secondary"]:hover {
            border-color: #94A3B8 !important;
            background-color: #F8FAFC !important;
        }

        /* Clean tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            border-bottom: 2px solid #E2E8F0;
            padding-bottom: 2px;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 8px 8px 0 0;
            padding: 8px 16px;
            font-weight: 600;
            color: #64748B;
        }

        .stTabs [aria-selected="true"] {
            color: #059669 !important;
            border-bottom-color: #059669 !important;
        }

        /* Subtle scrollbars */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-thumb {
            background: #CBD5E1;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #94A3B8;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def setup(title: str, icon: str = "🍲") -> None:
    st.set_page_config(
        page_title=f"{title} · {APP_NAME}",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_custom_css()
    _boot()
    _maybe_tick()


def current_user() -> User | None:
    uid = st.session_state.get("user_id")
    if not uid:
        return None
    with session_scope() as s:
        return s.get(User, uid)


def logout() -> None:
    st.session_state.pop("user_id", None)


def switch_to_demo_user(email: str) -> None:
    with session_scope() as s:
        u = s.scalar(select(User).where(User.email == email.lower()))
        if u:
            st.session_state["user_id"] = u.id


def render_user_badge(user: User) -> str:
    role_color = {
        "donor": ("#0369A1", "#E0F2FE"),
        "ngo": ("#065F46", "#D1FAE5"),
        "volunteer": ("#B45309", "#FEF3C7"),
        "admin": ("#4338CA", "#E0E7FF"),
    }.get(user.role, ("#334155", "#F1F5F9"))
    
    verified_pill = (
        '<span style="background: #ECFDF5; color: #047857; padding: 2px 8px; border-radius: 9999px; font-size: 0.72rem; font-weight: 600; border: 1px solid #A7F3D0;">✓ Verified</span>'
        if user.verified
        else '<span style="background: #FFFBEB; color: #B45309; padding: 2px 8px; border-radius: 9999px; font-size: 0.72rem; font-weight: 600; border: 1px solid #FDE68A;">⏳ Pending Verification</span>'
    )
    
    initials = (user.name[0] if user.name else "U").upper()
    name_escaped = html.escape(user.display_name)
    role_escaped = html.escape(user.role.upper())
    
    return f"""
    <div class="sl-user-card">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
            <div style="display: flex; align-items: center;">
                <div class="sl-user-avatar">{initials}</div>
                <div>
                    <div style="font-weight: 700; font-size: 0.95rem; color: #0F172A; line-height: 1.2;">{name_escaped}</div>
                    <div style="font-size: 0.78rem; color: #64748B;">{html.escape(user.email)}</div>
                </div>
            </div>
        </div>
        <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
            <span style="background: {role_color[1]}; color: {role_color[0]}; padding: 2px 8px; border-radius: 9999px; font-size: 0.72rem; font-weight: 700;">{role_escaped}</span>
            {verified_pill}
        </div>
    </div>
    """


def sidebar(user: User) -> None:
    with st.sidebar:
        # App logo / title
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 18px; padding-bottom: 12px; border-bottom: 1px solid #E2E8F0;">
                <span style="font-size: 1.8rem;">🍲</span>
                <div>
                    <div style="font-size: 1.2rem; font-weight: 800; color: #064E3B; letter-spacing: -0.01em;">SurplusLink</div>
                    <div style="font-size: 0.74rem; color: #059669; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Food Rescue Network</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(render_user_badge(user), unsafe_allow_html=True)

        # Quick navigation
        st.markdown("<p style='font-size: 0.78rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em; margin: 12px 0 6px 0;'>Navigation</p>", unsafe_allow_html=True)
        st.page_link("Home.py", label="Dashboard / Home", icon="🏠")
        if user.role == "donor" or user.role == "admin":
            st.page_link("pages/1_Post_Food.py", label="Post Surplus Food", icon="➕")
        if user.role in ("ngo", "volunteer", "admin"):
            find_label = "Available Food Offers" if user.role == "ngo" else "Transport Jobs"
            st.page_link("pages/2_Find_Food.py", label=find_label, icon="🔎")
        st.page_link("pages/3_My_Activity.py", label="My Activity & Orders", icon="📋")
        st.page_link("pages/4_Impact.py", label="Impact & AI Forecast", icon="📈")
        if user.role == "admin":
            st.page_link("pages/5_Admin.py", label="Admin Control Panel", icon="🛠️")

        st.markdown("<div style='margin-top: 18px;'></div>", unsafe_allow_html=True)

        # Notifications
        with session_scope() as s:
            notes = s.scalars(
                select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(8)
            ).all()
        unread = sum(not n.is_read for n in notes)
        
        note_title = f"🔔 Notifications ({unread} new)" if unread else "🔔 Notifications"
        with st.expander(note_title, expanded=bool(unread)):
            if not notes:
                st.caption("No notifications yet.")
            else:
                for n in notes:
                    dot = "🟢 " if not n.is_read else "⚪ "
                    st.markdown(
                        f"""
                        <div style="padding: 6px 0; border-bottom: 1px solid #F1F5F9; font-size: 0.8rem;">
                            <span style="font-weight: 600; color: #475569;">{dot}{n.created_at:%d %b, %H:%M}</span><br/>
                            <span style="color: #1E293B;">{html.escape(n.message)}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                if unread and st.button("Mark all as read", key="sb_mark_read", use_container_width=True):
                    with session_scope() as s:
                        s.execute(update(Notification).where(Notification.user_id == user.id).values(is_read=True))
                    st.rerun()

        # Switch demo accounts easily
        with st.expander("⚡ Switch Demo Role"):
            st.caption("Quickly test the platform from other perspectives:")
            for acc in DEMO_ACCOUNTS:
                if acc["email"].lower() != user.email.lower():
                    if st.button(acc["label"], key=f"sb_switch_{acc['email']}", use_container_width=True):
                        switch_to_demo_user(acc["email"])
                        st.rerun()

        st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
        if st.button("Log out", key="sb_logout", use_container_width=True):
            logout()
            st.rerun()


def start(title: str, roles: list[str] | None = None, icon: str = "🍲") -> User:
    """Standard page opener: setup, require login, optional role check. Stops the page if it fails."""
    setup(title, icon)
    user = current_user()
    if user is None:
        st.warning("⚠️ You must be logged in to view this page.")
        st.page_link("Home.py", label="Go to Home / Login", icon="🏠")
        st.stop()
    sidebar(user)
    if roles and user.role not in roles and user.role != "admin":
        st.error(f"⛔ This page is reserved for: {', '.join(roles)}. You are currently logged in as '{user.role}'.")
        st.info("Tip: You can use the 'Switch Demo Role' tool in the sidebar to switch views.")
        st.stop()
    return user


def location_input(prefix: str, default: tuple[float, float] | None = None) -> tuple[float, float]:
    """City preset + editable coordinates with helpful map guidance."""
    cities = list(config.CITY_PRESETS)
    choice = st.selectbox("📍 Select Nearest City", cities, key=f"{prefix}_city")
    start = default if default else config.CITY_PRESETS[choice]
    c1, c2 = st.columns(2)
    lat = c1.number_input("Latitude", value=float(start[0]), format="%.5f", key=f"{prefix}_lat_{choice}",
                          help="Right-click in Google Maps to copy exact latitude.")
    lon = c2.number_input("Longitude", value=float(start[1]), format="%.5f", key=f"{prefix}_lon_{choice}",
                          help="Right-click in Google Maps to copy exact longitude.")
    st.caption(f"📌 Coordinates set for **{choice}**: `{lat:.4f}, {lon:.4f}`")
    return lat, lon


def save_photo(uploaded) -> str | None:
    if uploaded is None:
        return None
    ext = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else "jpg"
    path = config.PHOTO_DIR / f"{uuid.uuid4().hex}.{ext}"
    path.write_bytes(uploaded.getbuffer())
    return str(path)


def render_stepper_html(status: str) -> str:
    """Render a modern visual order tracking pipeline."""
    steps = [
        ("open", "1", "Listed"),
        ("claimed", "2", "Claimed"),
        ("picked_up", "3", "In Transit"),
        ("delivered", "4", "Delivered"),
    ]
    status_order = {"open": 1, "claimed": 2, "picked_up": 3, "delivered": 4, "expired": 0}
    current_idx = status_order.get(status, 0)

    if status == "expired":
        return """
        <div style="background: #F8FAFC; border: 1px dashed #CBD5E1; border-radius: 12px; padding: 10px 14px; text-align: center; color: #64748B; font-size: 0.85rem; font-weight: 600;">
            ⚪ This listing expired before collection.
        </div>
        """

    html_out = ['<div class="sl-stepper">']
    for code, num, label in steps:
        step_idx = status_order[code]
        if step_idx < current_idx:
            cls = "sl-step-done"
            symbol = "✓"
        elif step_idx == current_idx:
            cls = "sl-step-active"
            symbol = num
        else:
            cls = ""
            symbol = num
        
        html_out.append(f"""
        <div class="sl-step {cls}">
            <div class="sl-step-circle">{symbol}</div>
            <div class="sl-step-label">{label}</div>
        </div>
        """)
    html_out.append('</div>')
    return "".join(html_out)
