"""SurplusLink - entry page: login, registration and role-based home."""
import streamlit as st
from sqlalchemy import select

from core import ui
from core.auth import authenticate, register_user
from core.db import Listing, session_scope

ui.setup("Home")
st.title("🍲 SurplusLink")
st.caption("Connecting surplus food from hotels and caterers with NGOs and volunteers who feed people in need.")

user = ui.current_user()

if user:
    ui.sidebar(user)
    st.success(f"Welcome, {user.display_name}!")
    if user.role == "ngo" and not user.verified:
        st.warning("Your NGO account is waiting for admin verification. You can claim food once it is approved.")

    st.subheader("Where to next?")
    links = {
        "donor": [("pages/1_Post_Food.py", "Post surplus food", "➕"), ("pages/3_My_Activity.py", "My donations", "📋")],
        "ngo": [("pages/2_Find_Food.py", "Find food to collect", "🔎"), ("pages/3_My_Activity.py", "My pickups", "📋")],
        "volunteer": [("pages/2_Find_Food.py", "Transport jobs near me", "🚗"), ("pages/3_My_Activity.py", "My jobs", "📋")],
        "admin": [("pages/5_Admin.py", "Admin panel", "🛠️")],
    }[user.role]
    links.append(("pages/4_Impact.py", "Impact & forecast", "📈"))
    for path, label, icon in links:
        st.page_link(path, label=label, icon=icon)

    with session_scope() as s:
        open_now = len(s.scalars(select(Listing.id).where(Listing.status == "open")).all())
    st.metric("Food listings open right now", open_now)
    st.stop()

login_tab, register_tab = st.tabs(["Log in", "Register"])

with login_tab:
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Log in", type="primary"):
            with session_scope() as s:
                u = authenticate(s, email, password)
                uid = u.id if u else None
            if uid:
                st.session_state["user_id"] = uid
                st.rerun()
            else:
                st.error("Wrong email or password.")

with register_tab:
    role_labels = {"donor": "Food donor (hotel, caterer, canteen)", "ngo": "NGO / food bank", "volunteer": "Volunteer driver"}
    role = st.radio("I am a…", list(role_labels), format_func=role_labels.get, horizontal=True)
    c1, c2 = st.columns(2)
    name = c1.text_input("Your name")
    org = c2.text_input("Organisation name" + ("" if role != "volunteer" else " (optional)"))
    email_r = c1.text_input("Email", key="reg_email")
    phone = c2.text_input("Phone (optional, used for SMS/WhatsApp alerts)")
    password_r = c1.text_input("Password (min 6 characters)", type="password", key="reg_pw")
    address = c2.text_input("Address")
    lat, lon = ui.location_input("reg")
    capacity, vehicle = 0, False
    if role == "ngo":
        capacity = st.number_input("How many meals can you handle at once?", min_value=0, value=100, step=10)
        vehicle = st.checkbox("We have our own vehicle for pickups")
    if st.button("Create account", type="primary"):
        try:
            with session_scope() as s:
                u = register_user(
                    s, email=email_r, password=password_r, name=name, role=role,
                    org_name=org.strip() or None, phone=phone.strip() or None,
                    address=address.strip() or None, lat=lat, lon=lon,
                    capacity_meals=int(capacity), has_vehicle=vehicle,
                )
                uid = u.id
            st.session_state["user_id"] = uid
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
