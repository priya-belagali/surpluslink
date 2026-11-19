"""Impact figures and a next-day surplus forecast."""
from datetime import timedelta

import pandas as pd
import streamlit as st

from core import config, forecast, impact, simulation, ui
from core.db import now, session_scope

user = ui.current_user()
is_donor = user.role == "donor"
ui.page_header("Impact", "Meals delivered, estimated food and emissions avoided, and the surplus we expect tomorrow.")

scope_donor = user.id if is_donor else None
with session_scope() as s:
    totals = impact.stats(s, scope_donor)
    series = impact.daily_series(s, 30, scope_donor)
    board = impact.leaderboard(s)
    check = forecast.platform_backtest(s, now().date())
    tomorrow = (now() + timedelta(days=1)).date()
    if is_donor:
        f = forecast.donor_forecast_detail(s, user.id, tomorrow)
        donors_counted = 1 if f["expected"] is not None else 0
        expected = f["expected"]
    else:
        expected, donors_counted = forecast.platform_forecast(s, tomorrow)

st.subheader("Your impact" if is_donor else "Platform impact")
ui.figures([("Meals delivered", f"{totals['meals']:,}"), ("Food rescued (kg)", f"{totals['kg_food']:,}"),
            ("CO2e avoided (kg)", f"{totals['co2e_kg']:,}"), ("Deliveries", totals["deliveries"])])
st.caption(f"Estimates assume {config.KG_PER_MEAL} kg of food per meal and {config.CO2E_KG_PER_KG_FOOD} kg CO2e per kg of food. "
           "Both are editable in core/config.py. They are rough figures, not measurements.")

if len(series):
    st.subheader("Meals delivered in the last 30 days")
    st.bar_chart(series, color="#23405F")

if not is_donor and board:
    st.subheader("Top donors")
    st.dataframe(pd.DataFrame([{"Rank": i, "Donor": name, "Meals delivered": meals}
                               for i, (name, meals) in enumerate(board, 1)]), hide_index=True)

st.subheader(f"Expected surplus tomorrow ({tomorrow:%A})")
if expected is None:
    st.info("There is not enough history yet. A forecast appears after a few days of donations.")
else:
    ui.figures([("Your expected surplus" if is_donor else "Expected across donors", f"about {round(expected)} meals")])
    st.caption("Average of past totals for the same weekday, or the overall daily average while history is short."
               + ("" if is_donor else f" Donors included: {donors_counted}."))

st.subheader("Is the forecast any good?")
if check is None:
    st.caption("The forecast needs about three weeks of history before it can test itself.")
else:
    ui.figures([("Weekday forecast, average error", f"{check['mae_weekday']:.0f} meals a day"),
                ("Overall average, average error", f"{check['mae_naive']:.0f} meals a day"),
                ("Difference", f"{check['improvement_pct']:+.0f}%")])
    st.caption(f"Each of the last {check['days_tested']} days was predicted using only earlier days, then compared with what happened. "
               "The overall average assumes every day looks the same. A positive difference means the weekday forecast did better. "
               "The demo history has a weekend effect built in, so on real data this number should be watched, not assumed.")

st.subheader("Does learning from NGO behaviour help?")
st.caption("Matching adds a waiting penalty for NGOs that often stay silent or decline, learned from past offers. "
           "This simulation compares it with ranking by distance alone, on the same synthetic listings and the same hidden NGO behaviour.")
if st.button("Run the simulation"):
    sim = simulation.simulate()
    f_, l_ = sim["fixed"], sim["learning"]
    st.dataframe(pd.DataFrame([
        {"Measure": "Average minutes until an NGO accepts", "Distance only": f"{f_['mean_minutes']:.1f}", "With learning": f"{l_['mean_minutes']:.1f}"},
        {"Measure": "Slowest 10 percent, minutes", "Distance only": f"{f_['p90_minutes']:.1f}", "With learning": f"{l_['p90_minutes']:.1f}"},
        {"Measure": "First NGO asked accepts", "Distance only": f"{f_['first_offer_accepted']:.0%}", "With learning": f"{l_['first_offer_accepted']:.0%}"},
        {"Measure": "Nobody accepted; opened to all", "Distance only": f"{f_['fell_through']:.0%}", "With learning": f"{l_['fell_through']:.0%}"},
    ]), hide_index=True)
    st.line_chart(pd.DataFrame(sim["curve"]).set_index("listings"))
    a = sim["assumptions"]
    st.caption(f"{a['listings']} synthetic listings, {a['ngos']} NGOs, {a['timeout_min']:g}-minute offers. Each NGO was given hidden "
               "habits (how often it is silent, how often it accepts, how quickly it answers). The result shows whether the idea works "
               "under these assumptions. It is not evidence about real NGOs.")
