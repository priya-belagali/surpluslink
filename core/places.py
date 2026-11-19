"""Coverage data: kitchens and venues from OpenStreetMap, cached to data/places.json.

Fetch once with internet access (`py scripts/fetch_places.py`), then the Coverage page works offline.
"""
import json
import urllib.parse
import urllib.request
from datetime import datetime

from core import config

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def build_query(lat: float, lon: float, radius_km: float) -> str:
    r = int(radius_km * 1000)
    return (
        "[out:json][timeout:60];(\n"
        f'  nwr["amenity"~"^(restaurant|fast_food|canteen|food_court|cafe)$"](around:{r},{lat},{lon});\n'
        f'  nwr["tourism"~"^(hotel|guest_house|hostel)$"](around:{r},{lat},{lon});\n'
        f'  nwr["amenity"~"^(events_venue|community_centre|social_centre)$"](around:{r},{lat},{lon});\n'
        ");\nout center tags;"
    )


def classify(tags: dict) -> str:
    amenity, tourism = tags.get("amenity", ""), tags.get("tourism", "")
    if tourism in ("hotel", "guest_house", "hostel"):
        return "Hotel or lodging"
    if amenity in ("events_venue", "community_centre", "social_centre"):
        return "Event hall or venue"
    if amenity == "canteen":
        return "Canteen"
    return "Restaurant or cafe"


def parse_elements(data: dict) -> list[dict]:
    places = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        if lat is None or lon is None:
            continue
        places.append({"name": tags.get("name", ""), "kind": classify(tags), "lat": float(lat), "lon": float(lon)})
    return places


def fetch(lat: float, lon: float, radius_km: float, urls=OVERPASS_URLS, timeout: int = 90) -> list[dict]:
    """Try each public Overpass server in turn. Raises RuntimeError if all fail."""
    body = urllib.parse.urlencode({"data": build_query(lat, lon, radius_km)}).encode()
    ua = f"SurplusLink/1.0 ({config.GEOCODE_CONTACT or 'student project'})"
    errors = []
    for url in urls:
        try:
            req = urllib.request.Request(url, data=body, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return parse_elements(json.load(resp))
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("All Overpass servers failed. " + " | ".join(errors))


def save(places: list[dict], city: str, radius_km: float) -> None:
    payload = {"fetched_at": datetime.now().isoformat(timespec="seconds"), "city": city, "radius_km": radius_km,
               "source": "OpenStreetMap contributors (ODbL)", "places": places}
    config.PLACES_FILE.write_text(json.dumps(payload), encoding="utf-8")


def load() -> dict | None:
    try:
        return json.loads(config.PLACES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def refresh() -> int:
    """Fetch for the configured coverage city and cache it. Returns the number of places."""
    lat, lon = config.CITY_PRESETS[config.COVERAGE_CITY]
    places = fetch(lat, lon, config.COVERAGE_RADIUS_KM)
    save(places, config.COVERAGE_CITY, config.COVERAGE_RADIUS_KM)
    return len(places)
"""Coverage data: kitchens and venues from OpenStreetMap, cached to data/places.json.

Fetch once with internet access (`py scripts/fetch_places.py`), then the Coverage page works offline.
"""
import json
import urllib.parse
import urllib.request
from datetime import datetime

from core import config

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def build_query(lat: float, lon: float, radius_km: float) -> str:
    r = int(radius_km * 1000)
    return (
        f"[out:json][timeout:45];(\n"
        f'  nwr["amenity"~"^(restaurant|fast_food|canteen|food_court|cafe)$"](around:{r},{lat},{lon});\n'
        f'  nwr["tourism"~"^(hotel|guest_house|hostel)$"](around:{r},{lat},{lon});\n'
        f'  nwr["amenity"~"^(events_venue|community_centre|social_centre)$"](around:{r},{lat},{lon});\n'
        ");\nout center tags;"
    )


def classify(tags: dict) -> str:
    amenity, tourism = tags.get("amenity", ""), tags.get("tourism", "")
    if tourism in ("hotel", "guest_house", "hostel"):
        return "Hotel or lodging"
    if amenity in ("events_venue", "community_centre", "social_centre"):
        return "Event hall or venue"
    if amenity == "canteen":
        return "Canteen"
    return "Restaurant or cafe"


def parse_elements(data: dict) -> list[dict]:
    places = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        if lat is None or lon is None:
            continue
        places.append({
            "name": tags.get("name", ""),
            "kind": classify(tags),
            "lat": float(lat),
            "lon": float(lon),
        })
    return places


def fetch(lat: float, lon: float, radius_km: float, urls=OVERPASS_URLS, timeout: int = 35) -> list[dict]:
    """Try each public Overpass server in turn. Raises RuntimeError if all fail."""
    body = urllib.parse.urlencode({"data": build_query(lat, lon, radius_km)}).encode("utf-8")
    ua = f"SurplusLink/1.0 ({config.GEOCODE_CONTACT or 'student project'})"
    headers = {
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    errors = []
    for url in urls:
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return parse_elements(json.load(resp))
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("All Overpass servers failed. " + " | ".join(errors))


def save(places: list[dict], city: str, radius_km: float) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "city": city,
        "radius_km": radius_km,
        "source": "OpenStreetMap contributors (ODbL)",
        "places": places,
    }
    config.PLACES_FILE.write_text(json.dumps(payload), encoding="utf-8")


def load() -> dict | None:
    try:
        return json.loads(config.PLACES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def refresh() -> int:
    """Fetch for the configured coverage city and cache it. Returns the number of places."""
    lat, lon = config.CITY_PRESETS[config.COVERAGE_CITY]
    places = fetch(lat, lon, config.COVERAGE_RADIUS_KM)
    save(places, config.COVERAGE_CITY, config.COVERAGE_RADIUS_KM)
    return len(places)
