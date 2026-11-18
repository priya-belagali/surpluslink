"""SurplusLink entry point: one-time setup, then a navigation menu that depends on who is signed in."""
import streamlit as st

from core import ui

ui.setup()
user = ui.current_user()

if user is None:
    nav = st.navigation([st.Page("views/welcome.py", title="Sign in", default=True)], position="hidden")
else:
    P = st.Page
    overview = P("views/overview.py", title="Overview", default=True)
    impact = P("views/impact.py", title="Impact", url_path="impact")
    coverage = P("views/coverage.py", title="Coverage", url_path="coverage")
    menus = {
        "donor": [overview, P("views/post_food.py", title="Post surplus food", url_path="post-food"),
                  P("views/activity.py", title="My donations", url_path="my-donations"), impact, coverage],
        "ngo": [overview, P("views/find_food.py", title="Available food", url_path="available-food"),
                P("views/activity.py", title="My pickups", url_path="my-pickups"), impact, coverage],
        "volunteer": [overview, P("views/find_food.py", title="Transport jobs", url_path="transport-jobs"),
                      P("views/activity.py", title="My jobs", url_path="my-jobs"), impact, coverage],
        "admin": [overview, P("views/admin.py", title="Administration", url_path="administration"), impact, coverage],
    }
    nav = st.navigation(menus[user.role])
    ui.sidebar(user)

nav.run()
