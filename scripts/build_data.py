"""Build the JSON dataset used by the PaleoIMAGING interactive map.

The Excel workbook remains the source dataset. Institution coordinates are
resolved automatically using public geocoding services and cached locally so
subsequent builds do not repeat successful requests.

Geocoding order:
1. Photon
2. Nominatim / OpenStreetMap

No API key is required.
"""

from __future__ import annotations

from pathlib import Path
import json

import pandas as pd
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim, Photon


ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = ROOT / "ListOfInsitutionalInventory.xlsx"
OUTPUT_DIR = ROOT / "data"
OUTPUT_FILE = OUTPUT_DIR / "institutions.json"
CACHE_FILE = OUTPUT_DIR / "geocoding_cache.json"

SHEET_NAME = "Inventory"

COLUMN_MAP = {
    "Laboratory": "laboratory",
    "Institution": "institution",
    "Country": "country",
    "Contact person": "contact_person",
    "Email": "email",
    "Inventory (equipment)": "equipment",
    "Available protocols": "available_protocols",
    "Interlaboratory comparison readiness": "interlaboratory_comparison_readiness",
    "other instruments from other institutes available": "other_instruments",
}

USER_AGENT = (
    "PaleoIMAGING-Techniques-Map/1.0 "
    "(https://github.com/PaleoIMAGING-DataFormats/PaleoIMAGING-Techniques-Map)"
)


def clean_value(value):
    """Convert pandas missing values to None and trim text fields."""
    if pd.isna(value):
        return None

    if isinstance(value, str):
        value = value.strip()
        return value or None

    return value


def load_cache() -> dict:
    """Load previously resolved coordinates."""
    if not CACHE_FILE.exists():
        return {}

    try:
        with CACHE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        print(f"Warning: could not read cache file: {CACHE_FILE}")
        return {}


def save_cache(cache: dict) -> None:
    """Persist the geocoding cache."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)


def make_cache_key(institution: str | None, country: str | None) -> str:
    """Create a stable cache key for one institution."""
    return f"{institution or ''} | {country or ''}".strip().casefold()


def build_queries(record: dict) -> list[str]:
    """Build increasingly specific search queries for one record."""
    institution = record.get("institution")
    laboratory = record.get("laboratory")
    country = record.get("country")

    queries: list[str] = []

    if institution and country:
        queries.append(f"{institution}, {country}")
    elif institution:
        queries.append(institution)

    if laboratory and institution and country:
        queries.append(f"{laboratory}, {institution}, {country}")
    elif laboratory and country:
        queries.append(f"{laboratory}, {country}")

    # Remove duplicates while preserving order.
    return list(dict.fromkeys(queries))


def location_to_result(location, query: str, provider: str) -> dict:
    """Convert a geopy Location into our JSON-compatible structure."""
    return {
        "latitude": float(location.latitude),
        "longitude": float(location.longitude),
        "geocoded_name": location.address,
        "geocoding_query": query,
        "geocoding_provider": provider,
        "geocoding_status": "ok",
    }


def try_provider(
    provider_name: str,
    geocode,
    queries: list[str],
) -> dict | None:
    """Try all queries against one geocoding provider."""
    for query in queries:
        try:
            location = geocode(query)
        except (GeocoderTimedOut, GeocoderServiceError) as exc:
            print(f"  {provider_name} error for '{query}': {exc}")
            continue

        if location is not None:
            return location_to_result(location, query, provider_name)

    return None


def geocode_record(
    record: dict,
    photon_geocode,
    nominatim_geocode,
    cache: dict,
) -> dict:
    """Resolve one institution with Photon, then Nominatim as fallback."""
    institution = record.get("institution")
    country = record.get("country")
    cache_key = make_cache_key(institution, country)

    # Reuse only successful cached results. Older "not_found" cache entries are
    # deliberately retried so Photon can resolve records that Nominatim missed.
    cached = cache.get(cache_key)
    if cached and cached.get("geocoding_status") == "ok":
        # Backward compatibility with caches created by older script versions.
        # Older entries may not include geocoding_provider.
        cached.setdefault("geocoding_provider", "cache")
        return cached

    queries = build_queries(record)

    if not queries:
        result = {
            "latitude": None,
            "longitude": None,
            "geocoded_name": None,
            "geocoding_query": None,
            "geocoding_provider": None,
            "geocoding_status": "missing_query",
        }
        cache[cache_key] = result
        return result

    result = try_provider("photon", photon_geocode, queries)

    if result is None:
        result = try_provider("nominatim", nominatim_geocode, queries)

    if result is None:
        result = {
            "latitude": None,
            "longitude": None,
            "geocoded_name": None,
            "geocoding_query": queries[0],
            "geocoding_provider": None,
            "geocoding_status": "not_found",
        }

    cache[cache_key] = result
    save_cache(cache)
    return result


def main() -> None:
    """Read the inventory, geocode institutions, and export JSON."""
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}\n"
            "Make sure ListOfInsitutionalInventory.xlsx is in the repository root."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(INPUT_FILE, sheet_name=SHEET_NAME)
    df = df.dropna(how="all")

    missing_columns = [column for column in COLUMN_MAP if column not in df.columns]
    if missing_columns:
        missing = "\n - ".join(missing_columns)
        raise ValueError(
            "The spreadsheet is missing expected columns:\n"
            f" - {missing}\n\n"
            f"Columns found: {list(df.columns)}"
        )

    df = df[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)

    photon = Photon(
        user_agent=USER_AGENT,
        timeout=10,
    )
    nominatim = Nominatim(
        user_agent=USER_AGENT,
        timeout=10,
    )

    # Keep requests polite to public services.
    photon_geocode = RateLimiter(
        photon.geocode,
        min_delay_seconds=1.0,
        swallow_exceptions=False,
    )
    nominatim_geocode = RateLimiter(
        nominatim.geocode,
        min_delay_seconds=1.1,
        swallow_exceptions=False,
    )

    cache = load_cache()
    records = []

    total = len(df)

    for index, (_, row) in enumerate(df.iterrows(), start=1):
        record = {key: clean_value(value) for key, value in row.items()}

        if not record["institution"] and not record["laboratory"]:
            continue

        label = record.get("institution") or record.get("laboratory")
        country = record.get("country") or "country unknown"

        print(f"[{index}/{total}] {label} ({country})")

        geo = geocode_record(
            record,
            photon_geocode,
            nominatim_geocode,
            cache,
        )
        record.update(geo)

        if geo["geocoding_status"] == "ok":
            provider = geo.get("geocoding_provider") or "cache"
            print(
                f"  -> {geo['latitude']:.5f}, {geo['longitude']:.5f} "
                f"[{provider}]"
            )
        else:
            print("  -> coordinates not found")

        records.append(record)

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    save_cache(cache)

    geocoded_count = sum(
        1 for record in records if record["geocoding_status"] == "ok"
    )
    unresolved_count = len(records) - geocoded_count

    print()
    print(f"Read {len(records)} institutional records.")
    print(f"Geocoded: {geocoded_count}")
    print(f"Unresolved: {unresolved_count}")
    print(f"Created: {OUTPUT_FILE}")
    print(f"Cache: {CACHE_FILE}")

    if unresolved_count:
        print(
            "\nSome institutions could not be geocoded automatically. "
            "Check entries with geocoding_status='not_found' in "
            "data/institutions.json."
        )


if __name__ == "__main__":
    main()
