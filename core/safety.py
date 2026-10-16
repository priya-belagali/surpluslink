"""Food-safety timing.

IMPORTANT: the hours below are conservative illustrative defaults for a demo, NOT legal or
medical advice. Before real-world use, check them against FSSAI guidance (including its
rules on recovery of surplus food) and with your NGO partners.
"""
from datetime import datetime, timedelta

SAFE_HOURS = {
    "Cooked meal (rice, curry, etc.)": 4,
    "Dairy-based dishes": 3,
    "Bakery / snacks": 8,
    "Raw fruits & vegetables": 24,
    "Packaged / sealed food": 72,
}


def compute_safe_until(category: str, cooked_at: datetime) -> datetime:
    return cooked_at + timedelta(hours=SAFE_HOURS.get(category, 3))


def minutes_left(until: datetime, at: datetime) -> int:
    return int((until - at).total_seconds() // 60)


def format_minutes(minutes: int) -> str:
    if minutes <= 0:
        return "expired"
    h, m = divmod(minutes, 60)
    return f"{h}h {m:02d}m left" if h else f"{m}m left"
