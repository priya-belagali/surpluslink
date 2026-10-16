"""Impact dashboard and next-day surplus forecast."""
from datetime import timedelta

import streamlit as st

from core import config, forecast, impact, ui
from core.db import now, session_scope

user = ui.start("Impact", icon="📈")
st.title("📈 Impact & forecast")

scope_donor = user.id if user.role == "donor" else None
with session_scope() as s:
    st_all = impact.stats(s, scope_donor)
    series = impact.daily_series(s, 30, scope_donor)
    board = impact.leaderboard(s)
    tomorrow = (now() + timedelta(days=1)).date()
    if user.role == "donor":
        expected, n_days = forecast.donor_forecast(s, user.id, tomorrow)
        donors_counted = 1 if expected is not None else 0
    else:
        expected, donors_counted = forecast.platform_forecast(s, tomorrow)
        n_days = None

st.subheader("Your impact" if scope_donor else "Platform impact")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Meals delivered", st_all["meals"])
c2.metric("Food rescued (kg)", st_all["kg_food"])
c3.metric("CO₂e avoided (kg)", st_all["co2e_kg"])
c4.metric("Deliveries", st_all["deliveries"])
st.caption(f"Estimates assume {config.KG_PER_MEAL} kg per meal and {config.CO2E_KG_PER_KG_FOOD} kg CO₂e per kg of food "
           "(editable in core/config.py). They are rough figures, not measurements.")

if len(series):
    st.subheader("Meals delivered, last 30 days")
    st.bar_chart(series)

if not scope_donor and board:
    st.subheader("🏆 Top donors")
    for rank, (name, meals) in enumerate(board, 1):
        st.write(f"{rank}. **{name}** — {meals} meals")

st.subheader(f"🔮 Expected surplus tomorrow ({tomorrow:%A})")
if expected is None:
    st.info("Not enough history yet. Forecasts appear after a few days of donations.")
else:
    label = "Your expected surplus" if user.role == "donor" else "Expected surplus across donors"
    st.metric(label, f"~{round(expected)} meals")
    st.caption("Based on the average of past same-weekday totals (or the overall daily average when history is short)."
               + (f" Donors counted: {donors_counted}." if user.role != "donor" else ""))
