"""Impact figures and a next-day surplus forecast."""
from datetime import timedelta

import pandas as pd
import streamlit as st

from core import config, forecast, impact, ui
from core.db import now, session_scope

user = ui.current_user()
is_donor = user.role == "donor"
ui.page_header("Impact", "Meals delivered, food and emissions avoided, and the surplus we expect tomorrow.")

scope_donor = user.id if is_donor else None
with session_scope() as s:
    totals = impact.stats(s, scope_donor)
    series = impact.daily_series(s, 30, scope_donor)
    board = impact.leaderboard(s)
    tomorrow = (now() + timedelta(days=1)).date()
    if is_donor:
        expected, _ = forecast.donor_forecast(s, user.id, tomorrow)
        donors_counted = 1 if expected is not None else 0
    else:
        expected, donors_counted = forecast.platform_forecast(s, tomorrow)

st.subheader("Your impact" if is_donor else "Platform impact")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Meals delivered", f"{totals['meals']:,}")
c2.metric("Food rescued (kg)", f"{totals['kg_food']:,}")
c3.metric("CO2e avoided (kg)", f"{totals['co2e_kg']:,}")
c4.metric("Deliveries", totals["deliveries"])
st.caption(f"Estimates assume {config.KG_PER_MEAL} kg of food per meal and {config.CO2E_KG_PER_KG_FOOD} kg CO2e per kg of food. "
           "You can change both in core/config.py. They are rough figures, not measurements.")

if len(series):
    st.subheader("Meals delivered in the last 30 days")
    st.bar_chart(series, color="#17565E")

if not is_donor and board:
    st.subheader("Top donors")
    st.dataframe(pd.DataFrame([{"Rank": i, "Donor": name, "Meals delivered": meals}
                               for i, (name, meals) in enumerate(board, 1)]), hide_index=True)

st.subheader(f"Expected surplus tomorrow ({tomorrow:%A})")
if expected is None:
    st.info("There is not enough history yet. A forecast appears after a few days of donations.")
else:
    st.metric("Your expected surplus" if is_donor else "Expected surplus across donors", f"About {round(expected)} meals")
    st.caption("Based on the average of past totals for the same weekday, or the overall daily average while history is short."
               + ("" if is_donor else f" Donors included: {donors_counted}."))
