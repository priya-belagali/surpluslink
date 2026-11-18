"""Download kitchens and venues around the coverage city from OpenStreetMap and cache them.

Run from the project folder, with internet access:   py scripts/fetch_places.py
The Coverage page reads data/places.json. Public Overpass servers are sometimes busy: try again later.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config, places  # noqa: E402

if __name__ == "__main__":
    print(f"Fetching places within {config.COVERAGE_RADIUS_KM} km of {config.COVERAGE_CITY}...")
    try:
        count = places.refresh()
    except RuntimeError as exc:
        print(exc)
        sys.exit(1)
    print(f"Saved {count} places to {config.PLACES_FILE}")
