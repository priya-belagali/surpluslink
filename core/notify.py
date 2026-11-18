"""Notifications: always stored in-app; optionally also sent through Twilio (SMS or WhatsApp)."""
import os
import re

from core.db import Notification, User


def normalize_phone(raw: str, default_country: str = "+91") -> str:
    """'98450 12345' -> '+919845012345'. Numbers that already start with + are kept."""
    digits = re.sub(r"[^\d+]", "", raw or "")
    if digits.startswith("+"):
        return digits
    digits = digits.lstrip("0")
    return default_country + digits if digits else ""


def notify(session, user_id: int, message: str) -> None:
    session.add(Notification(user_id=user_id, message=message[:500]))
    user = session.get(User, user_id)
    if user and user.phone:
        _send_external(user.phone, message)


def _send_external(phone: str, message: str) -> tuple[bool, str]:
    """Returns (sent, detail). Quietly does nothing when Twilio is not configured."""
    sid, token, sender = (os.getenv(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM"))
    if not (sid and token and sender):
        return False, "Twilio is not configured, so only in-app alerts are used."
    to = normalize_phone(phone)
    if not to:
        return False, "No valid phone number."
    try:
        from twilio.rest import Client  # lazy import so Twilio stays optional

        target = f"whatsapp:{to}" if sender.startswith("whatsapp:") else to
        Client(sid, token).messages.create(body=message[:1500], from_=sender, to=target)
        return True, f"Sent to {to}."
    except Exception as exc:  # never let a failed alert break the main flow
        print(f"[notify] external send failed: {exc}")
        return False, f"Sending failed: {exc}"


def send_test(phone: str) -> tuple[bool, str]:
    return _send_external(phone, "SurplusLink test message. If you can read this, alerts are working.")
