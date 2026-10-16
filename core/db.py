"""Database models and session helpers (SQLAlchemy 2.x, SQLite by default)."""
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from core import config


def now() -> datetime:
    """Current local time as a naive datetime (the app assumes a single region)."""
    return datetime.now(ZoneInfo(config.TIMEZONE)).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    org_name: Mapped[str | None] = mapped_column(String(160), default=None)
    role: Mapped[str] = mapped_column(String(20))  # donor | ngo | volunteer | admin
    phone: Mapped[str | None] = mapped_column(String(32), default=None)
    address: Mapped[str | None] = mapped_column(String(300), default=None)
    lat: Mapped[float | None] = mapped_column(Float, default=None)
    lon: Mapped[float | None] = mapped_column(Float, default=None)
    capacity_meals: Mapped[int] = mapped_column(default=0)  # NGOs: meals they can handle at once
    has_vehicle: Mapped[bool] = mapped_column(Boolean, default=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    @property
    def display_name(self) -> str:
        return self.org_name or self.name


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    donor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80))
    veg: Mapped[bool] = mapped_column(Boolean, default=True)
    quantity_meals: Mapped[int] = mapped_column(default=1)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    event_type: Mapped[str | None] = mapped_column(String(60), default=None)
    address: Mapped[str] = mapped_column(String(300))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    cooked_at: Mapped[datetime] = mapped_column(DateTime)
    safe_until: Mapped[datetime] = mapped_column(DateTime)
    pickup_by: Mapped[datetime] = mapped_column(DateTime)
    photo_path: Mapped[str | None] = mapped_column(String(300), default=None)

    # open -> claimed -> picked_up -> delivered   (or open -> expired)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    ngo_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    volunteer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    visible_to_all: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    donor: Mapped[User] = relationship(foreign_keys=[donor_id], lazy="joined")
    ngo: Mapped[User | None] = relationship(foreign_keys=[ngo_id], lazy="joined")
    volunteer: Mapped[User | None] = relationship(foreign_keys=[volunteer_id], lazy="joined")


class Offer(Base):
    """A priority offer of one listing to one NGO. Used for the escalation chain."""

    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    ngo_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | accepted | declined | expired | cancelled
    offered_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    message: Mapped[str] = mapped_column(String(500))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


engine = create_engine(
    config.DB_URL,
    connect_args={"check_same_thread": False} if config.DB_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope():
    """Commit on success, roll back on error, always close."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    from core.auth import ensure_admin

    Base.metadata.create_all(engine)
    with session_scope() as session:
        ensure_admin(session)
