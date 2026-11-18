"""Coverage: kitchens and venues from OpenStreetMap next to the NGOs registered on the platform."""
import pandas as pd
import streamlit as st
from sqlalchemy import select

from core import config, places, ui
from core.db import User, session_scope
from core.geo import haversine_km

ui.page_header("Coverage", f"Kitchens and venues within {config.COVERAGE_RADIUS_KM:g} km of {config.COVERAGE_CITY}, "
                           "and the NGOs registered here.")
data = places.load()
if not data:
    st.info("No coverage data has been fetched yet. Run `py scripts/fetch_places.py` once with an internet connection, "
            "or ask an administrator to fetch it from the Administration page.")
    st.stop()

centre = config.CITY_PRESETS.get(data["city"], config.CITY_PRESETS[config.COVERAGE_CITY])
with session_scope() as s:
    ngos = [u for u in s.scalars(select(User).where(User.role == "ngo", User.verified.is_(True), User.lat.is_not(None))).all()
            if haversine_km(centre[0], centre[1], u.lat, u.lon) <= data["radius_km"]]
    donors = s.scalars(select(User).where(User.role == "donor")).all()

pts = data["places"]
kinds = pd.Series([p["kind"] for p in pts]).value_counts()
ui.figures([("Kitchens and venues mapped", f"{len(pts):,}"), ("Approved NGOs on SurplusLink", len(ngos)),
            ("Donors on SurplusLink", len(donors))])

frame = pd.DataFrame(
    [{"lat": p["lat"], "lon": p["lon"], "color": "#8793A0", "size": 40} for p in pts]
    + [{"lat": u.lat, "lon": u.lon, "color": "#23405F", "size": 160} for u in ngos]
)
st.map(frame, latitude="lat", longitude="lon", color="color", size="size")
st.caption("Grey points are kitchens and venues from OpenStreetMap. Dark points are approved NGOs on this platform.")

st.subheader("What was mapped")
st.dataframe(pd.DataFrame({"Type": kinds.index, "Count": kinds.values}), hide_index=True)
st.caption(f"Map data from OpenStreetMap contributors (ODbL). Fetched {data['fetched_at']}. "
           "OpenStreetMap is volunteer-edited and incomplete, so treat the counts as a lower bound.")
