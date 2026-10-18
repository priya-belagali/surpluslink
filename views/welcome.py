"""Signed-out landing page: what the service does, plus sign in and registration."""
import streamlit as st

from core import config, impact, ui
from core.auth import authenticate, register_user
from core.db import session_scope

ROLE_CHOICES = {"donor": "Food donor", "ngo": "NGO or food bank", "volunteer": "Volunteer driver"}
ROLE_HELP = {
    "donor": "Hotels, caterers, canteens and event kitchens with surplus food.",
    "ngo": "Registered organisations that feed people in need. An administrator approves new NGOs.",
    "volunteer": "Individuals with a vehicle who can move food from donors to NGOs.",
}

with session_scope() as s:
    meals = impact.stats(s)["meals"]

left, right = st.columns([7, 5], gap="large")

with left:
    note = f'<p class="hero-note"><b>{meals:,}</b> meals delivered so far.</p>' if meals else ""
    st.markdown(
        '<div class="hero"><div class="hero-name">SurplusLink</div>'
        "<h1>Get surplus food to people who need it, before it spoils.</h1>"
        '<p class="hero-sub">Hotels and caterers list what is left over. Verified NGOs claim it. '
        "Volunteers carry it across town.</p>"
        '<ol class="steps">'
        "<li><div><strong>Post.</strong> A donor lists what is left, how much, and when it was cooked.</div></li>"
        f"<li><div><strong>Match.</strong> The closest NGO with room gets first refusal for "
        f"{config.OFFER_TIMEOUT_MIN} minutes. If it passes, the next one is asked.</div></li>"
        "<li><div><strong>Deliver.</strong> The NGO or a volunteer collects the food and confirms the delivery.</div></li>"
        f"</ol>{note}</div>",
        unsafe_allow_html=True,
    )

with right:
    with st.container(border=True):
        tab_in, tab_up = st.tabs(["Sign in", "Create account"])

        with tab_in:
            with st.form("login", border=False):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign in", type="primary")
            if submitted:
                with session_scope() as s:
                    u = authenticate(s, email, password)
                    uid = u.id if u else None
                if uid:
                    st.session_state["user_id"] = uid
                    st.rerun()
                else:
                    st.error("That email and password do not match an account. Check both and try again.")

        with tab_up:
            role = st.radio("I am a", list(ROLE_CHOICES), format_func=ROLE_CHOICES.get, horizontal=True)
            st.caption(ROLE_HELP[role])
            name = st.text_input("Your name")
            org = st.text_input("Organisation name" + (" (optional)" if role == "volunteer" else ""))
            email_r = st.text_input("Email", key="reg_email")
            phone = st.text_input("Phone (optional)", help="Used for SMS or WhatsApp alerts if they are enabled.")
            password_r = st.text_input("Password", type="password", key="reg_pw", help="At least 6 characters.")
            address = st.text_input("Address")
            lat, lon = ui.location_input("reg")
            capacity, vehicle = 0, False
            if role == "ngo":
                capacity = st.number_input("Meals you can handle at once", min_value=0, value=100, step=10)
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
