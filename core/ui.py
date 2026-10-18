"""Shared Streamlit helpers: setup, theme CSS, sidebar account block and small HTML components.

All text that comes from users is escaped with esc() before it is placed in HTML.
"""
import html
import time
import uuid
from pathlib import Path

import streamlit as st
from sqlalchemy import select, update

from core import config, matching, safety
from core.db import Notification, User, init_db, now, session_scope

APP_NAME = "SurplusLink"
ROLE_LABEL = {"donor": "Food donor", "ngo": "NGO", "volunteer": "Volunteer", "admin": "Administrator"}
STATUS_LABEL = {"open": "Open", "claimed": "Claimed", "picked_up": "In transit",
                "delivered": "Delivered", "expired": "Expired"}
_STATUS_TONE = {"open": "open", "claimed": "claimed", "picked_up": "transit",
                "delivered": "done", "expired": "muted"}
_last_tick = {"t": 0.0}


def esc(text) -> str:
    return html.escape("" if text is None else str(text), quote=True)


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


def setup() -> None:
    """Call once, first, from the entry point."""
    st.set_page_config(page_title=APP_NAME, page_icon=":material/volunteer_activism:", layout="wide")
    _boot()
    _maybe_tick()
    css = Path(__file__).with_name("style.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ---------- session ----------

def current_user() -> User | None:
    uid = st.session_state.get("user_id")
    if not uid:
        return None
    with session_scope() as s:
        return s.get(User, uid)


def logout() -> None:
    st.session_state.pop("user_id", None)


def require_role(user: User | None, roles: list[str]) -> None:
    if user is None or (user.role not in roles and user.role != "admin"):
        st.error("You do not have access to this page.")
        st.stop()


# ---------- chrome ----------

def sidebar(user: User) -> None:
    with st.sidebar:
        chip = ""
        if user.role == "ngo":
            chip = badge("Verified", "done") if user.verified else badge("Pending approval", "claimed")
        st.markdown(
            f'<div class="acct"><div class="acct-name">{esc(user.display_name)}</div>'
            f'<div class="acct-role">{ROLE_LABEL[user.role]}</div>{chip}</div>',
            unsafe_allow_html=True,
        )
        with session_scope() as s:
            notes = s.scalars(
                select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(8)
            ).all()
        unread = sum(not n.is_read for n in notes)
        with st.expander(f"Notifications ({unread} new)" if unread else "Notifications", expanded=bool(unread)):
            if not notes:
                st.caption("No notifications yet.")
            for n in notes:
                prefix = "**New** " if not n.is_read else ""
                st.caption(f"{prefix}{n.created_at:%d %b, %H:%M}  \n{n.message}")
            if unread and st.button("Mark all as read", key="mark_read"):
                with session_scope() as s:
                    s.execute(update(Notification).where(Notification.user_id == user.id).values(is_read=True))
                st.rerun()
        if st.button("Sign out"):
            logout()
            st.rerun()


def page_header(title: str, subtitle: str | None = None) -> None:
    sub = f"<p>{esc(subtitle)}</p>" if subtitle else ""
    st.markdown(f'<div class="ph"><h1>{esc(title)}</h1>{sub}</div>', unsafe_allow_html=True)


def verification_notice(user: User) -> None:
    if user.role == "ngo" and not user.verified:
        st.warning(
            "Your NGO account is waiting for administrator approval. "
            "You can sign in and look around, but you cannot claim food until it is approved."
        )


# ---------- HTML components (single-line strings: indented lines would render as code in markdown) ----------

def badge(label: str, tone: str) -> str:
    return f'<span class="badge badge-{tone}">{esc(label)}</span>'


def status_badge(status: str) -> str:
    return badge(STATUS_LABEL.get(status, status), _STATUS_TONE.get(status, "muted"))


def veg_mark(veg: bool) -> str:
    kind, label = ("veg", "Vegetarian") if veg else ("nonveg", "Non-vegetarian")
    return f'<span class="vm vm-{kind}" role="img" aria-label="{label}" title="{label}"></span>'


def listing_html(l, *, distance_km: float | None = None, badge_html: str = "", show_donor: bool = True, at=None) -> str:
    """Title, quantity, meta line and the safe-time rail for one listing."""
    at = at or now()
    total = max((l.safe_until - l.cooked_at).total_seconds(), 1.0)
    left_s = (l.safe_until - at).total_seconds()
    frac = min(max(left_s / total, 0.0), 1.0)
    tone = "ok" if frac >= 0.5 else "warn" if frac >= 0.25 else "bad"
    left_min = int(left_s // 60)
    safe_txt = "Safe time has ended" if left_min <= 0 else f"Safe until {l.safe_until:%H:%M}"
    remaining = "" if left_min <= 0 else safety.format_minutes(left_min)

    meta = ([esc(l.donor.display_name)] if show_donor else []) + [esc(l.address)]
    if distance_km is not None:
        meta.append(f"{distance_km:.1f} km away")
    meta_html = "".join(f"<span>{m}</span>" for m in meta)

    collect = ""
    if l.status == "open":
        collect = (f'<div class="collect">Collect by {l.pickup_by:%H:%M} '
                   f'({safety.format_minutes(safety.minutes_left(l.pickup_by, at))})</div>')

    return (
        f'<div class="lcard"><div class="lcard-top">'
        f'<div class="lcard-title">{veg_mark(l.veg)}<span>{esc(l.title)}</span></div>'
        f'<div class="lcard-side"><span class="lcard-qty"><b>{l.quantity_meals}</b> meals</span>{badge_html}</div></div>'
        f'<div class="lmeta">{meta_html}</div>'
        f'<div class="rail rail-{tone}" role="img" aria-label="{frac * 100:.0f} percent of safe time remaining">'
        f'<div style="width:{frac * 100:.0f}%"></div></div>'
        f'<div class="rail-text"><span>{safe_txt}</span><span>{remaining}</span></div>{collect}</div>'
    )


# ---------- inputs ----------

def location_input(prefix: str, default: tuple[float, float] | None = None) -> tuple[float, float]:
    """Nearest-city preset plus editable coordinates."""
    choice = st.selectbox("Nearest city", list(config.CITY_PRESETS), key=f"{prefix}_city")
    start = default if default else config.CITY_PRESETS[choice]
    with st.expander("Exact coordinates"):
        st.caption("Matching is based on distance, so exact coordinates give better results. "
                   "In Google Maps, right-click your location to copy its latitude and longitude.")
        c1, c2 = st.columns(2)
        # The key includes the city so the numbers reset when the city changes.
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
