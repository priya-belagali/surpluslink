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


BUNDLED_FILE = config.BASE_DIR / "assets" / "places.json"  # a copy committed to Git, so a deployed site has data too


def _first(d: dict, *names):
    for n in names:
        if d.get(n) not in (None, ""):
            return d[n]
    return None


def normalise(data) -> dict | None:
    """Accept a places file made by the fetch script or by hand.

    Handles a plain list of places as well as the full format, alternative key names (latitude, lng, type...),
    missing keys (given sensible defaults) and bad entries (dropped). Returns None if nothing usable is left.
    """
    if isinstance(data, list):
        data = {"places": data}
    if not isinstance(data, dict):
        return None
    cleaned = []
    for p in data.get("places") or []:
        if not isinstance(p, dict):
            continue
        try:
            cleaned.append({"name": str(_first(p, "name", "title") or ""),
                            "kind": str(_first(p, "kind", "type", "category") or "Other"),
                            "lat": float(_first(p, "lat", "latitude")),
                            "lon": float(_first(p, "lon", "lng", "long", "longitude"))})
        except (TypeError, ValueError):
            continue
    if not cleaned:
        return None
    try:
        radius = float(data.get("radius_km") or config.COVERAGE_RADIUS_KM)
    except (TypeError, ValueError):
        radius = config.COVERAGE_RADIUS_KM
    return {"fetched_at": str(data.get("fetched_at") or "unknown"), "city": str(data.get("city") or config.COVERAGE_CITY),
            "radius_km": radius, "source": str(data.get("source") or "not stated"), "places": cleaned}


def load_with_report() -> tuple[dict | None, str]:
    """Like load(), plus a plain sentence saying what was found, so a missing map can be diagnosed from the page."""
    problems = []
    for path in (config.PLACES_FILE, BUNDLED_FILE):
        try:
            raw = path.read_text(encoding="utf-8-sig")  # also accepts files saved with a byte-order mark
        except OSError:
            continue
        try:
            result = normalise(json.loads(raw))
        except ValueError as exc:
            problems.append(f"{path.name} is not valid JSON ({exc})")
            continue
        if result:
            return result, f"Read {len(result['places'])} places from {path.parent.name}/{path.name}."
        problems.append(f"{path.parent.name}/{path.name} was found but has no entries with a latitude and longitude")
    return None, ("; ".join(problems) + ".") if problems else "No places file was found in data/ or assets/."


def load() -> dict | None:
    """Read the cached coverage data: the fetched copy in data/ first, then the copy bundled in assets/."""
    return load_with_report()[0]


def refresh() -> int:
    """Fetch for the configured coverage city and cache it. Returns the number of places."""
    lat, lon = config.CITY_PRESETS[config.COVERAGE_CITY]
    places = fetch(lat, lon, config.COVERAGE_RADIUS_KM)
    save(places, config.COVERAGE_CITY, config.COVERAGE_RADIUS_KM)
    return len(places)
