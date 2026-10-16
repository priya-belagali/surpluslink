"""Central configuration. Override anything with environment variables or a .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
PHOTO_DIR = DATA_DIR / "photos"
DATA_DIR.mkdir(exist_ok=True)
PHOTO_DIR.mkdir(exist_ok=True)

DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'app.db'}")
TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Kolkata")

# Matching
OFFER_TIMEOUT_MIN = int(os.getenv("OFFER_TIMEOUT_MIN", "15"))
MAX_MATCH_RADIUS_KM = float(os.getenv("MAX_MATCH_RADIUS_KM", "30"))
VOLUNTEER_RADIUS_KM = 25.0

# Food must be picked up at least this long before it stops being safe
PICKUP_BUFFER_MIN = 30
MIN_PICKUP_WINDOW_MIN = 15

# Default admin account (created on first run). CHANGE THE PASSWORD via .env.
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Rough impact estimates - editable assumptions, not measurements
KG_PER_MEAL = 0.4
CO2E_KG_PER_KG_FOOD = 2.5

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
