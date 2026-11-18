"""Address search using the public OpenStreetMap Nominatim service.

Its usage policy asks for: at most one request per second, an identifying User-Agent, cached
results, and visible attribution. No bulk lookups and no search-as-you-type.
"""
import json
import threading
import time
import urllib.parse
import urllib.request

from core import config

ATTRIBUTION = "Address search by OpenStreetMap Nominatim. Map data from OpenStreetMap contributors."
_lock = threading.Lock()
_last_call = [0.0]


def _user_agent() -> str:
    return f"SurplusLink/1.0 ({config.GEOCODE_CONTACT or 'student project'})"


def parse_result(data) -> dict | None:
    """Turn a Nominatim /search response into {lat, lon, name}, or None."""
    if not data:
        return None
    first = data[0]
    try:
        return {"lat": float(first["lat"]), "lon": float(first["lon"]), "name": str(first.get("display_name", ""))}
    except (KeyError, TypeError, ValueError):
        return None


def _load_cache() -> dict:
    try:
        return json.loads(config.GEOCODE_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_cache(cache: dict) -> None:
    try:
        config.GEOCODE_CACHE.write_text(json.dumps(cache), encoding="utf-8")
    except OSError:
        pass


def geocode(query: str) -> dict | None:
    q = " ".join((query or "").split())
    if len(q) < 4:
        return None
    key = q.lower()
    cache = _load_cache()
    if key in cache:
        return cache[key]

    with _lock:  # keep to one request per second across all visitors
        wait = 1.1 - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        params = urllib.parse.urlencode({"q": q, "format": "jsonv2", "limit": 1, "countrycodes": "in"})
        req = urllib.request.Request(f"https://nominatim.openstreetmap.org/search?{params}",
                                     headers={"User-Agent": _user_agent(), "Accept-Language": "en"})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.load(resp)
        except Exception as exc:
            print(f"[geocode] lookup failed: {exc}")
            return None

    result = parse_result(data)
    if result:
        cache[key] = result
        _save_cache(cache)
    return result
