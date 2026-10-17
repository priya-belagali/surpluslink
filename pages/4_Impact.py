"""Impact Intelligence Dashboard and AI Surplus Forecast."""
from datetime import timedelta
import altair as alt
import pandas as pd
import streamlit as st

from core import config, forecast, impact, ui
from core.db import now, session_scope

user = ui.start("Impact", icon="📈")

scope_donor = user.id if user.role == "donor" else None

st.markdown(
    """
    <div style="margin-bottom: 24px;">
        <span class="sl-brand-badge">Environmental & Social Impact</span>
        <h1 style="font-size: 2.1rem; font-weight: 800; color: #0F172A; margin: 4px 0 6px 0;">Impact Intelligence & Forecast</h1>
        <p style="color: #64748B; font-size: 1rem; margin: 0;">Quantifying food waste diversion, greenhouse gas abatement, and predictive AI dispatch planning.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with session_scope() as s:
    st_all = impact.stats(s, scope_donor)
    series_df = impact.daily_series(s, 30, scope_donor)
    leaderboard_data = impact.leaderboard(s)
    tomorrow = (now() + timedelta(days=1)).date()
    if user.role == "donor":
        expected, n_days = forecast.donor_forecast(s, user.id, tomorrow)
        donors_counted = 1 if expected is not None else 0
    else:
        expected, donors_counted = forecast.platform_forecast(s, tomorrow)
        n_days = None

# ------------------------------------------------------------------------------
# 1. CORE IMPACT METRIC TILES
# ------------------------------------------------------------------------------
co2_kg = st_all["co2e_kg"]
# Real-world equivalents: EPA estimates ~0.4 kg CO2 per passenger car km, ~21 kg CO2 absorbed per tree year
car_km_equiv = round(co2_kg / 0.40)
tree_days_equiv = round(co2_kg / (21.0 / 365.0))

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(
        f"""
        <div class="sl-stat-card">
            <div class="sl-stat-val" style="color: #059669;">{st_all['meals']:,}</div>
            <div class="sl-stat-lbl">Meals Rescued</div>
            <div class="sl-stat-sub">🍲 100% edible surplus</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f"""
        <div class="sl-stat-card">
            <div class="sl-stat-val" style="color: #0284C7;">{st_all['kg_food']:,} kg</div>
            <div class="sl-stat-lbl">Food Rescued</div>
            <div class="sl-stat-sub">⚖️ Kept out of landfills</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        f"""
        <div class="sl-stat-card">
            <div class="sl-stat-val" style="color: #10B981;">{co2_kg:,.0f} kg</div>
            <div class="sl-stat-lbl">CO₂e Abated</div>
            <div class="sl-stat-sub">🌱 Methane emissions avoided</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with c4:
    st.markdown(
        f"""
        <div class="sl-stat-card">
            <div class="sl-stat-val" style="color: #7C3AED;">{st_all['deliveries']}</div>
            <div class="sl-stat-lbl">Rescue Missions</div>
            <div class="sl-stat-sub">🚚 Direct handovers</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Environmental equivalency pill bar
st.markdown(
    f"""
    <div style="background: linear-gradient(135deg, #ECFDF5 0%, #F0FDF4 100%); border: 1px solid #A7F3D0; border-radius: 12px; padding: 12px 18px; margin: 18px 0 28px 0; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
        <div style="font-size: 0.9rem; color: #065F46; font-weight: 700;">
            🌍 Carbon Offset Equivalent:
        </div>
        <div style="display: flex; gap: 16px; flex-wrap: wrap; font-size: 0.85rem; color: #047857; font-weight: 600;">
            <span>🚗 <b>{car_km_equiv:,} km</b> of car travel emissions avoided</span>
            <span>🌳 <b>{tree_days_equiv:,} tree-days</b> of carbon absorption</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------------------
# 2. INTERACTIVE TREND CHART (30-DAY DAILY VOLUME)
# ------------------------------------------------------------------------------
st.markdown("### 📊 30-Day Food Rescue Velocity")
if len(series_df) > 0:
    chart_df = series_df.reset_index()
    chart_df["date_str"] = pd.to_datetime(chart_df["date"]).dt.strftime("%d %b")

    chart = (
        alt.Chart(chart_df)
        .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, color="#059669")
        .encode(
            x=alt.X("date_str:N", title="Date", sort=None, axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("meals:Q", title="Meals Rescued"),
            tooltip=[
                alt.Tooltip("date_str:N", title="Date"),
                alt.Tooltip("meals:Q", title="Meals Rescued", format=","),
            ],
        )
        .properties(height=300)
        .configure_axis(
            labelFont="Plus Jakarta Sans, sans-serif",
            titleFont="Plus Jakarta Sans, sans-serif",
            gridColor="#F1F5F9",
        )
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("No distribution records within the last 30 days yet.")


# ------------------------------------------------------------------------------
# 3. PREDICTIVE AI SURPLUS FORECAST
# ------------------------------------------------------------------------------
st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
st.markdown("### 🔮 Predictive Surplus Intelligence")

with st.container(border=True):
    col_fc1, col_fc2 = st.columns([2, 3], gap="medium")
    with col_fc1:
        st.markdown(f"#### Tomorrow ({tomorrow:%A, %d %B})")
        if expected is None:
            st.info("Gathering historical data. SurplusLink requires at least 3 historical donation cycles to project volume.")
        else:
            fc_label = "Your Predicted Surplus" if user.role == "donor" else "Network Projected Surplus"
            st.markdown(
                f"""
                <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 14px; padding: 20px; text-align: center;">
                    <div style="font-size: 0.85rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em;">{fc_label}</div>
                    <div style="font-size: 2.6rem; font-weight: 800; color: #059669; line-height: 1.2; margin: 8px 0;">~{round(expected):,}</div>
                    <div style="font-size: 0.85rem; font-weight: 600; color: #334155;">Expected Meals</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with col_fc2:
        st.markdown("#### Operational Dispatch Insight")
        weekday_name = tomorrow.strftime("%A")
        is_weekend = tomorrow.weekday() >= 4  # Fri, Sat, Sun
        tip = (
            "Weekend wedding and banquet schedules typically yield 40-60% higher evening surplus. Recommend alerting volunteer drivers for late collections between 21:00 - 23:00."
            if is_weekend
            else "Weekday commercial and corporate canteen surpluses remain steady. Optimal pickup windows occur right after lunch (14:00 - 15:30) and dinner (21:30)."
        )
        st.markdown(
            f"""
            <div style="font-size: 0.92rem; line-height: 1.6; color: #334155; margin-bottom: 14px;">
                💡 <b>Pattern Analysis:</b> {tip}
            </div>
            <div style="background: #F1F5F9; border-radius: 8px; padding: 10px 14px; font-size: 0.82rem; color: #64748B;">
                📌 <b>Algorithm Methodology:</b> Weighted moving average of historical <code>{weekday_name}</code> distributions across active donors. 
                {f"Evaluated across {donors_counted} donor partners." if user.role != "donor" else f"Based on {n_days} recorded cycles."}
            </div>
            """,
            unsafe_allow_html=True,
        )


# ------------------------------------------------------------------------------
# 4. COMMUNITY LEADERBOARD (FOR NON-DONOR OR PLATFORM VIEW)
# ------------------------------------------------------------------------------
if not scope_donor and leaderboard_data:
    st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True)
    st.markdown("### 🏆 Top Food Rescue Champions")
    st.caption("Recognizing hotels and catering establishments diverting the highest volume of surplus food.")

    podium_cols = st.columns(min(3, len(leaderboard_data)))
    medals = ["🥇", "🥈", "🥉"]
    for idx, (org_name, meals) in enumerate(leaderboard_data[:3]):
        with podium_cols[idx]:
            st.markdown(
                f"""
                <div class="sl-card" style="text-align: center; border-top: 4px solid {'#F59E0B' if idx == 0 else '#94A3B8' if idx == 1 else '#B45309'};">
                    <div style="font-size: 2.2rem; margin-bottom: 6px;">{medals[idx]}</div>
                    <div style="font-weight: 800; font-size: 1.1rem; color: #0F172A; margin-bottom: 4px;">{org_name}</div>
                    <div style="font-size: 1.5rem; font-weight: 800; color: #059669; margin-bottom: 2px;">{meals:,}</div>
                    <div style="font-size: 0.78rem; font-weight: 600; color: #64748B; text-transform: uppercase;">Meals Rescued</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if len(leaderboard_data) > 3:
        with st.expander("View Full Leaderboard (Top 10)"):
            lb_df = pd.DataFrame([
                {"Rank": f"#{i}", "Donor Organization": name, "Total Meals Rescued": f"{m:,}"}
                for i, (name, m) in enumerate(leaderboard_data, 1)
            ])
            st.dataframe(lb_df, use_container_width=True, hide_index=True)
