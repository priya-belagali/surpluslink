"""SurplusLink entry point: one-time setup, then a navigation menu that depends on who is signed in."""
import streamlit as st

from core import ui

ui.setup()
user = ui.current_user()

if user is None:
    nav = st.navigation([st.Page("views/welcome.py", title="Sign in", default=True)], position="hidden")
else:
    P = st.Page
    overview = P("views/overview.py", title="Overview", icon=":material/dashboard:", default=True)
    impact = P("views/impact.py", title="Impact", icon=":material/insights:", url_path="impact")
    menus = {
        "donor": [
            overview,
            P("views/post_food.py", title="Post surplus food", icon=":material/add_circle:", url_path="post-food"),
            P("views/activity.py", title="My donations", icon=":material/receipt_long:", url_path="my-donations"),
            impact,
        ],
        "ngo": [
            overview,
            P("views/find_food.py", title="Available food", icon=":material/search:", url_path="available-food"),
            P("views/activity.py", title="My pickups", icon=":material/inventory_2:", url_path="my-pickups"),
            impact,
        ],
        "volunteer": [
            overview,
            P("views/find_food.py", title="Transport jobs", icon=":material/local_shipping:", url_path="transport-jobs"),
            P("views/activity.py", title="My jobs", icon=":material/task_alt:", url_path="my-jobs"),
            impact,
        ],
        "admin": [
            overview,
            P("views/admin.py", title="Administration", icon=":material/admin_panel_settings:", url_path="administration"),
            impact,
        ],
    }
    nav = st.navigation(menus[user.role])
    ui.sidebar(user)

nav.run()
