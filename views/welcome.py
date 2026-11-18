"""Signed-out landing page: what the service does, plus sign in and registration."""
import streamlit as st

from core import config, impact, ui
from core.auth import authenticate, register_user
from core.db import session_scope
from core.safety import format_duration

ROLE_CHOICES = {"donor": "Food donor", "ngo": "NGO or food bank", "volunteer": "Volunteer driver"}
ROLE_HELP = {
    "donor": "Hotels, caterers, canteens and event kitchens with surplus cooked food.",
    "ngo": "Organisations that distribute food to people in need. An administrator approves each NGO before it can claim.",
    "volunteer": "Individuals with a vehicle who can move food from a donor to an NGO.",
}

with session_scope() as s:
    totals = impact.stats(s)

left, right = st.columns([6, 5], gap="large")

with left:
    note = (f'<p class="note"><b>{totals["meals"]:,}</b> meals delivered in {totals["deliveries"]:,} deliveries so far.</p>'
            if totals["meals"] else "")
    st.markdown(
        '<div class="intro"><div class="wordmark">SurplusLink</div>'
        "<h1>Surplus cooked food, matched to an NGO before it spoils.</h1>"
        "<p>Kitchens list what is left, with the time it was cooked. The nearest NGO with room for it gets first refusal for "
        f"{format_duration(config.OFFER_TIMEOUT_SEC)}. If it does not respond, the next NGO is asked. "
        "Each delivery produces a record laid out in the format of FSSAI Schedule II.</p>"
        '<ol class="proc">'
        "<li><div><strong>List.</strong> The kitchen enters the food, quantity, time cooked and temperature.</div></li>"
        "<li><div><strong>Offer.</strong> NGOs are ranked by distance, capacity and vehicle. The best match is asked first.</div></li>"
        "<li><div><strong>Claim.</strong> The first NGO to accept gets the food. Only one claim can succeed.</div></li>"
        "<li><div><strong>Collect.</strong> The NGO, or a volunteer driver, collects it and confirms.</div></li>"
        "<li><div><strong>Record.</strong> The quantity and area distributed complete the record, which both sides can download.</div></li>"
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
                    st.error("That email and password do not match an account.")

        with tab_up:
            role = st.radio("Account type", list(ROLE_CHOICES), format_func=ROLE_CHOICES.get, horizontal=True)
            st.caption(ROLE_HELP[role])
            name = st.text_input("Your name")
            org = st.text_input("Organisation name" + (" (optional)" if role == "volunteer" else ""))
            email_r = st.text_input("Email", key="reg_email")
            phone = st.text_input("Phone", help="Include the country code, for example +91, so WhatsApp or SMS alerts can reach you.")
            password_r = st.text_input("Password", type="password", key="reg_pw", help="At least 6 characters.")
            fssai = darpan = None
            capacity, vehicle = 0, False
            if role == "donor":
                fssai = st.text_input("FSSAI licence or registration number",
                                      help="Printed on each donation record. You can add it later from the Post surplus food page.")
            if role == "ngo":
                fssai = st.text_input("FSSAI registration number", help="Distribution organisations are expected to be registered with FSSAI.")
                darpan = st.text_input("NGO Darpan ID", help="The unique ID from the NITI Aayog NGO Darpan portal.")
                capacity = st.number_input("Meals you can handle at once", min_value=0, value=100, step=10)
                vehicle = st.checkbox("We have our own vehicle for pickups")
            address, lat, lon = ui.location_input("reg", label="Address")
            if st.button("Create account", type="primary"):
                try:
                    with session_scope() as s:
                        u = register_user(
                            s, email=email_r, password=password_r, name=name, role=role,
                            org_name=org.strip() or None, phone=phone.strip() or None,
                            address=address.strip() or None, lat=lat, lon=lon,
                            capacity_meals=int(capacity), has_vehicle=vehicle,
                            fssai_number=(fssai or "").strip() or None, darpan_id=(darpan or "").strip() or None,
                        )
                        uid = u.id
                    st.session_state["user_id"] = uid
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
