"""Central configuration. Override anything with environment variables or a .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


DATA_DIR = BASE_DIR / "data"
PHOTO_DIR = DATA_DIR / "photos"
DATA_DIR.mkdir(exist_ok=True)
PHOTO_DIR.mkdir(exist_ok=True)
PLACES_FILE = DATA_DIR / "places.json"
GEOCODE_CACHE = DATA_DIR / "geocode_cache.json"

DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'app.db'}")
TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Kolkata")

# Matching and escalation. OFFER_TIMEOUT_SEC wins if set; use 90 for a quick on-stage demo.
OFFER_TIMEOUT_MIN = int(os.getenv("OFFER_TIMEOUT_MIN", "15"))
OFFER_TIMEOUT_SEC = int(os.getenv("OFFER_TIMEOUT_SEC", str(OFFER_TIMEOUT_MIN * 60)))
TICK_SECONDS = int(os.getenv("TICK_SECONDS", "10"))
MAX_MATCH_RADIUS_KM = float(os.getenv("MAX_MATCH_RADIUS_KM", "30"))
VOLUNTEER_RADIUS_KM = 25.0

# DEMO_MODE=true lets every verified NGO see and claim every open listing right away,
# which switches the priority-offer cascade off. Leave it off when you want to show the cascade.
DEMO_MODE = _flag("DEMO_MODE")
# SEED_DEMO_ON_EMPTY=true fills an empty database with clearly labelled demo accounts and history.
SEED_DEMO_ON_EMPTY = _flag("SEED_DEMO_ON_EMPTY")

# Food must be picked up at least this long before the planning limit for its type
PICKUP_BUFFER_MIN = 30
MIN_PICKUP_WINDOW_MIN = 15

# Default admin account (created on first run). CHANGE THE PASSWORD via .env.
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Rough impact estimates: editable assumptions, not measurements
KG_PER_MEAL = 0.4
CO2E_KG_PER_KG_FOOD = 2.5

# Address search (OpenStreetMap Nominatim asks for an identifying contact in the User-Agent)
GEOCODE_CONTACT = os.getenv("GEOCODE_CONTACT", "")

# Coverage map
COVERAGE_CITY = os.getenv("COVERAGE_CITY", "Mysuru")
COVERAGE_RADIUS_KM = float(os.getenv("COVERAGE_RADIUS_KM", "8"))

CITY_PRESETS = {
    "Bengaluru": (12.9716, 77.5946),
    "Mysuru": (12.2958, 76.6394),
    "Chennai": (13.0827, 80.2707),
    "Hyderabad": (17.3850, 78.4867),
    "Mumbai": (19.0760, 72.8777),
    "Pune": (18.5204, 73.8567),
    "Delhi": (28.6139, 77.2090),
    "Kolkata": (22.5726, 88.3639),
}
