"""Shared Streamlit helpers: page setup, login gate, sidebar, location widget."""
import time
import uuid

import streamlit as st
from sqlalchemy import select, update

from core import config, matching
from core.db import Notification, User, init_db, session_scope

APP_NAME = "SurplusLink"
_last_tick = {"t": 0.0}


@st.cache_resource
def _boot() -> bool:
    init_db()
    return True


def _maybe_tick() -> None:
    """Run housekeeping at most every 30 s. worker.py does the same if you run it separately."""
    if time.time() - _last_tick["t"] > 30:
        _last_tick["t"] = time.time()
        with session_scope() as s:
            matching.tick(s)


def setup(title: str, icon: str = "🍲") -> None:
    st.set_page_config(page_title=f"{title} · {APP_NAME}", page_icon=icon, layout="wide")
    _boot()
    _maybe_tick()


def current_user() -> User | None:
    uid = st.session_state.get("user_id")
    if not uid:
        return None
    with session_scope() as s:
        return s.get(User, uid)


def logout() -> None:
    st.session_state.pop("user_id", None)


def sidebar(user: User) -> None:
    with st.sidebar:
        st.markdown(f"**{user.display_name}**  \n`{user.role}`" + ("" if user.verified else " · ⏳ pending verification"))
        with session_scope() as s:
            notes = s.scalars(
                select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(8)
            ).all()
        unread = sum(not n.is_read for n in notes)
        with st.expander(f"🔔 Notifications ({unread} new)", expanded=bool(unread)):
            if not notes:
                st.caption("Nothing yet.")
            for n in notes:
                st.caption(f"{'🆕 ' if not n.is_read else ''}{n.created_at:%d %b %H:%M} · {n.message}")
            if unread and st.button("Mark all read", key="mark_read"):
                with session_scope() as s:
                    s.execute(update(Notification).where(Notification.user_id == user.id).values(is_read=True))
                st.rerun()
        if st.button("Log out"):
            logout()
            st.rerun()


def start(title: str, roles: list[str] | None = None, icon: str = "🍲") -> User:
    """Standard page opener: setup, require login, optional role check. Stops the page if it fails."""
    setup(title, icon)
    user = current_user()
    if user is None:
        st.warning("Please log in from the Home page first.")
        st.page_link("Home.py", label="Go to Home / Login", icon="🏠")
        st.stop()
    sidebar(user)
    if roles and user.role not in roles and user.role != "admin":
        st.error(f"This page is for: {', '.join(roles)}. You are logged in as {user.role}.")
        st.stop()
    return user


def location_input(prefix: str, default: tuple[float, float] | None = None) -> tuple[float, float]:
    """City preset + editable coordinates. Tip: right-click a spot in Google Maps to copy its lat/lon."""
    cities = list(config.CITY_PRESETS)
    choice = st.selectbox("Nearest city (sets the starting coordinates)", cities, key=f"{prefix}_city")
    start = default if default else config.CITY_PRESETS[choice]
    c1, c2 = st.columns(2)
    # The widget key includes the city so the coordinates reset when the city changes.
    lat = c1.number_input("Latitude", value=float(start[0]), format="%.5f", key=f"{prefix}_lat_{choice}")
    lon = c2.number_input("Longitude", value=float(start[1]), format="%.5f", key=f"{prefix}_lon_{choice}")
    return lat, lon


def save_photo(uploaded) -> str | None:
    if uploaded is None:
        return None
    ext = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else "jpg"
    path = config.PHOTO_DIR / f"{uuid.uuid4().hex}.{ext}"
    path.write_bytes(uploaded.getbuffer())
    return str(path)
