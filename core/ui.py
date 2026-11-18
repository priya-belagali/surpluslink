"""Shared Streamlit helpers: setup, stylesheet, sidebar, and the small HTML pieces used by the pages.

Everything that comes from a user is escaped with esc() before it goes into HTML.
"""
import html
import time
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import select, update

from core import config, geocode, matching, safety
from core.db import Notification, User, init_db, now, session_scope

APP_NAME = "SurplusLink"
ROLE_LABEL = {"donor": "Food donor", "ngo": "NGO", "volunteer": "Volunteer", "admin": "Administrator"}
STATUS_LABEL = {"open": "Open", "claimed": "Claimed", "picked_up": "In transit",
                "delivered": "Delivered", "expired": "Expired"}
_STATUS_TONE = {"open": "open", "claimed": "claimed", "picked_up": "transit", "delivered": "done", "expired": "muted"}
_last_tick = {"t": 0.0}


def esc(text) -> str:
    return html.escape("" if text is None else str(text), quote=True)


@st.cache_resource
def _boot() -> bool:
    init_db()
    return True


def run_tick(force: bool = False) -> None:
    """Expire stale listings and escalate unanswered offers, at most once per TICK_SECONDS."""
    if force or time.time() - _last_tick["t"] >= config.TICK_SECONDS:
        _last_tick["t"] = time.time()
        with session_scope() as s:
            matching.tick(s)


def setup() -> None:
    """Call once, first, from the entry point."""
    icon = None
    favicon = config.BASE_DIR / "assets" / "favicon.png"
    if favicon.exists():
        from PIL import Image

        icon = Image.open(favicon)
    st.set_page_config(page_title=APP_NAME, page_icon=icon, layout="wide")
    _boot()
    run_tick()
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


# ---------- page furniture ----------

def sidebar(user: User) -> None:
    with st.sidebar:
        status = ""
        if user.role == "ngo":
            status = status_label("delivered" if user.verified else "claimed", "Approved" if user.verified else "Awaiting approval")
        st.markdown(
            f'<div class="acct"><div class="acct-name">{esc(user.display_name)}</div>'
            f'<div class="acct-role">{ROLE_LABEL[user.role]}</div>{status}</div>', unsafe_allow_html=True)
        with session_scope() as s:
            notes = s.scalars(select(Notification).where(Notification.user_id == user.id)
                              .order_by(Notification.id.desc()).limit(8)).all()
        unread = sum(not n.is_read for n in notes)
        with st.expander(f"Notifications ({unread} unread)" if unread else "Notifications", expanded=bool(unread)):
            if not notes:
                st.caption("Nothing yet.")
            for n in notes:
                st.caption(f"{'Unread. ' if not n.is_read else ''}{n.created_at:%d %b, %H:%M}  \n{n.message}")
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
        st.warning("Your NGO account is waiting for administrator approval. You can look around, "
                   "but you cannot claim food until it is approved.")


def figures(items: list[tuple[str, object]]) -> None:
    """A row of labelled numbers separated by hairlines."""
    cells = "".join(f'<div class="fig"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div></div>' for k, v in items)
    st.markdown(f'<div class="figures">{cells}</div>', unsafe_allow_html=True)


# ---------- HTML pieces (single-line strings: indented lines would render as code in markdown) ----------

def status_label(status: str, text: str | None = None) -> str:
    tone = _STATUS_TONE.get(status, "muted")
    return f'<span class="status status-{tone}">{esc(text or STATUS_LABEL.get(status, status))}</span>'


def veg_mark(veg: bool) -> str:
    kind, label = ("veg", "Vegetarian") if veg else ("nonveg", "Non-vegetarian")
    return f'<span class="vm vm-{kind}" role="img" aria-label="{label}" title="{label}"></span>'


def countdown(until: datetime, at: datetime | None = None) -> str:
    secs = int((until - (at or now())).total_seconds())
    if secs <= 0:
        return "expired"
    minutes, seconds = divmod(secs, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def listing_html(l, *, distance_km: float | None = None, show_status: bool = False, show_donor: bool = True,
                 offer_expires: datetime | None = None, at: datetime | None = None) -> str:
    """One listing as a small specification sheet with the safe-time rail underneath."""
    at = at or now()
    total = max((l.safe_until - l.cooked_at).total_seconds(), 1.0)
    left_s = (l.safe_until - at).total_seconds()
    frac = min(max(left_s / total, 0.0), 1.0)
    tone = "ok" if frac >= 0.5 else "warn" if frac >= 0.25 else "bad"
    left_min = int(left_s // 60)
    remaining = "Safe time has ended" if left_min <= 0 else safety.format_minutes(left_min)

    sub = ([esc(l.donor.display_name)] if show_donor else []) + [esc(l.address)]
    spec = [("Meals", str(l.quantity_meals))]
    if distance_km is not None:
        spec.append(("Distance", f"{distance_km:.1f} km"))
    spec.append(("Planning limit", f"{l.safe_until:%H:%M}"))
    if l.status == "open":
        spec.append(("Collect by", f"{l.pickup_by:%H:%M}"))
    if offer_expires is not None:
        spec.append(("Offer expires in", countdown(offer_expires, at)))
    if l.temperature_c is not None:
        spec.append(("Packed at", f"{l.temperature_c:.0f} C"))
    spec_html = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in spec)
    status = f'<div class="lstatus">{status_label(l.status)}</div>' if show_status else ""

    return (
        f'<div class="lrow"><div class="lhead"><div class="ltitle">{veg_mark(l.veg)}<span>{esc(l.title)}</span></div>{status}</div>'
        f'<div class="lsub">{", ".join(sub)}</div><dl class="lspec">{spec_html}</dl>'
        f'<div class="rail rail-{tone}" role="img" aria-label="{frac * 100:.0f} percent of planning time remaining">'
        f'<div style="width:{frac * 100:.0f}%"></div></div>'
        f'<div class="rail-text"><span>Time remaining against the planning limit</span><span>{remaining}</span></div></div>'
    )


def timeline_html(events: list[tuple[datetime, str]], pending=None, at: datetime | None = None) -> str:
    """Journey of a listing. `pending` is the open Offer, shown last with a live countdown."""
    at = at or now()

    def stamp(dt: datetime) -> str:
        return f"{dt:%H:%M:%S}" if dt.date() == at.date() else f"{dt:%d %b %H:%M}"

    items = [f'<li><span class="t">{stamp(t)}</span><span class="e">{esc(text)}</span></li>' for t, text in events]
    if pending is not None:
        items.append(f'<li class="live"><span class="t">Now</span><span class="e">Waiting for {esc(pending.ngo.display_name)}. '
                     f'Offer expires in {countdown(pending.expires_at, at)}</span></li>')
    return f'<ol class="tl">{"".join(items)}</ol>'


# ---------- inputs ----------

def location_input(prefix: str, label: str = "Address", default: tuple[float, float] | None = None):
    """Address search with a manual fallback. Returns (address_text, lat, lon)."""
    addr = st.text_input(label, key=f"{prefix}_addr", placeholder="Building, street, area, city")
    found_key = f"{prefix}_found"
    if st.button("Find on map", key=f"{prefix}_find"):
        res = geocode.geocode(addr)
        if res:
            st.session_state[found_key] = (res["lat"], res["lon"], res["name"], addr)
            st.session_state.pop(f"{prefix}_miss", None)
        else:
            st.session_state.pop(found_key, None)
            st.session_state[f"{prefix}_miss"] = True
    found = st.session_state.get(found_key)
    if found and found[3] != addr:
        st.caption("The address has changed since the last search. Press Find on map again.")
        found = None
    missed = st.session_state.get(f"{prefix}_miss", False)
    if missed and not found:
        st.warning("No match found for that address. Add the area and city, or set the location below.")

    cities = list(config.CITY_PRESETS)
    with st.expander("Choose a city or enter coordinates instead", expanded=bool(missed and not found)):
        city = st.selectbox("City", cities, index=cities.index(config.COVERAGE_CITY), key=f"{prefix}_city")
        start = default if default else config.CITY_PRESETS[city]
        c1, c2 = st.columns(2)
        lat_m = c1.number_input("Latitude", value=float(start[0]), format="%.5f", key=f"{prefix}_lat_{city}")
        lon_m = c2.number_input("Longitude", value=float(start[1]), format="%.5f", key=f"{prefix}_lon_{city}")

    if found:
        lat, lon = found[0], found[1]
        st.caption(f"Matched to: {found[2]}")
        st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}), latitude="lat", longitude="lon", size=40, zoom=14, height=220)
    else:
        lat, lon = lat_m, lon_m
        st.caption(f"No address match is in use. The position is {city} unless you edited the coordinates, "
                   "so distances will be approximate.")
    st.caption(geocode.ATTRIBUTION)
    return addr, lat, lon


def save_photo(uploaded) -> str | None:
    if uploaded is None:
        return None
    ext = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else "jpg"
    path = config.PHOTO_DIR / f"{uuid.uuid4().hex}.{ext}"
    path.write_bytes(uploaded.getbuffer())
    return str(path)
