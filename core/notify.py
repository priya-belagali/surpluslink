"""Notifications: always stored in-app; optionally also sent via Twilio SMS/WhatsApp."""
import os

from core.db import Notification, User


def notify(session, user_id: int, message: str) -> None:
    session.add(Notification(user_id=user_id, message=message[:500]))
    user = session.get(User, user_id)
    if user and user.phone:
        _send_external(user.phone, message)


def _send_external(phone: str, message: str) -> None:
    sid, token, sender = (os.getenv(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM"))
    if not (sid and token and sender):
        return  # not configured: in-app notifications only
    try:
        from twilio.rest import Client  # lazy import so Twilio stays optional

        to = f"whatsapp:{phone}" if sender.startswith("whatsapp:") else phone
        Client(sid, token).messages.create(body=message, from_=sender, to=to)
    except Exception as exc:  # never let a failed alert break the main flow
        print(f"[notify] external send failed: {exc}")
