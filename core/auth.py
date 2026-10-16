"""Registration and login. Passwords are salted PBKDF2 hashes (never stored in plain text)."""
import hashlib
import hmac
import os

from sqlalchemy import select

from core import config
from core.db import User

_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split("$")
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return hmac.compare_digest(digest.hex(), hash_hex)


def register_user(session, *, email: str, password: str, name: str, role: str, **extra) -> User:
    email = email.strip().lower()
    if role not in ("donor", "ngo", "volunteer"):
        raise ValueError("Invalid role.")
    if "@" not in email or "." not in email:
        raise ValueError("Please enter a valid email address.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    if not name.strip():
        raise ValueError("Please enter your name.")
    if session.scalar(select(User).where(User.email == email)):
        raise ValueError("An account with this email already exists.")

    user = User(
        email=email,
        password_hash=hash_password(password),
        name=name.strip(),
        role=role,
        verified=(role != "ngo"),  # NGOs must be approved by an admin before claiming food
        **extra,
    )
    session.add(user)
    session.flush()
    return user


def authenticate(session, email: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.email == email.strip().lower()))
    if user and verify_password(password, user.password_hash):
        return user
    return None


def ensure_admin(session) -> None:
    email = config.ADMIN_EMAIL.lower()
    if session.scalar(select(User).where(User.email == email)):
        return
    session.add(
        User(
            email=email,
            password_hash=hash_password(config.ADMIN_PASSWORD),
            name="Administrator",
            role="admin",
            verified=True,
        )
    )
